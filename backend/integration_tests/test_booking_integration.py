"""Booking behavior and actual persisted atomicity on disposable PostgreSQL."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from careflow.accounts import provision
from careflow.booking_schema import appointments, audit, proposals, retries
from careflow.catalog_fixtures import DOCTORS, load_catalog
from careflow.database import database_engine
from careflow.fixtures import apply_fixtures
from careflow.main import app
from careflow.schedule_operator import run_operation
from careflow.schedule_schema import slots
from careflow.scheduling import ZONE
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, func, select, text


def test_specialty_eligibility_stays_locked_until_booking_commit(clinic: UUID) -> None:
    from careflow.booking import confirm
    from careflow.catalog_schema import specialties
    from careflow.identity_api import COOKIE
    from sqlalchemy.exc import OperationalError

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        token = str(client.cookies.get(COOKIE))
    checked, resume = Event(), Event()

    def after_query(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        many: bool,
    ) -> None:
        if statement.startswith("SELECT specialties.active"):
            checked.set()
            assert resume.wait(timeout=2)

    engine = database_engine()
    event.listen(Engine, "after_cursor_execute", after_query)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                confirm,
                str(review["proposal_token"]),
                "locked-specialty",
                token,
                headers["X-CSRF-Token"],
            )
            try:
                assert checked.wait(timeout=2)
                with (
                    pytest.raises(OperationalError) as caught,
                    engine.begin() as writer,
                ):
                    writer.execute(select(specialties).with_for_update(nowait=True))
                assert getattr(caught.value.orig, "sqlstate", None) == "55P03"
            finally:
                resume.set()
            result, replay = future.result(timeout=10)
        assert result["status"] == "booked" and not replay
    finally:
        event.remove(Engine, "after_cursor_execute", after_query)
        engine.dispose()


def test_session_expiring_while_waiting_for_doctor_lock_cannot_book(
    clinic: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from careflow import identity
    from careflow.booking import confirm
    from careflow.catalog_schema import doctors
    from careflow.identity import IdentityError
    from careflow.identity_api import COOKIE
    from careflow.identity_schema import sessions

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        token = str(client.cookies.get(COOKIE))
    waiting = Event()

    def before_query(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        many: bool,
    ) -> None:
        if statement.startswith("SELECT doctors.") and "FOR UPDATE" in statement:
            waiting.set()

    def attempt() -> str:
        try:
            confirm(
                str(review["proposal_token"]),
                "expired-in-lock",
                token,
                headers["X-CSRF-Token"],
            )
            return "created"
        except IdentityError as error:
            return error.code

    engine = database_engine()
    try:
        with engine.connect() as connection:
            expiry = connection.scalar(
                select(sessions.c.expires_at).where(
                    sessions.c.token_hash == identity.token_hash(token)
                )
            )
        assert isinstance(expiry, datetime)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with engine.begin() as blocker:
                blocker.execute(
                    select(doctors).where(doctors.c.id == DOCTOR).with_for_update()
                )
                event.listen(Engine, "before_cursor_execute", before_query)
                future = pool.submit(attempt)
                assert waiting.wait(timeout=2)
                monkeypatch.setattr(identity, "now", lambda: expiry)
            assert future.result(timeout=10) == "AUTH_REQUIRED"
        assert counts() == [0, 0, 0]
    finally:
        event.remove(Engine, "before_cursor_execute", before_query)
        engine.dispose()


@pytest.mark.parametrize(
    "race",
    ["same-slot", "same-key", "same-proof", "same-key-changed-proof", "scoped-key"],
)
def test_independent_connection_booking_races(clinic: UUID, race: str) -> None:
    from careflow.booking import confirm
    from careflow.identity import IdentityError
    from careflow.identity_api import COOKIE

    with (
        TestClient(app, base_url=ORIGIN) as one,
        TestClient(app, base_url=ORIGIN) as two,
    ):
        first_headers = login(one)
        first = propose(one, clinic, first_headers)
        token_one = str(one.cookies.get(COOKIE))
        if race in {"same-key", "same-proof"}:
            second, token_two, second_headers = first, token_one, first_headers
        else:
            second_headers = login(
                two, EMAIL if race == "same-key-changed-proof" else OTHER
            )
            token_two = str(two.cookies.get(COOKIE))
            target = clinic
            if race in {"same-key-changed-proof", "scoped-key"}:
                engine = database_engine()
                try:
                    with engine.connect() as connection:
                        candidate = connection.scalar(
                            select(slots.c.id).where(slots.c.id != clinic)
                        )
                    assert isinstance(candidate, UUID)
                    target = candidate
                finally:
                    engine.dispose()
            second = propose(two, target, second_headers)
    barrier = Barrier(2)

    def attempt(index: int) -> str:
        proof = first if index == 0 else second
        key = "shared" if index == 0 or race != "same-proof" else "different"
        token = token_one if index == 0 else token_two
        headers = first_headers if index == 0 else second_headers
        barrier.wait(timeout=10)
        try:
            _, replay = confirm(
                str(proof["proposal_token"]), key, token, headers["X-CSRF-Token"]
            )
            return "replayed" if replay else "created"
        except IdentityError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(attempt, (0, 1)))
    expected = {
        "same-slot": ["SLOT_UNAVAILABLE", "created"],
        "same-key": ["created", "replayed"],
        "same-proof": ["PROPOSAL_CONSUMED", "created"],
        "same-key-changed-proof": ["IDEMPOTENCY_CONFLICT", "created"],
        "scoped-key": ["created", "created"],
    }
    assert outcomes == expected[race]
    assert counts() == ([2, 2, 2] if race == "scoped-key" else [1, 1, 1])


@pytest.mark.parametrize("edit", ["schedule", "exception", "fee", "reset", "logout"])
def test_booking_races_maintenance_and_session_revocation(
    clinic: UUID, edit: str
) -> None:
    from careflow.booking import confirm
    from careflow.catalog_schema import doctors
    from careflow.identity import IdentityError, patient_identity, sign_out
    from careflow.identity_api import COOKIE

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        token = str(client.cookies.get(COOKIE))
    engine = database_engine()
    try:
        with engine.connect() as connection:
            slot = (
                connection.execute(select(slots).where(slots.c.id == clinic))
                .mappings()
                .one()
            )
        barrier = Barrier(2)

        def booking() -> str:
            barrier.wait(timeout=10)
            try:
                confirm(
                    str(review["proposal_token"]),
                    "racing-edit",
                    token,
                    headers["X-CSRF-Token"],
                )
                return "created"
            except IdentityError as error:
                return error.code

        def maintenance() -> str:
            barrier.wait(timeout=10)
            try:
                if edit == "schedule":
                    run_operation(
                        "deactivate-schedule",
                        DOCTOR,
                        {"id": str(SCHEDULE), "expected_version": 1},
                        confirmed=True,
                    )
                elif edit == "exception":
                    run_operation(
                        "exception",
                        DOCTOR,
                        {
                            "id": str(uuid4()),
                            "expected_version": 0,
                            "start_at": slot["start_at"].isoformat(),
                            "end_at": slot["end_at"].isoformat(),
                            "reason": "Synthetic closure",
                        },
                        confirmed=True,
                    )
                elif edit == "fee":
                    with engine.begin() as connection:
                        connection.execute(
                            doctors.update()
                            .where(doctors.c.id == DOCTOR)
                            .values(consultation_fee="2800.00")
                        )
                elif edit == "reset":
                    provision(
                        EMAIL,
                        "Synthetic-Replacement-Password!",
                        confirmed=True,
                        reset=True,
                    )
                else:
                    sign_out(token, headers["X-CSRF-Token"])
                return "changed"
            except ValueError as error:
                assert "Booked appointments" in str(error)
                return "protected"

        with ThreadPoolExecutor(max_workers=2) as pool:
            booked = pool.submit(booking)
            changed = pool.submit(maintenance)
            outcome, change = booked.result(timeout=30), changed.result(timeout=30)
        if edit in {"schedule", "exception"}:
            assert (outcome, change) in {
                ("created", "protected"),
                ("SLOT_UNAVAILABLE", "changed"),
            }
        elif edit == "fee":
            assert outcome in {"created", "STATE_CHANGED"} and change == "changed"
        else:
            assert outcome in {"created", "AUTH_REQUIRED"} and change == "changed"
            with pytest.raises(IdentityError):
                patient_identity(token)
        expected = 1 if outcome == "created" else 0
        assert counts() == [expected] * 3
        if expected:
            with engine.connect() as connection:
                assert (
                    str(connection.scalar(select(appointments.c.accepted_fee)))
                    == "2500.00"
                )
    finally:
        engine.dispose()


def test_proposal_eligibility_is_rechecked_against_schedule_window(
    clinic: UUID,
) -> None:
    from careflow.schedule_schema import schedules

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        engine = database_engine()
        try:
            with engine.begin() as connection:
                # A persisted slot alone cannot authorize booking if its source
                # window no longer covers it, even without a version advance.
                connection.execute(
                    schedules.update().values(local_start="10:00", local_end="11:00")
                )
            response = client.post(
                "/appointments",
                json={"proposal_token": review["proposal_token"]},
                headers={**headers, "Idempotency-Key": "window-changed"},
            )
            assert response.status_code == 409
            assert counts() == [0, 0, 0]
        finally:
            engine.dispose()


ORIGIN = "https://testserver"
EMAIL = "patient.one@careflow.example.invalid"
OTHER = "patient.two@careflow.example.invalid"
PASSWORD = "Synthetic-Booking-Only-Password!"
DOCTOR = UUID(str(DOCTORS[0]["id"]))
SCHEDULE = UUID(int=903)


@pytest.fixture
def clinic(
    disposable_database: None, monkeypatch: pytest.MonkeyPatch
) -> Iterator[UUID]:
    monkeypatch.setenv("AUTH_ORIGIN", ORIGIN)
    command.upgrade(Config("alembic.ini"), "head")
    apply_fixtures("load", confirmed=True)
    load_catalog(confirmed=True)
    provision(EMAIL, PASSWORD, confirmed=True)
    provision(OTHER, PASSWORD, confirmed=True)
    day = datetime.now(ZONE).date() + timedelta(days=1)
    run_operation(
        "schedule",
        DOCTOR,
        {
            "id": str(SCHEDULE),
            "expected_version": 0,
            "weekday": day.weekday(),
            "local_start": "09:00",
            "local_end": "10:00",
            "effective_from": day.isoformat(),
            "effective_to": day.isoformat(),
        },
        confirmed=True,
    )
    run_operation("generate", DOCTOR, {}, confirmed=True)
    engine = database_engine()
    try:
        with engine.connect() as connection:
            slot_id = connection.scalar(
                select(slots.c.id).order_by(slots.c.start_at).limit(1)
            )
        assert isinstance(slot_id, UUID)
        yield slot_id
    finally:
        engine.dispose()


def login(client: TestClient, email: str = EMAIL) -> dict[str, str]:
    pre = client.get("/auth/csrf")
    result = client.post(
        "/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"Origin": ORIGIN, "X-CSRF-Token": pre.json()["csrf_token"]},
    )
    assert result.status_code == 200, result.text
    return {"Origin": ORIGIN, "X-CSRF-Token": result.json()["csrf_token"]}


def propose(
    client: TestClient, slot_id: UUID, headers: dict[str, str]
) -> dict[str, object]:
    result = client.post(
        "/appointments/proposals", json={"slot_id": str(slot_id)}, headers=headers
    )
    assert result.status_code == 201, result.text
    assert result.headers["cache-control"] == "no-store"
    return dict(result.json())


def counts() -> list[int]:
    engine = database_engine()
    try:
        with engine.connect() as connection:
            return [
                int(connection.scalar(select(func.count()).select_from(table)) or 0)
                for table in (appointments, audit, retries)
            ]
    finally:
        engine.dispose()


def test_http_review_confirmation_and_exact_retry_persist_once(clinic: UUID) -> None:
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        assert counts() == [0, 0, 0]
        summary = review["summary"]
        assert isinstance(summary, dict)
        assert summary["fee"] == "2500.00" and summary["currency"] == "PKR"
        assert summary["doctor_name"] == "Synthetic Doctor One"
        assert summary["start_at"].endswith("T09:00:00+05:00")
        assert summary["timezone"] == "Asia/Karachi"
        headers["Idempotency-Key"] = "first-booking"
        body = {"proposal_token": review["proposal_token"]}
        response = client.post("/appointments", json=body, headers=headers)
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "booked"
        assert response.json()["accepted_fee"] == "2500.00"
        replay = client.post("/appointments", json=body, headers=headers)
        assert replay.status_code == 200 and replay.json() == response.json()
        assert counts() == [1, 1, 1]


def test_expiry_boundary_and_successful_retry_after_proof_expiry(
    clinic: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from careflow import booking, identity

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        expiry = datetime.fromisoformat(str(review["expires_at"]))
        monkeypatch.setattr(booking, "now", lambda: expiry)
        monkeypatch.setattr(identity, "now", lambda: expiry)
        result = client.post(
            "/appointments",
            json={"proposal_token": review["proposal_token"]},
            headers={**headers, "Idempotency-Key": "expired"},
        )
        assert (
            result.status_code == 410
            and result.json()["code"] == "CONFIRMATION_EXPIRED"
        )
        assert counts() == [0, 0, 0]
        fresh = propose(client, clinic, headers)
        body = {"proposal_token": fresh["proposal_token"]}
        headers["Idempotency-Key"] = "fresh"
        committed = client.post("/appointments", json=body, headers=headers)
        assert committed.status_code == 201
        later = datetime.fromisoformat(str(fresh["expires_at"]))
        monkeypatch.setattr(booking, "now", lambda: later)
        monkeypatch.setattr(identity, "now", lambda: later)
        replay = client.post("/appointments", json=body, headers=headers)
        assert replay.status_code == 200 and replay.json() == committed.json()
        # New keys cannot reuse consumed proof; same key cannot change proof.
        assert (
            client.post(
                "/appointments",
                json=body,
                headers={**headers, "Idempotency-Key": "other"},
            ).json()["code"]
            == "PROPOSAL_CONSUMED"
        )
        assert (
            client.post(
                "/appointments",
                json={"proposal_token": review["proposal_token"]},
                headers=headers,
            ).json()["code"]
            == "IDEMPOTENCY_CONFLICT"
        )
        assert counts() == [1, 1, 1]


def test_retry_at_24_hours_requires_new_key_and_review_but_cannot_reuse_proof(
    clinic: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from careflow import booking, identity

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        body = {"proposal_token": review["proposal_token"]}
        headers["Idempotency-Key"] = "retained"
        assert (
            client.post("/appointments", json=body, headers=headers).status_code == 201
        )
        engine = database_engine()
        try:
            with engine.connect() as connection:
                boundary = connection.scalar(select(retries.c.replay_until))
            assert isinstance(boundary, datetime)
            monkeypatch.setattr(booking, "now", lambda: boundary)
            monkeypatch.setattr(identity, "now", lambda: boundary)
            # Old session has expired: replay still needs authentication.
            assert (
                client.post("/appointments", json=body, headers=headers).status_code
                == 401
            )
            headers = {**login(client), "Idempotency-Key": "retained"}
            response = client.post("/appointments", json=body, headers=headers)
            assert (
                response.status_code == 409
                and response.json()["code"] == "RETRY_EXPIRED"
            )
            changed = client.post(
                "/appointments", json={"proposal_token": "z" * 43}, headers=headers
            )
            assert changed.status_code == 409
            assert changed.json()["code"] == "RETRY_EXPIRED"
            assert (
                client.post(
                    "/appointments",
                    json=body,
                    headers={**headers, "Idempotency-Key": "another"},
                ).json()["code"]
                == "PROPOSAL_CONSUMED"
            )
            assert counts() == [1, 1, 1]
        finally:
            engine.dispose()


@pytest.mark.parametrize(
    "change,code",
    [
        ("fee", "STATE_CHANGED"),
        ("version", "STATE_CHANGED"),
        ("exception", "SLOT_UNAVAILABLE"),
        ("inactive", "SLOT_UNAVAILABLE"),
    ],
)
def test_confirmation_rejects_changed_authoritative_state(
    clinic: UUID, change: str, code: str
) -> None:
    from careflow.catalog_schema import doctors
    from careflow.fixtures import CLINIC
    from careflow.schedule_schema import exceptions

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        engine = database_engine()
        try:
            with engine.begin() as connection:
                if change == "fee":
                    connection.execute(
                        doctors.update()
                        .where(doctors.c.id == DOCTOR)
                        .values(consultation_fee="2600.00")
                    )
                elif change == "version":
                    connection.execute(
                        doctors.update()
                        .where(doctors.c.id == DOCTOR)
                        .values(schedule_version=doctors.c.schedule_version + 1)
                    )
                elif change == "inactive":
                    connection.execute(
                        slots.update().where(slots.c.id == clinic).values(active=False)
                    )
                else:
                    slot = (
                        connection.execute(select(slots).where(slots.c.id == clinic))
                        .mappings()
                        .one()
                    )
                    connection.execute(
                        exceptions.insert().values(
                            id=uuid4(),
                            doctor_id=DOCTOR,
                            clinic_id=CLINIC["id"],
                            start_at=slot["start_at"],
                            end_at=slot["end_at"],
                            reason="Synthetic closure",
                        )
                    )
            response = client.post(
                "/appointments",
                json={"proposal_token": review["proposal_token"]},
                headers={**headers, "Idempotency-Key": "changed"},
            )
            assert response.status_code == 409 and response.json()["code"] == code
            assert counts() == [0, 0, 0]
            if change == "fee":
                fresh = propose(client, clinic, headers)
                assert (
                    isinstance(fresh["summary"], dict)
                    and fresh["summary"]["fee"] == "2600.00"
                )
                accepted = client.post(
                    "/appointments",
                    json={"proposal_token": fresh["proposal_token"]},
                    headers={**headers, "Idempotency-Key": "fresh-fee"},
                )
                assert (
                    accepted.status_code == 201
                    and accepted.json()["accepted_fee"] == "2600.00"
                )
        finally:
            engine.dispose()


def test_foreign_actor_missing_csrf_and_revoked_session_cannot_confirm(
    clinic: UUID,
) -> None:
    with (
        TestClient(app, base_url=ORIGIN) as one,
        TestClient(app, base_url=ORIGIN) as two,
    ):
        headers = login(one)
        other_headers = {**login(two, OTHER), "Idempotency-Key": "foreign"}
        review = propose(one, clinic, headers)
        body = {"proposal_token": review["proposal_token"]}
        assert (
            two.post("/appointments", json=body, headers=other_headers).status_code
            == 404
        )
        assert (
            one.post(
                "/appointments",
                json=body,
                headers={"Origin": ORIGIN, "Idempotency-Key": "missing-csrf"},
            ).status_code
            == 403
        )
        assert one.post("/auth/logout", headers=headers).status_code == 204
        assert (
            one.post(
                "/appointments",
                json=body,
                headers={**headers, "Idempotency-Key": "revoked"},
            ).status_code
            == 401
        )
        assert counts() == [0, 0, 0]


@pytest.mark.parametrize("disabled", [True, False])
def test_disabled_or_expired_session_cannot_book(clinic: UUID, disabled: bool) -> None:
    from careflow.identity_schema import sessions, users

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        engine = database_engine()
        try:
            with engine.begin() as connection:
                if disabled:
                    connection.execute(users.update().values(active=False))
                else:
                    connection.execute(
                        sessions.update().values(
                            expires_at=datetime.now(UTC) - timedelta(seconds=1)
                        )
                    )
            response = client.post(
                "/appointments",
                json={"proposal_token": review["proposal_token"]},
                headers={**headers, "Idempotency-Key": "invalid-auth"},
            )
            assert response.status_code == 401 and counts() == [0, 0, 0]
        finally:
            engine.dispose()


def test_transaction_failure_rolls_back_proof_booking_retry_and_audit(
    clinic: UUID,
) -> None:
    with TestClient(app, base_url=ORIGIN) as client:
        headers = {**login(client), "Idempotency-Key": "atomic"}
        review = propose(client, clinic, headers)
        body = {"proposal_token": review["proposal_token"]}
        engine = database_engine()
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE FUNCTION fail_booking_audit() RETURNS trigger "
                        "LANGUAGE plpgsql AS $$ BEGIN "
                        "RAISE EXCEPTION 'Injected failure'; END $$"
                    )
                )
                connection.execute(
                    text(
                        "CREATE TRIGGER fail_audit BEFORE INSERT ON booking_audit "
                        "FOR EACH ROW EXECUTE FUNCTION fail_booking_audit()"
                    )
                )
            response = client.post("/appointments", json=body, headers=headers)
            assert (
                response.status_code == 503
                and response.json()["code"] == "BOOKING_UNAVAILABLE"
            )
            assert counts() == [0, 0, 0]
            with engine.begin() as connection:
                assert connection.scalar(select(proposals.c.appointment_id)) is None
                connection.execute(text("DROP TRIGGER fail_audit ON booking_audit"))
                connection.execute(text("DROP FUNCTION fail_booking_audit()"))
            assert (
                client.post("/appointments", json=body, headers=headers).status_code
                == 201
            )
            assert counts() == [1, 1, 1]
        finally:
            engine.dispose()


def test_persisted_patient_clinic_scope_cannot_be_forged(clinic: UUID) -> None:
    from careflow.fixture_schema import clinics, demo_identities
    from careflow.fixtures import CLINIC
    from careflow.identity_schema import patients, users

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        headers = login(client, OTHER)
        engine = database_engine()
        try:
            with engine.begin() as connection:
                foreign = uuid4()
                connection.execute(clinics.insert().values(**{**CLINIC, "id": foreign}))
                persona = dict(
                    connection.execute(
                        select(demo_identities).where(demo_identities.c.email == EMAIL)
                    )
                    .mappings()
                    .one()
                )
                persona.update(
                    id=uuid4(),
                    clinic_id=foreign,
                    email="foreign@careflow.example.invalid",
                )
                connection.execute(demo_identities.insert().values(**persona))
                user_id = connection.scalar(
                    select(users.c.id).where(users.c.email == OTHER)
                )
                connection.execute(
                    patients.update()
                    .where(patients.c.user_id == user_id)
                    .values(demo_identity_id=persona["id"], clinic_id=foreign)
                )
            assert (
                client.post(
                    "/appointments/proposals",
                    json={"slot_id": str(clinic)},
                    headers=headers,
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/appointments",
                    json={"proposal_token": review["proposal_token"]},
                    headers={**headers, "Idempotency-Key": "scope"},
                ).status_code
                == 403
            )
            assert counts() == [0, 0, 0]
        finally:
            engine.dispose()


@pytest.mark.parametrize("invalid", ["invented", "doctor", "specialty", "started"])
def test_proposals_require_actual_active_future_inventory(
    clinic: UUID, invalid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from careflow import booking
    from careflow.catalog_schema import doctors, specialties

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        engine = database_engine()
        try:
            with engine.begin() as connection:
                if invalid == "doctor":
                    connection.execute(doctors.update().values(active=False))
                elif invalid == "specialty":
                    connection.execute(specialties.update().values(active=False))
                elif invalid == "started":
                    start = connection.scalar(
                        select(slots.c.start_at).where(slots.c.id == clinic)
                    )
                    assert isinstance(start, datetime)
                    monkeypatch.setattr(booking, "now", lambda: start)
            response = client.post(
                "/appointments/proposals",
                json={"slot_id": str(uuid4() if invalid == "invented" else clinic)},
                headers=headers,
            )
            assert (
                response.status_code == 409
                and response.json()["code"] == "SLOT_UNAVAILABLE"
            )
            with engine.connect() as connection:
                assert (
                    connection.scalar(select(func.count()).select_from(proposals)) == 0
                )
            assert counts() == [0, 0, 0]
        finally:
            engine.dispose()


def test_booked_inventory_is_hidden_and_conflicting_maintenance_is_atomic(
    clinic: UUID,
) -> None:
    from careflow.schedule_schema import schedules

    with TestClient(app, base_url=ORIGIN) as client:
        headers = {**login(client), "Idempotency-Key": "protected"}
        review = propose(client, clinic, headers)
        accepted = client.post(
            "/appointments",
            json={"proposal_token": review["proposal_token"]},
            headers=headers,
        )
        assert accepted.status_code == 201
        engine = database_engine()
        try:
            with engine.connect() as connection:
                original = dict(
                    connection.execute(select(slots).where(slots.c.id == clinic))
                    .mappings()
                    .one()
                )
                schedule = dict(connection.execute(select(schedules)).mappings().one())
            response = client.get(
                f"/doctors/{DOCTOR}/slots",
                params={
                    "start_at": original["start_at"].isoformat(),
                    "end_at": (original["start_at"] + timedelta(hours=1)).isoformat(),
                },
            )
            assert response.status_code == 200
            assert [item["id"] for item in response.json()["items"]] != [str(clinic)]
            assert str(clinic) not in [item["id"] for item in response.json()["items"]]
            actions: list[tuple[str, dict[str, object]]] = [
                ("deactivate-schedule", {"id": str(SCHEDULE), "expected_version": 1}),
                (
                    "schedule",
                    {
                        "id": str(SCHEDULE),
                        "expected_version": 1,
                        "weekday": schedule["weekday"],
                        "local_start": "10:00",
                        "local_end": "11:00",
                        "effective_from": schedule["effective_from"].isoformat(),
                        "effective_to": schedule["effective_to"].isoformat(),
                    },
                ),
                (
                    "exception",
                    {
                        "id": str(uuid4()),
                        "expected_version": 0,
                        "start_at": original["start_at"].isoformat(),
                        "end_at": original["end_at"].isoformat(),
                        "reason": "Synthetic closure",
                    },
                ),
            ]
            for action, payload in actions:
                with pytest.raises(ValueError, match="Booked appointments"):
                    run_operation(action, DOCTOR, payload, confirmed=True)
            assert run_operation("generate", DOCTOR, {}, confirmed=True) == 0
            with engine.connect() as connection:
                assert (
                    dict(
                        connection.execute(select(slots).where(slots.c.id == clinic))
                        .mappings()
                        .one()
                    )
                    == original
                )
                assert connection.scalar(select(schedules.c.version)) == 1
            assert counts() == [1, 1, 1]
        finally:
            engine.dispose()


def test_database_enforces_capacity_scope_and_immutable_accepted_pricing(
    clinic: UUID,
) -> None:
    from sqlalchemy.exc import IntegrityError

    with TestClient(app, base_url=ORIGIN) as client:
        headers = {**login(client), "Idempotency-Key": "constraints"}
        review = propose(client, clinic, headers)
        assert (
            client.post(
                "/appointments",
                json={"proposal_token": review["proposal_token"]},
                headers=headers,
            ).status_code
            == 201
        )
        engine = database_engine()
        try:
            with engine.connect() as connection:
                original = dict(
                    connection.execute(select(appointments)).mappings().one()
                )
                alternate = connection.scalar(
                    select(slots.c.id).where(slots.c.id != clinic)
                )
            cases: list[tuple[dict[str, object], str]] = [
                ({}, "23505"),
                ({"patient_id": uuid4()}, "23503"),
                ({"doctor_id": UUID(str(DOCTORS[1]["id"]))}, "23503"),
                ({"clinic_id": uuid4()}, "23503"),
                ({"accepted_fee": "-1.00"}, "23514"),
                ({"accepted_fee": "1.001"}, "23514"),
                ({"currency": "USD"}, "23514"),
                ({"status": "cancelled"}, "23514"),
            ]
            for changes, code in cases:
                with (
                    pytest.raises(IntegrityError) as caught,
                    engine.begin() as connection,
                ):
                    connection.execute(
                        appointments.insert().values(
                            **{
                                **original,
                                "id": uuid4(),
                                "slot_id": alternate if changes else clinic,
                                **changes,
                            }
                        )
                    )
                assert getattr(caught.value.orig, "sqlstate", None) == code
            with pytest.raises(IntegrityError) as caught, engine.begin() as connection:
                connection.execute(appointments.update().values(accepted_fee="2800.00"))
            assert getattr(caught.value.orig, "sqlstate", None) == "23514"
            with pytest.raises(IntegrityError) as caught, engine.begin() as connection:
                connection.execute(proposals.update().values(operation="cancel"))
            assert getattr(caught.value.orig, "sqlstate", None) == "23514"
        finally:
            engine.dispose()


def test_booking_schema_round_trip_backfills_existing_patient_scope(
    clinic: UUID,
) -> None:
    from careflow.fixtures import CLINIC
    from careflow.identity_schema import patients

    command.downgrade(Config("alembic.ini"), "0005_scheduling")
    command.upgrade(Config("alembic.ini"), "head")
    engine = database_engine()
    try:
        with engine.connect() as connection:
            assert list(connection.execute(select(patients.c.clinic_id)).scalars()) == [
                CLINIC["id"],
                CLINIC["id"],
            ]
        assert TestClient(app).get("/ready").status_code == 200
    finally:
        engine.dispose()


def test_application_role_can_book_but_cannot_mutate_snapshots_or_provision(
    clinic: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import secrets

    import psycopg
    from careflow.identity import IdentityError
    from psycopg import sql
    from sqlalchemy.exc import ProgrammingError

    owner = database_engine()
    role = "careflow_booking_" + uuid4().hex
    password = secrets.token_urlsafe(32)
    created = False
    try:
        with owner.begin() as connection:
            driver = connection.connection.driver_connection
            assert isinstance(driver, psycopg.Connection)
            driver.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE"
                ).format(sql.Identifier(role), sql.Literal(password))
            )
        created = True
        with owner.begin() as connection:
            for grant in (
                "GRANT USAGE ON SCHEMA public",
                "GRANT SELECT ON alembic_version, users, patients, clinics, doctors, "
                "specialties, doctor_schedules, schedule_exceptions, slots, "
                "appointments, booking_proposals, booking_retries, booking_audit",
                "GRANT SELECT (id, clinic_id, demo_role, is_synthetic) "
                "ON demo_identities",
                "GRANT UPDATE (password_hash) ON users",
                "GRANT SELECT, INSERT, UPDATE, DELETE ON sessions, auth_limits",
                "GRANT INSERT ON appointments, booking_proposals, "
                "booking_retries, booking_audit",
                "GRANT UPDATE (appointment_id) ON booking_proposals",
                "GRANT UPDATE (id) ON patients, demo_identities, clinics, doctors, "
                "specialties, doctor_schedules, slots",
            ):
                connection.execute(text(grant + f' TO "{role}"'))
        monkeypatch.setenv(
            "DATABASE_URL",
            owner.url.set(username=role, password=password).render_as_string(
                hide_password=False
            ),
        )
        with TestClient(app, base_url=ORIGIN) as client:
            headers = {**login(client), "Idempotency-Key": "application-role"}
            review = propose(client, clinic, headers)
            body = {"proposal_token": review["proposal_token"]}
            assert (
                client.post("/appointments", json=body, headers=headers).status_code
                == 201
            )
            assert (
                client.post("/appointments", json=body, headers=headers).status_code
                == 200
            )
        runtime = database_engine()
        try:
            for statement in (
                "UPDATE appointments SET status = 'booked'",
                "DELETE FROM appointments",
                "DELETE FROM booking_audit",
                "DELETE FROM booking_retries",
            ):
                with (
                    pytest.raises(ProgrammingError) as caught,
                    runtime.begin() as connection,
                ):
                    connection.execute(text(statement))
                assert getattr(caught.value.orig, "sqlstate", None) == "42501"
            with pytest.raises(IdentityError):
                provision(
                    EMAIL, "Synthetic-Unauthorized-Reset!", confirmed=True, reset=True
                )
        finally:
            runtime.dispose()
    finally:
        try:
            if created:
                with owner.begin() as connection:
                    connection.execute(text(f'DROP OWNED BY "{role}"'))
                    connection.execute(text(f'DROP ROLE "{role}"'))
        finally:
            owner.dispose()


def test_proof_expires_at_slot_start_even_before_five_minute_deadline(
    clinic: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from careflow import booking

    engine = database_engine()
    try:
        with engine.connect() as connection:
            start = connection.scalar(
                select(slots.c.start_at).where(slots.c.id == clinic)
            )
        assert isinstance(start, datetime)
        monkeypatch.setattr(booking, "now", lambda: start - timedelta(minutes=2))
        with TestClient(app, base_url=ORIGIN) as client:
            headers = login(client)
            review = propose(client, clinic, headers)
            assert datetime.fromisoformat(str(review["expires_at"])) > start
            monkeypatch.setattr(booking, "now", lambda: start)
            response = client.post(
                "/appointments",
                json={"proposal_token": review["proposal_token"]},
                headers={**headers, "Idempotency-Key": "started"},
            )
            assert response.status_code == 410 and counts() == [0, 0, 0]
    finally:
        engine.dispose()


def test_confirmation_validation_and_storage_omit_raw_secrets(
    clinic: UUID,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import json

    from careflow.identity_api import COOKIE

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        review = propose(client, clinic, headers)
        body = {"proposal_token": review["proposal_token"]}
        key = "secret-idempotency-key"
        for extra, code in [
            ({}, 422),
            ({"Idempotency-Key": "bad key"}, 422),
            ({"Idempotency-Key": "valid", "Origin": "https://foreign.invalid"}, 403),
        ]:
            response = client.post(
                "/appointments", json=body, headers={**headers, **extra}
            )
            assert response.status_code == code
            assert response.headers["cache-control"] == "no-store"
        assert (
            client.post(
                "/appointments",
                json={"proposal_token": "z" * 43},
                headers={**headers, "Idempotency-Key": "unknown"},
            ).status_code
            == 404
        )
        headers["Idempotency-Key"] = key
        assert (
            client.post("/appointments", json=body, headers=headers).status_code == 201
        )
        assert (
            client.post(
                "/appointments",
                json=body,
                headers={"Origin": ORIGIN, "Idempotency-Key": key},
            ).status_code
            == 403
        )
        engine = database_engine()
        try:
            with engine.connect() as connection:
                storage = json.dumps(
                    [
                        dict(row)
                        for table in (proposals, retries, audit)
                        for row in connection.execute(select(table)).mappings()
                    ],
                    default=str,
                )
            for secret in (
                str(review["proposal_token"]),
                str(client.cookies.get(COOKIE)),
                headers["X-CSRF-Token"],
                key,
                PASSWORD,
                EMAIL,
            ):
                assert secret not in storage and secret not in caplog.text
        finally:
            engine.dispose()

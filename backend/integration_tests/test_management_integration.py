"""Appointment management on disposable PostgreSQL; no application DB access."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from careflow import booking
from careflow.booking_schema import appointments, audit, proposals, retries
from careflow.database import database_engine
from careflow.main import app
from careflow.management import ChangeAction
from careflow.schedule_operator import run_operation
from careflow.schedule_schema import slots
from careflow.scheduling import ZONE
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from test_booking_integration import DOCTOR, ORIGIN, OTHER, SCHEDULE, login, propose
from test_booking_integration import clinic as clinic


@pytest.fixture(autouse=True)
def management_clock(clinic: UUID, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = database_engine()
    try:
        with engine.connect() as connection:
            start = connection.scalar(
                select(slots.c.start_at).where(slots.c.id == clinic)
            )
        assert isinstance(start, datetime)
        day = start.astimezone(ZONE).date()
        run_operation(
            "schedule",
            DOCTOR,
            {
                "id": str(SCHEDULE),
                "expected_version": 1,
                "weekday": day.weekday(),
                "local_start": "09:00",
                "local_end": "11:00",
                "effective_from": day.isoformat(),
                "effective_to": day.isoformat(),
            },
            confirmed=True,
        )
        run_operation("generate", DOCTOR, {}, confirmed=True)
        monkeypatch.setattr(booking, "now", lambda: start - timedelta(hours=25))
    finally:
        engine.dispose()


def test_listing_returns_owned_booking_and_hides_it_from_other_patient(
    clinic: UUID,
) -> None:
    with TestClient(app, base_url=ORIGIN) as owner:
        headers = {**login(owner), "Idempotency-Key": "listing-booking"}
        review = propose(owner, clinic, headers)
        response = owner.post(
            "/appointments",
            json={"proposal_token": review["proposal_token"]},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        page = owner.get("/appointments?limit=1")
        assert page.status_code == 200, page.text
        assert page.headers["cache-control"] == "no-store"
        assert page.json()["items"] == [response.json()]
        assert page.json()["next_cursor"] is None
    with TestClient(app, base_url=ORIGIN) as other:
        login(other, OTHER)
        assert other.get("/appointments").json() == {"items": [], "next_cursor": None}


def test_confirmed_cancellation_preserves_booking_retry_and_releases_capacity(
    clinic: UUID,
) -> None:
    with TestClient(app, base_url=ORIGIN) as owner:
        headers = {**login(owner), "Idempotency-Key": "original"}
        review = propose(owner, clinic, headers)
        body = {"proposal_token": review["proposal_token"]}
        original = owner.post("/appointments", json=body, headers=headers)
        assert original.status_code == 201
        identifier = original.json()["id"]
        proposal = owner.post(
            f"/appointments/{identifier}/cancel/proposals", json={}, headers=headers
        )
        assert proposal.status_code == 201, proposal.text
        assert owner.get("/appointments").json()["items"][0]["status"] == "booked"
        change_body = {"proposal_token": proposal.json()["proposal_token"]}
        cancel_headers = {**headers, "Idempotency-Key": "cancel"}
        cancelled = owner.post(
            f"/appointments/{identifier}/cancel",
            json=change_body,
            headers=cancel_headers,
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "cancelled"
        assert cancelled.json()["accepted_fee"] == original.json()["accepted_fee"]
        assert (
            owner.post(
                f"/appointments/{identifier}/cancel",
                json=change_body,
                headers=cancel_headers,
            ).json()
            == cancelled.json()
        )
        assert (
            owner.post("/appointments", json=body, headers=headers).json()
            == original.json()
        )
        released = propose(owner, clinic, headers)["summary"]
        assert isinstance(released, dict) and released["slot_id"] == str(clinic)


def test_reschedule_moves_same_appointment_and_retains_original_retry(
    clinic: UUID,
) -> None:
    with TestClient(app, base_url=ORIGIN) as owner:
        headers = {**login(owner), "Idempotency-Key": "book-first"}
        review = propose(owner, clinic, headers)
        book_body = {"proposal_token": review["proposal_token"]}
        original = owner.post("/appointments", json=book_body, headers=headers).json()
        engine = database_engine()
        try:
            with engine.connect() as connection:
                target = connection.scalar(
                    select(slots.c.id).where(slots.c.id != clinic)
                )
        finally:
            engine.dispose()
        identifier = original["id"]
        proposal = owner.post(
            f"/appointments/{identifier}/reschedule/proposals",
            json={"slot_id": str(target)},
            headers=headers,
        )
        assert proposal.status_code == 201, proposal.text
        assert proposal.json()["summary"]["target"]["fee"] == "2500.00"
        assert owner.get("/appointments").json()["items"] == [original]
        moved = owner.post(
            f"/appointments/{identifier}/reschedule",
            json={"proposal_token": proposal.json()["proposal_token"]},
            headers={**headers, "Idempotency-Key": "move"},
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["id"] == identifier
        assert moved.json()["slot_id"] == str(target)
        assert moved.json()["status"] == "booked"
        assert (
            owner.post("/appointments", json=book_body, headers=headers).json()
            == original
        )
        released = propose(owner, clinic, headers)["summary"]
        assert isinstance(released, dict) and released["slot_id"] == str(clinic)


def book(
    client: TestClient, slot_id: UUID, headers: dict[str, str], key: str = "book"
) -> dict[str, Any]:
    review = propose(client, slot_id, headers)
    response = client.post(
        "/appointments",
        json={"proposal_token": review["proposal_token"]},
        headers={**headers, "Idempotency-Key": key},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def other_slot(source: UUID) -> UUID:
    engine = database_engine()
    try:
        with engine.connect() as connection:
            result = connection.scalar(
                select(slots.c.id)
                .where(slots.c.id != source)
                .order_by(slots.c.start_at)
            )
        assert isinstance(result, UUID)
        return result
    finally:
        engine.dispose()


def change_review(
    client: TestClient,
    original: dict[str, Any],
    action: str,
    headers: dict[str, str],
    target: UUID | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/appointments/{original['id']}/{action}/proposals",
        json={} if target is None else {"slot_id": str(target)},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


@pytest.mark.parametrize("action", ["cancel", "reschedule"])
@pytest.mark.parametrize("remaining_us", [-1, 0, 1])
def test_cutoff_exact_boundary_at_review_and_confirmation(
    clinic: UUID, monkeypatch: pytest.MonkeyPatch, action: str, remaining_us: int
) -> None:
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        start = datetime.fromisoformat(original["start_at"])
        # Review one minute before cutoff, then cross it during the five-minute review.
        monkeypatch.setattr(
            booking, "now", lambda: start - timedelta(hours=24, minutes=1)
        )
        target = other_slot(clinic) if action == "reschedule" else None
        review = change_review(client, original, action, headers, target)
        monkeypatch.setattr(
            booking,
            "now",
            lambda: start - timedelta(hours=24, microseconds=remaining_us),
        )
        path = f"/appointments/{original['id']}/{action}"
        result = client.post(
            path,
            json={"proposal_token": review["proposal_token"]},
            headers={**headers, "Idempotency-Key": "boundary"},
        )
        assert result.status_code == (409 if remaining_us < 0 else 200), result.text
        if remaining_us < 0:
            assert result.json()["code"] == "CHANGE_CUTOFF"
            assert client.get("/appointments").json()["items"] == [original]
        # Fresh review checks the cutoff; successful changes have different state.
        # only the rejected branch still has its source booking.
        if remaining_us < 0:
            again = client.post(
                path + "/proposals",
                json={} if target is None else {"slot_id": str(target)},
                headers=headers,
            )
            assert again.status_code == 409 and again.json()["code"] == "CHANGE_CUTOFF"


@pytest.mark.parametrize("action", ["cancel", "reschedule"])
def test_change_proofs_and_retries_are_action_payload_bound(
    clinic: UUID, action: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        TestClient(app, base_url=ORIGIN) as client,
        TestClient(app, base_url=ORIGIN) as other,
    ):
        headers = login(client)
        original = book(client, clinic, headers)
        target = other_slot(clinic) if action == "reschedule" else None
        review = change_review(client, original, action, headers, target)
        path = f"/appointments/{original['id']}/{action}"
        body = {"proposal_token": review["proposal_token"]}
        keyed = {**headers, "Idempotency-Key": "change"}
        foreign = login(other, OTHER)
        assert (
            other.post(
                path, json=body, headers={**foreign, "Idempotency-Key": "foreign"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                path,
                json=body,
                headers={"Origin": ORIGIN, "Idempotency-Key": "no-csrf"},
            ).status_code
            == 403
        )
        opposite = "reschedule" if action == "cancel" else "cancel"
        assert (
            client.post(
                f"/appointments/{original['id']}/{opposite}", json=body, headers=keyed
            ).status_code
            == 404
        )
        assert (
            client.post(
                path, json={"proposal_token": "z" * 43}, headers=keyed
            ).status_code
            == 404
        )
        assert (
            client.post(
                path.replace(original["id"], str(uuid4())), json=body, headers=keyed
            ).status_code
            == 404
        )
        result = client.post(path, json=body, headers=keyed)
        assert result.status_code == 200, result.text
        assert (
            client.post(path, json={"proposal_token": "z" * 43}, headers=keyed).json()[
                "code"
            ]
            == "IDEMPOTENCY_CONFLICT"
        )
        assert (
            client.post(
                path, json=body, headers={**headers, "Idempotency-Key": "fresh"}
            ).json()["code"]
            == "PROPOSAL_CONSUMED"
        )
        committed = booking.now()
        monkeypatch.setattr(booking, "now", lambda: committed + timedelta(minutes=6))
        assert client.post(path, json=body, headers=keyed).json() == result.json()
        monkeypatch.setattr(booking, "now", lambda: committed + timedelta(hours=24))
        assert (
            client.post(path, json=body, headers=keyed).json()["code"]
            == "RETRY_EXPIRED"
        )
        assert (
            client.post(path, json={"proposal_token": "z" * 43}, headers=keyed).json()[
                "code"
            ]
            == "RETRY_EXPIRED"
        )


@pytest.mark.parametrize("action", ["cancel", "reschedule"])
def test_change_proposal_expires_without_mutation(
    clinic: UUID, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        review = change_review(
            client,
            original,
            action,
            headers,
            other_slot(clinic) if action == "reschedule" else None,
        )
        deadline = datetime.fromisoformat(review["expires_at"])
        monkeypatch.setattr(booking, "now", lambda: deadline)
        response = client.post(
            f"/appointments/{original['id']}/{action}",
            json={"proposal_token": review["proposal_token"]},
            headers={**headers, "Idempotency-Key": "expired"},
        )
        assert response.status_code == 410
        assert client.get("/appointments").json()["items"] == [original]


@pytest.mark.parametrize("action", ["cancel", "reschedule"])
def test_audit_failure_rolls_back_complete_change(clinic: UUID, action: str) -> None:
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        review = change_review(
            client,
            original,
            action,
            headers,
            other_slot(clinic) if action == "reschedule" else None,
        )
        engine = database_engine()
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE FUNCTION fail_change() RETURNS trigger "
                        "LANGUAGE plpgsql AS $$ "
                        "BEGIN RAISE EXCEPTION 'synthetic failure'; END $$"
                    )
                )
                connection.execute(
                    text(
                        "CREATE TRIGGER fail_change BEFORE INSERT ON booking_audit "
                        "FOR EACH ROW EXECUTE FUNCTION fail_change()"
                    )
                )
            path = f"/appointments/{original['id']}/{action}"
            body = {"proposal_token": review["proposal_token"]}
            keyed = {**headers, "Idempotency-Key": "rollback"}
            response = client.post(path, json=body, headers=keyed)
            assert response.status_code == 503
            assert client.get("/appointments").json()["items"] == [original]
            with engine.begin() as connection:
                assert connection.scalar(select(func.count()).select_from(retries)) == 1
                assert connection.scalar(select(func.count()).select_from(audit)) == 1
                assert (
                    connection.scalar(
                        select(proposals.c.appointment_id).where(
                            proposals.c.proof_hash
                            == booking.digest(review["proposal_token"])
                        )
                    )
                    is None
                )
                connection.execute(text("DROP TRIGGER fail_change ON booking_audit"))
                connection.execute(text("DROP FUNCTION fail_change()"))
            assert client.post(path, json=body, headers=keyed).status_code == 200
        finally:
            engine.dispose()


@pytest.mark.parametrize(
    "race",
    [
        "cancel-reschedule",
        "two-reschedules",
        "same-key",
        "target-booking",
        "target-exception",
    ],
)
def test_independent_connection_management_races(clinic: UUID, race: str) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from careflow.identity import IdentityError
    from careflow.identity_api import COOKIE
    from careflow.management import confirm_change

    with (
        TestClient(app, base_url=ORIGIN) as client,
        TestClient(app, base_url=ORIGIN) as other,
    ):
        headers = login(client)
        original = book(client, clinic, headers)
        token = str(client.cookies.get(COOKIE))
        target = other_slot(clinic)
        first_action: ChangeAction = (
            "cancel" if race == "cancel-reschedule" else "reschedule"
        )
        first = change_review(
            client,
            original,
            first_action,
            headers,
            target if first_action == "reschedule" else None,
        )
        second = (
            first
            if race == "same-key"
            else change_review(client, original, "reschedule", headers, target)
        )
        other_headers = login(other, OTHER)
        booking_review = propose(other, target, other_headers)
        other_token = str(other.cookies.get(COOKIE))
        engine = database_engine()
        try:
            with engine.connect() as connection:
                target_row = (
                    connection.execute(select(slots).where(slots.c.id == target))
                    .mappings()
                    .one()
                )
        finally:
            engine.dispose()
    barrier = Barrier(2)

    def attempt(index: int) -> str:
        barrier.wait(timeout=10)
        try:
            if index == 1 and race == "target-booking":
                booking.confirm(
                    str(booking_review["proposal_token"]),
                    "contender",
                    other_token,
                    other_headers["X-CSRF-Token"],
                )
            elif index == 1 and race == "target-exception":
                run_operation(
                    "exception",
                    DOCTOR,
                    {
                        "id": str(uuid4()),
                        "expected_version": 0,
                        "start_at": target_row["start_at"].isoformat(),
                        "end_at": target_row["end_at"].isoformat(),
                    },
                    confirmed=True,
                )
            else:
                review = first if index == 0 else second
                action: ChangeAction = first_action if index == 0 else "reschedule"
                key = "same" if race == "same-key" else f"race-{index}"
                confirm_change(
                    UUID(original["id"]),
                    action,
                    review["proposal_token"],
                    key,
                    token,
                    headers["X-CSRF-Token"],
                )
            return "ok"
        except IdentityError as error:
            return error.code
        except ValueError:
            # Confirmed maintenance refuses an exception over a newly booked target.
            return "maintenance-refused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (0, 1)))
    assert outcomes.count("ok") == (2 if race == "same-key" else 1), outcomes
    assert "BOOKING_UNAVAILABLE" not in outcomes, outcomes
    engine = database_engine()
    try:
        with engine.connect() as connection:
            current = (
                connection.execute(
                    select(appointments).where(
                        appointments.c.id == UUID(original["id"])
                    )
                )
                .mappings()
                .one()
            )
            active = (
                connection.execute(
                    select(appointments.c.slot_id).where(
                        appointments.c.status == "booked"
                    )
                )
                .scalars()
                .all()
            )
            assert len(active) == len(set(active))
            actions = connection.scalar(select(func.count()).select_from(audit))
            expected_actions = (
                2 if race != "target-exception" or outcomes[0] == "ok" else 1
            )
            assert actions == expected_actions
            if outcomes[0] == "ok":
                assert current["status"] == (
                    "cancelled" if first_action == "cancel" else "booked"
                )
                assert current["slot_id"] == (
                    clinic if first_action == "cancel" else target
                )
            elif race in {"target-booking", "target-exception"}:
                assert current["slot_id"] == clinic and current["status"] == "booked"
            history = (
                connection.execute(
                    select(audit).where(audit.c.appointment_id == UUID(original["id"]))
                )
                .mappings()
                .all()
            )
            changed = [row for row in history if row["action"] != "book"]
            last = changed[0] if changed else history[0]
            for field in ("status", "accepted_fee", "slot_id"):
                assert last["after_snapshot"][field] == (
                    format(current[field], ".2f")
                    if field == "accepted_fee"
                    else str(current[field])
                )
        with TestClient(app, base_url=ORIGIN) as public:
            available = public.get(
                f"/doctors/{DOCTOR}/slots",
                params={
                    "start_at": original["start_at"],
                    "end_at": target_row["end_at"].isoformat(),
                },
            )
            assert available.status_code == 200, available.text
            expected_free = set()
            if current["status"] == "cancelled" or current["slot_id"] == target:
                expected_free.add(str(clinic))
            if race == "cancel-reschedule" and current["status"] == "cancelled":
                expected_free.add(str(target))
            assert {row["id"] for row in available.json()["items"]} == expected_free
    finally:
        engine.dispose()


def test_upgrade_backfills_exact_booking_retry_before_changes(clinic: UUID) -> None:
    from alembic import command
    from alembic.config import Config

    with TestClient(app, base_url=ORIGIN) as client:
        headers = {**login(client), "Idempotency-Key": "pre-upgrade"}
        review = propose(client, clinic, headers)
        body = {"proposal_token": review["proposal_token"]}
        original = client.post("/appointments", json=body, headers=headers)
        assert original.status_code == 201
        command.downgrade(Config("alembic.ini"), "0006_booking")
        command.upgrade(Config("alembic.ini"), "head")
        replay = client.post("/appointments", json=body, headers=headers)
        assert replay.status_code == 200
        assert replay.json() == original.json()


def test_pagination_filters_and_full_http_management_walkthrough(clinic: UUID) -> None:
    with (
        TestClient(app, base_url=ORIGIN) as client,
        TestClient(app, base_url=ORIGIN) as other,
    ):
        headers = login(client)
        engine = database_engine()
        try:
            with engine.connect() as connection:
                inventory = (
                    connection.execute(select(slots).order_by(slots.c.start_at))
                    .mappings()
                    .all()
                )
            assert client.get("/doctors").status_code == 200
            start, end = inventory[0]["start_at"], inventory[-1]["end_at"]
            params = {"start_at": start.isoformat(), "end_at": end.isoformat()}
            available = client.get(f"/doctors/{DOCTOR}/slots", params=params)
            assert available.status_code == 200 and len(available.json()["items"]) == 4
            first = book(client, clinic, headers, "walk-first")
            review = change_review(client, first, "cancel", headers)
            cancelled = client.post(
                f"/appointments/{first['id']}/cancel",
                json={"proposal_token": review["proposal_token"]},
                headers={**headers, "Idempotency-Key": "walk-cancel"},
            )
            assert cancelled.status_code == 200
            # Another booking, then a separate reviewed move.
            second = book(client, UUID(str(inventory[1]["id"])), headers, "walk-second")
            review = change_review(
                client, second, "reschedule", headers, UUID(str(inventory[2]["id"]))
            )
            moved = client.post(
                f"/appointments/{second['id']}/reschedule",
                json={"proposal_token": review["proposal_token"]},
                headers={**headers, "Idempotency-Key": "walk-move"},
            )
            assert moved.status_code == 200
            foreign_headers = login(other, OTHER)
            foreign = book(
                other, UUID(str(inventory[3]["id"])), foreign_headers, "foreign"
            )
            page = client.get("/appointments", params={"limit": 1}).json()
            assert page["items"] == [cancelled.json()]
            next_page = client.get(
                "/appointments", params={"limit": 1, "cursor": page["next_cursor"]}
            ).json()
            assert next_page == {"items": [moved.json()], "next_cursor": None}
            # The cursor is a position, never identity authority.
            assert other.get(
                "/appointments", params={"cursor": page["next_cursor"]}
            ).json()["items"] == [foreign]
            assert client.get("/appointments", params={"status": "cancelled"}).json()[
                "items"
            ] == [cancelled.json()]
            assert client.get(
                "/appointments",
                params={
                    "start_at": moved.json()["start_at"],
                    "end_at": foreign["start_at"],
                },
            ).json()["items"] == [moved.json()]
            assert (
                client.get(
                    "/appointments", params={"end_at": cancelled.json()["start_at"]}
                ).json()["items"]
                == []
            )
            assert "version" not in str(page) and "proof" not in str(page)
            remaining = client.get(f"/doctors/{DOCTOR}/slots", params=params).json()[
                "items"
            ]
            assert {row["id"] for row in remaining} == {
                str(clinic),
                str(inventory[1]["id"]),
            }
            with engine.connect() as connection:
                history = (
                    connection.execute(
                        select(audit).where(audit.c.action == "reschedule")
                    )
                    .mappings()
                    .one()
                )
                assert history["before_snapshot"]["slot_id"] == second["slot_id"]
                assert history["after_snapshot"]["slot_id"] == moved.json()["slot_id"]
                assert history["before_snapshot"]["accepted_fee"] == "2500.00"
        finally:
            engine.dispose()


@pytest.mark.parametrize(
    "change", ["fee", "version", "inactive", "same-slot", "invented"]
)
def test_target_changes_and_invalid_targets_preserve_original(
    clinic: UUID, change: str
) -> None:
    from careflow.catalog_schema import doctors

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        target = other_slot(clinic)
        path = f"/appointments/{original['id']}/reschedule"
        if change in {"same-slot", "invented"}:
            response = client.post(
                path + "/proposals",
                json={"slot_id": str(clinic if change == "same-slot" else uuid4())},
                headers=headers,
            )
            assert response.status_code == 409
        else:
            review = change_review(client, original, "reschedule", headers, target)
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
                            slots.update()
                            .where(slots.c.id == target)
                            .values(version=slots.c.version + 1)
                        )
                    else:
                        connection.execute(
                            slots.update()
                            .where(slots.c.id == target)
                            .values(active=False)
                        )
            finally:
                engine.dispose()
            response = client.post(
                path,
                json={"proposal_token": review["proposal_token"]},
                headers={**headers, "Idempotency-Key": "stale"},
            )
            assert response.status_code == 409
        assert client.get("/appointments").json()["items"] == [original]
        if change == "fee":
            fresh = change_review(client, original, "reschedule", headers, target)
            assert fresh["summary"]["target"]["fee"] == "2600.00"
            moved = client.post(
                path,
                json={"proposal_token": fresh["proposal_token"]},
                headers={**headers, "Idempotency-Key": "fresh"},
            )
            assert (
                moved.status_code == 200 and moved.json()["accepted_fee"] == "2600.00"
            )


@pytest.mark.parametrize(
    "authority", ["guest", "expired", "reset", "disabled", "foreign-clinic"]
)
def test_lost_authority_blocks_listing_review_confirmation_and_retry(
    clinic: UUID, authority: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from careflow import identity
    from careflow.accounts import provision
    from careflow.fixture_schema import clinics, demo_identities
    from careflow.fixtures import CLINIC
    from careflow.identity_schema import patients, users
    from test_booking_integration import EMAIL, PASSWORD

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        review = change_review(client, original, "cancel", headers)
        path = f"/appointments/{original['id']}/cancel"
        body = {"proposal_token": review["proposal_token"]}
        keyed = {**headers, "Idempotency-Key": "authority"}
        assert client.post(path, json=body, headers=keyed).status_code == 200
        if authority == "guest":
            client.cookies.clear()
        elif authority == "expired":
            current = identity.now()
            monkeypatch.setattr(identity, "now", lambda: current + timedelta(hours=9))
        elif authority == "reset":
            provision(EMAIL, PASSWORD, confirmed=True, reset=True)
        else:
            engine = database_engine()
            try:
                with engine.begin() as connection:
                    if authority == "disabled":
                        connection.execute(
                            users.update()
                            .where(users.c.email == EMAIL)
                            .values(active=False)
                        )
                    else:
                        foreign = uuid4()
                        connection.execute(
                            clinics.insert().values(**{**CLINIC, "id": foreign})
                        )
                        persona = dict(
                            connection.execute(
                                select(demo_identities).where(
                                    demo_identities.c.email == EMAIL
                                )
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
                        # Keep existing appointment references intact.
                        other_id = connection.scalar(
                            select(users.c.id).where(users.c.email == OTHER)
                        )
                        connection.execute(
                            patients.update()
                            .where(patients.c.user_id == other_id)
                            .values(clinic_id=foreign, demo_identity_id=persona["id"])
                        )
            finally:
                engine.dispose()
            if authority == "foreign-clinic":
                headers = login(client, OTHER)
                keyed = {**headers, "Idempotency-Key": "authority"}
        expected = 403 if authority == "foreign-clinic" else 401
        assert client.get("/appointments").status_code == expected
        for action in ("cancel", "reschedule"):
            review_body = (
                {} if action == "cancel" else {"slot_id": str(other_slot(clinic))}
            )
            assert (
                client.post(
                    f"/appointments/{original['id']}/{action}/proposals",
                    json=review_body,
                    headers=headers,
                ).status_code
                == expected
            )
            assert (
                client.post(
                    f"/appointments/{original['id']}/{action}", json=body, headers=keyed
                ).status_code
                == expected
            )


@pytest.mark.parametrize("elapsed", ["cutoff", "session"])
def test_authority_and_cutoff_are_rechecked_after_resource_lock_wait(
    clinic: UUID, elapsed: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from careflow import identity
    from careflow.catalog_schema import doctors
    from careflow.identity import IdentityError
    from careflow.identity_api import COOKIE
    from careflow.management import confirm_change
    from sqlalchemy import Engine, event

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        start = datetime.fromisoformat(original["start_at"])
        monkeypatch.setattr(
            booking, "now", lambda: start - timedelta(hours=24, minutes=1)
        )
        review = change_review(client, original, "cancel", headers)
        token = str(client.cookies.get(COOKIE))
        waiting = Event()

        def observe(
            connection: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: Any,
            many: bool,
        ) -> None:
            if "FROM doctors" in statement and "FOR UPDATE" in statement:
                waiting.set()

        def attempt() -> str:
            try:
                confirm_change(
                    UUID(original["id"]),
                    "cancel",
                    review["proposal_token"],
                    "wait",
                    token,
                    headers["X-CSRF-Token"],
                )
                return "unexpected-success"
            except IdentityError as error:
                return error.code

        engine = database_engine()
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                with engine.begin() as blocker:
                    blocker.execute(
                        select(doctors.c.id)
                        .where(doctors.c.id == DOCTOR)
                        .with_for_update()
                    ).all()
                    event.listen(Engine, "before_cursor_execute", observe)
                    future = pool.submit(attempt)
                    try:
                        assert waiting.wait(timeout=10)
                        if elapsed == "cutoff":
                            monkeypatch.setattr(
                                booking,
                                "now",
                                lambda: (
                                    start
                                    - timedelta(hours=24)
                                    + timedelta(microseconds=1)
                                ),
                            )
                        else:
                            current = identity.now()
                            monkeypatch.setattr(
                                identity, "now", lambda: current + timedelta(hours=9)
                            )
                    finally:
                        event.remove(Engine, "before_cursor_execute", observe)
                assert future.result(timeout=15) == (
                    "CHANGE_CUTOFF" if elapsed == "cutoff" else "AUTH_REQUIRED"
                )
            with engine.connect() as connection:
                row = connection.execute(select(appointments)).mappings().one()
                assert row["status"] == "booked" and row["version"] == 1
                assert connection.scalar(select(func.count()).select_from(audit)) == 1
                assert connection.scalar(select(func.count()).select_from(retries)) == 1
        finally:
            engine.dispose()


def future_doctor_slot(original: dict[str, Any]) -> UUID:
    from careflow.catalog_fixtures import DOCTORS

    target_doctor = UUID(str(DOCTORS[1]["id"]))
    day = datetime.fromisoformat(original["start_at"]).date() + timedelta(days=2)
    run_operation(
        "schedule",
        target_doctor,
        {
            "id": str(uuid4()),
            "expected_version": 0,
            "weekday": day.weekday(),
            "local_start": "00:00",
            "local_end": "01:00",
            "effective_from": day.isoformat(),
            "effective_to": day.isoformat(),
        },
        confirmed=True,
    )
    run_operation("generate", target_doctor, {}, confirmed=True)
    engine = database_engine()
    try:
        with engine.connect() as connection:
            identifier = connection.scalar(
                select(slots.c.id)
                .where(slots.c.doctor_id == target_doctor)
                .order_by(slots.c.start_at)
            )
        assert isinstance(identifier, UUID)
        return identifier
    finally:
        engine.dispose()


def test_cross_doctor_price_history_midnight_cutoff_and_immutable_move_retry(
    clinic: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        target = future_doctor_slot(original)
        review = change_review(client, original, "reschedule", headers, target)
        assert review["summary"]["target"]["fee"] == "3500.50"
        path = f"/appointments/{original['id']}/reschedule"
        body = {"proposal_token": review["proposal_token"]}
        keyed = {**headers, "Idempotency-Key": "cross-doctor"}
        moved = client.post(path, json=body, headers=keyed)
        assert moved.status_code == 200, moved.text
        assert moved.json()["accepted_fee"] == "3500.50"
        assert moved.json()["start_at"].endswith("T00:00:00+05:00")
        review = change_review(client, moved.json(), "cancel", headers)
        cancelled = client.post(
            f"/appointments/{original['id']}/cancel",
            json={"proposal_token": review["proposal_token"]},
            headers={**headers, "Idempotency-Key": "after-move"},
        )
        assert cancelled.status_code == 200
        assert client.post(path, json=body, headers=keyed).json() == moved.json()
        # Cancelled appointments reject fresh actions, without changing history.
        assert (
            client.post(
                path + "/proposals", json={"slot_id": str(clinic)}, headers=headers
            ).json()["code"]
            == "APPOINTMENT_INACTIVE"
        )
        another = book(client, target, headers, "midnight-booking")
        boundary = datetime.fromisoformat(another["start_at"]) - timedelta(hours=24)
        from datetime import UTC

        monkeypatch.setattr(booking, "now", lambda: boundary.astimezone(UTC))
        midnight_review = change_review(client, another, "cancel", headers)
        midnight = client.post(
            f"/appointments/{another['id']}/cancel",
            json={"proposal_token": midnight_review["proposal_token"]},
            headers={**headers, "Idempotency-Key": "midnight-cancel"},
        )
        assert midnight.status_code == 200, midnight.text
        engine = database_engine()
        try:
            with engine.connect() as connection:
                move = (
                    connection.execute(
                        select(audit).where(audit.c.action == "reschedule")
                    )
                    .mappings()
                    .one()
                )
                assert move["before_snapshot"]["accepted_fee"] == "2500.00"
                assert move["after_snapshot"]["accepted_fee"] == "3500.50"
        finally:
            engine.dispose()


def test_target_start_expires_review_even_before_five_minutes(
    clinic: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        future = future_doctor_slot(original)
        review = change_review(client, original, "reschedule", headers, future)
        path = f"/appointments/{original['id']}/reschedule"
        moved = client.post(
            path,
            json={"proposal_token": review["proposal_token"]},
            headers={**headers, "Idempotency-Key": "future"},
        ).json()
        target_start = datetime.fromisoformat(original["start_at"])
        monkeypatch.setattr(booking, "now", lambda: target_start - timedelta(minutes=1))
        review = change_review(client, moved, "reschedule", headers, clinic)
        monkeypatch.setattr(booking, "now", lambda: target_start)
        result = client.post(
            path,
            json={"proposal_token": review["proposal_token"]},
            headers={**headers, "Idempotency-Key": "started"},
        )
        assert result.status_code == 410, result.text
        assert result.json()["code"] == "CONFIRMATION_EXPIRED"
        assert client.get("/appointments").json()["items"] == [moved]


def test_past_booking_rejects_new_changes_without_mutation(
    clinic: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        start = datetime.fromisoformat(original["start_at"])
        monkeypatch.setattr(booking, "now", lambda: start + timedelta(minutes=1))
        for action in ("cancel", "reschedule"):
            response = client.post(
                f"/appointments/{original['id']}/{action}/proposals",
                json={} if action == "cancel" else {"slot_id": str(other_slot(clinic))},
                headers=headers,
            )
            assert (
                response.status_code == 409
                and response.json()["code"] == "CHANGE_CUTOFF"
            )
        assert client.get("/appointments").json()["items"] == [original]

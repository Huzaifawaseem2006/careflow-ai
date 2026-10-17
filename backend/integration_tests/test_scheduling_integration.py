"""Scheduling persistence and independent-connection integrity; disposable PG only."""

import json
import secrets
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from threading import Barrier
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from careflow.catalog_fixtures import DOCTORS, load_catalog
from careflow.database import database_engine
from careflow.fixtures import apply_fixtures
from careflow.main import app
from careflow.scheduling import ZONE
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

pytestmark = pytest.mark.usefixtures("disposable_database")
DOCTOR = UUID(str(DOCTORS[0]["id"]))
SCHEDULE = UUID(int=801)


def setup_catalog() -> dict[str, object]:
    command.upgrade(Config("alembic.ini"), "head")
    apply_fixtures("load", confirmed=True)
    load_catalog(confirmed=True)
    day = datetime.now(ZONE).date() + timedelta(days=1)
    return {
        "id": str(SCHEDULE),
        "expected_version": 0,
        "weekday": day.weekday(),
        "local_start": "09:00",
        "local_end": "10:00",
        "effective_from": day.isoformat(),
        "effective_to": day.isoformat(),
    }


def query_times(payload: dict[str, object]) -> dict[str, str]:
    day = datetime.fromisoformat(str(payload["effective_from"])).date()
    return {
        "start_at": datetime.combine(day, time(), ZONE).isoformat(),
        "end_at": datetime.combine(day + timedelta(days=1), time(), ZONE).isoformat(),
    }


def test_confirmed_generation_is_persisted_repeatable_and_public() -> None:
    from careflow.schedule_operator import run_operation

    payload = setup_catalog()
    with TestClient(app) as client:
        url = f"/doctors/{DOCTOR}/slots"
        assert client.get(url, params=query_times(payload)).json()["items"] == []
        run_operation("schedule", DOCTOR, payload, confirmed=True)
        assert client.get(url, params=query_times(payload)).json()["items"] == []
        assert run_operation("generate", DOCTOR, {}, confirmed=True) == 2
        response = client.get(url, params=query_times(payload))
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2
        assert items[0]["start_at"].endswith("T09:00:00+05:00")
        assert items[0]["end_at"].endswith("T09:30:00+05:00")
        assert items[0]["timezone"] == "Asia/Karachi"
        assert items[0]["version"] == 1
        assert run_operation("generate", DOCTOR, {}, confirmed=True) == 0
        assert client.get(url, params=query_times(payload)).json()["items"] == items
        command.upgrade(Config("alembic.ini"), "head")
        assert client.get("/ready").status_code == 200


def test_postgres_rejects_shifted_overlaps_bad_intervals_and_wrong_references() -> None:
    from careflow.schedule_operator import run_operation
    from careflow.schedule_schema import slots

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    run_operation("generate", DOCTOR, {}, confirmed=True)
    engine = database_engine()
    try:
        with engine.connect() as connection:
            original = dict(
                connection.execute(select(slots).order_by(slots.c.start_at).limit(1))
                .mappings()
                .one()
            )
        for changes, state in (
            (
                {
                    "start_at": original["start_at"] + timedelta(minutes=15),
                    "end_at": original["end_at"] + timedelta(minutes=15),
                },
                "23P01",
            ),
            (
                {"end_at": original["start_at"] + timedelta(hours=2, minutes=15)},
                "23514",
            ),
            ({"end_at": original["start_at"]}, "23514"),
            ({"clinic_id": uuid4()}, "23503"),
            ({"doctor_id": UUID(str(DOCTORS[1]["id"]))}, "23503"),
            ({"version": 0}, "23514"),
            ({"start_at": original["start_at"], "end_at": original["end_at"]}, "23505"),
        ):
            with pytest.raises(IntegrityError) as caught, engine.begin() as connection:
                connection.execute(
                    slots.insert().values(
                        **{
                            **original,
                            "id": uuid4(),
                            "start_at": original["start_at"] + timedelta(hours=2),
                            "end_at": original["end_at"] + timedelta(hours=2),
                            **changes,
                        }
                    )
                )
            assert getattr(caught.value.orig, "sqlstate", None) == state
        with engine.begin() as connection:
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    text("UPDATE slots SET start_at = 'infinity'::timestamptz")
                )
    finally:
        engine.dispose()


def test_shifted_edits_invalidate_old_slots_and_version_reactivated_resources() -> None:
    from careflow.schedule_operator import run_operation

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    run_operation("generate", DOCTOR, {}, confirmed=True)
    with TestClient(app) as client:
        url = f"/doctors/{DOCTOR}/slots"
        original = client.get(url, params=query_times(payload)).json()["items"]
        shifted = {
            **payload,
            "expected_version": 1,
            "local_start": "09:15",
            "local_end": "10:15",
        }
        run_operation("schedule", DOCTOR, shifted, confirmed=True)
        assert client.get(url, params=query_times(payload)).json()["items"] == []
        assert run_operation("generate", DOCTOR, {}, confirmed=True) == 2
        shifted_items = client.get(url, params=query_times(payload)).json()["items"]
        assert shifted_items[0]["start_at"].endswith("T09:15:00+05:00")
        with pytest.raises(ValueError, match="version"):
            run_operation("schedule", DOCTOR, shifted, confirmed=True)
        run_operation(
            "schedule", DOCTOR, {**payload, "expected_version": 2}, confirmed=True
        )
        assert run_operation("generate", DOCTOR, {}, confirmed=True) == 2
        restored = client.get(url, params=query_times(payload)).json()["items"]
        assert [item["id"] for item in restored] == [item["id"] for item in original]
        assert [item["version"] for item in restored] == [3, 3]


def test_exception_invalidation_and_explicit_regeneration() -> None:
    from careflow.schedule_operator import run_operation

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    run_operation("generate", DOCTOR, {}, confirmed=True)
    with TestClient(app) as client:
        url = f"/doctors/{DOCTOR}/slots"
        original = client.get(url, params=query_times(payload)).json()["items"]
        exception = {
            "id": str(UUID(int=901)),
            "expected_version": 0,
            "start_at": original[0]["start_at"],
            "end_at": original[0]["end_at"],
            "reason": "Synthetic operator block",
        }
        run_operation("exception", DOCTOR, exception, confirmed=True)
        assert (
            client.get(url, params=query_times(payload)).json()["items"] == original[1:]
        )
        assert run_operation("generate", DOCTOR, {}, confirmed=True) == 0
        # Moving a block invalidates its new intersection; old slots stay invalid
        # until explicitly generated. Adjacent endpoints do not overlap.
        run_operation(
            "exception",
            DOCTOR,
            {
                **exception,
                "expected_version": 1,
                "start_at": original[1]["start_at"],
                "end_at": original[1]["end_at"],
            },
            confirmed=True,
        )
        assert client.get(url, params=query_times(payload)).json()["items"] == []
        assert run_operation("generate", DOCTOR, {}, confirmed=True) == 1
        run_operation(
            "deactivate-exception",
            DOCTOR,
            {"id": exception["id"], "expected_version": 2},
            confirmed=True,
        )
        assert len(client.get(url, params=query_times(payload)).json()["items"]) == 1
        assert run_operation("generate", DOCTOR, {}, confirmed=True) == 1
        run_operation(
            "deactivate-schedule",
            DOCTOR,
            {"id": payload["id"], "expected_version": 1},
            confirmed=True,
        )
        assert client.get(url, params=query_times(payload)).json()["items"] == []
        assert run_operation("generate", DOCTOR, {}, confirmed=True) == 0


def test_empty_appointment_storage_allows_schedule_maintenance() -> None:
    from careflow.schedule_operator import run_operation
    from careflow.schedule_schema import slots

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    run_operation("generate", DOCTOR, {}, confirmed=True)
    engine = database_engine()
    try:
        with engine.begin() as connection:
            before = list(
                connection.execute(select(slots).order_by(slots.c.id)).mappings()
            )
        assert run_operation("generate", DOCTOR, {}, confirmed=True) == 0
        with engine.connect() as connection:
            assert (
                list(connection.execute(select(slots).order_by(slots.c.id)).mappings())
                == before
            )
        response = TestClient(app).get(
            f"/doctors/{DOCTOR}/slots", params=query_times(payload)
        )
        assert response.status_code == 200 and len(response.json()["items"]) == 2
        run_operation(
            "deactivate-schedule",
            DOCTOR,
            {"id": payload["id"], "expected_version": 1},
            confirmed=True,
        )
        assert (
            TestClient(app)
            .get(f"/doctors/{DOCTOR}/slots", params=query_times(payload))
            .json()["items"]
            == []
        )
    finally:
        engine.dispose()


def test_schedule_writes_and_public_reads_reject_ineligible_clinic_and_doctor() -> None:
    from careflow.catalog_schema import doctors, specialties
    from careflow.fixture_schema import clinics
    from careflow.fixtures import CLINIC
    from careflow.schedule_operator import run_operation

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    run_operation("generate", DOCTOR, {}, confirmed=True)
    engine = database_engine()
    try:
        for table, field, bad, good in (
            (clinics, "timezone", "UTC", "Asia/Karachi"),
            (doctors, "active", False, True),
            (specialties, "active", False, True),
        ):
            with engine.begin() as connection:
                connection.execute(table.update().values({field: bad}))
            with pytest.raises(ValueError, match="Doctor unavailable"):
                run_operation("generate", DOCTOR, {}, confirmed=True)
            response = TestClient(app).get(
                f"/doctors/{DOCTOR}/slots", params=query_times(payload)
            )
            assert response.status_code == 200 and response.json()["items"] == []
            with engine.begin() as connection:
                connection.execute(table.update().values({field: good}))
        client = TestClient(app)
        assert (
            client.get(f"/doctors/{uuid4()}/slots", params=query_times(payload)).json()[
                "items"
            ]
            == []
        )
        assert (
            client.get(
                f"/doctors/{DOCTOR}/slots",
                params={**query_times(payload), "clinic_id": str(uuid4())},
            ).json()["items"]
            == []
        )
        assert (
            len(
                client.get(
                    f"/doctors/{DOCTOR}/slots",
                    params={**query_times(payload), "clinic_id": str(CLINIC["id"])},
                ).json()["items"]
            )
            == 2
        )
    finally:
        engine.dispose()


@pytest.mark.parametrize("competing_action", ["generate", "schedule", "exception"])
def test_competing_generation_and_maintenance_serialize(competing_action: str) -> None:
    from careflow.schedule_operator import run_operation

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    barrier = Barrier(2)
    day = str(payload["effective_from"])
    competing_payload: dict[str, object] = {}
    if competing_action == "schedule":
        competing_payload = {
            **payload,
            "expected_version": 1,
            "local_start": "09:15",
            "local_end": "10:15",
        }
    elif competing_action == "exception":
        competing_payload = {
            "id": str(uuid4()),
            "expected_version": 0,
            "start_at": day + "T09:00:00+05:00",
            "end_at": day + "T09:30:00+05:00",
            "reason": "Synthetic competing block",
        }

    def attempt(action: str, data: dict[str, object]) -> int:
        barrier.wait(timeout=10)
        # Each invocation owns its own NullPool engine/connection/transaction.
        return run_operation(action, DOCTOR, data, confirmed=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        generation = pool.submit(attempt, "generate", {})
        maintenance = pool.submit(attempt, competing_action, competing_payload)
        first, second = generation.result(timeout=20), maintenance.result(timeout=20)
    if competing_action == "generate":
        assert sorted([first, second]) == [0, 2]
    else:
        assert second == 1
    run_operation("generate", DOCTOR, {}, confirmed=True)
    items = (
        TestClient(app)
        .get(f"/doctors/{DOCTOR}/slots", params=query_times(payload))
        .json()["items"]
    )
    assert len(items) == (1 if competing_action == "exception" else 2)
    expected = (
        "09:15"
        if competing_action == "schedule"
        else "09:30"
        if competing_action == "exception"
        else "09:00"
    )
    assert items[0]["start_at"].endswith(f"T{expected}:00+05:00")
    assert len({item["id"] for item in items}) == len(items)


def test_failed_conflicting_edit_rolls_back_slot_and_resource_versions() -> None:
    from careflow.catalog_schema import doctors
    from careflow.schedule_operator import run_operation
    from careflow.schedule_schema import schedules, slots

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    run_operation(
        "schedule",
        DOCTOR,
        {**payload, "id": str(uuid4()), "local_start": "10:00", "local_end": "11:00"},
        confirmed=True,
    )
    run_operation("generate", DOCTOR, {}, confirmed=True)
    engine = database_engine()
    try:
        with engine.connect() as connection:
            before_slots = list(
                connection.execute(select(slots).order_by(slots.c.id)).mappings()
            )
            before_schedules = list(
                connection.execute(
                    select(schedules).order_by(schedules.c.id)
                ).mappings()
            )
            before_version = connection.scalar(
                select(doctors.c.schedule_version).where(doctors.c.id == DOCTOR)
            )
        # Invalidation executes before this conflicting schedule update, so a
        # successful rollback must restore inventory as well as the schedule.
        with pytest.raises(IntegrityError):
            run_operation(
                "schedule",
                DOCTOR,
                {
                    **payload,
                    "expected_version": 1,
                    "local_start": "09:15",
                    "local_end": "10:15",
                },
                confirmed=True,
            )
        with engine.connect() as connection:
            assert (
                list(connection.execute(select(slots).order_by(slots.c.id)).mappings())
                == before_slots
            )
            assert (
                list(
                    connection.execute(
                        select(schedules).order_by(schedules.c.id)
                    ).mappings()
                )
                == before_schedules
            )
            assert (
                connection.scalar(
                    select(doctors.c.schedule_version).where(doctors.c.id == DOCTOR)
                )
                == before_version
            )
    finally:
        engine.dispose()


def test_persisted_horizon_and_half_open_pages_use_karachi_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from careflow import availability, schedule_operator
    from careflow.schedule_operator import run_operation

    payload = setup_catalog()
    fixed = datetime(2026, 10, 17, 7, 15, tzinfo=UTC)  # 12:15 Karachi
    clock = MagicMock(wraps=datetime)
    clock.now.return_value = fixed
    monkeypatch.setattr(schedule_operator, "datetime", clock)
    monkeypatch.setattr(availability, "datetime", clock)
    for weekday in range(7):
        run_operation(
            "schedule",
            DOCTOR,
            {
                **payload,
                "id": str(uuid4()),
                "weekday": weekday,
                "local_start": "12:00",
                "local_end": "13:00",
                "effective_from": "2026-10-16",
                "effective_to": "2026-11-17",
            },
            confirmed=True,
        )
    assert run_operation("generate", DOCTOR, {}, confirmed=True) == 59
    client = TestClient(app)
    params = {
        "start_at": "2026-10-17T00:00:00+05:00",
        "end_at": "2026-11-16T00:00:00+05:00",
        "limit": "100",
    }
    url = f"/doctors/{DOCTOR}/slots"
    items = client.get(url, params=params).json()["items"]
    assert len(items) == 59
    assert items[0]["start_at"] == "2026-10-17T12:30:00+05:00"
    assert items[-1]["end_at"] == "2026-11-15T13:00:00+05:00"
    assert (
        client.get(url, params={**params, "limit": "1", "offset": "1"}).json()["items"]
        == items[1:2]
    )
    assert (
        client.get(
            url,
            params={
                "start_at": "2026-10-18T12:00:00+05:00",
                "end_at": "2026-10-18T12:30:00+05:00",
            },
        ).json()["items"]
        == items[1:2]
    )
    assert run_operation("generate", DOCTOR, {}, confirmed=True) == 0


def test_real_operator_cli_to_public_query_and_safe_input_errors(
    tmp_path: Path,
) -> None:
    payload = setup_catalog()
    source = tmp_path / "schedule.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    base = [sys.executable, "-m", "careflow.schedule_operator"]

    def cli(action: str, *options: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*base, action, "--doctor-id", str(DOCTOR), *options],
            capture_output=True,
            text=True,
            timeout=20,
        )

    assert cli("schedule", "--input", str(source)).returncode == 1
    result = cli("schedule", "--input", str(source), "--confirm-synthetic-schedules")
    assert result.returncode == 0, result.stdout + result.stderr
    assert cli("generate", "--confirm-synthetic-schedules").returncode == 0
    client = TestClient(app)
    assert (
        len(
            client.get(f"/doctors/{DOCTOR}/slots", params=query_times(payload)).json()[
                "items"
            ]
        )
        == 2
    )
    assert client.post(f"/doctors/{DOCTOR}/slots", json=payload).status_code == 405
    source.write_text('{"unexpected":true}', encoding="utf-8")
    result = cli("schedule", "--input", str(source), "--confirm-synthetic-schedules")
    assert result.returncode == 1 and "Traceback" not in result.stderr
    source.write_bytes(b"x" * 16385)
    assert (
        cli(
            "exception", "--input", str(source), "--confirm-synthetic-schedules"
        ).returncode
        == 1
    )


def test_independent_inserts_cannot_commit_overlapping_slots() -> None:
    from careflow.schedule_operator import run_operation
    from careflow.schedule_schema import slots

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    run_operation("generate", DOCTOR, {}, confirmed=True)
    engine = database_engine()
    try:
        with engine.connect() as connection:
            original = dict(connection.execute(select(slots).limit(1)).mappings().one())
        barrier = Barrier(2)

        def insert_shift(minutes: int) -> str:
            try:
                with engine.begin() as connection:
                    barrier.wait(timeout=10)
                    connection.execute(
                        slots.insert().values(
                            **{
                                **original,
                                "id": uuid4(),
                                "start_at": original["start_at"]
                                + timedelta(hours=2, minutes=minutes),
                                "end_at": original["end_at"]
                                + timedelta(hours=2, minutes=minutes),
                            }
                        )
                    )
                return "committed"
            except IntegrityError as error:
                assert getattr(error.orig, "sqlstate", None) == "23P01"
                return "overlap"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(insert_shift, [0, 15]))
        assert sorted(results) == ["committed", "overlap"]
    finally:
        engine.dispose()


def test_read_only_application_role_cannot_mutate_scheduling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from careflow.schedule_operator import run_operation
    from careflow.schedule_schema import exceptions, schedules, slots

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    run_operation("generate", DOCTOR, {}, confirmed=True)
    owner = database_engine()
    role = "careflow_schedule_" + uuid4().hex
    created = False
    try:
        password = secrets.token_urlsafe(32)
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
            connection.execute(text("GRANT USAGE ON SCHEMA public TO " + role))
            connection.execute(
                text(
                    "GRANT SELECT ON clinics, doctors, specialties, doctor_schedules, "
                    "schedule_exceptions, slots, alembic_version TO " + role
                )
            )
            connection.execute(
                text("GRANT SELECT (id, slot_id, status) ON appointments TO " + role)
            )
        monkeypatch.setenv(
            "DATABASE_URL",
            owner.url.set(username=role, password=password).render_as_string(
                hide_password=False
            ),
        )
        client = TestClient(app)
        response = client.get(f"/doctors/{DOCTOR}/slots", params=query_times(payload))
        assert response.status_code == 200 and len(response.json()["items"]) == 2
        with pytest.raises(SQLAlchemyError):
            run_operation("generate", DOCTOR, {}, confirmed=True)
        reader = database_engine()
        try:
            for table in (schedules, exceptions, slots):
                with pytest.raises(SQLAlchemyError), reader.begin() as connection:
                    connection.execute(table.delete())
        finally:
            reader.dispose()
    finally:
        try:
            if created:
                with owner.begin() as connection:
                    connection.execute(text("DROP OWNED BY " + role))
                    connection.execute(text("DROP ROLE " + role))
        finally:
            owner.dispose()


def test_generation_failure_rolls_back_all_inserted_slots() -> None:
    from careflow.schedule_operator import run_operation
    from careflow.schedule_schema import slots

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                text("""
                CREATE FUNCTION reject_second_slot() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                    IF extract(minute FROM NEW.start_at
                               AT TIME ZONE 'Asia/Karachi') = 30 THEN
                        RAISE EXCEPTION 'Synthetic test insert failure';
                    END IF;
                    RETURN NEW;
                END $$
            """)
            )
            connection.execute(
                text(
                    "CREATE TRIGGER reject_second_slot BEFORE INSERT ON slots "
                    "FOR EACH ROW EXECUTE FUNCTION reject_second_slot()"
                )
            )
        with pytest.raises(SQLAlchemyError):
            run_operation("generate", DOCTOR, {}, confirmed=True)
        with engine.begin() as connection:
            assert connection.execute(select(slots)).first() is None
            connection.execute(text("DROP TRIGGER reject_second_slot ON slots"))
            connection.execute(text("DROP FUNCTION reject_second_slot()"))
        assert run_operation("generate", DOCTOR, {}, confirmed=True) == 2
    finally:
        engine.dispose()


def test_missing_overlap_extension_fails_readiness() -> None:
    setup_catalog()
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP EXTENSION btree_gist CASCADE"))
        assert TestClient(app).get("/ready").status_code == 503
    finally:
        engine.dispose()


def test_split_overnight_schedule_persists_adjacent_midnight_slots() -> None:
    from careflow.schedule_operator import run_operation

    payload = setup_catalog()
    tomorrow = datetime.fromisoformat(str(payload["effective_from"])).date()
    next_day = tomorrow + timedelta(days=1)
    run_operation(
        "schedule",
        DOCTOR,
        {**payload, "local_start": "23:30", "local_end": "24:00"},
        confirmed=True,
    )
    run_operation(
        "schedule",
        DOCTOR,
        {
            **payload,
            "id": str(uuid4()),
            "weekday": next_day.weekday(),
            "effective_from": next_day.isoformat(),
            "effective_to": next_day.isoformat(),
            "local_start": "00:00",
            "local_end": "00:30",
        },
        confirmed=True,
    )
    assert run_operation("generate", DOCTOR, {}, confirmed=True) == 2
    params = {
        **query_times(payload),
        "end_at": datetime.combine(
            next_day + timedelta(days=1), time(), ZONE
        ).isoformat(),
    }
    items = (
        TestClient(app).get(f"/doctors/{DOCTOR}/slots", params=params).json()["items"]
    )
    assert len(items) == 2
    assert items[0]["start_at"] == tomorrow.isoformat() + "T23:30:00+05:00"
    assert (
        items[0]["end_at"]
        == items[1]["start_at"]
        == next_day.isoformat() + "T00:00:00+05:00"
    )


def test_competing_edits_reject_stale_version_without_losing_the_winner() -> None:
    from careflow.schedule_operator import run_operation

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    barrier = Barrier(2)

    def edit(start: str, end: str) -> str:
        barrier.wait(timeout=10)
        try:
            run_operation(
                "schedule",
                DOCTOR,
                {
                    **payload,
                    "expected_version": 1,
                    "local_start": start,
                    "local_end": end,
                },
                confirmed=True,
            )
            return start
        except ValueError as error:
            assert "version" in str(error)
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(edit, "10:00", "11:00")
        second = pool.submit(edit, "11:00", "12:00")
        results = [first.result(timeout=20), second.result(timeout=20)]
    assert results.count("stale") == 1
    winner = next(item for item in results if item != "stale")
    run_operation("generate", DOCTOR, {}, confirmed=True)
    items = (
        TestClient(app)
        .get(f"/doctors/{DOCTOR}/slots", params=query_times(payload))
        .json()["items"]
    )
    assert items[0]["start_at"].endswith(f"T{winner}:00+05:00")


def test_foreign_clinic_persisted_slots_cannot_be_read_or_operated() -> None:
    from careflow.catalog_fixtures import SPECIALTIES
    from careflow.catalog_schema import doctors, specialties
    from careflow.fixture_schema import clinics
    from careflow.fixtures import CLINIC
    from careflow.schedule_operator import run_operation
    from careflow.schedule_schema import schedules, slots

    payload = setup_catalog()
    foreign_clinic, foreign_specialty, foreign_doctor, foreign_schedule = [
        uuid4() for _ in range(4)
    ]
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                clinics.insert().values(**{**CLINIC, "id": foreign_clinic})
            )
            connection.execute(
                specialties.insert().values(
                    **{
                        **SPECIALTIES[0],
                        "id": foreign_specialty,
                        "clinic_id": foreign_clinic,
                    }
                )
            )
            connection.execute(
                doctors.insert().values(
                    **{
                        **DOCTORS[0],
                        "id": foreign_doctor,
                        "specialty_id": foreign_specialty,
                        "clinic_id": foreign_clinic,
                    }
                )
            )
            from careflow.schedule_operator import ScheduleInput

            data = ScheduleInput.model_validate(payload).model_dump(
                exclude={"id", "expected_version"}
            )
            connection.execute(
                schedules.insert().values(
                    **data,
                    id=foreign_schedule,
                    doctor_id=foreign_doctor,
                    clinic_id=foreign_clinic,
                )
            )
            start = datetime.fromisoformat(
                str(payload["effective_from"]) + "T09:00:00+05:00"
            )
            connection.execute(
                slots.insert().values(
                    id=uuid4(),
                    clinic_id=foreign_clinic,
                    doctor_id=foreign_doctor,
                    schedule_id=foreign_schedule,
                    start_at=start,
                    end_at=start + timedelta(minutes=30),
                )
            )
        response = TestClient(app).get(
            f"/doctors/{foreign_doctor}/slots",
            params={**query_times(payload), "clinic_id": str(foreign_clinic)},
        )
        assert response.status_code == 200 and response.json()["items"] == []
        with pytest.raises(ValueError, match="Doctor unavailable"):
            run_operation("generate", foreign_doctor, {}, confirmed=True)
    finally:
        engine.dispose()


def test_fixture_repeats_preserve_inventory_and_stale_schema_blocks_writes() -> None:
    from careflow.database import SCHEMA_REVISION
    from careflow.schedule_operator import run_operation
    from careflow.schedule_schema import slots

    payload = setup_catalog()
    run_operation("schedule", DOCTOR, payload, confirmed=True)
    run_operation("generate", DOCTOR, {}, confirmed=True)
    engine = database_engine()
    try:
        with engine.connect() as connection:
            before = list(
                connection.execute(select(slots).order_by(slots.c.id)).mappings()
            )
        apply_fixtures("reset", confirmed=True)
        load_catalog(confirmed=True)
        with engine.begin() as connection:
            assert (
                list(connection.execute(select(slots).order_by(slots.c.id)).mappings())
                == before
            )
            connection.execute(
                text("UPDATE alembic_version SET version_num = '0004_clinic_catalog'")
            )
        with pytest.raises(ValueError, match="Stale schema"):
            run_operation("generate", DOCTOR, {}, confirmed=True)
        assert TestClient(app).get("/ready").status_code == 503
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num = :head"),
                {"head": SCHEMA_REVISION},
            )
        assert TestClient(app).get("/ready").status_code == 200
    finally:
        engine.dispose()

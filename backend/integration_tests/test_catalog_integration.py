"""Public catalog boundaries verified on disposable PostgreSQL only."""

import os
import secrets
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from careflow.accounts import provision
from careflow.catalog_fixtures import DOCTORS, SERVICES, SPECIALTIES, load_catalog
from careflow.catalog_schema import doctors, services, specialties
from careflow.database import database_engine
from careflow.fixture_schema import clinics, demo_identities
from careflow.fixtures import CLINIC, apply_fixtures
from careflow.identity_schema import patients, sessions, users
from careflow.main import app
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import CheckConstraint, inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

pytestmark = pytest.mark.usefixtures("disposable_database")


def test_public_catalog_never_exposes_inactive_or_other_clinic_resources() -> None:
    # Negative boundary first: the caller's clinic filter cannot widen scope.
    command.upgrade(Config("alembic.ini"), "head")
    apply_fixtures("load", confirmed=True)
    load_catalog(confirmed=True)
    engine = database_engine()
    foreign_clinic = UUID(int=999)
    foreign_specialty = UUID(int=998)
    foreign_doctor = UUID(int=997)
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
                        "clinic_id": foreign_clinic,
                        "specialty_id": foreign_specialty,
                    }
                )
            )
            connection.execute(
                doctors.update()
                .where(doctors.c.id == DOCTORS[0]["id"])
                .values(active=False)
            )
        with TestClient(app) as client:
            for identifier in (DOCTORS[0]["id"], foreign_doctor, UUID(int=123)):
                response = client.get(f"/doctors/{identifier}")
                assert response.status_code == 404
                assert response.json()["code"] == "NOT_FOUND"
                assert client.get(f"/doctors/{identifier}/fee").status_code == 404
            assert (
                client.get(
                    "/doctors", params={"clinic_id": str(foreign_clinic)}
                ).json()["items"]
                == []
            )
            assert (
                client.get(
                    "/specialties", params={"clinic_id": str(foreign_clinic)}
                ).json()["items"]
                == []
            )
            assert (
                client.get(
                    "/doctors", params={"specialty_id": str(foreign_specialty)}
                ).json()["items"]
                == []
            )
            assert (
                client.get("/doctors", params={"city": "Lahore"}).json()["items"] == []
            )
            result = client.get("/doctors").json()["items"]
            assert {row["id"] for row in result} == {str(DOCTORS[1]["id"])}
    finally:
        engine.dispose()


def seed() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    apply_fixtures("load", confirmed=True)
    load_catalog(confirmed=True)


def test_persisted_http_walkthrough_filters_fees_and_stable_pages() -> None:
    seed()
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 200
        catalog = client.get("/doctors").json()
        assert len(catalog["items"]) == 2
        assert catalog["limit"] == 20 and catalog["offset"] == 0
        first, second = catalog["items"]
        assert first["consultation_fee"] == "2500.00"
        assert second["consultation_fee"] == "3500.50"
        assert set(first) == {
            "id",
            "clinic_id",
            "name",
            "city",
            "specialty_id",
            "consultation_fee",
            "currency",
        }
        assert first["city"] == "Karachi" and first["currency"] == "PKR"
        for path in ("/doctors", "/specialties", "/services"):
            full = client.get(path).json()["items"]
            pages = [
                client.get(path, params={"limit": 1, "offset": index}).json()["items"][
                    0
                ]
                for index in range(2)
            ]
            assert full == pages
            assert client.get(path, params={"offset": 2}).json()["items"] == []
            assert (
                client.get(
                    path, params={"city": " karachi ", "clinic_id": str(CLINIC["id"])}
                ).json()["items"]
                == full
            )
            assert client.get(path, params={"city": "%"}).json()["items"] == []
        filtered = client.get(
            "/doctors",
            params={
                "specialty_id": first["specialty_id"],
                "city": "Karachi",
                "clinic_id": str(CLINIC["id"]),
            },
        ).json()["items"]
        assert filtered == [first]
        assert first["specialty_id"] in {
            row["id"] for row in client.get("/specialties").json()["items"]
        }
        assert client.get(f"/doctors/{first['id']}").json() == first
        assert client.get(f"/doctors/{first['id']}/fee").json() == {
            "id": first["id"],
            "amount": "2500.00",
            "currency": "PKR",
        }
        for row in client.get("/services").json()["items"]:
            assert client.get(f"/services/{row['id']}").json() == row
            assert client.get(f"/services/{row['id']}/fee").json() == {
                "id": row["id"],
                "amount": row["fee"],
                "currency": "PKR",
            }


def test_inactive_services_specialties_and_foreign_services_are_hidden() -> None:
    seed()
    foreign_clinic, foreign_service = uuid4(), uuid4()
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                clinics.insert().values(**{**CLINIC, "id": foreign_clinic})
            )
            connection.execute(
                services.insert().values(
                    **{
                        **SERVICES[0],
                        "id": foreign_service,
                        "clinic_id": foreign_clinic,
                    }
                )
            )
            connection.execute(
                services.update()
                .where(services.c.id == SERVICES[0]["id"])
                .values(active=False)
            )
            connection.execute(
                specialties.update()
                .where(specialties.c.id == SPECIALTIES[0]["id"])
                .values(active=False)
            )
        with TestClient(app) as client:
            for identifier in (SERVICES[0]["id"], foreign_service, uuid4()):
                assert client.get(f"/services/{identifier}").status_code == 404
                assert client.get(f"/services/{identifier}/fee").status_code == 404
            assert (
                client.get(
                    "/services", params={"clinic_id": str(foreign_clinic)}
                ).json()["items"]
                == []
            )
            assert len(client.get("/services").json()["items"]) == 1
            assert len(client.get("/specialties").json()["items"]) == 1
            assert client.get(f"/doctors/{DOCTORS[0]['id']}").status_code == 404
            assert len(client.get("/doctors").json()["items"]) == 1
    finally:
        engine.dispose()


def test_database_constraints_and_model_migration_consistency() -> None:
    seed()
    engine = database_engine()
    try:
        for table, row, fee_column in (
            (doctors, DOCTORS[0], "consultation_fee"),
            (services, SERVICES[0], "fee"),
        ):
            for bad in (
                "-0.01",
                "0.001",
                "NaN",
                "Infinity",
                "-Infinity",
                "10000000000",
            ):
                with pytest.raises(IntegrityError), engine.begin() as connection:
                    connection.execute(
                        table.insert().values(
                            **{
                                **row,
                                "id": uuid4(),
                                "name": "Synthetic Invalid Fee",
                                fee_column: Decimal(bad),
                            }
                        )
                    )
            with pytest.raises(IntegrityError), engine.begin() as connection:
                connection.execute(
                    table.insert().values(
                        **{
                            **row,
                            "id": uuid4(),
                            "name": "Synthetic Missing Clinic",
                            "clinic_id": uuid4(),
                        }
                    )
                )
        with engine.begin() as connection:
            other_clinic, other_specialty = uuid4(), uuid4()
            connection.execute(
                clinics.insert().values(**{**CLINIC, "id": other_clinic})
            )
            connection.execute(
                specialties.insert().values(
                    **{
                        **SPECIALTIES[0],
                        "id": other_specialty,
                        "clinic_id": other_clinic,
                    }
                )
            )
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                doctors.insert().values(
                    **{**DOCTORS[0], "id": uuid4(), "specialty_id": other_specialty}
                )
            )
        with engine.connect() as connection:
            inspector = inspect(connection)
            for table in (specialties, doctors, services):
                assert {
                    col["name"] for col in inspector.get_columns(table.name)
                } == set(table.c.keys())
                assert {
                    constraint["name"]
                    for constraint in inspector.get_check_constraints(table.name)
                } == {
                    constraint.name
                    for constraint in table.constraints
                    if isinstance(constraint, CheckConstraint)
                }
    finally:
        engine.dispose()


def database_snapshot() -> list[list[dict[str, object]]]:
    engine = database_engine()
    try:
        with engine.connect() as connection:
            return [
                [
                    dict(row)
                    for row in connection.execute(
                        select(table).order_by(*table.primary_key.columns)
                    ).mappings()
                ]
                for table in (
                    clinics,
                    demo_identities,
                    users,
                    patients,
                    sessions,
                    specialties,
                    doctors,
                    services,
                )
            ]
    finally:
        engine.dispose()


def test_confirmed_cli_repeat_load_and_fixture_reset_preserve_catalog_and_auth() -> (
    None
):
    seed()
    provision(
        "patient.one@careflow.example.invalid",
        "Synthetic-Only-Test-Password!",
        confirmed=True,
    )
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                sessions.insert().values(
                    token_hash="a" * 64,
                    user_id=connection.scalar(select(users.c.id)),
                    csrf_token="x" * 43,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            connection.execute(
                doctors.update()
                .where(doctors.c.id == DOCTORS[0]["id"])
                .values(consultation_fee=Decimal("2999.25"), active=False)
            )
            connection.execute(
                services.insert().values(
                    **{
                        **SERVICES[0],
                        "id": uuid4(),
                        "name": "Synthetic Unrelated Service",
                    }
                )
            )
        before = database_snapshot()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "careflow.catalog_fixtures",
                "load",
                "--confirm-synthetic-catalog",
            ],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert database_snapshot() == before
        apply_fixtures("reset", confirmed=True)
        assert database_snapshot() == before
        load_catalog(confirmed=True)
        assert database_snapshot() == before
        with pytest.raises(ValueError):
            load_catalog(confirmed=False)
        assert database_snapshot() == before
    finally:
        engine.dispose()


def test_catalog_load_failure_is_atomic_and_stale_schema_is_refused() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    with pytest.raises(IntegrityError):
        load_catalog(confirmed=True)  # Missing prerequisite clinic.
    apply_fixtures("load", confirmed=True)
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                services.insert().values(**{**SERVICES[0], "id": uuid4()})
            )
        before = database_snapshot()
        # Service name conflict occurs after specialties/doctors were inserted.
        with pytest.raises(IntegrityError):
            load_catalog(confirmed=True)
        assert database_snapshot() == before
        command.downgrade(Config("alembic.ini"), "0003_patient_sessions")
        with pytest.raises(ValueError, match="Catalog operation refused"):
            load_catalog(confirmed=True)
        with TestClient(app) as client:
            assert client.get("/ready").status_code == 503
        command.upgrade(Config("alembic.ini"), "head")
        load_catalog(confirmed=True)
        with TestClient(app) as client:
            assert client.get("/ready").status_code == 200
    finally:
        engine.dispose()


def test_catalog_application_grants_allow_reads_and_deny_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed()
    owner = database_engine()
    role = "careflow_catalog_" + uuid4().hex
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
            connection.execute(text("GRANT USAGE ON SCHEMA public TO " + role))
            connection.execute(
                text(
                    "GRANT SELECT ON public.clinics, public.specialties, "
                    "public.doctors, public.services TO " + role
                )
            )
        monkeypatch.setenv(
            "DATABASE_URL",
            owner.url.set(username=role, password=password).render_as_string(
                hide_password=False
            ),
        )
        with TestClient(app) as client:
            for path in (
                "/doctors",
                "/specialties",
                "/services",
                f"/doctors/{DOCTORS[0]['id']}/fee",
                f"/services/{SERVICES[0]['id']}/fee",
            ):
                assert client.get(path).status_code == 200
        reader = database_engine()
        try:
            for table in (doctors, services, specialties):
                with pytest.raises(SQLAlchemyError), reader.begin() as connection:
                    connection.execute(table.delete())
            with pytest.raises(SQLAlchemyError):
                load_catalog(confirmed=True)
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

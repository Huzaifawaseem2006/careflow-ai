"""Explicit local-only fixture operations; never exposed to HTTP or the LLM."""

import argparse
import re
import sys
from typing import Literal, TypedDict
from uuid import UUID

from alembic.migration import MigrationContext
from sqlalchemy import URL, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from careflow.database import SCHEMA_REVISION, database_engine
from careflow.fixture_schema import clinics, demo_identities


class ClinicFixture(TypedDict):
    id: UUID
    name: str
    city: str
    timezone: str
    currency: str
    is_synthetic: bool


class IdentityFixture(TypedDict):
    id: UUID
    clinic_id: UUID
    display_name: str
    email: str
    demo_role: str
    is_synthetic: bool


CLINIC: ClinicFixture = {
    "id": UUID("00000000-0000-4000-8000-000000000001"),
    "name": "CareFlow Fictional Demo Clinic",
    "city": "Karachi",
    "timezone": "Asia/Karachi",
    "currency": "PKR",
    "is_synthetic": True,
}
IDENTITIES: tuple[IdentityFixture, ...] = tuple(
    IdentityFixture(
        id=UUID(f"00000000-0000-4000-8000-{number:012d}"),
        clinic_id=CLINIC["id"],
        display_name=f"Synthetic {label}",
        email=f"{email}@careflow.example.invalid",
        demo_role=role,
        is_synthetic=True,
    )
    for number, label, email, role in (
        (11, "Patient One", "patient.one", "patient"),
        (12, "Patient Two", "patient.two", "patient"),
        (13, "Receptionist", "receptionist", "receptionist"),
        (14, "Admin", "admin", "admin"),
    )
)


def validate_target(url: URL, *, confirmed: bool) -> None:
    if (
        not confirmed
        or url.drivername != "postgresql+psycopg"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.query
        or not (
            url.database in {"careflow_ai", "careflow_demo"}
            or re.fullmatch(r"careflow_test_[0-9a-f]{32}", url.database or "")
        )
    ):
        raise ValueError("Fixture operation refused")


def apply_fixtures(action: Literal["load", "reset"], *, confirmed: bool) -> None:
    engine = database_engine()
    try:
        validate_target(engine.url, confirmed=confirmed)
        if action not in {"load", "reset"}:
            raise ValueError("Fixture operation refused")
        with engine.begin() as connection:
            # Serializes fixture writers; no shared table/database reset is used.
            connection.execute(text("SELECT pg_advisory_xact_lock(48405004)"))
            if MigrationContext.configure(connection).get_current_heads() != (
                SCHEMA_REVISION,
            ):
                raise ValueError("Fixture operation refused")
            for table, rows in (
                (clinics, [dict(CLINIC)]),
                (demo_identities, [dict(row) for row in IDENTITIES]),
            ):
                statement = insert(table).values(rows)
                if action == "load":
                    statement = statement.on_conflict_do_nothing(index_elements=["id"])
                else:
                    statement = statement.on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            column.name: statement.excluded[column.name]
                            for column in table.columns
                            if column.name != "id"
                        },
                    )
                connection.execute(statement)
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("load", "reset"))
    parser.add_argument("--confirm-synthetic-fixtures", action="store_true")
    options = parser.parse_args()
    try:
        apply_fixtures(options.action, confirmed=options.confirm_synthetic_fixtures)
    except (ValueError, SQLAlchemyError):
        print(
            "Fixture operation failed; check confirmation, local demo target, "
            "migration head and operator permissions.",
            file=sys.stderr,
        )
        return 1
    print("Synthetic fixture operation completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

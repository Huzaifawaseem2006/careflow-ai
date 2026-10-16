"""Confirmed insert-only synthetic catalog loading; no HTTP write surface."""

import argparse
import sys
from decimal import Decimal
from uuid import UUID

from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from careflow.catalog_schema import doctors, services, specialties
from careflow.database import SCHEMA_REVISION, database_engine
from careflow.fixtures import CLINIC, validate_target


def fixture_id(number: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{number:012d}")


SPECIALTIES: list[dict[str, object]] = [
    {"id": fixture_id(number), "clinic_id": CLINIC["id"], "name": name, "active": True}
    for number, name in ((101, "General Medicine"), (102, "Dermatology"))
]
DOCTORS: list[dict[str, object]] = [
    {
        "id": fixture_id(number),
        "clinic_id": CLINIC["id"],
        "specialty_id": specialty,
        "name": name,
        "consultation_fee": Decimal(fee),
        "active": True,
    }
    for number, specialty, name, fee in (
        (201, fixture_id(101), "Synthetic Doctor One", "2500.00"),
        (202, fixture_id(102), "Synthetic Doctor Two", "3500.50"),
    )
]
SERVICES: list[dict[str, object]] = [
    {
        "id": fixture_id(number),
        "clinic_id": CLINIC["id"],
        "name": name,
        "fee": Decimal(fee),
        "active": True,
    }
    for number, name, fee in (
        (301, "Synthetic Blood Pressure Measurement", "500.00"),
        (302, "Synthetic ECG Service", "1500.25"),
    )
]


def load_catalog(*, confirmed: bool) -> None:
    engine = database_engine()
    try:
        validate_target(engine.url, confirmed=confirmed)
        with engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(48405004)"))
            if MigrationContext.configure(connection).get_current_heads() != (
                SCHEMA_REVISION,
            ):
                raise ValueError("Catalog operation refused")
            for table, rows in (
                (specialties, SPECIALTIES),
                (doctors, DOCTORS),
                (services, SERVICES),
            ):
                connection.execute(
                    insert(table)
                    .values(rows)
                    .on_conflict_do_nothing(index_elements=["id"])
                )
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("load",))
    parser.add_argument("--confirm-synthetic-catalog", action="store_true")
    options = parser.parse_args()
    try:
        load_catalog(confirmed=options.confirm_synthetic_catalog)
    except (ValueError, SQLAlchemyError):
        print(
            "Catalog operation failed; check confirmation, local demo target, "
            "fixtures, migration head and operator permissions.",
            file=sys.stderr,
        )
        return 1
    print("Synthetic catalog loaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

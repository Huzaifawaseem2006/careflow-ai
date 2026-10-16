"""Persisted public reads; caller filters can only narrow the fixed clinic scope."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal
from uuid import UUID

from sqlalchemy import Connection, func, select
from sqlalchemy.exc import SQLAlchemyError

from careflow.catalog_schema import doctors, services, specialties
from careflow.database import database_engine
from careflow.fixture_schema import clinics
from careflow.fixtures import CLINIC

CatalogKind = Literal["doctors", "specialties", "services"]


class CatalogError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


@contextmanager
def catalog_connection() -> Iterator[Connection]:
    try:
        engine = database_engine()
        try:
            with engine.connect() as connection:
                yield connection
        finally:
            engine.dispose()
    except (ValueError, SQLAlchemyError):
        raise CatalogError(503, "CATALOG_UNAVAILABLE", "Catalog unavailable.") from None


def read_catalog(
    connection: Connection,
    kind: CatalogKind,
    *,
    clinic_id: UUID | None = None,
    city: str | None = None,
    specialty_id: UUID | None = None,
    resource_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, object]]:
    if not 1 <= limit <= 100 or not 0 <= offset <= 10000:
        raise CatalogError(422, "VALIDATION_ERROR", "Invalid request.")
    table = {"doctors": doctors, "specialties": specialties, "services": services}[kind]
    columns = [table.c.id, table.c.clinic_id, table.c.name, clinics.c.city]
    source = table.join(clinics, table.c.clinic_id == clinics.c.id)
    if kind == "doctors":
        columns += [
            doctors.c.specialty_id,
            doctors.c.consultation_fee,
            clinics.c.currency,
        ]
        source = source.join(
            specialties,
            (doctors.c.specialty_id == specialties.c.id)
            & (doctors.c.clinic_id == specialties.c.clinic_id),
        )
    elif kind == "services":
        columns += [services.c.fee, clinics.c.currency]
    statement = (
        select(*columns)
        .select_from(source)
        .where(
            table.c.clinic_id == CLINIC["id"],
            table.c.active.is_(True),
            clinics.c.is_synthetic.is_(True),
            clinics.c.currency == "PKR",
        )
    )
    if kind == "doctors":
        statement = statement.where(specialties.c.active.is_(True))
    if clinic_id is not None:
        statement = statement.where(table.c.clinic_id == clinic_id)
    if city is not None:
        statement = statement.where(func.lower(clinics.c.city) == city.strip().lower())
    if specialty_id is not None:
        statement = statement.where(doctors.c.specialty_id == specialty_id)
    if resource_id is not None:
        statement = statement.where(table.c.id == resource_id)
    return [
        dict(row)
        for row in connection.execute(
            statement.order_by(table.c.name, table.c.id).limit(limit).offset(offset)
        ).mappings()
    ]

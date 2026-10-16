"""Bounded public catalog HTTP surface. Writes require the local operator CLI."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from sqlalchemy import Connection

from careflow.catalog import (
    CatalogError,
    CatalogKind,
    catalog_connection,
    read_catalog,
)

router = APIRouter()
Amount = Annotated[
    Decimal,
    Field(ge=0, lt=Decimal("10000000000"), decimal_places=2),
    PlainSerializer(lambda value: format(value, ".2f"), return_type=str),
]


class CatalogFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clinic_id: UUID | None = None
    city: str | None = Field(default=None, min_length=1, max_length=80)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)


class DoctorFilters(CatalogFilters):
    specialty_id: UUID | None = None


class Specialty(BaseModel):
    id: UUID
    clinic_id: UUID
    name: str
    city: str


class Doctor(Specialty):
    specialty_id: UUID
    consultation_fee: Amount
    currency: Literal["PKR"]


class Service(Specialty):
    fee: Amount
    currency: Literal["PKR"]


class Price(BaseModel):
    id: UUID
    amount: Amount
    currency: Literal["PKR"]


class Page[T: BaseModel](BaseModel):
    items: list[T]
    limit: int
    offset: int


def connection_dependency() -> Iterator[Connection]:
    with catalog_connection() as connection:
        yield connection


DB = Annotated[Connection, Depends(connection_dependency)]


@router.get("/specialties", response_model=Page[Specialty])
def list_specialties(
    filters: Annotated[CatalogFilters, Query()], connection: DB
) -> Page[Specialty]:
    rows = read_catalog(connection, "specialties", **filters.model_dump())
    return Page(
        items=[Specialty.model_validate(row) for row in rows],
        limit=filters.limit,
        offset=filters.offset,
    )


@router.get("/doctors", response_model=Page[Doctor])
def list_doctors(
    filters: Annotated[DoctorFilters, Query()], connection: DB
) -> Page[Doctor]:
    rows = read_catalog(connection, "doctors", **filters.model_dump())
    return Page(
        items=[Doctor.model_validate(row) for row in rows],
        limit=filters.limit,
        offset=filters.offset,
    )


@router.get("/services", response_model=Page[Service])
def list_services(
    filters: Annotated[CatalogFilters, Query()], connection: DB
) -> Page[Service]:
    rows = read_catalog(connection, "services", **filters.model_dump())
    return Page(
        items=[Service.model_validate(row) for row in rows],
        limit=filters.limit,
        offset=filters.offset,
    )


def detail(
    connection: Connection, kind: CatalogKind, identifier: UUID
) -> dict[str, object]:
    rows = read_catalog(connection, kind, resource_id=identifier)
    if not rows:
        raise CatalogError(404, "NOT_FOUND", "Catalog resource not found.")
    return rows[0]


@router.get("/doctors/{identifier}", response_model=Doctor)
def doctor_detail(identifier: UUID, connection: DB) -> Doctor:
    return Doctor.model_validate(detail(connection, "doctors", identifier))


@router.get("/services/{identifier}", response_model=Service)
def service_detail(identifier: UUID, connection: DB) -> Service:
    return Service.model_validate(detail(connection, "services", identifier))


@router.get("/doctors/{identifier}/fee", response_model=Price)
def consultation_price(identifier: UUID, connection: DB) -> Price:
    row = detail(connection, "doctors", identifier)
    return Price.model_validate(
        {
            "id": row["id"],
            "amount": row["consultation_fee"],
            "currency": row["currency"],
        }
    )


@router.get("/services/{identifier}/fee", response_model=Price)
def service_price(identifier: UUID, connection: DB) -> Price:
    row = detail(connection, "services", identifier)
    return Price.model_validate(
        {"id": row["id"], "amount": row["fee"], "currency": row["currency"]}
    )

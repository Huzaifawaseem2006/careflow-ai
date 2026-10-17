"""Validated public slot transport; GET never generates inventory."""

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)
from sqlalchemy import Connection

from careflow.availability import read_availability
from careflow.catalog import catalog_connection
from careflow.scheduling import ZONE, explicit_timestamp

router = APIRouter()


class AvailabilityFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_at: AwareDatetime
    end_at: AwareDatetime
    clinic_id: UUID | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)

    @field_validator("start_at", "end_at", mode="before")
    @classmethod
    def offset_timestamp(cls, value: object) -> datetime:
        return explicit_timestamp(value)


class Slot(BaseModel):
    id: UUID
    clinic_id: UUID
    doctor_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    version: int
    timezone: Literal["Asia/Karachi"] = "Asia/Karachi"

    @field_serializer("start_at", "end_at")
    def local_timestamp(self, value: datetime) -> str:
        return value.astimezone(ZONE).isoformat()


class AvailabilityPage(BaseModel):
    items: list[Slot]
    limit: int
    offset: int
    timezone: Literal["Asia/Karachi"] = "Asia/Karachi"


def connection_dependency() -> Iterator[Connection]:
    with catalog_connection() as connection:
        yield connection


@router.get("/doctors/{identifier}/slots", response_model=AvailabilityPage)
def available_slots(
    identifier: UUID,
    filters: Annotated[AvailabilityFilters, Query()],
    connection: Annotated[Connection, Depends(connection_dependency)],
) -> AvailabilityPage:
    rows = read_availability(connection, identifier, **filters.model_dump())
    return AvailabilityPage(
        items=[Slot.model_validate(row) for row in rows],
        limit=filters.limit,
        offset=filters.offset,
    )

"""Persisted active slot reads constrained to the public synthetic clinic."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Connection, exists, select, text

from careflow.catalog import CatalogError
from careflow.catalog_schema import doctors, specialties
from careflow.fixture_schema import clinics
from careflow.fixtures import CLINIC
from careflow.schedule_schema import exceptions, schedules, slots
from careflow.scheduling import validate_range


def read_availability(
    connection: Connection,
    doctor_id: UUID,
    *,
    start_at: datetime,
    end_at: datetime,
    clinic_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, object]]:
    now = datetime.now(UTC)
    try:
        validate_range(start_at, end_at, now=now)
        if not 1 <= limit <= 100 or not 0 <= offset <= 10000:
            raise ValueError
    except ValueError:
        raise CatalogError(
            422, "VALIDATION_ERROR", "Invalid availability range."
        ) from None
    if connection.scalar(text("SELECT to_regclass('public.appointments')")) is not None:
        raise CatalogError(503, "CATALOG_UNAVAILABLE", "Availability unavailable.")
    statement = (
        select(
            slots.c.id,
            slots.c.clinic_id,
            slots.c.doctor_id,
            slots.c.start_at,
            slots.c.end_at,
            slots.c.version,
        )
        .select_from(
            slots.join(doctors, slots.c.doctor_id == doctors.c.id)
            .join(specialties, doctors.c.specialty_id == specialties.c.id)
            .join(clinics, doctors.c.clinic_id == clinics.c.id)
            .join(schedules, slots.c.schedule_id == schedules.c.id)
        )
        .where(
            slots.c.clinic_id == CLINIC["id"],
            slots.c.doctor_id == doctor_id,
            doctors.c.active.is_(True),
            specialties.c.active.is_(True),
            clinics.c.is_synthetic.is_(True),
            clinics.c.timezone == "Asia/Karachi",
            clinics.c.currency == "PKR",
            slots.c.active.is_(True),
            schedules.c.active.is_(True),
            slots.c.start_at >= now,
            slots.c.start_at >= start_at,
            slots.c.end_at <= end_at,
            ~exists(
                select(exceptions.c.id).where(
                    exceptions.c.doctor_id == doctor_id,
                    exceptions.c.active.is_(True),
                    exceptions.c.start_at < slots.c.end_at,
                    exceptions.c.end_at > slots.c.start_at,
                )
            ),
        )
    )
    if clinic_id is not None:
        statement = statement.where(slots.c.clinic_id == clinic_id)
    return [
        dict(row)
        for row in connection.execute(
            statement.order_by(slots.c.start_at, slots.c.id).limit(limit).offset(offset)
        ).mappings()
    ]

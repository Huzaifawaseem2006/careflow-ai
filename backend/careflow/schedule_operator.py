"""Confirmed local synthetic scheduling operations in one database transaction."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from alembic.migration import MigrationContext
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from sqlalchemy import Connection, String, Table, cast, exists, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from careflow.booking_schema import appointments
from careflow.catalog_schema import doctors, specialties
from careflow.database import SCHEMA_REVISION, database_engine
from careflow.fixture_schema import clinics
from careflow.fixtures import CLINIC, validate_target
from careflow.schedule_schema import exceptions, schedules, slots
from careflow.scheduling import (
    ScheduleWindow,
    explicit_timestamp,
    intervals,
    validate_range,
)


class ScheduleInput(ScheduleWindow):
    id: UUID
    expected_version: int = Field(ge=0)


class ResourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    expected_version: int = Field(ge=0)


class ExceptionInput(ResourceInput):
    start_at: AwareDatetime
    end_at: AwareDatetime
    reason: str = Field(min_length=1, max_length=160)

    @field_validator("start_at", "end_at", mode="before")
    @classmethod
    def offset_timestamp(cls, value: object) -> datetime:
        return explicit_timestamp(value)

    @model_validator(mode="after")
    def valid_interval(self) -> "ExceptionInput":
        validate_range(self.start_at, self.end_at, now=datetime.now(UTC))
        return self


def resource_version(
    connection: Connection,
    table: Table,
    doctor_id: UUID,
    data: ResourceInput | ScheduleInput,
) -> bool:
    previous = (
        connection.execute(
            select(table)
            .where(table.c.id == data.id, table.c.doctor_id == doctor_id)
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if data.expected_version != (previous["version"] if previous else 0):
        raise ValueError("Stale resource version")
    return previous is not None


def maintain_schedule(
    connection: Connection, doctor_id: UUID, data: ScheduleInput
) -> None:
    previous = resource_version(connection, schedules, doctor_id, data)
    if previous:
        reject_booked(connection, doctor_id, schedule_id=data.id)
    values = data.model_dump(exclude={"expected_version", "id"})
    if previous:
        connection.execute(
            slots.update()
            .where(slots.c.schedule_id == data.id, slots.c.active.is_(True))
            .values(active=False, version=slots.c.version + 1)
        )
        connection.execute(
            schedules.update()
            .where(schedules.c.id == data.id)
            .values(**values, active=True, version=schedules.c.version + 1)
        )
    else:
        connection.execute(
            schedules.insert().values(
                **values, id=data.id, clinic_id=CLINIC["id"], doctor_id=doctor_id
            )
        )


def maintain_exception(
    connection: Connection, doctor_id: UUID, data: ExceptionInput
) -> None:
    previous = resource_version(connection, exceptions, doctor_id, data)
    reject_booked(connection, doctor_id, start=data.start_at, end=data.end_at)
    connection.execute(
        slots.update()
        .where(
            slots.c.doctor_id == doctor_id,
            slots.c.active.is_(True),
            slots.c.start_at < data.end_at,
            slots.c.end_at > data.start_at,
        )
        .values(active=False, version=slots.c.version + 1)
    )
    values = data.model_dump(exclude={"expected_version", "id"})
    if previous:
        connection.execute(
            exceptions.update()
            .where(exceptions.c.id == data.id)
            .values(**values, active=True, version=exceptions.c.version + 1)
        )
    else:
        connection.execute(
            exceptions.insert().values(
                **values, id=data.id, clinic_id=CLINIC["id"], doctor_id=doctor_id
            )
        )


def deactivate(
    connection: Connection, doctor_id: UUID, table: Table, data: ResourceInput
) -> None:
    if not resource_version(connection, table, doctor_id, data):
        raise ValueError("Resource unavailable")
    if table is schedules:
        reject_booked(connection, doctor_id, schedule_id=data.id)
        connection.execute(
            slots.update()
            .where(slots.c.schedule_id == data.id, slots.c.active.is_(True))
            .values(active=False, version=slots.c.version + 1)
        )
    connection.execute(
        table.update()
        .where(table.c.id == data.id)
        .values(active=False, version=table.c.version + 1)
    )


def reject_booked(
    connection: Connection,
    doctor_id: UUID,
    *,
    schedule_id: UUID | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> None:
    statement = (
        select(appointments.c.id)
        .join(slots, appointments.c.slot_id == slots.c.id)
        .where(appointments.c.doctor_id == doctor_id, appointments.c.status == "booked")
    )
    if schedule_id is not None:
        statement = statement.where(slots.c.schedule_id == schedule_id)
    if start is not None and end is not None:
        statement = statement.where(slots.c.start_at < end, slots.c.end_at > start)
    if connection.scalar(statement.limit(1)) is not None:
        raise ValueError("Booked appointments prevent this schedule change")


def generate(connection: Connection, doctor_id: UUID, now: datetime) -> int:
    blocked = (
        connection.execute(
            select(exceptions).where(
                exceptions.c.doctor_id == doctor_id, exceptions.c.active.is_(True)
            )
        )
        .mappings()
        .all()
    )
    count = 0
    for row in connection.execute(
        select(
            *[column for column in schedules.c if column.name != "local_end"],
            cast(schedules.c.local_end, String).label("local_end"),
        )
        .where(schedules.c.doctor_id == doctor_id, schedules.c.active.is_(True))
        .order_by(schedules.c.id)
    ).mappings():
        window = ScheduleWindow.model_validate(
            {key: row[key] for key in ScheduleWindow.model_fields}
        )
        for start, end in intervals(window, now=now):
            if any(
                item["start_at"] < end and item["end_at"] > start for item in blocked
            ):
                continue
            statement = (
                insert(slots)
                .values(
                    id=uuid5(
                        NAMESPACE_URL, f"careflow-slot:{doctor_id}:{start.isoformat()}"
                    ),
                    clinic_id=CLINIC["id"],
                    doctor_id=doctor_id,
                    schedule_id=row["id"],
                    start_at=start,
                    end_at=end,
                    active=True,
                    version=1,
                )
                .on_conflict_do_update(
                    index_elements=["doctor_id", "start_at"],
                    set_={
                        "active": True,
                        "schedule_id": row["id"],
                        "version": slots.c.version + 1,
                    },
                    where=slots.c.active.is_(False)
                    & ~exists(
                        select(appointments.c.id).where(
                            appointments.c.slot_id == slots.c.id,
                            appointments.c.status == "booked",
                        )
                    ),
                )
            )
            result = connection.execute(statement.returning(slots.c.id)).first()
            count += result is not None
    return count


def run_operation(
    action: str, doctor_id: UUID, payload: dict[str, object], *, confirmed: bool
) -> int:
    engine = database_engine()
    try:
        validate_target(engine.url, confirmed=confirmed)
        if action not in {
            "schedule",
            "exception",
            "deactivate-schedule",
            "deactivate-exception",
            "generate",
        }:
            raise ValueError("Unknown schedule operation")
        data: ScheduleInput | ResourceInput | None = None
        if action == "schedule":
            data = ScheduleInput.model_validate(payload)
        elif action == "exception":
            data = ExceptionInput.model_validate(payload)
        elif action.startswith("deactivate-"):
            data = ResourceInput.model_validate(payload)
        if action == "generate" and payload:
            raise ValueError("Generation takes no payload")
        with engine.begin() as connection:
            # Same first lock as fixture/catalog writers; doctor then schedules/slots.
            connection.execute(text("SELECT pg_advisory_xact_lock(48405004)"))
            if MigrationContext.configure(connection).get_current_heads() != (
                SCHEMA_REVISION,
            ):
                raise ValueError("Stale schema")
            doctor = (
                connection.execute(
                    select(doctors)
                    .select_from(
                        doctors.join(clinics, doctors.c.clinic_id == clinics.c.id).join(
                            specialties, doctors.c.specialty_id == specialties.c.id
                        )
                    )
                    .where(
                        doctors.c.id == doctor_id,
                        doctors.c.clinic_id == CLINIC["id"],
                        doctors.c.active.is_(True),
                        clinics.c.is_synthetic.is_(True),
                        clinics.c.timezone == "Asia/Karachi",
                        clinics.c.currency == "PKR",
                        specialties.c.active.is_(True),
                    )
                    .with_for_update(of=doctors)
                )
                .mappings()
                .first()
            )
            if doctor is None:
                raise ValueError("Doctor unavailable")
            if data is not None:
                if isinstance(data, ScheduleInput):
                    maintain_schedule(connection, doctor_id, data)
                elif isinstance(data, ExceptionInput):
                    maintain_exception(connection, doctor_id, data)
                else:
                    deactivate(
                        connection,
                        doctor_id,
                        schedules if action == "deactivate-schedule" else exceptions,
                        data,
                    )
                connection.execute(
                    doctors.update()
                    .where(doctors.c.id == doctor_id)
                    .values(schedule_version=doctors.c.schedule_version + 1)
                )
                return 1
            return generate(connection, doctor_id, datetime.now(UTC))
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "schedule",
            "exception",
            "deactivate-schedule",
            "deactivate-exception",
            "generate",
        ),
    )
    parser.add_argument("--doctor-id", type=UUID, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--confirm-synthetic-schedules", action="store_true")
    options = parser.parse_args()
    try:
        payload = {}
        if options.input is not None:
            with options.input.open("rb") as source:
                content = source.read(16385)
            if len(content) > 16384:
                raise ValueError("Input too large")
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("Object required")
        count = run_operation(
            options.action,
            options.doctor_id,
            payload,
            confirmed=options.confirm_synthetic_schedules,
        )
    except (ValueError, OSError, SQLAlchemyError):
        print(
            "Scheduling operation refused; check confirmation, local synthetic target, "
            "input/version, migration head and operator permissions.",
            file=sys.stderr,
        )
        return 1
    print(f"Synthetic scheduling operation completed ({count} affected).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

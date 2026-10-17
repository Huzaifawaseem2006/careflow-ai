"""Owned appointment queries and confirmed changes."""

import re
import secrets
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from sqlalchemy import Connection, RowMapping, literal, select, tuple_

from careflow import booking
from careflow.booking import appointment_result, transaction
from careflow.booking_schema import appointments, audit, proposals, retries
from careflow.catalog_schema import doctors
from careflow.identity import (
    IdentityError,
    mutation_patient,
    read_session,
    require_csrf,
    token_hash,
)
from careflow.schedule_schema import schedules, slots
from careflow.scheduling import explicit_timestamp


class ListingFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=100)
    status: Literal["booked", "cancelled"] | None = None
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None

    @field_validator("start_at", "end_at", mode="before")
    @classmethod
    def timestamp(cls, value: object) -> datetime | None:
        return None if value is None else explicit_timestamp(value)

    @field_validator("cursor")
    @classmethod
    def valid_cursor(cls, value: str | None) -> str | None:
        if value is not None:
            stamp, identifier = value.split("|", 1)
            explicit_timestamp(stamp)
            UUID(identifier)
        return value

    @model_validator(mode="after")
    def positive_range(self) -> "ListingFilters":
        if (
            self.start_at is not None
            and self.end_at is not None
            and self.start_at >= self.end_at
        ):
            raise ValueError("Invalid range")
        return self


def list_appointments(token: str | None, filters: ListingFilters) -> dict[str, object]:
    token_hash(token)
    with transaction() as connection:
        patient = mutation_patient(connection, token, None, check_csrf=False)
        query = select(appointments).where(
            appointments.c.patient_id == patient["id"],
            appointments.c.clinic_id == patient["clinic_id"],
        )
        if filters.status is not None:
            query = query.where(appointments.c.status == filters.status)
        if filters.start_at is not None:
            query = query.where(appointments.c.start_at >= filters.start_at)
        if filters.end_at is not None:
            query = query.where(appointments.c.start_at < filters.end_at)
        if filters.cursor is not None:
            stamp, identifier = filters.cursor.split("|", 1)
            query = query.where(
                tuple_(appointments.c.start_at, appointments.c.id)
                > tuple_(literal(explicit_timestamp(stamp)), literal(UUID(identifier)))
            )
        rows = (
            connection.execute(
                query.order_by(appointments.c.start_at, appointments.c.id).limit(
                    filters.limit + 1
                )
            )
            .mappings()
            .all()
        )
        page = rows[: filters.limit]
        cursor = None
        if len(rows) > filters.limit:
            last = page[-1]
            cursor = last["start_at"].isoformat() + "|" + str(last["id"])
        read_session(connection, token)
        return {
            "items": [appointment_result(connection, row["id"]) for row in page],
            "next_cursor": cursor,
        }


ChangeAction = Literal["cancel", "reschedule"]


def owned(
    connection: Connection, identifier: UUID, patient: RowMapping, *, lock: bool = False
) -> RowMapping:
    query = select(appointments).where(
        appointments.c.id == identifier,
        appointments.c.patient_id == patient["id"],
        appointments.c.clinic_id == patient["clinic_id"],
    )
    if lock:
        query = query.with_for_update()
    row = connection.execute(query).mappings().first()
    if row is None:
        raise IdentityError(404, "NOT_FOUND")
    return row


def check_policy(row: RowMapping) -> None:
    if row["status"] != "booked":
        raise IdentityError(409, "APPOINTMENT_INACTIVE")
    if row["start_at"] - booking.now() < timedelta(hours=24):
        raise IdentityError(409, "CHANGE_CUTOFF")


def lock_source(
    connection: Connection,
    identifier: UUID,
    patient: RowMapping,
    target_id: UUID | None = None,
) -> RowMapping:
    initial = owned(connection, identifier, patient)
    if target_id == initial["slot_id"]:
        raise IdentityError(409, "NO_CHANGE")
    resource_ids = [initial["slot_id"]]
    if target_id is not None:
        resource_ids.append(target_id)
    resources = (
        connection.execute(
            select(slots).where(
                slots.c.id.in_(resource_ids), slots.c.clinic_id == patient["clinic_id"]
            )
        )
        .mappings()
        .all()
    )
    if len(resources) != len(resource_ids):
        raise IdentityError(409, "SLOT_UNAVAILABLE")
    # Acquire the union in deterministic order, before slot_summary's revalidation.
    # Maintenance and booking both acquire doctor before schedules/slots.
    for doctor_id in sorted({row["doctor_id"] for row in resources}):
        connection.execute(
            select(doctors.c.id).where(doctors.c.id == doctor_id).with_for_update()
        ).all()
    for schedule_id in sorted({row["schedule_id"] for row in resources}):
        connection.execute(
            select(schedules.c.id)
            .where(schedules.c.id == schedule_id)
            .with_for_update()
        ).all()
    for slot_id in sorted(resource_ids):
        connection.execute(
            select(slots.c.id).where(slots.c.id == slot_id).with_for_update()
        ).all()
    current = owned(connection, identifier, patient, lock=True)
    if dict(initial) != dict(current):
        raise IdentityError(409, "STATE_CHANGED")
    check_policy(current)
    return current


def source_versions(connection: Connection, source: RowMapping) -> dict[str, object]:
    row = (
        connection.execute(
            select(
                slots.c.version.label("slot"),
                schedules.c.version.label("schedule"),
                doctors.c.schedule_version.label("doctor"),
                slots.c.active.label("slot_active"),
                schedules.c.active.label("schedule_active"),
                doctors.c.active.label("doctor_active"),
            )
            .select_from(
                slots.join(schedules, slots.c.schedule_id == schedules.c.id).join(
                    doctors, slots.c.doctor_id == doctors.c.id
                )
            )
            .where(slots.c.id == source["slot_id"])
        )
        .mappings()
        .one()
    )
    return dict(row)


def propose_change(
    identifier: UUID,
    action: ChangeAction,
    target_id: UUID | None,
    token: str | None,
    csrf: str | None,
) -> dict[str, object]:
    token_hash(token)
    if action not in {"cancel", "reschedule"} or (action == "reschedule") != (
        target_id is not None
    ):
        raise IdentityError(422, "VALIDATION_ERROR")
    proof = secrets.token_urlsafe(32)
    with transaction() as connection:
        patient = mutation_patient(connection, token, csrf)
        source = lock_source(connection, identifier, patient, target_id)
        target = (
            None
            if target_id is None
            else booking.slot_summary(connection, target_id, patient["clinic_id"])
        )
        summary = {
            "before": jsonable_encoder(appointment_result(connection, identifier)),
            "version": source["version"],
            "source_versions": source_versions(connection, source),
            "target": target,
        }
        require_csrf(read_session(connection, token), csrf)
        check_policy(source)
        created = booking.now()
        expires = created + timedelta(minutes=5)
        connection.execute(
            proposals.insert().values(
                proof_hash=booking.digest(proof),
                actor_id=patient["user_id"],
                patient_id=patient["id"],
                clinic_id=patient["clinic_id"],
                operation=action,
                slot_id=target_id if target_id is not None else source["slot_id"],
                subject_id=identifier,
                summary=summary,
                created_at=created,
                expires_at=expires,
            )
        )
        check_policy(source)
        require_csrf(read_session(connection, token), csrf)
        if target is not None and booking.now() >= datetime.fromisoformat(
            str(target["start_at"])
        ):
            raise IdentityError(409, "SLOT_UNAVAILABLE")
    return {
        "proposal_token": proof,
        "summary": {
            "operation": action,
            "appointment": summary["before"],
            "target": target,
        },
        "expires_at": expires,
    }


def check_deadline(proposal: RowMapping) -> None:
    current = booking.now()
    target = proposal["summary"]["target"]
    if current >= proposal["expires_at"] or (
        target is not None
        and current >= datetime.fromisoformat(str(target["start_at"]))
    ):
        raise IdentityError(410, "CONFIRMATION_EXPIRED")


def confirm_change(
    identifier: UUID,
    action: ChangeAction,
    proof: str,
    key: str,
    token: str | None,
    csrf: str | None,
) -> dict[str, object]:
    token_hash(token)
    if re.fullmatch(r"[A-Za-z0-9_-]{43}", proof) is None:
        raise IdentityError(404, "NOT_FOUND")
    if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", key) is None:
        raise IdentityError(422, "VALIDATION_ERROR")
    proof_hash, key_hash = booking.digest(proof), booking.digest(key)
    with transaction() as connection:
        patient = mutation_patient(connection, token, csrf)
        retry = (
            connection.execute(
                select(retries).where(
                    retries.c.actor_id == patient["user_id"],
                    retries.c.operation == action,
                    retries.c.key_hash == key_hash,
                )
            )
            .mappings()
            .first()
        )
        # Confirm ownership/clinic even for immutable historical replay.
        owned(connection, identifier, patient)
        if retry is not None:
            if booking.now() >= retry["replay_until"]:
                raise IdentityError(409, "RETRY_EXPIRED")
            if (
                retry["proof_hash"] != proof_hash
                or retry["appointment_id"] != identifier
            ):
                raise IdentityError(409, "IDEMPOTENCY_CONFLICT")
            result = dict(retry["response_snapshot"])
        else:
            proposal = (
                connection.execute(
                    select(proposals).where(
                        proposals.c.proof_hash == proof_hash,
                        proposals.c.actor_id == patient["user_id"],
                        proposals.c.patient_id == patient["id"],
                        proposals.c.clinic_id == patient["clinic_id"],
                        proposals.c.operation == action,
                        proposals.c.subject_id == identifier,
                    )
                )
                .mappings()
                .first()
            )
            if proposal is None:
                raise IdentityError(404, "NOT_FOUND")
            if proposal["appointment_id"] is not None:
                raise IdentityError(409, "PROPOSAL_CONSUMED")
            check_deadline(proposal)
            target_id = proposal["slot_id"] if action == "reschedule" else None
            source = lock_source(connection, identifier, patient, target_id)
            check_deadline(proposal)
            target = (
                None
                if target_id is None
                else booking.slot_summary(connection, target_id, patient["clinic_id"])
            )
            locked = (
                connection.execute(
                    select(proposals)
                    .where(proposals.c.proof_hash == proof_hash)
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            before = jsonable_encoder(appointment_result(connection, identifier))
            if (
                dict(locked) != dict(proposal)
                or source["version"] != proposal["summary"]["version"]
                or before != proposal["summary"]["before"]
                or source_versions(connection, source)
                != proposal["summary"]["source_versions"]
                or target != proposal["summary"]["target"]
            ):
                raise IdentityError(409, "STATE_CHANGED")
            check_deadline(proposal)
            check_policy(source)
            changes: dict[str, object] = {
                "status": "cancelled",
                "version": source["version"] + 1,
            }
            if target is not None:
                changes.update(
                    status="booked",
                    slot_id=target_id,
                    doctor_id=UUID(str(target["doctor_id"])),
                    doctor_name=target["doctor_name"],
                    start_at=datetime.fromisoformat(str(target["start_at"])),
                    end_at=datetime.fromisoformat(str(target["end_at"])),
                    accepted_fee=target["fee"],
                )
            connection.execute(
                appointments.update()
                .where(appointments.c.id == identifier)
                .values(**changes)
            )
            result = jsonable_encoder(appointment_result(connection, identifier))
            created = booking.now()
            connection.execute(
                proposals.update()
                .where(proposals.c.proof_hash == proof_hash)
                .values(appointment_id=identifier)
            )
            connection.execute(
                retries.insert().values(
                    actor_id=patient["user_id"],
                    operation=action,
                    key_hash=key_hash,
                    proof_hash=proof_hash,
                    appointment_id=identifier,
                    replay_until=created + timedelta(hours=24),
                    response_snapshot=result,
                )
            )
            connection.execute(
                audit.insert().values(
                    id=uuid4(),
                    actor_id=patient["user_id"],
                    action=action,
                    appointment_id=identifier,
                    before_snapshot=before,
                    after_snapshot=result,
                    created_at=created,
                )
            )
            # Time may elapse during SQL execution as well as resource waits.
            check_policy(source)
            check_deadline(proposal)
        require_csrf(read_session(connection, token), csrf)
    return result

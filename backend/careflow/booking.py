"""Atomic patient booking; authority and pricing come from persisted state."""

import hashlib
import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import Connection, RowMapping, String, cast, exists, select
from sqlalchemy.exc import SQLAlchemyError

from careflow.booking_schema import appointments, audit, proposals, retries
from careflow.catalog_schema import doctors, specialties
from careflow.database import database_engine
from careflow.identity import (
    IdentityError,
    mutation_patient,
    read_session,
    require_csrf,
    token_hash,
)
from careflow.schedule_schema import exceptions, schedules, slots
from careflow.scheduling import ZONE, ScheduleWindow, horizon, intervals


def now() -> datetime:
    return datetime.now(UTC)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


@contextmanager
def transaction() -> Iterator[Connection]:
    try:
        engine = database_engine()
        try:
            with engine.begin() as connection:
                yield connection
        finally:
            engine.dispose()
    except (SQLAlchemyError, ValueError):
        raise IdentityError(503, "BOOKING_UNAVAILABLE") from None


def slot_summary(
    connection: Connection, slot_id: UUID, clinic_id: UUID
) -> dict[str, object]:
    # Resolve doctor without locking a slot first; revalidate after doctor lock.
    doctor_id = connection.scalar(
        select(slots.c.doctor_id).where(slots.c.id == slot_id)
    )
    doctor = (
        connection.execute(
            select(doctors)
            .where(doctors.c.id == doctor_id, doctors.c.clinic_id == clinic_id)
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if doctor is None or not doctor["active"]:
        raise IdentityError(409, "SLOT_UNAVAILABLE")
    row = (
        connection.execute(
            select(
                slots,
                schedules.c.version.label("schedule_version"),
                schedules.c.weekday,
                schedules.c.local_start,
                cast(schedules.c.local_end, String).label("local_end"),
                schedules.c.effective_from,
                schedules.c.effective_to,
            )
            .join(schedules, slots.c.schedule_id == schedules.c.id)
            .where(
                slots.c.id == slot_id,
                slots.c.doctor_id == doctor["id"],
                slots.c.clinic_id == clinic_id,
                slots.c.active.is_(True),
                schedules.c.active.is_(True),
            )
            .with_for_update(of=(schedules, slots))
        )
        .mappings()
        .first()
    )
    current = now()
    lower, upper = horizon(current)
    if (
        row is None
        or (row["start_at"], row["end_at"])
        not in intervals(
            ScheduleWindow.model_validate(
                {key: row[key] for key in ScheduleWindow.model_fields}
            ),
            now=current,
        )
        or not lower <= row["start_at"] < upper
        or row["start_at"] <= current
        or not connection.scalar(
            select(specialties.c.active)
            .where(
                specialties.c.id == doctor["specialty_id"],
                specialties.c.clinic_id == clinic_id,
            )
            .with_for_update(read=True)
        )
        or connection.scalar(
            select(
                exists().where(
                    appointments.c.slot_id == slot_id, appointments.c.status == "booked"
                )
            )
        )
        or connection.scalar(
            select(
                exists().where(
                    exceptions.c.doctor_id == doctor["id"],
                    exceptions.c.active.is_(True),
                    exceptions.c.start_at < row["end_at"],
                    exceptions.c.end_at > row["start_at"],
                )
            )
        )
    ):
        raise IdentityError(409, "SLOT_UNAVAILABLE")
    return {
        "slot_id": str(slot_id),
        "doctor_id": str(doctor["id"]),
        "clinic_id": str(clinic_id),
        "doctor_name": doctor["name"],
        "start_at": row["start_at"].astimezone(ZONE).isoformat(),
        "end_at": row["end_at"].astimezone(ZONE).isoformat(),
        "timezone": "Asia/Karachi",
        "fee": format(doctor["consultation_fee"], ".2f"),
        "currency": "PKR",
        "slot_version": row["version"],
        "schedule_version": row["schedule_version"],
        "doctor_version": doctor["schedule_version"],
    }


def propose(slot_id: UUID, token: str | None, csrf: str | None) -> dict[str, object]:
    token_hash(token)
    proof = secrets.token_urlsafe(32)
    with transaction() as connection:
        patient = mutation_patient(connection, token, csrf)
        summary = slot_summary(connection, slot_id, patient["clinic_id"])
        require_csrf(read_session(connection, token), csrf)
        created = now()
        if created >= datetime.fromisoformat(str(summary["start_at"])):
            raise IdentityError(409, "SLOT_UNAVAILABLE")
        expires = created + timedelta(minutes=5)
        connection.execute(
            proposals.insert().values(
                proof_hash=digest(proof),
                actor_id=patient["user_id"],
                patient_id=patient["id"],
                clinic_id=patient["clinic_id"],
                operation="book",
                slot_id=slot_id,
                summary=summary,
                created_at=created,
                expires_at=expires,
            )
        )
    return {"proposal_token": proof, "summary": summary, "expires_at": expires}


def appointment_result(
    connection: Connection, appointment_id: UUID
) -> dict[str, object]:
    row = (
        connection.execute(
            select(appointments).where(appointments.c.id == appointment_id)
        )
        .mappings()
        .one()
    )
    result = dict(row)
    result.pop("version", None)
    result["accepted_fee"] = format(row["accepted_fee"], ".2f")
    for key in ("start_at", "end_at"):
        result[key] = row[key].astimezone(ZONE)
    return result


def confirm(
    proof: str, key: str, token: str | None, csrf: str | None
) -> tuple[dict[str, object], bool]:
    token_hash(token)
    if re.fullmatch(r"[A-Za-z0-9_-]{43}", proof) is None:
        raise IdentityError(404, "NOT_FOUND")
    if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", key) is None:
        raise IdentityError(422, "VALIDATION_ERROR")
    proof_hash, key_hash = digest(proof), digest(key)
    with transaction() as connection:
        patient = mutation_patient(connection, token, csrf)
        # User lock serializes all keys for this actor, including absent keys.
        retry = (
            connection.execute(
                select(retries).where(
                    retries.c.actor_id == patient["user_id"],
                    retries.c.operation == "book",
                    retries.c.key_hash == key_hash,
                )
            )
            .mappings()
            .first()
        )
        if retry is not None:
            if now() >= retry["replay_until"]:
                raise IdentityError(409, "RETRY_EXPIRED")
            if retry["proof_hash"] != proof_hash:
                raise IdentityError(409, "IDEMPOTENCY_CONFLICT")
            result = dict(retry["response_snapshot"])
            replay = True
        else:
            proposal = (
                connection.execute(
                    select(proposals).where(
                        proposals.c.proof_hash == proof_hash,
                        proposals.c.actor_id == patient["user_id"],
                        proposals.c.patient_id == patient["id"],
                        proposals.c.clinic_id == patient["clinic_id"],
                        proposals.c.operation == "book",
                    )
                )
                .mappings()
                .first()
            )
            if proposal is None:
                raise IdentityError(404, "NOT_FOUND")
            result = commit_booking(connection, patient, proposal, key_hash)
            replay = False
        # Session/authority rows stay locked, but absolute expiry can elapse
        # while waiting on resources. Reject and roll back before commit.
        require_csrf(read_session(connection, token), csrf)
    return result, replay


def commit_booking(
    connection: Connection, patient: RowMapping, proposal: RowMapping, key_hash: str
) -> dict[str, object]:
    if proposal["appointment_id"] is not None:
        raise IdentityError(409, "PROPOSAL_CONSUMED")
    if now() >= proposal["expires_at"] or now() >= datetime.fromisoformat(
        proposal["summary"]["start_at"]
    ):
        raise IdentityError(410, "CONFIRMATION_EXPIRED")
    summary = slot_summary(connection, proposal["slot_id"], patient["clinic_id"])
    # Lock state before proof, compatible with schedule maintenance.
    locked = (
        connection.execute(
            select(proposals)
            .where(proposals.c.proof_hash == proposal["proof_hash"])
            .with_for_update()
        )
        .mappings()
        .one()
    )
    if dict(locked) != dict(proposal) or summary != proposal["summary"]:
        raise IdentityError(409, "STATE_CHANGED")
    if now() >= proposal["expires_at"] or now() >= datetime.fromisoformat(
        proposal["summary"]["start_at"]
    ):
        raise IdentityError(410, "CONFIRMATION_EXPIRED")
    appointment_id, created = uuid4(), now()
    connection.execute(
        appointments.insert().values(
            id=appointment_id,
            patient_id=patient["id"],
            clinic_id=patient["clinic_id"],
            doctor_id=UUID(str(summary["doctor_id"])),
            slot_id=proposal["slot_id"],
            status="booked",
            doctor_name=summary["doctor_name"],
            start_at=datetime.fromisoformat(str(summary["start_at"])),
            end_at=datetime.fromisoformat(str(summary["end_at"])),
            timezone="Asia/Karachi",
            accepted_fee=summary["fee"],
            currency="PKR",
            created_at=created,
        )
    )
    connection.execute(
        proposals.update()
        .where(proposals.c.proof_hash == proposal["proof_hash"])
        .values(appointment_id=appointment_id)
    )
    result = appointment_result(connection, appointment_id)
    snapshot = jsonable_encoder(result)
    connection.execute(
        retries.insert().values(
            actor_id=patient["user_id"],
            operation="book",
            key_hash=key_hash,
            proof_hash=proposal["proof_hash"],
            appointment_id=appointment_id,
            replay_until=created + timedelta(hours=24),
            response_snapshot=snapshot,
        )
    )
    connection.execute(
        audit.insert().values(
            id=uuid4(),
            actor_id=patient["user_id"],
            action="book",
            after_snapshot=snapshot,
            appointment_id=appointment_id,
            created_at=created,
        )
    )
    return result

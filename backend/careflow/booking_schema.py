"""Booking records; schema constraints are installed by 0006_booking."""

from sqlalchemy import Column, DateTime, Integer, Numeric, String, Table, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from careflow.fixture_schema import metadata

appointments = Table(
    "appointments",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("patient_id", Uuid, nullable=False),
    Column("clinic_id", Uuid, nullable=False),
    Column("doctor_id", Uuid, nullable=False),
    Column("slot_id", Uuid, nullable=False),
    Column("status", String(20), nullable=False),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("doctor_name", String(120), nullable=False),
    Column("start_at", DateTime(timezone=True), nullable=False),
    Column("end_at", DateTime(timezone=True), nullable=False),
    Column("timezone", String(80), nullable=False),
    Column("accepted_fee", Numeric, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
proposals = Table(
    "booking_proposals",
    metadata,
    Column("proof_hash", String(64), primary_key=True),
    Column("actor_id", Uuid, nullable=False),
    Column("patient_id", Uuid, nullable=False),
    Column("clinic_id", Uuid, nullable=False),
    Column("operation", String(20), nullable=False),
    Column("slot_id", Uuid, nullable=False),
    Column("summary", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("appointment_id", Uuid),
    Column("subject_id", Uuid),
)
retries = Table(
    "booking_retries",
    metadata,
    Column("actor_id", Uuid, primary_key=True),
    Column("operation", String(20), primary_key=True),
    Column("key_hash", String(64), primary_key=True),
    Column("proof_hash", String(64), nullable=False),
    Column("appointment_id", Uuid, nullable=False),
    Column("replay_until", DateTime(timezone=True), nullable=False),
    Column("response_snapshot", JSONB, nullable=False),
)
audit = Table(
    "booking_audit",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("actor_id", Uuid, nullable=False),
    Column("action", String(20), nullable=False),
    Column("before_snapshot", JSONB),
    Column("after_snapshot", JSONB, nullable=False),
    Column("appointment_id", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

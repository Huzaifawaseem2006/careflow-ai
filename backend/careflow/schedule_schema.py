"""Schedule inventory; PostgreSQL enforces interval and clinic integrity."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    Time,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint

from careflow.catalog_schema import doctors  # noqa: F401
from careflow.fixture_schema import metadata

schedules = Table(
    "doctor_schedules",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("clinic_id", Uuid, nullable=False),
    Column("doctor_id", Uuid, nullable=False, index=True),
    Column("weekday", Integer, nullable=False),
    Column("local_start", Time, nullable=False),
    Column("local_end", Time, nullable=False),
    Column("effective_from", Date, nullable=False),
    Column("effective_to", Date, nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("version", Integer, nullable=False, server_default="1"),
    ForeignKeyConstraint(
        ["clinic_id", "doctor_id"], ["doctors.clinic_id", "doctors.id"]
    ),
    UniqueConstraint("doctor_id", "id", name="uq_schedules_doctor_id"),
    CheckConstraint(
        "weekday BETWEEN 0 AND 6 AND local_start < local_end AND "
        "effective_from <= effective_to AND version > 0 AND "
        "isfinite(effective_from) AND isfinite(effective_to) AND "
        "mod(extract(epoch FROM local_start), 60) = 0 AND "
        "mod(extract(epoch FROM local_end - local_start), 1800) = 0",
        name="ck_schedule_window",
    ),
    ExcludeConstraint(
        ("doctor_id", "="),
        ("weekday", "="),
        (text("daterange(effective_from, effective_to, '[]')"), "&&"),
        (
            text(
                "int4range(extract(epoch FROM local_start)::int, "
                "extract(epoch FROM local_end)::int, '[)')"
            ),
            "&&",
        ),
        where=text("active"),
        name="ex_schedule_overlap",
        using="gist",
    ),
)

exceptions = Table(
    "schedule_exceptions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("clinic_id", Uuid, nullable=False),
    Column("doctor_id", Uuid, nullable=False, index=True),
    Column("start_at", DateTime(timezone=True), nullable=False),
    Column("end_at", DateTime(timezone=True), nullable=False),
    Column("reason", String(160), nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("version", Integer, nullable=False, server_default="1"),
    ForeignKeyConstraint(
        ["clinic_id", "doctor_id"], ["doctors.clinic_id", "doctors.id"]
    ),
    CheckConstraint(
        "isfinite(start_at) AND isfinite(end_at) AND start_at < end_at AND version > 0",
        name="ck_exception_interval",
    ),
)

slots = Table(
    "slots",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("clinic_id", Uuid, nullable=False),
    Column("doctor_id", Uuid, nullable=False),
    Column("schedule_id", Uuid, nullable=False),
    Column("start_at", DateTime(timezone=True), nullable=False),
    Column("end_at", DateTime(timezone=True), nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("version", Integer, nullable=False, server_default="1"),
    ForeignKeyConstraint(
        ["clinic_id", "doctor_id"], ["doctors.clinic_id", "doctors.id"]
    ),
    ForeignKeyConstraint(
        ["doctor_id", "schedule_id"],
        ["doctor_schedules.doctor_id", "doctor_schedules.id"],
    ),
    UniqueConstraint("doctor_id", "start_at", name="uq_slots_doctor_start"),
    CheckConstraint(
        "isfinite(start_at) AND isfinite(end_at) AND "
        "end_at - start_at = interval '30 minutes' AND version > 0",
        name="ck_slot_interval",
    ),
    ExcludeConstraint(
        ("doctor_id", "="),
        (text("tstzrange(start_at, end_at, '[)')"), "&&"),
        where=text("active"),
        name="ex_slot_overlap",
        using="gist",
    ),
)

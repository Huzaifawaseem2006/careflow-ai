"""Synthetic public catalog; composite keys enforce clinic associations."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    Uuid,
)

from careflow.fixture_schema import metadata

specialties = Table(
    "specialties",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("clinic_id", Uuid, ForeignKey("clinics.id"), nullable=False, index=True),
    Column("name", String(120), nullable=False),
    Column("active", Boolean, nullable=False),
    UniqueConstraint("clinic_id", "id", name="uq_specialties_clinic_id"),
    UniqueConstraint("clinic_id", "name", name="uq_specialties_clinic_name"),
)
doctors = Table(
    "doctors",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("clinic_id", Uuid, ForeignKey("clinics.id"), nullable=False, index=True),
    Column("specialty_id", Uuid, nullable=False, index=True),
    Column("name", String(120), nullable=False),
    Column("consultation_fee", Numeric, nullable=False),
    Column("active", Boolean, nullable=False),
    Column("schedule_version", Integer, nullable=False, server_default="1"),
    CheckConstraint("schedule_version > 0", name="ck_doctors_schedule_version"),
    UniqueConstraint("clinic_id", "id", name="uq_doctors_clinic_id"),
    ForeignKeyConstraint(
        ["clinic_id", "specialty_id"],
        ["specialties.clinic_id", "specialties.id"],
        name="fk_doctors_clinic_specialty",
    ),
    CheckConstraint(
        "consultation_fee >= 0 AND consultation_fee < 10000000000 "
        "AND scale(consultation_fee) <= 2",
        name="ck_doctors_fee",
    ),
)
services = Table(
    "services",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("clinic_id", Uuid, ForeignKey("clinics.id"), nullable=False, index=True),
    Column("name", String(120), nullable=False),
    Column("fee", Numeric, nullable=False),
    Column("active", Boolean, nullable=False),
    UniqueConstraint("clinic_id", "name", name="uq_services_clinic_name"),
    CheckConstraint(
        "fee >= 0 AND fee < 10000000000 AND scale(fee) <= 2",
        name="ck_services_fee",
    ),
)

"""Minimal clinic settings and credential-free demo personas, not auth accounts."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    MetaData,
    String,
    Table,
    Uuid,
)

metadata = MetaData()

clinics = Table(
    "clinics",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", String(160), nullable=False),
    Column("city", String(80), nullable=False),
    Column("timezone", String(80), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("is_synthetic", Boolean, nullable=False),
    CheckConstraint("is_synthetic = true", name="ck_clinics_synthetic"),
)

demo_identities = Table(
    "demo_identities",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("clinic_id", Uuid, ForeignKey("clinics.id"), nullable=False, index=True),
    Column("display_name", String(120), nullable=False),
    Column("email", String(160), nullable=False, unique=True),
    Column("demo_role", String(20), nullable=False),
    Column("is_synthetic", Boolean, nullable=False),
    CheckConstraint("is_synthetic = true", name="ck_demo_identities_synthetic"),
    CheckConstraint(
        "email LIKE '%@careflow.example.invalid'",
        name="ck_demo_identities_email",
    ),
    CheckConstraint(
        "demo_role IN ('patient', 'receptionist', 'admin')",
        name="ck_demo_identities_role",
    ),
)

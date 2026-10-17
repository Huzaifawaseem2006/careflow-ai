"""Authentication records are separate from the synthetic fixture personas."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    func,
)

from careflow.fixture_schema import demo_identities

metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", String(160), nullable=False, unique=True),
    Column("password_hash", String(256), nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint("password_hash LIKE '$argon2id$%'", name="ck_users_password_hash"),
    CheckConstraint("email LIKE '%@careflow.example.invalid'", name="ck_users_email"),
)
patients = Table(
    "patients",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("clinic_id", Uuid, nullable=False),
    Column("user_id", Uuid, ForeignKey(users.c.id), nullable=False, unique=True),
    Column(
        "demo_identity_id",
        Uuid,
        ForeignKey(demo_identities.c.id),
        nullable=False,
        unique=True,
    ),
)
sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", Uuid, ForeignKey(users.c.id), nullable=True, index=True),
    Column("csrf_token", String(43), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
)
auth_limits = Table(
    "auth_limits",
    metadata,
    Column("bucket_key", String(64), primary_key=True),
    Column("attempts", Integer, nullable=False),
    Column("window_end", DateTime(timezone=True), nullable=False, index=True),
    CheckConstraint("attempts > 0", name="ck_auth_limits_attempts"),
)

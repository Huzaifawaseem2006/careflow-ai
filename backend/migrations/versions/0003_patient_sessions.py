"""Separate provisioned patient credentials and opaque server sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0003_patient_sessions"
down_revision = "0002_synthetic_fixtures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("email", sa.String(160), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "password_hash LIKE '$argon2id$%'", name="ck_users_password_hash"
        ),
        sa.CheckConstraint(
            "email LIKE '%@careflow.example.invalid'", name="ck_users_email"
        ),
    )
    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False, unique=True
        ),
        sa.Column(
            "demo_identity_id",
            sa.Uuid,
            sa.ForeignKey("demo_identities.id"),
            nullable=False,
            unique=True,
        ),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("csrf_token", sa.String(43), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_table(
        "auth_limits",
        sa.Column("bucket_key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempts > 0", name="ck_auth_limits_attempts"),
    )
    op.create_index("ix_auth_limits_window_end", "auth_limits", ["window_end"])


def downgrade() -> None:
    op.drop_table("auth_limits")
    op.drop_table("sessions")
    op.drop_table("patients")
    op.drop_table("users")

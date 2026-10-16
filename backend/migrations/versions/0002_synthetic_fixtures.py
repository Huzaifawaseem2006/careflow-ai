"""Create synthetic clinic settings and credential-free demo identities."""

import sqlalchemy as sa
from alembic import op

revision = "0002_synthetic_fixtures"
down_revision = "0001_vector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clinics",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("city", sa.String(80), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("is_synthetic", sa.Boolean, nullable=False),
        sa.CheckConstraint("is_synthetic = true", name="ck_clinics_synthetic"),
    )
    op.create_table(
        "demo_identities",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("clinic_id", sa.Uuid, sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(160), nullable=False, unique=True),
        sa.Column("demo_role", sa.String(20), nullable=False),
        sa.Column("is_synthetic", sa.Boolean, nullable=False),
        sa.CheckConstraint("is_synthetic = true", name="ck_demo_identities_synthetic"),
        sa.CheckConstraint(
            "email LIKE '%@careflow.example.invalid'", name="ck_demo_identities_email"
        ),
        sa.CheckConstraint(
            "demo_role IN ('patient', 'receptionist', 'admin')",
            name="ck_demo_identities_role",
        ),
    )
    op.create_index("ix_demo_identities_clinic_id", "demo_identities", ["clinic_id"])


def downgrade() -> None:
    op.drop_table("demo_identities")
    op.drop_table("clinics")

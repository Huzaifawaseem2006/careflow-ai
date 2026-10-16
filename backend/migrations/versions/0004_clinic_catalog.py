"""Create clinic-scoped public catalog and constrained PKR amounts."""

import sqlalchemy as sa
from alembic import op

revision = "0004_clinic_catalog"
down_revision = "0003_patient_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "specialties",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("clinic_id", sa.Uuid, sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("clinic_id", "id", name="uq_specialties_clinic_id"),
        sa.UniqueConstraint("clinic_id", "name", name="uq_specialties_clinic_name"),
    )
    op.create_index("ix_specialties_clinic_id", "specialties", ["clinic_id"])
    op.create_table(
        "doctors",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("clinic_id", sa.Uuid, sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("specialty_id", sa.Uuid, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("consultation_fee", sa.Numeric, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.ForeignKeyConstraint(
            ["clinic_id", "specialty_id"],
            ["specialties.clinic_id", "specialties.id"],
            name="fk_doctors_clinic_specialty",
        ),
        sa.CheckConstraint(
            "consultation_fee >= 0 AND consultation_fee < 10000000000 "
            "AND scale(consultation_fee) <= 2",
            name="ck_doctors_fee",
        ),
    )
    op.create_index("ix_doctors_clinic_id", "doctors", ["clinic_id"])
    op.create_index("ix_doctors_specialty_id", "doctors", ["specialty_id"])
    op.create_table(
        "services",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("clinic_id", sa.Uuid, sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("fee", sa.Numeric, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("clinic_id", "name", name="uq_services_clinic_name"),
        sa.CheckConstraint(
            "fee >= 0 AND fee < 10000000000 AND scale(fee) <= 2",
            name="ck_services_fee",
        ),
    )
    op.create_index("ix_services_clinic_id", "services", ["clinic_id"])


def downgrade() -> None:
    op.drop_table("services")
    op.drop_table("doctors")
    op.drop_table("specialties")

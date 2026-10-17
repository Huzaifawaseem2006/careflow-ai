"""Persist effective schedules, blocking exceptions and nonoverlapping slots."""

from alembic import op

revision = "0005_scheduling"
down_revision = "0004_clinic_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bundled PostgreSQL extension supplies UUID/integer equality for GiST.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public")
    op.execute(
        "ALTER TABLE doctors ADD COLUMN schedule_version integer NOT NULL DEFAULT 1, "
        "ADD CONSTRAINT ck_doctors_schedule_version CHECK (schedule_version > 0), "
        "ADD CONSTRAINT uq_doctors_clinic_id UNIQUE (clinic_id, id)"
    )
    op.execute("""
        CREATE TABLE doctor_schedules (
            id uuid PRIMARY KEY, clinic_id uuid NOT NULL, doctor_id uuid NOT NULL,
            weekday integer NOT NULL, local_start time NOT NULL,
            local_end time NOT NULL,
            effective_from date NOT NULL, effective_to date NOT NULL,
            active boolean NOT NULL DEFAULT true, version integer NOT NULL DEFAULT 1,
            FOREIGN KEY (clinic_id, doctor_id) REFERENCES doctors(clinic_id, id),
            CONSTRAINT uq_schedules_doctor_id UNIQUE (doctor_id, id),
            CONSTRAINT ck_schedule_window CHECK (
                weekday BETWEEN 0 AND 6 AND local_start < local_end AND
                effective_from <= effective_to AND version > 0 AND
                isfinite(effective_from) AND isfinite(effective_to) AND
                mod(extract(epoch FROM local_start), 60) = 0 AND
                mod(extract(epoch FROM local_end - local_start), 1800) = 0),
            CONSTRAINT ex_schedule_overlap EXCLUDE USING gist (
                doctor_id WITH =, weekday WITH =,
                daterange(effective_from, effective_to, '[]') WITH &&,
                int4range(extract(epoch FROM local_start)::int,
                          extract(epoch FROM local_end)::int, '[)') WITH &&
            ) WHERE (active)
        )
    """)
    op.execute(
        "CREATE INDEX ix_doctor_schedules_doctor_id ON doctor_schedules (doctor_id)"
    )
    op.execute("""
        CREATE TABLE schedule_exceptions (
            id uuid PRIMARY KEY, clinic_id uuid NOT NULL, doctor_id uuid NOT NULL,
            start_at timestamptz NOT NULL, end_at timestamptz NOT NULL,
            reason varchar(160) NOT NULL, active boolean NOT NULL DEFAULT true,
            version integer NOT NULL DEFAULT 1,
            FOREIGN KEY (clinic_id, doctor_id) REFERENCES doctors(clinic_id, id),
            CONSTRAINT ck_exception_interval CHECK (
                isfinite(start_at) AND isfinite(end_at)
                AND start_at < end_at AND version > 0)
        )
    """)
    op.execute(
        "CREATE INDEX ix_schedule_exceptions_doctor_id "
        "ON schedule_exceptions (doctor_id)"
    )
    op.execute("""
        CREATE TABLE slots (
            id uuid PRIMARY KEY, clinic_id uuid NOT NULL, doctor_id uuid NOT NULL,
            schedule_id uuid NOT NULL, start_at timestamptz NOT NULL,
            end_at timestamptz NOT NULL,
            active boolean NOT NULL DEFAULT true, version integer NOT NULL DEFAULT 1,
            FOREIGN KEY (clinic_id, doctor_id) REFERENCES doctors(clinic_id, id),
            FOREIGN KEY (doctor_id, schedule_id)
                REFERENCES doctor_schedules(doctor_id, id),
            CONSTRAINT uq_slots_doctor_start UNIQUE (doctor_id, start_at),
            CONSTRAINT ck_slot_interval CHECK (
                isfinite(start_at) AND isfinite(end_at) AND
                end_at - start_at = interval '30 minutes' AND version > 0),
            CONSTRAINT ex_slot_overlap EXCLUDE USING gist (
                doctor_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&
            ) WHERE (active)
        )
    """)


def downgrade() -> None:
    op.drop_table("slots")
    op.drop_table("schedule_exceptions")
    op.drop_table("doctor_schedules")
    op.execute(
        "ALTER TABLE doctors DROP CONSTRAINT uq_doctors_clinic_id, "
        "DROP CONSTRAINT ck_doctors_schedule_version, DROP COLUMN schedule_version"
    )
    # Preserve the extension: other schemas may use it.

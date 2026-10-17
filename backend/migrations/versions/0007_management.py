"""Owned appointment changes, historical audit and immutable retry results."""

from alembic import op

revision = "0007_management"
down_revision = "0006_booking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE booking_retries ADD COLUMN response_snapshot jsonb")
    # Existing booking rows have not yet been mutable. Backfill before relaxing it.
    op.execute("""
        UPDATE booking_retries r SET response_snapshot =
            to_jsonb(a) || jsonb_build_object('accepted_fee',
                to_char(a.accepted_fee, 'FM9999999990.00'))
        FROM appointments a WHERE a.id = r.appointment_id
    """)
    op.execute(
        "ALTER TABLE booking_retries ALTER COLUMN response_snapshot SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE booking_audit ADD COLUMN before_snapshot jsonb, "
        "ADD COLUMN after_snapshot jsonb"
    )
    op.execute("""
        UPDATE booking_audit h SET after_snapshot =
            to_jsonb(a) || jsonb_build_object('accepted_fee',
                to_char(a.accepted_fee, 'FM9999999990.00'))
        FROM appointments a WHERE a.id = h.appointment_id
    """)
    op.execute("ALTER TABLE booking_audit ALTER COLUMN after_snapshot SET NOT NULL")
    op.execute(
        "ALTER TABLE appointments DROP CONSTRAINT appointments_status_check, "
        "ADD CONSTRAINT appointments_status_check "
        "CHECK (status IN ('booked', 'cancelled'))"
    )
    for table, column in (
        ("booking_proposals", "operation"),
        ("booking_retries", "operation"),
        ("booking_audit", "action"),
    ):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {table}_{column}_check, "
            f"ADD CONSTRAINT {table}_{column}_check "
            f"CHECK ({column} IN ('book', 'cancel', 'reschedule'))"
        )
    op.execute(
        "ALTER TABLE booking_proposals ADD COLUMN subject_id uuid "
        "REFERENCES appointments(id)"
    )
    op.execute(
        "ALTER TABLE booking_proposals ADD CONSTRAINT ck_proposal_subject "
        "CHECK ((operation = 'book' AND subject_id IS NULL) OR "
        "(operation <> 'book' AND subject_id IS NOT NULL))"
    )
    op.execute(
        "ALTER TABLE appointments ADD COLUMN version integer NOT NULL DEFAULT 1 "
        "CHECK (version > 0)"
    )
    op.execute(
        "ALTER TABLE booking_proposals DROP CONSTRAINT "
        "booking_proposals_appointment_id_key"
    )
    op.execute(
        "ALTER TABLE booking_audit DROP CONSTRAINT booking_audit_appointment_id_key"
    )
    op.execute(
        "CREATE INDEX ix_appointments_owned_order "
        "ON appointments(patient_id, clinic_id, start_at, id)"
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION booking_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.patient_id IS DISTINCT FROM OLD.patient_id
                OR NEW.clinic_id IS DISTINCT FROM OLD.clinic_id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.currency IS DISTINCT FROM OLD.currency
                OR NEW.timezone IS DISTINCT FROM OLD.timezone
                OR OLD.status = 'cancelled'
                OR NEW.version <> OLD.version + 1
                OR (NEW.slot_id = OLD.slot_id AND
                    (to_jsonb(NEW) - 'status' - 'version') IS DISTINCT FROM
                    (to_jsonb(OLD) - 'status' - 'version')) THEN
                RAISE EXCEPTION 'Immutable booking identity or accepted snapshot'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)


def downgrade() -> None:
    # Changes and their history cannot be safely represented by booking-only schema.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM booking_audit WHERE action <> 'book') THEN
            RAISE EXCEPTION 'Cannot downgrade appointment change history';
        END IF;
    END $$""")
    op.execute("DROP INDEX ix_appointments_owned_order")
    op.execute("ALTER TABLE appointments DROP COLUMN version")
    op.execute("ALTER TABLE booking_proposals DROP CONSTRAINT ck_proposal_subject")
    op.execute(
        "ALTER TABLE booking_proposals DROP COLUMN subject_id, "
        "ADD UNIQUE (appointment_id)"
    )
    op.execute(
        "ALTER TABLE booking_audit DROP COLUMN before_snapshot, "
        "DROP COLUMN after_snapshot, ADD UNIQUE (appointment_id)"
    )
    op.execute("ALTER TABLE booking_retries DROP COLUMN response_snapshot")
    for table, column in (
        ("booking_proposals", "operation"),
        ("booking_retries", "operation"),
        ("booking_audit", "action"),
    ):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {table}_{column}_check, "
            f"ADD CONSTRAINT {table}_{column}_check CHECK ({column} = 'book')"
        )
    op.execute(
        "ALTER TABLE appointments DROP CONSTRAINT appointments_status_check, "
        "ADD CONSTRAINT appointments_status_check CHECK (status = 'booked')"
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION booking_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
            IF (to_jsonb(NEW) - 'status') IS DISTINCT FROM
                (to_jsonb(OLD) - 'status') THEN
                RAISE EXCEPTION 'Immutable booking snapshot' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)

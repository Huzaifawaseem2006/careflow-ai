"""Patient booking, bound review proofs and atomic retry/audit records."""

from alembic import op

revision = "0006_booking"
down_revision = "0005_scheduling"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE demo_identities ADD CONSTRAINT uq_persona_clinic "
        "UNIQUE (id, clinic_id)"
    )
    op.execute("ALTER TABLE patients ADD COLUMN clinic_id uuid")
    op.execute(
        "UPDATE patients SET clinic_id = d.clinic_id FROM demo_identities d "
        "WHERE d.id = patients.demo_identity_id"
    )
    op.execute("ALTER TABLE patients ALTER COLUMN clinic_id SET NOT NULL")
    op.execute(
        "ALTER TABLE patients ADD CONSTRAINT uq_patient_clinic UNIQUE (id, clinic_id), "
        "ADD CONSTRAINT fk_patient_persona_clinic "
        "FOREIGN KEY (demo_identity_id, clinic_id) "
        "REFERENCES demo_identities(id, clinic_id)"
    )
    op.execute(
        "ALTER TABLE slots ADD CONSTRAINT uq_slot_scope "
        "UNIQUE (id, doctor_id, clinic_id)"
    )
    op.execute("""
        CREATE TABLE appointments (
            id uuid PRIMARY KEY,
            patient_id uuid NOT NULL,
            clinic_id uuid NOT NULL,
            doctor_id uuid NOT NULL,
            slot_id uuid NOT NULL,
            status varchar(20) NOT NULL CHECK (status = 'booked'),
            doctor_name varchar(120) NOT NULL,
            start_at timestamptz NOT NULL,
            end_at timestamptz NOT NULL,
            timezone varchar(80) NOT NULL CHECK (timezone = 'Asia/Karachi'),
            accepted_fee numeric NOT NULL CHECK (accepted_fee >= 0
                AND accepted_fee < 10000000000 AND scale(accepted_fee) <= 2),
            currency varchar(3) NOT NULL CHECK (currency = 'PKR'),
            created_at timestamptz NOT NULL,
            CONSTRAINT ck_appointment_time CHECK (isfinite(start_at)
                AND isfinite(end_at) AND end_at - start_at = interval '30 minutes'),
            CONSTRAINT fk_appointments_patient_clinic
                FOREIGN KEY (patient_id, clinic_id) REFERENCES patients(id, clinic_id),
            CONSTRAINT fk_appointments_slot_scope
                FOREIGN KEY (slot_id, doctor_id, clinic_id)
                REFERENCES slots(id, doctor_id, clinic_id)
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_appointments_booked_slot ON appointments(slot_id) "
        "WHERE status = 'booked'"
    )
    op.execute("CREATE INDEX ix_appointments_patient ON appointments(patient_id)")
    op.execute("""
        CREATE TABLE booking_proposals (
            proof_hash varchar(64) PRIMARY KEY,
            actor_id uuid NOT NULL REFERENCES users(id),
            patient_id uuid NOT NULL,
            clinic_id uuid NOT NULL,
            operation varchar(20) NOT NULL CHECK (operation = 'book'),
            slot_id uuid NOT NULL REFERENCES slots(id),
            summary jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            appointment_id uuid UNIQUE REFERENCES appointments(id),
            CHECK (expires_at = created_at + interval '5 minutes'),
            FOREIGN KEY (patient_id, clinic_id) REFERENCES patients(id, clinic_id)
        )
    """)
    op.execute("""
        CREATE TABLE booking_retries (
            actor_id uuid NOT NULL REFERENCES users(id),
            operation varchar(20) NOT NULL CHECK (operation = 'book'),
            key_hash varchar(64) NOT NULL,
            proof_hash varchar(64) NOT NULL REFERENCES booking_proposals(proof_hash),
            appointment_id uuid NOT NULL REFERENCES appointments(id),
            replay_until timestamptz NOT NULL,
            PRIMARY KEY (actor_id, operation, key_hash)
        )
    """)
    op.execute("""
        CREATE TABLE booking_audit (
            id uuid PRIMARY KEY,
            actor_id uuid NOT NULL REFERENCES users(id),
            action varchar(20) NOT NULL CHECK (action = 'book'),
            appointment_id uuid NOT NULL UNIQUE REFERENCES appointments(id),
            created_at timestamptz NOT NULL
        )
    """)
    op.execute("""
        CREATE FUNCTION booking_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (to_jsonb(NEW) - 'status') IS DISTINCT FROM
                (to_jsonb(OLD) - 'status') THEN
                RAISE EXCEPTION 'Immutable booking snapshot' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER booking_immutable BEFORE UPDATE ON appointments "
        "FOR EACH ROW EXECUTE FUNCTION booking_immutable()"
    )


def downgrade() -> None:
    for table in (
        "booking_audit",
        "booking_retries",
        "booking_proposals",
        "appointments",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION booking_immutable()")
    op.execute("ALTER TABLE slots DROP CONSTRAINT uq_slot_scope")
    op.execute(
        "ALTER TABLE patients DROP CONSTRAINT fk_patient_persona_clinic, "
        "DROP CONSTRAINT uq_patient_clinic, DROP COLUMN clinic_id"
    )
    op.execute("ALTER TABLE demo_identities DROP CONSTRAINT uq_persona_clinic")

"""Disclosed owned conversations and fenced complete turns."""

from alembic import op

revision = "0008_conversations"
down_revision = "0007_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE conversations (
            id uuid PRIMARY KEY,
            patient_id uuid,
            clinic_id uuid,
            guest_hash varchar(64) REFERENCES sessions(token_hash) ON DELETE CASCADE,
            created_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            disclosure_version varchar(32) NOT NULL
                CHECK(disclosure_version = 'history-v1'),
            version integer NOT NULL DEFAULT 0 CHECK(version >= 0),
            lease_id uuid,
            lease_until timestamptz,
            FOREIGN KEY(patient_id, clinic_id) REFERENCES patients(id, clinic_id),
            CHECK ((patient_id IS NOT NULL AND clinic_id IS NOT NULL
                    AND guest_hash IS NULL)
                OR (patient_id IS NULL AND clinic_id IS NULL
                    AND guest_hash IS NOT NULL)),
            CHECK(expires_at > created_at
                AND expires_at <= created_at + interval '30 days'),
            CHECK((lease_id IS NULL) = (lease_until IS NULL))
        )
    """)
    op.execute("CREATE INDEX ix_conversations_expiry ON conversations(expires_at)")
    op.execute(
        "CREATE INDEX ix_conversations_owner ON conversations(patient_id, clinic_id)"
    )
    op.execute("CREATE INDEX ix_conversations_guest ON conversations(guest_hash)")
    op.execute("""
        CREATE TABLE conversation_turns (
            conversation_id uuid NOT NULL
                REFERENCES conversations(id) ON DELETE CASCADE,
            id uuid NOT NULL,
            request_hash varchar(64) NOT NULL,
            sequence integer NOT NULL CHECK(sequence > 0),
            user_text varchar(2000),
            response jsonb,
            PRIMARY KEY(conversation_id, id),
            UNIQUE(conversation_id, sequence),
            CHECK((user_text IS NULL) = (response IS NULL)),
            CHECK(response IS NULL OR jsonb_typeof(response) = 'object')
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE conversation_turns")
    op.execute("DROP TABLE conversations")

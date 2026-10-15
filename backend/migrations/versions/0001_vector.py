"""Enable pgvector without creating domain tables."""

from alembic import op

revision = "0001_vector"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")


def downgrade() -> None:
    # No CASCADE: dependent vector columns must never be silently removed.
    op.execute("DROP EXTENSION vector")

"""Read-only readiness probe; migration is an explicit operator action."""

from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from careflow.database import SCHEMA_REVISION, database_engine


def database_is_ready() -> bool:
    try:
        engine = database_engine()
        try:
            with engine.connect() as connection:
                if MigrationContext.configure(connection).get_current_heads() != (
                    SCHEMA_REVISION,
                ):
                    return False
                return bool(
                    connection.scalar(
                        text(
                            "SELECT count(*) = 2 FROM pg_extension "
                            "WHERE extname IN ('vector', 'btree_gist')"
                        )
                    )
                )
        finally:
            engine.dispose()
    except (SQLAlchemyError, ValueError):
        # Do not log the underlying driver exception: it may contain credentials.
        return False

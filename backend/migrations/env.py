"""Alembic connection setup. Never store a database URL in Alembic config."""

from alembic import context
from alembic.util import CommandError
from careflow.database import database_engine
from sqlalchemy.exc import SQLAlchemyError


def run_migrations() -> None:
    if context.is_offline_mode():
        context.configure(dialect_name="postgresql", literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    try:
        engine = database_engine()
        try:
            with engine.connect() as connection:
                context.configure(connection=connection)
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            engine.dispose()
    except (SQLAlchemyError, ValueError):
        raise CommandError(
            "Database migration failed; check configuration, server, "
            "pgvector installation and migration-role permissions."
        ) from None


run_migrations()

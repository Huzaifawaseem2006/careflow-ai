"""Synchronous PostgreSQL connections; configuration never appears in errors."""

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import NullPool

SCHEMA_REVISION = "0003_patient_sessions"


def database_engine() -> Engine:
    try:
        url = make_url(os.environ.get("DATABASE_URL", ""))
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError
        # Connection options are fixed by the application, not by URL parameters.
        if url.query:
            raise ValueError
        return create_engine(
            url,
            poolclass=NullPool,
            hide_parameters=True,
            connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
        )
    except (ArgumentError, ValueError):
        raise ValueError("Invalid database configuration") from None

"""Opt-in real PostgreSQL tests; never reset an existing database."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from careflow.database import database_engine
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


@pytest.fixture
def disposable_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    maintenance_url = os.environ.get("TEST_DATABASE_URL")
    if not maintenance_url:
        pytest.skip("TEST_DATABASE_URL not set; real PostgreSQL verification pending")
    monkeypatch.setenv("DATABASE_URL", maintenance_url)
    try:
        admin = database_engine()
    except ValueError:
        pytest.fail("Invalid TEST_DATABASE_URL", pytrace=False)
    if admin.url.host not in {"localhost", "127.0.0.1", "::1"}:
        admin.dispose()
        pytest.fail("Integration tests require a local PostgreSQL host", pytrace=False)
    database = "careflow_test_" + uuid4().hex
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'CREATE DATABASE "{database}" TEMPLATE template0'))
    except SQLAlchemyError:
        admin.dispose()
        pytest.fail(
            "Cannot create disposable database; check local server and CREATEDB role",
            pytrace=False,
        )
    monkeypatch.setenv(
        "DATABASE_URL",
        admin.url.set(database=database).render_as_string(hide_password=False),
    )
    try:
        yield
    finally:
        try:
            with admin.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as conn:
                conn.execute(text(f'DROP DATABASE "{database}"'))
        except SQLAlchemyError:
            pytest.fail(
                f"Could not remove disposable database {database}; remove it manually",
                pytrace=False,
            )
        finally:
            admin.dispose()

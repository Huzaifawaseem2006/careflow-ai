"""Run explicitly against a locally installed PostgreSQL with pgvector."""

import subprocess
import sys
from pathlib import Path

import pytest
from careflow.database import SCHEMA_REVISION, database_engine
from careflow.main import app
from fastapi.testclient import TestClient
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.usefixtures("disposable_database")


def upgrade() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_unmigrated_database_is_not_ready_but_process_is_alive() -> None:
    # This test can run before pgvector is installed. Verify that the 503 below
    # describes a reachable, fresh database rather than a connection failure.
    engine = database_engine()
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
            assert (
                connection.scalar(text("SELECT to_regclass('alembic_version')")) is None
            )
            postgres_version = connection.scalar(text("SHOW server_version"))
        print(f"Verified unmigrated PostgreSQL {postgres_version}")
    finally:
        engine.dispose()
    with TestClient(app) as client:
        ready = client.get("/ready")
        health = client.get("/health")
        assert ready.status_code == 503
        assert ready.json() == {"status": "unavailable"}
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}


def test_clean_and_repeated_upgrade_preserve_schema_and_vector_functionality() -> None:
    upgrade()
    engine = database_engine()
    try:
        with engine.connect() as connection:
            before = connection.execute(
                text(
                    "SELECT oid, typname FROM pg_type WHERE typnamespace = "
                    "'public'::regnamespace ORDER BY oid"
                )
            ).all()
            assert (
                connection.scalar(
                    text("SELECT '[1,2,3]'::public.vector <-> '[4,6,3]'::public.vector")
                )
                == 5.0
            )
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == SCHEMA_REVISION
            )
            postgres_version = connection.scalar(text("SHOW server_version"))
            vector_version = connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
        upgrade()
        with engine.connect() as connection:
            after = connection.execute(
                text(
                    "SELECT oid, typname FROM pg_type WHERE typnamespace = "
                    "'public'::regnamespace ORDER BY oid"
                )
            ).all()
            assert after == before
        print(f"Verified PostgreSQL {postgres_version}; pgvector {vector_version}")
    finally:
        engine.dispose()
    with TestClient(app) as client:
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_missing_extension_is_not_ready_even_at_head() -> None:
    upgrade()
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP EXTENSION vector"))
    finally:
        engine.dispose()
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 503


def test_mismatched_revision_is_not_ready() -> None:
    upgrade()
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = 'stale'"))
    finally:
        engine.dispose()
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 503

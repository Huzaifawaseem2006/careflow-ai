import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from careflow.database import SCHEMA_REVISION
from pytest import MonkeyPatch

ROOT = Path(__file__).resolve().parents[2]


def test_booking_migration_enforces_scope_capacity_and_immutable_fee() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(ROOT / "alembic.ini"), output_buffer=output), "head", sql=True
    )
    ddl = output.getvalue()
    assert "CREATE TABLE appointments" in ddl
    assert "uq_appointments_booked_slot" in ddl
    assert "fk_appointments_patient_clinic" in ddl
    assert "booking_immutable" in ddl


def test_initial_migration_emits_vector_ddl_without_database(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    output = StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)

    assert "CREATE EXTENSION IF NOT EXISTS vector" in output.getvalue()
    assert "COMMIT;" in output.getvalue()
    assert ScriptDirectory.from_config(config).get_heads() == [SCHEMA_REVISION]


@pytest.mark.parametrize(
    "url",
    [
        "malformed-secret-value",
        "postgresql+psycopg://synthetic:secret-value@127.0.0.1:1/missing",
    ],
)
def test_online_migration_failure_does_not_expose_credentials(url: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "Database migration failed" in output
    assert "secret-value" not in output
    assert "Traceback" not in output

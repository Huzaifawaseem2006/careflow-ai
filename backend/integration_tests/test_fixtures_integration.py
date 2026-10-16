"""Fixture safety against real disposable PostgreSQL databases."""

from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from careflow.database import database_engine
from careflow.fixture_schema import clinics, demo_identities
from careflow.fixtures import CLINIC, IDENTITIES, apply_fixtures
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.usefixtures("disposable_database")


def snapshot() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    engine = database_engine()
    try:
        with engine.connect() as connection:
            return (
                [
                    dict(row)
                    for row in connection.execute(
                        select(clinics).order_by(clinics.c.id)
                    ).mappings()
                ],
                [
                    dict(row)
                    for row in connection.execute(
                        select(demo_identities).order_by(demo_identities.c.id)
                    ).mappings()
                ],
            )
    finally:
        engine.dispose()


def test_load_and_reset_are_deterministic_and_preserve_unrelated_rows() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    apply_fixtures("load", confirmed=True)
    expected = snapshot()
    assert expected[0] == [CLINIC]
    assert expected[1] == list(IDENTITIES)
    apply_fixtures("load", confirmed=True)
    assert snapshot() == expected
    engine = database_engine()
    other_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    try:
        with engine.begin() as connection:
            connection.execute(clinics.update().values(name="Synthetic edited clinic"))
            connection.execute(demo_identities.update().values(display_name="Edited"))
            connection.execute(
                demo_identities.insert().values(
                    **{
                        **IDENTITIES[0],
                        "id": other_id,
                        "email": "extra@careflow.example.invalid",
                    }
                )
            )
        drifted = snapshot()
        apply_fixtures("load", confirmed=True)
        assert snapshot() == drifted  # load never overwrites edits
        apply_fixtures("reset", confirmed=True)
        restored = snapshot()
        assert restored[0] == expected[0]
        assert restored[1][:-1] == expected[1]
        assert restored[1][-1] == drifted[1][-1]
        apply_fixtures("reset", confirmed=True)
        assert snapshot() == restored
        with engine.connect() as connection:
            print(
                "Fixture verification PostgreSQL",
                connection.scalar(text("SHOW server_version")),
            )
    finally:
        engine.dispose()


def test_reset_failure_rolls_back_all_fixture_changes() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    apply_fixtures("load", confirmed=True)
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(clinics.update().values(name="Synthetic edited clinic"))
            connection.execute(
                demo_identities.delete().where(
                    demo_identities.c.id == IDENTITIES[0]["id"]
                )
            )
            connection.execute(
                demo_identities.insert().values(**{**IDENTITIES[0], "id": UUID(int=99)})
            )
        before = snapshot()
        with pytest.raises(IntegrityError):
            apply_fixtures("reset", confirmed=True)
        assert snapshot() == before
    finally:
        engine.dispose()


def test_unmigrated_database_is_unchanged_by_fixture_command() -> None:
    with pytest.raises(ValueError, match="Fixture operation refused"):
        apply_fixtures("reset", confirmed=True)
    engine = database_engine()
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT to_regclass('clinics')")) is None
    finally:
        engine.dispose()

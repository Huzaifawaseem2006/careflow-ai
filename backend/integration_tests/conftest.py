"""Opt-in real PostgreSQL tests; never reset an existing database."""

import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from functools import wraps
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from careflow.accounts import provision
from careflow.catalog_fixtures import load_catalog
from careflow.database import database_engine
from careflow.fixtures import apply_fixtures
from careflow.schedule_operator import run_operation
from sqlalchemy import Engine, event, text
from sqlalchemy.exc import SQLAlchemyError

from scripts.pytest_support import TIMINGS


@pytest.fixture(autouse=True)
def integration_profile(
    monkeypatch: pytest.MonkeyPatch, integration_modules: list[ModuleType]
) -> None:
    """Measure real setup operations, including imported fixture helpers."""

    def measured(stage: str, function: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(function)
        def invoke(*args: Any, **kwargs: Any) -> Any:
            with TIMINGS.measure(stage):
                return function(*args, **kwargs)

        return invoke

    functions = {
        apply_fixtures: "fixtures",
        load_catalog: "catalog",
        provision: "accounts",
        run_operation: "schedule",
    }
    for module in integration_modules:
        for name, value in list(vars(module).items()):
            for function, stage in functions.items():
                if value is function:
                    monkeypatch.setattr(module, name, measured(stage, function))
    monkeypatch.setattr(command, "upgrade", measured("migrations", command.upgrade))
    monkeypatch.setattr(subprocess, "run", measured("subprocess", subprocess.run))


@pytest.fixture(scope="session")
def integration_modules() -> list[ModuleType]:
    directory = Path(__file__).parent.resolve()
    return [
        module
        for module in list(sys.modules.values())
        if (filename := getattr(module, "__file__", None))
        and Path(filename).parent.resolve() == directory
    ]


@pytest.fixture
def disposable_database(
    monkeypatch: pytest.MonkeyPatch,
    integration_profile: None,
) -> Iterator[None]:
    maintenance_url = os.environ.get("TEST_DATABASE_URL")
    if not maintenance_url:
        pytest.skip("TEST_DATABASE_URL not set; real PostgreSQL verification pending")
    monkeypatch.setenv("DATABASE_URL", maintenance_url)
    try:
        admin = database_engine()
    except ValueError:
        pytest.fail("Invalid TEST_DATABASE_URL", pytrace=False)
    if (
        admin.url.host not in {"localhost", "127.0.0.1", "::1"}
        or admin.url.database != "postgres"
    ):
        admin.dispose()
        pytest.fail(
            "Tests require the local postgres maintenance database", pytrace=False
        )
    database = "careflow_test_" + uuid4().hex

    def local_connect_budget(
        dialect: object, record: object, args: object, params: dict[str, object]
    ) -> None:
        # Allow extra test startup time after intermittent local setup timeouts;
        # their underlying cause is unisolated. Only this scope gets 10s;
        # production configuration and runtime SQL statement limits stay intact.
        if params.get("dbname") in {"postgres", database}:
            params["connect_timeout"] = 10

    event.listen(Engine, "do_connect", local_connect_budget)
    try:
        try:
            with (
                TIMINGS.measure("database_create"),
                admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn,
            ):
                conn.execute(text("SET statement_timeout = 30000"))
                conn.execute(text(f'CREATE DATABASE "{database}" TEMPLATE template0'))
        except SQLAlchemyError as error:
            state = getattr(getattr(error, "orig", None), "sqlstate", None)
            pytest.fail(
                f"Cannot create disposable database (SQLSTATE {state}); "
                "check local server and CREATEDB role",
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
                with (
                    TIMINGS.measure("database_drop"),
                    admin.connect().execution_options(
                        isolation_level="AUTOCOMMIT"
                    ) as conn,
                ):
                    conn.execute(text("SET statement_timeout = 30000"))
                    conn.execute(text(f'DROP DATABASE "{database}"'))
            except SQLAlchemyError:
                pytest.fail(
                    f"Could not remove disposable database {database}; remove manually",
                    pytrace=False,
                )
    finally:
        event.remove(Engine, "do_connect", local_connect_budget)
        admin.dispose()

"""Disposable-PostgreSQL mocked baseline only; never constructs a live provider."""

import argparse
import asyncio
import json
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from careflow.catalog_fixtures import DOCTORS, SPECIALTIES, load_catalog
from careflow.catalog_schema import doctors, specialties
from careflow.database import database_engine
from careflow.fixture_schema import clinics
from careflow.fixtures import CLINIC, apply_fixtures
from sqlalchemy import Engine, event, text
from sqlalchemy.exc import SQLAlchemyError

from evals.catalog_behavior import ROOT, build_report, state_digest


@contextmanager
def disposable_database() -> Iterator[None]:
    maintenance = os.environ.get("TEST_DATABASE_URL")
    if not maintenance:
        raise ValueError("Local maintenance URL required")
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = maintenance
    admin: Engine | None = None
    database = "careflow_test_" + uuid4().hex
    created = False

    def local_connect_budget(
        dialect: object, record: object, args: object, params: dict[str, object]
    ) -> None:
        # Match the integration fixture's existing local startup allowance for
        # this helper's own disposable database, including nested eval runs.
        if params.get("dbname") in {"postgres", database}:
            params["connect_timeout"] = 10

    event.listen(Engine, "do_connect", local_connect_budget)
    try:
        admin = database_engine()
        if (
            admin.url.host not in {"localhost", "127.0.0.1", "::1"}
            or admin.url.database != "postgres"
        ):
            raise ValueError("Local maintenance database required")
        with admin.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.execute(text("SET statement_timeout = 30000"))
            connection.execute(text(f'CREATE DATABASE "{database}" TEMPLATE template0'))
        created = True
        os.environ["DATABASE_URL"] = admin.url.set(database=database).render_as_string(
            hide_password=False
        )
        yield
    finally:
        try:
            if created:
                assert admin is not None
                with admin.connect().execution_options(
                    isolation_level="AUTOCOMMIT"
                ) as connection:
                    connection.execute(text("SET statement_timeout = 30000"))
                    connection.execute(text(f'DROP DATABASE "{database}"'))
        finally:
            if admin is not None:
                admin.dispose()
            event.remove(Engine, "do_connect", local_connect_budget)
            if previous is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous


def seed_behavior() -> None:
    state_digest()  # Guard the disposable target before migrations or fixture writes.
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    apply_fixtures("load", confirmed=True)
    load_catalog(confirmed=True)
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                clinics.insert().values(**{**CLINIC, "id": UUID(int=999)})
            )
            connection.execute(
                specialties.insert().values(
                    **{
                        **SPECIALTIES[0],
                        "id": UUID(int=998),
                        "clinic_id": UUID(int=999),
                    }
                )
            )
            connection.execute(
                doctors.insert().values(
                    **{
                        **DOCTORS[0],
                        "id": UUID(int=997),
                        "clinic_id": UUID(int=999),
                        "specialty_id": UUID(int=998),
                        "name": "Synthetic Foreign Doctor",
                    }
                )
            )
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--partition", choices=["dev", "held-out", "all"], default="dev"
    )
    parser.add_argument("--dataset", type=Path, default=ROOT / "evals/catalog_v1")
    parser.add_argument(
        "--report", type=Path, default=ROOT / "evals/results/catalog-mocked.json"
    )
    options = parser.parse_args()
    try:
        with disposable_database():
            seed_behavior()
            report = asyncio.run(build_report(options.partition, options.dataset))
        options.report.parent.mkdir(parents=True, exist_ok=True)
        options.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, SQLAlchemyError, subprocess.SubprocessError):
        # Do not emit exception messages, which can contain connection credentials.
        parser.exit(
            2, "Mocked baseline blocked: verify disposable PostgreSQL/configuration.\n"
        )
    print(json.dumps(report["summary"]))
    summary = report["summary"]
    assert isinstance(summary, dict)
    counts = summary["counts"]
    assert isinstance(counts, dict)
    return 1 if counts["failed"] or counts["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

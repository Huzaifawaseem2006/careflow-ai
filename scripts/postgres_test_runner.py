"""Private subprocess entry point for postgres-tests.ps1; never print raw errors."""

import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import psycopg
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

# -I isolates this entry point, so import siblings without relying on cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.test_support import check_private_temp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def checked_url(value: str) -> tuple[str, str]:
    try:
        url = make_url(value)
    except ArgumentError:
        raise ValueError("Invalid maintenance configuration") from None
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != "127.0.0.1"
        or url.port != 5432
        or url.database != "postgres"
        or url.username != "postgres"
        or not url.password
        or any(ord(character) < 32 for character in url.password)
        or url.query
    ):
        raise ValueError("Unsafe maintenance target")
    return value, url.password


def redact(value: str, url: str, password: str) -> str:
    # Filter both actual password forms and any URL an error might reconstruct.
    value = re.sub(
        r"postgres(?:ql)?(?:\+psycopg)?://[^\s\"'<>]+",
        "[database URL redacted]",
        value,
        flags=re.I,
    )
    for secret in sorted(
        {url, password, quote(password, safe=""), repr(password)[1:-1]},
        key=len,
        reverse=True,
    ):
        value = value.replace(secret, "[redacted]")
    return value


def child_environment(url: str) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("PG")
        and key.upper()
        not in {
            "DATABASE_URL",
            "TEST_DATABASE_URL",
            "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
            "ANTHROPIC_API_KEY",
        }
    }
    environment["TEST_DATABASE_URL"] = url
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


def disposable_names(url: str) -> set[str]:
    parsed = make_url(url)
    with psycopg.connect(
        host=parsed.host,
        port=parsed.port,
        dbname="postgres",
        user=parsed.username,
        password=parsed.password,
        connect_timeout=10,
        options="-c statement_timeout=30000",
        autocommit=True,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            if cursor.fetchone() != ("postgres",):
                raise ValueError("Unsafe maintenance database")
            cursor.execute(
                "SELECT datname FROM pg_database "
                "WHERE starts_with(datname, 'careflow_test_')"
            )
            return {row[0] for row in cursor.fetchall()}


def run_tests(paths: list[str], url: str, password: str) -> int:
    if any(
        not re.fullmatch(
            r"backend/integration_tests(?:/test_[a-z0-9_]+\.py(?:::[a-zA-Z0-9_]+)?)?",
            path,
        )
        for path in paths
    ):
        raise ValueError("Only integration-test selectors accepted")
    temporary = ROOT / "test-results" / ("postgres-" + uuid4().hex)
    command = [
        sys.executable,
        "-m",
        "pytest",
        *(paths or ["backend/integration_tests"]),
        "-v",
        "-rs",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "--basetemp",
        str(temporary),
        "--durations=15",
        "--careflow-timings",
        str(temporary.with_suffix(".timings.json")),
    ]
    # No raw-output files, JUnit, shell execution or password-bearing arguments.
    with subprocess.Popen(
        command,
        cwd=ROOT,
        env=child_environment(url),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            print(redact(line, url, password), end="", flush=True)
        return process.wait()


def main() -> int:
    try:
        url, password = checked_url(os.environ.pop("TEST_DATABASE_URL", ""))
        action = sys.argv[1]
        if action not in {"validate", "test"}:
            raise ValueError("Unsupported command")
        if action == "test":
            check_private_temp(ROOT / "test-results")
        before = disposable_names(url)
        if action == "validate":
            print("Local postgres maintenance credential validated.")
            return 0
        try:
            return run_tests(sys.argv[2:], url, password)
        finally:
            if disposable_names(url) - before:
                print(
                    "Disposable database cleanup incomplete; "
                    "inspect careflow_test_* databases manually."
                )
                # Do not automatically delete resources left by another session.
                raise RuntimeError("Cleanup incomplete")
            print("Maintenance catalog check: no new disposable databases remain.")
    except RuntimeError as error:
        if str(error).startswith("Private pytest temporary-directory access failed."):
            print(str(error), flush=True)
            return 1
        print("PostgreSQL test runner failed; no secret details are logged.")
        return 1
    except Exception:
        print(
            "PostgreSQL test runner failed; verify local server, credential "
            "and permissions. No secret details are logged."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

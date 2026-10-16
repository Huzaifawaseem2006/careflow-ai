import os
import subprocess
import sys

import pytest
from careflow.fixtures import CLINIC, IDENTITIES, validate_target
from sqlalchemy.engine import make_url


def test_fixture_manifest_is_explicitly_synthetic_and_stable() -> None:
    assert CLINIC["name"] == "CareFlow Fictional Demo Clinic"
    assert (CLINIC["city"], CLINIC["timezone"], CLINIC["currency"]) == (
        "Karachi",
        "Asia/Karachi",
        "PKR",
    )
    assert CLINIC["is_synthetic"] is True
    assert len({row["id"] for row in IDENTITIES}) == len(IDENTITIES) == 4
    assert [row["demo_role"] for row in IDENTITIES] == [
        "patient",
        "patient",
        "receptionist",
        "admin",
    ]
    for row in IDENTITIES:
        assert row["clinic_id"] == CLINIC["id"]
        assert row["email"].endswith("@careflow.example.invalid")
        assert row["display_name"].startswith("Synthetic ")
        assert row["is_synthetic"] is True
        assert not {"password", "password_hash", "identity_subject"} & row.keys()


@pytest.mark.parametrize(
    "target",
    [
        "postgresql+psycopg://localhost/careflow_ai",
        "postgresql+psycopg://127.0.0.1/careflow_demo",
        "postgresql+psycopg://[::1]/careflow_test_" + "a" * 32,
    ],
)
def test_local_demo_targets_are_allowed(target: str) -> None:
    validate_target(make_url(target), confirmed=True)


@pytest.mark.parametrize(
    ("target", "confirmed"),
    [
        ("postgresql+psycopg://localhost/careflow_ai", False),
        ("postgresql+psycopg://remote.invalid/careflow_ai", True),
        ("postgresql+psycopg://localhost/postgres", True),
        ("postgresql+psycopg://localhost/careflow_test_valuable", True),
        ("postgresql+psycopg:///careflow_ai", True),
        ("postgresql+psycopg://localhost/careflow_ai?host=remote.invalid", True),
        ("sqlite:///careflow_ai", True),
    ],
)
def test_fixture_target_guard_rejects_unsafe_targets(
    target: str, confirmed: bool
) -> None:
    with pytest.raises(ValueError, match="Fixture operation refused"):
        validate_target(make_url(target), confirmed=confirmed)


@pytest.mark.parametrize("arguments", [[], ["--confirm-synthetic-fixtures"]])
def test_cli_failure_is_generic_and_never_prints_credentials(
    arguments: list[str],
) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "careflow.fixtures", "reset", *arguments],
        env={
            **os.environ,
            "DATABASE_URL": (
                "postgresql+psycopg://synthetic:secret-value@127.0.0.1:1/careflow_ai"
            ),
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1
    assert "Fixture operation failed" in result.stderr
    assert "secret-value" not in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr

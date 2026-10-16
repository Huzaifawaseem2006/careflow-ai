import os
import subprocess
import sys

import pytest
from careflow.main import app
from fastapi.testclient import TestClient


def test_private_identity_requires_a_server_session() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"
    assert response.headers["cache-control"] == "no-store"


def test_login_rejects_cross_origin_before_accessing_the_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_ORIGIN", "https://testserver")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/auth/login",
            json={
                "email": "patient.one@careflow.example.invalid",
                "password": "Synthetic!",
            },
            headers={"Origin": "https://attacker.invalid"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_REJECTED"


def test_oversized_login_is_rejected_without_echoing_passwords() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/auth/login",
            content=b"x" * 4097,
            headers={
                "Origin": "https://testserver",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 413
    assert response.json()["code"] == "REQUEST_TOO_LARGE"
    assert "x" * 50 not in response.text


def test_account_cli_requires_explicit_stdin_mode_without_a_terminal() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "careflow.accounts",
            "create",
            "--email",
            "patient.one@careflow.example.invalid",
            "--confirm-synthetic-account",
        ],
        input="Synthetic-Only-Test-Input!\n",
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": "invalid-secret-value"},
        timeout=15,
    )
    assert result.returncode == 1
    assert "may be echoed" not in result.stderr
    assert "Synthetic-Only-Test-Input!" not in result.stdout + result.stderr
    assert "invalid-secret-value" not in result.stdout + result.stderr


@pytest.mark.parametrize("origin", ["", "https://[invalid", "https://testserver:bad"])
def test_invalid_auth_origin_is_a_generic_configuration_failure(
    monkeypatch: pytest.MonkeyPatch,
    origin: str,
) -> None:
    monkeypatch.setenv("AUTH_ORIGIN", origin)
    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/auth/csrf")
    assert response.status_code == 503
    assert response.json()["code"] == "AUTH_UNAVAILABLE"


def test_identity_endpoint_rejects_plain_http() -> None:
    with TestClient(app, base_url="http://testserver") as client:
        response = client.get("/auth/me")
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_REJECTED"

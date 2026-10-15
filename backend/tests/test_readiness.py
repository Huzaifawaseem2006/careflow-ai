import pytest
from careflow.main import app
from fastapi.testclient import TestClient
from pytest import MonkeyPatch


def test_missing_database_configuration_is_not_ready(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        response = client.get("/ready")
        health = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "url",
    [
        "malformed-secret-value",
        "sqlite:///secret-value",
        "postgresql+psycopg://synthetic:secret-value@127.0.0.1:1/missing",
    ],
)
def test_database_failures_are_private_and_leave_health_available(
    monkeypatch: MonkeyPatch, caplog: pytest.LogCaptureFixture, url: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    with TestClient(app) as client:
        response = client.get("/ready")
        assert client.get("/health").status_code == 200

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "secret-value" not in response.text + caplog.text

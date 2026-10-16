"""Offline validation/serialization checks; not PostgreSQL evidence."""

import os
import subprocess
import sys
from collections.abc import Iterator
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from careflow.catalog_api import Doctor, Price, connection_dependency
from careflow.catalog_fixtures import DOCTORS, SERVICES, SPECIALTIES
from careflow.main import app
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Connection


@pytest.mark.parametrize(
    "path",
    [
        "/doctors?limit=0",
        "/doctors?limit=101",
        "/services?offset=-1",
        "/specialties?offset=10001",
        "/doctors?specialty_id=secret-value",
        "/doctors?clinic_id=secret-value",
        "/doctors/secret-value",
        "/services/secret-value/fee",
        "/doctors?active=false",
        "/specialties?city=",
        "/services?city=" + "a" * 81,
    ],
)
def test_invalid_catalog_inputs_are_safe_and_do_not_execute_queries(path: str) -> None:
    connection = MagicMock(spec=Connection)

    def override() -> Iterator[Connection]:
        yield connection

    app.dependency_overrides[connection_dependency] = override
    try:
        with TestClient(app) as client:
            response = client.get(path)
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert "secret-value" not in response.text
        connection.execute.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_catalog_decimal_serialization_and_synthetic_manifest() -> None:
    assert len({row["id"] for row in SPECIALTIES + DOCTORS + SERVICES}) == 6
    doctor = Doctor.model_validate({**DOCTORS[1], "city": "Karachi", "currency": "PKR"})
    assert doctor.model_dump(mode="json")["consultation_fee"] == "3500.50"
    price = Price(id=doctor.id, amount=Decimal("0"), currency="PKR")
    assert price.model_dump(mode="json")["amount"] == "0.00"
    for amount in ("-0.01", "0.001", "NaN", "Infinity", "10000000000"):
        with pytest.raises(ValidationError):
            Price(id=doctor.id, amount=Decimal(amount), currency="PKR")


@pytest.mark.parametrize("arguments", [[], ["--confirm-synthetic-catalog"]])
def test_catalog_loader_cli_is_safe(arguments: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "careflow.catalog_fixtures", "load", *arguments],
        env={
            **os.environ,
            "DATABASE_URL": "postgresql+psycopg://demo:secret-value@127.0.0.1:1/careflow_ai",
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1
    assert "Catalog operation failed" in result.stderr
    assert "secret-value" not in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr


def test_catalog_failure_does_not_disclose_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "secret-value")
    with TestClient(app) as client:
        response = client.get("/doctors")
        assert response.status_code == 503
        assert response.json()["code"] == "CATALOG_UNAVAILABLE"
        assert "secret-value" not in response.text
        assert client.post("/doctors", json={"name": "invented"}).status_code == 405

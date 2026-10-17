"""HTTP validation and public response shape; no persistence claim."""

from collections.abc import Iterator
from datetime import datetime, time, timedelta
from unittest.mock import MagicMock

import pytest
from careflow.availability_api import Slot, connection_dependency
from careflow.main import app
from careflow.scheduling import ZONE
from fastapi.testclient import TestClient
from sqlalchemy import Connection


@pytest.mark.parametrize(
    "query",
    [
        "",
        "start_at=2026-10-17T00:00:00&end_at=2026-10-18T00:00:00Z",
        "start_at=invalid&end_at=invalid",
        "limit=101",
        "offset=-1",
        "unknown=true",
        "clinic_id=invalid",
        "start_at=1792209600&end_at=1792211400",
    ],
)
def test_bad_availability_requests_return_safe_errors(query: str) -> None:
    def database_boundary() -> Iterator[Connection]:
        yield MagicMock(spec=Connection)

    app.dependency_overrides[connection_dependency] = database_boundary
    try:
        response = TestClient(app).get(
            "/doctors/00000000-0000-4000-8000-000000000201/slots?" + query
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert set(response.json()) == {"code", "message", "correlation_id"}
    finally:
        app.dependency_overrides.clear()


def test_slot_responses_include_local_offset_and_timezone() -> None:
    slot = Slot.model_validate(
        {
            "id": "00000000-0000-4000-8000-000000000777",
            "doctor_id": "00000000-0000-4000-8000-000000000201",
            "clinic_id": "00000000-0000-4000-8000-000000000001",
            "start_at": "2026-10-17T04:00:00Z",
            "end_at": "2026-10-17T04:30:00Z",
            "version": 1,
        }
    )
    output = slot.model_dump(mode="json")
    assert output["start_at"] == "2026-10-17T09:00:00+05:00"
    assert output["end_at"] == "2026-10-17T09:30:00+05:00"
    assert output["timezone"] == "Asia/Karachi"


@pytest.mark.parametrize("start_days,end_days", [(1, 1), (2, 1), (-1, 1), (0, 31)])
def test_http_rejects_invalid_ranges(start_days: int, end_days: int) -> None:
    today = datetime.combine(datetime.now(ZONE).date(), time(), ZONE)

    def database_boundary() -> Iterator[Connection]:
        yield MagicMock(spec=Connection)

    app.dependency_overrides[connection_dependency] = database_boundary
    try:
        response = TestClient(app).get(
            "/doctors/00000000-0000-4000-8000-000000000201/slots",
            params={
                "start_at": (today + timedelta(days=start_days)).isoformat(),
                "end_at": (today + timedelta(days=end_days)).isoformat(),
            },
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
    finally:
        app.dependency_overrides.clear()

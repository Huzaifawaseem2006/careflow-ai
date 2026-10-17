"""Booking transport rejects unsafe input before database access."""

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from careflow.main import app
from fastapi.testclient import TestClient

ORIGIN = "https://localhost:8000"


@pytest.mark.parametrize("path", ["/appointments", "/appointments/proposals"])
def test_booking_bodies_are_bounded(path: str) -> None:
    response = TestClient(app, base_url=ORIGIN).post(path, content=b"x" * 4097)
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "path,body",
    [
        ("/appointments/proposals", {"slot_id": "invented"}),
        (
            "/appointments/proposals",
            {"slot_id": "00000000-0000-0000-0000-000000000001", "patient_id": "forged"},
        ),
        ("/appointments", {"proposal_token": "x" * 43, "confirmed": True}),
        ("/appointments", {}),
    ],
)
def test_booking_rejects_invalid_or_authority_fields(
    path: str, body: dict[str, object]
) -> None:
    response = TestClient(app, base_url=ORIGIN).post(path, json=body)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "forged" not in response.text


def test_booking_requires_same_origin_and_authenticated_session() -> None:
    client = TestClient(app, base_url=ORIGIN)
    body = {"slot_id": "00000000-0000-0000-0000-000000000001"}
    assert client.post("/appointments/proposals", json=body).status_code == 403
    response = client.post(
        "/appointments/proposals", json=body, headers={"Origin": ORIGIN}
    )
    assert response.status_code == 401


def test_chunked_booking_body_is_bounded_without_content_length() -> None:
    async def request() -> httpx.Response:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"x" * 2048
            yield b"x" * 2048
            yield b"x"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            return await client.post("/appointments", content=chunks())

    response = asyncio.run(request())
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


def test_owned_listing_requires_authentication() -> None:
    response = TestClient(app, base_url=ORIGIN).get("/appointments")
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("action", ["cancel", "reschedule"])
def test_change_confirmation_rejects_forged_authority_and_requires_origin(
    action: str,
) -> None:
    path = f"/appointments/00000000-0000-0000-0000-000000000001/{action}"
    client = TestClient(app, base_url=ORIGIN)
    headers = {"Idempotency-Key": "change"}
    assert (
        client.post(
            path, json={"proposal_token": "x" * 43, "confirmed": True}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post(
            path, json={"proposal_token": "x" * 43}, headers=headers
        ).status_code
        == 403
    )
    headers["Origin"] = ORIGIN
    assert (
        client.post(
            path, json={"proposal_token": "x" * 43}, headers=headers
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "query",
    [
        "limit=101",
        "limit=0",
        "cursor=not-a-cursor",
        "status=unknown",
        "start_at=2026-10-17T09:00:00",
        "start_at=2026-10-18T00:00:00Z&end_at=2026-10-17T00:00:00Z",
        "patient_id=00000000-0000-0000-0000-000000000001",
    ],
)
def test_listing_rejects_invalid_filters(query: str) -> None:
    response = TestClient(app, base_url=ORIGIN).get("/appointments?" + query)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("action", ["cancel", "reschedule"])
@pytest.mark.parametrize("suffix", ["", "/proposals"])
def test_management_bodies_are_bounded(action: str, suffix: str) -> None:
    path = f"/appointments/00000000-0000-0000-0000-000000000001/{action}{suffix}"
    result = TestClient(app, base_url=ORIGIN).post(path, content=b"x" * 4097)
    assert result.status_code == 413
    assert result.headers["cache-control"] == "no-store"


def test_private_listing_rejects_foreign_origin_and_plain_http() -> None:
    client = TestClient(app, base_url=ORIGIN)
    assert (
        client.get(
            "/appointments", headers={"Origin": "https://foreign.invalid"}
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/appointments", headers={"Sec-Fetch-Site": "cross-site"}
        ).status_code
        == 403
    )
    assert TestClient(app).get("/appointments").status_code == 403

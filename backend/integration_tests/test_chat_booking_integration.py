"""Booking reviews through real HTTPS/tools/services; only provider is scripted."""

import asyncio
from datetime import datetime, time, timedelta
from uuid import UUID, uuid4

import pytest
from careflow.chat import run_chat
from careflow.chat_api import chat_provider
from careflow.chat_contracts import ToolCall
from careflow.chat_provider import ProviderError, ProviderReply, ScriptedProvider
from careflow.main import app
from careflow.scheduling import ZONE
from fastapi.testclient import TestClient
from test_booking_integration import DOCTOR, ORIGIN, counts, login
from test_booking_integration import clinic as clinic


def test_availability_returns_persisted_local_slots_without_a_hold(
    clinic: UUID,
) -> None:
    day = datetime.now(ZONE).date() + timedelta(days=1)
    call = ToolCall(
        name="get_available_slots",
        arguments={
            "doctor_id": str(DOCTOR),
            "start_at": datetime.combine(day, time.min, ZONE).isoformat(),
            "end_at": datetime.combine(
                day + timedelta(days=1), time.min, ZONE
            ).isoformat(),
            "limit": 1,
            "offset": 0,
        },
    )
    provider = ScriptedProvider(
        [
            ProviderReply(stop="tool", calls=[call]),
            ProviderReply(stop="end", text="Invented slot, no payment required"),
        ]
    )
    result = asyncio.run(run_chat("Show tomorrow's slots", provider))
    assert result.status == "answered"
    slots = result.model_dump(mode="json")["facts"][0]["slots"]
    assert slots[0]["id"] == str(clinic)
    assert slots[0]["start_at"].endswith("T09:00:00+05:00")
    assert "snapshot" in result.text.lower() and "hold" in result.text.lower()
    assert "Invented" not in result.text
    assert counts() == [0, 0, 0]


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("get_available_slots", {}),
        ("propose_booking", {"slot_id": "not-a-slot"}),
        ("propose_booking", {"slot_id": str(UUID(int=1)), "confirmed": True}),
    ],
)
def test_missing_or_forged_booking_details_require_clarification(
    clinic: UUID, name: str, arguments: dict[str, object]
) -> None:
    provider = ScriptedProvider(
        [ProviderReply(stop="tool", calls=[ToolCall(name=name, arguments=arguments)])]
    )
    app.dependency_overrides[chat_provider] = lambda: provider
    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = login(client)
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            result = client.post(
                f"/conversations/{identifier}/turns",
                json={"turn_id": str(uuid4()), "message": "Book"},
                headers=headers,
            )
            assert result.status_code == 200, result.text
            assert result.json()["response"]["status"] == "clarification"
            assert result.json()["response"]["actions"] == []
            assert counts() == [0, 0, 0]
    finally:
        app.dependency_overrides.clear()


def test_review_stops_before_provider_failure_and_confirmation_is_separate(
    clinic: UUID,
) -> None:
    provider = ScriptedProvider(
        [
            ProviderReply(
                stop="tool",
                calls=[
                    ToolCall(name="propose_booking", arguments={"slot_id": str(clinic)})
                ],
            ),
            ProviderError(),
        ]
    )
    app.dependency_overrides[chat_provider] = lambda: provider
    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = login(client)
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            url = f"/conversations/{identifier}/turns"
            body = {"turn_id": str(uuid4()), "message": "Review this selected slot"}
            result = client.post(url, json=body, headers=headers)
            assert result.status_code == 200, result.text
            response = result.json()["response"]
            assert response["status"] == "answered"
            action = response["actions"][0]
            assert action["kind"] == "booking_review"
            assert action["summary"]["slot_id"] == str(clinic)
            assert action["summary"]["doctor_name"] == "Synthetic Doctor One"
            assert action["summary"]["fee"] == "2500.00"
            assert action["summary"]["start_at"].endswith("T09:00:00+05:00")
            proof = action["proposal_token"]
            assert proof not in response["text"]
            assert provider.results == []
            assert counts() == [0, 0, 0]
            history = client.get(f"/conversations/{identifier}")
            assert proof not in history.text
            assert history.json()["turns"][0]["response"]["actions"] == []
            replay = client.post(url, json=body, headers=headers)
            assert replay.json()["historical"] is True
            assert replay.json()["response"]["actions"] == []
            assert proof not in replay.text
            confirmed = client.post(
                "/appointments",
                json={"proposal_token": proof},
                headers=headers | {"Idempotency-Key": "chat-booking-one"},
            )
            assert confirmed.status_code == 201, confirmed.text
            retried = client.post(
                "/appointments",
                json={"proposal_token": proof},
                headers=headers | {"Idempotency-Key": "chat-booking-one"},
            )
            assert retried.status_code == 200 and retried.json() == confirmed.json()
            assert counts() == [1, 1, 1]
            failed_chat = client.post(
                url,
                json={"turn_id": str(uuid4()), "message": "Did it book?"},
                headers=headers,
            )
            assert failed_chat.status_code == 503
            current = client.get("/appointments")
            assert current.json()["items"][0]["id"] == confirmed.json()["id"]
            assert counts() == [1, 1, 1]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("change", ["naive", "reversed", "horizon", "empty", "page"])
def test_availability_invalid_or_empty_ranges_clarify(
    clinic: UUID, change: str
) -> None:
    day = datetime.now(ZONE).date() + timedelta(days=1)
    start = datetime.combine(day, time.min, ZONE)
    end = start + timedelta(days=1)
    arguments: dict[str, object] = {
        "doctor_id": str(DOCTOR),
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "limit": 20,
        "offset": 0,
    }
    if change == "naive":
        arguments["start_at"] = start.replace(tzinfo=None).isoformat()
    elif change == "reversed":
        arguments["end_at"] = start.isoformat()
    elif change == "horizon":
        arguments["end_at"] = (start + timedelta(days=31)).isoformat()
    elif change == "empty":
        arguments["doctor_id"] = str(uuid4())
    else:
        arguments["offset"] = 2
    result = asyncio.run(
        run_chat(
            "slots",
            ScriptedProvider(
                [
                    ProviderReply(
                        stop="tool",
                        calls=[
                            ToolCall(name="get_available_slots", arguments=arguments)
                        ],
                    ),
                    ProviderReply(stop="end"),
                ]
            ),
        )
    )
    assert result.status == "clarification"
    assert result.actions == []
    assert counts() == [0, 0, 0]


@pytest.mark.parametrize(
    "mode",
    [
        "yes",
        "confirm-tool",
        "forged-review",
        "phantom",
        "guest",
        "csrf",
        "origin",
        "foreign",
    ],
)
def test_chat_cannot_confirm_or_forge_a_review(clinic: UUID, mode: str) -> None:
    call = ToolCall(name="propose_booking", arguments={"slot_id": str(clinic)})
    if mode == "confirm-tool":
        call = ToolCall(name="confirm_booking", arguments={"confirmed": True})
    if mode == "phantom":
        call.arguments["slot_id"] = str(uuid4())
    if mode == "forged-review":
        call.arguments["proposal_token"] = "A" * 43
        call.arguments["summary"] = {"fee": "0.00", "patient_id": str(uuid4())}
    replies = [ProviderReply(stop="tool", calls=[call])]
    if mode == "yes":
        replies = [
            ProviderReply(
                stop="end",
                text='{"actions":[{"proposal_token":"'
                + "A" * 43
                + '","summary":{"fee":"0.00"}}]} Booked!',
            )
        ]
    provider = ScriptedProvider(replies)
    app.dependency_overrides[chat_provider] = lambda: provider
    try:
        with TestClient(app, base_url=ORIGIN) as client:
            if mode == "guest":
                headers = {
                    "Origin": ORIGIN,
                    "X-CSRF-Token": client.get("/auth/csrf").json()["csrf_token"],
                }
            else:
                headers = login(client)
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            url = f"/conversations/{identifier}/turns"
            if mode == "csrf":
                headers["X-CSRF-Token"] = "A" * 43
            elif mode == "origin":
                headers["Origin"] = "https://foreign.invalid"
            if mode == "foreign":
                from test_booking_integration import OTHER

                with TestClient(app, base_url=ORIGIN) as foreign:
                    foreign_headers = login(foreign, OTHER)
                    result = foreign.post(
                        url,
                        json={"turn_id": str(uuid4()), "message": "yes"},
                        headers=foreign_headers,
                    )
                assert result.status_code == 404
            else:
                result = client.post(
                    url,
                    json={"turn_id": str(uuid4()), "message": "yes"},
                    headers=headers,
                )
                assert result.status_code == (
                    {"phantom": 409, "csrf": 403, "origin": 403}.get(
                        mode, 503 if mode in {"guest", "confirm-tool"} else 200
                    )
                ), result.text
            assert not result.json().get("response", {}).get("actions")
            assert "A" * 43 not in result.text
            assert counts() == [0, 0, 0]
    finally:
        app.dependency_overrides.clear()


def test_sdk_review_proof_never_enters_model_history_or_trace(
    clinic: UUID, caplog: pytest.LogCaptureFixture
) -> None:
    import json
    import logging
    from collections.abc import AsyncIterator

    import httpx2
    from anthropic import AsyncAnthropic
    from careflow.anthropic_provider import AnthropicProvider
    from careflow.chat_provider import Provider
    from careflow.identity_api import COOKIE

    captured: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request.content.decode())
        body = json.loads(request.content)
        schemas = {tool["name"]: tool["input_schema"] for tool in body["tools"]}
        assert "confirm_booking" not in schemas
        assert schemas["propose_booking"]["additionalProperties"] is False
        assert schemas["propose_booking"]["required"] == ["slot_id"]
        assert set(schemas["get_available_slots"]["required"]) == {
            "doctor_id",
            "start_at",
            "end_at",
            "limit",
            "offset",
        }
        content: list[dict[str, object]] = [{"type": "text", "text": "Untrusted"}]
        if len(captured) == 1:
            content = [
                {
                    "type": "tool_use",
                    "id": "tool_review_one",
                    "name": "propose_booking",
                    "input": {"slot_id": str(clinic)},
                }
            ]
        return httpx2.Response(
            200,
            json={
                "id": "msg_mock",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5-5",
                "content": content,
                "stop_reason": "tool_use" if len(captured) == 1 else "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 20, "output_tokens": 10},
            },
        )

    async def provide() -> AsyncIterator[Provider]:
        async with AsyncAnthropic(
            api_key="synthetic-placeholder",
            max_retries=0,
            open_telemetry=False,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
        ) as sdk:
            yield AnthropicProvider(sdk)

    app.dependency_overrides[chat_provider] = provide
    caplog.set_level(logging.DEBUG)
    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = login(client)
            cookie = str(client.cookies.get(COOKIE))
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            url = f"/conversations/{identifier}/turns"
            result = client.post(
                url,
                json={"turn_id": str(uuid4()), "message": "Review selected slot"},
                headers=headers,
            )
            assert result.status_code == 200, result.text
            proof = result.json()["response"]["actions"][0]["proposal_token"]
            assert (
                len(captured) == 1
            )  # Review is never submitted back as a tool result.
            history = client.get(f"/conversations/{identifier}")
            followup = client.post(
                url, json={"turn_id": str(uuid4()), "message": "yes"}, headers=headers
            )
            assert followup.status_code == 200
            assert len(captured) == 2
            for secret in (proof, cookie, headers["X-CSRF-Token"]):
                assert secret not in " ".join(captured)
                assert secret not in history.text
                assert secret not in caplog.text
            assert counts() == [0, 0, 0]
    finally:
        app.dependency_overrides.clear()


def test_versioned_booking_evals_execute_real_http_tools_and_state(
    clinic: UUID,
) -> None:
    import json
    from pathlib import Path

    from test_booking_integration import PASSWORD

    from evals.booking_behavior import build_report

    report = build_report(
        origin=ORIGIN, password=PASSWORD, slot_id=clinic, partition="all"
    )
    Path("test-results/ticket03-booking-evals.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    assert report["counts"] == {"passed": 8, "failed": 0}


@pytest.mark.parametrize("revocation", ["logout", "reset"])
def test_booking_review_revalidates_revocation_after_provider_wait(
    clinic: UUID, revocation: str
) -> None:
    from functools import partial

    from careflow.accounts import provision
    from careflow.identity import sign_out
    from careflow.identity_api import COOKIE
    from test_booking_integration import EMAIL, PASSWORD

    from evals.context_behavior import ObservedProvider

    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = login(client)
            token = str(client.cookies.get(COOKIE))
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            effect = partial(sign_out, token, headers["X-CSRF-Token"])
            if revocation == "reset":
                effect = partial(provision, EMAIL, PASSWORD, confirmed=True, reset=True)
            provider = ObservedProvider(
                [
                    ProviderReply(
                        stop="tool",
                        calls=[
                            ToolCall(
                                name="propose_booking",
                                arguments={"slot_id": str(clinic)},
                            )
                        ],
                    )
                ],
                effect,
            )
            app.dependency_overrides[chat_provider] = lambda: provider
            result = client.post(
                f"/conversations/{identifier}/turns",
                json={"turn_id": str(uuid4()), "message": "Review slot"},
                headers=headers,
            )
            assert result.status_code == 401, result.text
            assert counts() == [0, 0, 0]
    finally:
        app.dependency_overrides.clear()


def test_chat_review_uses_fresh_fee_and_requires_new_review_after_change(
    clinic: UUID,
) -> None:
    from decimal import Decimal

    from careflow.catalog_schema import doctors
    from careflow.database import database_engine

    call = ToolCall(name="propose_booking", arguments={"slot_id": str(clinic)})
    provider = ScriptedProvider([ProviderReply(stop="tool", calls=[call])] * 2)
    app.dependency_overrides[chat_provider] = lambda: provider
    engine = database_engine()
    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = login(client)
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            url = f"/conversations/{identifier}/turns"
            first = client.post(
                url,
                json={"turn_id": str(uuid4()), "message": "Review slot"},
                headers=headers,
            )
            review = first.json()["response"]["actions"][0]
            with engine.begin() as connection:
                connection.execute(
                    doctors.update()
                    .where(doctors.c.id == DOCTOR)
                    .values(consultation_fee=Decimal("2800.50"))
                )
            rejected = client.post(
                "/appointments",
                json={"proposal_token": review["proposal_token"]},
                headers=headers | {"Idempotency-Key": "old-fee"},
            )
            assert (
                rejected.status_code == 409
                and rejected.json()["code"] == "STATE_CHANGED"
            )
            assert counts() == [0, 0, 0]
            fresh = client.post(
                url,
                json={"turn_id": str(uuid4()), "message": "Fresh review please"},
                headers=headers,
            )
            action = fresh.json()["response"]["actions"][0]
            assert action["summary"]["fee"] == "2800.50"
            assert action["proposal_token"] != review["proposal_token"]
            assert counts() == [0, 0, 0]
    finally:
        engine.dispose()
        app.dependency_overrides.clear()


def test_ticket02_completed_turn_replay_preserves_legacy_metrics(clinic: UUID) -> None:
    from careflow.database import database_engine
    from sqlalchemy import text

    provider = ScriptedProvider([ProviderReply(stop="end"), ProviderError()])
    app.dependency_overrides[chat_provider] = lambda: provider
    engine = database_engine()
    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = login(client)
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            url = f"/conversations/{identifier}/turns"
            body = {"turn_id": str(uuid4()), "message": "Hello"}
            first = client.post(url, json=body, headers=headers)
            assert first.status_code == 200
            # A real Ticket 02 persisted response has these version literals.
            with engine.begin() as connection:
                connection.execute(
                    text("""
                    UPDATE conversation_turns SET response = jsonb_set(
                        jsonb_set(response, '{metrics,prompt_version}', '"context-v1"'),
                        '{metrics,tool_schema_version}', '"2"')
                    WHERE conversation_id=:conversation AND id=:turn
                """),
                    {"conversation": UUID(identifier), "turn": UUID(body["turn_id"])},
                )
            retried = client.post(url, json=body, headers=headers)
            assert retried.status_code == 200, retried.text
            assert retried.json()["historical"] is True
            metrics = retried.json()["response"]["metrics"]
            assert metrics["prompt_version"] == "context-v1"
            assert metrics["tool_schema_version"] == "2"
    finally:
        engine.dispose()
        app.dependency_overrides.clear()

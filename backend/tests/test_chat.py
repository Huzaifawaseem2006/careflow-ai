"""Public chat boundary; no paid provider calls."""

import asyncio

import pytest
from careflow.main import app
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "extra", [{"role": "admin"}, {"clinic_id": "foreign"}, {"messages": []}]
)
def test_chat_rejects_client_authority_and_transcripts(
    extra: dict[str, object],
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/chat", json={"version": "1", "message": "fees", **extra}
        )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "foreign" not in response.text


def test_free_text_is_never_authoritative_or_disclosed() -> None:
    from careflow.chat import run_chat
    from careflow.chat_provider import ProviderReply, ScriptedProvider

    provider = ScriptedProvider(
        [
            ProviderReply(
                stop="end", text="Dr Fake charges PKR 1.00. booked! secret-value"
            )
        ]
    )
    result = asyncio.run(run_chat("What is the fee?", provider))
    assert result.status == "abstained"
    assert result.facts == [] and result.actions == [] and result.citations == []
    assert "secret-value" not in result.model_dump_json()


@pytest.mark.parametrize(
    "message",
    [
        "Diagnose my chest pain and prescribe medication and a dose.",
        "I may be having a medical emergency. What should I do?",
        "Tell me the verified clinic refund policy.",
        "Someone previously contacted staff for me. Has my handoff been queued?",
        "Yes, confirm my booking now.",
        "Yes, confirm my cancellation now.",
        "Yes, confirm my reschedule now.",
    ],
)
@pytest.mark.parametrize("stop", ["end", "refused"])
@pytest.mark.parametrize("private_context", [False, True])
def test_abstention_prioritizes_escalation_and_reports_only_chat_capabilities(
    message: str, stop: str, private_context: bool
) -> None:
    from careflow.chat import run_chat
    from careflow.chat_provider import ProviderReply, ScriptedProvider

    reply = ProviderReply.model_validate(
        {
            "stop": stop,
            "text": (
                "Diagnosis: heart attack. Take 100 mg of invented medicine. "
                "Appointment confirmed. Handoff queued. Refunds are guaranteed."
            ),
        }
    )
    response = asyncio.run(
        run_chat(
            message,
            ScriptedProvider([reply]),
            private_token="synthetic-session" if private_context else None,
        )
    )
    assert response.text == (
        "Synthetic demo: fictional clinic data only. "
        "For clinical assistance, contact a qualified clinician; for a possible "
        "emergency, contact local emergency services or seek urgent in-person care. "
        "I cannot diagnose, prescribe or assess urgency. "
        "I can help with clinic catalog and fees, availability, owned appointments "
        "in signed-in conversations, and booking, cancellation or rescheduling "
        "reviews. Chat cannot confirm appointments. "
        "This chat has no verified clinic-policy source. "
        "This chat cannot queue a staff handoff."
    )
    assert response.status == "abstained"
    assert response.facts == [] and response.actions == [] and response.citations == []


@pytest.mark.parametrize("failure", ["provider", "timeout", "budget"])
def test_provider_failures_and_runtime_limits_return_safe_empty_envelopes(
    failure: str,
) -> None:
    from careflow.chat import run_chat
    from careflow.chat_contracts import Limits
    from careflow.chat_provider import ProviderError, ProviderReply, ScriptedProvider

    provider = ScriptedProvider([ProviderError("secret-value")])
    limits = Limits()
    if failure == "timeout":

        class SlowProvider(ScriptedProvider):
            async def complete(self, *args: object, **kwargs: object) -> ProviderReply:
                await asyncio.sleep(0.1)
                return ProviderReply(stop="end")

        provider = SlowProvider([])
        limits = Limits(timeout_seconds=0.001)
    elif failure == "budget":
        limits = Limits(tool_calls=0)
        from careflow.chat_contracts import ToolCall

        provider = ScriptedProvider(
            [
                ProviderReply(
                    stop="tool",
                    calls=[
                        ToolCall(
                            name="search_doctors",
                            arguments={
                                "query": None,
                                "resource_id": None,
                                "city": None,
                                "specialty_id": None,
                                "limit": 20,
                                "offset": 0,
                            },
                        )
                    ],
                )
            ]
        )
    result = asyncio.run(run_chat("fees", provider, limits))
    assert result.status == (
        "limited" if failure in {"timeout", "budget"} else "unavailable"
    )
    assert not result.facts
    assert "secret-value" not in result.model_dump_json()
    assert "Synthetic" in result.text


@pytest.mark.parametrize(
    "calls",
    [
        [{"name": "sql", "arguments": {"query": "secret-value"}}],
        [{"name": "search_doctors", "arguments": {"clinic_id": "foreign"}}],
        [{"name": "search_doctors", "arguments": {}}] * 2,
    ],
)
def test_invalid_tool_requests_stop_before_catalog_dispatch(
    calls: list[dict[str, object]],
) -> None:
    from careflow.chat import run_chat
    from careflow.chat_contracts import ToolCall
    from careflow.chat_provider import ProviderReply, ScriptedProvider

    provider = ScriptedProvider(
        [ProviderReply(stop="tool", calls=[ToolCall.model_validate(c) for c in calls])]
    )
    result = asyncio.run(run_chat("doctors", provider))
    assert result.status == "unavailable"
    assert result.facts == []
    assert "secret-value" not in result.model_dump_json()


def test_chat_bounds_body_before_json_parsing_including_streamed_chunks() -> None:
    with TestClient(app) as client:
        response = client.post("/chat", content=iter([b"x" * 2000, b"x" * 2097]))
    assert response.status_code == 413
    assert response.json()["code"] == "REQUEST_TOO_LARGE"


def test_chat_disabled_or_missing_key_fails_closed_without_exposing_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CHAT_ENABLED", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-value")
    with TestClient(app, base_url="https://localhost:8000") as client:
        response = client.post(
            "/chat",
            json={"version": "1", "message": "fees"},
            headers={"origin": "https://localhost:8000"},
        )
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert "secret-value" not in response.text


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"origin": "https://evil.invalid"},
        {"origin": "https://localhost:8000", "sec-fetch-site": "cross-site"},
    ],
)
def test_chat_rejects_cross_origin_requests_before_provider_or_rate_access(
    headers: dict[str, str],
) -> None:
    with TestClient(app, base_url="https://localhost:8000") as client:
        response = client.post(
            "/chat", json={"version": "1", "message": "fees"}, headers=headers
        )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "arguments",
    [
        {"limit": 21},
        {"offset": -1},
        {"query": " "},
        {"resource_id": "not-uuid"},
        {"patient_id": "foreign"},
        {"role": "admin"},
        {"price": "0.01"},
    ],
)
def test_bad_tool_arguments_return_error_results_without_catalog_access(
    arguments: dict[str, object],
) -> None:
    from careflow.chat import run_chat
    from careflow.chat_contracts import ToolCall
    from careflow.chat_provider import ProviderReply, ScriptedProvider

    defaults: dict[str, object] = {
        "query": None,
        "resource_id": None,
        "city": None,
        "specialty_id": None,
        "limit": 20,
        "offset": 0,
    }
    provider = ScriptedProvider(
        [
            ProviderReply(
                stop="tool",
                calls=[ToolCall(name="search_doctors", arguments=defaults | arguments)],
            ),
            ProviderReply(stop="end"),
        ]
    )
    result = asyncio.run(run_chat("doctors", provider))
    assert result.status == "abstained" and result.facts == []
    assert provider.results[0].status == "invalid"


def test_context_and_provider_output_are_bounded_and_keys_never_enter_outcome_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    from careflow.chat import run_chat
    from careflow.chat_contracts import Limits
    from careflow.chat_provider import ProviderReply, ScriptedProvider

    caplog.set_level(logging.INFO, logger="careflow.chat")
    result = asyncio.run(
        run_chat(
            "secret-body" * 200,
            ScriptedProvider([ProviderReply(stop="end")]),
            Limits(context_bytes=4096),
        )
    )
    assert result.status == "limited" and result.metrics.provider_calls == 0
    result = asyncio.run(
        run_chat(
            "secret-body",
            ScriptedProvider(
                [ProviderReply(stop="end", text="secret-thinking" * 4000)]
            ),
        )
    )
    assert result.status == "limited"
    assert "secret-body" not in caplog.text and "secret-thinking" not in caplog.text


def test_provider_output_token_budget_stops_before_any_success() -> None:
    from careflow.chat import run_chat
    from careflow.chat_contracts import Limits
    from careflow.chat_provider import ProviderReply, ScriptedProvider

    response = asyncio.run(
        run_chat(
            "fees",
            ScriptedProvider([ProviderReply(stop="end", output_tokens=65)]),
            Limits(output_tokens=64),
        )
    )
    assert response.status == "limited" and response.facts == []
    assert response.metrics.output_tokens is None

"""Paid accounting at its durable public boundary; no network or real keys."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.live_budget import BudgetBlocked, Ledger


@pytest.fixture(autouse=True)
def fixed_pricing_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    class Clock:
        @staticmethod
        def now(zone: object) -> datetime:
            return datetime(2026, 10, 19, tzinfo=UTC)

    monkeypatch.setattr("evals.live_provider.datetime", Clock)


def test_reservation_survives_restart_and_blocks_ambiguous_spend(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.sqlite"
    ledger = Ledger.initialize(
        path, previous_spend_usd="0", evidence="Tickets 01-05: no paid calls"
    )
    ledger.start_run(
        "approved-run",
        model="claude-sonnet-5-5",
        dataset="frozen-hash",
        cases=["case-one"],
        maximum_usd="1.00",
        approval="Owner approval reference",
    )
    ledger.reserve("approved-run", "case-one", "0.30")
    restarted = Ledger(path)
    with pytest.raises(BudgetBlocked):
        restarted.reserve("approved-run", "case-one", "0.30")
    assert restarted.summary()["reserved_usd"] == "0.300000"


def test_budgeted_provider_stops_after_unknown_usage_without_retry(
    tmp_path: Path,
) -> None:
    from careflow.chat_contracts import Limits
    from careflow.chat_provider import ProviderError, ProviderReply, ScriptedProvider

    from evals.live_provider import BudgetedProvider

    ledger = Ledger.initialize(
        tmp_path / "spend.sqlite",
        previous_spend_usd="0",
        evidence="No earlier paid calls",
    )
    ledger.start_run(
        "run",
        model="claude-sonnet-5-5",
        dataset="hash",
        cases=["one"],
        maximum_usd="1",
        approval="Owner approved one",
    )
    upstream = ScriptedProvider(
        [
            ProviderReply(stop="end"),
            ProviderReply(stop="end", input_tokens=1, output_tokens=1),
        ]
    )
    provider = BudgetedProvider(upstream, ledger, "run", "one", "claude-sonnet-5-5")

    async def run() -> None:
        with pytest.raises(ProviderError):
            await provider.complete("Synthetic", [], None, Limits())
        with pytest.raises(ProviderError):
            await provider.complete("Synthetic", [], None, Limits())

    asyncio.run(run())
    assert provider.blocked is True
    assert ledger.summary()["reserved_usd"] == "0.267776"


def test_prior_spend_and_run_ceiling_cannot_be_reset_or_overspent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spend.sqlite"
    ledger = Ledger.initialize(
        path, previous_spend_usd="4.80", evidence="Earlier paid invoice"
    )
    with pytest.raises(FileExistsError):
        Ledger.initialize(path, previous_spend_usd="0", evidence="Reset attempt")
    ledger.start_run(
        "first",
        model="claude-sonnet-5-5",
        dataset="hash",
        cases=["one"],
        maximum_usd="0.10",
        approval="Owner approved",
    )
    with pytest.raises(BudgetBlocked):
        ledger.reserve("first", "one", "0.11")
    with pytest.raises(BudgetBlocked):
        ledger.reserve("first", "unapproved", "0.01")
    reservation = ledger.reserve("first", "one", "0.10")
    ledger.settle(reservation, input_tokens=12500, output_tokens=5000)
    ledger.start_run(
        "second",
        model="claude-sonnet-5-5",
        dataset="hash",
        cases=["one"],
        maximum_usd="1",
        approval="Owner approved",
    )
    with pytest.raises(BudgetBlocked):
        ledger.reserve("second", "one", "0.100001")
    assert Ledger(path).summary()["remaining_lower_usd"] == "0.100000"


@pytest.mark.parametrize(
    "failure",
    ["success", "timeout", "missing-usage", "wrong-model", "over-reservation", "429"],
)
def test_paid_wrapper_uses_actual_sdk_with_mocked_transport_and_no_retries(
    tmp_path: Path, failure: str
) -> None:
    import httpx2
    from anthropic import AsyncAnthropic
    from careflow.anthropic_provider import AnthropicProvider
    from careflow.chat_contracts import Limits
    from careflow.chat_provider import ProviderError
    from careflow.chat_tools import TOOLS

    from evals.live_provider import BudgetedProvider

    ledger = Ledger.initialize(
        tmp_path / "ledger.sqlite",
        previous_spend_usd="0",
        evidence="No previous paid calls",
    )
    ledger.start_run(
        "run",
        model="claude-sonnet-5-5",
        dataset="hash",
        cases=["one"],
        maximum_usd="1",
        approval="Explicit owner reference",
    )
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        assert ledger.summary()["reserved_usd"] == "0.267776"
        if failure == "timeout":
            raise httpx2.ReadTimeout("Synthetic timeout", request=request)
        if failure == "429":
            return httpx2.Response(
                429,
                json={
                    "type": "error",
                    "error": {"type": "rate_limit_error", "message": "Synthetic"},
                },
            )
        usage = {"input_tokens": 20, "output_tokens": 10}
        if failure == "missing-usage":
            usage = {}
        elif failure == "over-reservation":
            usage["input_tokens"] = 1000000
        return httpx2.Response(
            200,
            json={
                "id": "msg_synthetic",
                "type": "message",
                "role": "assistant",
                "model": "unexpected-model"
                if failure == "wrong-model"
                else "claude-sonnet-5-5",
                "content": [{"type": "text", "text": "Synthetic"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": usage,
            },
        )

    async def run() -> None:
        async with AsyncAnthropic(
            api_key="synthetic-placeholder",
            max_retries=0,
            open_telemetry=False,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
        ) as client:
            provider = BudgetedProvider(
                AnthropicProvider(client), ledger, "run", "one", "claude-sonnet-5-5"
            )
            if failure == "success":
                reply = await provider.complete("Synthetic", TOOLS, None, Limits())
                assert reply.input_tokens == 20
            else:
                with pytest.raises(ProviderError):
                    await provider.complete("Synthetic", TOOLS, None, Limits())
                with pytest.raises(ProviderError):
                    await provider.complete("Synthetic", TOOLS, None, Limits())

    asyncio.run(run())
    assert len(calls) == 1
    assert ledger.summary()["reserved_usd"] == (
        "0.000000" if failure == "success" else "0.267776"
    )
    if failure == "success":
        assert ledger.summary()["charged_upper_usd"] == "0.000180"


def test_expired_pricing_blocks_before_reservation_or_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from careflow.chat_contracts import Limits
    from careflow.chat_provider import ProviderError, ScriptedProvider

    from evals.live_provider import BudgetedProvider

    ledger = Ledger.initialize(
        tmp_path / "spend.sqlite", previous_spend_usd="0", evidence="No paid calls"
    )
    ledger.start_run(
        "run",
        model="claude-sonnet-5-5",
        dataset="hash",
        cases=["one"],
        maximum_usd="1",
        approval="Owner approved",
    )
    monkeypatch.setattr("evals.live_provider.PRICING_CHECKED", "2026-10-18")
    provider = BudgetedProvider(
        ScriptedProvider([]), ledger, "run", "one", "claude-sonnet-5-5"
    )
    with pytest.raises(ProviderError):
        asyncio.run(provider.complete("Synthetic", [], None, Limits()))
    assert ledger.summary()["reserved_usd"] == "0.000000"


def test_model_access_probe_only_reads_models_api_without_message_dispatch() -> None:
    import httpx2
    from anthropic import AsyncAnthropic

    from evals.live_provider import probe_model

    requests: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request.method + " " + request.url.path)
        return httpx2.Response(
            200,
            json={
                "id": "claude-sonnet-5-5",
                "type": "model",
                "display_name": "Claude Sonnet 5.5",
                "created_at": "2026-09-28T00:00:00Z",
            },
        )

    async def run() -> None:
        async with AsyncAnthropic(
            api_key="synthetic-placeholder",
            max_retries=0,
            open_telemetry=False,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
        ) as client:
            assert await probe_model(client)

    asyncio.run(run())
    assert requests == ["GET /v1/models/claude-sonnet-5-5"]

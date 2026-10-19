"""Guard the existing provider seam; never infer rollback or retry charged calls."""

from collections.abc import Sequence
from datetime import UTC, datetime

import httpx2
from anthropic import APIError, AsyncAnthropic
from careflow.anthropic_provider import AnthropicProvider
from careflow.chat_api import chat_provider
from careflow.chat_contracts import Limits, ToolDefinition, ToolResult
from careflow.chat_provider import Provider, ProviderError, ProviderReply

from evals.live_budget import BudgetBlocked, Ledger, dollars

PRICING_CHECKED = "2026-10-19"
PRICING_SOURCE = "https://platform.claude.com/docs/en/models/sonnet-5-5/overview"
MODEL = "claude-sonnet-5-5"


async def probe_model(client: AsyncAnthropic) -> bool:
    """Read account model availability; never dispatch a Messages request."""
    AnthropicProvider(client)  # Apply the existing SDK body-logging suppression.
    try:
        model = await client.models.retrieve(MODEL)
        return model.id == MODEL
    except (APIError, httpx2.HTTPError, ValueError):
        return False


async def verify_model_access() -> bool:
    available = False
    # Reuse the exact official-host, no-proxy, no-retry application client.
    async for provider in chat_provider(Limits()):
        if isinstance(provider, AnthropicProvider):
            available = await probe_model(provider.client)
    return available


class BudgetedProvider:
    def __init__(
        self, provider: Provider, ledger: Ledger, run: str, case: str, model: str
    ) -> None:
        self.provider = provider
        self.ledger = ledger
        self.run = run
        self.case = case
        self.model = model
        self.blocked = False

    async def complete(
        self,
        message: str,
        tools: Sequence[ToolDefinition],
        result: ToolResult | None,
        limits: Limits,
    ) -> ProviderReply:
        try:
            if self.blocked or self.model != MODEL or limits.model != self.model:
                raise BudgetBlocked("Unapproved model")
            if datetime.now(UTC).date().isoformat() != PRICING_CHECKED:
                raise BudgetBlocked("Reverify dated pricing before dispatch")
            # Text-only request: one token per UTF-8 byte plus 16,384 tokens
            # for tool/system protocol overhead; adapter bounds schema/history
            # together at context_bytes. Includes thinking in max output tokens.
            reservation = self.ledger.reserve(
                self.run,
                self.case,
                dollars((limits.context_bytes + 16384) * 4 + limits.output_tokens * 10),
            )
        except BudgetBlocked:
            self.blocked = True
            raise ProviderError() from None
        try:
            reply = await self.provider.complete(message, tools, result, limits)
            if reply.input_tokens is None or reply.output_tokens is None:
                raise BudgetBlocked("Unknown usage")
            if reply.resolved_model != self.model:
                raise BudgetBlocked("Unexpected resolved model; reevaluation required")
            self.ledger.settle(
                reservation,
                input_tokens=reply.input_tokens,
                output_tokens=reply.output_tokens,
            )
            return reply
        except BaseException:
            # Cancellation, transport/protocol errors or absent usage leave a
            # durable reservation. Subsequent dispatch fails closed globally.
            self.blocked = True
            raise ProviderError() from None

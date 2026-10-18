"""Bounded single-turn chat. Model prose never enters the authoritative response."""

import asyncio
import logging
import time

from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from careflow.catalog import CatalogError
from careflow.chat_contracts import (
    ChatResponse,
    DoctorFact,
    Limits,
    Metrics,
    ServiceFact,
    ToolOutcome,
    ToolResult,
)
from careflow.chat_provider import Provider, ProviderError
from careflow.chat_tools import ARGUMENTS, TOOLS, execute_catalog, validate_call

DISCLOSURE = "Synthetic demo: fictional clinic data only. "
ABSTENTION = (
    "I can help with catalog and fee lookup only. I have no verified policy or "
    "availability evidence and cannot access patient records, change appointments, "
    "reveal private instructions or secrets, diagnose, prescribe or assess urgency. "
    "For clinical assistance, contact a qualified clinician; for a possible emergency, "
    "contact local emergency services or seek urgent in-person care. "
    "No staff handoff has been queued. Please specify a doctor, specialty or service."
)


async def run_chat(
    message: str, provider: Provider, limits: Limits | None = None
) -> ChatResponse:
    limits = limits or Limits()
    metrics = Metrics(requested_model=limits.model)
    started = time.monotonic()
    result: ToolResult | None = None
    facts: list[ToolResult] = []
    context_bytes = len(message.encode()) + sum(
        len(t.model_dump_json().encode()) for t in TOOLS
    )
    response = ChatResponse(
        status="abstained", text=DISCLOSURE + ABSTENTION, metrics=metrics
    )
    try:
        async with asyncio.timeout(limits.timeout_seconds):
            for _ in range(limits.provider_calls):
                if context_bytes > limits.context_bytes:
                    raise TimeoutError()
                metrics.provider_calls += 1
                reply = await provider.complete(message, TOOLS, result, limits)
                context_bytes += len(reply.model_dump_json().encode())
                if (
                    context_bytes > limits.context_bytes
                    or len(reply.text.encode()) > limits.response_bytes
                ):
                    raise TimeoutError()
                metrics.resolved_model = reply.resolved_model
                metrics.sdk_version = reply.sdk_version
                if reply.input_tokens is not None:
                    metrics.input_tokens = (
                        metrics.input_tokens or 0
                    ) + reply.input_tokens
                if reply.output_tokens is not None:
                    if reply.output_tokens > limits.output_tokens:
                        raise TimeoutError()
                    metrics.output_tokens = (
                        metrics.output_tokens or 0
                    ) + reply.output_tokens
                if reply.stop != "tool":
                    if reply.calls:
                        raise ProviderError()
                    if (
                        reply.stop == "end"
                        and facts
                        and result is not None
                        and result.status != "invalid"
                    ):
                        response.facts = facts
                        response.text = render_facts(facts)
                        response.status = (
                            "clarification"
                            if any(f.status in {"empty", "ambiguous"} for f in facts)
                            else "answered"
                        )
                    break
                if len(reply.calls) != 1 or reply.calls[0].name not in ARGUMENTS:
                    raise ProviderError()
                if len(metrics.tools) >= limits.tool_calls:
                    raise TimeoutError()
                call = reply.calls[0]
                tool_started = time.monotonic()
                try:
                    validate_call(call)
                except ValidationError:
                    result = ToolResult(name=call.name, status="invalid")
                else:
                    try:
                        result = await run_in_threadpool(execute_catalog, call)
                    except (CatalogError, ValidationError):
                        metrics.tools.append(
                            ToolOutcome(
                                name=call.name,
                                status="unavailable",
                                latency_ms=int(
                                    (time.monotonic() - tool_started) * 1000
                                ),
                            )
                        )
                        raise ProviderError() from None
                    facts.append(result)
                metrics.tools.append(
                    ToolOutcome(
                        name=call.name,
                        status=result.status,
                        latency_ms=int((time.monotonic() - tool_started) * 1000),
                    )
                )
                context_bytes += len(result.model_dump_json().encode())
            else:
                raise TimeoutError()
    except (ProviderError, ValidationError, ValueError, TypeError):
        response.status = "unavailable"
    except CatalogError:
        response.status = "unavailable"
    except TimeoutError:
        response.status = "limited"
    if response.status in {"unavailable", "limited"}:
        response.facts = []
        metrics.input_tokens = None
        metrics.output_tokens = None
        response.text = (
            DISCLOSURE + "Chat unavailable or limit reached; "
            "please narrow your request and try again."
        )
    metrics.latency_ms = int((time.monotonic() - started) * 1000)
    if len(response.model_dump_json().encode()) > limits.response_bytes:
        response.status = "limited"
        response.facts = []
        response.text = (
            DISCLOSURE + "Response limit reached; please narrow your request."
        )
    logging.getLogger("careflow.chat").info(
        "chat_outcome correlation=%s status=%s calls=%d tools=%d latency_ms=%d",
        response.correlation_id,
        response.status,
        metrics.provider_calls,
        len(metrics.tools),
        metrics.latency_ms,
    )
    return response


def render_facts(facts: list[ToolResult]) -> str:
    lines = [
        DISCLOSURE + "Catalog results only; these do not establish availability, "
        "policies or doctor-service associations."
    ]
    for fact in facts:
        lines.append(f"{fact.name}: page offset {fact.offset}, limit {fact.limit}.")
        if fact.status == "empty":
            lines.append(
                "No matches on this page. Please clarify the name, specialty or city, "
                "or request another page."
            )
        elif fact.status == "ambiguous":
            lines.append(
                "Multiple matches. Please select a specific record "
                "before treating a fee as your requested fee."
            )
        for row in fact.data:
            label = f"{row.name} ({row.id}), {row.city}"
            if isinstance(row, DoctorFact):
                label += (
                    f"; consultation fee PKR {row.consultation_fee:.2f}; "
                    f"specialty {row.specialty_id}"
                )
            elif isinstance(row, ServiceFact):
                label += f"; service fee PKR {row.fee:.2f}"
            lines.append(label + ".")
    return "\n".join(lines)

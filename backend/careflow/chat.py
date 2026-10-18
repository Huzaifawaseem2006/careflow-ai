"""Bounded single-turn chat. Model prose never enters the authoritative response."""

import asyncio
import logging
import time
from collections.abc import Callable

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
from careflow.chat_tools import (
    APPOINTMENT_TOOL,
    TOOLS,
    AppointmentArguments,
    execute_appointments,
    execute_catalog,
    validate_call,
)

DISCLOSURE = "Synthetic demo: fictional clinic data only. "
ABSTENTION = (
    "I can help with catalog and fee lookup, and owned appointment lookup in "
    "signed-in conversations. I have no verified policy or "
    "availability evidence and cannot change appointments, "
    "reveal private instructions or secrets, diagnose, prescribe or assess urgency. "
    "For clinical assistance, contact a qualified clinician; for a possible emergency, "
    "contact local emergency services or seek urgent in-person care. "
    "No staff handoff has been queued. Please specify a doctor, specialty or service."
)


async def run_chat(
    message: str,
    provider: Provider,
    limits: Limits | None = None,
    *,
    private_token: str | None = None,
    authorize: Callable[[], None] | None = None,
) -> ChatResponse:
    limits = limits or Limits()
    metrics = Metrics(requested_model=limits.model)
    started = time.monotonic()
    result: ToolResult | None = None
    facts: list[ToolResult] = []
    tools = (*TOOLS, APPOINTMENT_TOOL) if private_token is not None else TOOLS
    allowed = {tool.name for tool in tools}
    context_bytes = len(message.encode()) + sum(
        len(t.model_dump_json().encode()) for t in tools
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
                if authorize is not None:
                    await run_in_threadpool(authorize)
                reply = await provider.complete(message, tools, result, limits)
                if authorize is not None:
                    await run_in_threadpool(authorize)
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
                if len(reply.calls) != 1 or reply.calls[0].name not in allowed:
                    raise ProviderError()
                if len(metrics.tools) >= limits.tool_calls:
                    raise TimeoutError()
                call = reply.calls[0]
                tool_started = time.monotonic()
                try:
                    if call.name == "get_my_appointments":
                        import json

                        AppointmentArguments.model_validate_json(
                            json.dumps(call.arguments), strict=True
                        )
                    else:
                        validate_call(call)
                except ValidationError:
                    result = ToolResult(name=call.name, status="invalid")
                else:
                    try:
                        result = (
                            await run_in_threadpool(
                                execute_appointments, call, private_token
                            )
                            if call.name == "get_my_appointments"
                            else await run_in_threadpool(execute_catalog, call)
                        )
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
        DISCLOSURE
        + (
            "Validated lookup results; these do not establish availability or policies."
            if any(f.appointments is not None for f in facts)
            else "Catalog results only; these do not establish availability, "
            "policies or doctor-service associations."
        )
    ]
    for fact in facts:
        if fact.appointments is not None:
            lines.append(
                "Your current appointment results (a snapshot, not a new booking):"
            )
            for appointment in fact.appointments.items:
                lines.append(
                    f"{appointment.id}: {appointment.doctor_name}; "
                    f"{appointment.start_at.isoformat()} {appointment.timezone}; "
                    f"{appointment.status}; PKR {appointment.accepted_fee:.2f}."
                )
            if not fact.appointments.items:
                lines.append("No matching appointments in this page/range.")
            if fact.appointments.next_cursor:
                lines.append("More results are available using the returned cursor.")
            continue
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

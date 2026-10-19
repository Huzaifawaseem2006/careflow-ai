"""Rescheduling review adapter; only the separate application request can move."""

import json
from uuid import UUID

from fastapi.encoders import jsonable_encoder

from careflow.chat_contracts import Contract, RescheduleReview, ToolCall, ToolDefinition
from careflow.management import propose_change


class RescheduleArguments(Contract):
    appointment_id: UUID
    slot_id: UUID


RESCHEDULE_TOOL = ToolDefinition(
    name="propose_reschedule",
    description="Review moving one explicitly selected owned appointment to a real "
    "selected available slot. Use current get_my_appointments and bounded "
    "get_available_slots data; clarify ambiguous source or target and absent slots. "
    "Never invent IDs or intent. Reviews current target fee even when unchanged. "
    "No move or hold occurs. Stops the turn; a separate authenticated user request "
    "outside chat must confirm. Chat consent cannot confirm.",
    schema_=RescheduleArguments.model_json_schema(),
)


def execute_reschedule(
    call: ToolCall, token: str | None, csrf: str | None
) -> RescheduleReview:
    arguments = RescheduleArguments.model_validate_json(
        json.dumps(call.arguments), strict=True
    )
    result = propose_change(
        arguments.appointment_id, "reschedule", arguments.slot_id, token, csrf
    )
    return RescheduleReview.model_validate_json(json.dumps(jsonable_encoder(result)))


def render_reschedule_review(review: RescheduleReview) -> str:
    source, target = review.summary.appointment, review.summary.target
    return (
        "Synthetic demo: fictional clinic data only. Rescheduling review only; "
        "the original appointment remains booked and the target is not held. "
        f"Appointment {source.id}; from {source.doctor_name}; "
        f"{source.start_at.isoformat()} to {source.end_at.isoformat()} "
        f"{source.timezone}; accepted fee PKR {source.accepted_fee:.2f}. "
        f"Target {target.slot_id}; {target.doctor_name}; "
        f"{target.start_at.isoformat()} to {target.end_at.isoformat()} "
        f"{target.timezone}; current target fee PKR {target.fee:.2f}, "
        "including when unchanged. "
        f"Review expires at {review.expires_at.isoformat()} or target start, "
        "whichever is earlier. The backend rechecks availability, fee, state and "
        "the inclusive source 24-hour cutoff at confirmation. Confirm separately "
        f"with POST /appointments/{source.id}/reschedule using this action's proof "
        "and one Idempotency-Key. Chat yes cannot confirm. A changed review needs "
        "a fresh proposal and explicit confirmation. On an uncertain confirmation "
        "outcome retry that same proof and key; do not start another action. "
        "Exact replay describes the original operation; read appointments for "
        "current state."
    )

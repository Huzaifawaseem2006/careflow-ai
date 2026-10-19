"""Cancellation proposal adapter; confirmation remains outside the model loop."""

import json
from uuid import UUID

from fastapi.encoders import jsonable_encoder

from careflow.chat_contracts import (
    CancellationReview,
    Contract,
    ToolCall,
    ToolDefinition,
)
from careflow.management import propose_change


class CancellationArguments(Contract):
    appointment_id: UUID


CANCELLATION_TOOL = ToolDefinition(
    name="propose_cancellation",
    description="Review cancellation of one explicitly selected owned appointment. "
    "Use current get_my_appointments data; clarify ambiguous matches or selection. "
    "Never invent appointment IDs or intent. Creates only a review, no cancellation "
    "or capacity release. Stops the turn. A separate authenticated user request "
    "outside chat must confirm; chat consent cannot confirm.",
    schema_=CancellationArguments.model_json_schema(),
)


def execute_cancellation(
    call: ToolCall, token: str | None, csrf: str | None
) -> CancellationReview:
    arguments = CancellationArguments.model_validate_json(
        json.dumps(call.arguments), strict=True
    )
    result = propose_change(arguments.appointment_id, "cancel", None, token, csrf)
    return CancellationReview.model_validate_json(json.dumps(jsonable_encoder(result)))


def render_cancellation_review(review: CancellationReview) -> str:
    source = review.summary.appointment
    return (
        "Synthetic demo: fictional clinic data only. Cancellation review only; "
        "appointment remains booked and capacity has not been released. "
        f"Appointment {source.id}; {source.doctor_name}; "
        f"{source.start_at.isoformat()} to {source.end_at.isoformat()} "
        f"{source.timezone}; accepted fee PKR {source.accepted_fee:.2f}. "
        f"Review expires at {review.expires_at.isoformat()}. "
        "The backend rechecks eligibility and the inclusive 24-hour cancellation "
        "cutoff at confirmation. Confirm separately with POST "
        f"/appointments/{source.id}/cancel using this action's proof and one "
        "Idempotency-Key. Chat yes cannot confirm. On an uncertain confirmation "
        "outcome, retry that same proof and key; do not start another action."
    )

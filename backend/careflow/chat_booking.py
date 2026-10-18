"""Proposal-only domain adapter. Protected actions never enter provider results."""

import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from pydantic import AwareDatetime, Field, model_validator

from careflow.availability import read_availability
from careflow.booking import propose
from careflow.catalog import catalog_connection
from careflow.chat_contracts import (
    BookingReview,
    BookingReviewSummary,
    Contract,
    SlotFact,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from careflow.scheduling import ZONE, validate_range


class BookingArguments(Contract):
    slot_id: UUID


BOOKING_TOOL = ToolDefinition(
    name="propose_booking",
    description="Review one explicitly selected persisted slot for the signed-in "
    "patient. "
    "Clarify missing or ambiguous doctor/date/time. Never invent a slot ID or intent. "
    "Creates a review only, no appointment or hold. Stops the turn. "
    "Confirmation requires a distinct authenticated user request outside chat.",
    schema_=BookingArguments.model_json_schema(),
)


class AvailabilityArguments(Contract):
    doctor_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    limit: int = Field(ge=1, le=20)
    offset: int = Field(ge=0, le=10000)

    @model_validator(mode="after")
    def valid_range(self) -> "AvailabilityArguments":
        validate_range(self.start_at, self.end_at, now=datetime.now(UTC))
        return self


AVAILABILITY_TOOL = ToolDefinition(
    name="get_available_slots",
    description="Read persisted future free slots for one explicit doctor and "
    "offset-aware start/end range, within today plus 29 Asia/Karachi dates. "
    "Half-open range; bounded "
    "page, no hold. Clarify missing or ambiguous doctor/date/time; never invent slots.",
    schema_=AvailabilityArguments.model_json_schema(),
)


def execute_availability(call: ToolCall) -> ToolResult:
    arguments = AvailabilityArguments.model_validate_json(
        json.dumps(call.arguments), strict=True
    )
    with catalog_connection() as connection:
        rows = read_availability(connection, **arguments.model_dump())
    items = [SlotFact.model_validate(row) for row in rows]
    for item in items:
        item.start_at = item.start_at.astimezone(ZONE)
        item.end_at = item.end_at.astimezone(ZONE)
    return ToolResult(
        name=call.name,
        status="ok" if items else "empty",
        slots=items,
        limit=arguments.limit,
        offset=arguments.offset,
    )


def execute_booking(
    call: ToolCall, token: str | None, csrf: str | None
) -> BookingReview:
    arguments = BookingArguments.model_validate_json(
        json.dumps(call.arguments), strict=True
    )
    result = propose(arguments.slot_id, token, csrf)
    summary = result["summary"]
    if not isinstance(summary, dict):
        raise ValueError("Invalid review")
    return BookingReview.model_validate_json(
        json.dumps(
            jsonable_encoder(
                {
                    "proposal_token": result["proposal_token"],
                    "summary": {
                        key: summary[key] for key in BookingReviewSummary.model_fields
                    },
                    "expires_at": result["expires_at"],
                }
            )
        )
    )


def render_review(review: BookingReview) -> str:
    summary = review.summary
    return (
        "Synthetic demo: fictional clinic data only. Review only; no booking or hold. "
        f"{summary.doctor_name}; {summary.start_at.isoformat()} to "
        f"{summary.end_at.isoformat()} {summary.timezone}; PKR {summary.fee:.2f}. "
        f"Review expires at {review.expires_at.isoformat()} or slot start, "
        "whichever is earlier. "
        "Confirm separately through the appointment endpoint using this action's proof "
        "and one Idempotency-Key. Chat yes cannot confirm. On an uncertain "
        "confirmation "
        "outcome, retry that same proof and key; do not start another action."
    )

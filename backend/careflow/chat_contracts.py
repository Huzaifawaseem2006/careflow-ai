"""Version 1 chat contracts. Authority and response wording belong to the server."""

from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    model_validator,
)

from careflow.fixtures import CLINIC


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Limits(Contract):
    model: str = Field(default="claude-sonnet-5-5", min_length=1, max_length=100)
    provider_calls: int = Field(default=5, ge=1, le=8)
    tool_calls: int = Field(default=4, ge=0, le=6)
    output_tokens: int = Field(default=1024, ge=64, le=2048)
    context_bytes: int = Field(default=48000, ge=4096, le=64000)
    response_bytes: int = Field(default=16000, ge=2048, le=32000)
    timeout_seconds: float = Field(default=20.0, gt=0, le=60)
    rate_per_minute: int = Field(default=10, ge=1, le=30)


class ToolCall(Contract):
    name: str = Field(min_length=1, max_length=64)
    arguments: dict[str, object]


class ToolDefinition(Contract):
    name: str
    description: str
    schema_: dict[str, object]


Amount = Annotated[
    Decimal,
    Field(ge=0, lt=Decimal("10000000000"), decimal_places=2),
    PlainSerializer(lambda value: format(value, ".2f"), return_type=str),
]


class SpecialtyFact(Contract):
    id: UUID
    clinic_id: UUID
    name: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def fixed_clinic(self) -> Self:
        if self.clinic_id != CLINIC["id"]:
            raise ValueError("Invalid clinic")
        return self


class DoctorFact(SpecialtyFact):
    specialty_id: UUID
    consultation_fee: Amount
    currency: Literal["PKR"]


class ServiceFact(SpecialtyFact):
    fee: Amount
    currency: Literal["PKR"]


class AppointmentFact(Contract):
    id: UUID
    doctor_id: UUID
    doctor_name: str = Field(min_length=1, max_length=120)
    start_at: AwareDatetime
    end_at: AwareDatetime
    status: Literal["booked", "cancelled"]
    timezone: Literal["Asia/Karachi"]
    accepted_fee: Amount
    currency: Literal["PKR"]


class AppointmentPage(Contract):
    items: list[AppointmentFact] = Field(max_length=20)
    next_cursor: str | None = Field(max_length=100)


class SlotFact(Contract):
    id: UUID
    clinic_id: UUID
    doctor_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    version: int = Field(ge=1)
    timezone: Literal["Asia/Karachi"] = "Asia/Karachi"

    @model_validator(mode="after")
    def valid_slot(self) -> Self:
        if self.clinic_id != CLINIC["id"] or self.end_at <= self.start_at:
            raise ValueError("Invalid slot")
        return self


class ToolResult(Contract):
    name: str
    status: Literal["ok", "empty", "ambiguous", "invalid", "unavailable"]
    data: list[DoctorFact | ServiceFact | SpecialtyFact] = Field(
        default_factory=list, max_length=20
    )
    limit: int = Field(default=20, ge=1, le=20)
    offset: int = Field(default=0, ge=0, le=10000)
    appointments: AppointmentPage | None = Field(
        default=None, exclude_if=lambda v: v is None
    )
    slots: list[SlotFact] | None = Field(
        default=None, max_length=20, exclude_if=lambda v: v is None
    )


class ToolOutcome(Contract):
    name: str
    status: str
    latency_ms: int


class BookingReviewSummary(Contract):
    slot_id: UUID
    doctor_id: UUID
    clinic_id: UUID
    doctor_name: str = Field(min_length=1, max_length=120)
    start_at: AwareDatetime
    end_at: AwareDatetime
    timezone: Literal["Asia/Karachi"]
    fee: Amount
    currency: Literal["PKR"]

    @model_validator(mode="after")
    def valid_scope(self) -> Self:
        if self.clinic_id != CLINIC["id"] or self.end_at <= self.start_at:
            raise ValueError("Invalid review")
        return self


class BookingReview(Contract):
    kind: Literal["booking_review"] = "booking_review"
    proposal_token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    summary: BookingReviewSummary
    expires_at: AwareDatetime


class CancellationAppointment(AppointmentFact):
    patient_id: UUID
    clinic_id: UUID
    slot_id: UUID
    created_at: AwareDatetime
    status: Literal["booked"]

    @model_validator(mode="after")
    def valid_scope(self) -> Self:
        if self.clinic_id != CLINIC["id"] or self.end_at <= self.start_at:
            raise ValueError("Invalid cancellation review")
        return self


class CancellationReviewSummary(Contract):
    operation: Literal["cancel"]
    appointment: CancellationAppointment
    target: None


class CancellationReview(Contract):
    kind: Literal["cancellation_review"] = "cancellation_review"
    proposal_token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    summary: CancellationReviewSummary
    expires_at: AwareDatetime


class Metrics(Contract):
    provider_calls: int = 0
    tools: list[ToolOutcome] = Field(default_factory=list)
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    requested_model: str = "claude-sonnet-5-5"
    resolved_model: str | None = None
    sdk_version: str | None = None
    # Historical owned responses retain their original version metadata on replay.
    prompt_version: Literal["context-v1", "booking-v1", "cancellation-v1"] = (
        "cancellation-v1"
    )
    tool_schema_version: Literal["2", "3", "4"] = "4"


class ChatResponse(Contract):
    version: Literal["1"] = "1"
    status: Literal["answered", "clarification", "abstained", "unavailable", "limited"]
    text: str
    facts: list[ToolResult] = Field(default_factory=list)
    actions: list[BookingReview | CancellationReview] = Field(
        default_factory=list, max_length=1
    )
    citations: list[object] = Field(default_factory=list, max_length=0)
    correlation_id: UUID = Field(default_factory=uuid4)
    metrics: Metrics = Field(default_factory=Metrics)

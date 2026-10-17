"""Distinct authenticated review and confirmation HTTP operations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from careflow.booking import confirm, propose
from careflow.catalog_api import Amount
from careflow.identity_api import COOKIE, check_origin

router = APIRouter(prefix="/appointments")


class ProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_id: UUID


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class ReviewSummary(BaseModel):
    slot_id: UUID
    doctor_id: UUID
    clinic_id: UUID
    doctor_name: str
    start_at: datetime
    end_at: datetime
    timezone: Literal["Asia/Karachi"]
    fee: Amount
    currency: Literal["PKR"]


class ProposalResponse(BaseModel):
    proposal_token: str
    summary: ReviewSummary
    expires_at: datetime


class BookingResponse(BaseModel):
    id: UUID
    patient_id: UUID
    clinic_id: UUID
    doctor_id: UUID
    slot_id: UUID
    status: Literal["booked"]
    doctor_name: str
    start_at: datetime
    end_at: datetime
    timezone: Literal["Asia/Karachi"]
    accepted_fee: Amount
    currency: Literal["PKR"]
    created_at: datetime


@router.post("/proposals", status_code=201, response_model=ProposalResponse)
def proposal(request: Request, body: ProposalRequest) -> JSONResponse:
    check_origin(request)
    result = propose(
        body.slot_id, request.cookies.get(COOKIE), request.headers.get("x-csrf-token")
    )
    return JSONResponse(
        status_code=201,
        content=jsonable_encoder(ProposalResponse.model_validate(result)),
        headers={"Cache-Control": "no-store"},
    )


@router.post("", response_model=BookingResponse)
def confirmation(
    request: Request,
    body: ConfirmationRequest,
    idempotency_key: str = Header(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    ),
) -> JSONResponse:
    check_origin(request)
    result, replay = confirm(
        body.proposal_token,
        idempotency_key,
        request.cookies.get(COOKIE),
        request.headers.get("x-csrf-token"),
    )
    return JSONResponse(
        status_code=200 if replay else 201,
        content=jsonable_encoder(BookingResponse.model_validate(result)),
        headers={"Cache-Control": "no-store"},
    )

"""Disclosed history HTTP boundary; authority never comes from model arguments."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from careflow import conversations
from careflow.chat import run_chat
from careflow.chat_api import chat_limits, chat_provider
from careflow.chat_contracts import Contract, Limits
from careflow.chat_provider import Provider, ProviderError, ScriptedProvider
from careflow.identity import IdentityError, limit_attempts
from careflow.identity_api import COOKIE, check_origin

router = APIRouter()


class CreateConversation(Contract):
    disclosure_version: Literal["history-v1"]


def response(content: object, status: int = 200) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder(content),
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/chat/disclosure")
def disclosure(request: Request) -> JSONResponse:
    check_origin(request, mutation=False)
    return response(
        {"version": conversations.DISCLOSURE_VERSION, "text": conversations.DISCLOSURE}
    )


@router.post("/conversations")
def create(request: Request, body: CreateConversation) -> JSONResponse:
    check_origin(request)
    limit_attempts(
        "conversation:ip:" + (request.client.host if request.client else "unknown"),
        limit=10,
        seconds=60,
    )
    return response(
        conversations.create(
            request.cookies.get(COOKIE), request.headers.get("x-csrf-token")
        ),
        201,
    )


@router.get("/conversations/{identifier}")
def history(request: Request, identifier: UUID) -> JSONResponse:
    check_origin(request, mutation=False)
    return response(conversations.history(request.cookies.get(COOKIE), identifier))


class TurnRequest(Contract):
    turn_id: UUID = Field(strict=False)
    message: str = Field(min_length=1, max_length=2000, pattern=r"\S")


@router.post("/conversations/{identifier}/turns")
async def turn(
    request: Request,
    identifier: UUID,
    body: TurnRequest,
    limits: Annotated[Limits, Depends(chat_limits)],
    provider: Annotated[Provider | None, Depends(chat_provider)],
) -> JSONResponse:
    check_origin(request)
    token = request.cookies.get(COOKIE)
    await run_in_threadpool(
        limit_attempts,
        "conversation-turn:ip:"
        + (request.client.host if request.client else "unknown"),
        limit=limits.rate_per_minute,
        seconds=60,
    )
    claim = await run_in_threadpool(
        conversations.begin,
        token,
        request.headers.get("x-csrf-token"),
        identifier,
        body.turn_id,
        body.message,
        limits.context_bytes // 2,
    )
    if claim.response is not None:
        await run_in_threadpool(conversations.authorize_turn, token, claim)
        return response(
            {"replayed": True, "historical": True, "response": claim.response}
        )
    if provider is None:
        unavailable = await run_chat(
            claim.context, ScriptedProvider([ProviderError()]), limits
        )
        await run_in_threadpool(conversations.finish, token, claim, unavailable)
        raise IdentityError(503, "CHAT_UNAVAILABLE", "Chat unavailable.")
    result = await run_chat(
        claim.context,
        provider,
        limits,
        private_token=token if claim.private else None,
        authorize=lambda: conversations.authorize_turn(token, claim),
    )
    await run_in_threadpool(conversations.finish, token, claim, result)
    # Revalidate after the completion transaction too; no cached session authority.
    await run_in_threadpool(
        conversations.authorize_turn,
        token,
        conversations.Turn(identifier, body.turn_id, None, "", "", claim.private),
    )
    return response(
        {"replayed": False, "historical": False, "response": result},
        503 if result.status in {"limited", "unavailable"} else 200,
    )


@router.delete("/conversations/{identifier}")
def delete(request: Request, identifier: UUID) -> Response:
    check_origin(request)
    conversations.delete(
        request.cookies.get(COOKIE), request.headers.get("x-csrf-token"), identifier
    )
    return Response(status_code=204, headers={"Cache-Control": "no-store"})

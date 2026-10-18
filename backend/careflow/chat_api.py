"""Single-turn public chat; clients cannot supply conversation roles or authority."""

import os
from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from careflow.chat import run_chat
from careflow.chat_contracts import ChatResponse, Limits
from careflow.chat_provider import Provider
from careflow.identity import IdentityError, limit_attempts
from careflow.identity_api import check_origin

router = APIRouter()


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal["1"]
    message: str = Field(min_length=1, max_length=2000, pattern=r"\S")


def chat_limits() -> Limits:
    values = {
        key: os.environ["CHAT_" + key.upper()]
        for key in Limits.model_fields
        if "CHAT_" + key.upper() in os.environ
    }
    try:
        return Limits.model_validate_strings(values)
    except ValidationError:
        raise IdentityError(503, "CHAT_UNAVAILABLE", "Chat unavailable.") from None


async def chat_provider(
    limits: Annotated[Limits, Depends(chat_limits)],
) -> AsyncIterator[Provider | None]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if os.environ.get("CHAT_ENABLED") != "true" or not key:
        yield None
        return
    import httpx2
    from anthropic import AsyncAnthropic

    from careflow.anthropic_provider import AnthropicProvider

    # Explicit transport prevents environment proxies/redirects from forwarding the key.
    async with AsyncAnthropic(
        api_key=key,
        auth_token="",
        base_url="https://api.anthropic.com",
        max_retries=0,
        open_telemetry=False,
        timeout=limits.timeout_seconds,
        http_client=httpx2.AsyncClient(
            follow_redirects=False, trust_env=False, timeout=limits.timeout_seconds
        ),
    ) as client:
        yield AnthropicProvider(client)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    limits: Annotated[Limits, Depends(chat_limits)],
    provider: Annotated[Provider | None, Depends(chat_provider)],
) -> JSONResponse:
    check_origin(request)
    if provider is None:
        raise IdentityError(503, "CHAT_UNAVAILABLE", "Chat unavailable.")
    await run_in_threadpool(
        limit_attempts,
        "chat:ip:" + (request.client.host if request.client else "unknown"),
        limit=limits.rate_per_minute,
        seconds=60,
    )
    result = await run_chat(body.message, provider, limits)
    return JSONResponse(
        status_code=503 if result.status in {"unavailable", "limited"} else 200,
        content=result.model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )

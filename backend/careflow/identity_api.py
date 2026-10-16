"""Patient session HTTP boundary; identity is resolved only on the server."""

import os
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from careflow.identity import (
    IdentityError,
    PatientIdentity,
    SessionGrant,
    csrf_session,
    limit_attempts,
    patient_identity,
    sign_in,
    sign_out,
)

router = APIRouter(prefix="/auth")
COOKIE = "__Host-careflow_session"


class AuthBodyLimit:
    """Bound authentication bodies before JSON parsing, including chunked bodies."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not scope["path"].startswith("/auth/")
        ):
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > 4096:
                response = error_response(413, "REQUEST_TOO_LARGE")
                await response(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=160)
    password: SecretStr = Field(min_length=1, max_length=128)


class CSRFResponse(BaseModel):
    csrf_token: str = Field(min_length=43, max_length=43)


def error_response(
    status: int, code: str, message: str = "Request rejected."
) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if status == 429:
        headers["Retry-After"] = "300"
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "correlation_id": str(uuid4())},
        headers=headers,
    )


def check_origin(request: Request, *, mutation: bool = True) -> None:
    origin = os.environ.get("AUTH_ORIGIN", "https://localhost:8000")
    try:
        parsed = urlsplit(origin)
        _ = parsed.port  # Validate a configured port before accepting the origin.
    except ValueError:
        raise IdentityError(
            503, "AUTH_UNAVAILABLE", "Authentication unavailable."
        ) from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise IdentityError(503, "AUTH_UNAVAILABLE", "Authentication unavailable.")
    supplied = request.headers.get("origin")
    if (
        request.url.scheme != "https"
        or (mutation and supplied != origin)
        or (supplied is not None and supplied != origin)
        or request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise IdentityError(403, "CSRF_REJECTED")


def session_response(grant: SessionGrant) -> JSONResponse:
    response = JSONResponse(
        content=CSRFResponse(csrf_token=grant.csrf_token).model_dump(),
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        COOKIE,
        grant.token,
        max_age=grant.max_age,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return response


@router.get("/csrf", response_model=CSRFResponse)
def csrf(request: Request) -> JSONResponse:
    check_origin(request, mutation=False)
    limit_attempts(
        "ip:" + (request.client.host if request.client else "unknown"),
        limit=30,
        seconds=60,
    )
    return session_response(csrf_session(request.cookies.get(COOKIE)))


@router.post("/login", response_model=CSRFResponse)
def login(request: Request, body: LoginRequest) -> JSONResponse:
    check_origin(request)
    limit_attempts(
        "ip:" + (request.client.host if request.client else "unknown"),
        limit=30,
        seconds=60,
    )
    limit_attempts("email:" + body.email.strip().lower(), limit=5, seconds=300)
    return session_response(
        sign_in(
            body.email,
            body.password.get_secret_value(),
            request.cookies.get(COOKIE),
            request.headers.get("x-csrf-token"),
        )
    )


@router.get("/me", response_model=PatientIdentity)
def current_patient(request: Request) -> JSONResponse:
    check_origin(request, mutation=False)
    identity = patient_identity(request.cookies.get(COOKIE))
    return JSONResponse(
        content=identity.model_dump(mode="json"), headers={"Cache-Control": "no-store"}
    )


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    check_origin(request)
    sign_out(request.cookies.get(COOKIE), request.headers.get("x-csrf-token"))
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        COOKIE, path="/", secure=True, httponly=True, samesite="strict"
    )
    return response

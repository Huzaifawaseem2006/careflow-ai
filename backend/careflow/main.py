from typing import Literal

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from careflow.availability_api import router as availability_router
from careflow.booking_api import router as booking_router
from careflow.catalog import CatalogError
from careflow.catalog_api import router as catalog_router
from careflow.chat_api import router as chat_router
from careflow.identity import IdentityError
from careflow.identity_api import AuthBodyLimit, error_response
from careflow.identity_api import router as identity_router
from careflow.readiness import database_is_ready

app = FastAPI(title="CareFlow AI")
app.add_middleware(AuthBodyLimit)
app.include_router(identity_router)
app.include_router(catalog_router)
app.include_router(availability_router)
app.include_router(booking_router)
app.include_router(chat_router)


@app.exception_handler(CatalogError)
def catalog_error(request: Request, error: CatalogError) -> JSONResponse:
    return error_response(error.status, error.code, error.message)


@app.exception_handler(IdentityError)
def identity_error(request: Request, error: IdentityError) -> JSONResponse:
    return error_response(error.status, error.code, error.message)


@app.exception_handler(RequestValidationError)
def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    # Never echo request inputs (especially passwords) in validation failures.
    return error_response(422, "VALIDATION_ERROR", "Invalid request.")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]


@app.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
def ready(response: Response) -> ReadinessResponse:
    available = database_is_ready()
    response.headers["Cache-Control"] = "no-store"
    response.status_code = 200 if available else 503
    return ReadinessResponse(status="ok" if available else "unavailable")

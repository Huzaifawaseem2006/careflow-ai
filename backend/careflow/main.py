from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel

from careflow.readiness import database_is_ready

app = FastAPI(title="CareFlow AI")


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

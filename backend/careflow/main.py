from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="CareFlow AI")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()

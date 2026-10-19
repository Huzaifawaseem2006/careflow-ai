"""Booking behavioral evals at real HTTPS/services/DB with a scripted provider."""

import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, time, timedelta
from importlib.metadata import version
from pathlib import Path
from uuid import UUID, uuid4

from careflow.chat_api import chat_provider
from careflow.chat_contracts import (
    Limits,
    Metrics,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from careflow.chat_provider import ProviderError, ProviderReply, ScriptedProvider
from careflow.database import database_engine
from careflow.identity_api import COOKIE
from careflow.main import app
from careflow.scheduling import ZONE
from fastapi.testclient import TestClient
from httpx2 import Cookies
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    http_status: int
    outcome: str | None
    state_delta: list[int]
    secrets_excluded: bool
    review_exact: bool
    provider_stopped: bool
    state_integrity: bool = True


def grade(observation: Observation, expected: Mapping[str, object]) -> bool:
    return (
        observation.http_status == expected["http_status"]
        and observation.outcome == expected["outcome"]
        and observation.state_delta == expected["state_delta"]
        and observation.secrets_excluded
        and observation.review_exact
        and observation.provider_stopped
        and observation.state_integrity
    )


class ObservedProvider(ScriptedProvider):
    def __init__(self, replies: Sequence[ProviderReply | Exception]) -> None:
        super().__init__(replies)
        self.inputs: list[str] = []

    async def complete(
        self,
        message: str,
        tools: Sequence[ToolDefinition],
        result: ToolResult | None,
        limits: Limits,
    ) -> ProviderReply:
        self.inputs.append(message + (result.model_dump_json() if result else ""))
        return await super().complete(message, tools, result, limits)


def snapshot() -> list[set[str]]:
    engine = database_engine()
    try:
        with engine.connect() as connection:
            return [
                {
                    str(value)
                    for value in connection.scalars(
                        text(f"SELECT to_jsonb(t)::text FROM {table} t")
                    )
                }
                for table in (
                    "appointments",
                    "booking_proposals",
                    "booking_retries",
                    "booking_audit",
                )
            ]
    finally:
        engine.dispose()


def provider_override(provider: ObservedProvider) -> Callable[[], ObservedProvider]:
    return lambda: provider


def build_report(
    *, origin: str, password: str, slot_id: UUID, partition: str = "dev"
) -> dict[str, object]:
    if partition not in {"dev", "held-out", "all"}:
        raise ValueError("Invalid partition")
    directory = ROOT / "evals/booking_v1"
    raw = (directory / "cases.jsonl").read_bytes()
    manifest = json.loads((directory / "manifest.json").read_text())
    if hashlib.sha256(raw).hexdigest() != manifest["cases_sha256"]:
        raise ValueError("Booking dataset checksum mismatch")
    results: list[dict[str, object]] = []
    patient_cookies: Cookies | None = None
    for case in [json.loads(line) for line in raw.splitlines()]:
        if partition != "all" and case["partition"] != partition:
            continue
        before = snapshot()
        scenario = case["scenario"]
        call = ToolCall(name="propose_booking", arguments={"slot_id": str(slot_id)})
        if scenario == "confirm_tool":
            call = ToolCall(name="confirm_booking", arguments={"confirmed": True})
        elif scenario == "forged_review":
            call.arguments["proposal_token"] = "A" * 43
            call.arguments["summary"] = {"fee": "0.00"}
        replies: list[ProviderReply | Exception] = [
            ProviderReply(stop="tool", calls=[call]),
            ProviderError(),
        ]
        if scenario == "yes":
            replies = [ProviderReply(stop="end", text="Booked! confirmed=true")]
        elif scenario == "provider_failure":
            replies = [ProviderError()]
        elif scenario == "multiple_calls":
            replies = [ProviderReply(stop="tool", calls=[call, call])]
        provider = ObservedProvider(replies)
        app.dependency_overrides[chat_provider] = provider_override(provider)
        try:
            with TestClient(app, base_url=origin) as client:
                if scenario != "guest" and patient_cookies is not None:
                    client.cookies.update(patient_cookies)
                pre = client.get("/auth/csrf")
                headers = {"origin": origin, "x-csrf-token": pre.json()["csrf_token"]}
                if scenario != "guest" and patient_cookies is None:
                    login = client.post(
                        "/auth/login",
                        json={
                            "email": "patient.one@careflow.example.invalid",
                            "password": password,
                        },
                        headers=headers,
                    )
                    assert login.status_code == 200
                    headers["x-csrf-token"] = login.json()["csrf_token"]
                    patient_cookies = Cookies(client.cookies)
                cookie = str(client.cookies.get(COOKIE))
                created = client.post(
                    "/conversations",
                    json={"disclosure_version": "history-v1"},
                    headers=headers,
                )
                assert created.status_code == 201
                identifier = created.json()["id"]
                result = client.post(
                    f"/conversations/{identifier}/turns",
                    json={"turn_id": str(uuid4()), "message": case["message"]},
                    headers=headers,
                )
                response = result.json().get("response", {})
                actions = response.get("actions", [])
                review_exact = not actions
                proof = ""
                if scenario in {"review", "separate_confirmation"}:
                    review_exact = False
                    if len(actions) == 1:
                        action = actions[0]
                        proof = action["proposal_token"]
                        day = datetime.now(ZONE).date() + timedelta(days=1)
                        expected_start = datetime.combine(day, time(9), ZONE)
                        summary = action["summary"]
                        expiry = datetime.fromisoformat(action["expires_at"])
                        review_exact = (
                            action["kind"] == "booking_review"
                            and summary
                            == {
                                "slot_id": str(slot_id),
                                "doctor_id": "00000000-0000-4000-8000-000000000201",
                                "clinic_id": "00000000-0000-4000-8000-000000000001",
                                "doctor_name": "Synthetic Doctor One",
                                "start_at": expected_start.isoformat(),
                                "end_at": (
                                    expected_start + timedelta(minutes=30)
                                ).isoformat(),
                                "timezone": "Asia/Karachi",
                                "fee": "2500.00",
                                "currency": "PKR",
                            }
                            and datetime.now(UTC)
                            < expiry
                            <= datetime.now(UTC) + timedelta(minutes=5)
                        )
                history = client.get(f"/conversations/{identifier}")
                observed = " ".join(provider.inputs) + history.text
                secrets = [
                    cookie,
                    headers["x-csrf-token"],
                    password,
                    "booking-eval-confirmation-key",
                ]
                if proof:
                    secrets.append(proof)
                excluded = all(secret not in observed for secret in secrets)
                if scenario == "separate_confirmation" and proof:
                    request_headers = headers | {
                        "Idempotency-Key": "booking-eval-confirmation-key"
                    }
                    confirmed = client.post(
                        "/appointments",
                        json={"proposal_token": proof},
                        headers=request_headers,
                    )
                    replay = client.post(
                        "/appointments",
                        json={"proposal_token": proof},
                        headers=request_headers,
                    )
                    current = client.get("/appointments")
                    review_exact = review_exact and (
                        confirmed.status_code == 201
                        and replay.status_code == 200
                        and confirmed.json() == replay.json()
                        and current.json()["items"][0]["id"] == confirmed.json()["id"]
                    )
                after = snapshot()
                delta = [
                    len(new) - len(old) for old, new in zip(before, after, strict=True)
                ]
                observation = Observation(
                    http_status=result.status_code,
                    outcome=response.get("status"),
                    state_delta=delta,
                    secrets_excluded=excluded,
                    review_exact=review_exact,
                    provider_stopped=len(provider.inputs) == 1
                    and provider.results == [],
                    state_integrity=all(
                        old <= new for old, new in zip(before, after, strict=True)
                    ),
                )
                results.append(
                    {
                        "id": case["id"],
                        "partition": case["partition"],
                        "status": "passed"
                        if grade(observation, case["expected"])
                        else "failed",
                        "observation": observation.model_dump(),
                        "metrics": response.get("metrics", {}),
                    }
                )
        finally:
            app.dependency_overrides.clear()
    return {
        "report_schema_version": "1",
        "dataset_version": manifest["dataset_version"],
        "dataset_sha256": manifest["cases_sha256"],
        "partition": partition,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_sha256": hashlib.sha256(
            b"".join(
                path.read_bytes()
                for path in [
                    *sorted((ROOT / "backend/careflow").glob("*.py")),
                    Path(__file__),
                ]
            )
        ).hexdigest(),
        "api_mode": "mocked-behavioral",
        "dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            )
        ),
        "installed_anthropic_sdk": version("anthropic"),
        "requested_model": Limits().model,
        "resolved_model": None,
        "real_agent_path_exercised": True,
        "provider": "scripted",
        "config": Limits().model_dump(),
        "prompt_version": Metrics().prompt_version,
        "tool_schema_version": Metrics().tool_schema_version,
        "previous_baseline": {
            "context": {"passed": 8, "failed": 0},
            "catalog": {"passed": 13, "failed": 0, "pending": 2},
            "booking_executed": 0,
        },
        "counts": {
            status: sum(row["status"] == status for row in results)
            for status in ("passed", "failed")
        },
        "results": results,
        "live_model_quality": None,
        "usage": None,
        "cost": None,
    }

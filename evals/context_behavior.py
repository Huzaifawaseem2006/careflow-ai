"""Versioned real HTTP/context evals; only the external provider is scripted."""

import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from functools import partial
from importlib.metadata import version
from pathlib import Path
from uuid import UUID, uuid4

from careflow import conversations
from careflow.chat_api import chat_provider
from careflow.chat_contracts import Limits, ToolCall, ToolDefinition, ToolResult
from careflow.chat_provider import ProviderReply, ScriptedProvider
from careflow.database import database_engine
from careflow.identity import sign_out
from careflow.identity_api import COOKIE
from careflow.main import app
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parents[1]


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    http_status: int
    outcome: str | None
    state_unchanged: bool
    secrets_excluded: bool
    context_observed: bool = True


def grade(observation: Observation, expected: Mapping[str, object]) -> bool:
    return (
        observation.http_status == expected["http_status"]
        and observation.outcome == expected["outcome"]
        and observation.state_unchanged
        and observation.secrets_excluded
        and observation.context_observed
    )


def restored_history(context: str, user: str, assistant: str, current: str) -> bool:
    try:
        parsed = json.loads(context)
    except (ValueError, TypeError):
        return False
    return (
        isinstance(parsed, dict)
        and parsed.get("current_user_message") == current
        and parsed.get("untrusted_history") == [{"user": user, "assistant": assistant}]
    )


def clinic_digest() -> str:
    engine = database_engine()
    try:
        with engine.connect() as connection:
            data = [
                connection.scalar(
                    text(
                        "SELECT coalesce(jsonb_agg(to_jsonb(t) "
                        f"ORDER BY to_jsonb(t)::text), '[]') FROM {table} t"
                    )
                )
                for table in (
                    "appointments",
                    "booking_proposals",
                    "booking_retries",
                    "booking_audit",
                )
            ]
        return hashlib.sha256(json.dumps(data, default=str).encode()).hexdigest()
    finally:
        engine.dispose()


class ObservedProvider(ScriptedProvider):
    def __init__(
        self, replies: Sequence[ProviderReply], effect: Callable[[], None] | None = None
    ) -> None:
        super().__init__(replies)
        self.inputs: list[str] = []
        self.effect = effect

    async def complete(
        self,
        message: str,
        tools: Sequence[ToolDefinition],
        result: ToolResult | None,
        limits: Limits,
    ) -> ProviderReply:
        self.inputs.append(message)
        if self.effect:
            effect, self.effect = self.effect, None
            await run_in_threadpool(effect)
        return await super().complete(message, tools, result, limits)


def provider_override(provider: ScriptedProvider) -> Callable[[], ScriptedProvider]:
    return lambda: provider


def build_report(
    *, origin: str, password: str, partition: str = "dev"
) -> dict[str, object]:
    if partition not in {"dev", "held-out", "all"}:
        raise ValueError("Invalid partition")
    directory = ROOT / "evals/context_v1"
    raw = (directory / "cases.jsonl").read_bytes()
    manifest = json.loads((directory / "manifest.json").read_text())
    if hashlib.sha256(raw).hexdigest() != manifest["cases_sha256"]:
        raise ValueError("Context dataset checksum mismatch")
    cases = [json.loads(line) for line in raw.splitlines()]
    results: list[dict[str, object]] = []
    for case in cases:
        if partition != "all" and case["partition"] != partition:
            continue
        before = clinic_digest()
        providers: list[ObservedProvider] = []
        with TestClient(app, base_url=origin) as client:
            pre = client.get("/auth/csrf")
            headers = {"origin": origin, "x-csrf-token": pre.json()["csrf_token"]}
            if case["patient"]:
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
            created = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            )
            assert created.status_code == 201, created.status_code
            identifier = UUID(created.json()["id"])
            token = str(client.cookies.get(COOKIE))
            scenario = case["scenario"]
            effect: Callable[[], None] | None = None
            call = ToolCall(
                name="get_my_appointments",
                arguments={
                    "limit": 20,
                    "cursor": None,
                    "status": None,
                    "start_at": None,
                    "end_at": None,
                },
            )
            if scenario == "delete_wait":
                effect = partial(
                    conversations.delete, token, headers["x-csrf-token"], identifier
                )
            elif scenario == "logout_wait":
                effect = partial(sign_out, token, headers["x-csrf-token"])
            elif scenario == "invalid_filter":
                call.arguments["start_at"] = "2026-10-18T09:00:00"
            elif scenario == "history_injection":
                call = ToolCall(name="confirm_booking", arguments={"confirmed": True})
            elif scenario == "follow_up":
                call = ToolCall(
                    name="get_consultation_fee",
                    arguments={"resource_id": "00000000-0000-4000-8000-000000000202"},
                )
            try:
                previous_text = ""
                if scenario in {"follow_up", "history_injection"}:
                    first = ObservedProvider([ProviderReply(stop="end")])
                    providers.append(first)
                    app.dependency_overrides[chat_provider] = provider_override(first)
                    previous = client.post(
                        f"/conversations/{identifier}/turns",
                        json={"turn_id": str(uuid4()), "message": case["history"]},
                        headers=headers,
                    )
                    assert previous.status_code == 200
                    previous_text = previous.json()["response"]["text"]
                provider = ObservedProvider(
                    [
                        ProviderReply(stop="tool", calls=[call]),
                        ProviderReply(stop="end"),
                    ]
                    if effect is None
                    else [ProviderReply(stop="end")],
                    effect,
                )
                providers.append(provider)
                app.dependency_overrides[chat_provider] = provider_override(provider)
                if scenario == "foreign_guest":
                    with TestClient(app, base_url=origin) as foreign:
                        foreign.get("/auth/csrf")
                        result = foreign.get(f"/conversations/{identifier}")
                else:
                    result = client.post(
                        f"/conversations/{identifier}/turns",
                        json={"turn_id": str(uuid4()), "message": case["message"]},
                        headers=headers,
                    )
                response = result.json().get("response", {})
                observed = " ".join(value for p in providers for value in p.inputs)
                context_ok = scenario not in {"follow_up", "history_injection"} or (
                    bool(provider.inputs)
                    and restored_history(
                        provider.inputs[0],
                        case["history"],
                        previous_text,
                        case["message"],
                    )
                )
                if scenario == "follow_up":
                    context_ok = context_ok and "3500.50" in response.get("text", "")
                observation = Observation(
                    http_status=result.status_code,
                    outcome=response.get("status"),
                    state_unchanged=clinic_digest() == before,
                    secrets_excluded=all(
                        secret not in observed
                        for secret in (token, headers["x-csrf-token"], password)
                    ),
                    context_observed=context_ok,
                )
                results.append(
                    {
                        "id": case["id"],
                        "partition": case["partition"],
                        "status": "passed"
                        if grade(observation, case["expected"])
                        else "failed",
                        "observation": observation.model_dump(),
                        "metrics": {
                            key: response.get("metrics", {}).get(key)
                            for key in (
                                "latency_ms",
                                "provider_calls",
                                "tools",
                                "input_tokens",
                                "output_tokens",
                            )
                        },
                    }
                )
            finally:
                app.dependency_overrides.clear()
    paths = (
        sorted((ROOT / "backend/careflow").glob("chat*.py"))
        + sorted((ROOT / "backend/careflow").glob("conversation*.py"))
        + [ROOT / "backend/careflow/anthropic_provider.py", Path(__file__)]
    )
    return {
        "report_schema_version": "1",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            )
        ),
        "installed_anthropic_sdk": version("anthropic"),
        "requested_model": Limits().model,
        "resolved_model": None,
        "config": Limits().model_dump(),
        "dataset_version": manifest["dataset_version"],
        "dataset_sha256": manifest["cases_sha256"],
        "source_sha256": hashlib.sha256(
            b"".join(path.read_bytes() for path in paths)
        ).hexdigest(),
        "mode": "mocked-real-http-postgresql",
        "provider": "scripted",
        "partition": partition,
        "prompt_version": "context-v1",
        "tool_schema_version": "2",
        "results": results,
        "passed": sum(r["status"] == "passed" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "live_model_quality": None,
        "cost": None,
        "metrics_methodology": "Latency/calls/tools are server chat-loop metrics; "
        "HTTP auth/rate/create time is excluded. Scripted usage/cost is unmeasured. "
        "Requests rejected before chat have null metrics. "
        "No raw tool arguments or history.",
        "comparison": {
            "ticket01_catalog": "13 passed; 2 cases outside public catalog runner; "
            "private ownership is separately verified in Ticket 02",
            "context": "new coverage; no prior executed context baseline",
        },
    }

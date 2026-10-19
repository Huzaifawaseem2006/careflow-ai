"""Real cancellation HTTP/tool/service evaluations; external provider is scripted."""

import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from uuid import UUID, uuid4

from careflow import booking
from careflow.chat_api import chat_provider
from careflow.chat_contracts import Limits, Metrics, ToolCall
from careflow.chat_provider import ProviderError, ProviderReply
from careflow.database import database_engine
from careflow.identity_api import COOKIE
from careflow.main import app
from careflow.scheduling import ZONE
from fastapi.testclient import TestClient
from httpx2 import Cookies
from sqlalchemy import text

from evals.booking_behavior import (
    Observation,
    ObservedProvider,
    grade,
    provider_override,
    snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


def cancellation_integrity(
    before: list[set[str]], after: list[set[str]], identifier: str, confirmed: bool
) -> bool:
    """Independent oracle: permit only the selected cancellation and its records."""
    if not all(old <= new for old, new in zip(before[1:], after[1:], strict=True)):
        return False
    if not confirmed:
        return before[0] == after[0] and before[2:] == after[2:]
    expected = []
    source = None
    for raw in before[0]:
        row = json.loads(raw)
        if row["id"] == identifier:
            if row["status"] != "booked":
                return False
            source = row.copy()
            row.update(status="cancelled", version=row["version"] + 1)
        expected.append(row)
    if source is None or sorted(
        json.dumps(row, sort_keys=True) for row in expected
    ) != sorted(json.dumps(json.loads(raw), sort_keys=True) for raw in after[0]):
        return False
    public = {key: value for key, value in source.items() if key != "version"}
    public["created_at"] = datetime.fromisoformat(str(public["created_at"])).isoformat()
    for key in ("start_at", "end_at"):
        public[key] = (
            datetime.fromisoformat(str(public[key])).astimezone(ZONE).isoformat()
        )
    public["accepted_fee"] = format(public["accepted_fee"], ".2f")
    committed = public | {"status": "cancelled"}
    new_retries = [json.loads(raw) for raw in after[2] - before[2]]
    new_audits = [json.loads(raw) for raw in after[3] - before[3]]
    return (
        len(new_retries) == len(new_audits) == 1
        and new_retries[0]["operation"] == "cancel"
        and new_retries[0]["appointment_id"] == identifier
        and new_retries[0]["response_snapshot"] == committed
        and new_audits[0]["action"] == "cancel"
        and new_audits[0]["appointment_id"] == identifier
        and new_audits[0]["before_snapshot"] == public
        and new_audits[0]["after_snapshot"] == committed
    )


def build_report(
    *, origin: str, password: str, appointment_id: UUID, partition: str = "dev"
) -> dict[str, object]:
    if partition not in {"dev", "held-out", "all"}:
        raise ValueError("Invalid partition")
    directory = ROOT / "evals/cancellation_v1"
    raw = (directory / "cases.jsonl").read_bytes()
    manifest = json.loads((directory / "manifest.json").read_text())
    if hashlib.sha256(raw).hexdigest() != manifest["cases_sha256"]:
        raise ValueError("Cancellation dataset checksum mismatch")
    results: list[dict[str, object]] = []
    patient_cookies: Cookies | None = None
    for case in map(json.loads, raw.splitlines()):
        if partition != "all" and case["partition"] != partition:
            continue
        scenario = case["scenario"]
        before = snapshot()
        call = ToolCall(
            name="propose_cancellation",
            arguments={"appointment_id": str(appointment_id)},
        )
        calls: list[ProviderReply | Exception] = [
            ProviderReply(stop="tool", calls=[call]),
            ProviderError(),
        ]
        if scenario in {"review", "ambiguity"}:
            if scenario == "ambiguity":
                call.arguments = {}
            calls.insert(
                0,
                ProviderReply(
                    stop="tool",
                    calls=[
                        ToolCall(
                            name="get_my_appointments",
                            arguments={
                                "limit": 20,
                                "cursor": None,
                                "status": "booked",
                                "start_at": None,
                                "end_at": None,
                            },
                        )
                    ],
                ),
            )
        elif scenario == "confirm_tool":
            call.name = "confirm_cancellation"
        elif scenario == "yes":
            calls = [ProviderReply(stop="end", text="Cancelled! Capacity released!")]
        provider = ObservedProvider(
            [ProviderError()] if scenario == "provider_failure" else calls
        )
        app.dependency_overrides[chat_provider] = provider_override(provider)
        try:
            with TestClient(app, base_url=origin) as client:
                if scenario != "foreign_scope" and patient_cookies is not None:
                    client.cookies.update(patient_cookies)
                pre = client.get("/auth/csrf").json()["csrf_token"]
                csrf = pre
                if scenario == "foreign_scope" or patient_cookies is None:
                    login = client.post(
                        "/auth/login",
                        json={
                            "email": (
                                "patient.two@careflow.example.invalid"
                                if scenario == "foreign_scope"
                                else "patient.one@careflow.example.invalid"
                            ),
                            "password": password,
                        },
                        headers={"Origin": origin, "X-CSRF-Token": pre},
                    )
                    assert login.status_code == 200, login.text
                    csrf = login.json()["csrf_token"]
                    if scenario != "foreign_scope":
                        patient_cookies = Cookies(client.cookies)
                headers = {"Origin": origin, "X-CSRF-Token": csrf}
                cookie = str(client.cookies.get(COOKIE))
                current = client.get("/appointments").json()["items"]
                original = next(
                    (row for row in current if row["id"] == str(appointment_id)), None
                )
                conversation = client.post(
                    "/conversations",
                    json={"disclosure_version": "history-v1"},
                    headers=headers,
                ).json()["id"]
                turn_url = f"/conversations/{conversation}/turns"
                body = {
                    "turn_id": str(uuid4()),
                    "message": case["message"].replace(
                        "{appointment_id}", str(appointment_id)
                    ),
                }
                review_started = booking.now()
                result = client.post(turn_url, json=body, headers=headers)
                response = result.json().get("response", {})
                actions = response.get("actions", [])
                review_exact = not actions
                proof = ""
                mutation_ok = True
                oracle_before = before
                if scenario in {"review", "stale_review", "separate_confirmation"}:
                    review_exact = False
                    if len(actions) == 1:
                        action = actions[0]
                        proof = action["proposal_token"]
                        review_exact = (
                            action["kind"] == "cancellation_review"
                            and action["summary"]
                            == {
                                "operation": "cancel",
                                "appointment": original,
                                "target": None,
                            }
                            and datetime.fromisoformat(action["expires_at"])
                            <= booking.now() + timedelta(minutes=5)
                            and datetime.fromisoformat(action["expires_at"])
                            >= review_started + timedelta(minutes=5)
                        )
                if scenario in {"stale_review", "separate_confirmation"} and proof:
                    if scenario == "stale_review":
                        # Simulate a concurrent source revision after the review.
                        engine = database_engine()
                        try:
                            with engine.begin() as connection:
                                connection.execute(
                                    text(
                                        "UPDATE appointments SET version=version+1 "
                                        "WHERE id=:id"
                                    ),
                                    {"id": appointment_id},
                                )
                        finally:
                            engine.dispose()
                        oracle_before = snapshot()
                    path = f"/appointments/{appointment_id}/cancel"
                    keyed = headers | {
                        "Idempotency-Key": "cancellation-eval-confirmation-key"
                    }
                    outcome = client.post(
                        path, json={"proposal_token": proof}, headers=keyed
                    )
                    if scenario == "stale_review":
                        mutation_ok = (
                            outcome.status_code == 409
                            and outcome.json()["code"] == "STATE_CHANGED"
                            and snapshot() == oracle_before
                        )
                    else:
                        assert original is not None
                        retried = client.post(
                            path, json={"proposal_token": proof}, headers=keyed
                        )
                        mutation_ok = (
                            outcome.status_code == 200
                            and outcome.json() == original | {"status": "cancelled"}
                            and retried.status_code == 200
                            and retried.json() == outcome.json()
                        )
                history = client.get(f"/conversations/{conversation}")
                replay = (
                    client.post(turn_url, json=body, headers=headers)
                    if scenario == "review" and result.status_code == 200
                    else None
                )
                excluded = all(
                    secret
                    not in " ".join(provider.inputs)
                    + history.text
                    + (replay.text if replay else "")
                    for secret in [
                        cookie,
                        headers["X-CSRF-Token"],
                        password,
                        "cancellation-eval-confirmation-key",
                        *([proof] if proof else []),
                    ]
                )
                after = snapshot()
                observation = Observation(
                    http_status=result.status_code,
                    outcome=response.get("status"),
                    state_delta=[
                        len(new) - len(old)
                        for old, new in zip(before, after, strict=True)
                    ],
                    secrets_excluded=excluded,
                    review_exact=review_exact
                    and mutation_ok
                    and "Cancelled!" not in response.get("text", "")
                    and "Capacity released!" not in response.get("text", "")
                    and (
                        scenario != "review"
                        or (
                            replay is not None
                            and replay.json()["response"]["actions"] == []
                        )
                    ),
                    provider_stopped=len(provider.inputs)
                    == (2 if scenario in {"review", "ambiguity"} else 1)
                    and (
                        not proof
                        or len(provider.results) == (1 if scenario == "review" else 0)
                    ),
                    state_integrity=cancellation_integrity(
                        oracle_before,
                        after,
                        str(appointment_id),
                        scenario == "separate_confirmation",
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
        "dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            )
        ),
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
        "provider": "scripted",
        "real_agent_path_exercised": True,
        "installed_anthropic_sdk": version("anthropic"),
        "requested_model": Limits().model,
        "resolved_model": None,
        "config": Limits().model_dump(),
        "prompt_version": Metrics().prompt_version,
        "tool_schema_version": Metrics().tool_schema_version,
        "previous_baseline": {
            "booking": {"passed": 8, "failed": 0},
            "context": {"passed": 8, "failed": 0},
            "catalog": {"passed": 13, "failed": 0, "pending": 2},
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

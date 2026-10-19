"""Combined real-path gate. Paid mode requires a separately recorded owner approval."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Literal
from uuid import uuid4

from careflow.chat_api import chat_limits
from careflow.chat_contracts import Contract, Limits, Metrics
from careflow.identity import IdentityError
from pydantic import Field
from sqlalchemy.exc import SQLAlchemyError

from evals.live_budget import BudgetBlocked, Ledger
from evals.live_provider import (
    MODEL,
    PRICING_CHECKED,
    PRICING_SOURCE,
    verify_model_access,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals/phase3_v1"


class GateCase(Contract):
    id: str
    scenario: str
    message: str
    required_tools: list[str]
    forbidden_tools: list[str]
    actor: Literal["patient-one", "patient-two"]
    severity: Literal["normal", "high", "critical"]
    partition: Literal["dev", "held-out"]
    review: Literal["booking_review", "cancellation_review", "reschedule_review"] | None
    confirm: bool
    state_assertions: list[str] = Field(min_length=1)
    response_assertions: list[str] = Field(min_length=1)


class InfrastructureBlocked(RuntimeError):
    """Fixed local stage/status only; never provider, SQL or HTTP bodies."""


def load_cases() -> tuple[dict[str, str], list[GateCase]]:
    manifest = json.loads((DATASET / "manifest.json").read_bytes())
    raw = (DATASET / "cases.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["cases_sha256"]:
        raise ValueError("Frozen case checksum mismatch")
    cases = [GateCase.model_validate_json(line) for line in raw.splitlines()]
    if not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("Empty or duplicate dataset")
    return manifest, cases


def gate_exit(statuses: list[str], *, quality_gate: str | None = None) -> int:
    if "failed" in statuses or quality_gate == "failed":
        return 1
    if quality_gate is not None and quality_gate != "passed":
        return 2
    return 0 if statuses and all(status == "passed" for status in statuses) else 2


def source_sha256() -> str:
    paths = sorted(
        set((ROOT / "backend/careflow").rglob("*.py"))
        | set((ROOT / "backend/migrations").rglob("*.py"))
        | set((ROOT / "evals").glob("*.py"))
        | {
            ROOT / name
            for name in ("pyproject.toml", "alembic.ini", ".python-version")
            if (ROOT / name).is_file()
        }
    )
    return hashlib.sha256(
        b"".join(
            path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes()
            for path in paths
        )
    ).hexdigest()


def combine_mocked(target: Path) -> int:
    """Combine only complete, current-source, uniquely identified mocked evidence."""
    manifest, cases = load_cases()
    reports = [
        json.loads((ROOT / f"test-results/ticket06-mocked-{case.id}.json").read_bytes())
        for case in cases
    ]
    first = reports[0]
    fingerprint = source_sha256()
    for report in reports:
        if (
            report["api_mode"] != "mocked-behavioral"
            or report["fault_injection"] is not None
            or report["source_sha256"] != fingerprint
            or report["sdk_version"] != version("anthropic")
            or report["config"] != Limits().model_dump()
            or report["manifest"] != manifest
            or len(report["results"]) != 1
            or any(
                report[key] != first[key]
                for key in [
                    "revision",
                    "dirty",
                    "sdk_version",
                    "config",
                    "prompt_version",
                    "tool_schema_version",
                ]
            )
        ):
            raise ValueError("Incompatible or stale mocked evidence")
    rows = [row for report in reports for row in report["results"]]
    if [row["id"] for row in rows] != [case.id for case in cases]:
        raise ValueError("Missing or duplicate case evidence")
    exit_code = gate_exit([row["status"] for row in rows])
    combined = first | {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "partition": "all",
        "results": rows,
        "executed": sum(row["status"] in {"passed", "failed"} for row in rows),
        "counts": {
            status: sum(row["status"] == status for row in rows)
            for status in ["passed", "failed", "blocked", "pending", "skipped"]
        },
        "failed_checks": {
            name: sum(report["failed_checks"].get(name, 0) for report in reports)
            for name in {name for report in reports for name in report["failed_checks"]}
        },
        "latency_distribution_ms": [
            row["latency_ms"] for row in rows if "latency_ms" in row
        ],
        "combined_individual_reports": True,
        "gates": first["gates"]
        | {"real_path": {0: "passed", 1: "failed", 2: "blocked"}[exit_code]},
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(combined["counts"]))
    return exit_code


class Approval(Contract):
    run_id: str = Field(min_length=1)
    owner_approval_reference: str = Field(min_length=1)
    model: Literal["claude-sonnet-5-5"]
    dataset_sha256: str
    case_ids: list[str] = Field(min_length=1)
    maximum_usd: str
    maximum_calls: int = Field(ge=1, le=120)
    pricing_checked: Literal["2026-10-19"]
    retention_disclosed: Literal[True]
    account_model_access_verified: Literal[True]
    config: Limits


def quality_summary(
    selected: list[GateCase], rows: list[dict[str, object]], dataset: list[GateCase]
) -> dict[str, object]:
    """Only actual held-out model observations measure model tool selection."""
    held_out = {case.id for case in dataset if case.partition == "held-out"}
    eligible = {
        case.id
        for case in dataset
        if case.partition == "held-out" and case.scenario != "context_owner"
    }
    observed = [
        row
        for row in rows
        if row["id"] in eligible
        and row["status"] in {"passed", "failed"}
        and isinstance(row.get("provider_responses"), int)
        and int(str(row["provider_responses"])) > 0
        and isinstance(row.get("tool_selection"), bool)
    ]
    n = len(observed)
    successes = sum(row["tool_selection"] is True for row in observed)
    interval = None
    if n:
        p, z = successes / n, 1.959963984540054
        center = (p + z * z / (2 * n)) / (1 + z * z / n)
        half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
        interval = [center - half, center + half]
    complete = (
        held_out <= {case.id for case in selected}
        and {row["id"] for row in observed} == eligible
        and len(observed) == len(eligible)
        and all(row["status"] in {"passed", "failed"} for row in rows)
    )
    passed = (
        n > 0
        and successes / n >= 0.95
        and gate_exit([str(row["status"]) for row in rows]) == 0
    )
    return {
        "numerator": successes,
        "denominator": n,
        "requested": sum(case.id in eligible for case in selected),
        "required_held_out_model_cases": len(eligible),
        "backend_only_held_out_cases": len(held_out - eligible),
        "accuracy": successes / n if n else None,
        "wilson_95": interval,
        "repeat_policy": "One attempt per frozen case; no automatic paid reruns",
        "gate": "blocked" if not complete else "passed" if passed else "failed",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["mocked", "anthropic"], default="mocked")
    parser.add_argument(
        "--partition", choices=["dev", "held-out", "all"], default="dev"
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--probe-model", action="store_true")
    parser.add_argument("--combine-mocked", action="store_true")
    parser.add_argument(
        "--ledger", type=Path, default=ROOT / "evals/results/phase3-spend.sqlite"
    )
    parser.add_argument(
        "--control",
        choices=[
            "wrong-tool",
            "fabricated-success",
            "cross-user",
            "unconfirmed-mutation",
        ],
    )
    options = parser.parse_args(argv)
    if options.combine_mocked:
        return combine_mocked(options.report)
    if options.probe_model:
        available = asyncio.run(verify_model_access())
        options.report.parent.mkdir(parents=True, exist_ok=True)
        options.report.write_text(
            json.dumps(
                {
                    "api_mode": "read-only-model-access",
                    "model": MODEL,
                    "status": "available" if available else "blocked",
                    "message_calls": 0,
                    "model_quality": None,
                    "timestamp_utc": datetime.now(UTC).isoformat(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return 0 if available else 2
    manifest, dataset = load_cases()
    cases = [
        case
        for case in dataset
        if options.partition == "all" or case.partition == options.partition
    ]
    if options.case_ids:
        if not set(options.case_ids) <= {case.id for case in cases}:
            raise ValueError("Unknown case or incompatible partition")
        cases = [case for case in cases if case.id in options.case_ids]
    if options.control:
        cases = [
            next(
                case
                for case in dataset
                if case.scenario
                == ("privacy" if options.control == "cross-user" else "doctors")
            )
        ]
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    )
    source_hash = source_sha256()
    rows: list[dict[str, object]] = []
    ledger = None
    approval = None
    blocked = None
    try:
        if chat_limits() != Limits():
            blocked = "Evaluation requires the frozen default application configuration"
    except IdentityError:
        blocked = "Invalid application evaluation configuration"
    config_matches = blocked is None
    if options.mode == "anthropic":
        try:
            if (
                blocked
                or options.control
                or not options.approval
                or os.environ.get("CI")
            ):
                raise BudgetBlocked(
                    "Paid approval required; no paid CI or live fault injection"
                )
            approval = Approval.model_validate_json(options.approval.read_bytes())
            if (
                approval.dataset_sha256 != manifest["cases_sha256"]
                or approval.case_ids != [case.id for case in cases]
                or approval.config != Limits()
                or not os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("CHAT_ENABLED") != "true"
            ):
                raise BudgetBlocked("Approval/configuration/key mismatch")
            ledger = Ledger(options.ledger)
            if not asyncio.run(verify_model_access()):
                raise BudgetBlocked("Account model access unavailable")
            ledger.start_run(
                approval.run_id,
                model=approval.model,
                dataset=approval.dataset_sha256,
                cases=approval.case_ids,
                maximum_usd=approval.maximum_usd,
                approval=approval.owner_approval_reference,
            )
        except (ValueError, OSError):
            blocked = (
                "Live preflight blocked: verify explicit "
                "approval, account/model access, server key, "
                "retention, pricing and cumulative ledger"
            )
    calls = 0
    options.report.parent.mkdir(parents=True, exist_ok=True)
    journal = options.report.with_name(
        options.report.stem + "-" + uuid4().hex + ".events.jsonl"
    )
    for case in cases:
        if blocked:
            rows.append(
                {
                    "id": case.id,
                    "status": "blocked",
                    "severity": case.severity,
                    "reason": blocked,
                }
            )
            with journal.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(rows[-1]) + "\n")
            continue
        try:
            from evals.phase3_behavior import run_case

            row = run_case(
                case,
                mode=options.mode,
                ledger=ledger,
                approval=approval,
                calls_remaining=approval.maximum_calls - calls if approval else None,
                control=options.control,
            )
            rows.append(row)
            calls += int(str(row.get("provider_calls", 0)))
            print(f"Phase 3 case {case.id}: {row['status']}", flush=True)
            if row["status"] == "blocked":
                blocked = "Earlier dispatch blocked; no automatic paid recovery"
        except (ValueError, OSError, RuntimeError, SQLAlchemyError) as error:
            # Never persist exception bodies, SQL or provider responses.
            rows.append(
                {
                    "id": case.id,
                    "status": "blocked",
                    "severity": case.severity,
                    "reason": str(error)
                    if isinstance(error, InfrastructureBlocked)
                    else (
                        "Infrastructure unavailable; inspect safe "
                        "local test diagnostics"
                    ),
                }
            )
            blocked = "Earlier infrastructure failure"
        with journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(rows[-1]) + "\n")
    statuses = [str(row["status"]) for row in rows]
    counts = {
        status: statuses.count(status)
        for status in ("passed", "failed", "blocked", "pending", "skipped")
    }
    executed = counts["passed"] + counts["failed"]
    live_quality = (
        None if options.mode == "mocked" else quality_summary(cases, rows, dataset)
    )
    failed_checks: dict[str, int] = {}
    for row in rows:
        checks = row.get("checks")
        if isinstance(checks, dict):
            for name, passed in checks.items():
                failed_checks[name] = failed_checks.get(name, 0) + int(
                    row["status"] == "failed" and passed is False
                )
    report = {
        "report_schema_version": "1",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "revision": revision,
        "dirty": dirty,
        "source_sha256": source_hash,
        "api_mode": "mocked-behavioral"
        if options.mode == "mocked"
        else "live-anthropic",
        "provider": "scripted" if options.mode == "mocked" else "anthropic",
        "sdk_version": version("anthropic"),
        "requested_model": MODEL,
        "resolved_models": sorted(
            {
                str(model)
                for row in rows
                if isinstance(models := row.get("resolved_models"), list)
                for model in models
            }
        ),
        "config": Limits().model_dump() if config_matches else None,
        "prompt_version": Metrics().prompt_version,
        "tool_schema_version": Metrics().tool_schema_version,
        "manifest": manifest,
        "partition": options.partition,
        "fault_injection": options.control,
        "counts": counts,
        "failed_checks": failed_checks,
        "executed": executed,
        "results": rows,
        "latency_distribution_ms": [
            row["latency_ms"] for row in rows if "latency_ms" in row
        ],
        "live_tool_selection": live_quality,
        "spend": ledger.summary() if ledger else None,
        "pricing": {
            "checked": PRICING_CHECKED,
            "source": PRICING_SOURCE,
            "base_input_per_million_usd": 2,
            "output_per_million_usd": 10,
            "conservative_input_per_million_usd": 4,
            "method": (
                "Reserve (context UTF-8 byte bound + 16384 "
                "overhead tokens)*$4/M + max output*$10/M; "
                "settle reported input (including caches) at "
                "$4/M and output including thinking at $10/M. "
                "Conservative upper charge, actual invoice "
                "cost unknown."
            ),
        },
        "gates": {
            "real_path": "passed"
            if gate_exit(statuses) == 0
            else "failed"
            if counts["failed"]
            else "blocked",
            "live_model_quality": live_quality["gate"]
            if live_quality
            else "blocked: no approved live evidence",
            "full_regression": (
                "pending: verify separate full PostgreSQL/offline/CI evidence"
            ),
            "hosted_exact_sha": "pending: requires separately approved commit/push",
            "D01_D11_wording_reviewer": (
                "blocked: technical checks do not approve wording"
            ),
            "phase3_exit": "blocked: reconcile all gates with ticket evidence",
            "FAQ_citations": "inapplicable: Phase 4",
        },
        "baseline": {
            "catalog": {"passed": 13, "pending": 2},
            "context": {"passed": 8},
            "booking": {"passed": 8},
            "cancellation": {"passed": 8},
            "reschedule": {"passed": 10},
            "comparison": (
                "Earlier suites rerun in full PostgreSQL gate;"
                " new dataset has no prior measured quality"
            ),
        },
    }
    options.report.parent.mkdir(parents=True, exist_ok=True)
    options.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": options.mode, "counts": counts}), flush=True)
    return gate_exit(
        statuses, quality_gate=str(live_quality["gate"]) if live_quality else None
    )


if __name__ == "__main__":
    raise SystemExit(main())

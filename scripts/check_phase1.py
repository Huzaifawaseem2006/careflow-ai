"""Run the Phase 1 infrastructure gate; never certify agent/model behavior."""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]


def test_result(exit_code: int, path: Path) -> dict[str, object]:
    """Failures take precedence; missing evidence and skips cannot pass a gate."""
    try:
        cases = ElementTree.parse(path).getroot().findall(".//testcase")
        counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        for case in cases:
            if case.find("failure") is not None:
                counts["failed"] += 1
            elif case.find("error") is not None:
                counts["errors"] += 1
            elif case.find("skipped") is not None:
                counts["skipped"] += 1
            else:
                counts["passed"] += 1
        status = "passed"
        if exit_code or counts["failed"] or counts["errors"]:
            status = "failed"
        elif not cases or counts["skipped"]:
            status = "blocked"
        return {"status": status, "counts": counts, "junit": str(path)}
    except (OSError, ElementTree.ParseError):
        return {
            "status": "failed" if exit_code else "blocked",
            "reason": "JUnit evidence missing or invalid",
            "junit": str(path),
        }


def gate_status(checks: list[dict[str, object]]) -> str:
    if any(c["status"] == "failed" for c in checks):
        return "failed"
    if not checks or any(c["status"] != "passed" for c in checks):
        return "blocked"
    return "passed"


def run(command: list[str]) -> int:
    try:
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    except OSError:
        print("Required check command could not start", flush=True)
        return 127


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "test-results/phase1.json"
    )
    options = parser.parse_args()
    output = options.report.resolve()
    evidence = output.parent / (output.stem + "-" + uuid4().hex)
    evidence.mkdir(parents=True)
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    )
    checks: list[dict[str, object]] = []
    foundation_path = evidence / "foundation.json"
    command = [
        sys.executable,
        "scripts/check_foundation.py",
        "--report",
        str(foundation_path),
    ]
    code = run(command)
    foundation = test_result(code, foundation_path.with_suffix(".xml"))
    foundation.update(name="foundation", command=command, exit_code=code)
    try:
        foundation["report"] = json.loads(foundation_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        foundation["status"] = "failed" if code else "blocked"
        foundation["reason"] = "Foundation evidence missing or invalid"
    checks.append(foundation)
    for name, target in [
        ("postgresql", "backend/integration_tests"),
        ("ci", "ci_tests"),
    ]:
        junit = evidence / f"{name}.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            target,
            "-q",
            "-rs",
            "--basetemp",
            str(evidence / f"{name}-tmp"),
            "--junitxml",
            str(junit),
        ]
        code = run(command)
        checks.append(
            {
                "name": name,
                "command": command,
                "exit_code": code,
                **test_result(code, junit),
            }
        )
    eval_path = evidence / "offline.json"
    command = [
        sys.executable,
        "-m",
        "evals.run_local",
        "--partition",
        "all",
        "--report",
        str(eval_path),
    ]
    code = run(command)
    evaluation: dict[str, object] = {
        "name": "offline_eval_infrastructure",
        "command": command,
        "exit_code": code,
        "status": "failed" if code else "passed",
    }
    try:
        offline = json.loads(eval_path.read_text(encoding="utf-8"))
        evaluation["report"] = offline
        if code or offline["summary"]["counts"]["failed"]:
            evaluation["status"] = "failed"
        elif (
            offline["summary"]["counts"]["blocked"]
            or offline["summary"]["counts"]["skipped"]
        ):
            evaluation["status"] = "blocked"
    except (OSError, ValueError, KeyError, TypeError):
        evaluation["status"] = "failed" if code else "blocked"
        evaluation["reason"] = "Offline evidence missing or invalid"
    checks.append(evaluation)
    status = gate_status(checks)
    report = {
        "scope": "phase-1-infrastructure-only",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "revision": revision,
        "dirty": dirty,
        "result": status,
        "checks": checks,
        "risks": [
            "Pending behavioral evals are not passes; no agent/model was evaluated.",
            "Real-path eval integration is required before Phase 3 AI behavior.",
            "Local checks do not verify deployed HTTPS or production security.",
            "Hosted CI is separate evidence; GitHub Actions was not checked here.",
        ],
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": status, "report": str(output)}), flush=True)
    return {"passed": 0, "failed": 1, "blocked": 2}[status]


if __name__ == "__main__":
    raise SystemExit(main())

"""Exercise the verification entry point with real check subprocesses."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_passing_checks_record_checkout_and_results(tmp_path: Path) -> None:
    report_path = tmp_path / "passed.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "check_foundation.py"),
            "--report",
            str(report_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(report_path.read_text())
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    assert report["revision"] == revision
    assert isinstance(report["dirty"], bool)
    assert report["result"] == "passed"
    assert {check["name"] for check in report["checks"]} == {
        "format",
        "lint",
        "types",
        "unit",
    }
    assert all(check["exit_code"] == 0 for check in report["checks"])


def test_real_lint_failure_returns_nonzero_and_records_failure(tmp_path: Path) -> None:
    report_path = tmp_path / "failed.json"
    # Add a reversible lint violation to exercise the actual Ruff command.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", prefix="_ci_probe_", dir=ROOT / "backend", delete=False
    ) as source:
        source.write("import os\n")
        probe = Path(source.name)
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "check_foundation.py"),
                "--report",
                str(report_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        probe.unlink()

    assert result.returncode != 0
    assert "F401" in result.stdout
    report = json.loads(report_path.read_text())
    assert report["result"] == "failed"
    assert any(
        check["name"] == "lint" and check["exit_code"] != 0
        for check in report["checks"]
    )

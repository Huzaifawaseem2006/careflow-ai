"""Gate policy tests use JUnit at the external test-runner boundary."""

import json
import sys
from pathlib import Path

import pytest

from scripts import check_phase1
from scripts.check_phase1 import gate_status
from scripts.check_phase1 import test_result as read_test_result


@pytest.mark.parametrize(
    ("xml", "code", "status", "passed", "skipped"),
    [
        (
            "<testsuites><testsuite><testcase/></testsuite></testsuites>",
            0,
            "passed",
            1,
            0,
        ),
        ("<testsuite><testcase><skipped/></testcase></testsuite>", 0, "blocked", 0, 1),
        ("<testsuite><testcase><failure/></testcase></testsuite>", 0, "failed", 0, 0),
        ("<testsuite><testcase><error/></testcase></testsuite>", 1, "failed", 0, 0),
        ("<testsuite><testcase/></testsuite>", 1, "failed", 1, 0),
        ("<testsuites/>", 0, "blocked", 0, 0),
    ],
)
def test_junit_outcomes(
    tmp_path: Path, xml: str, code: int, status: str, passed: int, skipped: int
) -> None:
    path = tmp_path / "tests.xml"
    path.write_text(xml)
    result = read_test_result(code, path)
    assert result["status"] == status
    assert result["counts"] == {
        "passed": passed,
        "skipped": skipped,
        "failed": int("<failure" in xml),
        "errors": int("<error" in xml),
    }


@pytest.mark.parametrize("content", [None, "broken XML"])
def test_missing_evidence_cannot_pass(tmp_path: Path, content: str | None) -> None:
    path = tmp_path / "missing.xml"
    if content is not None:
        path.write_text(content)
    assert read_test_result(0, path)["status"] == "blocked"
    assert read_test_result(1, path)["status"] == "failed"


def test_gate_failure_overrides_skips_and_no_checks_cannot_pass() -> None:
    assert gate_status([]) == "blocked"
    assert gate_status([{"status": "passed"}]) == "passed"
    assert gate_status([{"status": "passed"}, {"status": "blocked"}]) == "blocked"
    assert gate_status([{"status": "blocked"}, {"status": "failed"}]) == "failed"


@pytest.mark.parametrize(
    ("skip_database", "eval_code", "eval_failed", "expected_exit", "status"),
    [
        (False, 0, 0, 0, "passed"),
        (True, 0, 0, 2, "blocked"),
        (True, 1, 0, 1, "failed"),
        (False, 0, 1, 1, "failed"),
    ],
)
def test_command_report_keeps_pending_separate_from_gate_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    skip_database: bool,
    eval_code: int,
    eval_failed: int,
    expected_exit: int,
    status: str,
) -> None:
    """Control external command outputs; exercise the real CLI/report boundary."""
    output = tmp_path / "gate.json"
    monkeypatch.setattr(sys, "argv", ["check_phase1", "--report", str(output)])

    def command_result(command: list[str]) -> int:
        if "scripts/check_foundation.py" in command:
            path = Path(command[command.index("--report") + 1])
            path.write_text(json.dumps({"result": "passed"}))
            path.with_suffix(".xml").write_text("<testsuite><testcase/></testsuite>")
        elif "pytest" in command:
            path = Path(command[command.index("--junitxml") + 1])
            child = (
                "<skipped/>"
                if skip_database and "backend/integration_tests" in command
                else ""
            )
            path.write_text(f"<testsuite><testcase>{child}</testcase></testsuite>")
        else:
            path = Path(command[command.index("--report") + 1])
            path.write_text(
                json.dumps(
                    {
                        "api_mode": "offline-infrastructure-only",
                        "real_agent_path_exercised": False,
                        "summary": {
                            "counts": {
                                "passed": 0,
                                "failed": eval_failed,
                                "pending": 7,
                                "skipped": int(bool(eval_code)),
                                "blocked": 0,
                            },
                            "executed": eval_failed,
                            "pass_rate": None,
                        },
                    }
                )
            )
            return eval_code
        return 0

    monkeypatch.setattr(check_phase1, "run", command_result)
    assert check_phase1.main() == expected_exit
    report = json.loads(output.read_text())
    assert report["result"] == status
    assert report["revision"]
    assert isinstance(report["dirty"], bool)
    assert all(check["command"] for check in report["checks"])
    summary = report["checks"][-1]["report"]["summary"]
    assert summary["counts"]["pending"] == 7
    assert summary["counts"]["passed"] == 0
    assert summary["pass_rate"] is None

"""Real disposable PostgreSQL gate; never constructs a paid provider."""

import json
from pathlib import Path

import pytest

from evals.phase3_gate import GateCase, load_cases


def assert_mocked_case(case: GateCase) -> None:
    from evals.phase3_gate import main

    target = Path(f"test-results/ticket06-mocked-{case.id}.json")
    assert (
        main(
            [
                "--mode",
                "mocked",
                "--partition",
                "all",
                "--case",
                case.id,
                "--report",
                str(target),
            ]
        )
        == 0
    )
    report = json.loads(target.read_bytes())
    assert report["counts"] == {
        "passed": 1,
        "failed": 0,
        "blocked": 0,
        "pending": 0,
        "skipped": 0,
    }
    assert report["live_tool_selection"] is None


@pytest.mark.parametrize(
    "case",
    [case for case in load_cases()[1] if case.scenario != "context_restore"],
    ids=lambda case: case.id,
)
def test_combined_mocked_gate(case: GateCase) -> None:
    assert_mocked_case(case)


def test_context_restore_case() -> None:
    assert_mocked_case(
        next(case for case in load_cases()[1] if case.scenario == "context_restore")
    )


@pytest.mark.parametrize(
    "control",
    ["wrong-tool", "fabricated-success", "cross-user", "unconfirmed-mutation"],
)
def test_adversarial_exit_control(control: str) -> None:
    from evals.phase3_gate import main

    path = Path(f"test-results/ticket06-control-{control}.json")
    assert main(["--control", control, "--report", str(path)]) == 1
    assert json.loads(path.read_bytes())["counts"]["failed"] == 1

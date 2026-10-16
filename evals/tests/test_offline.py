"""Dataset and report boundary regressions, not evidence of agent behavior."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from evals.graders import STATUSES, Result, summarize
from evals.run_local import ROOT, build_report
from evals.schema import Case, load_dataset


def test_versioned_seed_covers_categories_and_fixture_references() -> None:
    from careflow.fixtures import CLINIC, IDENTITIES

    manifest, cases = load_dataset(ROOT / "evals")
    assert manifest.dataset_version == "phase1-v1"
    assert {c.category for c in cases} == {
        "positive",
        "negative",
        "adversarial",
        "missing-evidence",
        "tool-misuse",
        "privacy",
        "escalation",
    }
    assert {c.partition for c in cases} == {"dev", "held-out"}
    assert all(c.clinic_fixture == str(CLINIC["id"]) for c in cases)
    assert all(c.actor_fixture in {str(i["id"]) for i in IDENTITIES} for c in cases)


@pytest.mark.parametrize(
    "mutation",
    [
        {"id": "unstable"},
        {"synthetic": False},
        {"severity": "low"},
        {"partition": "training"},
        {"turns": []},
        {"unknown": "value"},
        {"actor_fixture": "real-patient"},
        {"group": " "},
    ],
)
def test_invalid_case_contract_is_rejected(mutation: dict[str, object]) -> None:
    _, cases = load_dataset(ROOT / "evals")
    data = cases[0].model_dump() | mutation
    with pytest.raises(ValueError):
        Case.model_validate(data)


def test_contradictory_tool_expectations_are_rejected() -> None:
    _, cases = load_dataset(ROOT / "evals")
    data = cases[0].model_dump()
    data["expected"]["forbidden_tools"] = ["search_doctors"]
    with pytest.raises(ValueError, match="overlap"):
        Case.model_validate(data)


def test_all_statuses_are_distinct_and_only_executed_cases_enter_pass_rate() -> None:
    results = [
        Result(
            id=str(i), group="test", severity="critical", status=status, reason="test"
        )
        for i, status in enumerate(STATUSES)
    ]
    assert summarize(results) == {
        "total": 5,
        "counts": {"passed": 1, "failed": 1, "skipped": 1, "blocked": 1, "pending": 1},
        "executed": 2,
        "pass_rate": 0.5,
    }
    assert summarize(results[2:])["pass_rate"] is None


def test_offline_report_has_no_behavioral_passes_and_reproducible_metadata() -> None:
    report = build_report(ROOT / "evals", "all")
    assert report["api_mode"] == "offline-infrastructure-only"
    assert report["real_agent_path_exercised"] is False
    assert report["summary"] == {
        "total": 7,
        "executed": 0,
        "pass_rate": None,
        "counts": {"passed": 0, "failed": 0, "skipped": 0, "blocked": 0, "pending": 7},
    }
    assert report["model_id"] is None
    assert report["prompt_version"] is None
    assert report["tool_schema_version"] is None
    assert report["fixture_version"] == "ticket04-v1"
    assert len(str(report["revision"])) == 40
    assert isinstance(report["dirty"], bool)
    again = build_report(ROOT / "evals", "all")
    assert report | {"timestamp_utc": None} == again | {"timestamp_utc": None}


def test_cli_defaults_to_dev_and_can_run_held_out_separately(tmp_path: Path) -> None:
    for partition, count in (("dev", 5), ("held-out", 2)):
        output = tmp_path / f"{partition}.json"
        arguments = [] if partition == "dev" else ["--partition", partition]
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "evals.run_local",
                *arguments,
                "--report",
                str(output),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == 0, run.stderr
        report = json.loads(output.read_text())
        assert report["partition"] == partition
        assert report["summary"]["counts"]["pending"] == count


@pytest.mark.parametrize("kind", ["checksum", "duplicate", "malformed", "empty"])
def test_invalid_dataset_fails_cli_without_echoing_input_or_report(
    tmp_path: Path,
    kind: str,
) -> None:
    manifest = json.loads((ROOT / "evals/manifest.json").read_text())
    row = (ROOT / "evals/cases.jsonl").read_text().splitlines()[0]
    data = {
        "checksum": row,
        "duplicate": row + "\n" + row,
        "malformed": "SENSITIVE-INPUT",
        "empty": "",
    }[kind].encode()
    if kind != "checksum":
        manifest["cases_sha256"] = hashlib.sha256(data).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "cases.jsonl").write_bytes(data)
    report_path = tmp_path / "report.json"
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.run_local",
            "--dataset",
            str(tmp_path),
            "--report",
            str(report_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 2
    assert "SENSITIVE-INPUT" not in run.stdout + run.stderr
    assert not report_path.exists()

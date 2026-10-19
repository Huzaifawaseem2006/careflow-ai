"""Combined gate accounting must reject violations and preserve blocked cases."""

import json
from pathlib import Path

import pytest
from careflow.chat_contracts import Limits

from evals.phase3_gate import gate_exit, load_cases, main


def test_frozen_cases_have_held_out_partitions_and_executable_contracts() -> None:
    manifest, cases = load_cases()
    assert manifest["dataset_version"] == "phase3-gate-v1"
    assert len(cases) == 32
    assert sum(case.partition == "held-out" for case in cases) == 23
    assert all(case.state_assertions and case.response_assertions for case in cases)


def test_gate_does_not_pass_pending_or_failed_observations() -> None:
    assert gate_exit(["passed", "passed"]) == 0
    assert gate_exit(["passed", "failed"]) == 1
    for status in ["blocked", "pending", "skipped"]:
        assert gate_exit(["passed", status]) == 2
    assert gate_exit([]) == 2


def test_unapproved_live_mode_blocks_every_case_before_database_or_provider(
    tmp_path: Path,
) -> None:
    report = tmp_path / "blocked.json"
    assert (
        main(
            ["--mode", "anthropic", "--partition", "held-out", "--report", str(report)]
        )
        == 2
    )
    actual = json.loads(report.read_bytes())
    assert actual["counts"] == {
        "passed": 0,
        "failed": 0,
        "blocked": 23,
        "pending": 0,
        "skipped": 0,
    }
    assert actual["executed"] == 0
    assert actual["live_tool_selection"]["accuracy"] is None
    assert actual["live_tool_selection"]["denominator"] == 0


def test_backend_only_or_dev_results_cannot_pass_live_held_out_quality() -> None:
    from evals.phase3_gate import quality_summary

    _, cases = load_cases()
    for scenario, responses in [("context_owner", 0), ("stale_fee", 1)]:
        case = next(case for case in cases if case.scenario == scenario)
        result = quality_summary(
            [case],
            [
                {
                    "id": case.id,
                    "status": "passed",
                    "tool_selection": True,
                    "provider_responses": responses,
                }
            ],
            cases,
        )
        assert result["gate"] == "blocked"
        assert result["denominator"] == 0
        assert result["accuracy"] is None


def test_quality_requires_held_out_coverage_and_reports_uncertainty() -> None:
    from evals.phase3_gate import quality_summary

    _, cases = load_cases()
    selected = [case for case in cases if case.partition == "held-out"]
    rows: list[dict[str, object]] = [
        {
            "id": case.id,
            "status": "passed",
            "tool_selection": True,
            "provider_responses": 0 if case.scenario == "context_owner" else 1,
        }
        for case in selected
    ]
    result = quality_summary(selected, rows, cases)
    assert result["numerator"] == result["denominator"] == 22
    assert result["gate"] == "passed"
    assert result["wilson_95"] is not None
    assert quality_summary(selected[:-1], rows[:-1], cases)["gate"] == "blocked"
    rows[0]["provider_responses"] = 0
    assert quality_summary(selected, rows, cases)["gate"] == "blocked"


@pytest.mark.parametrize("corruption", ["mode", "source", "duplicate", "sdk"])
def test_combining_rejects_mixed_stale_or_duplicate_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    from evals.phase3_gate import combine_mocked

    manifest, cases = load_cases()
    monkeypatch.setattr("evals.phase3_gate.ROOT", tmp_path)
    monkeypatch.setattr("evals.phase3_gate.version", lambda package: "synthetic")
    directory = tmp_path / "test-results"
    directory.mkdir()
    reports = []
    for case in cases:
        reports.append(
            {
                "api_mode": "mocked-behavioral",
                "fault_injection": None,
                "source_sha256": (
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                ),
                "manifest": manifest,
                "results": [{"id": case.id, "status": "passed"}],
                "revision": "synthetic-revision",
                "dirty": True,
                "sdk_version": "synthetic",
                "config": Limits().model_dump(),
                "prompt_version": "synthetic",
                "tool_schema_version": "synthetic",
                "failed_checks": {},
                "gates": {"real_path": "passed"},
            }
        )
    if corruption == "mode":
        reports[0]["api_mode"] = "live-anthropic"
    elif corruption == "source":
        reports[0]["source_sha256"] = "0" * 64
    elif corruption == "sdk":
        for report in reports:
            report["sdk_version"] = "obsolete-sdk"
    else:
        reports[0]["results"] = [{"id": cases[1].id, "status": "passed"}]
    for case, report in zip(cases, reports, strict=True):
        (directory / f"ticket06-mocked-{case.id}.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
    with pytest.raises(ValueError):
        combine_mocked(tmp_path / "combined.json")


@pytest.mark.parametrize("status,code", [("failed", 1), ("blocked", 2)])
def test_combined_gate_label_reflects_later_failed_or_blocked_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str, code: int
) -> None:
    from evals.phase3_gate import combine_mocked

    manifest, cases = load_cases()
    monkeypatch.setattr("evals.phase3_gate.ROOT", tmp_path)
    monkeypatch.setattr("evals.phase3_gate.version", lambda package: "synthetic")
    directory = tmp_path / "test-results"
    directory.mkdir()
    for index, case in enumerate(cases):
        report = {
            "api_mode": "mocked-behavioral",
            "fault_injection": None,
            "source_sha256": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
            "manifest": manifest,
            "results": [{"id": case.id, "status": status if index == 1 else "passed"}],
            "revision": "synthetic-revision",
            "dirty": True,
            "sdk_version": "synthetic",
            "config": Limits().model_dump(),
            "prompt_version": "synthetic",
            "tool_schema_version": "synthetic",
            "failed_checks": {},
            "gates": {"real_path": "passed", "live_model_quality": "blocked"},
        }
        (directory / f"ticket06-mocked-{case.id}.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
    target = tmp_path / "combined.json"
    assert combine_mocked(target) == code
    assert json.loads(target.read_bytes())["gates"]["real_path"] == status


@pytest.mark.parametrize(
    "name", ["backend/migrations/versions/0001.py", "pyproject.toml", "alembic.ini"]
)
def test_evidence_fingerprint_includes_schema_and_dependency_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    from evals.phase3_gate import source_sha256

    monkeypatch.setattr("evals.phase3_gate.ROOT", tmp_path)
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("original")
    before = source_sha256()
    path.write_text("changed")
    assert source_sha256() != before


@pytest.mark.parametrize("value", ["512", "invalid"])
def test_effective_configuration_mismatch_blocks_before_application_or_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Configuration must be checked before execution")

    monkeypatch.setenv("CHAT_OUTPUT_TOKENS", value)
    monkeypatch.setattr("evals.phase3_behavior.run_case", forbidden)
    target = tmp_path / "blocked-config.json"
    assert main(["--partition", "held-out", "--report", str(target)]) == 2
    report = json.loads(target.read_bytes())
    assert report["counts"]["blocked"] == 23
    assert report["config"] is None


@pytest.mark.parametrize(
    "quality,expected", [("blocked", 2), ("failed", 1), ("passed", 0)]
)
def test_live_quality_is_required_for_successful_exit(
    quality: str, expected: int
) -> None:
    assert gate_exit(["passed"], quality_gate=quality) == expected


def test_offline_simulated_live_subset_exits_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from evals.live_budget import Ledger
    from evals.phase3_gate import Approval

    manifest, cases = load_cases()
    case = cases[0]
    approval = Approval(
        run_id="synthetic-offline-run",
        owner_approval_reference="Synthetic test only",
        model="claude-sonnet-5-5",
        dataset_sha256=manifest["cases_sha256"],
        case_ids=[case.id],
        maximum_usd="1",
        maximum_calls=1,
        pricing_checked="2026-10-19",
        retention_disclosed=True,
        account_model_access_verified=True,
        config=Limits(),
    )
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(approval.model_dump_json())
    ledger = tmp_path / "synthetic-ledger.sqlite"
    Ledger.initialize(ledger, previous_spend_usd="0", evidence="Offline test")

    async def access() -> bool:
        return True

    def observed(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "id": case.id,
            "status": "passed",
            "tool_selection": True,
            "provider_responses": 1,
            "provider_calls": 1,
            "checks": {},
        }

    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-offline-key")
    monkeypatch.setenv("CHAT_ENABLED", "true")
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("evals.phase3_gate.verify_model_access", access)
    monkeypatch.setattr("evals.phase3_behavior.run_case", observed)
    report = tmp_path / "simulated.json"
    assert (
        main(
            [
                "--mode",
                "anthropic",
                "--partition",
                "held-out",
                "--case",
                case.id,
                "--approval",
                str(approval_path),
                "--ledger",
                str(ledger),
                "--report",
                str(report),
            ]
        )
        == 2
    )
    assert json.loads(report.read_bytes())["live_tool_selection"]["gate"] == "blocked"

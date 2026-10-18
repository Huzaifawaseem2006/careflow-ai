"""Validate synthetic cases and report pending agent work without model/DB calls."""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from evals.graders import Result, summarize
from evals.schema import load_dataset

ROOT = Path(__file__).resolve().parents[1]


def build_report(directory: Path, partition: str) -> dict[str, object]:
    manifest, cases = load_dataset(directory)
    selected = [c for c in cases if partition == "all" or c.partition == partition]
    if not selected:
        raise ValueError("Partition contains no cases")
    results = [
        Result(
            id=c.id,
            group=c.group,
            severity=c.severity,
            status="pending",
            reason=(
                "Historical inventory only; behavioral execution uses evals.run_catalog"
            ),
        )
        for c in selected
    ]
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    )
    return {
        "report_schema_version": "1",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "revision": revision,
        "dirty": dirty,
        "api_mode": "offline-infrastructure-only",
        "real_agent_path_exercised": False,
        "model_id": None,
        "prompt_version": None,
        "tool_schema_version": None,
        "dataset_version": manifest.dataset_version,
        "dataset_sha256": manifest.cases_sha256,
        "case_schema_version": manifest.schema_version,
        "partition": partition,
        "fixture_version": manifest.fixture_version,
        "corpus_versions": sorted(
            {c.corpus_version for c in selected if c.corpus_version}
        ),
        "index_version": None,
        "summary": summarize(results),
        "by_group": {
            group: summarize([r for r in results if r.group == group])
            for group in sorted({r.group for r in results})
        },
        "by_severity": {
            severity: summarize([r for r in results if r.severity == severity])
            for severity in sorted({r.severity for r in results})
        },
        "metrics": dict.fromkeys(
            [
                "retrieval_recall_at_k",
                "citation_validity",
                "grounded_faq_correctness",
                "tool_selection_accuracy",
                "refusal_count",
                "escalation_count",
                "latency_distribution_ms",
                "token_counts",
                "estimated_cost",
                "actual_cost",
            ]
        ),
        "metrics_unavailable_reason": "No agent/model/retrieval/database path executed",
        "cost_methodology": "No provider calls; behavioral costs unmeasured",
        "results": [r.model_dump() for r in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "evals")
    parser.add_argument(
        "--partition", choices=["dev", "held-out", "all"], default="dev"
    )
    parser.add_argument(
        "--report", type=Path, default=ROOT / "evals/results/offline.json"
    )
    options = parser.parse_args()
    try:
        report = build_report(options.dataset, options.partition)
    except (ValueError, OSError, subprocess.SubprocessError):
        # Never echo case text, parser input, environment variables or credentials.
        parser.exit(
            2, "Offline eval failed: invalid dataset or unavailable Git metadata\n"
        )
    options.report.parent.mkdir(parents=True, exist_ok=True)
    options.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"]))
    return 0  # Infrastructure success; never a behavioral gate pass.


if __name__ == "__main__":
    raise SystemExit(main())

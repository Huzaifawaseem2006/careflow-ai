"""Honest accounting shared by offline reports and future adapter graders."""

from typing import Literal

from evals.schema import Contract, Text

Status = Literal["passed", "failed", "skipped", "blocked", "pending"]
STATUSES: tuple[Status, ...] = ("passed", "failed", "skipped", "blocked", "pending")


class Result(Contract):
    id: Text
    group: Text
    severity: Literal["normal", "high", "critical"]
    status: Status
    reason: Text


def summarize(results: list[Result]) -> dict[str, object]:
    """Only executed pass/fail cases enter a behavioral pass-rate denominator."""
    counts = {status: sum(r.status == status for r in results) for status in STATUSES}
    executed = counts["passed"] + counts["failed"]
    return {
        "total": len(results),
        "counts": counts,
        "executed": executed,
        "pass_rate": counts["passed"] / executed if executed else None,
    }

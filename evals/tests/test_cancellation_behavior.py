"""Independent cancellation oracle rejects invented success and state corruption."""

import json

import pytest

from evals.booking_behavior import Observation, grade
from evals.cancellation_behavior import cancellation_integrity


def evidence(status: str = "booked") -> tuple[list[set[str]], list[set[str]]]:
    source = {
        "id": "synthetic-appointment",
        "patient_id": "synthetic-patient",
        "clinic_id": "synthetic-clinic",
        "doctor_id": "synthetic-doctor",
        "slot_id": "synthetic-slot",
        "status": status,
        "version": 1,
        "doctor_name": "Synthetic Doctor",
        "start_at": "2026-10-21T09:00:00+05:00",
        "end_at": "2026-10-21T09:30:00+05:00",
        "timezone": "Asia/Karachi",
        "accepted_fee": 2500.0,
        "currency": "PKR",
        "created_at": "2026-10-19T04:00:00+00:00",
    }
    public = {key: value for key, value in source.items() if key != "version"}
    public["accepted_fee"] = "2500.00"
    committed = public | {"status": "cancelled"}
    before = [{json.dumps(source)}, set(), set(), set()]
    after = [
        {json.dumps(source | {"status": "cancelled", "version": 2})},
        set(),
        {
            json.dumps(
                {
                    "operation": "cancel",
                    "appointment_id": source["id"],
                    "response_snapshot": committed,
                }
            )
        },
        {
            json.dumps(
                {
                    "action": "cancel",
                    "appointment_id": source["id"],
                    "before_snapshot": public,
                    "after_snapshot": committed,
                }
            )
        },
    ]
    return before, after


def test_oracle_rejects_invented_success_on_an_already_cancelled_source() -> None:
    before, after = evidence("cancelled")
    assert not cancellation_integrity(before, after, "synthetic-appointment", True)


def test_oracle_accepts_postgres_trimmed_creation_timestamp_in_audit() -> None:
    before, after = evidence()
    for state in (before, after):
        row = json.loads(next(iter(state[0])))
        row["created_at"] = "2026-10-19T04:00:00.1+00:00"
        state[0] = {json.dumps(row)}
    retry = json.loads(next(iter(after[2])))
    retry["response_snapshot"]["created_at"] = "2026-10-19T04:00:00.100000+00:00"
    after[2] = {json.dumps(retry)}
    audit = json.loads(next(iter(after[3])))
    for key in ("before_snapshot", "after_snapshot"):
        audit[key]["created_at"] = "2026-10-19T04:00:00.100000+00:00"
    after[3] = {json.dumps(audit)}
    assert cancellation_integrity(before, after, "synthetic-appointment", True)


@pytest.mark.parametrize(
    "corruption",
    [
        "unchanged",
        "fee",
        "version",
        "audit-missing",
        "audit-before",
        "retry-action",
        "unrelated",
        "missing-source",
    ],
)
def test_oracle_rejects_fabricated_cancellation_and_changed_history(
    corruption: str,
) -> None:
    before, after = evidence()
    assert cancellation_integrity(before, after, "synthetic-appointment", True)
    if corruption == "unchanged":
        after[0] = before[0].copy()
    elif corruption in {"fee", "version"}:
        row = json.loads(next(iter(after[0])))
        row["accepted_fee" if corruption == "fee" else "version"] = 0
        after[0] = {json.dumps(row)}
    elif corruption == "audit-missing":
        after[3] = set()
    elif corruption == "audit-before":
        row = json.loads(next(iter(after[3])))
        row["before_snapshot"]["accepted_fee"] = "0.00"
        after[3] = {json.dumps(row)}
    elif corruption == "retry-action":
        row = json.loads(next(iter(after[2])))
        row["operation"] = "book"
        after[2] = {json.dumps(row)}
    elif corruption == "unrelated":
        after[0].add(json.dumps({"id": "another-patient", "status": "cancelled"}))
    else:
        before[0] = set()
    assert not cancellation_integrity(before, after, "synthetic-appointment", True)
    assert not cancellation_integrity(before, after, "synthetic-appointment", False)


@pytest.mark.parametrize(
    "change",
    [
        {"http_status": 503},
        {"outcome": "abstained"},
        {"state_delta": [0, 1, 1, 1]},
        {"secrets_excluded": False},
        {"review_exact": False},
        {"provider_stopped": False},
        {"state_integrity": False},
    ],
)
def test_cancellation_grader_rejects_wrong_outcome_or_state(
    change: dict[str, object],
) -> None:
    observation = Observation(
        http_status=200,
        outcome="answered",
        state_delta=[0, 1, 0, 0],
        secrets_excluded=True,
        review_exact=True,
        provider_stopped=True,
        state_integrity=True,
    )
    expected = {"http_status": 200, "outcome": "answered", "state_delta": [0, 1, 0, 0]}
    assert grade(observation, expected)
    assert not grade(
        Observation.model_validate(observation.model_dump() | change), expected
    )

"""Behavioral graders must reject wrong tool, fabricated price and forbidden output."""

import pytest
from careflow.chat_contracts import ChatResponse, Metrics, ToolOutcome


@pytest.mark.parametrize(
    "mutation", ["wrong-tool", "fabricated-fee", "forbidden-output", "state-change"]
)
def test_behavioral_graders_reject_deliberately_bad_observations(mutation: str) -> None:
    from evals.catalog_behavior import grade
    from evals.run_local import ROOT
    from evals.schema import load_dataset

    _, cases = load_dataset(ROOT / "evals")
    case = cases[2]  # Refusal/exfiltration case: no facts or tools are legal.
    response = ChatResponse(
        status="abstained", text="Synthetic demo. I cannot reveal secrets."
    )
    before, after = "unchanged", "unchanged"
    assert all(grade(case, response, before, after).values())
    if mutation == "wrong-tool":
        response.metrics = Metrics(
            tools=[ToolOutcome(name="sql", status="ok", latency_ms=0)]
        )
    elif mutation == "fabricated-fee":
        response.text += " Consultation fee PKR 9999.99."
    elif mutation == "forbidden-output":
        response.text += " Appointment confirmed."
    else:
        after = "changed"
    grader = {
        "wrong-tool": "tool_legality",
        "fabricated-fee": "grounding",
        "forbidden-output": "safety",
        "state-change": "state",
    }[mutation]
    assert grade(case, response, before, after)[grader] is False


def test_mocked_runner_refuses_demo_database_and_restores_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    from evals.run_catalog import disposable_database

    original = "postgresql+psycopg://demo:placeholder@127.0.0.1/careflow_ai"
    monkeypatch.setenv("DATABASE_URL", original)
    monkeypatch.setenv("TEST_DATABASE_URL", original)
    with pytest.raises(ValueError, match="Local maintenance"):
        with disposable_database():
            pytest.fail("Must not reach database work")
    assert os.environ["DATABASE_URL"] == original


def test_mocked_grader_snapshot_refuses_demo_database_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evals.catalog_behavior import state_digest

    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://demo:placeholder@127.0.0.1/careflow_ai"
    )
    with pytest.raises(ValueError, match="Disposable"):
        state_digest()

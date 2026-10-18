"""Independent adversarial checks that the executable context grader can fail."""

import pytest

from evals.context_behavior import Observation, grade


@pytest.mark.parametrize(
    "change",
    [
        {"http_status": 200},
        {"outcome": "answered"},
        {"state_unchanged": False},
        {"secrets_excluded": False},
        {"context_observed": False},
    ],
)
def test_context_grader_rejects_wrong_status_authority_state_or_disclosure(
    change: dict[str, object],
) -> None:
    expected = {"http_status": 404, "outcome": None}
    correct = Observation(
        http_status=404, outcome=None, state_unchanged=True, secrets_excluded=True
    )
    assert grade(correct, expected)
    assert not grade(
        Observation.model_validate(correct.model_dump() | change), expected
    )


@pytest.mark.parametrize(
    "broken",
    [
        {},
        {"untrusted_history": []},
        {
            "untrusted_history": [{"user": "Wrong", "assistant": "Safe"}],
            "current_user_message": "Now",
        },
        {
            "untrusted_history": [{"user": "Before", "assistant": "Wrong"}],
            "current_user_message": "Now",
        },
        {
            "untrusted_history": [{"user": "Before", "assistant": "Safe"}],
            "current_user_message": "Wrong",
        },
    ],
)
def test_restored_history_grader_rejects_missing_or_changed_followup_context(
    broken: dict[str, object],
) -> None:
    import json

    from evals.context_behavior import restored_history

    correct = {
        "untrusted_history": [{"user": "Before", "assistant": "Safe"}],
        "current_user_message": "Now",
    }
    assert restored_history(json.dumps(correct), "Before", "Safe", "Now")
    assert not restored_history(json.dumps(broken), "Before", "Safe", "Now")

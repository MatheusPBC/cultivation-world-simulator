"""Fail-closed edge contracts for public MutualAttack aggression."""

from __future__ import annotations

from types import SimpleNamespace

from src.classes.action_runtime import ActionStatus
from src.classes.mutual_action.attack import MutualAttack


def test_stale_target_before_first_execution_records_no_hostility(dummy_avatar, monkeypatch):
    """Commit-time validity is not enough: no first-frame target, no casus."""

    action = MutualAttack(dummy_avatar, dummy_avatar.world)
    monkeypatch.setattr(action, "can_start", lambda **_params: (False, "gone"))

    result = action.step(target_avatar="vanished")

    assert result.status is ActionStatus.FAILED
    assert result.events == []
    assert action._hostility_attempted is False
    assert action._aggression_event_id == ""


def test_renamed_replacement_reply_mutates_neither_person_nor_response_state(dummy_avatar):
    """A queued reply is pinned to an Avatar id, not a reusable name."""

    action = MutualAttack(dummy_avatar, dummy_avatar.world)
    action._target_avatar_id = "original-target"
    replacement = SimpleNamespace(
        id="replacement-target",
        is_dead=False,
        thinking="keep this thought",
        current_action=None,
        planned_actions=[],
    )

    result = action._handle_response_result(
        replacement,
        {"thinking": "stale reply", "response": "Escape", "response_source": "llm"},
    )

    assert result.status is ActionStatus.COMPLETED
    assert result.events == []
    assert replacement.thinking == "keep this thought"
    assert replacement.planned_actions == []
    assert action._response_settled is False
    assert action._defence_decision_event_id == ""

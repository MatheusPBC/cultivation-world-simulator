"""
`Avatar.commit_next_plan` is the only place `Action.can_start(**params)`
actually runs with concrete params, and the reason string it produces was
previously only logged and discarded. It must now land in the owning
decision's `AgentDecision.rejected`, addressed via
`Avatar.current_decision_event_id` -- including when the rejection happens
in a later month than the decision itself (§5.4 cardinality rules).
"""
from src.classes.action_runtime import ActionPlan
from src.classes.agent_decision import AgentDecision
from src.classes.event import Event, FactKind
from src.systems.cultivation import CultivationProgress


def _seed_decision(avatar, world, *, persist: bool = False):
    decision = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_id=str(avatar.id),
        chosen_chain=[{"action_name": "Breakthrough", "params": {}}],
    )
    causal_payload = {"deltas": [], "decision": decision.to_dict()}
    event = Event(
        world.month_stamp,
        "decision",
        related_avatars=[avatar.id],
        fact_kind=FactKind.DECISION,
        causal_payload=causal_payload,
    )
    avatar.current_decision_event_id = event.id
    avatar._current_decision_payload = causal_payload
    if persist:
        world.event_manager.add_event(event)
    return event


def test_commit_next_plan_captures_can_start_rejection_into_decision(dummy_avatar, base_world):
    _seed_decision(dummy_avatar, base_world)
    dummy_avatar.cultivation_progress = CultivationProgress(level=15, exp=0)  # not at bottleneck
    dummy_avatar.planned_actions.append(ActionPlan("Breakthrough", {}))

    started = dummy_avatar.commit_next_plan()

    assert started is None
    rejected = dummy_avatar._current_decision_payload["decision"]["rejected"]
    assert len(rejected) == 1
    assert rejected[0]["action_name"] == "Breakthrough"
    assert rejected[0]["params"] == {}
    assert rejected[0]["reason"]


def test_commit_next_plan_rejection_persists_when_decision_already_written(dummy_avatar, base_world):
    """Cross-month case: the decision event was already flushed to storage in
    a previous finalize_step, so capturing a later rejection must update the
    stored row (not silently only mutate an orphaned in-memory dict)."""
    event = _seed_decision(dummy_avatar, base_world, persist=True)
    dummy_avatar.cultivation_progress = CultivationProgress(level=15, exp=0)
    dummy_avatar.planned_actions.append(ActionPlan("Breakthrough", {}))

    dummy_avatar.commit_next_plan()

    stored = [
        e for e in base_world.event_manager.get_recent_events(limit=10, include_decisions=True)
        if e.id == event.id
    ]
    assert len(stored) == 1
    assert stored[0].causal_payload["decision"]["rejected"][0]["action_name"] == "Breakthrough"


def test_commit_next_plan_does_not_crash_without_a_recorded_decision(dummy_avatar, base_world):
    """A plan can be enqueued without going through phase_decide_actions
    (e.g. manual/roleplay). Rejection capture must be a no-op, not a crash."""
    assert dummy_avatar.current_decision_event_id == ""
    dummy_avatar.cultivation_progress = CultivationProgress(level=15, exp=0)
    dummy_avatar.planned_actions.append(ActionPlan("Breakthrough", {}))

    started = dummy_avatar.commit_next_plan()

    assert started is None


def test_commit_next_plan_success_does_not_touch_rejected(dummy_avatar, base_world):
    _seed_decision(dummy_avatar, base_world)
    dummy_avatar.cultivation_progress = CultivationProgress(level=30, exp=0)  # at bottleneck
    dummy_avatar.planned_actions.append(ActionPlan("Breakthrough", {}))

    started = dummy_avatar.commit_next_plan()

    assert started is not None
    assert dummy_avatar._current_decision_payload["decision"]["rejected"] == []

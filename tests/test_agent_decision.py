from src.classes.agent_decision import AgentDecision


def test_agent_decision_defaults():
    decision = AgentDecision()
    assert decision.subject_kind == "avatar"
    assert decision.source == "llm"
    assert decision.chosen_chain == []
    assert decision.rejected == []
    assert decision.considered_count == 0
    assert decision.id


def test_agent_decision_round_trips_through_to_dict_from_dict():
    decision = AgentDecision(
        month_stamp=42,
        subject_kind="avatar",
        subject_id="avatar-1",
        source="llm",
        considered_count=12,
        chosen_chain=[{"action_name": "Respire", "params": {}}],
        thinking="I should cultivate.",
        short_term_objective="Reach Foundation Establishment",
        rejected=[{"action_name": "Breakthrough", "params": {}, "reason": "Not at bottleneck"}],
    )

    restored = AgentDecision.from_dict(decision.to_dict())

    assert restored == decision


def test_agent_decision_from_dict_tolerates_missing_keys():
    restored = AgentDecision.from_dict({})

    assert restored.month_stamp == 0
    assert restored.subject_kind == "avatar"
    assert restored.chosen_chain == []
    assert restored.rejected == []
    assert restored.id

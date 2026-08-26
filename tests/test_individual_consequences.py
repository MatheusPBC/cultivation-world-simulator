from src.classes.individual_consequence import IndividualConsequenceState
from src.classes.action.attack import Attack


def test_relevant_damage_creates_and_aggregates_active_injury():
    state = IndividualConsequenceState()

    state.record_injury(month=12, max_hp=100, damage=25, cause_event_id="combat-1")
    state.record_injury(month=13, max_hp=100, damage=50, cause_event_id="combat-2")

    assert state.active_injury is not None
    assert state.active_injury.severity == "severe"
    assert state.active_injury.hp_lost == 75
    assert state.active_injury.cause_event_ids == ["combat-1", "combat-2"]
    assert state.derived_priority == "recover"


def test_small_damage_is_not_an_individual_consequence():
    state = IndividualConsequenceState()

    state.record_injury(month=12, max_hp=100, damage=24, cause_event_id="minor")

    assert state.active_injury is None
    assert state.derived_priority == ""


def test_full_hp_resolves_injury_and_preserves_event_ids():
    state = IndividualConsequenceState()
    state.record_injury(month=12, max_hp=100, damage=50, cause_event_id="combat-1")

    resolved = state.resolve_if_recovered(month=14, current_hp=100, max_hp=100)

    assert resolved is not None
    assert resolved["cause_event_ids"] == ["combat-1"]
    assert state.active_injury is None
    assert state.derived_priority == ""
    assert state.recent_resolved[0]["resolved_month"] == 14


def test_injury_blocks_attack_but_not_the_recovery_state_itself(dummy_avatar):
    dummy_avatar.individual_consequences.record_injury(
        month=12, max_hp=100, damage=25, cause_event_id="combat-1"
    )

    allowed, reason = Attack(dummy_avatar, dummy_avatar.world).can_start("any target")

    assert allowed is False
    assert "伤势未愈" in reason

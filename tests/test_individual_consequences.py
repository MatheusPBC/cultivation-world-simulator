from copy import copy

import pytest

from src.classes.action.assassinate import Assassinate
from src.classes.individual_consequence import IndividualConsequenceState
from src.classes.action.attack import Attack
from src.classes.action.dig_grave import DigGrave
from src.classes.event import Event
from src.classes.hp import HP
from src.classes.individual_consequence import record_hp_change_from_event
from src.classes.action.sect_mission import SectMission
from src.classes.action.take_treasure import TakeTreasure
from src.classes.mutual_action.attack import MutualAttack
from src.classes.mutual_action.conversation import Conversation
from src.classes.mutual_action.drive_away import DriveAway
from src.classes.mutual_action.occupy import Occupy
from src.classes.mutual_action.spar import Spar
from src.sim.simulator_engine.phases.lifecycle import phase_resolve_individual_consequences


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


def test_recovery_emits_navigable_event_and_state_delta(dummy_avatar):
    dummy_avatar.individual_consequences.record_injury(
        month=12,
        max_hp=100,
        damage=50,
        cause_event_id="combat-1",
    )
    dummy_avatar.hp.cur = dummy_avatar.hp.max

    events = phase_resolve_individual_consequences([dummy_avatar])

    assert len(events) == 1
    assert events[0].causal_links[0].cause_event_id == "combat-1"
    assert events[0].causal_links[0].relation.value == "resolves"
    assert events[0].causal_payload["deltas"][0]["aspect"] == "active_injury"
    assert events[0].causal_payload["deltas"][0]["after"] is None
    assert events[0].causal_payload["deltas"][1]["aspect"] == "recovery"
    assert events[0].causal_payload["deltas"][1]["magnitude"] == 0.0


def test_hp_is_bounded_and_zero_is_dead():
    hp = HP(max=100, cur=150)

    assert hp.cur == 100
    assert hp.reduce(150) is False
    assert hp.cur == 0
    assert hp.recover(150) is True
    assert hp.cur == 100


def test_hp_change_attaches_hp_and_injury_evidence_once(dummy_avatar):
    dummy_avatar.hp = HP(max=100, cur=80)
    event = Event(dummy_avatar.world.month_stamp, "A material injury occurred.", related_avatars=[dummy_avatar.id])
    before_hp = dummy_avatar.hp.cur
    dummy_avatar.hp.reduce(30)

    recorded = record_hp_change_from_event(dummy_avatar, event, before_hp)

    assert recorded is True
    deltas = event.causal_payload["deltas"]
    assert [delta["aspect"] for delta in deltas] == ["hp", "active_injury"]
    assert deltas[0]["before"] == "80"
    assert deltas[0]["after"] == "50"
    assert dummy_avatar.individual_consequences.active_injury is not None


def test_injury_blocks_attack_but_not_the_recovery_state_itself(dummy_avatar):
    dummy_avatar.individual_consequences.record_injury(
        month=12, max_hp=100, damage=25, cause_event_id="combat-1"
    )

    allowed, reason = Attack(dummy_avatar, dummy_avatar.world).can_start("any target")

    assert allowed is False
    assert "伤势未愈" in reason


@pytest.mark.parametrize(
    ("action_type", "params"),
    [
        (Attack, {"avatar_name": "target"}),
        (Assassinate, {"avatar_name": "target"}),
        (DigGrave, {"poi_id": "grave"}),
        (TakeTreasure, {"poi_id": "treasure"}),
        (SectMission, {}),
        (MutualAttack, {"target_avatar": "target"}),
        (Spar, {"target_avatar": "target"}),
        (DriveAway, {"target_avatar": "target"}),
        (Occupy, {"region_name": "region"}),
    ],
)
def test_all_audited_risky_actions_share_the_injury_guard(dummy_avatar, action_type, params):
    dummy_avatar.individual_consequences.record_injury(
        month=12,
        max_hp=100,
        damage=25,
        cause_event_id="combat-1",
    )

    allowed, reason = action_type(dummy_avatar, dummy_avatar.world).can_start(**params)

    assert allowed is False
    assert "伤势未愈" in reason


def test_injury_does_not_block_conversation(dummy_avatar):
    target = copy(dummy_avatar)
    target.id = "conversation-target"
    dummy_avatar.individual_consequences.record_injury(
        month=12,
        max_hp=100,
        damage=25,
        cause_event_id="combat-1",
    )

    allowed, reason = Conversation(dummy_avatar, dummy_avatar.world).can_start(target)

    assert allowed is True
    assert reason == ""

"""Focused evidence for real commanders and delayed bounded doctrines."""

import asyncio

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.systems.calendar_agenda import ScheduledSituation
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.field_engagement import field_engagement_offer_options, field_strength
from src.sim.medieval.force import withdraw_detachment, withdrawal_options
from src.sim.medieval.force_contact_policy import (COMMAND_REVIEW_KIND, REVIEW_KIND,
                                                   review_force_contacts, review_id)
from src.sim.medieval.force_command import (APPOINT_ACTION, SET_DOCTRINE_ACTION,
                                            appoint_detachment_commander, detachment_command_options,
                                            effective_doctrine, set_detachment_doctrine)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from tests.test_medieval_field_engagement import OWNER, decide, prepared_challenger_world, tick


def _commanded_world():
    world, own_id, _, _ = prepared_challenger_world()
    # The catalog's real Auren commander has the required skill.  Setup places
    # that same existing person beside the already-real column; no character is
    # generated or cloned by the command executor.
    person = world.society.characters["character:002"]
    world.society.characters[person.id] = person.model_copy(update={"location_id": "salgueiro"})
    option = next(item for item in detachment_command_options(world, OWNER, detachment_id=own_id)
                  if item.decision()["action"] == APPOINT_ACTION)
    command = appoint_detachment_commander(world, OWNER, option.id, decide(world, option).id)
    return world, own_id, person.id, command


def _set(world, detachment_id, doctrine):
    actor = EntityRef("character", world.society.detachment_commands[detachment_id].character_id)
    option = next(item for item in detachment_command_options(world, actor, detachment_id=detachment_id)
                  if item.decision()["action"] == SET_DOCTRINE_ACTION and item.doctrine == doctrine)
    return set_detachment_doctrine(world, actor, option.id, decide(world, option).id)


def test_real_commander_is_thresholded_local_delayed_and_round_trips(tmp_path):
    world, own_id, person_id, command = _commanded_world()
    assert command.character_id == person_id
    assert command.id == command.detachment_id == own_id
    assert world.society.characters[person_id].skills.command >= 40
    assert effective_doctrine(world, own_id) is None
    assert not any(option.decision()["action"] == SET_DOCTRINE_ACTION
                   for option in detachment_command_options(world, OWNER, detachment_id=own_id))

    command = _set(world, own_id, "hold")
    assert command.doctrine_effective_day == world.clock.absolute_day + 1
    assert effective_doctrine(world, own_id) is None
    tick(world)
    assert effective_doctrine(world, own_id) == "hold"

    path = tmp_path / "force-command.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    assert restored.society.detachment_commands[own_id].character_id == person_id


def test_hold_and_press_redistribute_existing_strength_without_inflation():
    world, own_id, _, _ = _commanded_world()
    detachment = world.society.detachments[own_id]
    # Prepared but hungry: hold spends the established position, press does not.
    world.society.detachments[own_id] = detachment.model_copy(update={"provisions": 0})
    baseline = field_strength(world, world.society.detachments[own_id])[0]
    _set(world, own_id, "hold")
    world.clock = world.clock.advance(1)
    hold = field_strength(world, world.society.detachments[own_id])[0]
    assert (baseline, hold) == (detachment.count * 3, detachment.count * 4)

    # A new command decision only changes the allocation tomorrow; press is
    # valuable only when actual provisions are present, never above total +4.
    world.society.detachments[own_id] = world.society.detachments[own_id].model_copy(
        update={"provisions": detachment.count * 3})
    assert not field_engagement_offer_options(world, OWNER), "hold cannot initiate a field engagement"
    _set(world, own_id, "press")
    assert effective_doctrine(world, own_id) == "hold", "replacement is not early"
    world.clock = world.clock.advance(1)
    press = field_strength(world, world.society.detachments[own_id])[0]
    assert press == detachment.count * 4
    assert press <= detachment.count * 4


def test_withdrawal_releases_commander_and_leaves_the_real_person_at_column_location():
    world, own_id, person_id, _ = _commanded_world()
    location = world.society.detachments[own_id].location_id
    option = withdrawal_options(world, OWNER, detachment_id=own_id)[0]
    decision = decide(world, option)
    withdraw_detachment(world, OWNER, option.id, decision.id)
    assert own_id not in world.society.detachment_commands
    assert world.society.characters[person_id].location_id == location
    released = [event for event in world.events if event.event_type == "detachment_commander_released"]
    assert len(released) == 1 and decision.id in {link.cause_event_id for link in released[0].causal_links}
    assert all(event.fact_kind == FactKind.STATE_TRANSITION for event in released)


def test_contact_gives_the_named_commander_a_separate_later_turn(monkeypatch, tmp_path):
    world, own_id, person_id, _ = _commanded_world()
    notice = next(item for item in world.knowledge.force_contact_notices.values()
                  if item.own_detachment_id == own_id and item.recipient_ref == OWNER)
    world.config = world.config.model_copy(update={"ai_enabled": True})
    asked = []

    async def choose(_world, actor, _situation, choices, **_kwargs):
        asked.append(actor)
        if actor.kind == "polity":
            return ai_decider.NO_ACTION
        assert actor == EntityRef("character", person_id)
        return next(item["id"] for item in choices if ":press:" in item["id"])

    monkeypatch.setattr(ai_decider, "select_option", choose)
    institutional = ScheduledSituation(review_id(notice.id), REVIEW_KIND, world.clock.absolute_day)
    asyncio.run(review_force_contacts(world, (institutional,)))
    assert asked == [OWNER]
    assert world.society.detachment_commands[own_id].doctrine is None

    path = tmp_path / "pending-commander-turn.mws"
    save_world(world, path)
    world = load_world(path)

    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    assert any(item.kind == COMMAND_REVIEW_KIND for item in due)
    resolve_dated(world, due)
    asyncio.run(review_force_contacts(world, due))
    assert asked[0] == OWNER and asked[-1] == EntityRef("character", person_id)
    assert world.society.detachment_commands[own_id].doctrine == "press"
    decision = next(item for item in reversed(world.events)
                    if item.event_type == "detachment_commander_decided")
    assert decision.decision["actor_ref"] == EntityRef("character", person_id).to_dict()
    assert notice.event_id in {link.cause_event_id for link in decision.causal_links}


def test_commander_no_action_is_a_decision_without_a_doctrine(monkeypatch):
    world, own_id, person_id, _ = _commanded_world()
    notice = next(item for item in world.knowledge.force_contact_notices.values()
                  if item.own_detachment_id == own_id and item.recipient_ref == OWNER)

    async def decline(_world, actor, _situation, _choices, **_kwargs):
        assert actor == EntityRef("character", person_id)
        return ai_decider.NO_ACTION

    monkeypatch.setattr(ai_decider, "select_option", decline)
    situation = ScheduledSituation(f"detachment-command-review:{notice.id}", COMMAND_REVIEW_KIND,
                                   world.clock.absolute_day)
    asyncio.run(review_force_contacts(world, (situation,)))
    assert world.society.detachment_commands[own_id].doctrine is None
    declined = [event for event in world.events if event.event_type == "detachment_commander_declined"]
    assert len(declined) == 1 and not declined[0].deltas
    assert declined[0].decision["actor_ref"] == EntityRef("character", person_id).to_dict()

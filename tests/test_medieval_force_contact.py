"""A physical armed contact grants a turn, never a battle."""

import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (detect_force_standoffs, raise_detachment, raise_options,
                                    stand_down_from_standoff, standoff_options)
from src.sim.medieval.force_contact_policy import REVIEW_KIND, review_force_contacts
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


OWNER = EntityRef("polity", "auren")
RIVAL = EntityRef("polity", "escarlia")
HOME = "campomanso"
TARGET = "salgueiro"


def decide(world, option):
    return record_event(world, "force_contact_decided", "Decisão diante de presença armada.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def contact_world():
    """One genuine raised column meets an already-present rival detachment."""
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 20})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    option = next(item for item in raise_options(world, OWNER) if item.destination_id == TARGET)
    own = raise_detachment(world, OWNER, option.id, decide(world, option).id)
    while world.society.detachments[own.id].stage == "marching":
        world.clock = world.clock.advance(1)
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))
    own = world.society.detachments[own.id]

    resident = next(item for item in world.society.population.values() if item.settlement_id == "ferroalto")
    rival_group = resident.model_copy(update={"id": f"pop:ferroalto:{resident.people}:soldier",
                                              "occupation": "soldier", "count": 5})
    world.society.population[rival_group.id] = rival_group
    rival = Detachment(id="detachment:contact-rival", owner_ref=RIVAL, source_group_id=rival_group.id,
                       count=5, location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0,
                       provisions=999, stage="present", started_day=world.clock.absolute_day,
                       due_day=world.clock.absolute_day + 1, decision_event_id=own.decision_event_id,
                       last_event_id=own.last_event_id)
    world.society.detachments[rival.id] = rival
    standoff = detect_force_standoffs(world, rival.id)[0]
    world.society.validate(set(world.map.regions), world)
    world.knowledge.validate(world)
    return world, own.id, rival.id, standoff.id


def enable(world):
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                   "ai_max_calls": 10})
    return world


def provider(monkeypatch, answer, prompts):
    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        if answer == "first":
            payload = json.loads(prompt[prompt.index("{"):])
            return {"selected_id": payload["choices"][0]["id"]}
        return {"selected_id": answer}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


async def advance_contact_review(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    await review_force_contacts(world, due)


async def test_force_contact_provider_stands_down_only_own_column_and_round_trips(tmp_path, monkeypatch):
    world, own_id, rival_id, standoff_id = contact_world()
    enable(world)
    prompts = []
    provider(monkeypatch, "first", prompts)
    notices = world.knowledge.force_contacts_for_actor(OWNER)
    assert len(notices) == 1
    assert notices[0].counterparty_ref == RIVAL and notices[0].own_detachment_id == own_id
    assert world.agenda.get(f"force-contact-review:{notices[0].id}").kind == REVIEW_KIND
    assert set(notices[0].model_dump()) == {"id", "recipient_ref", "standoff_id", "own_detachment_id",
                                            "counterparty_ref", "settlement_id", "event_id", "learned_day",
                                            "counterparty_strength_band", "counterparty_posture", "last_event_id",
                                            "channel"}
    people = sum(group.count for group in world.society.population.values())

    await advance_contact_review(world)

    assert world.society.detachments[own_id].stage == "disbanded"
    assert world.society.detachments[rival_id].stage == "present"
    assert world.society.force_standoffs[standoff_id].stage == "resolved"
    assert world.society.settlements[TARGET].occupier_id is None
    assert sum(group.count for group in world.society.population.values()) == people
    prompt = prompts[0]
    for private_rival_value in ("999", "source_group_id", "route_ids", "stock"):
        assert private_rival_value not in prompt
    started = next(event for event in world.events if event.event_type == "armed_standoff_started")
    stood_down = next(event for event in world.events if event.event_type == "detachment_stood_down")
    assert started.deltas and stood_down.deltas
    interpretations = {event.id for event in world.events if event.causal_origin.value == "llm_interpretation"}
    assert not interpretations & {link.cause_event_id for link in stood_down.causal_links}
    path = tmp_path / "force-contact.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


async def test_contact_noaction_or_invalid_authority_cannot_mutate_and_lapse_resolves_without_battle(monkeypatch):
    world, own_id, _, standoff_id = contact_world()
    enable(world)
    prompts = []
    provider(monkeypatch, ai_decider.NO_ACTION, prompts)
    before = world_snapshot(world)
    await advance_contact_review(world)
    assert world.society.force_standoffs[standoff_id].stage == "active"
    # The pre-existing column still consumes its own ration on a dated force
    # tick; the provider's NO_ACTION itself adds only a zero-delta receipt.
    new_events = world.events[before["event_count"]:]
    assert any(event.event_type == ai_decider.DECLINED_EVENT and not event.deltas for event in new_events)
    assert not any(event.event_type == "detachment_stood_down" for event in world.events)

    option = standoff_options(world, OWNER)[0]
    with pytest.raises(ValueError, match="stale or unknown"):
        stand_down_from_standoff(world, OWNER, option.id + ":forged", decide(world, option).id)
    office = world.authority.offices["office:polity:auren"]
    world.authority.offices[office.id] = office.model_copy(
        update={"scopes": tuple(scope for scope in office.scopes if scope != "military")})
    with pytest.raises(ValueError, match="stale or unknown"):
        stand_down_from_standoff(world, OWNER, option.id, decide(world, option).id)
    assert world.society.detachments[own_id].stage == "present"
    world.authority.offices[office.id] = office

    world.society.detachments[own_id] = world.society.detachments[own_id].model_copy(update={"provisions": 0})
    world.clock = world.clock.advance(1)
    resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))
    assert world.society.detachments[own_id].stage == "disbanded"
    assert world.society.force_standoffs[standoff_id].stage == "resolved"
    assert not any(event.event_type in {"battle_resolved", "casualties_taken", "loot_taken"}
                   for event in world.events)

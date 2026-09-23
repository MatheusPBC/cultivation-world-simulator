"""Bounded force-contact readings are factual knowledge, never battle data."""

import json

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (detect_force_standoffs, raise_detachment, raise_options,
                                    stand_down_from_standoff, standoff_options)
from src.sim.medieval.force_contact_policy import (contact_sighting_for_provider,
                                                    review_force_contacts)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.systems.calendar_agenda import ScheduledSituation


OWNER = EntityRef("polity", "auren")
RIVAL = EntityRef("polity", "escarlia")
HOME = "campomanso"
TARGET = "salgueiro"


def decide(world, option):
    return record_event(world, "sighting_test_decided", "Decisão de contato para teste.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def sighting_world():
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
        tick(world)
    own = world.society.detachments[own.id]
    resident = next(item for item in world.society.population.values() if item.settlement_id == "ferroalto")
    rival_group = resident.model_copy(update={"id": f"pop:ferroalto:{resident.people}:soldier",
                                              "occupation": "soldier", "count": 5})
    world.society.population[rival_group.id] = rival_group
    rival = Detachment(id="detachment:sighting-rival", owner_ref=RIVAL, source_group_id=rival_group.id,
                       count=5, location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0,
                       provisions=999, stage="present", started_day=world.clock.absolute_day,
                       due_day=world.clock.absolute_day + 1, decision_event_id=own.decision_event_id,
                       last_event_id=own.last_event_id)
    world.society.detachments[rival.id] = rival
    standoff = detect_force_standoffs(world, rival.id)[0]
    return world, own.id, rival.id, rival_group.id, standoff.id


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


async def test_contact_sighting_is_bounded_updates_only_on_change_and_round_trips(tmp_path, monkeypatch):
    world, own_id, rival_id, rival_group_id, standoff_id = sighting_world()
    own_notice = world.knowledge.force_contacts_for_actor(OWNER)[0]
    rival_notice = world.knowledge.force_contacts_for_actor(RIVAL)[0]
    assert (own_notice.counterparty_strength_band, own_notice.counterparty_posture) == ("1-9", "present")
    assert (rival_notice.counterparty_strength_band, rival_notice.counterparty_posture) == ("10-24", "present")
    assert "provisions" not in own_notice.model_dump() and "route_ids" not in own_notice.model_dump()

    # The underlying Society truth changes; only the affected private reading
    # receives one same-day factual update, then stays quiet if unchanged.
    rival_group = world.society.population[rival_group_id]
    world.society.population[rival_group_id] = rival_group.model_copy(update={"count": 10})
    rival = world.society.detachments[rival_id]
    world.society.detachments[rival_id] = rival.model_copy(update={"count": 10})
    before = len(world.events)
    detect_force_standoffs(world, rival_id)
    assert len(world.events) == before + 1
    assert world.knowledge.force_contacts_for_actor(OWNER)[0].counterparty_strength_band == "10-24"
    detect_force_standoffs(world, rival_id)
    assert len(world.events) == before + 1
    assert world.events[-1].event_type == "force_contact_sighting_observed"
    path = tmp_path / "sighting.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

    prompts = []
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 10, "ai_max_calls": 10})
    async def no_action(prompt, *args, **kwargs):
        prompts.append(prompt)
        return {"selected_id": ai_decider.NO_ACTION}
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    due = tick(world)
    await review_force_contacts(world, due)
    assert '"counterparty_strength_band": "10-24"' in prompts[0]
    for private in ("999", "source_group_id", "route_ids", "destination_id", "provisions"):
        assert private not in prompts[0]


async def test_contact_sighting_hides_after_resolution_or_age_and_provider_never_forces(monkeypatch):
    world, own_id, _, _, _ = sighting_world()
    notice = world.knowledge.force_contacts_for_actor(OWNER)[0]
    option = standoff_options(world, OWNER)[0]
    stand_down_from_standoff(world, OWNER, option.id, decide(world, option).id)
    assert contact_sighting_for_provider(world, notice) == {
        "counterparty_strength_band": None, "counterparty_posture": None}
    assert world.knowledge.force_contacts_for_actor(OWNER)[0].counterparty_strength_band == "1-9"

    aged, _, _, _, _ = sighting_world()
    aged_notice = aged.knowledge.force_contacts_for_actor(OWNER)[0]
    aged.clock = aged.clock.advance(3)
    assert contact_sighting_for_provider(aged, aged_notice) == {
        "counterparty_strength_band": None, "counterparty_posture": None}

    disabled, own_id, _, _, _ = sighting_world()
    notice = disabled.knowledge.force_contacts_for_actor(OWNER)[0]
    due = (ScheduledSituation(f"force-contact-review:{notice.id}", "force_contact_review",
                              disabled.clock.absolute_day),)
    before = world_snapshot(disabled)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    await review_force_contacts(disabled, due)
    assert world_snapshot(disabled) == before

    disabled.config = disabled.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})
    async def no_action(*args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    await review_force_contacts(disabled, due)
    assert disabled.society.detachments[own_id].stage == "present"
    assert not any(event.event_type in {"battle_resolved", "casualties_taken", "loot_taken"}
                   for event in disabled.events)

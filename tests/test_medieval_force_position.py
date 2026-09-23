"""A prepared position is a dated force fact, not a combat result."""

import asyncio
import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (detect_force_standoffs, force_options, force_position_options,
                                    occupy_settlement, prepare_force_position, raise_detachment, raise_options,
                                    withdraw_detachment, withdrawal_options)
from src.sim.medieval.force_contact_policy import review_force_contacts
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


OWNER = EntityRef("polity", "auren")
RIVAL = EntityRef("polity", "escarlia")
HOME = "campomanso"
TARGET = "salgueiro"


def decide(world, option):
    return record_event(world, "force_position_decided", "Decisão canônica de preparo.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def contact_world():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 20})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    raise_option = next(item for item in raise_options(world, OWNER, days=20) if item.destination_id == TARGET)
    own = raise_detachment(world, OWNER, raise_option.id, decide(world, raise_option).id, days=20)
    while world.society.detachments[own.id].stage == "marching":
        tick(world)
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)

    resident = next(item for item in world.society.population.values() if item.settlement_id == "ferroalto")
    rival_group = resident.model_copy(update={"id": f"pop:ferroalto:{resident.people}:soldier",
                                              "occupation": "soldier", "count": 5})
    world.society.population[rival_group.id] = rival_group
    own = world.society.detachments[own.id]
    rival = Detachment(id="detachment:position-rival", owner_ref=RIVAL, source_group_id=rival_group.id,
                       count=5, location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0,
                       provisions=999, stage="present", started_day=world.clock.absolute_day,
                       due_day=world.clock.absolute_day + 1, decision_event_id=own.decision_event_id,
                       last_event_id=own.last_event_id)
    world.society.detachments[rival.id] = rival
    standoff = detect_force_standoffs(world, rival.id)[0]
    return world, own.id, rival.id, standoff.id


async def _prepare_through_contact_provider(world, monkeypatch, prompts):
    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        payload = json.loads(prompt[prompt.index("{"):])
        preparation = next((choice["id"] for choice in payload["choices"]
                            if choice["label"].startswith("Preparar")), None)
        return {"selected_id": preparation or ai_decider.NO_ACTION}

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    due = tick(world)
    await review_force_contacts(world, due)


async def test_position_prepares_for_three_supplied_days_then_only_sighting_is_fortified(tmp_path, monkeypatch):
    world, own_id, _, standoff_id = contact_world()
    prompts = []
    await _prepare_through_contact_provider(world, monkeypatch, prompts)
    position_id = f"force-position:{own_id}"
    detachment = world.society.detachments[own_id]
    before = detachment.provisions
    assert world.society.force_positions[position_id].stage == "preparing"
    rival_notice = world.knowledge.force_contacts_for_actor(RIVAL)[0]
    assert rival_notice.counterparty_posture == "present"
    assert "999" not in prompts[0] and "provisions" not in prompts[0] and "route_ids" not in prompts[0]

    for _ in range(3):
        tick(world)
    position = world.society.force_positions[position_id]
    assert position.stage == "prepared"
    assert world.society.detachments[own_id].provisions == before - 3 * world.society.detachments[own_id].count
    assert world.knowledge.force_contacts_for_actor(RIVAL)[0].counterparty_posture == "fortified"
    assert world.society.force_standoffs[standoff_id].stage == "active"
    assert world.society.settlements[TARGET].occupier_id == OWNER.id

    path = tmp_path / "force-position.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    assert not any(event.event_type in {"battle_resolved", "casualties_taken", "loot_taken"}
                   for event in world.events)


def test_withdrawal_or_lapse_records_position_abandonment():
    world, own_id, _, _ = contact_world()
    option = force_position_options(world, OWNER)[0]
    prepare_force_position(world, OWNER, option.id, decide(world, option).id)
    withdrawal = withdrawal_options(world, OWNER, detachment_id=own_id)[0]
    withdraw_detachment(world, OWNER, withdrawal.id, decide(world, withdrawal).id)
    assert f"force-position:{own_id}" not in world.society.force_positions
    assert any(event.event_type == "force_position_abandoned" and event.deltas for event in world.events)

    lapsed, lapsed_id, _, _ = contact_world()
    option = force_position_options(lapsed, OWNER)[0]
    prepare_force_position(lapsed, OWNER, option.id, decide(lapsed, option).id)
    lapsed.society.detachments[lapsed_id] = lapsed.society.detachments[lapsed_id].model_copy(update={"provisions": 0})
    tick(lapsed)
    assert f"force-position:{lapsed_id}" not in lapsed.society.force_positions
    assert any(event.event_type == "force_position_abandoned" for event in lapsed.events)


async def test_provider_off_noaction_and_stale_option_never_prepare_or_fight(monkeypatch):
    world, own_id, _, _ = contact_world()
    notice = world.knowledge.force_contacts_for_actor(OWNER)[0]
    before = world_snapshot(world)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    await review_force_contacts(world, (world.agenda.get(f"force-contact-review:{notice.id}"),))
    assert world_snapshot(world) == before

    option = force_position_options(world, OWNER)[0]
    with pytest.raises(ValueError, match="stale or unknown"):
        prepare_force_position(world, OWNER, option.id + ":forged", decide(world, option).id)
    assert f"force-position:{own_id}" not in world.society.force_positions

    async def no_action(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    await review_force_contacts(world, (world.agenda.get(f"force-contact-review:{notice.id}"),))
    assert f"force-position:{own_id}" not in world.society.force_positions
    assert not any(event.event_type in {"battle_resolved", "casualties_taken", "loot_taken"}
                   for event in world.events)

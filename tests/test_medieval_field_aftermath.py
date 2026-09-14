"""A field victory permits a choice; it never grants settlement control by itself."""

import asyncio
import copy
import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.field_aftermath_policy import (execute_field_aftermath_option,
                                                      field_aftermath_options,
                                                      review_field_aftermaths, review_id)
from src.sim.medieval.field_engagement import (field_engagement_join_options,
                                               field_engagement_offer_options,
                                               join_field_engagement, offer_field_engagement)
from src.sim.medieval.force import (detect_force_standoffs, force_position_options,
                                    prepare_force_position, raise_detachment, raise_options)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


OWNER = EntityRef("polity", "auren")
RIVAL = EntityRef("polity", "escarlia")
HOME = "campomanso"
TARGET = "salgueiro"


def decide(world, option):
    return record_event(world, "field_aftermath_decided", "Decisão canônica após combate.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def resolved_victory_world():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 30})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    raised = next(item for item in raise_options(world, OWNER, days=20) if item.destination_id == TARGET)
    own = raise_detachment(world, OWNER, raised.id, decide(world, raised).id, days=20)
    while world.society.detachments[own.id].stage == "marching":
        tick(world)
    position = force_position_options(world, OWNER, detachment_id=own.id)[0]
    prepare_force_position(world, OWNER, position.id, decide(world, position).id)
    for _ in range(3):
        tick(world)
    own = world.society.detachments[own.id]

    resident = next(item for item in world.society.population.values() if item.settlement_id == "ferroalto")
    rival_group = resident.model_copy(update={"id": f"pop:ferroalto:{resident.people}:soldier",
                                              "occupation": "soldier", "count": 50})
    world.society.population[rival_group.id] = rival_group
    rival = Detachment(id="detachment:aftermath-rival", owner_ref=RIVAL, source_group_id=rival_group.id,
                       count=50, location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0,
                       provisions=100, stage="present", started_day=world.clock.absolute_day,
                       due_day=world.clock.absolute_day + 1, decision_event_id=own.decision_event_id,
                       last_event_id=own.last_event_id)
    world.society.detachments[rival.id] = rival
    detect_force_standoffs(world, rival.id)
    offer = field_engagement_offer_options(world, OWNER)[0]
    engagement = offer_field_engagement(world, OWNER, offer.id, decide(world, offer).id)
    # The defender's independent answer is a next-day contact turn, not an
    # immediate consequence of the challenge.
    tick(world)
    join = field_engagement_join_options(world, RIVAL)[0]
    join_field_engagement(world, RIVAL, join.id, decide(world, join).id)
    winner = next(notice for notice in world.knowledge.field_engagement_outcome_notices.values()
                  if notice.recipient_ref == OWNER)
    return world, engagement.id, winner


async def test_victory_schedules_private_review_and_explicit_occupy_preserves_assets(tmp_path, monkeypatch):
    world, engagement_id, notice = resolved_victory_world()
    scheduled = world.agenda.get(review_id(notice.id))
    assert scheduled is not None and scheduled.due_day == world.clock.absolute_day + 1
    assert world.society.field_engagements[engagement_id].winner_ref == OWNER
    assert world.society.settlements[TARGET].occupier_id is None

    path = tmp_path / "field-aftermath.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

    due = tick(world)
    stock_before = {key: item.model_dump(mode="json") for key, item in world.economy.stocks.items()}
    account_before = {key: item.model_dump(mode="json") for key, item in world.economy.accounts.items()}
    administration_before = world.society.settlements[TARGET].administrator_id
    prompts = []

    async def choose_occupy(prompt, *args, **kwargs):
        prompts.append(prompt)
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": next(item["id"] for item in payload["choices"]
                               if item["label"].startswith("Ocupar"))}

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                   "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_occupy)
    await review_field_aftermaths(world, due)

    assert world.society.settlements[TARGET].occupier_id == OWNER.id
    assert world.society.settlements[TARGET].administrator_id == administration_before
    assert {key: item.model_dump(mode="json") for key, item in world.economy.stocks.items()} == stock_before
    assert {key: item.model_dump(mode="json") for key, item in world.economy.accounts.items()} == account_before
    assert "counterparty_strength_band" not in prompts[0]
    assert "provisions" not in prompts[0] and "route_ids" not in prompts[0]
    assert not any(event.event_type in {"battle_resolved", "loot_taken"} for event in world.events)


async def test_provider_off_or_no_action_leaves_victory_without_occupation(monkeypatch):
    world, _, notice = resolved_victory_world()
    due = tick(world)
    before = world_snapshot(world)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    await review_field_aftermaths(world, due)
    assert world_snapshot(world) == before

    silent, _, _ = resolved_victory_world()
    silent_due = tick(silent)

    async def no_action(*_args, **_kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    silent.config = silent.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                     "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    await review_field_aftermaths(silent, silent_due)
    assert silent.society.settlements[TARGET].occupier_id is None
    assert not any(event.event_type in {"settlement_occupied", "battle_resolved", "loot_taken"}
                   for event in silent.events[-2:])


def test_stale_authority_or_supervening_occupier_block_aftermath_atomically():
    world, _, notice = resolved_victory_world()
    option = next(item for item in field_aftermath_options(world, OWNER, outcome_notice_id=notice.id)
                  if item.decision()["action"] == "occupy_settlement")
    with pytest.raises(ValueError, match="stale or unknown"):
        execute_field_aftermath_option(world, OWNER, notice.id, option.id + ":forged", decide(world, option).id)
    assert world.society.settlements[TARGET].occupier_id is None

    authority_lost = copy.deepcopy(world)
    office = authority_lost.authority.offices["office:polity:auren"]
    authority_lost.authority.offices[office.id] = office.model_copy(
        update={"scopes": tuple(scope for scope in office.scopes if scope != "military")})
    with pytest.raises(ValueError, match="stale or unknown"):
        execute_field_aftermath_option(authority_lost, OWNER, notice.id, option.id,
                                       decide(authority_lost, option).id)
    assert authority_lost.society.settlements[TARGET].occupier_id is None

    occupied = copy.deepcopy(world)
    occupied.society.set_occupation(TARGET, RIVAL.id)
    with pytest.raises(ValueError, match="no longer possible"):
        execute_field_aftermath_option(occupied, OWNER, notice.id, option.id, decide(occupied, option).id)
    assert occupied.society.settlements[TARGET].occupier_id == RIVAL.id

"""A column can leave a real occupation without resolving a battle."""

import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (force_options, occupy_settlement, raise_detachment, raise_options,
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
    return record_event(world, "withdrawal_test_decided", "Decisão de retirada para teste.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def food_total(world):
    return (sum(stock.goods.get("food", 0) for stock in world.economy.stocks.values())
            + sum(detachment.provisions for detachment in world.society.detachments.values()
                  if detachment.stage != "disbanded")
            + sum(parcel.quantity for parcel in world.economy.parcels.values()
                  if world.economy.freight_orders[parcel.order_id].resource_id == "food"))


def withdrawal_world():
    """A supplied Auren column occupies Salgueiro, then meets a rival there."""
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 20})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    # Twenty days avoids manufacturing a supply notice in this withdrawal
    # fixture; campaign freight remains an independent owner concern.
    option = next(item for item in raise_options(world, OWNER, days=20) if item.destination_id == TARGET)
    own = raise_detachment(world, OWNER, option.id, decide(world, option).id, days=20)
    while world.society.detachments[own.id].stage == "marching":
        tick(world)
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)

    resident = next(item for item in world.society.population.values() if item.settlement_id == "ferroalto")
    rival_group = resident.model_copy(update={"id": f"pop:ferroalto:{resident.people}:soldier",
                                              "occupation": "soldier", "count": 5})
    world.society.population[rival_group.id] = rival_group
    own = world.society.detachments[own.id]
    rival = Detachment(id="detachment:withdrawal-rival", owner_ref=RIVAL, source_group_id=rival_group.id,
                       count=5, location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0,
                       provisions=999, stage="present", started_day=world.clock.absolute_day,
                       due_day=world.clock.absolute_day + 1, decision_event_id=own.decision_event_id,
                       last_event_id=own.last_event_id)
    world.society.detachments[rival.id] = rival
    from src.sim.medieval.force import detect_force_standoffs
    standoff = detect_force_standoffs(world, rival.id)[0]
    return world, own.id, rival.id, standoff.id


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def withdrawal_provider(monkeypatch, prompts):
    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": next(choice["id"] for choice in payload["choices"]
                               if choice["label"].startswith("Retirar"))}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


async def test_contact_provider_withdraws_occupied_force_home_with_real_upkeep(tmp_path, monkeypatch):
    world, own_id, rival_id, standoff_id = withdrawal_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})
    prompts = []
    withdrawal_provider(monkeypatch, prompts)
    before_food = food_total(world)
    baseline = len(world.events)

    due = tick(world)
    await review_force_contacts(world, due)
    assert world.society.detachments[own_id].stage == "marching"
    assert world.society.settlements[TARGET].occupier_id is None
    assert world.society.detachments[rival_id].stage == "present"
    assert world.society.force_standoffs[standoff_id].stage == "resolved"
    assert "999" not in prompts[0] and "source_group_id" not in prompts[0]

    while world.society.detachments[own_id].stage == "marching":
        tick(world)
    own = world.society.detachments[own_id]
    consumed = sum(own.count for event in world.events[baseline:] if event.event_type == "detachment_supplied")
    assert own.stage == "present" and own.location_id == HOME
    assert world.knowledge.settlement_report(OWNER, HOME) is not None
    assert food_total(world) == before_food - consumed
    assert not any(event.event_type in {"battle_resolved", "casualties_taken", "loot_taken"}
                   for event in world.events)
    path = tmp_path / "withdrawal.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_withdrawal_rejects_stale_mandateless_unknown_route_and_active_supply():
    world, own_id, _, _ = withdrawal_world()
    option = withdrawal_options(world, OWNER)[0]
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale or unknown"):
        withdraw_detachment(world, OWNER, option.id + ":forged", decide(world, option).id)
    assert world.society.detachments[own_id].stage == "present"
    assert world.society.settlements[TARGET].occupier_id == OWNER.id
    assert world_snapshot(world)["event_count"] == before["event_count"] + 1

    office = world.authority.offices["office:polity:auren"]
    world.authority.offices[office.id] = office.model_copy(
        update={"scopes": tuple(scope for scope in office.scopes if scope != "military")})
    assert not withdrawal_options(world, OWNER)
    with pytest.raises(ValueError, match="stale or unknown"):
        withdraw_detachment(world, OWNER, option.id, decide(world, option).id)
    world.authority.offices[office.id] = office

    route_less, _, _, _ = withdrawal_world()
    route_less.knowledge.route_reports.clear()
    assert not withdrawal_options(route_less, OWNER)

    supplied, supplied_id, _, _ = withdrawal_world()
    supplied.society.detachments[supplied_id] = supplied.society.detachments[supplied_id].model_copy(
        update={"provisions": 100})
    tick(supplied)  # real upkeep records the low-bag notice; it is not test-authored knowledge.
    assert any(notice.detachment_id == supplied_id and notice.state == "open"
               for notice in supplied.knowledge.campaign_supply_notices.values())
    assert not withdrawal_options(supplied, OWNER)
    assert not any(event.event_type in {"battle_resolved", "casualties_taken", "loot_taken"}
                   for event in supplied.events)

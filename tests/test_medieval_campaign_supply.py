"""Campaign food travels by ordinary freight or the column simply lapses."""

import json

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.force import force_options, occupy_settlement, raise_detachment, raise_options
from src.sim.medieval.campaign_supply import (campaign_stock_id, review_campaign_supplies)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


OWNER = EntityRef("polity", "auren")
HOME = "campomanso"
TARGET = "salgueiro"


def decide(world, option):
    return record_event(world, "campaign_test_decided", "Decisão de campanha para teste.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


async def campaign_world():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 20})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    option = next(item for item in raise_options(world, OWNER) if item.destination_id == TARGET)
    detachment = raise_detachment(world, OWNER, option.id, decide(world, option).id)
    while world.society.detachments[detachment.id].stage == "marching":
        await advance(world)
    detachment = world.society.detachments[detachment.id]
    assert campaign_stock_id(detachment.id) in world.economy.stocks
    return world, detachment.id


def enable(world):
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                   "ai_max_calls": 10})


def provider(monkeypatch, answer, prompts):
    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        if answer == "first":
            payload = json.loads(prompt[prompt.index("{"):])
            return {"selected_id": payload["choices"][0]["id"]}
        return {"selected_id": answer}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


async def advance(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    await review_campaign_supplies(world, due)


def totals(world):
    food = (sum(stock.goods.get("food", 0) for stock in world.economy.stocks.values())
            + sum(detachment.provisions for detachment in world.society.detachments.values()
                  if detachment.stage != "disbanded")
            + sum(parcel.quantity for parcel in world.economy.parcels.values()
                  if world.economy.freight_orders[parcel.order_id].resource_id == "food"))
    return food, sum(account.balance for account in world.economy.accounts.values()), \
        sum(group.count for group in world.society.population.values())


async def make_low(world, detachment_id):
    # Arrival with the force's real ten-day ration creates the route-aware
    # early warning (home freight needs longer than the remaining field bag).
    return next(item for item in world.knowledge.campaign_supply_notices.values()
                if item.detachment_id == detachment_id and item.state == "open")


async def test_campaign_supply_freight_arrives_loads_bag_and_round_trips(tmp_path, monkeypatch):
    world, detachment_id = await campaign_world()
    enable(world)
    prompts = []
    provider(monkeypatch, "first", prompts)
    notice = await make_low(world, detachment_id)
    before_food, before_money, before_people = totals(world)
    baseline_events = len(world.events)
    await advance(world)  # provider opens freight, force remains supplied.
    order = next(iter(world.economy.freight_orders.values()))
    assert order.destination_id == campaign_stock_id(detachment_id) and order.owner_ref == OWNER
    assert world.knowledge.campaign_supply_notices[notice.id].state == "dispatched"
    prompt = prompts[0]
    for private_value in ("stock:", "account", "balance", "route_ids"):
        assert private_value not in prompt

    for _ in range(12):
        if world.knowledge.campaign_supply_notices[notice.id].state == "fulfilled":
            break
        await advance(world)
    detachment = world.society.detachments[detachment_id]
    assert detachment.stage == "present" and detachment.provisions >= 100
    assert world.knowledge.campaign_supply_notices[notice.id].state == "fulfilled"
    after_food, after_money, after_people = totals(world)
    consumed = sum(detachment.count for event in world.events[baseline_events:]
                   if event.event_type == "detachment_supplied")
    assert after_food == before_food - consumed
    assert after_money == before_money and after_people == before_people
    interpretations = {event.id for event in world.events if event.causal_origin.value == "llm_interpretation"}
    freight = next(event for event in world.events if event.event_type == "freight_opened" and event.id == order.last_event_id)
    assert not interpretations & {link.cause_event_id for link in freight.causal_links}
    path = tmp_path / "campaign.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


async def test_noaction_or_blocked_cargo_never_forces_supply_and_the_force_lapses(monkeypatch):
    world, detachment_id = await campaign_world()
    enable(world)
    prompts = []
    provider(monkeypatch, ai_decider.NO_ACTION, prompts)
    occupy = next(option for option in force_options(world, OWNER) if option.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)
    await make_low(world, detachment_id)
    await advance(world)
    assert not world.economy.freight_orders
    while world.society.detachments[detachment_id].stage != "disbanded":
        await advance(world)
    assert world.society.settlements[TARGET].occupier_id is None

    delayed, delayed_id = await campaign_world()
    enable(delayed)
    provider(monkeypatch, "first", [])
    await make_low(delayed, delayed_id)
    await advance(delayed)
    order = next(iter(delayed.economy.freight_orders.values()))
    for route_id in order.route_ids:
        delayed.map.routes[route_id].update_runtime(enabled=False)
    while delayed.society.detachments[delayed_id].stage != "disbanded":
        await advance(delayed)
    assert any(event.event_type == "cargo_delayed" for event in delayed.events)
    assert delayed.society.detachments[delayed_id].stage == "disbanded"
    assert not any(event.event_type in {"battle_resolved", "casualties_taken", "loot_taken"}
                   for event in delayed.events)

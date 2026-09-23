"""One creature decision interrupts a real defensive plan and a food shipment."""

import asyncio
from copy import deepcopy

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_creatures import DRAKE_ID, ROUTE_ID
from src.sim.medieval import ai_decider
from src.sim.medieval.creatures import creature_options, execute_creature_option
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.markets import purchase
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.strategy_response import (adopt_occupied_settlement_defense,
                                                 defense_adoption_options,
                                                 review_strategy_responses_with_provider)
from tests.test_medieval_creatures import crossed_world
from tests.test_medieval_markets import consent, terms
from tests.test_medieval_strategy_response import tick


VALEDOURO = EntityRef("polity", "valedouro")


def decide(world, option):
    return record_event(world, "fixture_decided", "O ator escolheu uma opção válida.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


@pytest.mark.asyncio
async def test_drake_closure_holds_a_mobilized_column_and_food_against_open_route(monkeypatch, tmp_path):
    world = await crossed_world()
    demand_option = next(item for item in creature_options(world, DRAKE_ID) if item.kind == "request")
    execute_creature_option(world, DRAKE_ID, demand_option.id, decide(world, demand_option).id)
    demand = next(iter(world.creatures.demands.values()))

    while world.clock.absolute_day < demand.due_day - 1:
        tick(world)
    direct = world.map.routes["road-portovelho-salgueiro"]
    record_event(world, "fixture_road_closed", "Uma estrada existente está indisponível.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("route", direct.id, "enabled", True, False),))
    direct.update_runtime(enabled=False)
    settlement = world.society.settlements["portovelho"]
    record_event(world, "fixture_occupation", "A cidade encontra-se ocupada.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("settlement", settlement.id, "occupier_id", None, "escarlia"),))
    world.society.set_occupation(settlement.id, "escarlia")
    refresh_route_reports(world)
    refresh_settlement_reports(world)

    adoption = next(item for item in defense_adoption_options(world, VALEDOURO)
                    if item.settlement_id == "portovelho")
    plan = adopt_occupied_settlement_defense(world, VALEDOURO, adoption.id, decide(world, adoption).id)
    values = terms(world, quantity=100)
    order = purchase(world, *consent(world, values))
    assert ROUTE_ID in order.route_ids

    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 10, "ai_max_calls": 100,
    })
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def choose(_world, _actor, _situation, choices, **_kwargs):
        return next(item["id"] for item in choices if ROUTE_ID in item["id"] and ":160:" in item["id"])

    monkeypatch.setattr(ai_decider, "select_option", choose)
    due = tick(world)
    assert world.clock.absolute_day == demand.due_day
    assert await review_strategy_responses_with_provider(world, due)
    plan = world.strategy.plans[plan.id]
    assert plan.stage == "mobilized"
    column_id = plan.detachment_id
    assert ROUTE_ID in world.society.detachments[column_id].route_ids

    open_world = deepcopy(world)
    restriction = next(item for item in creature_options(world, DRAKE_ID) if item.kind == "restrict")
    execute_creature_option(world, DRAKE_ID, restriction.id, decide(world, restriction).id)
    closure = next(item for item in reversed(world.events) if item.event_type == "creature_restricted_route")
    assert not world.map.routes[ROUTE_ID].enabled

    for _ in range(12):
        tick(world)
        tick(open_world)
        if any(event.event_type == "detachment_held" for event in world.events):
            break
    else:
        pytest.fail("the column never reached the closed river")
    held = next(item for item in reversed(world.events) if item.event_type == "detachment_held")
    assert closure.id in {link.cause_event_id for link in held.causal_links}
    assert world.society.detachments[column_id].stage == "marching"
    assert world.society.detachments[column_id].route_index < len(world.society.detachments[column_id].route_ids)
    assert open_world.society.detachments[column_id].route_index > world.society.detachments[column_id].route_index

    for _ in range(12):
        tick(world)
        tick(open_world)
        if any(event.event_type == "cargo_delayed" for event in world.events):
            break
    assert any(event.event_type == "cargo_delayed" for event in world.events)
    assert any(closure.id in {link.cause_event_id for link in event.causal_links}
               for event in world.events if event.event_type == "cargo_delayed")
    assert open_world.economy.freight_orders[order.id].delivered_quantity > \
        world.economy.freight_orders[order.id].delivered_quantity
    assert open_world.society.detachments[column_id].stage == "present"

    path = tmp_path / "drake-interrupted-campaign.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True

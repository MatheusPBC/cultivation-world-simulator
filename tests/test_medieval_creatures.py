"""The drake only knows what crossed its river, and only asks with a decision."""

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.creatures import (creature_options, execute_creature_option, offer_creature_tribute,
                                        tribute_options)
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.run.medieval_creatures import DRAKE_ID, ROUTE_ID
from src.sim.medieval.markets import purchase
from tests.test_medieval_logistics import cargo_world, total_food
from tests.test_medieval_markets import consent, terms

SELLER_STOCK = "stock:campomanso"
AUREN = EntityRef("polity", "auren")
VALEDOURO = EntityRef("polity", "valedouro")


def decide(world, option):
    return record_event(world, "creature_decided", "Decisão do habitante do rio.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def buy_across_the_river(world, quantity=10):
    """A real bilateral purchase whose second leg crosses the drake's river."""
    values = terms(world, quantity=quantity)
    assert ROUTE_ID in values["route_ids"], "the agreed path must cross the river"
    return purchase(world, *consent(world, values))


async def crossed_world(crossings=8, steps=40):
    """Real cargo crosses the drake's river until it is materially hungry."""
    world = cargo_world()
    seller = world.economy.stocks[SELLER_STOCK]
    world.economy.stocks[seller.id] = seller.model_copy(
        update={"goods": {**seller.goods, "food": seller.goods.get("food", 0) + 5000}})
    for _ in range(crossings):
        buy_across_the_river(world)
    engine = MedievalSimulator(world)
    drake = world.creatures.creatures[DRAKE_ID]
    for _ in range(steps):
        if world.creatures.creatures[DRAKE_ID].condition < drake.hunger_threshold:
            break
        await engine.step()
    assert world.creatures.creatures[DRAKE_ID].condition < drake.hunger_threshold
    return world


def pick(world, kind, **fields):
    return next(item for item in creature_options(world, DRAKE_ID)
                if item.kind == kind and all(getattr(item, key) == value for key, value in fields.items()))


async def test_a_river_crossing_is_perceived_and_a_tribute_settles_the_demand(tmp_path):
    world = await crossed_world()
    drake = world.creatures.creatures[DRAKE_ID]
    assert drake.perceived_crossings > 0 and drake.condition < 1000
    perception = next(item for item in reversed(world.events) if item.event_type == "creature_perceived_cargo")
    departure = next(item for item in world.events
                     if item.id in {link.cause_event_id for link in perception.causal_links}
                     and item.event_type == "cargo_departed")
    assert departure.day == perception.day, "perception follows a real departure"
    assert not world.creatures.demands, "hunger alone demands nothing"

    request = pick(world, "request", route_id=ROUTE_ID)
    execute_creature_option(world, DRAKE_ID, request.id, decide(world, request).id)
    demand = next(iter(world.creatures.demands.values()))
    assert demand.stage == "open" and demand.food == drake.tribute_food
    notices = [world.knowledge.creature_tribute_notices[key]
               for key in sorted(world.knowledge.creature_tribute_notices)]
    assert {item.recipient_ref for item in notices} == {AUREN, VALEDOURO}
    for notice in notices:
        assert (notice.food, notice.route_id, notice.due_day) == (demand.food, ROUTE_ID, demand.due_day)
        assert not any(hasattr(notice, field) for field in ("condition", "hunger_threshold", "perceived_crossings"))
    assert world.map.routes[ROUTE_ID].enabled, "asking closes nothing"

    food = total_food(world)
    option = next(item for item in tribute_options(world, AUREN) if item.stock_id == SELLER_STOCK)
    stock_before = world.economy.stocks[SELLER_STOCK].goods["food"]
    settled = offer_creature_tribute(world, AUREN, option.id, decide(world, option).id)

    assert settled.stage == "satisfied" and settled.settled_by_ref == AUREN.to_dict()
    assert world.economy.stocks[SELLER_STOCK].goods["food"] == stock_before - demand.food
    assert total_food(world) == food - demand.food, "the tribute was eaten, not created"
    assert world.creatures.creatures[DRAKE_ID].condition > drake.condition
    assert world.map.routes[ROUTE_ID].enabled
    path = tmp_path / "drake.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    assert restored.creatures.creatures[DRAKE_ID] == world.creatures.creatures[DRAKE_ID]
    remembered = restored.creatures.creatures[DRAKE_ID].memory_event_ids
    assert any(item.event_type == "creature_perceived_cargo" and item.id in remembered
               for item in restored.events)
    assert any(item.event_type == "creature_tribute_delivered"
               and item.id in remembered for item in restored.events)


async def test_partial_tribute_keeps_demand_open_and_can_be_completed():
    world = await crossed_world()
    request = pick(world, "request", route_id=ROUTE_ID)
    execute_creature_option(world, DRAKE_ID, request.id, decide(world, request).id)
    demand = next(iter(world.creatures.demands.values()))
    partial = next(item for item in tribute_options(world, AUREN)
                   if item.stock_id == SELLER_STOCK and item.food < demand.food)
    before = world.economy.stocks[SELLER_STOCK].goods["food"]
    offer_creature_tribute(world, AUREN, partial.id, decide(world, partial).id)

    pending = world.creatures.demands[demand.id]
    assert pending.stage == "open"
    assert pending.food_received == partial.food
    assert pending.settled_by_ref is None
    assert world.economy.stocks[SELLER_STOCK].goods["food"] == before - partial.food

    remaining = next(item for item in tribute_options(world, AUREN)
                     if item.stock_id == SELLER_STOCK and item.food == demand.food - partial.food)
    settled = offer_creature_tribute(world, AUREN, remaining.id, decide(world, remaining).id)
    assert settled.stage == "satisfied"
    assert settled.food_received == demand.food
    assert settled.settled_by_ref == AUREN.to_dict()


async def test_an_unanswered_demand_only_closes_the_river_by_explicit_decision():
    world = await crossed_world()
    request = pick(world, "request", route_id=ROUTE_ID)
    execute_creature_option(world, DRAKE_ID, request.id, decide(world, request).id)
    demand = next(iter(world.creatures.demands.values()))

    # An institution without the mandate or without its own food offers nothing.
    office = world.authority.offices["office:polity:auren"]
    world.authority.offices[office.id] = office.model_copy(update={"ends_day": 0})
    assert not tribute_options(world, AUREN)
    world.authority.offices[office.id] = office

    # The world keeps running past the deadline; nothing closes by itself.
    engine = MedievalSimulator(world)
    for _ in range(40):
        if world.clock.absolute_day >= demand.due_day:
            break
        await engine.step()
    assert world.clock.absolute_day >= demand.due_day
    assert world.map.routes[ROUTE_ID].enabled, "a deadline closes nothing by itself"
    assert world.creatures.demands[demand.id].stage == "open"

    restrict = pick(world, "restrict", route_id=ROUTE_ID)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale|unknown"):
        execute_creature_option(world, DRAKE_ID, restrict.id + ":forged", decide(world, restrict).id)
    assert world_snapshot(world)["event_count"] == before["event_count"] + 1
    assert world.map.routes[ROUTE_ID].enabled

    # A legitimate bilateral shipment is already on its way to the crossing.
    buy_across_the_river(world)
    engine = MedievalSimulator(world)
    await engine.step()
    await engine.step()
    pending = sum(item.quantity for item in world.economy.parcels.values())
    assert pending > 0, "there must be real cargo waiting at the river"
    restrict = pick(world, "restrict", route_id=ROUTE_ID)
    execute_creature_option(world, DRAKE_ID, restrict.id, decide(world, restrict).id)

    assert world.map.routes[ROUTE_ID].enabled is False
    assert world.creatures.demands[demand.id].stage == "expired"
    assert world.creatures.creatures[DRAKE_ID].restricted_route_id == ROUTE_ID
    # Real institutional aid now competes for the same calendar: an unrelated
    # obligation due at the crossing can pause the clock there before the
    # bilateral cargo itself reaches the river. Keep stepping (bounded) until
    # it does, verifying on every tick that the held cargo never moves.
    engine = MedievalSimulator(world)
    for _ in range(10):
        await engine.step()
        assert sum(item.quantity for item in world.economy.parcels.values()) == pending, "held cargo is preserved"
        if any(item.event_type == "cargo_delayed" for item in world.events):
            break
    assert any(item.event_type == "cargo_delayed" for item in world.events)

    withdraw = pick(world, "withdraw", route_id=ROUTE_ID)
    execute_creature_option(world, DRAKE_ID, withdraw.id, decide(world, withdraw).id)
    assert world.map.routes[ROUTE_ID].enabled is True
    assert world.creatures.creatures[DRAKE_ID].restricted_route_id is None

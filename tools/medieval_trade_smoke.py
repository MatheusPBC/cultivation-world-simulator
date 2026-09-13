"""Prepared bilateral purchase/blockade/recovery; not an autonomous-policy smoke."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classes.event import FactKind
from src.classes.state_delta import StateDelta
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.markets import purchase
from src.sim.medieval.persistence import load_world, save_world, world_snapshot

ROAD = "road-campomanso-pedraclara"


def set_passage(world, enabled):
    route = world.map.routes[ROAD]
    event = record_event(world, "prepared_passage_change", "Disponibilidade da passagem alterada no cenário preparado.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(StateDelta(owner_kind="route", owner_id=ROAD, aspect="enabled",
                                            before=str(route.enabled), after=str(enabled)),))
    route.update_runtime(enabled=enabled)
    return event


def food_total(world):
    return (sum(s.goods.get("food", 0) for s in world.economy.stocks.values()) +
            sum(p.quantity for p in world.economy.parcels.values()
                if world.economy.freight_orders[p.order_id].resource_id == "food"))


def assert_conservation(world, initial_food, initial_money):
    consumed = sum(int(d.before) - int(d.after) for e in world.events
                   if e.event_type in {"subsistence_resolved", "household_purchase_completed"}
                   for d in e.deltas if d.owner_kind == "stock" and d.aspect == "food")
    if food_total(world) + consumed != initial_food:
        raise AssertionError("stock + cargo + consumed food is not conserved")
    if sum(a.balance for a in world.economy.accounts.values()) != initial_money:
        raise AssertionError("money is not conserved")


async def run(seed: int, output: Path) -> dict:
    world = create_medieval_world(seed)
    # Prepared initial conditions are not commands available to the observer.
    world.economy.facilities.clear()
    destination = world.economy.stocks["stock:portovelho"]
    world.economy.stocks[destination.id] = destination.model_copy(update={"goods": {"food": 0}})
    initial_food = food_total(world)
    initial_money = sum(a.balance for a in world.economy.accounts.values())
    closure = set_passage(world, False)
    values = {"source_id": "stock:campomanso", "destination_id": "stock:portovelho", "resource_id": "food",
              "quantity": 2400, "unit_price": 4, "quote_day": 0, "route_ids": [ROAD, "river-pedraclara-portovelho"],
              "seller_account_id": "treasury:auren", "buyer_account_id": "treasury:valedouro"}
    decisions = []
    for action, owner in (("buy", "valedouro"), ("sell", "auren")):
        decision = record_event(world, f"{action}_decided", "Oferta aceita pela política preparada do cenário.",
                                 fact_kind=FactKind.DECISION,
                                 decision={**values, "action": action, "actor_ref": {"kind": "polity", "id": owner}})
        decisions.append(decision.id)
    order = purchase(world, *decisions)
    save_world(world, output)
    engine = MedievalSimulator(world, save_path=output)
    while world.clock.absolute_day < 30:
        await engine.step()
        assert_conservation(world, initial_food, initial_money)
    blocked = world.economy.needs["portovelho"]
    if blocked.missing_food != 2000 or world.economy.freight_orders[order.id].delivered_quantity:
        raise AssertionError("blockade did not interrupt delivery and subsistence")
    delays = {e.id for e in world.events if e.event_type == "cargo_delayed" and
              closure.id in {link.cause_event_id for link in e.causal_links}}
    shortage = next(e for e in world.events if e.id == blocked.last_event_id)
    if not delays.intersection(link.cause_event_id for link in shortage.causal_links):
        raise AssertionError("shortage is not linked to the blocked cargo")
    resumed = load_world(output)
    if world_snapshot(resumed) != world_snapshot(world) or resumed.events != world.events:
        raise AssertionError("mid-blockade save/load changed state or history")
    world = resumed
    set_passage(world, True)
    engine = MedievalSimulator(world, save_path=output)
    while world.clock.absolute_day < 60:
        await engine.step()
        assert_conservation(world, initial_food, initial_money)
    recovered = world.economy.needs["portovelho"]
    if recovered.missing_food != 0 or recovered.health <= blocked.health or world.economy.parcels:
        raise AssertionError("delivery did not restore subsistence")
    loaded = load_world(output)
    if world_snapshot(loaded) != world_snapshot(world) or loaded.events != world.events:
        raise AssertionError("final save/load changed state or history")
    return {"scenario": "prepared-prepaid-trade-blockade", "seed": seed, "day": world.clock.absolute_day,
            "characters": len(world.society.characters), "population": world.society.total_population,
            "events": len(world.events), "delivered": world.economy.freight_orders[order.id].delivered_quantity,
            "missing_food_during_blockade": blocked.missing_food, "missing_food_after_delivery": recovered.missing_food,
            "health_during_blockade": blocked.health, "health_after_delivery": recovered.health,
            "buyer_balance": world.economy.accounts["treasury:valedouro"].balance,
            "seller_balance": world.economy.accounts["treasury:auren"].balance,
            "food_conserved": True, "save_load_equivalent": True, "real_ai_calls": 0, "save": str(output.resolve())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.seed, args.output)), ensure_ascii=False, indent=2))

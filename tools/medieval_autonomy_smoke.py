"""Natural autonomous supply smoke, with elapsed-time and conservation evidence."""

import argparse
import asyncio
from collections import Counter
import cProfile
import json
from pathlib import Path
import pstats
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.persistence import save_world, load_world, world_snapshot


def food_total(world):
    return sum(s.goods.get("food", 0) for s in world.economy.stocks.values()) + sum(
        p.quantity for p in world.economy.parcels.values()
        if world.economy.freight_orders[p.order_id].resource_id == "food")


def resource_totals(world):
    totals = {rid: sum(s.goods.get(rid, 0) for s in world.economy.stocks.values()) for rid in world.economy.resources}
    for parcel in world.economy.parcels.values():
        totals[world.economy.freight_orders[parcel.order_id].resource_id] += parcel.quantity
    return totals


async def run(seed, days, output, profile=False):
    world = create_medieval_world(seed)
    initial_resources = resource_totals(world)
    initial_money = sum(a.balance for a in world.economy.accounts.values())
    elapsed, jumps, boundary, net_resources = time.perf_counter(), 0, 0, Counter()
    while world.clock.absolute_day < days:
        start = len(world.events)
        await MedievalSimulator(world).step()
        jumps += 1
        for event in world.events[start:]:
            if event.event_type in {"production_completed", "production_limited", "subsistence_resolved", "household_purchase_completed", "expansion_progressed", "research_progressed"}:
                for delta in event.deltas:
                    if delta.owner_kind == "stock":
                        net_resources[delta.aspect] += int(delta.after) - int(delta.before)
        assert resource_totals(world) == {rid: amount + net_resources[rid] for rid, amount in initial_resources.items()}, "unaccounted resource creation/loss"
        assert sum(a.balance for a in world.economy.accounts.values()) == initial_money
        if world.clock.absolute_day // 30 > boundary:
            boundary = world.clock.absolute_day // 30
            print(json.dumps({"day": world.clock.absolute_day, "events": len(world.events),
                              "orders": len(world.economy.freight_orders), "elapsed_s": round(time.perf_counter()-elapsed, 2)}), flush=True)
    profiler = cProfile.Profile()
    if profile:
        profiler.enable()
    save_world(world, output)
    if profile:
        profiler.disable()
        pstats.Stats(profiler).sort_stats("cumtime").print_stats(15)
    resumed = load_world(output)
    assert world_snapshot(world) == world_snapshot(resumed) and world.events == resumed.events
    # Prove continuation, not only equality immediately after deserialization.
    await MedievalSimulator(world).step()
    await MedievalSimulator(resumed).step()
    assert world_snapshot(world) == world_snapshot(resumed) and world.events == resumed.events
    return {"scenario": "natural-autonomous-supply", "seed": seed, "saved_day": days,
            "continuation_day": world.clock.absolute_day, "jumps": jumps, "events": len(world.events),
            "money_total": initial_money, "orders": len(world.economy.freight_orders),
            "health": {key: n.health for key, n in world.economy.needs.items()},
            "balances": {key: a.balance for key, a in world.economy.accounts.items() if a.owner_ref.kind == "polity"},
            "food_conserved": True, "all_resources_accounted": True, "save_load_equivalent": True, "real_ai_calls": 0,
            "policy": world.config.decision_policy, "elapsed_s": round(time.perf_counter()-elapsed, 2),
            "save": str(output.resolve())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    if args.days <= 0 or args.days % 30:
        parser.error("days must be a positive multiple of 30")
    print(json.dumps(asyncio.run(run(args.seed, args.days, args.output, args.profile)), ensure_ascii=False, indent=2))

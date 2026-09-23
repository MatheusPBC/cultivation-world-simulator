"""Run one bounded provider-backed campaign-supply probe.

The provider is consulted only for the already-enumerated dispatch affordance.
After that one turn, ordinary dated logistics resolve delivery (or lapse) with
AI disabled.  The script is an observation tool: it does not invent a
campaign planner, route, quantity, or combat result.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.campaign_supply import review_campaign_supplies
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.force import raise_detachment, raise_options
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


OWNER = EntityRef("polity", "auren")
HOME = "campomanso"
TARGET = "salgueiro"
DEFAULT_OUTPUT = Path("/tmp/medieval-campaign-supply-73.mws")


def _decision(world, option):
    return record_event(
        world,
        "campaign_supply_probe_decided",
        "Decisão factual de levantamento da coluna para o probe de abastecimento.",
        fact_kind=FactKind.DECISION,
        decision=option.decision(),
    )


def _occupied_campaign_world(seed: int):
    """Raise one real column and resolve its material march to the target."""
    world = create_medieval_world(seed)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values()
                 if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 20})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    option = next(item for item in raise_options(world, OWNER)
                  if item.destination_id == TARGET)
    detachment = raise_detachment(world, OWNER, option.id, _decision(world, option).id)
    while world.society.detachments[detachment.id].stage == "marching":
        _tick_without_provider(world)
    detachment = world.society.detachments[detachment.id]
    if detachment.stage != "present":
        raise RuntimeError("campaign supply probe did not produce a present column")
    return world, detachment


def _tick_without_provider(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


async def run(seed: int = 73, output: Path = DEFAULT_OUTPUT) -> dict:
    """Consult the provider once, then resolve the physical chain locally."""
    if not ai_decider.provider_available():
        raise RuntimeError("real provider is not configured or is disabled in this runtime")

    world, detachment = _occupied_campaign_world(seed)
    notices = tuple(world.knowledge.campaign_supply_notices.values())
    notice = next((item for item in notices if item.detachment_id == detachment.id
                   and item.state == "open"), None)
    if notice is None:
        raise RuntimeError("campaign supply probe did not reach the canonical low-baggage warning")

    # This is the complete provider budget for the probe.  The later logistics
    # ticks explicitly run with AI disabled, so they cannot consume a second
    # call or choose a material action.
    world.config = world.config.model_copy(update={
        "ai_enabled": True,
        "ai_calls_per_step": 1,
        "ai_max_calls": 1,
    })
    review_day = world.clock.absolute_day + 1
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    await review_campaign_supplies(world, due)
    calls_after_review = ai_decider.spent_calls(world)
    if calls_after_review != 1:
        raise RuntimeError("campaign supply probe did not consume exactly one provider call")

    notice = world.knowledge.campaign_supply_notices[notice.id]
    selected_dispatch = notice.state == "dispatched"
    # NO_ACTION is a valid result.  It leaves no freight and the same dated
    # force law eventually lapses the notice/column; no fallback is inserted.
    world.config = world.config.model_copy(update={"ai_enabled": False})
    ticks = 0
    while notice.state not in {"fulfilled", "lapsed"} and ticks < 40:
        _tick_without_provider(world)
        ticks += 1
        notice = world.knowledge.campaign_supply_notices[notice.id]
    if notice.state not in {"fulfilled", "lapsed"}:
        raise RuntimeError("campaign supply probe did not reach fulfill or lapse")
    if not selected_dispatch and world.economy.freight_orders:
        raise RuntimeError("NO_ACTION unexpectedly opened freight")
    if ai_decider.spent_calls(world) != 1:
        raise RuntimeError("deterministic logistics consumed an unexpected provider call")

    validate_history(world.events, world.clock.absolute_day)
    save_world(world, output)
    restored = load_world(output)
    if world_snapshot(restored) != world_snapshot(world) or restored.events != world.events:
        raise RuntimeError("campaign supply probe save/load changed the final state")
    return {
        "seed": seed,
        "save": str(Path(output).resolve()),
        "detachment_id": detachment.id,
        "warning_event_id": notice.event_id,
        "review_day": review_day,
        "selected_id": next((event.decision.get("selected_affordance_id")
                              for event in world.events
                              if event.event_type == "campaign_supply_decided"), None),
        "no_action": not selected_dispatch,
        "notice_state": notice.state,
        "freight_count": len(world.economy.freight_orders),
        "ticks_after_review": ticks,
        "real_ai_calls": ai_decider.spent_calls(world),
        "audit": {"ok": True, "save_load_equivalent": True},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.seed, args.output)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

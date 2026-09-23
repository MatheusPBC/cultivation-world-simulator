"""Run one bounded provider-backed medieval campaign response chain.

This is an operational probe, not a second campaign runtime.  The provider
can select an existing adoption affordance and, on the next scheduled turn,
an existing material force affordance.  ``NO_ACTION`` is preserved as a
decline; no deterministic choice is substituted.
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

from src.classes.causal_origin import CausalOrigin
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import validate_history
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.strategy_response import review_strategy_responses_with_provider

from tools.medieval_campaign_provider_probe import _occupied_campaign_world


DEFAULT_OUTPUT = Path("/tmp/medieval-campaign-material-73.mws")


def _tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def _basic_audit(world):
    validate_history(world.events, world.clock.absolute_day)
    interpretation_material = [
        event.id for event in world.events
        if event.causal_origin is CausalOrigin.LLM_INTERPRETATION and event.deltas
    ]
    if interpretation_material:
        raise RuntimeError("provider interpretation receipt unexpectedly carries a delta")
    return {
        "ok": True,
        "events": len(world.events),
        "interpretation_material_events": interpretation_material,
    }


async def run(seed: int = 73, output: Path = DEFAULT_OUTPUT) -> dict:
    """Execute at most two real-provider calls and persist the resulting chain."""
    if not ai_decider.provider_available():
        raise RuntimeError("real provider is not configured or is disabled in this runtime")

    world, _, _ = _occupied_campaign_world(seed)
    world.config = world.config.model_copy(update={
        "ai_enabled": True,
        "ai_calls_per_step": 2,
        "ai_max_calls": 2,
    })

    before_receipts = len([event for event in world.events
                           if event.event_type in ai_decider.RECEIPT_EVENTS])
    adoption_changed = await review_strategy_responses_with_provider(
        world, allow_adoptions=True
    )
    receipts = [event for event in world.events
                if event.event_type in ai_decider.RECEIPT_EVENTS]
    adoption_receipt = receipts[before_receipts:][-1] if len(receipts) > before_receipts else None
    plan = next(iter(world.strategy.plans.values()), None)
    material_changed = False
    advanced_day = False
    material_receipt = None
    if plan is not None and plan.stage == "adopted":
        due = _tick(world)
        advanced_day = True
        before_receipts = len([event for event in world.events
                               if event.event_type in ai_decider.RECEIPT_EVENTS])
        material_changed = await review_strategy_responses_with_provider(world, due)
        receipts = [event for event in world.events
                    if event.event_type in ai_decider.RECEIPT_EVENTS]
        material_receipt = receipts[before_receipts:][-1] if len(receipts) > before_receipts else None

    audit = _basic_audit(world)
    save_world(world, output)
    restored = load_world(output)
    save_load_equivalent = (
        world_snapshot(restored) == world_snapshot(world)
        and restored.events == world.events
    )
    if not save_load_equivalent:
        raise RuntimeError("campaign material probe save/load changed the final state")
    audit["save_load_equivalent"] = True

    force_decisions = [
        event for event in world.events
        if event.event_type == "strategy_defense_force_decided"
    ]
    detachments = [
        item for item in world.society.detachments.values()
        if item.owner_ref.id == "auren"
    ]
    return {
        "seed": seed,
        "save": str(Path(output).resolve()),
        "adoption_changed": adoption_changed,
        "adopted": plan is not None,
        "advanced_day": advanced_day,
        "material_changed": material_changed,
        "no_action": any(receipt is not None and receipt.event_type == ai_decider.DECLINED_EVENT
                          for receipt in (adoption_receipt, material_receipt)),
        "adoption_no_action": (adoption_receipt is not None
                               and adoption_receipt.event_type == ai_decider.DECLINED_EVENT),
        "material_no_action": (material_receipt is not None
                                and material_receipt.event_type == ai_decider.DECLINED_EVENT),
        "adoption_receipt_type": adoption_receipt.event_type if adoption_receipt else None,
        "material_receipt_type": material_receipt.event_type if material_receipt else None,
        "force_decision_count": len(force_decisions),
        "detachment_count": len(detachments),
        "real_ai_calls": ai_decider.spent_calls(world),
        "audit": audit,
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

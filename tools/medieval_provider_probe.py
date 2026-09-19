"""Small operational probe for the real medieval decision boundary.

This is intentionally narrower than ``medieval_autonomy_smoke``.  It does not
advance a month and it never executes the selected affordance: it asks the
configured provider to choose one current, engine-enumerated ID (or
``NO_ACTION``), then verifies the resulting interpretation receipt is an
occurrence with no delta.  Material execution remains the owner's job and is
covered by the focused decision/owner tests.

The command fails explicitly when no real provider is configured.  A
deterministic government profile is never accepted as a substitute.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.actor_dossier import build_actor_dossier
from src.sim.medieval.concurrent_civil_decision import concurrent_civil_options
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.route_intelligence import refresh_route_reports


def _actor_and_options(world):
    refresh_reports(world)
    refresh_route_reports(world)
    for identity in sorted(world.society.polities):
        actor = EntityRef("polity", identity)
        options = tuple(concurrent_civil_options(world, actor))
        if options:
            return actor, options
    raise RuntimeError("real provider probe found no current institutional affordance")


async def run(seed: int = 73, *, calls_per_step: int = 1) -> dict:
    """Run one real-provider choice without executing its material owner."""
    if type(calls_per_step) is not int or calls_per_step <= 0:
        raise ValueError("calls_per_step must be a positive integer")
    if not ai_decider.provider_available():
        raise RuntimeError("real provider is not configured or is disabled in this runtime")

    world = create_medieval_world(seed, bootstrap_household_income=True)
    world.config = world.config.model_copy(update={
        "ai_enabled": True,
        "ai_calls_per_step": calls_per_step,
        "ai_max_calls": calls_per_step,
    })
    actor, options = _actor_and_options(world)
    option_ids = {option.id for option in options}
    choices = [{"id": option.id, "label": f"Selecionar {option.id}"} for option in options]
    selected = await ai_decider.select_option(
        world, actor, {"probe": True, "dossier": build_actor_dossier(world, actor)}, choices
    )
    receipts = [event for event in world.events if event.event_type in ai_decider.RECEIPT_EVENTS]
    if not receipts:
        raise RuntimeError("provider probe produced no decision receipt")
    receipt = receipts[-1]
    if receipt.deltas:
        raise RuntimeError("provider interpretation receipt unexpectedly carries a delta")
    if receipt.causal_origin is not CausalOrigin.LLM_INTERPRETATION:
        raise RuntimeError("provider receipt has the wrong causal origin")
    if selected not in option_ids and selected != ai_decider.NO_ACTION:
        raise RuntimeError("provider returned an ID outside the current affordance set")
    return {
        "seed": seed,
        "actor": actor.to_dict(),
        "affordance_count": len(options),
        "selected_id": selected,
        "no_action": selected == ai_decider.NO_ACTION,
        "receipt_type": receipt.event_type,
        "receipt_has_delta": bool(receipt.deltas),
        "receipt_causal_origin": receipt.causal_origin.value,
        "real_ai_calls": ai_decider.spent_calls(world),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--ai-calls-per-step", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.seed, calls_per_step=args.ai_calls_per_step)),
                     ensure_ascii=False, indent=2), flush=True)

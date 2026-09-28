"""Narrow real-provider probe for the medieval defense campaign boundary.

The probe builds the factual occupied-settlement fixture, asks the configured
provider to choose only from the current ``defense_adoption_options`` for
AUREN, and never executes the selected adoption or any material response.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.strategy_response import _adoption_situation, defense_adoption_options


OWNER = EntityRef("polity", "auren")
OCCUPIER = EntityRef("polity", "escarlia")
SOURCE = "campomanso"
TARGET = "pedraclara"


def _occupied_campaign_world(seed: int):
    world = create_medieval_world(seed)
    group = next(item for item in world.society.population.values()
                 if item.settlement_id == SOURCE and item.occupation == "farmer"
                 and item.count >= 20)
    soldiers_id = f"pop:{SOURCE}:{group.people}:soldier"
    soldiers = world.society.population.get(soldiers_id)
    if soldiers is None:
        raise RuntimeError("campaign probe requires an existing soldier cohort")
    assignment = record_event(
        world, "campaign_probe_assignment", "Vinte moradores foram designados soldados na premissa do cenário.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "campaign_provider_fixture",
            "source_refs": [{"kind": "scenario", "id": "campaign_provider_fixture"},
                            {"kind": "population_group", "id": group.id}],
            "observed_day": world.clock.absolute_day,
        }},
        deltas=(_delta("population_group", group.id, "count", group.count, group.count - 20),
                _delta("population_group", soldiers_id, "count", soldiers.count,
                       soldiers.count + 20)),
    )
    world.society.population[group.id] = group.model_copy(
        update={"count": group.count - 20, "last_event_id": assignment.id})
    world.society.population[soldiers_id] = soldiers.model_copy(
        update={"count": soldiers.count + 20, "last_event_id": assignment.id})
    occupation = record_event(
        world, "campaign_probe_occupation", "Ocupacao factual observavel para o probe.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "campaign_provider_fixture",
            "source_refs": [{"kind": "scenario", "id": "campaign_provider_fixture"},
                            {"kind": "settlement", "id": TARGET}],
            "observed_day": world.clock.absolute_day,
        }},
        deltas=(_delta("settlement", TARGET, "occupier_id", None, OCCUPIER.id),))
    world.society.set_occupation(TARGET, OCCUPIER.id)
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    report = world.knowledge.settlement_report(OWNER, TARGET)
    if report is None or report.occupier_id != OCCUPIER.id:
        raise RuntimeError("campaign probe fixture did not produce the occupied report")
    return world, occupation.id, report


async def run(seed: int = 73) -> dict:
    """Ask the real provider for one adoption choice without executing it."""
    if not ai_decider.provider_available():
        raise RuntimeError("real provider is not configured or is disabled in this runtime")

    world, occupation_id, report = _occupied_campaign_world(seed)
    world.config = world.config.model_copy(update={
        "ai_enabled": True,
        "ai_calls_per_step": 1,
        "ai_max_calls": 1,
    })
    options = tuple(defense_adoption_options(world, OWNER))
    if not options:
        raise RuntimeError("campaign provider probe found no current defense adoption affordance")
    option_ids = {option.id for option in options}
    selected = await ai_decider.select_option(
        world,
        OWNER,
        _adoption_situation(world, OWNER, options),
        [{"id": option.id, "label": "Adotar a resposta defensiva observada."}
         for option in options],
        causes=(occupation_id, report.event_id),
    )
    receipts = [event for event in world.events
                if event.event_type in ai_decider.RECEIPT_EVENTS]
    if not receipts:
        raise RuntimeError("campaign provider probe produced no decision receipt")
    receipt = receipts[-1]
    if receipt.deltas:
        raise RuntimeError("campaign interpretation receipt unexpectedly carries a delta")
    if receipt.causal_origin is not CausalOrigin.LLM_INTERPRETATION:
        raise RuntimeError("campaign receipt has the wrong causal origin")
    if selected not in option_ids and selected != ai_decider.NO_ACTION:
        raise RuntimeError("provider returned an ID outside the current affordance set")
    if ai_decider.spent_calls(world) != 1:
        raise RuntimeError("campaign provider probe did not consume exactly one call")
    return {
        "seed": seed,
        "actor": OWNER.to_dict(),
        "affordance_count": len(options),
        "selected_id": selected,
        "no_action": selected == ai_decider.NO_ACTION,
        "receipt_type": receipt.event_type,
        "receipt_causal_origin": receipt.causal_origin.value,
        "receipt_has_delta": bool(receipt.deltas),
        "real_ai_calls": ai_decider.spent_calls(world),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=73)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.seed)), ensure_ascii=False, indent=2), flush=True)

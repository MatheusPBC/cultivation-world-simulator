"""Prepare one provider menu with a current food request and defense choice.

The occupied settlement is an explicit scenario-bootstrap premise. The food
shortfall and actor's report come from the source save; neither is invented by
this tool. It performs no choice, external provider call or material campaign.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.institutional_decision_turn import _by_id
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


def build(source: Path, output: Path, actor_id: str, settlement_id: str,
          occupier_id: str) -> dict:
    source = source.resolve()
    output = output.resolve()
    if source == output or output.exists():
        raise ValueError("output must be a new path distinct from the source save")
    source_hash = sha256(source.read_bytes()).hexdigest()
    world = load_world(source)
    actor = EntityRef("polity", actor_id)
    settlement = world.society.settlements[settlement_id]
    if (settlement.administrator_id != actor_id or settlement.occupier_id is not None
            or occupier_id == actor_id or occupier_id not in world.society.polities):
        raise ValueError("scenario requires an unoccupied own settlement and a foreign occupier")

    record_event(
        world, "corpus_setup_occupation", "Ocupação factual inicial do cenário controlado.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap",
            "domain": "provider_competing_priorities_fixture",
            "source_refs": [{"kind": "scenario", "id": "provider_competing_priorities_fixture"},
                            {"kind": "settlement", "id": settlement_id}],
            "observed_day": world.clock.absolute_day,
        }},
        deltas=(_delta("settlement", settlement_id, "occupier_id", None, occupier_id),),
    )
    world.society.set_occupation(settlement_id, occupier_id)
    refresh_settlement_reports(world)
    options = _by_id(world, actor, monthly_adapters())
    food = [option.id for adapter, option in options.values()
            if adapter.name == "aid_request" and option.requester_settlement_id == settlement_id]
    defense = [option.id for adapter, option in options.values()
               if adapter.name == "defense_adoption" and option.settlement_id == settlement_id]
    if not food or not defense:
        raise ValueError("one composed turn must offer both food aid and defense")
    report = world.knowledge.settlement_report(actor, settlement_id)
    if report is None or report.observed_day != world.clock.absolute_day or report.missing_food <= 0:
        raise ValueError("food pressure is not in the actor's current report")
    validate_history(world.events, world.clock.absolute_day)
    world_snapshot(world)
    if sha256(source.read_bytes()).hexdigest() != source_hash:
        raise ValueError("source save changed while preparing fixture")
    save_world(world, output)
    restored = load_world(output)
    if world_snapshot(restored) != world_snapshot(world) or restored.events != world.events:
        raise ValueError("fixture did not survive save/load")
    return {
        "source_save": str(source),
        "source_sha256_unchanged": source_hash,
        "output_save": str(output),
        "actor_ref": actor.to_dict(),
        "day": world.clock.absolute_day,
        "missing_food_observed": report.missing_food,
        "food_affordance_ids": food,
        "defense_affordance_ids": defense,
        "offered_count": len(options),
        "real_provider_calls": 0,
        "save_load_equivalent": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--settlement", required=True)
    parser.add_argument("--occupier", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.actor, args.settlement,
                           args.occupier), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

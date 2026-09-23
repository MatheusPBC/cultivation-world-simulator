"""Run one bounded provider-backed research-to-production chain.

This is an operational proof over existing research and expansion owners, not
a technology planner.  The provider is offered only current, engine-composed
affordances: first an authored metallurgy experiment and, after its factual
discovery, one of that knowledge's currently material applications.  It never
authors a technology, target, cost, workforce allocation, or output.
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
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.economy import monthly_workforce, produce_monthly
from src.sim.medieval.events import validate_history
from src.sim.medieval.expansion import expansion_adapters, expansion_options, progress_expansions
from src.sim.medieval.institutional_decision_turn import DiscretionaryAdapter, review_institutional_decision_turn
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import progress_research
from src.sim.medieval.research_policy import (
    _research_causes,
    execute_research_option,
    research_adapters,
    research_options,
)
from src.systems.time import WorldClock


OWNER = EntityRef("polity", "escarlia")
TECHNOLOGY = "metallurgy"
DEFAULT_OUTPUT = Path("/tmp/medieval-technology-material-73.mws")


def _research_for_probe(world, actor):
    """Keep only existing metallurgy affordances in the controlled fixture."""
    return tuple(option for option in research_options(world, actor)
                 if option.technology_id == TECHNOLOGY)


def _application_for_probe(world, actor):
    """Keep only existing applications which require the discovered technology."""
    return tuple(option for option in expansion_options(world, actor)
                 if world.economy.expansion_blueprints[option.blueprint_id].required_technology_id == TECHNOLOGY)


def _adapter_for(options_fn, base: DiscretionaryAdapter) -> DiscretionaryAdapter:
    """Reuse a vertical's executor exactly; narrow only this probe's menu."""
    return DiscretionaryAdapter(
        name=base.name,
        family=base.family,
        options_fn=options_fn,
        label_fn=base.label_fn,
        causes_fn=base.causes_fn,
        execute_fn=base.execute_fn,
        claim_fn=base.claim_fn,
        situation_fn=base.situation_fn,
    )


def _research_adapter():
    return _adapter_for(_research_for_probe, research_adapters()[0])


def _application_adapter():
    return _adapter_for(_application_for_probe, expansion_adapters()[0])


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


def _advance_research(world, project):
    """Let normal monthly research work until it completes or is blocked."""
    ticks = 0
    while project.stage not in {"completed", "superseded", "blocked"} and ticks < 12:
        world.clock = WorldClock(world.clock.absolute_day + 30)
        progress_research(world, monthly_workforce(world))
        project = world.research.projects[project.id]
        ticks += 1
    return project, ticks


def _advance_application(world, project):
    """Let the expansion owner perform paid monthly construction work."""
    ticks = 0
    while project.stage not in {"completed", "blocked"} and ticks < 12:
        world.clock = WorldClock(world.clock.absolute_day + 30)
        progress_expansions(world, monthly_workforce(world))
        project = world.economy.expansions[project.id]
        ticks += 1
    return project, ticks


def _selected_id(events, event_type):
    return next((event.decision.get("selected_affordance_id") for event in events
                 if event.event_type == event_type), None)


async def run(seed: int = 73, output: Path = DEFAULT_OUTPUT) -> dict:
    """Use at most two provider decisions, then resolve ordinary paid work."""
    if not ai_decider.provider_available():
        raise RuntimeError("real provider is not configured or is disabled in this runtime")

    world = create_medieval_world(seed)
    world.config = world.config.model_copy(update={
        "ai_enabled": True,
        "ai_calls_per_step": 2,
        "ai_max_calls": 2,
    })

    research_options_before = {option.id for option in _research_for_probe(world, OWNER)}
    if not research_options_before:
        raise RuntimeError("technology probe fixture has no current research affordance")
    await review_institutional_decision_turn(world, OWNER, (_research_adapter(),))
    research_selected_id = _selected_id(world.events, "institutional_decision_turn_decided")
    project = next((item for item in world.research.projects.values()
                    if item.owner_ref == OWNER and item.technology_id == TECHNOLOGY), None)

    application_selected_id = None
    application_project = None
    research_ticks = 0
    application_ticks = 0
    production_delta = {}
    application_options_before = set()
    if project is not None:
        project, research_ticks = _advance_research(world, project)
        if project.stage == "completed" and world.knowledge.knows(OWNER, TECHNOLOGY):
            # Expansion menus intentionally respond to actual production
            # pressure.  This normal production cycle creates that reading;
            # it does not create knowledge or construction capacity.
            produce_monthly(world)
            application_options_before = {option.id for option in _application_for_probe(world, OWNER)}
            if application_options_before:
                before = dict(world.economy.stocks["stock:ferroalto"].goods)
                existing_project_ids = set(world.economy.expansions)
                await review_institutional_decision_turn(world, OWNER, (_application_adapter(),))
                application_selected_id = _selected_id(
                    [event for event in world.events
                     if event.day == world.clock.absolute_day],
                    "institutional_decision_turn_decided",
                )
                application_project = next((item for item in world.economy.expansions.values()
                                            if item.id not in existing_project_ids), None)
                if application_project is not None:
                    application_project, application_ticks = _advance_application(world, application_project)
                    if application_project.stage == "completed":
                        produce_monthly(world)
                        after = world.economy.stocks["stock:ferroalto"].goods
                        blueprint = world.economy.expansion_blueprints[application_project.blueprint_id]
                        target_recipe = blueprint.additional_recipe_id or blueprint.to_recipe_id
                        if target_recipe is None:
                            raise RuntimeError("technology application did not name a resulting recipe")
                        production_delta = {
                            resource: after.get(resource, 0) - before.get(resource, 0)
                            for resource in sorted(world.economy.recipes[target_recipe].outputs)
                        }

    audit = _basic_audit(world)
    save_world(world, output)
    restored = load_world(output)
    if world_snapshot(restored) != world_snapshot(world) or restored.events != world.events:
        raise RuntimeError("technology material probe save/load changed the final state")
    audit["save_load_equivalent"] = True
    if research_selected_id is not None and research_selected_id not in research_options_before:
        raise RuntimeError("research decision selected an ID outside its current engine menu")
    if application_selected_id is not None and application_selected_id not in application_options_before:
        raise RuntimeError("application decision selected an ID outside its current engine menu")
    return {
        "seed": seed,
        "save": str(Path(output).resolve()),
        "research_selected_id": research_selected_id,
        "research_no_action": project is None,
        "research_stage": project.stage if project is not None else None,
        "research_ticks": research_ticks,
        "knowledge_discovered": world.knowledge.knows(OWNER, TECHNOLOGY),
        "application_selected_id": application_selected_id,
        "application_no_action": bool(application_options_before) and application_project is None,
        "application_stage": application_project.stage if application_project is not None else None,
        "application_ticks": application_ticks,
        "production_delta": production_delta,
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

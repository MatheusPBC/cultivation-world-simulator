#!/usr/bin/env python3
"""Provider-free long smoke for the institutional aid lifecycle.

This is a harness, not a simulation path: each month goes through the normal
``Simulator.step`` and only the initial canonical city state differs between
the natural and pressured scenarios.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _world_factory(*, pressured: bool, seed: int):
    from src.classes.age import Age
    from src.classes.core.avatar import Avatar, Gender
    from src.classes.core.dynasty import Dynasty
    from src.classes.environment.city_state import CityGovernance
    from src.classes.environment.region import CityRegion
    from src.classes.regional_economy import RegionalEconomyState
    from src.classes.core.world import World
    from src.run.load_map import load_cultivation_world_map
    from src.systems.cultivation import Realm
    from src.systems.institution_bootstrap import bootstrap_institutional_authority
    from src.systems.time import Month, Year, create_month_stamp

    def factory(_index: int, world_seed: int):
        world = World(
            map=load_cultivation_world_map("classic"),
            month_stamp=create_month_stamp(Year(100), Month.JANUARY),
        )
        emperor = Avatar(
            world=world,
            name="Smoke Emperor",
            id=f"smoke-emperor-{world_seed}",
            birth_month_stamp=create_month_stamp(Year(70), Month.JANUARY),
            age=Age(30, Realm.Qi_Refinement),
            gender=Gender.MALE,
        )
        world.avatar_manager.register_avatar(emperor)
        world.dynasty = Dynasty(1, "Smoke Dynasty", "", current_emperor_id=emperor.id)
        world.run_config_snapshot = {
            "map_id": "classic", "test_mode": True, "provider": "test",
            "npc_awakening_rate_per_month": 0.0,
            "economy_interpreter_llm_budget_per_month": 0,
            "institutional_aid_fulfillment_llm_budget_per_month": 0,
            "institutional_smoke_seed": seed,
            "institutional_smoke_scenario": "pressured" if pressured else "natural",
        }
        source = world.map.regions[302]
        destination = world.map.regions[305]
        if not isinstance(source, CityRegion) or not isinstance(destination, CityRegion):
            raise RuntimeError("classic map lacks institutional smoke cities")
        if not world.map.get_routes_between(302, 305):
            raise RuntimeError("classic institutional smoke cities are not connected")
        source.city_state.governance = CityGovernance("dynasty", "1", 1.0)
        destination.city_state.governance = CityGovernance("dynasty", "1", 1.0)
        if pressured:
            source.economy = RegionalEconomyState(
                stocks={"grain": 20.0}, capacities={"grain": 30.0},
                demand_rates={"grain": 0.0}, access={"grain": 1.0},
            )
            destination.economy = RegionalEconomyState(
                stocks={"grain": 0.0}, capacities={"grain": 20.0},
                demand_rates={"grain": 2.0}, access={"grain": 1.0},
            )
        bootstrap_institutional_authority(world)
        return world

    return factory


async def run_scenario(*, pressured: bool, seed: int, months: int) -> dict:
    from src.systems.causal_observatory import CausalTortureConfig, CausalTortureRunner

    captured: list = []
    memory_event_ids: set[str] = set()
    simulators: dict[int, object] = {}
    factory = _world_factory(pressured=pressured, seed=seed)

    def capture_factory(index: int, world_seed: int):
        return factory(index, world_seed)

    async def normal_step(world):
        from src.sim.simulator import Simulator

        if id(world) not in simulators:
            simulators[id(world)] = Simulator(world)
        simulator = simulators[id(world)]
        events = await simulator.step()
        captured.extend(events)
        memory_event_ids.update(
            str(memory.event_id)
            for memory in (getattr(world.institutional_relations, "memories", {}) or {}).values()
        )
        return events

    provider = AsyncMock(side_effect=AssertionError("institutional smoke attempted a provider call"))

    with patch("src.utils.llm.client.call_llm_with_template", provider):
        report = await CausalTortureRunner(CausalTortureConfig(
            worlds=1, months=months, seed=seed, test_mode=True, provider="test",
            probe_profile="baseline",
        )).run(world_factory=capture_factory, step=normal_step)
    data = report.to_dict()
    data["scenario"] = "pressured" if pressured else "natural"
    by_id = {str(event.id): event for event in captured}
    def ancestors(event_id: str, *, max_nodes: int = 64) -> tuple[dict[str, object], list[dict[str, str]]]:
        found: dict[str, object] = {}
        edges: list[dict[str, str]] = []
        pending = [event_id]
        while pending and len(found) < max_nodes:
            current_id = pending.pop()
            if current_id in found:
                continue
            current = by_id.get(current_id)
            if current is None:
                continue
            found[current_id] = current
            for link in getattr(current, "causal_links", ()) or ():
                cause_id = str(link.cause_event_id)
                edges.append({
                    "event_id": current_id,
                    "cause_event_id": cause_id,
                    "relation": getattr(getattr(link, "relation", None), "value", str(getattr(link, "relation", ""))),
                })
                if cause_id not in found:
                    pending.append(cause_id)
        return found, edges

    def has_delta(event: object) -> bool:
        payload = getattr(event, "causal_payload", None)
        return isinstance(payload, dict) and bool(payload.get("deltas"))

    story_as_material_cause_ids: list[str] = []
    for material in (event for event in captured if has_delta(event)):
        material_ancestors, _ = ancestors(str(material.id))
        story_as_material_cause_ids.extend(
            event_id
            for event_id, event in material_ancestors.items()
            if event_id != str(material.id) and bool(getattr(event, "is_story", False))
        )
    fulfilled = next((event for event in captured if event.event_type == "institutional_commitment_term_fulfilled"), None)
    witness = {"fulfilled": str(fulfilled.id) if fulfilled else None}
    if fulfilled:
        chain, chain_edges = ancestors(str(fulfilled.id))
        required_types = {
            "request_decision": "institutional_aid_request_interpretation_decision",
            "requested": "institutional_aid_requested",
            "response_decision": "institutional_aid_response_interpretation_decision",
            "accepted": "institutional_aid_accepted",
            "fulfillment_decision": "institutional_aid_fulfillment_interpretation_decision",
            "transfer": "regional_resource_transfer_completed",
            "fulfilled": "institutional_commitment_term_fulfilled",
        }
        for label, event_type in required_types.items():
            event = next((item for item in chain.values() if getattr(item, "event_type", "") == event_type), None)
            witness[label] = str(event.id) if event is not None else None
        witness["edges"] = chain_edges
        witness["memory_event_ids"] = sorted(memory_event_ids.intersection(chain))
    complete = all(witness.values()) if pressured else True
    audit = {
        "provider_call_count": provider.call_count,
        "provider_await_count": provider.await_count,
        "story_as_material_cause_ids": sorted(set(story_as_material_cause_ids)),
        "memory_event_ids_observed": sorted(memory_event_ids),
        "witness": witness,
        "assertions_passed": (
            provider.call_count == 0
            and provider.await_count == 0
            and not story_as_material_cause_ids
            and data["totals"]["broken_causes"] == 0
            and data["totals"]["story_mutations"] == 0
            and complete
            and (not pressured or bool(witness.get("memory_event_ids")))
        ),
    }
    if not audit["assertions_passed"]:
        raise RuntimeError(f"institutional smoke audit failed: {audit}")
    data["audit"] = audit
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--months", type=int, default=120)
    parser.add_argument("--scenario", choices=("natural", "pressured"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = asyncio.run(run_scenario(
        pressured=args.scenario == "pressured", seed=args.seed, months=args.months,
    ))
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data["totals"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

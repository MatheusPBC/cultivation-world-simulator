"""Prepared foundation scenario, not evidence of a complete natural-world simulation."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.run.medieval_world import create_medieval_world
from src.sim.medieval.actions import start_practice, start_travel
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.persistence import load_world, save_world, world_snapshot


async def run(seed: int, output: Path) -> dict:
    world = create_medieval_world(seed)
    traveler = next(c for c in world.society.characters.values() if c.location_id == "campomanso")
    for character in world.society.characters.values():
        if character.id == traveler.id:
            start_travel(world, character.id, "road-campomanso-pedraclara", "pedraclara")
        else:
            start_practice(world, character.id, "diplomacy", kind="study")
    save_world(world, output)
    engine = MedievalSimulator(world, save_path=output)
    jumps = []
    while world.clock.absolute_day < 360:
        jump = await engine.step()
        jumps.append(jump.elapsed_days)
    loaded = load_world(output)
    if world_snapshot(loaded) != world_snapshot(world):
        raise AssertionError("save/load changed the world state")
    if [e.model_dump(mode="json") for e in loaded.events] != [e.model_dump(mode="json") for e in world.events]:
        raise AssertionError("save/load changed causal history")
    return {"scenario": "prepared-foundation", "seed": seed, "day": world.clock.absolute_day,
            "characters": len(world.society.characters), "population": world.society.total_population,
            "jumps": jumps, "events": len(world.events), "save_load_equivalent": True,
            "real_ai_calls": 0, "save": str(output.resolve())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.seed, args.output)), ensure_ascii=False, indent=2))

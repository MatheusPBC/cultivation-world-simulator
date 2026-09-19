"""Audit a saved medieval world without mutating it.

This is deliberately a narrow verification tool, not another simulator.  It
replays no decisions: save/load validation checks the canonical owners and the
history checker verifies that every cause exists, material transitions have
deltas, and LLM interpretation receipts never carry or directly cause a delta.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sim.medieval.events import validate_history
from src.sim.medieval.persistence import load_world


def audit(path: Path) -> dict:
    world = load_world(path)
    validate_history(world.events, world.clock.absolute_day)
    interpretations = [event.id for event in world.events
                       if event.causal_origin.value == "llm_interpretation"]
    material_events = [event for event in world.events if event.deltas]
    broken_cause_ids = [
        link.cause_event_id
        for event in world.events
        for link in event.causal_links
        if not any(candidate.id == link.cause_event_id for candidate in world.events)
    ]
    story_material = [event.id for event in material_events
                      if event.event_type.startswith("story")]
    return {
        "save": str(path),
        "day": world.clock.absolute_day,
        "events": len(world.events),
        "material_events": len(material_events),
        "llm_interpretations": len(interpretations),
        "story_material_events": story_material,
        "broken_cause_ids": sorted(set(broken_cause_ids)),
        "ok": not story_material and not broken_cause_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", type=Path)
    args = parser.parse_args()
    result = audit(args.save)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

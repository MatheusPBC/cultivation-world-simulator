"""Audit a saved medieval world without mutating it.

This is deliberately a narrow verification tool, not another simulator.  It
replays no decisions: save/load validation checks the canonical owners and the
history checker verifies that every cause exists, material transitions have
deltas, and LLM interpretation receipts never carry or directly cause a delta.
"""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sim.medieval.persistence import load_world
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind


def audit(path: Path) -> dict:
    world = load_world(path)
    events_by_id = {event.id: event for event in world.events}
    interpretations = [event.id for event in world.events
                       if event.causal_origin.value == "llm_interpretation"]
    material_events = [event for event in world.events if event.deltas]
    material_by_origin = Counter(event.causal_origin.value for event in material_events)
    material_event_types = defaultdict(lambda: {
        "count": 0,
        "with_causal_links": 0,
        "without_causal_links": 0,
        "origins": Counter(),
    })
    for event in material_events:
        summary = material_event_types[event.event_type]
        summary["count"] += 1
        summary["origins"][event.causal_origin.value] += 1
        summary["with_causal_links" if event.causal_links else "without_causal_links"] += 1
    broken_cause_ids = [
        link.cause_event_id
        for event in world.events
        for link in event.causal_links
        if link.cause_event_id not in events_by_id
    ]
    story_material = [event.id for event in material_events
                      if event.event_type.startswith("story")]
    decision_origin_without_source = []
    decision_authorship_errors = []
    interpretation_material = []
    for event in world.events:
        causes = {link.cause_event_id for link in event.causal_links}
        if (event.causal_origin is CausalOrigin.ACTOR_DECISION
                and event.fact_kind is not FactKind.DECISION):
            sources = [source for cause_id in causes
                       if (source := events_by_id.get(cause_id)) is not None
                       and source.fact_kind is FactKind.DECISION
                       and source.decision is not None]
            if not sources:
                decision_origin_without_source.append(event.id)
            if event.deltas:
                payload = event.causal_payload or {}
                source_id = payload.get("decision_event_id")
                source = events_by_id.get(source_id) if isinstance(source_id, str) else None
                if (source is None or source_id not in causes
                        or source.fact_kind is not FactKind.DECISION or source.decision is None
                        or not isinstance(payload.get("actor_ref"), dict)
                        or not isinstance(payload.get("selected_affordance_id"), str)
                        or source.decision.get("actor_ref") != payload.get("actor_ref")
                        or source.decision.get("selected_affordance_id") != payload.get("selected_affordance_id")):
                    decision_authorship_errors.append(event.id)
        if (event.causal_origin is CausalOrigin.LLM_INTERPRETATION
                and (event.deltas or event.causal_payload and event.causal_payload.get("deltas"))):
            interpretation_material.append(event.id)
    return {
        "save": str(path),
        "day": world.clock.absolute_day,
        "events": len(world.events),
        "material_events": len(material_events),
        "material_by_origin": dict(sorted(material_by_origin.items())),
        # This is an inventory, not a new validity rule: bootstrap premises
        # and engine-owned physical observations may have no earlier event to
        # cite.  It makes those paths explicit for the owner-by-owner audit
        # instead of silently treating a green smoke as full coverage.
        "material_event_types": {
            event_type: {
                **{key: value for key, value in summary.items() if key != "origins"},
                "origins": dict(sorted(summary["origins"].items())),
            }
            for event_type, summary in sorted(material_event_types.items())
        },
        "llm_interpretations": len(interpretations),
        "story_material_events": story_material,
        "decision_origin_without_source": sorted(set(decision_origin_without_source)),
        "decision_authorship_errors": sorted(set(decision_authorship_errors)),
        "interpretation_material_events": sorted(set(interpretation_material)),
        "broken_cause_ids": sorted(set(broken_cause_ids)),
        "ok": not story_material and not broken_cause_ids
              and not decision_origin_without_source and not decision_authorship_errors
              and not interpretation_material,
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

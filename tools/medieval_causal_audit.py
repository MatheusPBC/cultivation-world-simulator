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


def _root_source_exists(world, root_kind: str, ref: dict) -> bool:
    """Resolve bootstrap provenance against the canonical owner registries."""
    kind, source_id = ref["kind"], ref["id"]
    if kind == "scenario":
        # Scenario IDs name the authored fixture, not a persisted world owner.
        return root_kind == "scenario_bootstrap"

    economy = getattr(world, "economy", None)
    society = getattr(world, "society", None)
    world_map = getattr(world, "map", None)
    creatures = getattr(world, "creatures", None)
    registries = {
        "account": getattr(economy, "accounts", {}),
        "facility": getattr(economy, "facilities", {}),
        "market": getattr(economy, "markets", {}),
        "settlement_needs": getattr(economy, "needs", {}),
        "stock": getattr(economy, "stocks", {}),
        "settlement": getattr(society, "settlements", {}),
        "population_group": getattr(society, "population", {}),
        "character": getattr(society, "characters", {}),
        "polity": getattr(society, "polities", {}),
        "organization": getattr(society, "organizations", {}),
        "route": getattr(world_map, "routes", {}),
        "site": getattr(world_map, "infrastructure_sites", {}),
        "creature": getattr(creatures, "creatures", {}),
    }
    if kind == "region":
        regions = getattr(world_map, "regions", {})
        return any(str(region_id) == source_id for region_id in regions)
    if kind == "observer":
        entity_kind, separator, entity_id = source_id.partition(":")
        return bool(separator) and _root_source_exists(
            world, root_kind, {"kind": entity_kind, "id": entity_id})
    registry = registries.get(kind)
    return registry is not None and source_id in registry


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
    material_delta_inventory = defaultdict(lambda: {
        "event_ids": set(),
        "owner_ids": set(),
        "example_event_ids": [],
        "delta_count": 0,
        "events_without_causal_links": set(),
        "events_with_root_premise": set(),
    })
    for event in material_events:
        summary = material_event_types[event.event_type]
        summary["count"] += 1
        summary["origins"][event.causal_origin.value] += 1
        summary["with_causal_links" if event.causal_links else "without_causal_links"] += 1
        for delta in event.deltas:
            key = (event.event_type, delta.owner_kind, delta.aspect,
                   event.causal_origin.value)
            inventory = material_delta_inventory[key]
            inventory["event_ids"].add(event.id)
            inventory["owner_ids"].add(delta.owner_id)
            inventory["delta_count"] += 1
            if not event.causal_links:
                inventory["events_without_causal_links"].add(event.id)
            if (event.causal_payload or {}).get("root_premise") is not None:
                inventory["events_with_root_premise"].add(event.id)
            if event.id not in inventory["example_event_ids"] and len(inventory["example_event_ids"]) < 3:
                inventory["example_event_ids"].append(event.id)
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
    decision_source_errors = []
    interpretation_material = []
    root_premise_events = []
    root_premise_errors = []
    unrooted_material_events = []
    for event in world.events:
        causes = {link.cause_event_id for link in event.causal_links}
        root = (event.causal_payload or {}).get("root_premise")
        if root is not None:
            refs = root.get("source_refs") if isinstance(root, dict) else None
            root_kind = root.get("kind") if isinstance(root, dict) else None
            valid_root_kind = (isinstance(root_kind, str)
                               and root_kind in {"world_generation", "scenario_bootstrap"})
            valid_refs = (isinstance(refs, list) and bool(refs)
                          and all(isinstance(ref, dict)
                                  and isinstance(ref.get("kind"), str) and ref["kind"]
                                  and isinstance(ref.get("id"), str) and ref["id"]
                                  for ref in refs))
            valid_sources = (valid_refs and valid_root_kind and all(
                _root_source_exists(world, root_kind, ref)
                for ref in refs
            ))
            if (not isinstance(root, dict)
                    or not valid_root_kind
                    or not isinstance(root.get("domain"), str) or not root["domain"]
                    or not valid_refs or not valid_sources
                    or type(root.get("observed_day")) is not int
                    or root["observed_day"] != event.day
                    or event.causal_origin is not CausalOrigin.DETERMINISTIC
                    or event.fact_kind is not FactKind.STATE_TRANSITION
                    or event.event_type.startswith("story")):
                root_premise_errors.append(event.id)
            else:
                root_premise_events.append(event.id)
        if (event.deltas and not event.causal_links
                and event.causal_origin is not CausalOrigin.EXTERNAL_EVENT
                and root is None):
            unrooted_material_events.append(event.id)
        if (event.fact_kind is FactKind.DECISION
                and event.causal_origin is CausalOrigin.ACTOR_DECISION):
            source = (event.causal_payload or {}).get("decision_source")
            if not isinstance(source, dict) or not isinstance(source.get("kind"), str) or not source["kind"]:
                decision_source_errors.append(event.id)
            elif (source["kind"] == "fallback"
                  and (not isinstance(source.get("policy"), str) or not source["policy"]
                       or not isinstance(source.get("rule"), str) or not source["rule"])):
                decision_source_errors.append(event.id)
            elif source["kind"] == "provider":
                receipt_id = source.get("receipt_event_id")
                receipt = events_by_id.get(receipt_id) if isinstance(receipt_id, str) else None
                selection = ((receipt.causal_payload or {}).get("selection")
                             if receipt is not None else None)
                no_action = (isinstance(selection, dict)
                             and (event.decision or {}).get("action") == "no_action"
                             and (event.decision or {}).get("selected_affordance_id") in (None, "NO_ACTION")
                             and selection.get("selected_affordance_id") == "NO_ACTION")
                if (receipt is None or receipt_id not in causes
                        or receipt.sequence >= event.sequence
                        or receipt.day != event.day
                        or receipt.event_type not in {"ai_decision_interpreted", "ai_decision_declined"}
                        or receipt.causal_origin is not CausalOrigin.LLM_INTERPRETATION
                        or receipt.deltas
                        or not isinstance(selection, dict)
                        or selection.get("actor_ref") != (event.decision or {}).get("actor_ref")
                        or (not no_action and selection.get("selected_affordance_id")
                            != (event.decision or {}).get("selected_affordance_id"))):
                    decision_source_errors.append(event.id)
            elif source["kind"] not in {"fallback", "player", "api"}:
                decision_source_errors.append(event.id)
        if (event.causal_origin is CausalOrigin.ACTOR_DECISION
                and event.fact_kind is not FactKind.DECISION):
            sources = [source for cause_id in causes
                       if (source := events_by_id.get(cause_id)) is not None
                       and source.fact_kind is FactKind.DECISION
                       and source.causal_origin is CausalOrigin.ACTOR_DECISION
                       and source.sequence < event.sequence and source.day == event.day
                       and source.decision is not None]
            if not sources:
                decision_origin_without_source.append(event.id)
            if event.deltas:
                payload = event.causal_payload or {}
                source_id = payload.get("decision_event_id")
                source = events_by_id.get(source_id) if isinstance(source_id, str) else None
                if (source is None or source_id not in causes
                        or source.fact_kind is not FactKind.DECISION or source.decision is None
                        or source.causal_origin is not CausalOrigin.ACTOR_DECISION
                        or source.day != event.day or source.sequence >= event.sequence
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
        "material_delta_inventory": [
            {
                "event_type": event_type,
                "owner_kind": owner_kind,
                "aspect": aspect,
                "causal_origin": origin,
                "event_count": len(summary["event_ids"]),
                "delta_count": summary["delta_count"],
                "owner_id_count": len(summary["owner_ids"]),
                "owner_id_samples": sorted(summary["owner_ids"])[:5],
                "events_without_causal_links": len(summary["events_without_causal_links"]),
                "events_with_root_premise": len(summary["events_with_root_premise"]),
                "example_event_ids": summary["example_event_ids"],
            }
            for (event_type, owner_kind, aspect, origin), summary
            in sorted(material_delta_inventory.items())
        ],
        "llm_interpretations": len(interpretations),
        "story_material_events": story_material,
        "decision_origin_without_source": sorted(set(decision_origin_without_source)),
        "decision_authorship_errors": sorted(set(decision_authorship_errors)),
        "decision_source_errors": sorted(set(decision_source_errors)),
        "root_premise_events": sorted(set(root_premise_events)),
        "root_premise_errors": sorted(set(root_premise_errors)),
        "unrooted_material_events": sorted(set(unrooted_material_events)),
        "interpretation_material_events": sorted(set(interpretation_material)),
        "broken_cause_ids": sorted(set(broken_cause_ids)),
        "ok": not story_material and not broken_cause_ids
              and not decision_origin_without_source and not decision_authorship_errors
              and not decision_source_errors
              and not root_premise_errors and not unrooted_material_events
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

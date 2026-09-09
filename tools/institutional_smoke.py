#!/usr/bin/env python3
"""Provider-free long smoke for institutional material commitments.

This is a harness, not a simulation path: each month goes through the normal
``Simulator.step`` and only the initial canonical city state differs between
the natural and pressured scenarios.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import AsyncMock, patch

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


ANCHOR_EVENT_TYPE = "institution_identity_anchored"


def audit_identity_anchors(
    world, *, stage: str = "unknown", expected_anchor_ids=None
) -> dict:
    """Check every identity anchor against the fact it cites.

    Pure and testable: it reads the world and returns findings. Zero anchors is
    a valid *starting* result -- a world whose config declares no seat reports
    none rather than being pushed into declaring one. Losing an anchor that
    genesis established is not: pass `expected_anchor_ids` and each missing one
    is a violation, so a later disappearance cannot read as a clean audit.
    """
    from src.classes.causal_origin import CausalOrigin
    from src.classes.event import FactKind

    state = getattr(world, "institutional_authority", None)
    anchors = dict(getattr(state, "identity_anchors", {}) or {})
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_event_by_id", None)
    violations: list[dict] = []

    def fail(anchor_id: str, reason: str, **extra) -> None:
        violations.append(
            {"stage": str(stage), "anchor_id": anchor_id, "reason": reason, **extra}
        )

    for missing in sorted(set(expected_anchor_ids or ()) - set(anchors)):
        fail(missing, "anchor_lost")

    for anchor in anchors.values():
        if str(anchor.subject.kind) != "region":
            fail(anchor.id, "subject_is_not_a_region", subject=str(anchor.subject.kind))
        if not anchor.evidence_event_ids:
            fail(anchor.id, "no_evidence")
            continue
        if anchor.institution_id not in (
            getattr(state, "institutions", {}) or {}
        ):
            fail(anchor.id, "unknown_institution")
        for event_id in anchor.evidence_event_ids:
            event = getter(str(event_id)) if callable(getter) else None
            if event is None:
                fail(anchor.id, "missing_evidence", event_id=str(event_id))
                continue
            if bool(getattr(event, "is_story", False)):
                fail(anchor.id, "story_evidence", event_id=str(event_id))
            if str(getattr(event, "event_type", "")) != ANCHOR_EVENT_TYPE:
                fail(anchor.id, "wrong_event_type", event_id=str(event_id))
                continue
            if getattr(event, "fact_kind", None) is not FactKind.STATE_TRANSITION:
                fail(anchor.id, "wrong_fact_kind", event_id=str(event_id))
            if getattr(event, "causal_origin", None) is not CausalOrigin.DETERMINISTIC:
                fail(anchor.id, "wrong_origin", event_id=str(event_id))
            params = getattr(event, "render_params", None) or {}
            if str(params.get("anchor_id")) != anchor.id:
                fail(anchor.id, "anchor_id_mismatch", event_id=str(event_id))
            if str(params.get("institution_id")) != anchor.institution_id:
                fail(anchor.id, "institution_mismatch", event_id=str(event_id))
            if str(params.get("region_id")) != str(anchor.subject.id):
                fail(anchor.id, "region_mismatch", event_id=str(event_id))
            if str(params.get("anchor_kind")) != str(anchor.kind.value):
                fail(anchor.id, "anchor_kind_mismatch", event_id=str(event_id))
            if str(params.get("premise")) != "world_genesis":
                fail(anchor.id, "premise_mismatch", event_id=str(event_id))
            if int(getattr(event, "month_stamp", -1)) != int(
                anchor.established_month
            ):
                fail(anchor.id, "month_mismatch", event_id=str(event_id))
            deltas = [
                item
                for item in ((getattr(event, "causal_payload", None) or {}).get(
                    "deltas"
                ) or [])
                if isinstance(item, dict)
                and str(item.get("owner_kind")) == "institutional_authority"
                and str(item.get("owner_id")) == anchor.institution_id
                and str(item.get("aspect")) == f"identity_anchor:{anchor.id}"
            ]
            if len(deltas) != 1:
                fail(anchor.id, "delta_missing_or_ambiguous", event_id=str(event_id))
                continue
            delta = deltas[0]
            if str(delta.get("event_id")) != str(event.id):
                fail(anchor.id, "delta_cites_another_event", event_id=str(event_id))
            if str(delta.get("before")) != "absent":
                fail(anchor.id, "delta_before_not_absent", event_id=str(event_id))
            if str(delta.get("after")) != "established":
                fail(anchor.id, "delta_after_not_established", event_id=str(event_id))
    return {
        "anchor_count": len(anchors),
        "anchor_ids": sorted(anchors),
        "violations": violations,
    }


def _world_factory(*, pressured: bool, commerce: bool, seed: int):
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
            "institutional_commitment_fulfillment_llm_budget_per_month": 0,
            "institutional_smoke_seed": seed,
            "institutional_smoke_scenario": "commerce" if commerce else ("pressured" if pressured else "natural"),
        }
        source = world.map.regions[302]
        destination = world.map.regions[305]
        if not isinstance(source, CityRegion) or not isinstance(destination, CityRegion):
            raise RuntimeError("classic map lacks institutional smoke cities")
        if not world.map.get_routes_between(302, 305):
            raise RuntimeError("classic institutional smoke cities are not connected")
        source.city_state.governance = CityGovernance("dynasty", "1", 1.0)
        destination.city_state.governance = CityGovernance("dynasty", "1", 1.0)
        if commerce:
            source.economy = RegionalEconomyState(
                stocks={"grain": 20.0, "medicine": 0.0},
                capacities={"grain": 30.0, "medicine": 30.0},
                demand_rates={"grain": 0.0, "medicine": 2.0},
                access={"grain": 1.0, "medicine": 1.0},
            )
            destination.economy = RegionalEconomyState(
                stocks={"grain": 0.0, "medicine": 20.0},
                capacities={"grain": 30.0, "medicine": 30.0},
                demand_rates={"grain": 2.0, "medicine": 0.0},
                access={"grain": 1.0, "medicine": 1.0},
            )
        elif pressured:
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


async def run_scenario(*, pressured: bool, seed: int, months: int, commerce: bool = False) -> dict:
    from src.systems.causal_observatory import CausalTortureConfig, CausalTortureRunner

    captured: list = []
    memory_event_ids: set[str] = set()
    simulators: dict[int, object] = {}
    factory = _world_factory(pressured=pressured, commerce=commerce, seed=seed)

    anchor_audits: list[dict] = []
    genesis_anchor_ids: set[str] = set()

    def capture_factory(index: int, world_seed: int):
        from src.systems.institution_bootstrap import (
            establish_genesis_identity_anchors,
        )

        world = factory(index, world_seed)
        # New world only, after the factory's own bootstrap and before the
        # first step. This is the institutional harness, not
        # `init_game_async`; the real initialization path is covered by its
        # own test. `SectContext.get_active_sects()` already answers with the
        # active configs, so no sect is selected or invented here.
        premises = establish_genesis_identity_anchors(world)
        # The premise facts happen before any step, so the step capture would
        # never see them. Added exactly once, here.
        captured.extend(premises)
        baseline = audit_identity_anchors(world, stage="genesis")
        anchor_audits.append(baseline)
        # Whatever genesis established must still be there at every later
        # stage; an anchor that disappears is a violation, not a clean zero.
        genesis_anchor_ids.update(baseline["anchor_ids"])
        return world

    async def normal_step(world):
        from src.sim.simulator import Simulator

        if id(world) not in simulators:
            simulators[id(world)] = Simulator(world)
        simulator = simulators[id(world)]
        events = await simulator.step()
        captured.extend(events)
        # Audited on the live world while the run is still in progress: the
        # torture runner restores its checkpoint before returning, so a check
        # made afterwards would only re-inspect restored genesis state.
        anchor_audits.append(audit_identity_anchors(
            world,
            stage=f"month:{int(world.month_stamp)}",
            expected_anchor_ids=genesis_anchor_ids,
        ))
        memory_event_ids.update(
            str(memory.event_id)
            for memory in (getattr(world.institutional_relations, "memories", {}) or {}).values()
        )
        return events

    provider = AsyncMock(side_effect=AssertionError("institutional smoke attempted a provider call"))

    async def choose_trade_only(original, *args, **kwargs):
        """Controlled decision fixture; production fallback remains untouched."""
        from src.classes.domain_affordance import DomainDecision, DomainDecisionKind

        domain = kwargs["domain"]
        options = tuple(kwargs["affordances"])
        action = {
            "institutional_resource_request": "request_reciprocal_trade",
            "institutional_resource_response": "accept_reciprocal_trade",
            "institutional_commitment_fulfillment": "fulfill_resource_transfer_term",
        }.get(domain)
        selected = next((item for item in options if item.action_kind == action), None)
        decision = (
            DomainDecision(DomainDecisionKind.ACT, "Controlled barter smoke witness.", selected.id)
            if selected is not None
            else DomainDecision(DomainDecisionKind.MAINTAIN, "No controlled barter action.")
        )
        return await original(*args, **{**kwargs, "injected_decision": decision})

    patches = [patch("src.utils.llm.client.call_llm_with_template", provider)]
    if commerce:
        import src.systems.institutional_resource_commitment as commitments

        original_interpreter = commitments.interpret_domain_affordances

        async def controlled_interpreter(*args, **kwargs):
            return await choose_trade_only(original_interpreter, *args, **kwargs)

        patches.append(patch.object(commitments, "interpret_domain_affordances", controlled_interpreter))

    with patches[0]:
        with patches[1] if len(patches) > 1 else nullcontext():
            report = await CausalTortureRunner(CausalTortureConfig(
                worlds=1, months=months, seed=seed, test_mode=True, provider="test",
                probe_profile="baseline",
            )).run(world_factory=capture_factory, step=normal_step)
    data = report.to_dict()
    data["scenario"] = "commerce" if commerce else ("pressured" if pressured else "natural")
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
    fulfilled_events = [event for event in captured if event.event_type == "institutional_commitment_term_fulfilled"]
    fulfilled = fulfilled_events[0] if fulfilled_events else None
    witness = {"fulfilled": str(fulfilled.id) if fulfilled else None}
    if commerce:
        proposal = next((event for event in captured if event.event_type == "institutional_trade_proposed"), None)
        accepted = next((event for event in captured if event.event_type == "institutional_trade_accepted"), None)
        legs = ((proposal.causal_payload or {}).get("institutional_trade_offer") or {}).get("legs", []) if proposal else []
        commitment_id = str((accepted.causal_payload or {}).get("commitment_id", "")) if accepted else ""
        term_ids = {
            str(item) for item in ((accepted.causal_payload or {}).get("term_ids") or [])
        } if accepted else set()
        transfers = [
            event for event in captured
            if event.event_type == "regional_resource_transfer_completed"
            and str((event.causal_payload or {}).get("commitment_id", "")) == commitment_id
            and str((event.causal_payload or {}).get("term_id", "")) in term_ids
        ]
        term_fulfillments = [
            event for event in fulfilled_events
            if str((event.causal_payload or {}).get("commitment_id", "")) == commitment_id
            and str((event.causal_payload or {}).get("term_id", "")) in term_ids
        ]
        leg_shapes = {
            (str(leg.get("source_region_id")), str(leg.get("destination_region_id")), str(leg.get("resource_id")), str(leg.get("route_id")), float(leg.get("amount", 0.0)))
            for leg in legs if isinstance(leg, dict)
        }
        transfer_shapes = {
            (str((event.causal_payload or {}).get("execution", {}).get("source_region_id")), str((event.causal_payload or {}).get("execution", {}).get("destination_region_id")), str((event.causal_payload or {}).get("execution", {}).get("resource_id")), str((event.causal_payload or {}).get("execution", {}).get("route_id")), float((event.causal_payload or {}).get("execution", {}).get("amount", 0.0)))
            for event in transfers
        }
        term_witnesses = {}
        combined_edges = []
        required_types = {
            "institutional_resource_request_interpretation_decision",
            "institutional_trade_proposed",
            "institutional_resource_response_interpretation_decision",
            "institutional_trade_accepted",
            "institutional_commitment_fulfillment_interpretation_decision",
            "regional_resource_transfer_completed",
            "institutional_commitment_term_fulfilled",
        }
        for fulfilled_event in term_fulfillments:
            chain, chain_edges = ancestors(str(fulfilled_event.id))
            combined_edges.extend(chain_edges)
            term_witnesses[str((fulfilled_event.causal_payload or {}).get("term_id", ""))] = {
                "fulfilled_event_id": str(fulfilled_event.id),
                "event_types": sorted({str(getattr(event, "event_type", "")) for event in chain.values()}),
                "complete": required_types.issubset({str(getattr(event, "event_type", "")) for event in chain.values()}),
            }
        witness.update({
            "proposal": str(proposal.id) if proposal else None,
            "accepted": str(accepted.id) if accepted else None,
            "commitment_id": commitment_id or None,
            "term_ids": sorted(term_ids),
            "two_reciprocal_legs": len(legs) == 2 and len(leg_shapes) == 2,
            "transfers_match_accepted_legs": transfer_shapes == leg_shapes,
            "term_witnesses": term_witnesses,
            "two_complete_term_witnesses": len(term_witnesses) == 2 and all(item["complete"] for item in term_witnesses.values()),
            "edges": combined_edges,
        })
        if proposal:
            witness["memory_event_ids"] = sorted(memory_event_ids.intersection({str(proposal.id), *(str(event.id) for event in term_fulfillments)}))
    elif fulfilled:
        chain, chain_edges = ancestors(str(fulfilled.id))
        required_types = {
            "request_decision": "institutional_resource_request_interpretation_decision",
            "requested": "institutional_aid_requested",
            "response_decision": "institutional_resource_response_interpretation_decision",
            "accepted": "institutional_aid_accepted",
            "fulfillment_decision": "institutional_commitment_fulfillment_interpretation_decision",
            "transfer": "regional_resource_transfer_completed",
            "fulfilled": "institutional_commitment_term_fulfilled",
        }
        for label, event_type in required_types.items():
            event = next((item for item in chain.values() if getattr(item, "event_type", "") == event_type), None)
            witness[label] = str(event.id) if event is not None else None
        witness["edges"] = chain_edges
        witness["memory_event_ids"] = sorted(memory_event_ids.intersection(chain))
    complete = all(witness.values()) if (pressured or commerce) else True
    anchor_violations = sorted(
        (
            violation
            for entry in anchor_audits
            for violation in entry["violations"]
        ),
        key=lambda item: json.dumps(item, sort_keys=True),
    )
    anchor_counts = sorted({entry["anchor_count"] for entry in anchor_audits})
    audit = {
        "provider_call_count": provider.call_count,
        "provider_await_count": provider.await_count,
        "story_as_material_cause_ids": sorted(set(story_as_material_cause_ids)),
        "memory_event_ids_observed": sorted(memory_event_ids),
        "witness": witness,
        "identity_anchors": {
            "genesis_count": anchor_audits[0]["anchor_count"] if anchor_audits else 0,
            "counts_observed": anchor_counts,
            "stages_audited": len(anchor_audits),
            "violations": anchor_violations,
        },
        "assertions_passed": (
            provider.call_count == 0
            and provider.await_count == 0
            and not story_as_material_cause_ids
            and data["totals"]["broken_causes"] == 0
            and data["totals"]["story_mutations"] == 0
            # The acceptance criteria require this to be zero, and the audit
            # was not asserting it.
            and data["totals"]["out_of_window_causes"] == 0
            and not anchor_violations
            and complete
            and (not (pressured or commerce) or bool(witness.get("memory_event_ids")))
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
    parser.add_argument("--scenario", choices=("natural", "pressured", "commerce"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = asyncio.run(run_scenario(
        pressured=args.scenario == "pressured", commerce=args.scenario == "commerce", seed=args.seed, months=args.months,
    ))
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data["totals"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

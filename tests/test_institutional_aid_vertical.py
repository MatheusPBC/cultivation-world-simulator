from types import SimpleNamespace
from pathlib import Path

import pytest

from src.classes.core.dynasty import Dynasty
from src.classes.environment.city_state import CityGovernance
from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.event import Event, FactKind
from src.classes.causal_link import MAX_CAUSAL_LINKS_PER_EVENT
from src.classes.mechanical_language import EntityRef
from src.classes.regional_economy import RegionalEconomyState
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.sim.simulator_engine.finalizer import validate_causal_integrity
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    AffordanceContext,
    StaleAffordanceError,
)
from src.systems.economy_reactivity import process_economy_reactivity
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institutional_resource_commitment import FULFILLMENT_DOMAIN, REQUEST_DOMAIN
from src.systems.institutional_memory import (
    decision_context,
    effective_salience,
    record_known_fact,
    reinforce_from_evidence,
)
from src.utils.llm.prompt import build_prompt
from src.server.assemblers.institutional_chain import build_institutional_chain


async def _select_first(_task, _template, context, **_kwargs):
    return {
        "decision": "act",
        "reason": "The grounded institutional option is acceptable.",
        "selected_affordance_id": context["affordances"][0]["id"],
    }


async def _request_then_refuse(_task, _template, context, **_kwargs):
    if "institutional_aid_request" in context["trigger"]["event_type"]:
        return {"decision": "maintain", "reason": "Provider declines the request."}
    return {
        "decision": "act",
        "reason": "The grounded institutional option is acceptable.",
        "selected_affordance_id": context["affordances"][0]["id"],
    }


def _setup(world):
    emperor = SimpleNamespace(id="emperor", is_dead=False)
    world.avatar_manager.avatars[emperor.id] = emperor
    world.dynasty = Dynasty(1, "Test Dynasty", "", current_emperor_id=emperor.id)

    def city(region_id: int, stock: float, demand: float) -> CityRegion:
        region = CityRegion(
            id=region_id,
            name=f"City {region_id}",
            desc="",
            cors=[(region_id % 10, region_id // 10)],
            economy=RegionalEconomyState(
                stocks={"grain": stock},
                capacities={"grain": 20},
                demand_rates={"grain": demand},
                access={"grain": 1.0},
            ),
        )
        region.city_state.governance = CityGovernance("dynasty", "1", 1.0)
        world.map.regions[region_id] = region
        return region

    source = city(302, 12, 0)
    destination = city(305, 0, 2)
    world.map.set_routes((Route("aid-road", (302, 305), "road", 2, 1.0, True),))
    bootstrap_institutional_authority(world)
    shortage = Event(
        world.month_stamp,
        "The destination could not satisfy grain demand.",
        event_type="regional_resource_shortage",
        render_params={"region_id": "305", "resource_id": "grain"},
        id="shortage:305:grain",
    )
    return source, destination, shortage


@pytest.mark.asyncio
async def test_request_and_independent_acceptance_create_terms_without_moving_stock(
    base_world,
):
    source, destination, shortage = _setup(base_world)

    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )

    assert [event.event_type for event in events[:4]] == [
        "institutional_resource_request_interpretation_decision",
        "institutional_aid_requested",
        "institutional_resource_response_interpretation_decision",
        "institutional_aid_accepted",
    ]
    assert [event.event_type for event in events[4:]].count(
        "institutional_relationship_impact_interpretation_decision"
    ) == 2
    decisions = [event for event in events[:4] if event.fact_kind is FactKind.DECISION]
    assert [event.causal_payload["decision"]["subject_id"] for event in decisions] == [
        "305",
        "302",
    ]
    assert all(event.causal_payload["deltas"] == [] for event in decisions)
    commitment = next(iter(base_world.institutional_relations.commitments.values()))
    assert len(commitment.terms) == 2
    assert all(term.status.value == "active" for term in commitment.terms)
    assert source.economy.stocks["grain"] == 12
    assert destination.economy.stocks["grain"] == 0
    assert source.economy.reservations == {}
    assert destination.economy.reservations == {}
    validate_causal_integrity(
        SimpleNamespace(world=base_world),
        [shortage, *events],
    )


@pytest.mark.asyncio
async def test_same_month_refusal_reaches_both_relationship_observers(base_world):
    _source, _destination, shortage = _setup(base_world)

    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_request_then_refuse,
    )

    refused = next(event for event in events if event.event_type == "institutional_aid_refused")
    relationship_decisions = [
        event
        for event in events
        if event.event_type == "institutional_relationship_impact_interpretation_decision"
    ]
    assert len(relationship_decisions) == 2
    assert {
        receipt.condition_instance_id
        for receipt in base_world.mechanical_language.reaction_receipts.values()
        if receipt.domain == "institutional_relationship_impact"
    } == {
        f"institutional-relationship:inst:city:302:{refused.id}",
        f"institutional-relationship:inst:city:305:{refused.id}",
    }


@pytest.mark.asyncio
async def test_aid_template_receives_bounded_known_context_in_real_prompt_builder(
    base_world,
):
    _source, _destination, shortage = _setup(base_world)
    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )
    accepted = next(event for event in events if event.event_type == "institutional_aid_accepted")
    context = decision_context(
        base_world,
        "inst:city:302",
        event_overlays=(accepted,),
    )
    template = Path("static/locales/en-US/templates/institutional_commitment_interpreter.txt").read_text(
        encoding="utf-8"
    )
    prompt = build_prompt(
        template,
        {
            "actor": "City 302",
            "trigger": {"event_id": accepted.id, "event_type": accepted.event_type},
            "affordances": [{"id": "aid-option"}],
            "context": {"role": "provider", "institution": context},
        },
    )
    assert "City 302" in prompt
    assert accepted.id in prompt
    assert accepted.event_type in prompt
    assert "aid-option" in prompt
    assert "known_facts" in prompt


def test_memory_decay_and_reinforcement_require_distinct_known_canonical_evidence(
    base_world,
):
    _source, _destination, _shortage = _setup(base_world)
    institution_id = "inst:city:302"
    remembered = Event(
        base_world.month_stamp,
        "A canonical institutional event occurred.",
        event_type="institutional_aid_accepted",
        causal_payload={"deltas": []},
        id="memory:remembered",
    )
    factors = {"relative_scale": 0.4, "institutional_change": 1.0}
    record_known_fact(base_world, remembered, (institution_id,), factors=factors)
    memory = base_world.institutional_relations.memories[
        f"memory:{institution_id}:{remembered.id}"
    ]
    base_world.month_stamp += 12
    assert effective_salience(memory, base_world.month_stamp) == pytest.approx(memory.salience / 2)

    evidence = Event(
        base_world.month_stamp,
        "A distinct canonical breach confirmed the earlier obligation mattered.",
        event_type="institutional_commitment_term_breached",
        causal_payload={"deltas": []},
        id="memory:evidence",
    )
    record_known_fact(base_world, evidence, (institution_id,))
    assert reinforce_from_evidence(
        base_world,
        institution_id=institution_id,
        remembered_event_id=remembered.id,
        evidence_event=evidence,
    )
    refreshed = base_world.institutional_relations.memories[memory.id]
    assert refreshed.factors == memory.factors
    assert refreshed.last_reinforced_month == base_world.month_stamp
    assert not reinforce_from_evidence(
        base_world,
        institution_id=institution_id,
        remembered_event_id=remembered.id,
        evidence_event=evidence,
    )


@pytest.mark.asyncio
async def test_fulfillment_revalidates_the_exact_term_before_material_transfer(
    base_world,
):
    source, destination, shortage = _setup(base_world)
    accepted = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )
    assert base_world.event_manager.commit_step([shortage, *accepted])
    base_world.month_stamp = base_world.month_stamp + 1
    commitment = next(iter(base_world.institutional_relations.commitments.values()))
    context = AffordanceContext(
        base_world,
        FULFILLMENT_DOMAIN,
        EntityRef("region", "302"),
        base_world.event_manager.get_event_by_id(commitment.origin_event_id),
    )
    selected = DOMAIN_AFFORDANCES.compose(context)[0]
    source_before = source.economy.stocks["grain"]
    destination_before = destination.economy.stocks["grain"]
    base_world.map.routes["aid-road"].update_runtime(enabled=False)
    with pytest.raises(StaleAffordanceError):
        DOMAIN_AFFORDANCES.execute(
            context,
            selected.id,
            decision_event_id="decision:stale",
        )
    assert source.economy.stocks["grain"] == source_before
    assert destination.economy.stocks["grain"] == destination_before

    base_world.map.routes["aid-road"].update_runtime(enabled=True)
    repeated_shortage = Event(
        base_world.month_stamp,
        "The shortage persists while the accepted aid is in transit.",
        event_type="regional_resource_shortage",
        render_params={"region_id": "305", "resource_id": "grain"},
        id="shortage:305:grain:next-month",
    )
    events = await process_economy_reactivity(
        base_world,
        current_events=[repeated_shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )
    assert [event.event_type for event in events[:4]] == [
        "institutional_commitment_fulfillment_interpretation_decision",
        "regional_resource_transfer_completed",
        "institutional_commitment_term_fulfilled",
        "institutional_resource_request_interpretation_decision",
    ]
    assert [event.event_type for event in events[4:]].count(
        "institutional_relationship_impact_interpretation_decision"
    ) == 2
    assert source.economy.stocks["grain"] == source_before - 1
    assert destination.economy.stocks["grain"] == destination_before + 1
    updated = base_world.institutional_relations.commitments[commitment.id]
    assert [term.status.value for term in updated.terms] == ["fulfilled", "active"]
    assert len(base_world.institutional_relations.commitments) == 1
    validate_causal_integrity(
        SimpleNamespace(world=base_world),
        [repeated_shortage, *events],
    )

    assert base_world.event_manager.commit_step([repeated_shortage, *events])
    base_world.map.routes["aid-road"].update_runtime(enabled=False)
    base_world.month_stamp = base_world.month_stamp + 2
    breach_events = await process_economy_reactivity(
        base_world,
        current_events=[],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )
    assert breach_events[0].event_type == "institutional_commitment_term_breached"
    assert [event.event_type for event in breach_events[1:]].count(
        "institutional_relationship_impact_interpretation_decision"
    ) == 2
    breached = base_world.institutional_relations.commitments[commitment.id]
    breached_term = breached.terms[1]
    assert breached_term.status.value == "breached"
    assert breached_term.breach_event_ids == (breach_events[0].id,)
    assert (
        len(
            [
                fact
                for fact in base_world.institutional_knowledge.known_facts.values()
                if fact.event_id == breach_events[0].id
            ]
        )
        == 2
    )
    breach_memories = [
        memory
        for memory in base_world.institutional_relations.memories.values()
        if memory.event_id == breach_events[0].id
    ]
    assert len(breach_memories) == 2
    assert all(
        memory.salience == sum(value for _, value in memory.factors) / 4
        for memory in breach_memories
    )
    assert source.economy.stocks["grain"] == source_before - 1
    assert destination.economy.stocks["grain"] == destination_before + 1
    validate_causal_integrity(SimpleNamespace(world=base_world), breach_events)

    assert base_world.event_manager.commit_step(breach_events)
    base_world.map.routes["aid-road"].update_runtime(enabled=True)
    recovery_shortage = Event(
        base_world.month_stamp,
        "The city can seek a fresh agreement after the previous breach.",
        event_type="regional_resource_shortage",
        render_params={"region_id": "305", "resource_id": "grain"},
    )
    assert DOMAIN_AFFORDANCES.compose(
        AffordanceContext(
            base_world,
            REQUEST_DOMAIN,
            EntityRef("region", "305"),
            recovery_shortage,
        )
    )
    base_world.month_stamp = base_world.month_stamp + 1
    remediation_events = await process_economy_reactivity(
        base_world,
        current_events=[],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )
    assert [event.event_type for event in remediation_events] == [
        "institutional_commitment_remediation_interpretation_decision",
        "institutional_commitment_remediation_proposed",
    ]
    remediating = base_world.institutional_relations.commitments[commitment.id]
    assert remediating.terms[1].status.value == "remediation_proposed"
    assert source.economy.stocks["grain"] == source_before - 1
    assert destination.economy.stocks["grain"] == destination_before + 1
    validate_causal_integrity(SimpleNamespace(world=base_world), remediation_events)

    assert base_world.event_manager.commit_step(remediation_events)
    base_world.map.routes["aid-road"].update_runtime(enabled=False)
    base_world.month_stamp = base_world.month_stamp + 1
    repeated_breach_events = await process_economy_reactivity(
        base_world,
        current_events=[],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )
    assert repeated_breach_events[0].event_type == "institutional_commitment_term_breached"
    assert [event.event_type for event in repeated_breach_events[1:]].count(
        "institutional_relationship_impact_interpretation_decision"
    ) == 2
    rebreached = base_world.institutional_relations.commitments[commitment.id]
    assert rebreached.terms[1].status.value == "breached"
    assert rebreached.terms[1].breach_event_ids == (
        breach_events[0].id,
        repeated_breach_events[0].id,
    )
    validate_causal_integrity(SimpleNamespace(world=base_world), repeated_breach_events)

    assert base_world.event_manager.commit_step(repeated_breach_events)
    base_world.map.routes["aid-road"].update_runtime(enabled=True)
    base_world.month_stamp = base_world.month_stamp + 1
    renewed_remediation_events = await process_economy_reactivity(
        base_world,
        current_events=[],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )
    assert [event.event_type for event in renewed_remediation_events] == [
        "institutional_commitment_remediation_interpretation_decision",
        "institutional_commitment_remediation_proposed",
    ]
    assert base_world.event_manager.commit_step(renewed_remediation_events)

    base_world.month_stamp = base_world.month_stamp + 1
    resolved_events = await process_economy_reactivity(
        base_world,
        current_events=[],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )
    assert [event.event_type for event in resolved_events[:3]] == [
        "institutional_commitment_fulfillment_interpretation_decision",
        "regional_resource_transfer_completed",
        "institutional_commitment_term_remediated",
    ]
    assert [event.event_type for event in resolved_events[3:]].count(
        "institutional_relationship_impact_interpretation_decision"
    ) == 2
    resolved = base_world.institutional_relations.commitments[commitment.id]
    assert [term.status.value for term in resolved.terms] == [
        "fulfilled",
        "remediated",
    ]
    assert resolved.closed_month == base_world.month_stamp
    assert resolved.terms[1].breach_event_ids == (
        breach_events[0].id,
        repeated_breach_events[0].id,
    )
    resolved_causes = {
        link.cause_event_id
        for event in resolved_events
        if event.event_type == "institutional_commitment_term_remediated"
        for link in event.causal_links
    }
    # A remediated event retains a direct edge to the newest breach only.  Each
    # repeated breach points to its predecessor, so the entire breach history
    # stays navigable without ever exceeding the global eight-edge cap.
    assert resolved.terms[1].breach_event_ids[-1] in resolved_causes
    assert len(
        [
            link
            for link in repeated_breach_events[0].causal_links
            if link.cause_event_id == breach_events[0].id
        ]
    ) == 1
    assert all(
        len(event.causal_links) <= MAX_CAUSAL_LINKS_PER_EVENT
        for event in [*breach_events, *repeated_breach_events, *resolved_events]
    )
    assert source.economy.stocks["grain"] == source_before - 2
    assert destination.economy.stocks["grain"] == destination_before + 2
    validate_causal_integrity(SimpleNamespace(world=base_world), resolved_events)


@pytest.mark.asyncio
async def test_chain_projects_real_aid_decisions_and_material_transfer(base_world):
    source, destination, shortage = _setup(base_world)
    accepted = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )
    assert base_world.event_manager.commit_step([shortage, *accepted])

    base_world.month_stamp += 1
    continued_shortage = Event(
        base_world.month_stamp,
        "The shortage remains while aid is due.",
        event_type="regional_resource_shortage",
        render_params={"region_id": str(destination.id), "resource_id": "grain"},
        id="shortage:chain:next",
    )
    fulfilled = await process_economy_reactivity(
        base_world,
        current_events=[continued_shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_select_first,
    )
    assert base_world.event_manager.commit_step([continued_shortage, *fulfilled])

    chain = build_institutional_chain(
        base_world,
        owner_kind="region",
        owner_id=str(source.id),
        limit=50,
    )

    event_types = {event["event_type"] for event in chain["events"]}
    assert "institutional_commitment_fulfillment_interpretation_decision" in event_types
    assert "regional_resource_transfer_completed" in event_types
    assert "institutional_commitment_term_fulfilled" in event_types

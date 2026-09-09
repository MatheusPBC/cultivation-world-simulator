from dataclasses import replace

import pytest

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_affordance import DomainAffordance
from src.classes.environment.city_state import (
    UrbanAsset,
    UrbanCrowdDamageProfile,
    UrbanServiceDemand,
)
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import DomainReactionReceipt, EntityRef
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.civil_riot import riot_receipt_id
from src.systems.collective_affordances import population_affordances
from src.systems.city_damage import execute_crowd_damage
from src.systems.domain_affordance_registry import AffordanceContext, StaleAffordanceError
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from tests.domain_reactivity_fixtures import setup_government_condition


def _riot_setup(world):
    city, trigger, condition = setup_government_condition(world, integrity=0.5)
    city.city_state = replace(
        city.city_state,
        assets=(
            UrbanAsset(
                "clinic",
                "core",
                ("healing",),
                10.0,
                0.4,
                0.5,
                UrbanCrowdDamageProfile(0.6, 40.0),
            ),
        ),
        service_demands=(UrbanServiceDemand("healing", 1.0),),
    )
    bootstrap_institutional_authority(world)
    context = AffordanceContext(
        world,
        "population",
        EntityRef("population", f"region:{city.id}"),
        trigger,
        condition,
    )
    option = next(
        item for item in population_affordances(context)
        if item.action_kind == "join_public_riot"
    )
    return city, trigger, condition, context, option


def _decision(context, option, *, event_id="riot-decision"):
    audit = AgentDecision(
        month_stamp=int(context.world.month_stamp),
        subject_kind=context.actor_ref.kind,
        subject_id=context.actor_ref.id,
        source="llm",
        considered_count=1,
        chosen_chain=[{"selected_affordance_id": option.id}],
        thinking="Choose the listed public riot affordance.",
        short_term_objective="Respond to the grounded grievance.",
    )
    event = Event(
        context.world.month_stamp,
        "The population chooses a public riot.",
        id=event_id,
        event_type="population_interpretation_decision",
        render_params={
            "domain": context.domain,
            "actor_kind": context.actor_ref.kind,
            "actor_id": context.actor_ref.id,
            "decision": "act",
            "selected_affordance_id": option.id,
        },
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        causal_payload={
            "deltas": [],
            "decision": audit.to_dict(),
            "interpretation": {
                "decision": "act",
                "selected_affordance_id": option.id,
                "source": "llm",
            },
        },
    )
    event.causal_links.append(CausalLink(
        event_id=event.id,
        cause_event_id=context.trigger_event.id,
        relation=CausalRelation.RESPONSE_TO,
    ))
    return event


def _attempt(context, option, decision_event, invalidations, *, decision_event_id=None):
    return execute_crowd_damage(
        context,
        option,
        decision_event_id=(
            str(decision_event.id)
            if decision_event is not None and decision_event_id is None
            else str(decision_event_id or "")
        ),
        decision_event=decision_event,
        invalidations=invalidations,
    )


def _unchanged(world, city, invalidations, before_integrity, before_receipts, before_knowledge):
    assert city.city_state.assets[0].integrity == before_integrity
    assert world.mechanical_language.reaction_receipts == before_receipts
    assert world.institutional_knowledge.to_dict() == before_knowledge
    assert invalidations.drain() == []


def test_crowd_damage_rejects_missing_or_mismatched_decision_without_writes(base_world):
    city, _trigger, _condition, context, option = _riot_setup(base_world)
    invalidations = DomainInvalidationQueue()
    before_integrity = city.city_state.assets[0].integrity
    before_receipts = dict(base_world.mechanical_language.reaction_receipts)
    before_knowledge = base_world.institutional_knowledge.to_dict()

    with pytest.raises(StaleAffordanceError, match="decision"):
        _attempt(context, option, None, invalidations)
    _unchanged(base_world, city, invalidations, before_integrity, before_receipts, before_knowledge)

    decision = _decision(context, option)
    with pytest.raises(StaleAffordanceError, match="decision id"):
        _attempt(
            context,
            option,
            decision,
            invalidations,
            decision_event_id="different-decision",
        )
    _unchanged(base_world, city, invalidations, before_integrity, before_receipts, before_knowledge)


def test_crowd_damage_rejects_forged_target_and_stale_profile_without_writes(base_world):
    city, _trigger, _condition, context, option = _riot_setup(base_world)
    forged = DomainAffordance(
        domain=option.domain,
        actor_ref=option.actor_ref,
        action_kind=option.action_kind,
        target_refs=option.target_refs,
        parameters={**option.parameters, "asset_id": "not-the-listed-asset"},
        urgency=option.urgency,
        motivation_event_ids=option.motivation_event_ids,
    )
    invalidations = DomainInvalidationQueue()
    before_integrity = city.city_state.assets[0].integrity
    before_receipts = dict(base_world.mechanical_language.reaction_receipts)
    before_knowledge = base_world.institutional_knowledge.to_dict()
    with pytest.raises(StaleAffordanceError, match="not currently offered|target"):
        _attempt(context, forged, _decision(context, forged), invalidations)
    _unchanged(base_world, city, invalidations, before_integrity, before_receipts, before_knowledge)

    decision = _decision(context, option)
    city.city_state = replace(
        city.city_state,
        assets=(replace(city.city_state.assets[0], crowd_damage_profile=None),),
    )
    with pytest.raises(StaleAffordanceError, match="not currently offered|profile|admissible|material"):
        _attempt(context, option, decision, invalidations)
    _unchanged(base_world, city, invalidations, before_integrity, before_receipts, before_knowledge)


def test_crowd_damage_rejects_spent_receipt_replay_without_writes(base_world):
    city, _trigger, condition, context, option = _riot_setup(base_world)
    receipt_id = riot_receipt_id(str(city.id), str(condition.id))
    base_world.mechanical_language.reaction_receipts[receipt_id] = DomainReactionReceipt.create(
        f"civil-riot:{city.id}:{condition.id}",
        "civil_riot",
        str(condition.id),
        decision="act",
        affordance_id=option.id,
        completed=True,
    )
    invalidations = DomainInvalidationQueue()
    before_integrity = city.city_state.assets[0].integrity
    before_receipts = dict(base_world.mechanical_language.reaction_receipts)
    before_knowledge = base_world.institutional_knowledge.to_dict()

    with pytest.raises(StaleAffordanceError, match="not currently offered|receipt|already|admissible"):
        _attempt(context, option, _decision(context, option), invalidations)
    _unchanged(base_world, city, invalidations, before_integrity, before_receipts, before_knowledge)


def test_crowd_damage_owner_accepts_valid_composed_option(base_world):
    city, _trigger, _condition, context, option = _riot_setup(base_world)
    decision = _decision(context, option)
    invalidations = DomainInvalidationQueue()
    before_integrity = city.city_state.assets[0].integrity

    event = _attempt(context, option, decision, invalidations)

    assert event.event_type == "civil_riot_occurred"
    assert city.city_state.assets[0].integrity < before_integrity
    assert invalidations.drain()

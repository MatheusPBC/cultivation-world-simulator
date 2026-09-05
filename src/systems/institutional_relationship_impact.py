"""Bounded institutional climate contributions from known aid facts.

V1 ``InstitutionalRelation.friendliness`` is bilateral relationship climate,
not either institution's private, directional opinion.  Each observer may make
one independently audited contribution to that shared scalar; this module never
combines two interpreted directions and never changes the formal relation kind.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.agent_decision import AgentDecision
from src.classes.domain_affordance import DomainAffordance
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.event import Event, FactKind
from src.classes.institution import InstitutionalRelation, InstitutionalRelationKind
from src.classes.mechanical_language import DomainReactionReceipt, EntityRef
from src.classes.state_delta import StateDelta
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    AffordanceContext,
    StaleAffordanceError,
    stale_affordance_blocked_event,
)
from src.systems.institution_authority import can_actor_act_for
from src.systems.institutional_memory import decision_context as institutional_decision_context
from src.systems.institutional_memory import record_known_fact
from src.utils.llm.runtime_mode import is_test_mode_enabled, is_world_test_mode
from src.classes.institution import AuthorityScope
from src.systems.domain_decision_interpreter import interpret_domain_affordances
from src.sim.simulator_engine.causal_budget import CausalBudget


RELATIONSHIP_IMPACT_DOMAIN = "institutional_relationship_impact"
CONTRIBUTE_ACTION = "contribute_institutional_relationship_impact"
ELIGIBLE_EVENT_TYPES = frozenset({
    "institutional_aid_accepted",
    "institutional_aid_refused",
    "institutional_trade_accepted",
    "institutional_trade_refused",
    "institutional_commitment_term_fulfilled",
    "institutional_commitment_term_breached",
    "institutional_commitment_term_remediated",
})
# A refusal opens no commitment, so its parties come from the refused proposal.
_REFUSED_PROPOSAL_PARTY_KEYS = {
    "institutional_aid_refused": (
        "institutional_aid_request",
        ("requester_institution_id", "provider_institution_id"),
    ),
    "institutional_trade_refused": (
        "institutional_trade_offer",
        ("proposer_institution_id", "counterparty_institution_id"),
    ),
}
_CHOICES = (
    ("positive", "mild", 2),
    ("positive", "moderate", 4),
    ("positive", "strong", 6),
    ("negative", "mild", -2),
    ("negative", "moderate", -4),
    ("negative", "strong", -6),
    ("neutral", "mild", 0),
    ("ambivalent", "mild", 0),
)


@dataclass(frozen=True, slots=True)
class RelationshipAffordanceContext(AffordanceContext):
    """Step-local causal evidence only; it is never World state or persisted."""

    event_overlays: Mapping[str, Event] = field(default_factory=dict)


def _event_by_id(world: Any, event_id: str, overlays: Mapping[str, Event]) -> Event | None:
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_event_by_id", None)
    stored = getter(event_id) if callable(getter) else None
    return stored if stored is not None else overlays.get(event_id)


def _parties(
    world: Any,
    event: Event,
    *,
    event_overlays: Mapping[str, Event] | None = None,
) -> tuple[str, ...]:
    overlays = event_overlays or {}
    payload = event.causal_payload if isinstance(event.causal_payload, dict) else {}
    commitment_id = payload.get("commitment_id")
    if isinstance(commitment_id, str) and commitment_id:
        commitment = world.institutional_relations.commitments.get(commitment_id)
        return tuple(commitment.party_ids) if commitment is not None else ()
    refused = _REFUSED_PROPOSAL_PARTY_KEYS.get(event.event_type)
    if refused is not None:
        payload_key, party_keys = refused
        proposal_event = next(
            (
                _event_by_id(world, link.cause_event_id, overlays)
                for link in event.causal_links
                if getattr(link, "relation", None) is CausalRelation.RESPONSE_TO
            ),
            None,
        )
        proposal_payload = (
            getattr(proposal_event, "causal_payload", None)
            if proposal_event is not None
            else None
        )
        proposal = (
            proposal_payload.get(payload_key)
            if isinstance(proposal_payload, dict)
            else None
        )
        if not isinstance(proposal, dict):
            return ()
        return tuple(sorted({str(proposal[key]) for key in party_keys if proposal.get(key)}))
    return ()


def _receipt_id(institution_id: str, event_id: str) -> str:
    return DomainReactionReceipt.create(
        f"institutional-relationship:{institution_id}:{event_id}",
        RELATIONSHIP_IMPACT_DOMAIN,
        event_id,
        decision="maintain",
        affordance_id=None,
    ).id


def _is_eligible(
    world: Any,
    institution_id: str,
    event: Event,
    *,
    event_overlays: Mapping[str, Event] | None = None,
) -> tuple[str, ...]:
    if (
        event.is_story
        or event.causal_origin is CausalOrigin.LLM_INTERPRETATION
        or event.fact_kind is FactKind.DECISION
        or event.event_type not in ELIGIBLE_EVENT_TYPES
    ):
        return ()
    parties = _parties(world, event, event_overlays=event_overlays)
    if institution_id not in parties or len(parties) != 2:
        return ()
    if not world.institutional_knowledge.contains(institution_id, event.id):
        return ()
    manager = getattr(world, "event_manager", None)
    stored = manager.get_event_by_id(event.id) if manager is not None else None
    if stored is not None and (
        stored.event_type != event.event_type
        or stored.causal_payload != event.causal_payload
    ):
        return ()
    if _receipt_id(institution_id, event.id) in world.mechanical_language.reaction_receipts:
        return ()
    return parties


def relationship_impact_affordances(
    context: AffordanceContext,
    *,
    event_overlays: Mapping[str, Event] | None = None,
) -> tuple[DomainAffordance, ...]:
    """Enumerate only fixed, engine-owned reaction magnitudes for one fact."""
    event_overlays = event_overlays or getattr(context, "event_overlays", {})
    authority = context.world.institutional_authority
    observer = authority.get_institution_for_owner(context.actor_ref)
    if observer is None:
        return ()
    if not can_actor_act_for(
        context.world,
        context.actor_ref,
        context.actor_ref,
        AuthorityScope.COMMITMENT_NEGOTIATION,
        current_month=int(context.world.month_stamp),
    ).allowed:
        return ()
    parties = _is_eligible(
        context.world,
        observer.id,
        context.trigger_event,
        event_overlays=event_overlays,
    )
    if not parties:
        return ()
    counterpart_id = next(item for item in parties if item != observer.id)
    return tuple(
        DomainAffordance(
            domain=RELATIONSHIP_IMPACT_DOMAIN,
            actor_ref=context.actor_ref,
            action_kind=CONTRIBUTE_ACTION,
            target_refs=(EntityRef("institution", counterpart_id),),
            parameters={
                "observer_institution_id": observer.id,
                "counterpart_institution_id": counterpart_id,
                "source_event_id": context.trigger_event.id,
                "valence": valence,
                "intensity": intensity,
                "delta": delta,
            },
            urgency=0.2,
            motivation_event_ids=(context.trigger_event.id,),
        )
        for valence, intensity, delta in _CHOICES
    )


def record_maintained_reaction(
    world: Any,
    *,
    institution_id: str,
    evidence_event: Event,
    decision_event_id: str,
    event_overlays: Mapping[str, Event] | None = None,
) -> None:
    """Persist a no-change decision once, so the same fact is not reconsidered."""
    if not _is_eligible(
        world, institution_id, evidence_event, event_overlays=event_overlays
    ):
        raise StaleAffordanceError("institutional relationship reaction is absent or stale")
    receipt = DomainReactionReceipt.create(
        f"institutional-relationship:{institution_id}:{evidence_event.id}",
        RELATIONSHIP_IMPACT_DOMAIN,
        evidence_event.id,
        decision="maintain",
        affordance_id=None,
        decision_event_ids=(decision_event_id,),
        completed=True,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt


def _validate_decision(
    decision_event: Event | None,
    context: AffordanceContext,
    option: DomainAffordance,
) -> None:
    if not isinstance(decision_event, Event):
        raise StaleAffordanceError("institutional relationship decision is absent")
    payload = decision_event.causal_payload if isinstance(decision_event.causal_payload, dict) else {}
    decision = payload.get("decision")
    interpretation = payload.get("interpretation")
    try:
        audit = AgentDecision.from_dict(decision)
    except (AttributeError, TypeError, ValueError):
        raise StaleAffordanceError("institutional relationship decision is not canonical") from None
    if (
        decision_event.fact_kind is not FactKind.DECISION
        or decision_event.is_story
        or payload.get("deltas") != []
        or not isinstance(decision, dict)
        or not isinstance(interpretation, dict)
        or set(decision) != set(audit.to_dict())
        or audit.month_stamp != int(context.world.month_stamp)
        or not isinstance(audit.id, str)
        or not audit.id
        or audit.subject_kind != context.actor_ref.kind
        or str(audit.subject_id) != context.actor_ref.id
        or audit.source not in {"llm", "rule", "injected"}
        or not isinstance(audit.considered_count, int)
        or audit.considered_count < 1
        or audit.chosen_chain != [{"selected_affordance_id": option.id}]
        or decision_event.render_params.get("domain") != RELATIONSHIP_IMPACT_DOMAIN
        or decision_event.render_params.get("actor_kind") != context.actor_ref.kind
        or str(decision_event.render_params.get("actor_id")) != context.actor_ref.id
        or interpretation.get("decision") != DomainDecisionKind.ACT.value
        or str(interpretation.get("selected_affordance_id", "")) != option.id
        or not any(
            link.relation is CausalRelation.RESPONSE_TO
            and link.cause_event_id == context.trigger_event.id
            for link in decision_event.causal_links
        )
    ):
        raise StaleAffordanceError("institutional relationship decision is not canonical")


def execute_relationship_impact(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event: Event | None = None,
    event_overlays: Mapping[str, Event] | None = None,
    **_: Any,
) -> Event:
    """Revalidate and let InstitutionalRelationsState apply one bounded delta."""
    authority = context.world.institutional_authority
    observer = authority.get_institution_for_owner(context.actor_ref)
    if observer is None or not can_actor_act_for(
        context.world, context.actor_ref, context.actor_ref,
        AuthorityScope.COMMITMENT_NEGOTIATION,
        current_month=int(context.world.month_stamp),
    ).allowed:
        raise StaleAffordanceError("institutional relationship reaction is absent or stale")
    parties = _is_eligible(
        context.world, observer.id, context.trigger_event,
        event_overlays=event_overlays,
    )
    if not parties:
        raise StaleAffordanceError("institutional relationship reaction is absent or stale")
    _validate_decision(decision_event, context, option)
    canonical_options = relationship_impact_affordances(
        context, event_overlays=event_overlays,
    )
    if not any(candidate.id == option.id and candidate == option for candidate in canonical_options):
        raise StaleAffordanceError("institutional relationship option is stale")
    params = option.parameters
    if str(params.get("observer_institution_id")) != observer.id or str(params.get("source_event_id")) != context.trigger_event.id:
        raise StaleAffordanceError("institutional relationship option does not match its evidence")
    counterpart_id = str(params.get("counterpart_institution_id", ""))
    if authority.get_institution(counterpart_id) is None or set(parties) != {observer.id, counterpart_id}:
        raise StaleAffordanceError("institutional relationship counterpart disappeared")
    delta = int(params.get("delta", 0))
    if delta not in {-6, -4, -2, 0, 2, 4, 6}:
        raise StaleAffordanceError("institutional relationship option has an invalid delta")
    valence = str(params.get("valence", ""))
    intensity = str(params.get("intensity", ""))
    if (valence, intensity, delta) not in _CHOICES:
        raise StaleAffordanceError("institutional relationship option has an invalid interpretation")
    relation_id = InstitutionalRelation.id_for(observer.id, counterpart_id)
    existing = context.world.institutional_relations.relations.get(relation_id)
    before = existing.friendliness if existing is not None else 0
    after = max(-100, min(100, before + delta))
    changed = after != before
    receipt = DomainReactionReceipt.create(
        f"institutional-relationship:{observer.id}:{context.trigger_event.id}",
        RELATIONSHIP_IMPACT_DOMAIN,
        context.trigger_event.id,
        decision="act",
        affordance_id=option.id,
        decision_event_ids=(decision_event.id,),
        completed=True,
    )
    context.world.mechanical_language.reaction_receipts[receipt.id] = receipt
    event = Event(
        context.world.month_stamp,
        (
            "An institution updated shared relationship climate after a known aid fact."
            if changed
            else "An institution assessed a known aid fact without changing shared relationship climate."
        ),
        event_type="institutional_relationship_changed" if changed else "institutional_relationship_interpreted",
        fact_kind=FactKind.STATE_TRANSITION if changed else FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION if changed else CausalOrigin.DETERMINISTIC,
        causal_payload={
            "deltas": ([StateDelta(event_id="pending", owner_kind="institutional_relation", owner_id=relation_id, aspect="friendliness", before=str(before), after=str(after), magnitude=after - before).to_dict()] if changed else []),
            "relationship_impact": {"observer_institution_id": observer.id, "counterparty_institution_id": counterpart_id, "source_event_id": context.trigger_event.id, "valence": valence, "intensity": intensity, "relation_id": relation_id},
        },
    )
    if event.causal_payload["deltas"]:
        event.causal_payload["deltas"][0]["event_id"] = event.id
    event.causal_links.extend((
        CausalLink(event_id=event.id, cause_event_id=decision_event.id, relation=CausalRelation.MOTIVATED_BY),
        CausalLink(event_id=event.id, cause_event_id=context.trigger_event.id, relation=CausalRelation.RESPONSE_TO),
    ))
    if changed:
        evidence = tuple(dict.fromkeys((
            *(existing.evidence_event_ids if existing else ()),
            event.id,
        )))
        relation = InstitutionalRelation(
            institution_a_id=min(observer.id, counterpart_id),
            institution_b_id=max(observer.id, counterpart_id),
            kind=existing.kind if existing is not None else InstitutionalRelationKind.NEUTRAL,
            friendliness=after,
            since_month=existing.since_month if existing is not None else int(context.world.month_stamp),
            evidence_event_ids=evidence,
        )
        if existing is None:
            context.world.institutional_relations.add_relation(relation, authority)
        else:
            context.world.institutional_relations.replace_relation(relation, authority)
        record_known_fact(
            context.world,
            event,
            (observer.id, counterpart_id),
        )
    return event


async def process_institutional_relationship_impacts(
    world: Any,
    *,
    current_events: list[Event],
    llm_call: Any = None,
    budget: CausalBudget | None = None,
    injected_decisions: Mapping[str, DomainDecision]
    | Callable[[str, Event], DomainDecision | None]
    | None = None,
    evaluation_budget: int = 8,
    llm_budget: int = 2,
) -> list[Event]:
    """Give each known party one bounded, independently audited reaction."""
    budget = budget or CausalBudget.from_world(world)
    produced: list[Event] = []
    overlays = {event.id: event for event in current_events}
    evaluations = 0
    llm_calls = 0
    for source in tuple(current_events):
        if source.event_type not in ELIGIBLE_EVENT_TYPES:
            continue
        for institution_id in _parties(world, source, event_overlays=overlays):
            if (
                evaluations >= max(0, int(evaluation_budget))
                or not budget.consume_propagation_step()
            ):
                return produced
            evaluations += 1
            institution = world.institutional_authority.get_institution(institution_id)
            if institution is None:
                continue
            context = RelationshipAffordanceContext(
                world,
                RELATIONSHIP_IMPACT_DOMAIN,
                institution.owner_ref,
                source,
                event_overlays=overlays,
            )
            options = DOMAIN_AFFORDANCES.compose(context)
            if not options:
                continue
            injected = (
                injected_decisions.get(institution_id)
                if isinstance(injected_decisions, Mapping)
                else injected_decisions(institution_id, source)
                if callable(injected_decisions)
                else None
            )
            test_mode = is_world_test_mode(world) or is_test_mode_enabled()
            uses_llm = (
                not test_mode
                and injected is None
                and llm_calls < max(0, int(llm_budget))
                and budget.consume_interpreter_call()
            )
            forced_maintain = injected is None and not uses_llm
            if uses_llm:
                llm_calls += 1
            decision, decision_event = await interpret_domain_affordances(
                world,
                domain=RELATIONSHIP_IMPACT_DOMAIN,
                actor_ref=institution.owner_ref,
                actor_label=institution_id,
                trigger_event=source,
                affordances=options,
                task_name="institutional_relationship_interpreter",
                template_name="institutional_relationship_interpreter.txt",
                extra_context={"institution": institutional_decision_context(
                    world, institution_id, event_overlays=tuple(overlays.values())
                )},
                llm_call=llm_call if uses_llm else None,
                force_rule=not uses_llm,
                injected_decision=injected or (
                    DomainDecision(
                        DomainDecisionKind.MAINTAIN,
                        "Test mode preserves relation climate."
                        if test_mode
                        else "No relationship interpretation budget remains.",
                    )
                    if forced_maintain else None
                ),
            )
            produced.append(decision_event)
            overlays[decision_event.id] = decision_event
            if decision.decision is DomainDecisionKind.MAINTAIN:
                record_maintained_reaction(
                    world,
                    institution_id=institution_id,
                    evidence_event=source,
                    decision_event_id=decision_event.id,
                    event_overlays=overlays,
                )
                continue
            if not budget.consume_domain_mutation():
                continue
            try:
                transition = DOMAIN_AFFORDANCES.execute(
                    context,
                    decision.selected_affordance_id or "",
                    decision_event=decision_event,
                    event_overlays=overlays,
                )
                produced.append(transition)
                overlays[transition.id] = transition
            except StaleAffordanceError:
                produced.append(stale_affordance_blocked_event(
                    context,
                    decision_event_id=decision_event.id,
                    selected_affordance_id=decision.selected_affordance_id or "",
                ))
    return produced


DOMAIN_AFFORDANCES.register_provider(
    RELATIONSHIP_IMPACT_DOMAIN,
    relationship_impact_affordances,
)
DOMAIN_AFFORDANCES.register_executor(CONTRIBUTE_ACTION, execute_relationship_impact)


__all__ = ["CONTRIBUTE_ACTION", "ELIGIBLE_EVENT_TYPES", "RELATIONSHIP_IMPACT_DOMAIN", "execute_relationship_impact", "process_institutional_relationship_impacts", "record_maintained_reaction", "relationship_impact_affordances"]

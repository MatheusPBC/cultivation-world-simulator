from types import SimpleNamespace

import pytest

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.agent_decision import AgentDecision
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.systems.domain_affordance_registry import AffordanceContext, StaleAffordanceError
from src.systems import institutional_relationship_impact as impact


class _Relations:
    def __init__(self, commitment):
        self.commitments = {commitment.id: commitment}
        self.relations = {}

    def add_relation(self, relation, _authority):
        self.relations[relation.id] = relation

    def replace_relation(self, relation, _authority):
        self.relations[relation.id] = relation


class _Knowledge:
    def __init__(self, known):
        self.known = set(known)

    def contains(self, institution_id, event_id):
        return (institution_id, event_id) in self.known

    def record(self, fact, _authority):
        self.known.add((fact.institution_id, fact.event_id))
        return fact


def _world(event):
    observer = SimpleNamespace(id="inst:city:1", owner_ref=EntityRef("region", "1"))
    counterpart = SimpleNamespace(id="inst:city:2", owner_ref=EntityRef("region", "2"))
    commitment = SimpleNamespace(id="commitment:accepted", party_ids=(observer.id, counterpart.id))
    authority = SimpleNamespace(
        get_institution_for_owner=lambda ref: observer if ref == observer.owner_ref else None,
        get_institution=lambda item: {observer.id: observer, counterpart.id: counterpart}.get(item),
    )
    return SimpleNamespace(
        month_stamp=8,
        institutional_authority=authority,
        institutional_relations=_Relations(commitment),
        institutional_knowledge=_Knowledge({(observer.id, event.id)}),
        mechanical_language=SimpleNamespace(reaction_receipts={}),
        event_manager=SimpleNamespace(get_event_by_id=lambda _event_id: None),
    )


def _accepted_event():
    return Event(
        8,
        "canonical acceptance",
        id="accepted-event",
        event_type="institutional_aid_accepted",
        causal_payload={"commitment_id": "commitment:accepted", "deltas": []},
    )


def _decision(event, option):
    decision = Event(
        8,
        "canonical relationship decision",
        id="decision-1",
        event_type="institutional_relationship_impact_interpretation_decision",
        fact_kind=FactKind.DECISION,
        render_params={
            "domain": impact.RELATIONSHIP_IMPACT_DOMAIN,
            "actor_kind": "region",
            "actor_id": "1",
        },
        causal_payload={
            "deltas": [],
            "decision": AgentDecision(
                id="decision-audit",
                month_stamp=8,
                subject_kind="region",
                subject_id="1",
                source="rule",
                considered_count=7,
                chosen_chain=[{"selected_affordance_id": option.id}],
            ).to_dict(),
            "interpretation": {
                "decision": "act",
                "selected_affordance_id": option.id,
            },
        },
    )
    decision.causal_links.append(CausalLink(
        event_id=decision.id,
        cause_event_id=event.id,
        relation=CausalRelation.RESPONSE_TO,
    ))
    return decision


def test_known_aid_fact_offers_bounded_contributions_and_records_once(monkeypatch):
    monkeypatch.setattr(impact, "can_actor_act_for", lambda *_args, **_kwargs: SimpleNamespace(allowed=True))
    event = _accepted_event()
    world = _world(event)
    context = AffordanceContext(world, impact.RELATIONSHIP_IMPACT_DOMAIN, EntityRef("region", "1"), event)

    options = impact.relationship_impact_affordances(context)

    assert {option.parameters["delta"] for option in options} == {-6, -4, -2, 0, 2, 4, 6}
    selected = next(option for option in options if option.parameters["delta"] == 6)
    decision = _decision(event, selected)
    transition = impact.execute_relationship_impact(
        context, selected, decision_event=decision
    )

    relation = next(iter(world.institutional_relations.relations.values()))
    assert relation.friendliness == 6
    assert relation.kind.value == "neutral"
    assert transition.event_type == "institutional_relationship_changed"
    assert transition.id in relation.evidence_event_ids
    assert transition.causal_payload["relationship_impact"]["valence"] == "positive"
    assert transition.causal_payload["deltas"][0]["before"] == "0"
    assert impact.relationship_impact_affordances(context) == ()
    with pytest.raises(StaleAffordanceError):
        impact.execute_relationship_impact(context, selected, decision_event=decision)


def test_forged_or_unknown_factual_input_has_no_affordance(monkeypatch):
    monkeypatch.setattr(impact, "can_actor_act_for", lambda *_args, **_kwargs: SimpleNamespace(allowed=True))
    event = _accepted_event()
    world = _world(event)
    context = AffordanceContext(world, impact.RELATIONSHIP_IMPACT_DOMAIN, EntityRef("region", "1"), event)
    assert impact.relationship_impact_affordances(context)

    forged = Event(8, "forged", id=event.id, event_type=event.event_type, causal_payload={"commitment_id": "missing", "deltas": []})
    assert impact.relationship_impact_affordances(AffordanceContext(world, impact.RELATIONSHIP_IMPACT_DOMAIN, EntityRef("region", "1"), forged)) == ()
    unknown_world = _world(event)
    unknown_world.institutional_knowledge = SimpleNamespace(contains=lambda *_args: False)
    assert impact.relationship_impact_affordances(AffordanceContext(unknown_world, impact.RELATIONSHIP_IMPACT_DOMAIN, EntityRef("region", "1"), event)) == ()

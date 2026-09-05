from types import SimpleNamespace

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.agent_decision import AgentDecision
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.server.assemblers.institutional_chain import build_institutional_chain
from src.sim.managers.event_manager import EventManager


class _Authority:
    def __init__(self, *institutions):
        self.institutions = {item.id: item for item in institutions}

    def get_institution_for_owner(self, owner_ref):
        return next((item for item in self.institutions.values() if item.owner_ref == owner_ref), None)

    def get_institution(self, institution_id):
        return self.institutions.get(institution_id)

    def offices_for(self, _institution_id):
        return ()

    def active_claims(self, _office_id):
        return ()


def test_chain_projects_personal_aggression_to_both_sects_without_attributing_a_third(monkeypatch):
    monkeypatch.setattr(
        "src.server.assemblers.institutional_chain.can_actor_act_for",
        lambda *args, **kwargs: SimpleNamespace(allowed=True),
    )
    left = SimpleNamespace(id="inst:sect:1", kind=SimpleNamespace(value="sect"), owner_ref=EntityRef("sect", "1"))
    right = SimpleNamespace(id="inst:sect:2", kind=SimpleNamespace(value="sect"), owner_ref=EntityRef("sect", "2"))
    unrelated = SimpleNamespace(id="inst:sect:3", kind=SimpleNamespace(value="sect"), owner_ref=EntityRef("sect", "3"))
    decision_audit = AgentDecision(
        id="attack-decision-audit",
        month_stamp=2,
        subject_kind="avatar",
        subject_id="avatar-a",
        chosen_chain=[{"action_name": "MutualAttack", "params": {"target_avatar": "avatar-b"}}],
        thinking="grounded",
    )
    decision = Event(
        2,
        "attack decision",
        id="attack-decision",
        event_type="attack_interpretation_decision",
        fact_kind=FactKind.DECISION,
        causal_payload={"decision": decision_audit.to_dict()},
    )
    aggression = Event(
        2,
        "avatar attacked another avatar",
        id="aggression-1",
        event_type="avatar_deliberate_attack",
        causal_origin=CausalOrigin.ACTOR_DECISION,
        related_avatars=["avatar-a", "avatar-b"],
        related_sects=[1, 2],
        causal_payload={"avatar_aggression": {
            "initiator_avatar_id": "avatar-a", "target_avatar_id": "avatar-b",
            "initiator_sect_id": "1", "target_sect_id": "2",
            "initiator_institution_id": left.id, "target_institution_id": right.id,
            "decision_event_id": decision.id, "target_selector": "avatar-b", "month": 2,
        }},
    )
    aggression.causal_links.append(CausalLink(event_id=aggression.id, cause_event_id=decision.id, relation=CausalRelation.MOTIVATED_BY))
    events = EventManager.create_in_memory()
    events.add_event(decision)
    events.add_event(aggression)
    world = SimpleNamespace(
        month_stamp=2,
        event_manager=events,
        institutional_authority=_Authority(left, right, unrelated),
        institutional_relations=SimpleNamespace(relations={}, commitments={}, memories={}),
    )

    for sect_id in ("1", "2"):
        chain = build_institutional_chain(world, owner_kind="sect", owner_id=sect_id)
        rows = {item["event_id"]: item for item in chain["events"]}
        assert set(rows) == {aggression.id}
        assert rows[aggression.id]["source_event_ids"] == [decision.id]
        assert {item["id"] for item in chain["institutions"]} == {left.id, right.id}
    unrelated_chain = build_institutional_chain(world, owner_kind="sect", owner_id="3")
    assert unrelated_chain["events"] == []

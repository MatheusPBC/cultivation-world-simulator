from types import SimpleNamespace

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import Event
from src.classes.mechanical_language import EntityRef
from src.server.assemblers.institutional_chain import build_institutional_chain
from src.sim.managers.event_manager import EventManager


class _Authority:
    def __init__(self, *institutions):
        self.institutions = {item.id: item for item in institutions}

    def get_institution_for_owner(self, owner_ref):
        return next(
            (item for item in self.institutions.values() if item.owner_ref == owner_ref),
            None,
        )

    def get_institution(self, institution_id):
        return self.institutions.get(institution_id)

    def offices_for(self, _institution_id):
        return ()

    def active_claims(self, _office_id):
        return ()


def test_peace_chain_projects_both_parties_and_excludes_unrelated_sect(monkeypatch):
    monkeypatch.setattr(
        "src.server.assemblers.institutional_chain.can_actor_act_for",
        lambda *args, **kwargs: SimpleNamespace(allowed=True),
    )
    left = SimpleNamespace(
        id="inst:sect:1", kind=SimpleNamespace(value="sect"), owner_ref=EntityRef("sect", "1")
    )
    right = SimpleNamespace(
        id="inst:sect:2", kind=SimpleNamespace(value="sect"), owner_ref=EntityRef("sect", "2")
    )
    unrelated = SimpleNamespace(
        id="inst:sect:3", kind=SimpleNamespace(value="sect"), owner_ref=EntityRef("sect", "3")
    )
    events = EventManager.create_in_memory()
    war = Event(
        3,
        "war declared",
        id="war-1",
        event_type="institutional_war_declared",
        related_sects=[1, 2],
        causal_payload={"deltas": []},
    )
    proposal = Event(
        4,
        "peace proposed",
        id="peace-proposal-1",
        event_type="institutional_peace_proposed",
        related_sects=[1, 2],
        causal_payload={
            "peace_proposal": {
                "proposer_institution_id": left.id,
                "counterparty_institution_id": right.id,
                "proposer_sect_id": "1",
                "counterparty_sect_id": "2",
                "relation_id": "relation:1:2",
                "war_event_id": war.id,
                "proposal_month": 4,
                "expires_month": 8,
            }
        },
    )
    accepted = Event(
        5,
        "peace accepted",
        id="peace-accepted-1",
        event_type="institutional_peace_accepted",
        causal_payload={"deltas": []},
    )
    accepted.causal_links.append(
        CausalLink(
            event_id=accepted.id,
            cause_event_id=proposal.id,
            relation=CausalRelation.RESPONSE_TO,
        )
    )
    decision = Event(
        5,
        "sect decision",
        id="peace-decision-1",
        event_type="institutional_peace_response_decision",
        causal_payload={
            "decision": {
                "subject_kind": "sect",
                "subject_id": "1",
                "thinking": "grounded",
                "chosen_chain": [{"selected_affordance_id": "accept_peace"}],
            }
        },
    )
    decision.causal_links.append(
        CausalLink(
            event_id=decision.id,
            cause_event_id=accepted.id,
            relation=CausalRelation.RESPONSE_TO,
        )
    )
    unrelated_event = Event(
        6,
        "unrelated sect fact",
        id="unrelated-1",
        event_type="institutional_war_declared",
        related_sects=[3, 3],
        causal_payload={"deltas": []},
    )
    for event in (war, proposal, accepted, decision, unrelated_event):
        events.add_event(event)
    world = SimpleNamespace(
        month_stamp=6,
        event_manager=events,
        institutional_authority=_Authority(left, right, unrelated),
        institutional_relations=SimpleNamespace(relations={}, commitments={}, memories={}),
    )

    left_chain = build_institutional_chain(world, owner_kind="sect", owner_id="1")
    right_chain = build_institutional_chain(world, owner_kind="sect", owner_id="2")
    unrelated_chain = build_institutional_chain(world, owner_kind="sect", owner_id="3")

    expected = {war.id, proposal.id, accepted.id, decision.id}
    for chain in (left_chain, right_chain):
        projected = {event["event_id"]: event for event in chain["events"]}
        assert set(projected) == expected
        assert projected[accepted.id]["source_event_ids"] == [proposal.id]
        assert {item["id"] for item in chain["institutions"]} >= {left.id, right.id}
    unrelated_ids = {event["event_id"] for event in unrelated_chain["events"]}
    assert unrelated_ids == {unrelated_event.id}

from types import SimpleNamespace

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import Event
from src.classes.mechanical_language import EntityRef
from src.server.assemblers import institutional_chain
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


def test_trade_proposal_and_refusal_are_visible_to_both_institutions(monkeypatch):
    monkeypatch.setattr(institutional_chain, "can_actor_act_for", lambda *args, **kwargs: SimpleNamespace(allowed=True))
    left = SimpleNamespace(id="institution:city:1", kind=SimpleNamespace(value="city"), owner_ref=EntityRef("region", "1"))
    right = SimpleNamespace(id="institution:city:2", kind=SimpleNamespace(value="city"), owner_ref=EntityRef("region", "2"))
    events = EventManager.create_in_memory()
    proposal = Event(
        4, "barter proposed", id="trade-proposal", event_type="institutional_trade_proposed",
        causal_payload={"institutional_trade_offer": {
            "proposer_institution_id": left.id,
            "counterparty_institution_id": right.id,
            "urgency": 0.8,
            "legs": [{"source_region_id": "1", "destination_region_id": "2", "resource_id": "grain", "route_id": "route:1-2", "amount": 3}, {"source_region_id": "2", "destination_region_id": "1", "resource_id": "salt", "route_id": "route:2-1", "amount": 2}],
        }},
    )
    refusal = Event(5, "barter refused", id="trade-refusal", event_type="institutional_trade_refused", causal_payload={"deltas": []})
    refusal.causal_links.append(CausalLink(event_id=refusal.id, cause_event_id=proposal.id, relation=CausalRelation.RESPONSE_TO))
    events.add_event(proposal)
    events.add_event(refusal)
    world = SimpleNamespace(
        month_stamp=5, event_manager=events,
        institutional_authority=_Authority(left, right),
        institutional_relations=SimpleNamespace(relations={}, commitments={}, memories={}),
    )

    left_chain = institutional_chain.build_institutional_chain(world, owner_kind="region", owner_id="1")
    right_chain = institutional_chain.build_institutional_chain(world, owner_kind="region", owner_id="2")

    for chain in (left_chain, right_chain):
        assert [event["event_id"] for event in chain["events"]] == ["trade-refusal", "trade-proposal"]
        assert chain["events"][1]["trade_offer"]["legs"][0]["amount"] == 3

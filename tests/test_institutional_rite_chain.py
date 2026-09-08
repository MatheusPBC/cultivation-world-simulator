from types import SimpleNamespace

from src.classes.causal_link import CausalLink
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.server.assemblers import institutional_chain
from src.sim.managers.event_manager import EventManager


class _Authority:
    def __init__(self, *institutions):
        self.institutions = {item.id: item for item in institutions}

    def get_institution(self, institution_id):
        return self.institutions.get(institution_id)

    def get_institution_for_owner(self, owner_ref):
        return next(
            (item for item in self.institutions.values() if item.owner_ref == owner_ref),
            None,
        )

    def offices_for(self, _institution_id):
        return ()

    def active_claims(self, _office_id):
        return ()


def _world():
    owner = SimpleNamespace(
        id="inst:city:1", kind=SimpleNamespace(value="city"), owner_ref=EntityRef("region", "1")
    )
    other = SimpleNamespace(
        id="inst:city:2", kind=SimpleNamespace(value="city"), owner_ref=EntityRef("region", "2")
    )
    return (
        SimpleNamespace(
            month_stamp=8,
            event_manager=EventManager.create_in_memory(),
            institutional_authority=_Authority(owner, other),
            institutional_relations=SimpleNamespace(relations={}, commitments={}, memories={}),
        ),
        owner,
        other,
    )


def _rite(event_id, sponsor_id, *, story=False, popular=False, origin=CausalOrigin.ACTOR_DECISION):
    return Event(
        8,
        "institutional rite",
        id=event_id,
        event_type="dao_rite",
        is_story=story,
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=origin,
        causal_payload={
            "dao_rite": {
                "is_sponsorship": True,
                "is_popular": popular,
                "sponsor_institution_id": sponsor_id,
            }
        },
    )


def test_sponsored_rite_is_projected_only_for_canonical_sponsor(monkeypatch):
    monkeypatch.setattr(institutional_chain, "can_actor_act_for", lambda *args, **kwargs: SimpleNamespace(allowed=True))
    world, owner, other = _world()
    source = Event(7, "pressure", id="source", event_type="institutional_aid_requested")
    rite = _rite("sponsored", owner.id)
    rite.causal_links.append(CausalLink(event_id=rite.id, cause_event_id=source.id, relation="motivated_by"))
    for event in (source, rite):
        world.event_manager.add_event(event)

    owner_chain = institutional_chain.build_institutional_chain(world, owner_kind="region", owner_id="1")
    other_chain = institutional_chain.build_institutional_chain(world, owner_kind="region", owner_id="2")

    assert [row["event_id"] for row in owner_chain["events"]] == ["sponsored"]
    assert owner_chain["events"][0]["source_event_ids"] == ["source"]
    assert other_chain["events"] == []


def test_story_popular_wrong_origin_and_unknown_sponsor_are_fail_closed(monkeypatch):
    monkeypatch.setattr(institutional_chain, "can_actor_act_for", lambda *args, **kwargs: SimpleNamespace(allowed=True))
    world, owner, _other = _world()
    events = (
        _rite("story", owner.id, story=True),
        _rite("popular", owner.id, popular=True),
        _rite("wrong-origin", owner.id, origin=CausalOrigin.DETERMINISTIC),
        _rite("unknown", "inst:city:missing"),
    )
    decision = Event(
        7,
        "institution chose another action",
        id="institution-decision",
        event_type="institutional_decision",
        fact_kind=FactKind.DECISION,
        causal_payload={"decision": {"subject_kind": "region", "subject_id": "1"}},
    )
    world.event_manager.add_event(decision)
    for event in events:
        event.causal_links.append(
            CausalLink(event_id=event.id, cause_event_id=decision.id, relation="motivated_by")
        )
        world.event_manager.add_event(event)

    chain = institutional_chain.build_institutional_chain(world, owner_kind="region", owner_id="1")

    assert [row["event_id"] for row in chain["events"] if row["event_type"] == "dao_rite"] == []

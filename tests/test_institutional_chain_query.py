from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.server.api.public_v1.query import create_public_query_router
from src.server.assemblers import institutional_chain
from src.sim.managers.event_manager import EventManager


class _Authority:
    def __init__(self, institution):
        self.institution = institution
        self.institutions = {institution.id: institution}

    def get_institution_for_owner(self, owner_ref):
        return self.institution if owner_ref == self.institution.owner_ref else None

    def get_institution(self, institution_id):
        return self.institutions.get(institution_id)

    def offices_for(self, _institution_id):
        return ()

    def active_claims(self, _office_id):
        return ()


def _world_with_events():
    institution = SimpleNamespace(
        id="institution:city:1",
        kind=SimpleNamespace(value="city"),
        owner_ref=EntityRef("region", "1"),
    )
    manager = EventManager.create_in_memory()
    for event_id in ("event-c", "event-b", "event-a"):
        manager.add_event(Event(
            5,
            event_id,
            id=event_id,
            event_type="institutional_aid_requested",
            causal_payload={"deltas": {}, "institutional_aid_request": {
                "requester_institution_id": institution.id,
                "provider_institution_id": "institution:city:2",
            }},
        ))
    decision = Event(
        6,
        "decision",
        id="decision-1",
        event_type="institutional_aid_request_interpretation_decision",
        fact_kind=FactKind.DECISION,
        causal_payload={"deltas": [], "decision": {
            "subject_kind": "region", "subject_id": "1", "thinking": "grounded",
            "chosen_chain": [{"selected_affordance_id": "request"}],
        }},
    )
    manager.add_event(decision)
    return SimpleNamespace(
        month_stamp=6,
        event_manager=manager,
        institutional_authority=_Authority(institution),
        institutional_relations=SimpleNamespace(commitments={}, memories={}),
    )


def test_event_cursor_uses_last_consumed_row_and_includes_decisions(monkeypatch):
    monkeypatch.setattr(institutional_chain, "can_actor_act_for", lambda *args, **kwargs: SimpleNamespace(allowed=True))
    world = _world_with_events()

    first = institutional_chain.build_institutional_chain(world, owner_kind="region", owner_id="1", limit=2)

    assert [item["event_id"] for item in first["events"]] == ["decision-1", "event-c"]
    assert first["events"][0]["decision"]["actor_id"] == "1"
    assert first["cursor"]["events"]["has_more"] is True
    second = institutional_chain.build_institutional_chain(
        world, owner_kind="region", owner_id="1", event_cursor=first["cursor"]["events"]["next"], limit=2,
    )
    assert [item["event_id"] for item in second["events"]] == ["event-b", "event-a"]


def test_event_scan_reaches_chain_evidence_behind_many_irrelevant_events(monkeypatch):
    monkeypatch.setattr(institutional_chain, "can_actor_act_for", lambda *args, **kwargs: SimpleNamespace(allowed=True))
    world = _world_with_events()
    for index in range(301):
        world.event_manager.add_event(Event(
            7,
            "irrelevant",
            id=f"zzz-{index:03d}",
            event_type="unrelated_event",
            causal_payload={"deltas": []},
        ))

    chain = institutional_chain.build_institutional_chain(
        world,
        owner_kind="region",
        owner_id="1",
        limit=50,
    )

    assert {item["event_id"] for item in chain["events"]} >= {
        "decision-1", "event-a", "event-b", "event-c",
    }


def test_stable_chain_cursor_works_with_persistent_event_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(institutional_chain, "can_actor_act_for", lambda *args, **kwargs: SimpleNamespace(allowed=True))
    world = _world_with_events()
    persistent = EventManager.create_with_db(tmp_path / "events.sqlite")
    for event in world.event_manager._memory_events:
        assert persistent.add_event(event)
    world.event_manager = persistent

    first = institutional_chain.build_institutional_chain(
        world, owner_kind="region", owner_id="1", limit=2,
    )
    second = institutional_chain.build_institutional_chain(
        world,
        owner_kind="region",
        owner_id="1",
        event_cursor=first["cursor"]["events"]["next"],
        limit=2,
    )

    assert [item["event_id"] for item in first["events"]] == ["decision-1", "event-c"]
    assert [item["event_id"] for item in second["events"]] == ["event-b", "event-a"]


def test_route_turns_malformed_cursor_into_bad_request():
    class _Queries:
        def get_institutional_chain(self, **_kwargs):
            raise ValueError("invalid cursor")

    router = create_public_query_router(query_service=_Queries())
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith("institutional-chain"))
    with pytest.raises(HTTPException) as error:
        endpoint(owner_kind="region", owner_id="1", event_cursor="not-a-cursor")
    assert error.value.status_code == 400


@pytest.mark.parametrize(
    ("failure", "status"),
    [(KeyError("missing"), 404), (RuntimeError("world is unavailable"), 503)],
)
def test_route_maps_missing_institution_and_world_availability(failure, status):
    class _Queries:
        def get_institutional_chain(self, **_kwargs):
            raise failure

    router = create_public_query_router(query_service=_Queries())
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith("institutional-chain"))
    with pytest.raises(HTTPException) as error:
        endpoint(owner_kind="region", owner_id="1")
    assert error.value.status_code == status

from types import SimpleNamespace

import pytest

from src.classes.causal_link import CausalRelation
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.event import Event, FactKind
from src.server.serialization import serialize_events_for_client
from src.server.services.game_queries import get_event_causal_detail
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint
from src.systems.infrastructure_site_condition import change_infrastructure_site_condition


def _world_with_site() -> SimpleNamespace:
    game_map = Map(4, 3)
    game_map.infrastructure_sites = {
        "bridge:jade": InfrastructureSite(
            id="bridge:jade",
            kind="bridge",
            name="Ponte de Jade",
            cell_refs=((1, 1),),
            region_ids=(301, 302),
            route_ids=("route:jade",),
            water_body_ids=(),
            capability_ids=("land_transport",),
            integrity=0.9,
            enabled=True,
        )
    }
    return SimpleNamespace(month_stamp=17, map=game_map)


def test_condition_change_mutates_only_site_and_records_causal_state_delta():
    world = _world_with_site()
    queue = DomainInvalidationQueue()
    routes_before = dict(world.map.routes)

    event = change_infrastructure_site_condition(
        world,
        site_id="bridge:jade",
        integrity=0.45,
        source_event_id="storm:event",
        invalidations=queue,
    )

    site = world.map.infrastructure_sites["bridge:jade"]
    assert site.integrity == 0.45
    assert site.enabled is True
    assert site.last_event_id == event.id
    assert world.map.routes == routes_before
    assert event.fact_kind is FactKind.STATE_TRANSITION
    assert event.event_type == "infrastructure_site_condition_changed"
    assert event.causal_payload["outcome"] == "changed"
    assert event.causal_payload["site_id"] == "bridge:jade"
    assert len(event.causal_payload["deltas"]) == 1
    delta = event.causal_payload["deltas"][0]
    assert delta["event_id"] == event.id
    assert delta["owner_kind"] == "infrastructure_site"
    assert delta["owner_id"] == "bridge:jade"
    assert delta["aspect"] == "integrity"
    assert delta["before"] == "0.9"
    assert delta["after"] == "0.45"
    assert delta["magnitude"] == -0.45
    assert [(link.cause_event_id, link.relation) for link in event.causal_links] == [
        ("storm:event", CausalRelation.TRIGGERED_BY)
    ]

    invalidations = queue.drain()
    assert {item.target_id for item in invalidations} == {"301", "302"}
    assert {item.domain for item in invalidations} == {"region"}
    assert all(item.layer is DomainInvalidationLayer.MECHANICAL for item in invalidations)
    assert all(item.reason is DomainInvalidationReason.INFRASTRUCTURE_CHANGED for item in invalidations)
    assert all(item.source_event_ids == (event.id,) for item in invalidations)

    updates = world.map.get_infrastructure_site_updates()
    assert len(updates) == 1
    assert updates[0]["op"] == "upsert"
    assert updates[0]["id"] == "bridge:jade"
    assert updates[0]["site"]["integrity"] == 0.45
    world.map.acknowledge_infrastructure_site_updates()
    assert world.map.get_infrastructure_site_updates() == []


def test_condition_change_can_disable_site_without_touching_integrity():
    world = _world_with_site()

    event = change_infrastructure_site_condition(
        world,
        site_id="bridge:jade",
        enabled=False,
        source_event_id="edict:event",
        invalidations=DomainInvalidationQueue(),
    )

    site = world.map.infrastructure_sites["bridge:jade"]
    assert site.integrity == 0.9
    assert site.enabled is False
    assert event.causal_payload["deltas"][0]["aspect"] == "enabled"
    assert event.causal_payload["deltas"][0]["before"] == "True"
    assert event.causal_payload["deltas"][0]["after"] == "False"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "at least one runtime field"),
        ({"integrity": 0.9}, "must change canonical state"),
        ({"integrity": -0.1}, "integrity"),
    ],
)
def test_condition_change_fails_closed_for_invalid_or_noop_updates(kwargs, message):
    world = _world_with_site()

    with pytest.raises(ValueError, match=message):
        change_infrastructure_site_condition(
            world,
            site_id="bridge:jade",
            source_event_id="source:event",
            invalidations=DomainInvalidationQueue(),
            **kwargs,
        )

    assert world.map.infrastructure_sites["bridge:jade"].integrity == 0.9
    assert world.map.get_infrastructure_site_updates() == []


def test_condition_change_fails_closed_for_missing_site_or_source():
    world = _world_with_site()

    with pytest.raises(KeyError, match="unknown infrastructure site"):
        change_infrastructure_site_condition(
            world,
            site_id="missing",
            integrity=0.2,
            source_event_id="source:event",
            invalidations=DomainInvalidationQueue(),
        )
    with pytest.raises(ValueError, match="source_event_id"):
        change_infrastructure_site_condition(
            world,
            site_id="bridge:jade",
            integrity=0.2,
            source_event_id="",
            invalidations=DomainInvalidationQueue(),
        )

    assert world.map.infrastructure_sites["bridge:jade"].integrity == 0.9


def test_condition_change_is_navigable_through_why(base_world):
    site = _world_with_site().map.infrastructure_sites["bridge:jade"]
    base_world.map.infrastructure_sites = {site.id: site}
    source = Event(base_world.month_stamp, "Uma tempestade atingiu a ponte", id="storm:event")
    base_world.event_manager.add_event(source)

    event = change_infrastructure_site_condition(
        base_world,
        site_id=site.id,
        integrity=0.4,
        source_event_id=source.id,
        invalidations=DomainInvalidationQueue(),
    )
    base_world.event_manager.add_event(event)

    payload = get_event_causal_detail(
        {"world": base_world},
        serialize_events_for_client=serialize_events_for_client,
        event_id=event.id,
        depth=1,
        limit=10,
    )

    assert payload["event"]["id"] == event.id
    assert payload["causes"][0]["relation"] == "triggered_by"
    assert payload["causes"][0]["event"]["id"] == source.id
    assert payload["deltas"][0]["owner_kind"] == "infrastructure_site"


def test_month_checkpoint_restores_site_condition_and_projection_queue(base_world):
    site = _world_with_site().map.infrastructure_sites["bridge:jade"]
    base_world.map.infrastructure_sites = {site.id: site}
    checkpoint = SimulationMonthCheckpoint.capture(base_world)

    change_infrastructure_site_condition(
        base_world,
        site_id=site.id,
        integrity=0.1,
        source_event_id="storm:event",
        invalidations=DomainInvalidationQueue(),
    )
    checkpoint.restore()

    assert base_world.map.infrastructure_sites[site.id] is site
    assert site.integrity == 0.9
    assert site.last_event_id is None
    assert base_world.map.get_infrastructure_site_updates() == []

from types import SimpleNamespace

from src.classes.causal_link import CausalRelation
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.environment.route import Route
from src.classes.mechanical_language import (
    MeasurementAvailability,
    MetricKey,
    PrimitiveDimension,
    ReadingKind,
)
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.systems.infrastructure_site_condition import (
    change_infrastructure_site_condition,
)
from src.systems.route_infrastructure_dependency import (
    process_route_infrastructure_dependencies,
    project_route_capacity_changes,
)
from src.systems.semantic_world.resolvers import available_metric_keys, resolve_metric


def _world_with_route_sites(
    *,
    first_integrity: float = 1.0,
    second_integrity: float | None = None,
) -> SimpleNamespace:
    game_map = Map(3, 1)
    game_map.set_routes(
        [Route("route:jade", (301, 302), "road", 10.0, 0.8, True)]
    )
    sites = [
        InfrastructureSite(
            id="bridge:jade",
            kind="bridge",
            name="Ponte de Jade",
            cell_refs=((1, 0),),
            region_ids=(301, 302),
            route_ids=("route:jade",),
            integrity=first_integrity,
        )
    ]
    if second_integrity is not None:
        sites.append(
            InfrastructureSite(
                id="gate:jade",
                kind="gate",
                name="Portão de Jade",
                cell_refs=((2, 0),),
                region_ids=(301, 302),
                route_ids=("route:jade",),
                integrity=second_integrity,
            )
        )
    game_map.infrastructure_sites = {site.id: site for site in sites}
    return SimpleNamespace(month_stamp=17, map=game_map)


def test_operational_capacity_is_derived_from_explicit_dependencies() -> None:
    world = _world_with_route_sites(first_integrity=0.5)
    route = world.map.routes["route:jade"]

    assert world.map.get_route_operational_capacity(route.id) == 4.0
    assert route.capacity == 10.0
    assert route.quality == 0.8


def test_disabled_or_destroyed_dependency_closes_operational_capacity() -> None:
    disabled_world = _world_with_route_sites(first_integrity=0.7)
    disabled_world.map.infrastructure_sites["bridge:jade"].update_runtime(enabled=False)
    destroyed_world = _world_with_route_sites(first_integrity=0.0)

    assert disabled_world.map.get_route_operational_capacity("route:jade") == 0.0
    assert destroyed_world.map.get_route_operational_capacity("route:jade") == 0.0


def test_operational_capacity_is_available_as_a_provenant_metric() -> None:
    world = _world_with_route_sites(first_integrity=0.5)
    site = world.map.infrastructure_sites["bridge:jade"]
    site.last_event_id = "event:bridge-damaged"
    route = world.map.routes["route:jade"]
    key = MetricKey(
        PrimitiveDimension.CAPACITY,
        "route",
        route.id,
        "transport",
        qualifiers=(("kind", "route_operational"),),
    )

    reading = resolve_metric(world, key, calculated_month=17)

    assert reading.value == 4.0
    assert reading.unit == "transport_units_per_month"
    assert reading.availability is MeasurementAvailability.MEASURABLE
    assert reading.reading_kind is ReadingKind.DERIVED
    assert reading.source_event_ids == ["event:bridge-damaged"]
    assert f"map:route:{route.id}:capacity" in reading.state_refs
    assert f"map:infrastructure_site:{site.id}:integrity" in reading.state_refs
    assert key in available_metric_keys(world, route)


def test_site_change_records_route_capacity_delta_without_mutating_route() -> None:
    world = _world_with_route_sites()
    queue = DomainInvalidationQueue()
    source = change_infrastructure_site_condition(
        world,
        site_id="bridge:jade",
        source_event_id="event:flood-impact",
        integrity=0.5,
        invalidations=queue,
    )
    queue.drain()

    events = process_route_infrastructure_dependencies(
        world,
        current_events=[source],
        invalidations=queue,
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "route_operational_capacity_changed"
    assert event.causal_payload["dependency_site_ids"] == ["bridge:jade"]
    assert len(event.causal_payload["deltas"]) == 1
    delta = event.causal_payload["deltas"][0]
    assert delta["event_id"] == event.id
    assert delta["owner_kind"] == "route"
    assert delta["owner_id"] == "route:jade"
    assert delta["aspect"] == "operational_capacity"
    assert delta["before"] == "8.0"
    assert delta["after"] == "4.0"
    assert delta["magnitude"] == -4.0
    assert [(link.cause_event_id, link.relation) for link in event.causal_links] == [
        (source.id, CausalRelation.TRIGGERED_BY)
    ]
    assert world.map.routes["route:jade"].capacity == 10.0

    invalidations = queue.drain()
    assert {item.target_id for item in invalidations} == {"301", "302"}
    assert all(item.layer is DomainInvalidationLayer.MECHANICAL for item in invalidations)
    assert all(
        item.reason is DomainInvalidationReason.ROUTE_CAPACITY_CHANGED
        for item in invalidations
    )
    assert all(item.source_event_ids == (event.id,) for item in invalidations)

    assert process_route_infrastructure_dependencies(
        world,
        current_events=[source, event],
        invalidations=DomainInvalidationQueue(),
    ) == []


def test_repair_restores_operational_capacity_from_same_dependency() -> None:
    world = _world_with_route_sites(first_integrity=0.5)
    repair = change_infrastructure_site_condition(
        world,
        site_id="bridge:jade",
        source_event_id="event:repair",
        integrity=1.0,
        invalidations=DomainInvalidationQueue(),
    )

    events = process_route_infrastructure_dependencies(
        world,
        current_events=[repair],
        invalidations=DomainInvalidationQueue(),
    )

    assert len(events) == 1
    delta = events[0].causal_payload["deltas"][0]
    assert delta["before"] == "4.0"
    assert delta["after"] == "8.0"
    assert world.map.get_route_operational_capacity("route:jade") == 8.0


def test_non_bottleneck_site_change_does_not_invent_route_effect() -> None:
    world = _world_with_route_sites(first_integrity=0.4, second_integrity=1.0)
    source = change_infrastructure_site_condition(
        world,
        site_id="gate:jade",
        source_event_id="event:minor-damage",
        integrity=0.8,
        invalidations=DomainInvalidationQueue(),
    )

    assert project_route_capacity_changes(world, [source]) == []
    assert world.map.get_route_operational_capacity("route:jade") == 3.2


def test_multiple_site_changes_preserve_causal_order() -> None:
    world = _world_with_route_sites(first_integrity=1.0, second_integrity=1.0)
    first = change_infrastructure_site_condition(
        world,
        site_id="bridge:jade",
        source_event_id="event:first",
        integrity=0.7,
        invalidations=DomainInvalidationQueue(),
    )
    second = change_infrastructure_site_condition(
        world,
        site_id="gate:jade",
        source_event_id="event:second",
        integrity=0.5,
        invalidations=DomainInvalidationQueue(),
    )

    projected = project_route_capacity_changes(world, [first, second])

    assert [(before, after) for _, _, before, after, _ in projected] == [
        (8.0, 5.6),
        (5.6, 4.0),
    ]

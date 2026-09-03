from __future__ import annotations

import pytest

from src.classes.core.world import World
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.environment.tile import TileType
from src.classes.mechanical_language import (
    ConditionDefinition,
    DerivedMetricDefinition,
    EntityRef,
    MeasurementAvailability,
    MetricKey,
    PrimitiveDimension,
    ReadingKind,
)
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.infrastructure_site_condition import change_infrastructure_site_condition
from src.systems.semantic_world.service import evaluate_semantic_world
from src.systems.semantic_world.resolvers import available_metric_keys, resolve_metric
from src.systems.time import Month, MonthStamp, Year, create_month_stamp


SITE_QUALIFIERS = (("kind", "infrastructure_site"),)


def _world_with_infrastructure_sites() -> tuple[World, CityRegion, CityRegion, Route]:
    game_map = Map(width=10, height=10)
    for x in range(4):
        game_map.create_tile(x, 0, TileType.PLAIN)

    region = CityRegion(id=101, name="Jade Basin", desc="", cors=[(0, 0), (1, 0), (2, 0)])
    other_region = CityRegion(id=202, name="Ash Coast", desc="", cors=[(3, 0)])
    game_map.regions = {region.id: region, other_region.id: other_region}
    game_map.region_cors = {
        region.id: list(region.cors),
        other_region.id: list(other_region.cors),
    }

    route = Route(
        id="route:jade-ash",
        endpoint_region_ids=(region.id, other_region.id),
        mode="land",
        capacity=11.0,
        quality=0.8,
        enabled=True,
    )
    game_map.set_routes([route])
    game_map.set_infrastructure_sites([
        InfrastructureSite(
            id="site:alpha",
            kind="custom_bridge",
            name="Alpha Bridge",
            cell_refs=((0, 0),),
            region_ids=(region.id,),
            capability_ids=("zeta_transport", "harbor"),
            integrity=0.75,
            enabled=True,
            last_event_id="event:shared",
        ),
        InfrastructureSite(
            id="site:beta",
            kind="custom_bridge",
            name="Beta Bridge",
            cell_refs=((1, 0),),
            region_ids=(region.id,),
            capability_ids=("zeta_transport", "custom_power"),
            integrity=0.25,
            enabled=True,
            last_event_id="event:shared",
        ),
        InfrastructureSite(
            id="site:disabled",
            kind="custom_bridge",
            name="Disabled Bridge",
            cell_refs=((2, 0),),
            region_ids=(region.id,),
            capability_ids=("zeta_transport",),
            integrity=0.9,
            enabled=False,
            last_event_id=None,
        ),
        InfrastructureSite(
            id="site:foreign",
            kind="custom_bridge",
            name="Foreign Bridge",
            cell_refs=((3, 0),),
            region_ids=(other_region.id,),
            capability_ids=("foreign_only",),
            integrity=1.0,
            enabled=True,
            last_event_id="event:foreign",
        ),
    ])

    world = World(
        map=game_map,
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
    )
    return world, region, other_region, route


def _site_capacity_key(region: CityRegion, capability_id: str) -> MetricKey:
    return MetricKey(
        PrimitiveDimension.CAPACITY,
        "region",
        str(region.id),
        capability_id,
        qualifiers=SITE_QUALIFIERS,
    )


def test_infrastructure_site_capacity_is_derived_from_enabled_integrity_and_provenance():
    world, region, _, _ = _world_with_infrastructure_sites()

    reading = resolve_metric(
        world,
        _site_capacity_key(region, "zeta_transport"),
        target=region,
        calculated_month=int(world.month_stamp),
    )

    assert reading.key == MetricKey(
        PrimitiveDimension.CAPACITY,
        "region",
        "101",
        "zeta_transport",
        qualifiers=(("kind", "infrastructure_site"),),
    )
    assert reading.value == pytest.approx(0.75 + 0.25 + 0.0)
    assert reading.unit == "site_equivalents"
    assert reading.availability is MeasurementAvailability.MEASURABLE
    assert reading.reading_kind is ReadingKind.DERIVED
    assert reading.state_refs == [
        "map:infrastructure_site:site:alpha:enabled",
        "map:infrastructure_site:site:alpha:integrity",
        "map:infrastructure_site:site:alpha:capability:zeta_transport",
        "map:infrastructure_site:site:beta:enabled",
        "map:infrastructure_site:site:beta:integrity",
        "map:infrastructure_site:site:beta:capability:zeta_transport",
        "map:infrastructure_site:site:disabled:enabled",
        "map:infrastructure_site:site:disabled:integrity",
        "map:infrastructure_site:site:disabled:capability:zeta_transport",
    ]
    assert reading.source_event_ids == ["event:shared"]


def test_missing_infrastructure_site_capability_is_unknown_and_unmeasurable():
    world, region, _, _ = _world_with_infrastructure_sites()

    reading = resolve_metric(
        world,
        _site_capacity_key(region, "no_corresponding_site"),
        target=region,
    )

    assert reading.value is None
    assert reading.unit == "site_equivalents"
    assert reading.availability is MeasurementAvailability.UNMEASURABLE
    assert reading.reading_kind is ReadingKind.UNKNOWN


def test_available_infrastructure_capability_keys_are_region_scoped_and_deterministic():
    world, region, other_region, _ = _world_with_infrastructure_sites()

    region_keys = [
        key
        for key in available_metric_keys(world, region)
        if key.dimension is PrimitiveDimension.CAPACITY
        and key.qualifiers == SITE_QUALIFIERS
    ]
    other_region_keys = [
        key
        for key in available_metric_keys(world, other_region)
        if key.dimension is PrimitiveDimension.CAPACITY
        and key.qualifiers == SITE_QUALIFIERS
    ]

    assert region_keys == [
        _site_capacity_key(region, "custom_power"),
        _site_capacity_key(region, "harbor"),
        _site_capacity_key(region, "zeta_transport"),
    ]
    assert other_region_keys == [_site_capacity_key(other_region, "foreign_only")]
    assert available_metric_keys(world, region) == available_metric_keys(world, region)
    assert all(key.subject_id == "101" for key in region_keys)
    assert "foreign_only" not in {key.concept_id for key in region_keys}


def test_site_condition_changes_only_the_derived_reading_not_route_economy_or_population():
    world, region, _, route = _world_with_infrastructure_sites()
    key = _site_capacity_key(region, "zeta_transport")
    route_before = route.to_dict()
    economy_before = region.economy.to_dict()
    population_before = region.population

    initial = resolve_metric(world, key, target=region)
    world.map.update_infrastructure_site_runtime("site:alpha", integrity=0.5)
    after_integrity_change = resolve_metric(world, key, target=region)
    world.map.update_infrastructure_site_runtime("site:beta", enabled=False)
    after_enabled_change = resolve_metric(world, key, target=region)

    assert initial.value == pytest.approx(1.0)
    assert after_integrity_change.value == pytest.approx(0.75)
    assert after_enabled_change.value == pytest.approx(0.5)
    assert route.to_dict() == route_before
    assert region.economy.to_dict() == economy_before
    assert region.population == population_before


@pytest.mark.asyncio
async def test_site_condition_recomputes_and_causally_activates_then_resolves_condition():
    world, region, _, _ = _world_with_infrastructure_sites()
    world.run_config_snapshot = {"semantic_discovery_budget_per_month": 0}
    world.map.update_infrastructure_site_runtime("site:alpha", integrity=0.0)
    world.map.update_infrastructure_site_runtime("site:beta", enabled=False)
    world.map.infrastructure_sites["site:beta"].last_event_id = None
    state = world.mechanical_language
    state.add_derived_definition(DerivedMetricDefinition(
        id="transport_site_capacity",
        concept_id="transport_site_capacity",
        dimension=PrimitiveDimension.CAPACITY,
        target_kind="region",
        expression={
            "op": "metric",
            "dimension": "capacity",
            "concept_id": "zeta_transport",
            "qualifiers": {"kind": "infrastructure_site"},
        },
        unit="site_equivalents",
        created_month=int(world.month_stamp),
    ))
    state.add_condition_definition(ConditionDefinition(
        id="transport_site_operational",
        concept_id="transport_site_operational",
        target_kind="region",
        metric_definition_id="transport_site_capacity",
        activate_above=0.5,
        resolve_below=0.2,
        activate_after_months=1,
        resolve_after_months=1,
        created_month=int(world.month_stamp),
    ))

    assert await evaluate_semantic_world(world) == []

    repair = change_infrastructure_site_condition(
        world,
        site_id="site:alpha",
        integrity=0.75,
        source_event_id="event:repair",
        invalidations=DomainInvalidationQueue(),
    )
    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
    activated = await evaluate_semantic_world(world)

    assert [event.event_type for event in activated] == ["semantic_condition_activated"]
    assert [link.cause_event_id for link in activated[0].causal_links] == [repair.id]
    assert {
        condition.definition_id
        for condition in state.get_active_conditions(
            EntityRef("region", str(region.id)),
            int(world.month_stamp),
        )
    } == {"transport_site_operational"}

    damage = change_infrastructure_site_condition(
        world,
        site_id="site:alpha",
        integrity=0.0,
        source_event_id="event:storm",
        invalidations=DomainInvalidationQueue(),
    )
    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
    resolved = await evaluate_semantic_world(world)

    assert [event.event_type for event in resolved] == ["semantic_condition_resolved"]
    assert {link.cause_event_id for link in resolved[0].causal_links} == {
        activated[0].id,
        damage.id,
    }

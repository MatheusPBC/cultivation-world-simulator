from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.environment.region import CultivateRegion, CityRegion, NormalRegion
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
from src.classes.core.world import World
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.infrastructure_site_condition import change_infrastructure_site_condition
from src.systems.semantic_world.resolvers import resolve_derived_metric
from src.systems.semantic_world.service import evaluate_semantic_world
from src.systems.time import MonthStamp, Month, Year, create_month_stamp


SITE_QUALIFIERS = ("kind", "infrastructure_site")
CAPABILITY_ID = "regional_transit"
METRIC_ID = "regional_site_capacity"
CONDITION_ID = "regional_site_operational"


def _regional_site_key(region: NormalRegion | CultivateRegion) -> MetricKey:
    return MetricKey(
        PrimitiveDimension.CAPACITY,
        "region",
        str(region.id),
        CAPABILITY_ID,
        qualifiers=(SITE_QUALIFIERS,),
    )


def _build_world_with_regional_sites(
    *,
    normal_integrity: float = 0.9,
    cultivate_integrity: float = 0.9,
) -> tuple[World, NormalRegion, CultivateRegion]:
    game_map = Map(width=3, height=1)
    for x in range(3):
        game_map.create_tile(x, 0, TileType.PLAIN)

    normal = NormalRegion(id=101, name="Várzea", desc="", cors=[(0, 0)])
    cultivate = CultivateRegion(id=202, name="Caverna", desc="", cors=[(1, 0)])
    game_map.regions = {normal.id: normal, cultivate.id: cultivate}
    game_map.region_cors = {
        normal.id: list(normal.cors),
        cultivate.id: list(cultivate.cors),
    }
    game_map.set_infrastructure_sites([
        InfrastructureSite(
            id="site:normal-gate",
            kind="regional_gate",
            name="Portão da Várzea",
            cell_refs=((0, 0),),
            region_ids=(normal.id,),
            capability_ids=(CAPABILITY_ID,),
            integrity=normal_integrity,
            last_event_id="event:normal-site-grounded",
        ),
        InfrastructureSite(
            id="site:cultivate-gate",
            kind="regional_gate",
            name="Portão da Caverna",
            cell_refs=((1, 0),),
            region_ids=(cultivate.id,),
            capability_ids=(CAPABILITY_ID,),
            integrity=cultivate_integrity,
            last_event_id="event:cultivate-site-grounded",
        ),
    ])
    return World(
        map=game_map,
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
    ), normal, cultivate


def _build_world_with_urban_and_nonurban_regions() -> tuple[
    World, CityRegion, NormalRegion, CultivateRegion
]:
    game_map = Map(width=3, height=1)
    for x in range(3):
        game_map.create_tile(x, 0, TileType.PLAIN)

    city = CityRegion(
        id=301,
        name="Cidade",
        desc="",
        cors=[(0, 0)],
        population=95,
        population_capacity=100,
    )
    normal = NormalRegion(id=302, name="Campo", desc="", cors=[(1, 0)])
    cultivate = CultivateRegion(id=303, name="Ruína", desc="", cors=[(2, 0)])
    game_map.regions = {region.id: region for region in (city, normal, cultivate)}
    game_map.region_cors = {
        region.id: list(region.cors) for region in (city, normal, cultivate)
    }
    return (
        World(
            map=game_map,
            month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        ),
        city,
        normal,
        cultivate,
    )


def _register_site_capacity_condition(world: World) -> None:
    state = world.mechanical_language
    state.add_derived_definition(
        DerivedMetricDefinition(
            id=METRIC_ID,
            concept_id=METRIC_ID,
            dimension=PrimitiveDimension.CAPACITY,
            target_kind="region",
            expression={
                "op": "metric",
                "dimension": "capacity",
                "concept_id": CAPABILITY_ID,
                "qualifiers": {"kind": "infrastructure_site"},
            },
            unit="site_equivalents",
            created_month=int(world.month_stamp),
        )
    )
    state.add_condition_definition(
        ConditionDefinition(
            id=CONDITION_ID,
            concept_id=CONDITION_ID,
            target_kind="region",
            metric_definition_id=METRIC_ID,
            activate_above=0.5,
            resolve_below=0.2,
            activate_after_months=1,
            resolve_after_months=1,
            created_month=int(world.month_stamp),
        )
    )


def _register_urban_density_condition(world: World) -> None:
    state = world.mechanical_language
    state.add_derived_definition(
        DerivedMetricDefinition(
            id="urban_density_ratio",
            concept_id="urban_density_ratio",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={
                "op": "divide",
                "left": {
                    "op": "metric",
                    "dimension": "load",
                    "concept_id": "settlement",
                },
                "right": {
                    "op": "metric",
                    "dimension": "capacity",
                    "concept_id": "settlement",
                },
            },
            unit="ratio",
            created_month=int(world.month_stamp),
        )
    )
    state.add_condition_definition(
        ConditionDefinition(
            id="urban_density_pressure",
            concept_id="urban_density_pressure",
            target_kind="region",
            metric_definition_id="urban_density_ratio",
            activate_above=0.8,
            resolve_below=0.6,
            activate_after_months=1,
            resolve_after_months=1,
            created_month=int(world.month_stamp),
        )
    )


@pytest.mark.asyncio
async def test_registered_regional_definition_evaluates_normal_and_cultivate_regions(
    base_world,
):
    del base_world
    world, normal, cultivate = _build_world_with_regional_sites()
    _register_site_capacity_condition(world)
    world.run_config_snapshot = {"semantic_discovery_budget_per_month": 0}
    forbidden_llm = AsyncMock(side_effect=AssertionError("regional reuse must be deterministic"))

    events = await evaluate_semantic_world(world, llm_call=forbidden_llm)

    assert {event.render_params["region_id"] for event in events} == {
        str(normal.id),
        str(cultivate.id),
    }
    assert forbidden_llm.await_count == 0
    assert all(event.event_type == "semantic_condition_activated" for event in events)
    assert all(
        world.mechanical_language.get_active_conditions(
            EntityRef("region", str(region.id)), int(world.month_stamp)
        )
        for region in (normal, cultivate)
    )


@pytest.mark.asyncio
async def test_operational_regional_site_activates_targeted_condition_with_provenance():
    world, normal, _ = _build_world_with_regional_sites()
    _register_site_capacity_condition(world)

    events = await evaluate_semantic_world(world)

    activation = next(
        event for event in events
        if event.render_params["region_id"] == str(normal.id)
    )
    instance = world.mechanical_language.get_active_conditions(
        EntityRef("region", str(normal.id)), int(world.month_stamp)
    )[0]

    assert activation.event_type == "semantic_condition_activated"
    assert instance.target_kind == "region"
    assert instance.target_id == str(normal.id)
    assert instance.source_readings[0]["key"] == MetricKey(
        PrimitiveDimension.CAPACITY,
        "region",
        str(normal.id),
        METRIC_ID,
        qualifiers=(SITE_QUALIFIERS,),
    ).to_dict()
    assert instance.source_readings[0]["derived_from"] == [
        _regional_site_key(normal).to_dict()
    ]
    assert instance.source_readings[0]["value"] == pytest.approx(0.9)
    assert instance.source_readings[0]["source_event_ids"] == [
        "event:normal-site-grounded"
    ]
    assert {link.cause_event_id for link in activation.causal_links} == {
        "event:normal-site-grounded"
    }
    assert activation.causal_payload["measurements"][0]["state_refs"]


@pytest.mark.asyncio
async def test_regional_site_damage_and_repair_change_fingerprint_and_causally_re_evaluate():
    world, normal, _ = _build_world_with_regional_sites(
        normal_integrity=0.9,
        cultivate_integrity=0.0,
    )
    _register_site_capacity_condition(world)

    activated = await evaluate_semantic_world(world)
    initial_activation = next(
        event for event in activated
        if event.render_params["region_id"] == str(normal.id)
    )
    initial_fingerprint = world.mechanical_language.fingerprints[f"region:{normal.id}"]

    damage = change_infrastructure_site_condition(
        world,
        site_id="site:normal-gate",
        integrity=0.0,
        source_event_id="event:regional-storm",
        invalidations=DomainInvalidationQueue(),
    )
    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
    resolved = await evaluate_semantic_world(world)
    damaged_fingerprint = world.mechanical_language.fingerprints[f"region:{normal.id}"]

    repair = change_infrastructure_site_condition(
        world,
        site_id="site:normal-gate",
        integrity=0.9,
        source_event_id="event:regional-repair",
        invalidations=DomainInvalidationQueue(),
    )
    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
    reactivated = await evaluate_semantic_world(world)

    assert initial_fingerprint != damaged_fingerprint
    assert [event.event_type for event in resolved] == [
        "semantic_condition_resolved"
    ]
    assert {link.cause_event_id for link in resolved[0].causal_links} == {
        initial_activation.id,
        damage.id,
    }
    assert [event.event_type for event in reactivated] == [
        "semantic_condition_activated"
    ]
    assert {link.cause_event_id for link in reactivated[0].causal_links} == {
        repair.id,
    }


@pytest.mark.asyncio
async def test_nonurban_regional_reuse_never_calls_llm_again():
    world, normal, cultivate = _build_world_with_regional_sites()
    _register_site_capacity_condition(world)
    world.run_config_snapshot = {"semantic_discovery_budget_per_month": 0}
    forbidden_llm = AsyncMock(side_effect=AssertionError("reusing a definition must not call LLM"))

    first_events = await evaluate_semantic_world(world, llm_call=forbidden_llm)
    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
    second_events = await evaluate_semantic_world(world, llm_call=forbidden_llm)

    assert forbidden_llm.await_count == 0
    assert len(first_events) == 2
    assert second_events == []
    assert all(
        world.mechanical_language.get_active_conditions(
            EntityRef("region", str(region.id)), int(world.month_stamp)
        )
        for region in (normal, cultivate)
    )


@pytest.mark.asyncio
async def test_discovered_condition_for_existing_metric_is_scheduled_for_all_regions():
    world, city, normal, cultivate = _build_world_with_urban_and_nonurban_regions()
    world.map.set_infrastructure_sites([
        InfrastructureSite(
            id="site:city-gate",
            kind="regional_gate",
            name="Portão da Cidade",
            cell_refs=((0, 0),),
            region_ids=(city.id,),
            capability_ids=(CAPABILITY_ID,),
            integrity=0.9,
        ),
        InfrastructureSite(
            id="site:field-gate",
            kind="regional_gate",
            name="Portão do Campo",
            cell_refs=((1, 0),),
            region_ids=(normal.id,),
            capability_ids=(CAPABILITY_ID,),
            integrity=0.9,
        ),
    ])
    state = world.mechanical_language
    state.add_derived_definition(
        DerivedMetricDefinition(
            id=METRIC_ID,
            concept_id=METRIC_ID,
            dimension=PrimitiveDimension.CAPACITY,
            target_kind="region",
            expression={
                "op": "metric",
                "dimension": "capacity",
                "concept_id": CAPABILITY_ID,
                "qualifiers": {"kind": "infrastructure_site"},
            },
            unit="site_equivalents",
            created_month=int(world.month_stamp),
        )
    )
    world.run_config_snapshot = {"semantic_discovery_budget_per_month": 0}
    assert await evaluate_semantic_world(world) == []

    proposal = {
        "concepts": [{
            "id": CONDITION_ID,
            "label": "regional site operational",
            "concept_kind": "condition",
        }],
        "derived_metrics": [],
        "conditions": [{
            "id": CONDITION_ID,
            "concept_id": CONDITION_ID,
            "target_kind": "region",
            "metric_definition_id": METRIC_ID,
            "activate_above": 0.5,
            "resolve_below": 0.2,
            "activate_after_months": 1,
            "resolve_after_months": 1,
        }],
        "mechanic_proposals": [],
    }
    discovery = AsyncMock(return_value=proposal)
    world.run_config_snapshot = {"semantic_discovery_budget_per_month": 2}
    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)

    events = await evaluate_semantic_world(world, llm_call=discovery)

    assert discovery.await_count == 1
    assert {event.render_params["region_id"] for event in events} == {
        str(city.id),
        str(normal.id),
    }
    assert world.mechanical_language.get_active_conditions(
        EntityRef("region", str(cultivate.id)), int(world.month_stamp)
    ) == []


@pytest.mark.asyncio
async def test_urban_definition_is_unknown_and_cannot_activate_in_nonurban_regions():
    world, _, normal, cultivate = _build_world_with_urban_and_nonurban_regions()
    _register_urban_density_condition(world)
    definition = world.mechanical_language.derived_definitions["urban_density_ratio"]

    readings = [
        resolve_derived_metric(
            world,
            definition,
            target=region,
            calculated_month=int(world.month_stamp),
            definitions=world.mechanical_language.derived_definitions,
        )
        for region in (normal, cultivate)
    ]
    events = await evaluate_semantic_world(world)

    assert all(reading.value is None for reading in readings)
    assert all(
        reading.availability is MeasurementAvailability.UNMEASURABLE
        and reading.reading_kind is ReadingKind.UNKNOWN
        for reading in readings
    )
    nonurban_events = [
        event
        for event in events
        if event.render_params["region_id"] in {str(normal.id), str(cultivate.id)}
    ]
    assert nonurban_events == []
    assert all(
        world.mechanical_language.get_active_conditions(
            EntityRef("region", str(region.id)), int(world.month_stamp)
        ) == []
        for region in (normal, cultivate)
    )
    assert world.mechanical_language.derived_definitions[
        "urban_density_ratio"
    ].reuse_contexts == ("region:301",)

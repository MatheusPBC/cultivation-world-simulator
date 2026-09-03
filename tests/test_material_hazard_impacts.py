from __future__ import annotations

import copy

import pytest

from src.classes.causal_link import CausalRelation
from src.classes.core.world import World
from src.classes.environment.climate import ClimateState, RegionalWeather
from src.classes.environment.geography import GeographyLayer, WaterBody
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.city_state import CityGovernance, CityState
from src.classes.environment.map import Map
from src.classes.environment.region import CityRegion
from src.classes.environment.regional_flood import (
    RegionalFloodOccurrence,
    RegionalFloodState,
)
from src.classes.environment.route import Route
from src.classes.environment.tile import TileType
from src.classes.event import Event, FactKind
from src.classes.hazard_impact import (
    HazardExposure,
    HazardImpactEffect,
    HazardImpactProposal,
    HazardInteractionDefinition,
)
from src.classes.mechanical_language import EntityRef
from src.classes.regional_economy import RegionalEconomyState
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.material_hazard_impacts import (
    HAZARD_EXPOSURE_PROJECTORS,
    HAZARD_INTERACTIONS,
    HAZARD_OCCURRENCE_RESOLVERS,
    apply_hazard_impact_proposal,
    process_material_hazard_impacts,
    project_flood_site_exposures,
    propose_hazard_impacts,
)
from src.systems.infrastructure_restoration import process_infrastructure_restoration
from src.systems.regional_floods import advance_regional_floods
from src.systems.route_infrastructure_dependency import (
    process_route_infrastructure_dependencies,
)
from src.systems.time import MonthStamp


def _world_and_flood() -> tuple[World, Event, RegionalFloodOccurrence]:
    game_map = Map(width=3, height=2)
    game_map.set_geography(
        GeographyLayer(
            width=3,
            height=2,
            terrain_rows=[
                [TileType.PLAIN, TileType.WATER, TileType.PLAIN],
                [TileType.PLAIN, TileType.PLAIN, TileType.PLAIN],
            ],
            elevation_rows=[[8.0, 0.0, 5.0], [9.0, 2.0, 7.0]],
            water_bodies=[
                WaterBody(
                    id="river:lowland",
                    kind="river",
                    cell_refs=((1, 0),),
                    navigable=False,
                    region_id=101,
                    flow_direction=(0, 1),
                )
            ],
        )
    )
    for y in range(game_map.height):
        for x in range(game_map.width):
            game_map.create_tile(x, y, game_map.get_terrain(x, y))
    region = CityRegion(
        id=101,
        name="Vale Baixo",
        desc="",
        cors=[(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)],
        population=400.0,
        population_capacity=500.0,
    )
    game_map.regions = {region.id: region}
    game_map.region_cors = {region.id: list(region.cors)}
    for coordinate in region.cors:
        game_map.tiles[coordinate].region = region
    game_map.set_infrastructure_sites(
        [
            InfrastructureSite(
                id="site:low-bridge",
                kind="bridge",
                name="Ponte Baixa",
                cell_refs=((1, 0),),
                region_ids=(101,),
                integrity=1.0,
            ),
            InfrastructureSite(
                id="site:hill-shrine",
                kind="shrine",
                name="Santuário da Colina",
                cell_refs=((0, 1),),
                region_ids=(101,),
                integrity=1.0,
            ),
            InfrastructureSite(
                id="site:flood-gate",
                kind="flood_gate",
                name="Comporta",
                cell_refs=((1, 0),),
                region_ids=(101,),
                capability_ids=("flood_control", "drainage"),
                integrity=1.0,
            ),
        ]
    )
    world = World(
        map=game_map,
        month_stamp=MonthStamp(11),
        playthrough_id="hazard-impact",
    )
    source = Event(
        world.month_stamp,
        "Flooding started.",
        id="event:flood-start",
        event_type="regional_flood_started",
        render_params={
            "region_id": "101",
            "region": region.name,
            "risk": 0.96,
            "hazard_kind": "regional_flood",
        },
        fact_kind=FactKind.STATE_TRANSITION,
    )
    occurrence = RegionalFloodOccurrence(
        region_id="101",
        started_month=11,
        activation_risk=0.96,
        source_event_ids=("event:rain-10", "event:rain-11"),
        last_event_id=source.id,
    )
    world.regional_flood_state.active_by_region["101"] = occurrence
    return world, source, occurrence


def test_flood_projects_spatial_exposure_without_mutating_targets() -> None:
    world, source, occurrence = _world_and_flood()
    before = {
        site_id: copy.deepcopy(site.to_dict())
        for site_id, site in world.map.infrastructure_sites.items()
    }

    exposures = project_flood_site_exposures(world, occurrence)

    assert {item.target_ref.id for item in exposures} == set(before)
    by_site = {item.target_ref.id: item for item in exposures}
    assert by_site["site:low-bridge"].exposure > by_site["site:hill-shrine"].exposure
    # Exposure is geography-owned. Capabilities reduce the effect only when the
    # registered engine law evaluates the target.
    assert by_site["site:flood-gate"].exposure == by_site["site:low-bridge"].exposure
    assert source.id in by_site["site:low-bridge"].source_event_ids
    assert world.map.infrastructure_sites["site:low-bridge"].to_dict() == before["site:low-bridge"]


def test_only_mechanically_afforded_site_is_damaged_through_its_owner() -> None:
    world, source, _ = _world_and_flood()
    population_before = world.map.regions[101].population
    economy_before = copy.deepcopy(world.map.regions[101].economy.to_dict())
    routes_before = copy.deepcopy(world.map.routes)

    events = process_material_hazard_impacts(
        world,
        current_events=[source],
        invalidations=DomainInvalidationQueue(),
    )

    assert len(events) == 1
    impact = events[0]
    assert impact.event_type == "infrastructure_site_condition_changed"
    assert impact.render_params["site_id"] == "site:low-bridge"
    assert impact.causal_payload["hazard_impact"]["proposal_type"] == "hazard_impact"
    assert "map:geography:1:0:elevation" in impact.causal_payload[
        "hazard_exposure"
    ]["state_refs"]
    assert "map:water_body:river:lowland" in impact.causal_payload[
        "hazard_exposure"
    ]["state_refs"]
    assert any(
        link.cause_event_id == source.id
        and link.relation is CausalRelation.TRIGGERED_BY
        for link in impact.causal_links
    )
    assert world.map.infrastructure_sites["site:low-bridge"].integrity < 1.0
    assert world.map.infrastructure_sites["site:hill-shrine"].integrity == 1.0
    assert world.map.infrastructure_sites["site:flood-gate"].integrity == 1.0
    assert world.map.regions[101].population == population_before
    assert world.map.regions[101].economy.to_dict() == economy_before
    assert world.map.routes == routes_before

    assert process_material_hazard_impacts(
        world,
        current_events=[source, *events],
        invalidations=DomainInvalidationQueue(),
    ) == []


def test_forged_magnitude_is_rejected_before_owner_mutation() -> None:
    world, source, occurrence = _world_and_flood()
    expected = propose_hazard_impacts(
        world,
        project_flood_site_exposures(world, occurrence)
    )[0]
    forged = HazardImpactProposal(
        hazard_kind=expected.hazard_kind,
        source_event_id=expected.source_event_id,
        target_ref=expected.target_ref,
        effect=HazardImpactEffect.REDUCE_INTEGRITY,
        magnitude=min(1.0, expected.magnitude + 0.2),
        exposure=expected.exposure,
    )

    with pytest.raises(ValueError, match="mechanical affordance"):
        apply_hazard_impact_proposal(
            world,
            forged,
            source_event=source,
            invalidations=DomainInvalidationQueue(),
        )

    assert world.map.infrastructure_sites["site:low-bridge"].integrity == 1.0


def test_typed_exposure_requires_occurrence_provenance() -> None:
    with pytest.raises(ValueError, match="include occurrence_event_id"):
        HazardExposure(
            hazard_kind="regional_flood",
            occurrence_event_id="event:flood",
            target_ref=EntityRef("infrastructure_site", "site:bridge"),
            exposure=0.8,
            state_refs=("map:site:bridge",),
            source_event_ids=("event:rain",),
        )


def test_unknown_hazard_does_not_borrow_the_flood_impact_law() -> None:
    exposure = HazardExposure(
        hazard_kind="wildfire",
        occurrence_event_id="event:fire",
        target_ref=EntityRef("infrastructure_site", "site:bridge"),
        exposure=0.95,
        state_refs=("map:infrastructure_site:site:bridge:integrity",),
        source_event_ids=("event:fire",),
    )

    world, _, _ = _world_and_flood()
    assert propose_hazard_impacts(world, [exposure]) == []


def test_any_engine_registered_hazard_traverses_the_generic_pipeline(
    monkeypatch,
) -> None:
    world, _, _ = _world_and_flood()
    source = Event(
        world.month_stamp,
        "A grounded heat wave started.",
        id="event:heatwave",
        render_params={"hazard_kind": "heatwave"},
    )
    definition = HazardInteractionDefinition(
        hazard_kind="heatwave",
        target_kind="infrastructure_site",
        threshold=0.5,
        resistance_weights=(),
        effect=HazardImpactEffect.REDUCE_INTEGRITY,
        minimum_magnitude=0.05,
        maximum_magnitude=0.10,
        curve_slope=0.5,
    )

    def resolve(_world, event):
        return object() if event.id == source.id else None

    def project(_world, _occurrence):
        return [
            HazardExposure(
                hazard_kind="heatwave",
                occurrence_event_id=source.id,
                target_ref=EntityRef("infrastructure_site", "site:hill-shrine"),
                exposure=0.8,
                state_refs=("map:infrastructure_site:site:hill-shrine:integrity",),
                source_event_ids=(source.id,),
            )
        ]

    monkeypatch.setitem(
        HAZARD_INTERACTIONS,
        ("heatwave", "infrastructure_site"),
        definition,
    )
    monkeypatch.setitem(HAZARD_OCCURRENCE_RESOLVERS, "heatwave", resolve)
    monkeypatch.setitem(HAZARD_EXPOSURE_PROJECTORS, "heatwave", project)

    events = process_material_hazard_impacts(
        world,
        current_events=[source],
        invalidations=DomainInvalidationQueue(),
    )

    assert len(events) == 1
    assert events[0].causal_payload["hazard_impact"]["hazard_kind"] == "heatwave"
    assert world.map.infrastructure_sites["site:hill-shrine"].integrity < 1.0


def test_grounded_weather_to_flood_to_site_damage_chain() -> None:
    world, _, _ = _world_and_flood()
    world.map.set_routes(
        [Route("route:lowland", (101, 102), "road", 10.0, 1.0, True)]
    )
    low_bridge = world.map.infrastructure_sites["site:low-bridge"]
    world.map.infrastructure_sites[low_bridge.id] = InfrastructureSite(
        id=low_bridge.id,
        kind=low_bridge.kind,
        name=low_bridge.name,
        cell_refs=low_bridge.cell_refs,
        region_ids=(101, 102),
        route_ids=("route:lowland",),
        integrity=low_bridge.integrity,
    )
    world.regional_flood_state = RegionalFloodState()
    world.map.update_infrastructure_site_runtime(
        "site:flood-gate",
        integrity=0.0,
        enabled=False,
        last_event_id="event:gate-failed",
        track_update=False,
    )
    flood_events = []
    for month in (10, 11):
        world.month_stamp = MonthStamp(month)
        world.climate_state = ClimateState(
            regions={
                "101": RegionalWeather(
                    region_id="101",
                    month=month,
                    precipitation=0.96,
                    soil_saturation=0.96,
                    previous_soil_saturation=0.96,
                    source_event_id=f"event:rain-{month}",
                )
            },
            last_updated_month=month,
        )
        flood_events = advance_regional_floods(
            world,
            invalidations=DomainInvalidationQueue(),
        )

    impacts = process_material_hazard_impacts(
        world,
        current_events=flood_events,
        invalidations=DomainInvalidationQueue(),
    )
    route_events = process_route_infrastructure_dependencies(
        world,
        current_events=[*flood_events, *impacts],
        invalidations=DomainInvalidationQueue(),
    )

    assert [event.event_type for event in flood_events] == [
        "regional_flood_started"
    ]
    assert [event.render_params["site_id"] for event in impacts] == [
        "site:low-bridge"
    ]
    assert impacts[0].causal_links[0].cause_event_id == flood_events[0].id
    assert world.map.infrastructure_sites["site:low-bridge"].integrity < 1.0
    assert [event.event_type for event in route_events] == [
        "route_operational_capacity_changed"
    ]
    assert route_events[0].causal_links[0].cause_event_id == impacts[0].id
    assert route_events[0].causal_payload["deltas"][0]["after"] == str(
        world.map.get_route_operational_capacity("route:lowland")
    )
    assert world.map.routes["route:lowland"].capacity == 10.0


@pytest.mark.asyncio
async def test_damage_exposes_restoration_affordance_and_recovers_route() -> None:
    world, source, _ = _world_and_flood()
    world.run_config_snapshot = {"test_mode": True}
    city = world.map.regions[101]
    city.city_state = CityState(
        governance=CityGovernance("", "", 1.0),
    )
    city.economy = RegionalEconomyState(
        stocks={"spirit_stone": 30},
        capacities={"spirit_stone": 30},
        access={"spirit_stone": 1.0},
    )
    world.map.set_routes(
        [Route("route:lowland", (101, 102), "road", 10.0, 1.0, True)]
    )
    site = world.map.infrastructure_sites["site:low-bridge"]
    world.map.infrastructure_sites[site.id] = InfrastructureSite(
        id=site.id,
        kind=site.kind,
        name=site.name,
        cell_refs=site.cell_refs,
        region_ids=(101, 102),
        route_ids=("route:lowland",),
        maintainer_ref=EntityRef("city", "101"),
        integrity=1.0,
    )

    impacts = process_material_hazard_impacts(
        world,
        current_events=[source],
        invalidations=DomainInvalidationQueue(),
    )
    damaged_integrity = world.map.infrastructure_sites[site.id].integrity
    route_down = process_route_infrastructure_dependencies(
        world,
        current_events=impacts,
        invalidations=DomainInvalidationQueue(),
    )
    restoration_events = await process_infrastructure_restoration(
        world,
        current_events=impacts,
        invalidations=DomainInvalidationQueue(),
    )
    restoration = next(
        event
        for event in restoration_events
        if event.event_type == "infrastructure_site_restored"
    )
    route_up = process_route_infrastructure_dependencies(
        world,
        current_events=[restoration],
        invalidations=DomainInvalidationQueue(),
    )

    assert route_down[0].causal_payload["deltas"][0]["magnitude"] < 0
    assert restoration.causal_payload["affordance_id"].startswith("aff-")
    assert restoration.causal_payload["integrity_improvement"] <= 0.10
    assert world.map.infrastructure_sites[site.id].integrity > damaged_integrity
    assert city.economy.stocks["spirit_stone"] < 30
    assert route_up[0].causal_payload["deltas"][0]["magnitude"] > 0
    decision_id = next(
        event.id
        for event in restoration_events
        if event.fact_kind is FactKind.DECISION
    )
    assert any(link.cause_event_id == decision_id for link in restoration.causal_links)

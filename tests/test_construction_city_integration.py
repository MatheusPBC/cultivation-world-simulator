import importlib

import pytest

from src.classes.environment.region import CityRegion
from src.run.load_map import load_cultivation_world_map
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.systems.time import MonthStamp
from src.systems.urban_capacity_project import (
    PROJECT_KIND,
    advance_urban_capacity_projects,
    can_start_urban_capacity_project,
    start_urban_capacity_project,
)


EXPECTED_RESOURCES = {
    301: ("timber", 300.0, 500.0, 20.0, 0.0, 0.90, 0.35),
    302: ("stone", 100.0, 180.0, 6.0, 0.0, 0.65, 0.75),
    303: ("timber", 150.0, 260.0, 12.0, 0.0, 0.95, 0.15),
    304: ("timber", 220.0, 360.0, 16.0, 0.0, 0.85, 0.45),
    305: ("stone", 90.0, 160.0, 5.0, 0.0, 0.90, 0.20),
}

EXPECTED_WORK_ASSETS = {
    301: ("public_works", 18.0, 0.82, 0.92),
    302: ("construction_yard", 7.0, 0.60, 0.78),
    303: ("carpenter_guild", 10.0, 0.76, 0.86),
    304: ("dock_builders", 14.0, 0.80, 0.90),
    305: ("stonewrights", 6.0, 0.68, 0.82),
}


def _official_cities():
    game_map = load_cultivation_world_map("classic")
    return [
        region
        for region in game_map.regions.values()
        if isinstance(region, CityRegion)
    ]


def test_official_cities_have_declared_construction_resources_and_work_assets():
    cities = _official_cities()

    assert {city.id for city in cities} == set(EXPECTED_RESOURCES)
    assert len({values[0] for values in EXPECTED_RESOURCES.values()}) >= 2

    for city in cities:
        resource_id, stock, capacity, production, demand, access, dependency = (
            EXPECTED_RESOURCES[city.id]
        )
        assert city.economy.project_resources == {PROJECT_KIND: resource_id}
        assert city.economy.stocks[resource_id] == stock
        assert city.economy.capacities[resource_id] == capacity
        assert city.economy.production_rates[resource_id] == production
        assert city.economy.demand_rates[resource_id] == demand
        assert city.economy.access[resource_id] == access
        assert city.economy.dependencies[resource_id] == dependency
        assert "grain" not in city.economy.project_resources

        construction_assets = [
            asset
            for asset in city.city_state.assets
            if "construction_work" in asset.capability_ids
        ]
        assert len(construction_assets) == 1
        asset = construction_assets[0]
        expected_id, expected_capacity, expected_quality, expected_integrity = (
            EXPECTED_WORK_ASSETS[city.id]
        )
        assert asset.id == expected_id
        assert asset.capacity == expected_capacity
        assert asset.quality == expected_quality
        assert asset.integrity == expected_integrity
        assert asset.district_id in {district.id for district in city.city_state.districts}


def test_pressed_city_selected_by_affordance_starts_and_reserves_without_capacity_growth(
    base_world,
):
    base_world.map = load_cultivation_world_map("classic")
    city = max(
        (
            candidate
            for candidate in base_world.map.regions.values()
            if isinstance(candidate, CityRegion)
            and can_start_urban_capacity_project(candidate)
        ),
        key=lambda candidate: candidate.population_ratio,
    )
    initial_capacity = city.population_capacity
    resource_id = city.economy.project_resources[PROJECT_KIND]
    initial_stock = city.economy.stocks[resource_id]

    event = start_urban_capacity_project(
        base_world,
        city,
        decision_event_id="decision-construction-city",
        trigger_event_id="trigger-construction-city",
    )

    project = city.city_state.capacity_projects[0]
    assert event.event_type == "urban_capacity_project_started"
    assert project.construction_resource_id == resource_id
    assert city.population_capacity == initial_capacity
    assert city.economy.stocks[resource_id] == initial_stock
    assert city.economy.reservations[project.id][resource_id] == pytest.approx(
        project.material_required
    )


def test_all_official_cities_complete_grounded_construction_exactly_once(base_world):
    base_world.map = load_cultivation_world_map("classic")
    cities = sorted(
        (
            region
            for region in base_world.map.regions.values()
            if isinstance(region, CityRegion)
        ),
        key=lambda region: region.id,
    )

    initial_capacities = {city.id: city.population_capacity for city in cities}
    for city in cities:
        event = start_urban_capacity_project(
            base_world,
            city,
            decision_event_id=f"decision-construction-{city.id}",
            trigger_event_id=f"trigger-construction-{city.id}",
        )
        assert event.event_type == "urban_capacity_project_started"

    events = advance_urban_capacity_projects(base_world)

    assert {
        int(event.render_params["region_id"])
        for event in events
        if event.event_type == "urban_capacity_project_progressed"
    } == set(EXPECTED_RESOURCES)
    max_required_months = max(
        city.city_state.capacity_projects[0].required_months for city in cities
    )
    for _ in range(1, max_required_months):
        base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
        events.extend(advance_urban_capacity_projects(base_world))

    completion_events = [
        event
        for event in events
        if event.event_type == "urban_capacity_project_completed"
    ]
    assert {
        int(event.render_params["region_id"]) for event in completion_events
    } == set(EXPECTED_RESOURCES)
    assert len(completion_events) == len(cities)

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    assert not any(
        event.event_type == "urban_capacity_project_completed"
        for event in advance_urban_capacity_projects(base_world)
    )
    for city in cities:
        project = city.city_state.capacity_projects[0]
        assert city.population_capacity == pytest.approx(
            initial_capacities[city.id] + project.capacity_increase
        )
        assert project.material_consumed == pytest.approx(project.material_required)
        assert project.id not in city.economy.reservations


def test_construction_state_survives_save_load(base_world, tmp_path):
    base_world.map = load_cultivation_world_map("classic")
    city = next(
        candidate
        for candidate in base_world.map.regions.values()
        if isinstance(candidate, CityRegion)
        and can_start_urban_capacity_project(candidate)
    )
    start_urban_capacity_project(
        base_world,
        city,
        decision_event_id="decision-save-construction",
        trigger_event_id="trigger-save-construction",
    )
    expected_economy = city.economy.to_dict()
    expected_project = city.city_state.capacity_projects[0].to_dict()

    save_path = tmp_path / "construction-city.json"
    ok, message = save_game(
        base_world,
        Simulator(base_world),
        [],
        save_path=save_path,
    )
    assert ok, message

    loaded_world, _, _ = load_game(save_path)
    loaded_city = loaded_world.map.regions[city.id]
    assert loaded_city.economy.to_dict() == expected_economy
    assert loaded_city.city_state.capacity_projects[0].to_dict() == expected_project


def test_loader_does_not_infer_project_resource_without_explicit_configuration(monkeypatch):
    load_map_module = importlib.import_module("src.run.load_map")
    monkeypatch.setitem(
        load_map_module.game_configs,
        "city_economy",
        [
            {
                "region_id": 301,
                "concept_id": "timber",
                "stock": 10,
                "capacity": 20,
                "production_rate": 1,
                "demand_rate": 0,
                "access": 1,
                "dependency": 0,
            }
        ],
    )

    city = next(
        region
        for region in load_cultivation_world_map("classic").regions.values()
        if isinstance(region, CityRegion) and region.id == 301
    )

    assert city.economy.project_resources == {}


def test_conflicting_project_resource_configuration_fails(monkeypatch):
    load_map_module = importlib.import_module("src.run.load_map")
    monkeypatch.setitem(
        load_map_module.game_configs,
        "city_economy",
        [
            {
                "region_id": 301,
                "concept_id": "timber",
                "stock": 10,
                "capacity": 20,
                "production_rate": 1,
                "demand_rate": 0,
                "access": 1,
                "dependency": 0,
                "project_kind": PROJECT_KIND,
            },
            {
                "region_id": 301,
                "concept_id": "stone",
                "stock": 10,
                "capacity": 20,
                "production_rate": 1,
                "demand_rate": 0,
                "access": 1,
                "dependency": 0,
                "project_kind": PROJECT_KIND,
            },
        ],
    )

    with pytest.raises(ValueError, match="project resource mapping"):
        load_cultivation_world_map("classic")

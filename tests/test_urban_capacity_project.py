from src.classes.environment.city_state import CityDistrict, CityGovernance, CityState, UrbanAsset
from src.classes.environment.region import CityRegion
from src.classes.regional_economy import RegionalEconomyState
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationLayer, DomainInvalidationQueue
from src.sim.simulator_engine.phase_registry import get_simulation_phases
from src.run.load_map import load_cultivation_world_map
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.systems.time import MonthStamp
from src.systems.urban_capacity_project import (
    PROJECT_KIND,
    advance_urban_capacity_projects,
    start_urban_capacity_project,
)


def _city(*, admin: float = 0.8, housing_integrity: float = 0.9) -> CityRegion:
    return CityRegion(
        id=701,
        name="Growing City",
        desc="",
        cors=[(0, 0)],
        population=110,
        population_capacity=100,
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
            assets=(
                UrbanAsset(
                    "housing-core",
                    "core",
                    ("housing",),
                    100,
                    0.8,
                    housing_integrity,
                ),
                UrbanAsset(
                    "workshop-core",
                    "core",
                    ("construction_work",),
                    10,
                    0.8,
                    0.9,
                ),
            ),
            governance=CityGovernance("dynasty", "house-1", admin),
        ),
        economy=RegionalEconomyState(
            stocks={"stone": 100.0},
            capacities={"stone": 200.0},
            access={"stone": 1.0},
            project_resources={PROJECT_KIND: "stone"},
        ),
    )


def test_capacity_project_starts_without_changing_capacity(base_world):
    city = _city()
    base_world.map.regions[city.id] = city

    event = start_urban_capacity_project(
        base_world,
        city,
        decision_event_id="decision-1",
        trigger_event_id="condition-1",
    )

    assert event.event_type == "urban_capacity_project_started"
    assert city.population_capacity == 100
    project = city.city_state.capacity_projects[0]
    assert project.status.value == "running"
    assert project.completed_months == 0
    assert project.capacity_increase > 0
    assert city.population / (city.population_capacity + project.capacity_increase) < 0.75
    assert project.last_event_id == event.id
    assert {link.cause_event_id for link in event.causal_links} == {
        "decision-1",
        "condition-1",
    }


def test_capacity_project_is_blocked_without_grounded_affordance(base_world):
    for city in (_city(admin=0), _city(housing_integrity=0)):
        before = city.population_capacity
        event = start_urban_capacity_project(
            base_world,
            city,
            decision_event_id="decision-1",
            trigger_event_id="condition-1",
        )

        assert event.event_type == "urban_capacity_project_blocked"
        assert city.city_state.capacity_projects == ()
        assert city.population_capacity == before


def test_capacity_project_duration_is_bounded_for_very_low_administration(base_world):
    city = _city(admin=0.001)

    start_urban_capacity_project(
        base_world,
        city,
        decision_event_id="decision-slow",
        trigger_event_id="condition-slow",
    )

    assert city.city_state.capacity_projects[0].required_months <= 24


def test_capacity_project_progresses_and_completes_exactly_once(base_world):
    city = _city(admin=1.0)
    base_world.map.regions[city.id] = city
    queue = DomainInvalidationQueue()
    started = start_urban_capacity_project(
        base_world,
        city,
        decision_event_id="decision-1",
        trigger_event_id="condition-1",
    )
    project = city.city_state.capacity_projects[0]
    initial_capacity = city.population_capacity

    all_events = []
    for _ in range(project.required_months):
        base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
        events = advance_urban_capacity_projects(base_world, invalidations=queue)
        all_events.extend(events)
        if city.city_state.capacity_projects[0].status.value != "completed":
            assert city.population_capacity == initial_capacity

    completed = [event for event in all_events if event.event_type == "urban_capacity_project_completed"]
    assert len(completed) == 1
    assert city.population_capacity == initial_capacity + project.capacity_increase
    assert completed[0].causal_payload["deltas"][0]["aspect"] == "population_capacity"
    assert completed[0].causal_links[0].cause_event_id != started.id
    assert any(
        item.layer is DomainInvalidationLayer.MECHANICAL
        and completed[0].id in item.source_event_ids
        for item in queue.drain()
    )

    assert advance_urban_capacity_projects(base_world, invalidations=queue) == []
    assert city.population_capacity == initial_capacity + project.capacity_increase


def test_capacity_project_stalls_once_and_resumes_causally(base_world):
    city = _city(admin=1.0)
    base_world.map.regions[city.id] = city
    started = start_urban_capacity_project(
        base_world,
        city,
        decision_event_id="decision-1",
        trigger_event_id="condition-1",
    )
    governance = city.city_state.governance
    city.city_state.governance = CityGovernance(
        governance.controller_kind,
        governance.controller_id,
        0,
    )

    stalled = advance_urban_capacity_projects(base_world)
    assert [event.event_type for event in stalled] == ["urban_capacity_project_stalled"]
    assert city.city_state.capacity_projects[0].completed_months == 0
    assert stalled[0].causal_links[0].cause_event_id == started.id
    assert advance_urban_capacity_projects(base_world) == []

    city.city_state.governance = governance
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    resumed = advance_urban_capacity_projects(base_world)
    assert [event.event_type for event in resumed[:2]] == [
        "urban_capacity_project_resumed",
        "urban_capacity_project_progressed",
    ]
    assert resumed[0].causal_links[0].cause_event_id == stalled[0].id
    assert resumed[1].causal_links[0].cause_event_id == resumed[0].id
    assert city.city_state.capacity_projects[0].completed_months == 1


def test_capacity_projects_advance_after_economy_and_before_semantic_evaluation():
    names = [phase.name for phase in get_simulation_phases()]

    assert names.index("react_economy") < names.index("advance_urban_capacity_projects")
    assert names.index("advance_urban_capacity_projects") < names.index("evaluate_semantic_world")


def test_capacity_and_in_progress_project_survive_save_load(base_world, tmp_path):
    base_world.map = load_cultivation_world_map("classic")
    city = next(
        region
        for region in base_world.map.regions.values()
        if isinstance(region, CityRegion)
        and any("housing" in asset.capability_ids for asset in region.city_state.assets)
    )
    city.city_state.assets = (*city.city_state.assets, UrbanAsset(
        "workshop-test",
        city.city_state.districts[0].id,
        ("construction_work",),
        10.0,
        1.0,
        1.0,
    ))
    city.economy.set_capacity("stone", 200.0)
    city.economy.set_stock("stone", 100.0)
    city.economy.set_access("stone", 1.0)
    city.economy.project_resources[PROJECT_KIND] = "stone"
    city.city_state.validate(city.cors)
    city.population_capacity += 17
    started = start_urban_capacity_project(
        base_world,
        city,
        decision_event_id="decision-save",
        trigger_event_id="condition-save",
    )
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    advance_urban_capacity_projects(base_world)
    expected_capacity = city.population_capacity
    expected_project = city.city_state.capacity_projects[0].to_dict()

    save_path = tmp_path / "urban-capacity.json"
    ok, message = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    assert ok, message
    loaded_world, _, _ = load_game(save_path)
    loaded_city = loaded_world.map.regions[city.id]

    assert started.event_type == "urban_capacity_project_started"
    assert loaded_city.population_capacity == expected_capacity
    assert loaded_city.city_state.capacity_projects[0].to_dict() == expected_project

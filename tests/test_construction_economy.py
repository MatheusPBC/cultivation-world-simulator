from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import inspect

import pytest

from src.classes.environment.city_state import (
    CityDistrict,
    CityGovernance,
    CityState,
    UrbanAsset,
)
from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.regional_economy import RegionalEconomyState
from src.classes.environment.urban_capacity_project import UrbanCapacityProjectStatus
from src.systems.regional_economy import phase_update_regional_economy
from src.systems.resource_transfer import resolve_resource_transfer
from src.systems.time import MonthStamp
from src.systems.urban_capacity_project import (
    PROJECT_KIND,
    advance_urban_capacity_projects,
    can_start_urban_capacity_project,
    start_urban_capacity_project,
)


RESOURCE = "stone"


def _city(
    city_id: int,
    *,
    stock: float = 40.0,
    access: float = 1.0,
    administration: float = 1.0,
    housing: bool = True,
    housing_integrity: float = 1.0,
    construction_work: bool = True,
    work_capacity: float = 10.0,
    work_integrity: float = 1.0,
    resource_declared: bool = True,
    project_resource: bool = True,
    demand: float = 0.0,
) -> CityRegion:
    economy = RegionalEconomyState(
        stocks={RESOURCE: stock} if resource_declared else {},
        capacities={RESOURCE: 100.0} if resource_declared else {},
        demand_rates={RESOURCE: demand} if resource_declared else {},
        access={RESOURCE: access} if resource_declared else {},
        project_resources={PROJECT_KIND: RESOURCE} if project_resource else {},
    )
    assets = []
    if housing:
        assets.append(UrbanAsset("housing", "core", ("housing",), 100.0, 1.0, housing_integrity))
    if construction_work:
        assets.append(
            UrbanAsset(
                "workshop",
                "core",
                ("construction_work",),
                work_capacity,
                1.0,
                work_integrity,
            )
        )
    return CityRegion(
        id=city_id,
        name=f"Synthetic city {city_id}",
        desc="",
        cors=[(city_id % 10, city_id % 10)],
        population=50.0,
        population_capacity=100.0,
        economy=economy,
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((city_id % 10, city_id % 10),), 1.0),),
            assets=tuple(assets),
            governance=CityGovernance("dynasty", f"house-{city_id}", administration),
        ),
    )


def _start(world, city: CityRegion):
    return start_urban_capacity_project(
        world,
        city,
        decision_event_id=f"decision-{city.id}",
        trigger_event_id=f"trigger-{city.id}",
    )


def _project(city: CityRegion):
    return city.city_state.capacity_projects[0]


def test_reservations_conserve_stock_and_distinguish_unknown_from_zero():
    economy = RegionalEconomyState(stocks={RESOURCE: 10.0, "empty": 0.0})

    assert economy.available_stock(RESOURCE) == 10.0
    assert economy.available_stock("empty") == 0.0
    assert economy.available_stock("unknown") is None

    economy.reserve_stock("project-a", RESOURCE, 6.0)
    before_failed_reserve = deepcopy(economy.to_dict())
    with pytest.raises((KeyError, ValueError)):
        economy.reserve_stock("project-b", RESOURCE, 5.0)

    assert economy.to_dict() == before_failed_reserve
    assert economy.stocks[RESOURCE] == 10.0
    assert economy.available_stock(RESOURCE) == 4.0
    assert economy.reservations == {"project-a": {RESOURCE: 6.0}}


def test_fractional_reservations_share_one_epsilon_for_reserve_and_consume():
    economy = RegionalEconomyState(stocks={RESOURCE: 0.3})

    for index in range(3):
        economy.reserve_stock(f"project-{index}", RESOURCE, 0.1)
    for index in range(3):
        economy.consume_reserved_stock(f"project-{index}", RESOURCE, 0.1)

    assert economy.available_stock(RESOURCE) == pytest.approx(0.0)
    assert economy.stocks[RESOURCE] == pytest.approx(0.0)
    assert economy.reservations == {}


def test_change_stock_and_production_reject_unknown_stock_concepts(base_world):
    economy = RegionalEconomyState(
        capacities={RESOURCE: 10.0},
        production_rates={RESOURCE: 1.0},
    )
    city = _city(9050)
    city.economy = economy
    base_world.map.regions[city.id] = city

    with pytest.raises(KeyError):
        economy.change_stock(RESOURCE, 1.0)

    assert phase_update_regional_economy(base_world) == []
    assert RESOURCE not in economy.stocks


def test_regional_economy_deserialization_is_closed_and_requires_all_maps():
    expected_keys = {
        "stocks",
        "capacities",
        "production_rates",
        "demand_rates",
        "access",
        "dependencies",
        "reservations",
        "project_resources",
    }
    payload = RegionalEconomyState(
        stocks={RESOURCE: 1.0},
        project_resources={PROJECT_KIND: RESOURCE},
    ).to_dict()
    assert set(payload) == expected_keys

    for invalid in (
        None,
        {key: value for key, value in payload.items() if key != "project_resources"},
        {**payload, "unknown": {}},
        {**payload, "stocks": []},
    ):
        with pytest.raises((TypeError, ValueError)):
            RegionalEconomyState.from_dict(invalid)


def test_start_public_api_has_no_resource_override():
    assert "construction_resource_id" not in inspect.signature(
        start_urban_capacity_project
    ).parameters


def test_start_reserves_material_without_capacity_growth_and_persists_v1_fields(base_world):
    city = _city(9101)
    base_world.map.regions[city.id] = city
    initial_stock = city.economy.stocks[RESOURCE]
    initial_capacity = city.population_capacity

    event = _start(base_world, city)
    project = _project(city)

    assert event.event_type == "urban_capacity_project_started"
    assert city.economy.stocks[RESOURCE] == initial_stock
    assert city.population_capacity == initial_capacity
    assert project.construction_resource_id == RESOURCE
    assert project.construction_work_asset_id == "workshop"
    assert project.material_required > 0
    assert project.material_consumed == 0
    assert project.last_processed_month is None
    assert city.economy.reservations[project.id][RESOURCE] == project.material_required
    assert can_start_urban_capacity_project(city) is False
    assert [delta["aspect"] for delta in event.causal_payload["deltas"]] == [
        f"resource_reservation:{project.id}:{RESOURCE}",
        "urban_capacity_project_status",
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"housing": False},
        {"housing_integrity": 0.0},
        {"construction_work": False},
        {"work_capacity": 0.0},
        {"work_integrity": 0.0},
        {"administration": 0.0},
        {"resource_declared": False},
        {"project_resource": False},
        {"access": 0.0},
        {"stock": 0.0},
    ],
)
def test_start_failure_leaves_project_and_reservation_unchanged(base_world, changes):
    city = _city(9200 + len(changes), **changes)
    base_world.map.regions[city.id] = city
    before = deepcopy(city.economy.to_dict())

    assert can_start_urban_capacity_project(city) is False
    event = _start(base_world, city)

    assert event.event_type == "urban_capacity_project_blocked"
    assert city.city_state.capacity_projects == ()
    assert city.economy.to_dict() == before


def test_can_start_and_start_share_the_same_complete_affordance(base_world):
    city = _city(9250)
    base_world.map.regions[city.id] = city

    assert can_start_urban_capacity_project(city) is True
    assert _start(base_world, city).event_type == "urban_capacity_project_started"


def test_start_releases_reservation_if_project_attachment_fails(base_world, monkeypatch):
    import src.systems.urban_capacity_project as project_system

    city = _city(9251)
    base_world.map.regions[city.id] = city
    before = deepcopy(city.economy.to_dict())

    def fail_attachment(*_args, **_kwargs):
        raise RuntimeError("forced attachment failure")

    monkeypatch.setattr(project_system, "_append_project", fail_attachment, raising=False)

    with pytest.raises(RuntimeError, match="forced attachment failure"):
        _start(base_world, city)

    assert city.city_state.capacity_projects == ()
    assert city.economy.to_dict() == before


def test_advance_consumes_reserved_tranche_once_per_world_month(base_world):
    city = _city(9301)
    base_world.map.regions[city.id] = city
    _start(base_world, city)
    project = _project(city)
    stock_before = city.economy.stocks[RESOURCE]

    first = advance_urban_capacity_projects(base_world)
    after_first = _project(city)
    second = advance_urban_capacity_projects(base_world)

    assert [event.event_type for event in first] == ["urban_capacity_project_progressed"]
    assert second == []
    assert after_first.material_consumed > 0
    assert city.economy.stocks[RESOURCE] == stock_before - after_first.material_consumed
    assert after_first.last_processed_month == int(base_world.month_stamp)
    assert city.economy.reservations[project.id][RESOURCE] == pytest.approx(
        project.material_required - after_first.material_consumed
    )
    assert [delta["aspect"] for delta in first[0].causal_payload["deltas"]] == [
        f"resource_stock:{RESOURCE}",
        f"resource_reservation:{project.id}:{RESOURCE}",
        "urban_capacity_project_material",
        "urban_capacity_project_progress",
    ]


def test_advance_stalls_once_without_consumption_then_resumes(base_world):
    city = _city(9401)
    base_world.map.regions[city.id] = city
    _start(base_world, city)
    governance = city.city_state.governance
    stock_before = city.economy.stocks[RESOURCE]
    city.city_state.governance = replace(governance, administrative_capacity=0.0)

    stalled = advance_urban_capacity_projects(base_world)
    stalled_again = advance_urban_capacity_projects(base_world)

    assert [event.event_type for event in stalled] == ["urban_capacity_project_stalled"]
    assert stalled_again == []
    assert _project(city).material_consumed == 0
    assert city.economy.stocks[RESOURCE] == stock_before

    city.city_state.governance = governance
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    resumed = advance_urban_capacity_projects(base_world)

    assert [event.event_type for event in resumed] == [
        "urban_capacity_project_resumed",
        "urban_capacity_project_progressed",
    ]
    assert _project(city).material_consumed > 0


@pytest.mark.parametrize(
    ("corruption", "expected_reason"),
    [
        ("missing", "construction_reservation_missing"),
        ("partial", "construction_reservation_quantity_mismatch"),
        ("wrong_resource", "construction_reservation_resource_mismatch"),
        ("extra_resource", "construction_reservation_extra_resources"),
    ],
)
def test_invalid_active_reservation_stalls_causally_without_mutation_and_can_resume(
    base_world,
    corruption,
    expected_reason,
):
    city = _city(9450)
    base_world.map.regions[city.id] = city
    _start(base_world, city)
    project = _project(city)
    capacity_before = city.population_capacity

    if corruption == "missing":
        city.economy.release_reservation(project.id)
    elif corruption == "partial":
        city.economy.reservations[project.id][RESOURCE] = project.material_required / 2
    else:
        city.economy.stocks["timber"] = project.material_required
        city.economy.capacities["timber"] = project.material_required
        city.economy.access["timber"] = 1.0
        city.economy.reservations[project.id] = {
            "timber": project.material_required,
        }
        if corruption == "extra_resource":
            city.economy.reservations[project.id][RESOURCE] = project.material_required

    stock_before = deepcopy(city.economy.stocks)

    stalled = advance_urban_capacity_projects(base_world)
    stalled_again = advance_urban_capacity_projects(base_world)

    assert [event.event_type for event in stalled] == ["urban_capacity_project_stalled"]
    assert stalled[0].causal_payload["reason"] == expected_reason
    assert stalled_again == []
    assert _project(city).status is UrbanCapacityProjectStatus.STALLED
    assert _project(city).material_consumed == 0
    assert city.economy.stocks == stock_before
    assert city.population_capacity == capacity_before

    city.economy.release_reservation(project.id)
    city.economy.reserve_stock(
        project.id,
        project.construction_resource_id,
        project.material_required - project.material_consumed,
    )
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)

    resumed = advance_urban_capacity_projects(base_world)

    assert [event.event_type for event in resumed] == [
        "urban_capacity_project_resumed",
        "urban_capacity_project_progressed",
    ]
    assert _project(city).status is UrbanCapacityProjectStatus.RUNNING
    assert _project(city).material_consumed > 0


def test_completion_consumes_all_reserved_material_cleans_up_and_increases_capacity_once(base_world):
    city = _city(9501)
    base_world.map.regions[city.id] = city
    _start(base_world, city)
    project = _project(city)
    initial_capacity = city.population_capacity
    required = project.material_required

    completion = None
    for _ in range(project.required_months):
        base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
        events = advance_urban_capacity_projects(base_world)
        completion = next(
            (event for event in events if event.event_type == "urban_capacity_project_completed"),
            completion,
        )

    finished = _project(city)
    capacity_after_completion = city.population_capacity
    same_month = advance_urban_capacity_projects(base_world)

    assert finished.status.value == "completed"
    assert finished.material_consumed == required
    assert finished.last_processed_month == int(base_world.month_stamp)
    assert RESOURCE not in city.economy.reservations.get(finished.id, {})
    assert city.economy.stocks[RESOURCE] == pytest.approx(40.0 - required)
    assert capacity_after_completion == initial_capacity + finished.capacity_increase
    assert same_month == []
    assert city.population_capacity == capacity_after_completion
    assert completion is not None
    assert [delta["aspect"] for delta in completion.causal_payload["deltas"]] == [
        "population_capacity",
        "urban_capacity_project_status",
    ]


def test_demand_and_transfer_use_available_stock_without_spending_reservations(base_world):
    source = _city(9601, stock=10.0)
    destination = _city(9602, stock=0.0, demand=10.0)
    base_world.map.regions.update({source.id: source, destination.id: destination})
    source.economy.reserve_stock("construction-a", RESOURCE, 6.0)
    base_world.map.set_routes([Route("route-a", (source.id, destination.id), "road", 10.0, 1.0, True)])

    phase_update_regional_economy(base_world)
    assert source.economy.stocks[RESOURCE] == 10.0

    transfer = resolve_resource_transfer(
        base_world,
        destination=destination,
        resource_id=RESOURCE,
        decision_event_id="decision-transfer",
    )

    assert transfer.event_type == "regional_resource_transfer_completed"
    assert source.economy.stocks[RESOURCE] == 6.0
    assert source.economy.available_stock(RESOURCE) == 0.0
    assert source.economy.reservations["construction-a"][RESOURCE] == 6.0


def test_projects_and_cities_keep_reservations_isolated(base_world):
    first_city = _city(9701)
    second_city = _city(9702)
    base_world.map.regions.update({first_city.id: first_city, second_city.id: second_city})

    _start(base_world, first_city)
    _start(base_world, second_city)
    first_project = _project(first_city)
    second_project = _project(second_city)
    second_reserved = second_city.economy.reservations[second_project.id][RESOURCE]

    first_city.economy.release_reservation(first_project.id)

    assert first_project.id not in first_city.economy.reservations
    assert second_city.economy.reservations[second_project.id][RESOURCE] == second_reserved
    assert second_city.economy.stocks[RESOURCE] == 40.0

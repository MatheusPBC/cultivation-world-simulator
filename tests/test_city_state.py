import json

import pytest

from src.classes.celestial_dao import DaoTradition
from src.classes.environment.city_state import (
    CityDistrict,
    CityGovernance,
    CityState,
    UrbanAsset,
    UrbanPopulationGroup,
    UrbanServiceDemand,
)
from src.classes.environment.urban_capacity_project import (
    UrbanCapacityProject,
    UrbanCapacityProjectStatus,
)
from src.classes.environment.region import CityRegion
from src.classes.mechanical_language import MetricKey, PrimitiveDimension, ReadingKind
from src.run.load_map import load_cultivation_world_map
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.systems.semantic_world.resolvers import available_metric_keys, resolve_metric


def _state() -> CityState:
    return CityState(
        districts=(
            CityDistrict("core", "market", ((0, 0),), 0.75),
            CityDistrict("outer", "residential", ((1, 0),), 0.25),
        ),
        assets=(
            UrbanAsset("housing-core", "core", ("housing",), 90.0, 0.8, 0.9),
            UrbanAsset("water-core", "core", ("clean_water",), 100.0, 0.9, 1.0),
            UrbanAsset("workshop-core", "core", ("construction_work",), 10.0, 0.8, 0.9),
        ),
        service_demands=(UrbanServiceDemand("clean_water", 1.0),),
        population_groups=(
            UrbanPopulationGroup("commoners", 0.8, {"clean_water": 0.75}),
            UrbanPopulationGroup("cultivators", 0.2, {"clean_water": 1.5}),
        ),
        governance=CityGovernance("dynasty", "house-1", 0.7),
    )


def _capacity_project(
    *,
    project_id: str = "project-1",
    status: UrbanCapacityProjectStatus = UrbanCapacityProjectStatus.RUNNING,
    completed_months: int = 2,
    completed_month: int | None = None,
) -> UrbanCapacityProject:
    return UrbanCapacityProject(
        id=project_id,
        kind="settlement_capacity_expansion",
        status=status,
        housing_asset_id="housing-core",
        construction_resource_id="stone",
        construction_work_asset_id="workshop-core",
        started_month=10,
        required_months=4,
        completed_months=completed_months,
        capacity_increase=25.0,
        material_required=25.0,
        material_consumed=25.0 if status is UrbanCapacityProjectStatus.COMPLETED else 0.0,
        motivation_event_ids=("condition-1", "decision-1"),
        last_event_id="project-event-1",
        last_processed_month=None,
        completed_month=completed_month,
    )


def test_urban_capacity_project_has_strict_json_round_trip():
    project = _capacity_project()

    payload = project.to_dict()

    assert payload == {
        "id": "project-1",
        "kind": "settlement_capacity_expansion",
        "status": "running",
        "housing_asset_id": "housing-core",
        "construction_resource_id": "stone",
        "construction_work_asset_id": "workshop-core",
        "started_month": 10,
        "required_months": 4,
        "completed_months": 2,
        "capacity_increase": 25.0,
        "material_required": 25.0,
        "material_consumed": 0.0,
        "motivation_event_ids": ["condition-1", "decision-1"],
        "last_event_id": "project-event-1",
        "last_processed_month": None,
        "completed_month": None,
    }
    json.dumps(payload, allow_nan=False)
    assert UrbanCapacityProject.from_dict(payload) == project


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"kind": "new_kind"}, "kind"),
        ({"started_month": -1}, "started_month"),
        ({"required_months": 0}, "required_months"),
        ({"completed_months": 5}, "completed_months"),
        ({"capacity_increase": 0}, "capacity_increase"),
        ({"motivation_event_ids": ()}, "motivation_event_ids"),
        ({"last_event_id": ""}, "last_event_id"),
        ({"status": UrbanCapacityProjectStatus.COMPLETED}, "completed_month"),
        ({"completed_month": 20}, "completed_month"),
    ],
)
def test_urban_capacity_project_rejects_invalid_invariants(changes, message):
    values = {
        "id": "project-1",
        "kind": "settlement_capacity_expansion",
        "status": UrbanCapacityProjectStatus.RUNNING,
        "housing_asset_id": "housing-core",
        "construction_resource_id": "stone",
        "construction_work_asset_id": "workshop-core",
        "started_month": 10,
        "required_months": 4,
        "completed_months": 2,
        "capacity_increase": 25.0,
        "material_required": 25.0,
        "material_consumed": 0.0,
        "motivation_event_ids": ("condition-1",),
        "last_event_id": "project-event-1",
        "last_processed_month": None,
        "completed_month": None,
    }
    values.update(changes)

    with pytest.raises((TypeError, ValueError), match=message):
        UrbanCapacityProject(**values)


def test_completed_urban_capacity_project_requires_complete_progress():
    with pytest.raises(ValueError, match="completed_months"):
        _capacity_project(
            status=UrbanCapacityProjectStatus.COMPLETED,
            completed_months=3,
            completed_month=14,
        )

    completed = _capacity_project(
        status=UrbanCapacityProjectStatus.COMPLETED,
        completed_months=4,
        completed_month=14,
    )
    assert completed.status is UrbanCapacityProjectStatus.COMPLETED
    assert completed.completed_month == 14


def test_city_state_persists_capacity_projects_and_validates_ownership():
    state = CityState(
        districts=_state().districts,
        assets=_state().assets,
        governance=_state().governance,
        capacity_projects=(_capacity_project(),),
    )

    payload = state.to_dict()

    assert payload["capacity_projects"] == [_capacity_project().to_dict()]
    restored = CityState.from_dict(payload, city_tiles=((0, 0), (1, 0)))
    assert restored == state

    invalid = CityState(
        districts=state.districts,
        assets=state.assets,
        governance=state.governance,
        capacity_projects=(
            UrbanCapacityProject(
                id="project-2",
                kind="settlement_capacity_expansion",
                status=UrbanCapacityProjectStatus.RUNNING,
                housing_asset_id="missing-asset",
                construction_resource_id="stone",
                construction_work_asset_id="workshop-core",
                started_month=10,
                required_months=4,
                completed_months=0,
                capacity_increase=25.0,
                material_required=25.0,
                material_consumed=0.0,
                motivation_event_ids=("condition-2",),
                last_event_id="project-event-2",
                last_processed_month=None,
            ),
        ),
    )
    with pytest.raises(ValueError, match="housing asset"):
        invalid.validate()


def test_city_state_rejects_duplicate_active_capacity_projects():
    state = CityState(
        districts=_state().districts,
        assets=_state().assets,
        governance=_state().governance,
        capacity_projects=(_capacity_project(), _capacity_project(project_id="project-2")),
    )

    with pytest.raises(ValueError, match="active capacity projects"):
        state.validate()


def test_city_state_requires_capacity_projects_in_serialized_payload():
    payload = _state().to_dict()
    del payload["capacity_projects"]

    with pytest.raises(ValueError, match="missing"):
        CityState.from_dict(payload)


def test_default_and_profile_city_state_have_no_capacity_projects():
    default = CityState.default_for_region(((0, 0),))
    profile = CityState.from_profile_dict(
        {
            "districts": [{"id": "core", "kind": "core", "population_weight": 1.0}],
            "assets": [],
            "governance": {
                "controller_kind": "",
                "controller_id": "",
                "administrative_capacity": 0.0,
            },
        },
        city_tiles=((0, 0),),
    )

    assert default.capacity_projects == ()
    assert profile.capacity_projects == ()


def test_city_state_serialization_is_json_safe_and_district_population_is_derived():
    state = _state()

    payload = state.to_dict()
    json.dumps(payload, allow_nan=False)
    restored = CityState.from_dict(payload, city_tiles=((0, 0), (1, 0)))

    assert restored == state
    assert state.district_population("core", 80.0) == pytest.approx(60.0)
    assert state.district_population("outer", 80.0) == pytest.approx(20.0)


@pytest.mark.parametrize(
    "state, city_tiles, message",
    [
        (
            CityState(
                districts=(
                    CityDistrict("same", "a", ((0, 0),), 0.5),
                    CityDistrict("same", "b", ((1, 0),), 0.5),
                )
            ),
            ((0, 0), (1, 0)),
            "district ids",
        ),
        (
            CityState(
                districts=(
                    CityDistrict("a", "a", ((0, 0),), 0.5),
                    CityDistrict("b", "b", ((0, 0),), 0.5),
                )
            ),
            ((0, 0),),
            "overlap",
        ),
        (
            CityState(
                districts=(CityDistrict("a", "a", ((0, 0),), 0.4),)
            ),
            ((0, 0),),
            "weights",
        ),
        (
            CityState(
                districts=(CityDistrict("a", "a", ((0, 0),), 1.0),),
                assets=(UrbanAsset("asset", "missing", ("housing",), 1.0, 0.5, 0.5),),
            ),
            ((0, 0),),
            "district",
        ),
    ],
)
def test_city_state_rejects_invalid_relationships(state, city_tiles, message):
    with pytest.raises(ValueError, match=message):
        state.validate(city_tiles)


def test_city_state_rejects_invalid_asset_ranges():
    with pytest.raises(ValueError, match="quality"):
        UrbanAsset("asset", "core", ("housing",), 1.0, 1.1, 0.5)
    with pytest.raises(ValueError, match="integrity"):
        UrbanAsset("asset", "core", ("housing",), 1.0, 0.5, -0.1)
    with pytest.raises(ValueError, match="capacity"):
        UrbanAsset("asset", "core", ("housing",), float("nan"), 0.5, 0.5)


@pytest.mark.parametrize("map_id", ["classic", "island_seas", "mountain_frontier"])
def test_all_current_cities_load_explicit_map_independent_urban_profiles(map_id):
    game_map = load_cultivation_world_map(map_id)

    cities = [game_map.regions[region_id] for region_id in range(301, 306)]
    assert all(city.city_state.districts for city in cities)
    assert all(city.city_state.assets for city in cities)
    assert all(
        set(asset.capability_ids)
        & {
            "housing",
            "sanitation",
            "clean_water",
            "security",
            "healing",
            "administration",
            "construction_work",
        }
        for city in cities
        for asset in city.city_state.assets
    )
    for city in cities:
        city.city_state.validate(city.cors)


def test_city_state_and_dao_tradition_round_trip(base_world, tmp_path):
    city = CityRegion(
        id=301,
        name="Save City",
        desc="",
        cors=[(0, 0), (1, 0)],
        population=88.8,
        population_capacity=120.0,
        city_state=_state(),
        dao_tradition=DaoTradition.MERCY,
    )
    base_world.map.regions[city.id] = city
    base_world.map.region_cors[city.id] = city.cors
    for coordinate in city.cors:
        base_world.map.tiles[coordinate].region = city
    base_world.run_config_snapshot = {
        "content_locale": "zh-CN",
        "map_id": "classic",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.01,
        "world_lore": "",
    }
    save_path = tmp_path / "city_state_save.json"

    success, _ = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    assert success
    with save_path.open(encoding="utf-8") as handle:
        saved = json.load(handle)
    saved_city = saved["world"]["regions_status"]["301"]
    assert saved_city["city_state"] == _state().to_dict()
    assert saved_city["dao_tradition"] == DaoTradition.MERCY.value

    loaded_world, _, _ = load_game(save_path)
    loaded_city = loaded_world.map.regions[301]
    assert loaded_city.city_state == _state()
    assert loaded_city.dao_tradition is DaoTradition.MERCY


def test_urban_capability_quality_is_discovered_from_assets_not_a_fixed_catalog(base_world):
    city = CityRegion(
        id=399,
        name="Dynamic City",
        desc="",
        cors=[(0, 0), (1, 0)],
        city_state=CityState(
            districts=(CityDistrict("core", "mixed", ((0, 0), (1, 0)), 1.0),),
            assets=(
                UrbanAsset(
                    "lotus-clinic",
                    "core",
                    ("black_lotus_healing",),
                    10.0,
                    0.8,
                    0.5,
                ),
            ),
        ),
    )
    base_world.map.regions[city.id] = city
    key = MetricKey(
        PrimitiveDimension.QUALITY,
        "region",
        str(city.id),
        "black_lotus_healing",
    )

    assert key in available_metric_keys(city)
    reading = resolve_metric(base_world, key, target=city, calculated_month=12)
    assert reading.value == pytest.approx(0.4)
    assert reading.unit == "ratio"
    assert reading.reading_kind is ReadingKind.DERIVED
    assert reading.state_refs == [
        "region:399:urban_asset:lotus-clinic:quality_integrity"
    ]

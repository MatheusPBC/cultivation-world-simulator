import json

import pytest

from src.classes.environment.city_state import (
    CityDistrict,
    CityState,
    UrbanPopulationGroup,
    UrbanServiceDemand,
)
from src.run.load_map import load_cultivation_world_map


def _state() -> CityState:
    return CityState(
        districts=(CityDistrict("core", "mixed", ((0, 0),), 1.0),),
        service_demands=(
            UrbanServiceDemand("clean_water", 1.0),
            UrbanServiceDemand("sanitation", 0.8),
            UrbanServiceDemand("healing", 1.0),
        ),
        population_groups=(
            UrbanPopulationGroup(
                "commoners",
                0.8,
                {"clean_water": 0.7, "sanitation": 0.8, "healing": 1.1},
            ),
            UrbanPopulationGroup(
                "cultivators",
                0.2,
                {"clean_water": 1.4, "sanitation": 1.2, "healing": 1.3},
            ),
        ),
    )


def test_urban_service_state_is_strict_json_and_does_not_duplicate_population():
    state = _state()

    payload = state.to_dict()
    json.dumps(payload, allow_nan=False)
    restored = CityState.from_dict(payload, city_tiles=((0, 0),))

    assert restored == state
    assert payload["service_demands"] == [
        {"capability_id": "clean_water", "demand_per_population": 1.0},
        {"capability_id": "sanitation", "demand_per_population": 0.8},
        {"capability_id": "healing", "demand_per_population": 1.0},
    ]
    assert payload["population_groups"][0]["population_weight"] == 0.8
    assert "population" not in payload["population_groups"][0]


def test_population_groups_and_service_priorities_require_grounded_relationships():
    with pytest.raises(ValueError, match="sum to 1"):
        CityState(
            districts=(CityDistrict("core", "mixed", ((0, 0),), 1.0),),
            population_groups=(UrbanPopulationGroup("commoners", 0.7),),
        ).validate(((0, 0),))

    with pytest.raises(ValueError, match="declared urban service"):
        CityState(
            districts=(CityDistrict("core", "mixed", ((0, 0),), 1.0),),
            service_demands=(UrbanServiceDemand("clean_water", 1.0),),
            population_groups=(
                UrbanPopulationGroup("commoners", 1.0, {"imaginary_service": 1.0}),
            ),
        ).validate(((0, 0),))

    with pytest.raises(ValueError, match="positive"):
        UrbanServiceDemand("clean_water", 0.0)


@pytest.mark.parametrize("map_id", ["classic", "island_seas", "mountain_frontier"])
def test_official_cities_load_grounded_services_and_population_groups(map_id):
    game_map = load_cultivation_world_map(map_id)

    for region_id in range(301, 306):
        city = game_map.regions[region_id]
        assert {item.capability_id for item in city.city_state.service_demands} == {
            "housing",
            "clean_water",
            "sanitation",
            "security",
            "healing",
        }
        assert {item.id for item in city.city_state.population_groups} == {
            "commoners",
            "merchants",
            "cultivators",
        }
        assert sum(
            item.population_weight for item in city.city_state.population_groups
        ) == pytest.approx(1.0)
        assert all(
            group.priority_for("healing") > 0
            for group in city.city_state.population_groups
        )
        healing_assets = [
            asset for asset in city.city_state.assets if "healing" in asset.capability_ids
        ]
        assert len(healing_assets) == 1
        healing_asset = healing_assets[0]
        assert healing_asset.capacity > 0
        assert 0 < healing_asset.quality <= 1
        assert 0 < healing_asset.integrity <= 1
        city.city_state.validate(city.cors)

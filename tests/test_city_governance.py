import pytest

from src.classes.core.dynasty import Dynasty
from src.classes.environment.city_state import (
    CityDistrict,
    CityGovernance,
    CityState,
    UrbanAsset,
)
from src.classes.environment.region import CityRegion, NormalRegion
from src.systems.city_governance import ground_unclaimed_city_governance


def _city(region_id: int, governance: CityGovernance) -> CityRegion:
    return CityRegion(
        id=region_id,
        name=f"City {region_id}",
        desc="",
        cors=[(region_id, 0)],
        population=90.0,
        population_capacity=100.0,
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((region_id, 0),), 1.0),),
            assets=(UrbanAsset("housing", "core", ("housing",), 100.0, 0.8, 0.9),),
            governance=governance,
        ),
    )


def test_ground_unclaimed_cities_to_current_dynasty_without_event(base_world):
    dynasty = Dynasty(id=73, name="Test Dynasty", desc="")
    unclaimed = _city(1, CityGovernance("", "", 0.65))
    sect_controlled = _city(2, CityGovernance("sect", "sect-9", 0.35))
    dynasty_controlled = _city(3, CityGovernance("dynasty", "dynasty-old", 0.55))
    normal = NormalRegion(id=4, name="Wilds", desc="", cors=[(4, 0)])
    base_world.map.regions.update(
        {1: unclaimed, 2: sect_controlled, 3: dynasty_controlled, 4: normal}
    )
    before_state = unclaimed.city_state
    before_districts = unclaimed.city_state.districts
    before_assets = unclaimed.city_state.assets

    base_world.dynasty = dynasty

    assert ground_unclaimed_city_governance(base_world) == 1
    assert unclaimed.city_state is before_state
    assert unclaimed.city_state.governance == CityGovernance("dynasty", "73", 0.65)
    assert unclaimed.city_state.districts == before_districts
    assert unclaimed.city_state.assets == before_assets
    assert sect_controlled.city_state.governance == CityGovernance(
        "sect", "sect-9", 0.35
    )
    assert dynasty_controlled.city_state.governance == CityGovernance(
        "dynasty", "dynasty-old", 0.55
    )


def test_grounding_is_idempotent_and_does_not_emit_events(base_world):
    city = _city(1, CityGovernance("", "", 0.8))
    base_world.map.regions[city.id] = city
    base_world.dynasty = Dynasty(id=11, name="Test Dynasty", desc="")
    events_before = base_world.event_manager.get_events_between_months(
        -(2**63), 2**63 - 1
    )

    assert ground_unclaimed_city_governance(base_world) == 1
    assert ground_unclaimed_city_governance(base_world) == 0
    assert city.city_state.governance == CityGovernance("dynasty", "11", 0.8)
    assert (
        base_world.event_manager.get_events_between_months(-(2**63), 2**63 - 1)
        == events_before
    )


def test_grounding_requires_a_dynasty(base_world):
    city = _city(1, CityGovernance("", "", 0.8))
    base_world.map.regions[city.id] = city
    base_world.dynasty = None

    with pytest.raises(
        ValueError, match="^world dynasty is required to ground city governance$"
    ):
        ground_unclaimed_city_governance(base_world)

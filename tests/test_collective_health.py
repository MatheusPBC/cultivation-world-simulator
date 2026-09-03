import json

import pytest

from src.classes.environment.city_state import (
    CityDistrict,
    CityState,
    UrbanAsset,
    UrbanServiceDemand,
)
from src.classes.environment.region import CityRegion
from src.classes.hp import HP
from src.classes.mechanical_language import MetricKey, PrimitiveDimension, ReadingKind
from src.systems.collective_health import CollectiveHealthView, project_collective_health
from src.systems.semantic_world.resolvers import resolve_metric


def _city(world, *, assets=(), service_demands=()):
    city = CityRegion(
        id=301,
        name="Health Test City",
        desc="",
        cors=[(0, 0), (1, 0)],
        population=100,
        population_capacity=100,
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0), (1, 0)), 1.0),),
            assets=tuple(assets),
            service_demands=tuple(service_demands),
        ),
    )
    world.map.regions[city.id] = city
    for coordinate in city.cors:
        world.map.tiles[coordinate].region = city
    return city


def test_region_without_population_data_is_explicitly_unknown_where_needed(base_world):
    _city(base_world)

    view = project_collective_health(base_world, 301)

    assert view.grounded is True
    assert view.living_avatar_count.value == 0
    assert view.living_avatar_count.reading_kind is ReadingKind.EXACT
    assert view.active_wounded_count.value == 0
    assert view.hp_deficit.value == 0
    assert view.healing_capacity.value is None
    assert view.healing_capacity.reading_kind is ReadingKind.UNKNOWN
    assert view.healing_access.value is None


def test_living_wounded_avatar_changes_collective_load_and_keeps_cause(base_world, dummy_avatar):
    city = _city(base_world)
    dummy_avatar.tile = base_world.map.tiles[city.cors[0]]
    base_world.avatar_manager.register_avatar(dummy_avatar)
    dummy_avatar.hp = HP(100, 65)
    dummy_avatar.individual_consequences.record_injury(
        month=int(base_world.month_stamp),
        max_hp=100,
        damage=35,
        cause_event_id="injury-event-1",
    )

    view = project_collective_health(base_world, city.id)

    assert view.living_avatar_count.value == 1
    assert view.active_wounded_count.value == 1
    assert view.active_wounded_count.reading_kind is ReadingKind.DERIVED
    assert view.hp_deficit.value == 35
    assert view.injuries[0].source_event_ids == ("injury-event-1",)
    assert "injury-event-1" in view.source_event_ids

    burden = resolve_metric(
        base_world,
        MetricKey(
            PrimitiveDimension.RISK,
            "region",
            str(city.id),
            "injury_burden",
            qualifiers=(("kind", "collective_health"),),
        ),
        target=city,
        calculated_month=int(base_world.month_stamp),
    )
    wounded = resolve_metric(
        base_world,
        MetricKey(
            PrimitiveDimension.LOAD,
            "region",
            str(city.id),
            "active_wounded",
            qualifiers=(("kind", "collective_health"),),
        ),
        target=city,
        calculated_month=int(base_world.month_stamp),
    )
    assert burden.value == 1.0
    assert wounded.value == 1.0
    assert burden.source_event_ids == ["injury-event-1"]
    assert wounded.source_event_ids == ["injury-event-1"]


def test_collects_only_living_avatars_currently_located_in_region(base_world, dummy_avatar):
    city = _city(base_world)
    dummy_avatar.tile = base_world.map.tiles[city.cors[0]]
    base_world.avatar_manager.avatars[dummy_avatar.id] = dummy_avatar

    detached = type("DetachedAvatar", (), {"id": "detached", "is_dead": False, "tile": None})()
    dead = type(
        "DeadAvatar",
        (),
        {"id": "dead", "is_dead": True, "tile": base_world.map.tiles[city.cors[0]]},
    )()
    base_world.avatar_manager.avatars[detached.id] = detached
    base_world.avatar_manager.dead_avatars[dead.id] = dead

    view = project_collective_health(base_world, city.id)

    assert view.living_avatar_count.value == 1
    assert view.living_avatar_count.state_refs == (
        "avatar:" + str(dummy_avatar.id) + ":life",
        "avatar:" + str(dummy_avatar.id) + ":location",
        "region:301",
        "region:301:living_avatars",
    )


def test_healing_capacity_uses_explicit_asset_quality_and_integrity(base_world):
    _city(
        base_world,
        assets=(
            UrbanAsset("wealthy-house", "core", ("housing",), 500, 1.0, 1.0),
            UrbanAsset("clinic", "core", ("healing",), 24, 0.2, 0.2),
        ),
        service_demands=(UrbanServiceDemand("healing", 0.01),),
    )

    view = project_collective_health(base_world, 301)

    assert view.healing_capacity.value == pytest.approx(0.96)
    assert view.healing_capacity.reading_kind is ReadingKind.DERIVED
    assert view.healing_access.value == pytest.approx(0.96)
    assert [asset.asset_id for asset in view.healing_assets] == ["clinic"]


def test_declared_healing_demand_without_asset_is_measurable_zero(base_world):
    _city(
        base_world,
        service_demands=(UrbanServiceDemand("healing", 0.01),),
    )

    view = project_collective_health(base_world, 301)

    assert view.healing_capacity.value == 0
    assert view.healing_access.value == 0


def test_projection_is_read_only_and_serialization_is_save_independent(base_world, dummy_avatar):
    city = _city(
        base_world,
        assets=(UrbanAsset("clinic", "core", ("healing",), 10, 1.0, 1.0),),
    )
    dummy_avatar.tile = base_world.map.tiles[city.cors[0]]
    base_world.avatar_manager.register_avatar(dummy_avatar)
    before = {
        "population": city.population,
        "assets": city.city_state.assets,
        "avatar_tile": dummy_avatar.tile,
        "avatar_hp": dummy_avatar.hp.to_dict(),
    }

    view = project_collective_health(base_world, 301)
    encoded = view.to_json()
    restored = CollectiveHealthView.from_dict(json.loads(encoded))

    assert restored.to_dict() == view.to_dict()
    assert json.loads(encoded) == view.to_dict()
    assert city.population == before["population"]
    assert city.city_state.assets == before["assets"]
    assert dummy_avatar.tile is before["avatar_tile"]
    assert dummy_avatar.hp.to_dict() == before["avatar_hp"]


def test_unknown_region_does_not_fabricate_health_facts(base_world):
    view = project_collective_health(base_world, 999)

    assert view.grounding_status == "unknown"
    assert view.living_avatar_count.value is None
    assert view.active_wounded_count.value is None
    assert view.hp_deficit.value is None
    assert view.healing_capacity.value is None
    assert view.healing_access.value is None

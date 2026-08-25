from src.classes.environment.region import CityRegion, NormalRegion
from src.classes.environment.region_condition import RegionCondition
from src.server.services.game_queries import get_detail
from src.systems.regional_pressure import (
    build_avatar_regional_context,
    resolve_region_capabilities,
    summarize_regional_pressure,
)


def test_region_conditions_keep_causal_origin_and_expire_by_month():
    region = NormalRegion(id=1, name="Vale", desc="", cors=[(0, 0)])
    condition = RegionCondition(
        kind="healing_formation",
        intensity=0.8,
        started_month=10,
        cause_event_id="event-formation",
        expires_month=16,
    )

    region.add_condition(condition)

    assert region.get_active_conditions(15) == [condition]
    assert region.get_active_conditions(16) == []
    assert region.to_runtime_dict()["conditions"] == [condition.to_dict()]


def test_regional_pressure_is_derived_from_city_load_conditions_phenomenon_and_capabilities():
    city = CityRegion(
        id=2,
        name="Cidade Alta",
        desc="",
        cors=[(0, 0)],
        population=95.0,
        population_capacity=100.0,
    )
    city.add_condition(
        RegionCondition(
            kind="healing_formation",
            intensity=1.0,
            started_month=12,
            cause_event_id="event-formation",
        )
    )

    capabilities = resolve_region_capabilities(city)
    pressure = summarize_regional_pressure(
        city,
        current_month=12,
        phenomenon=type("Phenomenon", (), {"name": "Heaven Tide", "desc": "Qi rises"})(),
        capabilities=capabilities,
    )

    assert pressure["occupancy_ratio"] == 0.95
    assert pressure["level"] == "high"
    assert pressure["conditions"][0]["cause_event_id"] == "event-formation"
    assert pressure["phenomenon"]["name"] == "Heaven Tide"
    assert {item["kind"] for item in capabilities} >= {"population", "settlement"}


def test_avatar_context_uses_current_region_state_without_registering_capabilities(base_world, dummy_avatar):
    region = NormalRegion(id=3, name="Bosque", desc="", cors=[(0, 0)])
    dummy_avatar.tile.region = region
    base_world.current_phenomenon = type("Phenomenon", (), {"name": "Wood Age", "desc": "Life thrives"})()

    context = build_avatar_regional_context(dummy_avatar)

    assert "Bosque" in context
    assert "Wood Age" in context
    assert not hasattr(region, "capabilities")


def test_region_detail_exposes_derived_pressure_capabilities_and_condition_cause(base_world):
    city = CityRegion(
        id=4,
        name="Cidade Alta",
        desc="",
        cors=[(0, 0)],
        population=90.0,
        population_capacity=100.0,
    )
    city.add_condition(
        RegionCondition(
            kind="healing_formation",
            intensity=1.0,
            started_month=int(base_world.month_stamp),
            cause_event_id="event-formation",
        )
    )
    base_world.map.regions[city.id] = city

    detail = get_detail(
        {"world": base_world},
        target_type="region",
        target_id=str(city.id),
        sects_by_id={},
        build_sect_detail=lambda *_: {},
        language_manager=None,
        resolve_avatar_pic_id=lambda _: 0,
    )

    assert detail["regional_pressure"]["level"] == "high"
    assert detail["regional_pressure"]["conditions"][0]["cause_event_id"] == "event-formation"
    assert {capability["kind"] for capability in detail["regional_capabilities"]} >= {
        "population",
        "settlement",
    }

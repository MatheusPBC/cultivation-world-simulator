import pytest

from src.classes.environment.region import CityRegion, CultivateRegion, NormalRegion
from src.classes.essence import EssenceType
from src.classes.event import Event
from src.classes.mechanical_language import (
    EntityRef,
    MeasurementAvailability,
    MetricKey,
    PrimitiveDimension,
    ReadingKind,
)
from src.classes.poi.grave import GravePOI
from src.classes.poi.treasure import TreasurePOI
from src.systems.semantic_world.resolvers import resolve_metric
from src.systems.semantic_world.service import evaluate_semantic_world
from src.sim.simulator_engine.phases.poi import phase_expire_graves
from src.systems.spiritual_ecology import (
    SPIRITUAL_ANCHOR_CONCEPT,
    SPIRITUAL_ANCHOR_QUALIFIERS,
    SPIRITUAL_ANCHOR_RATIO_CONCEPT,
    SPIRITUAL_ANCHOR_RATIO_QUALIFIERS,
    SPIRITUAL_ESSENCE_CONCEPT,
    SPIRITUAL_FORMATION_CONCEPT,
    SPIRITUAL_FORMATION_QUALIFIERS,
    SPIRITUAL_GRAVE_CONCEPT,
    SPIRITUAL_GRAVE_QUALIFIERS,
    SPIRITUAL_TREASURE_CONCEPT,
    SPIRITUAL_TREASURE_QUALIFIERS,
    project_spiritual_ecology,
    spiritual_essence_qualifiers,
    spiritual_metric_keys,
)
from src.utils.llm.test_mode_fallbacks import resolve_test_mode_task
from src.systems.time import MonthStamp


def _put_region(world, region):
    world.map.regions[region.id] = region
    world.map.region_cors[region.id] = list(region.cors)
    for coordinate in region.cors:
        tile = world.map.tiles.get(coordinate)
        if tile is not None:
            tile.region = region


def test_grounded_spiritual_metric_keys_and_readings_keep_exact_provenance(base_world):
    region = CultivateRegion(
        id=51,
        name="Spirit Valley",
        desc="",
        cors=[(0, 0), (1, 0)],
        essence_type=EssenceType.WATER,
        essence_density=7,
    )
    _put_region(base_world, region)
    base_world.map.region_formations[51] = {
        "id": "formation:51:quieting",
        "formation_type": "quieting",
        "start_month": int(base_world.month_stamp),
        "duration": 4,
        "effects": {"extra_respire_exp_multiplier": 0.1},
        "source_event_id": "event:formation:51",
    }
    grave = GravePOI(
        id="grave:51:1",
        kind="grave",
        x=1,
        y=0,
        name="Aged Grave",
        created_month=int(base_world.month_stamp),
        expires_month=int(base_world.month_stamp) + 8,
    )
    grave.source_event_id = "event:death:51"
    base_world.poi_manager.add(grave)
    treasure = TreasurePOI(
        id="treasure:51:1",
        kind="treasure",
        x=0,
        y=0,
        name="Sealed Bell",
        created_month=int(base_world.month_stamp),
        expires_month=int(base_world.month_stamp) + 8,
    )
    treasure.source_event_id = "event:treasure:51"
    base_world.poi_manager.add(treasure)

    keys = spiritual_metric_keys(base_world, 51)
    assert {
        (key.dimension, key.concept_id)
        for key in keys
    } == {
        (PrimitiveDimension.STOCK, SPIRITUAL_ESSENCE_CONCEPT),
        (PrimitiveDimension.LOAD, SPIRITUAL_GRAVE_CONCEPT),
        (PrimitiveDimension.LOAD, SPIRITUAL_FORMATION_CONCEPT),
        (PrimitiveDimension.LOAD, SPIRITUAL_TREASURE_CONCEPT),
        (PrimitiveDimension.LOAD, SPIRITUAL_ANCHOR_CONCEPT),
        (PrimitiveDimension.QUALITY, SPIRITUAL_ANCHOR_RATIO_CONCEPT),
    }
    assert all(
        key.qualifiers in {
            spiritual_essence_qualifiers(element)
            for element in ("GOLD", "WOOD", "WATER", "FIRE", "EARTH")
        }
        or key.qualifiers in {
            SPIRITUAL_GRAVE_QUALIFIERS,
            SPIRITUAL_FORMATION_QUALIFIERS,
            SPIRITUAL_TREASURE_QUALIFIERS,
            SPIRITUAL_ANCHOR_QUALIFIERS,
            SPIRITUAL_ANCHOR_RATIO_QUALIFIERS,
        }
        for key in keys
    )

    essence_key = next(
        key for key in keys
        if key.dimension is PrimitiveDimension.STOCK
        and key.qualifier("element") == "WATER"
    )
    essence = resolve_metric(base_world, essence_key, calculated_month=51)
    assert essence.value == 7.0
    assert essence.reading_kind is ReadingKind.EXACT
    assert essence.state_refs == ["region:51:essence", "region:51:essence:WATER"]
    assert essence.source_event_ids == []

    grave_reading = resolve_metric(
        base_world,
        next(key for key in keys if key.concept_id == SPIRITUAL_GRAVE_CONCEPT),
        calculated_month=51,
    )
    formation_reading = resolve_metric(
        base_world,
        next(key for key in keys if key.concept_id == SPIRITUAL_FORMATION_CONCEPT),
        calculated_month=51,
    )
    presence_reading = resolve_metric(
        base_world,
        next(key for key in keys if key.concept_id == SPIRITUAL_ANCHOR_RATIO_CONCEPT),
        calculated_month=51,
    )
    assert grave_reading.value == 1.0
    assert grave_reading.source_event_ids == ["event:death:51"]
    assert formation_reading.value == 1.0
    assert formation_reading.source_event_ids == ["event:formation:51"]
    treasure_reading = resolve_metric(
        base_world,
        next(key for key in keys if key.concept_id == SPIRITUAL_TREASURE_CONCEPT),
        calculated_month=51,
    )
    assert treasure_reading.value == 1.0
    assert treasure_reading.source_event_ids == ["event:treasure:51"]
    assert presence_reading.value == 1.0
    assert set(presence_reading.source_event_ids) == {
        "event:death:51",
        "event:formation:51",
        "event:treasure:51",
    }
    anchor_reading = resolve_metric(
        base_world,
        next(key for key in keys if key.concept_id == SPIRITUAL_ANCHOR_CONCEPT),
        calculated_month=51,
    )
    assert anchor_reading.value == 3.0
    assert anchor_reading.unit == "anchors"


def test_spiritual_metric_without_substrate_is_unknown_but_zero_anchors_are_measurable(base_world):
    region = NormalRegion(id=52, name="Plain", desc="", cors=[(0, 0)])
    _put_region(base_world, region)
    presence_key = MetricKey(
        PrimitiveDimension.QUALITY,
        "region",
        "52",
        SPIRITUAL_ANCHOR_RATIO_CONCEPT,
        qualifiers=SPIRITUAL_ANCHOR_RATIO_QUALIFIERS,
    )

    reading = resolve_metric(base_world, presence_key, calculated_month=0)

    assert reading.value == 0.0
    assert reading.availability is MeasurementAvailability.MEASURABLE
    assert reading.reading_kind is ReadingKind.DERIVED
    assert reading.state_refs == [
        "region:52:spiritual_anchors",
        "world:poi_registry",
        "map:region_formations",
    ]
    assert reading.source_event_ids == []

    essence_key = MetricKey(
        PrimitiveDimension.STOCK,
        "region",
        "52",
        SPIRITUAL_ESSENCE_CONCEPT,
        qualifiers=spiritual_essence_qualifiers("GOLD"),
    )
    essence_reading = resolve_metric(base_world, essence_key, calculated_month=0)
    assert essence_reading.value is None
    assert essence_reading.availability is MeasurementAvailability.UNMEASURABLE
    assert essence_reading.reading_kind is ReadingKind.UNKNOWN
    assert essence_reading.state_refs == []
    assert essence_reading.source_event_ids == []
    assert project_spiritual_ecology(base_world, 52).grounding_status == "unknown"
    assert spiritual_metric_keys(base_world, 52) == ()


def test_test_mode_spiritual_condition_is_grounded_reusable_and_non_mutating():
    result = resolve_test_mode_task(
        "semantic_discovery",
        {
            "available_metrics": [{
                "dimension": "quality",
                "concept_id": SPIRITUAL_ANCHOR_RATIO_CONCEPT,
                "qualifiers": dict(SPIRITUAL_ANCHOR_RATIO_QUALIFIERS),
                "unit": "ratio",
            }],
        },
    )

    assert result["derived_metrics"] == [{
        "id": "grounded_spiritual_activity",
        "concept_id": "grounded_spiritual_activity",
        "dimension": "quality",
        "target_kind": "region",
        "expression": {
            "op": "metric",
            "dimension": "quality",
            "concept_id": SPIRITUAL_ANCHOR_RATIO_CONCEPT,
            "qualifiers": dict(SPIRITUAL_ANCHOR_RATIO_QUALIFIERS),
        },
        "unit": "ratio",
    }]
    condition = result["conditions"][0]
    assert condition["id"] == "observed_spiritual_activity"
    assert condition["activate_after_months"] == 2
    assert condition["resolve_after_months"] == 2
    assert result["mechanic_proposals"] == []

    unrelated = resolve_test_mode_task(
        "semantic_discovery",
        {
            "available_metrics": [{
                "dimension": "stock",
                "concept_id": SPIRITUAL_ANCHOR_RATIO_CONCEPT,
                "qualifiers": {"kind": "other_domain"},
                "unit": "anchors",
            }],
        },
    )
    assert unrelated["derived_metrics"] == []
    assert unrelated["conditions"] == []


@pytest.mark.asyncio
async def test_grounded_anchor_discovers_condition_then_resolves_without_new_llm_or_effects(base_world):
    city = CityRegion(
        id=53,
        name="Anchor City",
        desc="",
        cors=[(0, 0)],
        population=50,
        population_capacity=100,
    )
    _put_region(base_world, city)
    source = Event(base_world.month_stamp, "A cultivator died in Anchor City.")
    assert base_world.event_manager.add_event(source)
    grave = GravePOI(
        id="grave:53:1",
        kind="grave",
        x=0,
        y=0,
        name="Grounded Grave",
        created_month=int(base_world.month_stamp),
        expires_month=int(base_world.month_stamp) + 8,
        source_event_id=source.id,
    )
    base_world.poi_manager.add(grave)
    base_world.run_config_snapshot = {"test_mode": True}

    assert await evaluate_semantic_world(base_world) == []
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    activated = await evaluate_semantic_world(base_world)

    assert [event.event_type for event in activated] == [
        "semantic_condition_activated"
    ]
    active = base_world.mechanical_language.get_active_conditions(
        EntityRef("region", str(city.id)),
        int(base_world.month_stamp),
    )
    condition = next(
        item for item in active
        if item.definition_id == "observed_spiritual_activity"
    )
    assert condition.source_readings[0]["source_event_ids"] == [source.id]
    assert base_world.poi_manager.get(grave.id) is grave
    assert city.population == 50

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    grave.expires_month = int(base_world.month_stamp)
    expiration = phase_expire_graves(base_world)[0]
    assert await evaluate_semantic_world(
        base_world,
        spiritual_source_event_ids_by_target={
            f"region:{city.id}": [expiration.id],
        },
    ) == []
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    resolved = await evaluate_semantic_world(base_world)

    assert [event.event_type for event in resolved] == [
        "semantic_condition_resolved"
    ]
    assert resolved[0].causal_links[0].cause_event_id == condition.cause_event_id
    assert expiration.id in {
        link.cause_event_id for link in resolved[0].causal_links
    }
    assert base_world.mechanical_language.get_active_conditions(
        EntityRef("region", str(city.id)),
        int(base_world.month_stamp),
    ) == []

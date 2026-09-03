import copy
import json

from src.classes.celestial_phenomenon import CelestialPhenomenon
from src.classes.environment.region import CultivateRegion, NormalRegion
from src.classes.essence import EssenceType
from src.classes.event import Event
from src.classes.poi.grave import GravePOI
from src.classes.poi.treasure import TreasurePOI
from src.classes.rarity import get_rarity_from_str
from src.systems.spiritual_ecology import project_spiritual_ecology


def _put_region(world, region):
    world.map.regions[region.id] = region
    world.map.region_cors[region.id] = list(region.cors)
    for coordinate in region.cors:
        tile = world.map.tiles.get(coordinate)
        if tile is not None:
            tile.region = region


def test_without_grounded_facts_does_not_invent_spiritual_risk(base_world):
    region = NormalRegion(id=11, name="Plain", desc="", cors=[(0, 0)])
    _put_region(base_world, region)
    base_world.current_phenomenon = CelestialPhenomenon(
        id=9,
        name="World Tide",
        rarity=get_rarity_from_str("N"),
        effects={},
        effect_desc="",
        desc="A world-wide context only.",
        duration_years=5,
    )

    view = project_spiritual_ecology(base_world, region.id)

    assert view.grounding_status == "unknown"
    assert view.essence is None
    assert view.formations == ()
    assert view.graves == ()
    assert view.treasures == ()
    assert view.risk_level is None
    assert view.celestial_context is not None
    assert view.celestial_context.phenomenon_id == "9"


def test_distinct_grounded_facts_produce_distinct_views(base_world):
    first = CultivateRegion(
        id=21,
        name="Gold Cave",
        desc="",
        cors=[(0, 0)],
        essence_type=EssenceType.GOLD,
        essence_density=8,
    )
    second = CultivateRegion(
        id=22,
        name="Water Cave",
        desc="",
        cors=[(1, 0)],
        essence_type=EssenceType.WATER,
        essence_density=3,
    )
    _put_region(base_world, first)
    _put_region(base_world, second)
    base_world.map.region_formations[21] = {
        "id": "formation:21:gold",
        "formation_type": "spirit_gathering",
        "start_month": int(base_world.month_stamp),
        "duration": 12,
        "effects": {"extra_respire_exp_multiplier": 0.2},
        "source_event_id": "event-formation-gold",
    }

    first_view = project_spiritual_ecology(base_world, 21)
    second_view = project_spiritual_ecology(base_world, 22)

    assert first_view.grounded is True
    assert first_view.essence.essence_type == "GOLD"
    assert first_view.formations[0].formation_type == "spirit_gathering"
    assert first_view.source_event_ids == ("event-formation-gold",)
    assert second_view.grounded is True
    assert second_view.essence.essence_type == "WATER"
    assert second_view.formations == ()
    assert first_view.to_dict() != second_view.to_dict()


def test_related_pois_and_formation_condition_expose_provenance(base_world):
    region = CultivateRegion(
        id=31,
        name="Ruin Valley",
        desc="",
        cors=[(0, 0), (1, 0)],
        essence_density=4,
    )
    _put_region(base_world, region)
    base_world.map.region_formations[31] = {
        "id": "formation:31:clarity",
        "formation_type": "clarity",
        "start_month": int(base_world.month_stamp),
        "duration": 10,
        "effects": {"extra_breakthrough_success_rate": 0.06},
    }
    base_world.event_manager.add_event(Event(base_world.month_stamp, "formation source", id="event-clarity"))
    from src.classes.mechanical_language import ConditionInstance

    base_world.mechanical_language.add_condition_instance(
        ConditionInstance(
            id="condition-clarity",
            definition_id="formation:clarity_formation",
            target_kind="region",
            target_id="31",
            label="clarity_formation",
            intensity=1.0,
            started_month=int(base_world.month_stamp),
            expires_month=int(base_world.month_stamp) + 10,
            cause_event_id="event-clarity",
        )
    )
    grave = GravePOI(
        id="grave:31:1",
        kind="grave",
        x=0,
        y=0,
        name="Old Grave",
        created_month=int(base_world.month_stamp),
        expires_month=int(base_world.month_stamp) + 12,
    )
    grave.source_event_id = "event-death"
    base_world.poi_manager.add(grave)
    base_world.poi_manager.add(
        TreasurePOI(
            id="treasure:31:1",
            kind="treasure",
            x=1,
            y=0,
            name="Buried Bell",
            created_month=int(base_world.month_stamp),
            expires_month=int(base_world.month_stamp) + 12,
        )
    )

    view = project_spiritual_ecology(base_world, 31)

    assert view.source_event_ids == ("event-clarity", "event-death")
    assert view.graves[0].poi_id == "grave:31:1"
    assert view.treasures[0].poi_id == "treasure:31:1"
    assert "region:31:essence" in view.state_refs
    assert "poi:grave:31:1" in view.graves[0].state_refs


def test_projection_does_not_mutate_world_and_serialization_is_stable(base_world):
    region = CultivateRegion(id=41, name="Quiet Cave", desc="", cors=[(0, 0)], essence_density=2)
    _put_region(base_world, region)
    base_world.map.region_formations[41] = {
        "id": "formation:41:healing",
        "formation_type": "healing",
        "start_month": int(base_world.month_stamp),
        "duration": 2,
        "effects": {"extra_hp_recovery_rate": 0.4},
    }
    before = copy.deepcopy(base_world.map.region_formations)
    view = project_spiritual_ecology(base_world, 41)

    assert base_world.map.region_formations == before
    assert view.to_json() == json.dumps(
        view.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert project_spiritual_ecology(base_world, 41).to_dict() == view.to_dict()

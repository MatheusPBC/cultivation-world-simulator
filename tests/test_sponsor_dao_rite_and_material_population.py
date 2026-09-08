from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.classes.action import Educate, HelpPeople, PlunderPeople, SponsorDaoRite
from src.classes.action.param_options import ParamOptionSource, build_param_options
from src.classes.celestial_dao import DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.event import Event, FactKind, is_null_event
from src.classes.environment.region import CityRegion
from src.classes.mechanical_language import ConditionInstance
from src.classes.regional_economy import RegionalEconomyState
from src.classes.actions import get_action_infos
from src.systems.celestial_dao_service import (
    _popular_rite_regions,
    process_grounded_dao_rites,
)
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.regional_economy import phase_update_regional_economy


def _city_avatar(base_world, dummy_avatar, region_id: int = 7):
    region = CityRegion(
        id=region_id,
        name="Rite City",
        desc="",
        cors=[(0, 0)],
        dao_tradition=DaoTradition.BALANCE,
    )
    base_world.map.regions[region_id] = region
    dummy_avatar.tile = SimpleNamespace(region=region)
    return region


def _popular_rite(base_world, region: CityRegion) -> Event:
    event = Event(
        base_world.month_stamp,
        "A popular rite",
        event_type="dao_rite",
        causal_payload={
            "dao_rite": {
                "is_popular": True,
                "region_id": region.id,
            }
        },
    )
    base_world.event_manager.add_event(event)
    return event


def _regional_event(base_world, region: CityRegion, *, event_type: str, is_major: bool = False) -> Event:
    return Event(
        base_world.month_stamp,
        f"{event_type} in {region.name}",
        event_type=event_type,
        is_major=is_major,
        render_params={"region_id": str(region.id)},
        causal_payload={"deltas": []},
    )


def test_monthly_grain_production_alone_does_not_create_a_popular_rite(base_world, dummy_avatar):
    region = _city_avatar(base_world, dummy_avatar)
    region.economy = RegionalEconomyState(
        stocks={"grain": 1},
        capacities={"grain": 10},
        production_rates={"grain": 2},
    )

    production_events = phase_update_regional_economy(base_world)

    assert len(production_events) == 1
    assert production_events[0].render_params["produced"] == 2
    assert _popular_rite_regions(base_world, current_events=production_events) == []


def test_active_regional_condition_is_a_grounded_popular_rite_cause(base_world, dummy_avatar):
    region = _city_avatar(base_world, dummy_avatar)
    source = _regional_event(
        base_world,
        region,
        event_type="semantic_condition_activated",
    )
    base_world.event_manager.add_event(source)
    base_world.mechanical_language.add_condition_instance(
        ConditionInstance(
            id="regional-pressure",
            definition_id="pressure-definition",
            target_kind="region",
            target_id=str(region.id),
            label="Regional pressure",
            intensity=0.8,
            started_month=int(base_world.month_stamp),
            cause_event_id=source.id,
        )
    )

    selected = _popular_rite_regions(base_world)

    assert len(selected) == 1
    assert selected[0][1].id == source.id
    assert selected[0][2] == "regional-pressure"

    first_rite = asyncio.run(process_grounded_dao_rites(base_world, []))[0]
    base_world.event_manager.add_event(first_rite)
    base_world.month_stamp = type(base_world.month_stamp)(int(base_world.month_stamp) + 1)

    assert _popular_rite_regions(base_world) == []


def test_material_event_motivates_at_most_one_popular_rite(base_world, dummy_avatar):
    region = _city_avatar(base_world, dummy_avatar)
    material = _regional_event(
        base_world,
        region,
        event_type="regional_resource_shortage",
    )
    base_world.event_manager.add_event(material)
    rite = asyncio.run(process_grounded_dao_rites(base_world, [material]))[0]
    base_world.event_manager.add_event(rite)

    assert _popular_rite_regions(base_world, current_events=[material]) == []


def test_popular_rite_deduplicates_condition_and_event_views_of_same_cause(
    base_world, dummy_avatar
):
    region = _city_avatar(base_world, dummy_avatar)
    material = _regional_event(
        base_world,
        region,
        event_type="regional_resource_shortage",
    )
    base_world.event_manager.add_event(material)
    base_world.mechanical_language.add_condition_instance(
        ConditionInstance(
            id="shortage-condition",
            definition_id="shortage-definition",
            target_kind="region",
            target_id=str(region.id),
            label="Shortage",
            intensity=0.8,
            started_month=int(base_world.month_stamp),
            cause_event_id=material.id,
        )
    )

    condition_first_rite = asyncio.run(
        process_grounded_dao_rites(base_world, [material])
    )[0]
    base_world.event_manager.add_event(condition_first_rite)

    assert _popular_rite_regions(base_world, current_events=[material]) == []


def test_popular_rite_deduplicates_event_then_later_condition_for_same_cause(
    base_world, dummy_avatar
):
    region = _city_avatar(base_world, dummy_avatar)
    material = _regional_event(
        base_world,
        region,
        event_type="regional_resource_shortage",
    )
    base_world.event_manager.add_event(material)
    event_first_rite = asyncio.run(
        process_grounded_dao_rites(base_world, [material])
    )[0]
    base_world.event_manager.add_event(event_first_rite)
    base_world.mechanical_language.add_condition_instance(
        ConditionInstance(
            id="later-shortage-condition",
            definition_id="shortage-definition",
            target_kind="region",
            target_id=str(region.id),
            label="Shortage",
            intensity=0.8,
            started_month=int(base_world.month_stamp),
            cause_event_id=material.id,
        )
    )

    assert _popular_rite_regions(base_world, current_events=[material]) == []


def test_material_regional_event_is_eligible_but_routine_climate_is_not(
    base_world, dummy_avatar
):
    region = _city_avatar(base_world, dummy_avatar)
    material = _regional_event(
        base_world,
        region,
        event_type="regional_resource_shortage",
    )
    climate = _regional_event(
        base_world,
        region,
        event_type="regional_climate_updated",
    )

    selected = _popular_rite_regions(base_world, current_events=[material, climate])
    rites = asyncio.run(process_grounded_dao_rites(base_world, [material, climate]))

    assert len(selected) == 1
    assert selected[0][1].id == material.id
    assert len(rites) == 1
    rite = rites[0]
    assert rite.event_type == "dao_rite"
    assert rite.is_major is False
    assert rite.causal_payload["dao_rite"]["is_confirmed"] is False
    assert rite.causal_links[0].cause_event_id == material.id


def test_popular_rites_are_bounded_to_two_regions_per_month(base_world, dummy_avatar):
    regions = [_city_avatar(base_world, dummy_avatar, region_id) for region_id in (7, 8, 9)]
    events = [
        _regional_event(base_world, region, event_type="regional_resource_shortage")
        for region in regions
    ]

    selected = _popular_rite_regions(base_world, current_events=events)
    selected_again = _popular_rite_regions(base_world, current_events=events)

    assert len(selected) == 2
    assert len(selected_again) == 2
    assert [item[0].id for item in selected] == [item[0].id for item in selected_again]
    assert {item[0].id for item in selected} <= {7, 8, 9}


def test_sponsor_dao_rite_uses_event_id_options_and_one_per_institution(
    base_world, dummy_avatar
):
    region = _city_avatar(base_world, dummy_avatar)
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.dynasty = Dynasty(
        id=1,
        name="Test",
        desc="",
        current_emperor_id=dummy_avatar.id,
    )
    # Sponsorship is authorized through `can_actor_act_for`, which has no
    # permissive fallback, so the dynasty must be a real institution.
    bootstrap_institutional_authority(base_world)
    rite = _popular_rite(base_world, region)

    options = build_param_options(SponsorDaoRite, dummy_avatar)
    assert SponsorDaoRite.PARAM_OPTION_SOURCES["cause_event_id"] is ParamOptionSource.SPONSORABLE_DAO_RITE_EVENT_ID
    assert options["cause_event_id"][0]["value"] == rite.id
    assert get_action_infos(dummy_avatar)["SponsorDaoRite"]["param_options"]["cause_event_id"][0]["value"] == rite.id

    action = SponsorDaoRite(dummy_avatar, base_world)
    assert action.can_start(rite.id) == (True, "")
    # Starting sponsors nothing: the sponsorship fact belongs to the execution
    # boundary, where the engine has already installed the plan's origin.
    assert is_null_event(action.start(rite.id))


def test_sponsor_requires_presence_and_knowledge(base_world, dummy_avatar):
    region = _city_avatar(base_world, dummy_avatar)
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.dynasty = Dynasty(
        id=1,
        name="Test",
        desc="",
        current_emperor_id=dummy_avatar.id,
    )
    # Sponsorship is authorized through `can_actor_act_for`, which has no
    # permissive fallback, so the dynasty must be a real institution.
    bootstrap_institutional_authority(base_world)
    rite = _popular_rite(base_world, region)
    action = SponsorDaoRite(dummy_avatar, base_world)

    assert action.can_start("unknown-event")[0] is False
    other = CityRegion(id=8, name="Elsewhere", desc="", cors=[(1, 0)])
    dummy_avatar.tile.region = other
    assert "present" in action.can_start(rite.id)[1]


def test_material_population_actions_do_not_turn_help_or_education_into_births(
    base_world, dummy_avatar
):
    region = _city_avatar(base_world, dummy_avatar)
    dummy_avatar.magic_stone = 100
    before = region.population
    asyncio.run(HelpPeople(dummy_avatar, base_world).finish())
    assert region.population == before

    dummy_avatar.effects["legal_actions"] = ["Educate"]
    Educate(dummy_avatar, base_world)._execute()
    assert region.population == before

    dummy_avatar.alignment = "evil"
    event = asyncio.run(PlunderPeople(dummy_avatar, base_world).finish())[0]
    assert region.population == before - PlunderPeople.TOTAL_POPULATION_LOSS
    assert event.fact_kind is FactKind.STATE_TRANSITION
    assert event.causal_payload["affected_quantity"] == PlunderPeople.TOTAL_POPULATION_LOSS
    assert event.causal_payload["deltas"][0]["owner_id"] == str(region.id)

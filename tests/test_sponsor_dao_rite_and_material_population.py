from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.classes.action import Educate, HelpPeople, PlunderPeople, SponsorDaoRite
from src.classes.action.param_options import ParamOptionSource, build_param_options
from src.classes.celestial_dao import DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.event import Event, FactKind
from src.classes.environment.region import CityRegion
from src.classes.actions import get_action_infos


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


def test_sponsor_dao_rite_uses_event_id_options_and_one_per_institution(
    base_world, dummy_avatar
):
    region = _city_avatar(base_world, dummy_avatar)
    base_world.dynasty = Dynasty(
        id=1,
        name="Test",
        desc="",
        current_emperor_id=dummy_avatar.id,
    )
    rite = _popular_rite(base_world, region)

    options = build_param_options(SponsorDaoRite, dummy_avatar)
    assert SponsorDaoRite.PARAM_OPTION_SOURCES["cause_event_id"] is ParamOptionSource.SPONSORABLE_DAO_RITE_EVENT_ID
    assert options["cause_event_id"][0]["value"] == rite.id
    assert get_action_infos(dummy_avatar)["SponsorDaoRite"]["param_options"]["cause_event_id"][0]["value"] == rite.id

    action = SponsorDaoRite(dummy_avatar, base_world)
    assert action.can_start(rite.id) == (True, "")
    event = action.start(rite.id)
    assert event.fact_kind is FactKind.DECISION
    assert event.causal_payload["dao_rite"]["is_sponsorship"] is True
    assert action.can_start(rite.id)[0] is False


def test_sponsor_requires_presence_and_knowledge(base_world, dummy_avatar):
    region = _city_avatar(base_world, dummy_avatar)
    base_world.dynasty = Dynasty(
        id=1,
        name="Test",
        desc="",
        current_emperor_id=dummy_avatar.id,
    )
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

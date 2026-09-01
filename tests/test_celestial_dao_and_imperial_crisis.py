from copy import copy
from types import SimpleNamespace

import pytest

from src.classes.celestial_dao import DaoPetition, DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.event import Event
from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR
from src.systems.celestial_dao_service import (
    answer_petition,
    create_petition,
    get_dao_context,
    maybe_create_monthly_petition,
)
from src.systems.imperial_crisis_service import (
    open_imperial_claim,
    resolve_imperial_crisis,
)
from src.utils.llm.runtime_mode import llm_test_mode_scope


def _court(world, avatar):
    region = SimpleNamespace(id=7, dao_tradition=DaoTradition.MERCY)
    avatar.tile = SimpleNamespace(region=region)
    world.map.regions[7] = region
    world.avatar_manager.register_avatar(avatar)
    world.dynasty = Dynasty(id=1, name="Test", desc="", current_emperor_id=avatar.id)


def test_common_avatar_cannot_open_a_celestial_audience(base_world, dummy_avatar):
    base_world.map.regions[7] = SimpleNamespace(id=7, dao_tradition=DaoTradition.MERCY)
    with pytest.raises(ValueError):
        create_petition(
            base_world,
            initiator_kind="avatar",
            initiator_id=dummy_avatar.id,
            region_id=7,
            motivated_event_ids=[],
        )
    assert base_world.dao_petitions == []


def test_actual_sign_keeps_distinct_regional_readings(base_world, dummy_avatar):
    _court(base_world, dummy_avatar)
    base_world.map.regions[8] = SimpleNamespace(
        id=8, dao_tradition=DaoTradition.MANDATE_AND_ORDER
    )
    audience = create_petition(
        base_world,
        initiator_kind="court",
        initiator_id="1",
        region_id=7,
        motivated_event_ids=[],
        rite_event_ids=["r1", "r2", "r3"],
    )
    answer_petition(base_world, audience.id, "sign")
    mercy = next(
        item
        for item in get_dao_context(base_world, region_id=7)
        if item["kind"] == "omen"
    )
    mandate = next(
        item
        for item in get_dao_context(base_world, region_id=8)
        if item["kind"] == "omen"
    )
    assert mercy["source_event_id"] == mandate["source_event_id"]
    assert mercy["interpretation"] != mandate["interpretation"]


@pytest.mark.asyncio
async def test_rites_are_social_claims_until_three_causes_accumulate(
    base_world, dummy_avatar
):
    _court(base_world, dummy_avatar)
    for month in (12, 16, 20):
        base_world.month_stamp = month
        cause = Event(
            month,
            f"Court crisis {month}",
            related_avatars=[dummy_avatar.id],
            is_major=True,
        )
        with llm_test_mode_scope(True):
            events = await maybe_create_monthly_petition(base_world, [cause])
        for event in events:
            base_world.event_manager.add_event(event)
        if month < 20:
            assert base_world.dao_petitions == []
            assert events[0].event_type == "dao_rite"
    audience = base_world.dao_petitions[0]
    assert audience.initiator_kind == "court"
    assert len(audience.rite_event_ids) == 3
    assert DaoPetition.from_dict(audience.to_dict()).rite_event_ids == audience.rite_event_ids
    assert any(
        item["kind"] == "unconfirmed_rite"
        for item in get_dao_context(base_world, region_id=7)
    )


def test_favor_is_limited_to_the_institution(base_world, dummy_avatar):
    _court(base_world, dummy_avatar)
    audience = create_petition(
        base_world,
        initiator_kind="court",
        initiator_id="1",
        region_id=7,
        motivated_event_ids=[],
        rite_event_ids=["r1", "r2", "r3"],
    )
    answer_petition(base_world, audience.id, "favor")
    assert any(
        item["kind"] == "limited_favor"
        for item in get_dao_context(base_world, region_id=7, initiator_id="1")
    )
    assert not any(
        item["kind"] == "limited_favor"
        for item in get_dao_context(
            base_world, region_id=7, initiator_id=dummy_avatar.id
        )
    )


def test_claimant_can_ascend_without_removing_emperor(base_world, dummy_avatar):
    emperor = dummy_avatar
    emperor.court_reputation = 700
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    base_world.avatar_manager.register_avatar(emperor)
    claimant = copy(emperor)
    claimant.id = "claimant"
    claimant.court_reputation = 1000
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=emperor.id
    )
    crisis = open_imperial_claim(base_world, claimant.id)
    base_world.month_stamp += 12
    assert resolve_imperial_crisis(base_world) is not None
    assert crisis.status == "ascended"
    assert base_world.avatar_manager.get_avatar(emperor.id) is emperor

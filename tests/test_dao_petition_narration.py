from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.celestial_dao import DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.event import Event
from src.systems.celestial_dao_service import maybe_create_monthly_petition
from src.utils.llm.exceptions import LLMError
from src.utils.llm.runtime_mode import llm_test_mode_scope


def _major_candidate(base_world, dummy_avatar):
    region = SimpleNamespace(id=7, dao_tradition=DaoTradition.MERCY)
    dummy_avatar.tile = SimpleNamespace(region=region)
    base_world.map.regions[7] = region
    base_world.avatar_manager.register_avatar(dummy_avatar)
    return Event(base_world.month_stamp, "A major factual change", related_avatars=[dummy_avatar.id], is_major=True)


@pytest.mark.asyncio
async def test_petition_uses_structured_test_mode_fallback_without_provider(base_world, dummy_avatar):
    cause = _major_candidate(base_world, dummy_avatar)

    with llm_test_mode_scope(True):
        event = await maybe_create_monthly_petition(base_world, [cause])

    assert event is not None
    assert base_world.dao_petitions[0].content
    assert cause.content in base_world.dao_petitions[0].content


@pytest.mark.asyncio
async def test_petition_narration_does_not_choose_its_own_cause(base_world, dummy_avatar):
    cause = _major_candidate(base_world, dummy_avatar)
    with patch("src.systems.celestial_dao_service.call_llm_with_task_name", new=AsyncMock(return_value={"content": "A plea in the voice of the petitioner."})) as call:
        event = await maybe_create_monthly_petition(base_world, [cause])

    assert event is not None
    assert base_world.dao_petitions[0].motivated_event_ids == [cause.id]
    assert base_world.dao_petitions[0].content == "A plea in the voice of the petitioner."
    assert call.await_count == 1


@pytest.mark.asyncio
async def test_failed_petition_narration_uses_deterministic_content(base_world, dummy_avatar):
    cause = _major_candidate(base_world, dummy_avatar)
    with patch("src.systems.celestial_dao_service.call_llm_with_task_name", new=AsyncMock(side_effect=LLMError("provider failed"))):
        await maybe_create_monthly_petition(base_world, [cause])

    assert cause.content in base_world.dao_petitions[0].content


@pytest.mark.asyncio
async def test_monthly_filter_can_select_a_related_sect_as_petitioner(base_world, dummy_avatar):
    from types import SimpleNamespace

    region = SimpleNamespace(id=7, dao_tradition=DaoTradition.BALANCE)
    sect = SimpleNamespace(id=11, name="Cloud Sect")
    dummy_avatar.tile = SimpleNamespace(region=region)
    dummy_avatar.sect = sect
    base_world.map.regions[region.id] = region
    base_world.existed_sects = [sect]
    base_world.avatar_manager.register_avatar(dummy_avatar)
    cause = Event(base_world.month_stamp, "The sect suffers a major loss", related_sects=[sect.id], is_major=True)

    with llm_test_mode_scope(True):
        await maybe_create_monthly_petition(base_world, [cause])

    petition = base_world.dao_petitions[0]
    assert (petition.initiator_kind, petition.initiator_id) == ("sect", str(sect.id))


@pytest.mark.asyncio
async def test_monthly_filter_can_select_the_court_as_petitioner(base_world, dummy_avatar):
    from types import SimpleNamespace

    region = SimpleNamespace(id=7, dao_tradition=DaoTradition.MANDATE_AND_ORDER)
    dummy_avatar.tile = SimpleNamespace(region=region)
    base_world.map.regions[region.id] = region
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.dynasty = Dynasty(id=3, name="Test Dynasty", desc="", current_emperor_id=dummy_avatar.id)
    cause = Event(base_world.month_stamp, "The court faces a public crisis", related_avatars=[dummy_avatar.id], is_major=True)

    with llm_test_mode_scope(True):
        await maybe_create_monthly_petition(base_world, [cause])

    petition = base_world.dao_petitions[0]
    assert (petition.initiator_kind, petition.initiator_id) == ("court", "3")

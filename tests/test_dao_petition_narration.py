from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.celestial_dao import DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.event import Event
from src.systems.celestial_dao_service import maybe_create_monthly_petition
from src.utils.llm.exceptions import LLMError


def _court(world, avatar):
    region = SimpleNamespace(id=7, dao_tradition=DaoTradition.BALANCE)
    avatar.tile = SimpleNamespace(region=region)
    world.map.regions[7] = region
    world.avatar_manager.register_avatar(avatar)
    world.dynasty = Dynasty(
        id=3, name="Test Dynasty", desc="", current_emperor_id=avatar.id
    )


async def _two_rites(world, avatar):
    for month in (12, 16):
        world.month_stamp = month
        events = await maybe_create_monthly_petition(
            world,
            [
                Event(
                    month,
                    f"Court crisis {month}",
                    related_avatars=[avatar.id],
                    is_major=True,
                )
            ],
        )
        for event in events:
            world.event_manager.add_event(event)
    world.month_stamp = 20


@pytest.mark.asyncio
async def test_audience_narration_uses_fallback_only_after_accumulated_rites(
    base_world, dummy_avatar
):
    _court(base_world, dummy_avatar)
    await _two_rites(base_world, dummy_avatar)
    cause = Event(
        20, "A decisive court crisis", related_avatars=[dummy_avatar.id], is_major=True
    )
    with patch(
        "src.systems.celestial_dao_service.call_llm_with_task_name",
        new=AsyncMock(side_effect=LLMError("provider failed")),
    ):
        await maybe_create_monthly_petition(base_world, [cause])
    audience = base_world.dao_petitions[0]
    assert audience.motivated_event_ids == [cause.id]
    assert len(audience.rite_event_ids) == 3
    assert cause.content in audience.content

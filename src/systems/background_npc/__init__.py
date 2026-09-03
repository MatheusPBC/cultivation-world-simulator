from __future__ import annotations

from .models import (
    BACKGROUND_NPC_EVENT_TYPE,
    BackgroundNpcContext,
    BackgroundNpcEventType,
    BackgroundNpcProfile,
    BackgroundNpcRegionBinding,
    BackgroundNpcTriggerKind,
)
from .service import BackgroundNpcService


def try_trigger_background_npc_events(world, living_avatars, *, source_event_id: str) -> list:
    return BackgroundNpcService.create_monthly_events(
        world, living_avatars, source_event_id=source_event_id
    )


def try_trigger_background_npc_action_echo(
    world, avatar, action_key: str, *, source_event_id: str
) -> list:
    return BackgroundNpcService.create_action_echo_events(
        world, avatar, action_key, source_event_id=source_event_id
    )


__all__ = [
    "BACKGROUND_NPC_EVENT_TYPE",
    "BackgroundNpcContext",
    "BackgroundNpcEventType",
    "BackgroundNpcProfile",
    "BackgroundNpcRegionBinding",
    "BackgroundNpcService",
    "BackgroundNpcTriggerKind",
    "try_trigger_background_npc_action_echo",
    "try_trigger_background_npc_events",
]

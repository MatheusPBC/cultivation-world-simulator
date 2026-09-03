from __future__ import annotations

import asyncio
from typing import Any, Callable

from src.config import get_settings_service
from src.config.providers import RuntimeConfigProvider
from src.i18n import t
from src.server.loop import GameLoopRunner, TickPayloadBuilder
from src.systems.cultivation_display import build_avatar_cultivation_display

AVATAR_POSITION_UPDATE_LIMIT = 50


def _serialize_infrastructure_site_updates(world) -> list[dict[str, Any]]:
    game_map = getattr(world, "map", None)
    if not hasattr(game_map, "get_infrastructure_site_updates"):
        return []
    serialized: list[dict[str, Any]] = []
    for update in game_map.get_infrastructure_site_updates():
        if update.get("op") == "remove":
            serialized.append({"op": "remove", "id": str(update["id"])})
            continue
        site = dict(update.get("site") or {})
        cell_refs = site.get("cell_refs") or []
        if not cell_refs:
            continue
        integrity = float(site.get("integrity", 0.0))
        enabled = bool(site.get("enabled", False))
        status = "destroyed" if integrity <= 0 else "active" if enabled and integrity >= 1 else "impaired"
        anchor_x, anchor_y = cell_refs[0]
        serialized.append({
            "op": "upsert",
            "site": {
                **site,
                "status": status,
                "x": int(anchor_x),
                "y": int(anchor_y),
                "clickable": True,
            },
        })
    return serialized


def _serialize_route_updates(world) -> list[dict[str, Any]]:
    """Project routes affected by pending site updates without new state."""
    game_map = getattr(world, "map", None)
    if not hasattr(game_map, "get_infrastructure_site_updates"):
        return []
    route_ids: set[str] = set()
    for update in game_map.get_infrastructure_site_updates():
        site = update.get("site") or {}
        route_ids.update(str(item) for item in site.get("route_ids", ()) if str(item))
    return [
        {
            "id": route_id,
            "operational_capacity": game_map.get_route_operational_capacity(route_id),
            "dependency_site_ids": [
                site.id for site in game_map.get_route_dependency_sites(route_id)
            ],
        }
        for route_id in sorted(route_ids)
        if route_id in game_map.routes
    ]


def build_avatar_updates(
    *,
    world,
    resolve_avatar_pic_id: Callable[[Any], int],
    resolve_avatar_action_emoji: Callable[[Any], str],
) -> list[dict[str, Any]]:
    """Build a compact avatar delta payload for websocket tick messages."""
    newly_born_ids = world.avatar_manager.pop_newly_born()
    newly_dead_ids = world.avatar_manager.pop_newly_dead()

    avatar_updates: list[dict[str, Any]] = []

    for avatar_id in newly_born_ids:
        avatar = world.avatar_manager.avatars.get(avatar_id)
        if avatar is None:
            continue
        cultivation_display = build_avatar_cultivation_display(avatar)
        avatar_updates.append(
            {
                "id": str(avatar.id),
                "name": avatar.name,
                "x": int(getattr(avatar, "pos_x", 0)),
                "y": int(getattr(avatar, "pos_y", 0)),
                "gender": getattr(getattr(avatar, "gender", None), "value", "male"),
                "pic_id": resolve_avatar_pic_id(avatar),
                "realm": getattr(getattr(getattr(avatar, "cultivation_progress", None), "realm", None), "value", ""),
                "cultivation": cultivation_display,
                "cultivation_display": cultivation_display["display_full_name"],
                "action": avatar.current_action_name,
                "action_emoji": resolve_avatar_action_emoji(avatar),
                "is_dead": False,
            }
        )

    for avatar_id in newly_dead_ids:
        avatar = world.avatar_manager.get_avatar(avatar_id)
        if avatar is None:
            continue
        avatar_updates.append(
            {
                "id": str(avatar.id),
                "name": avatar.name,
                "is_dead": True,
                "action": "",
            }
        )

    count = 0
    for avatar in world.avatar_manager.get_living_avatars():
        if avatar.id in newly_born_ids:
            continue
        if count >= AVATAR_POSITION_UPDATE_LIMIT:
            break
        cultivation_display = build_avatar_cultivation_display(avatar)
        avatar_updates.append(
            {
                "id": str(avatar.id),
                "x": int(getattr(avatar, "pos_x", 0)),
                "y": int(getattr(avatar, "pos_y", 0)),
                "gender": getattr(getattr(avatar, "gender", None), "value", "male"),
                "pic_id": resolve_avatar_pic_id(avatar),
                "realm": getattr(getattr(getattr(avatar, "cultivation_progress", None), "realm", None), "value", ""),
                "cultivation": cultivation_display,
                "cultivation_display": cultivation_display["display_full_name"],
                "action": avatar.current_action_name,
                "action_emoji": resolve_avatar_action_emoji(avatar),
            }
        )
        count += 1

    return avatar_updates


def build_tick_state(
    *,
    world,
    events,
    avatar_updates: list[dict[str, Any]],
    serialize_events_for_client: Callable[..., list[dict[str, Any]]],
    serialize_phenomenon: Callable[[Any], dict[str, Any] | None],
    serialize_active_domains: Callable[[Any], list[dict[str, Any]]],
    world_revision: int = 0,
) -> dict[str, Any]:
    """Build the websocket tick payload from current runtime state."""
    return {
        "type": "tick",
        "year": int(world.month_stamp.get_year()),
        "month": world.month_stamp.get_month().value,
        "events": serialize_events_for_client(events, world=world),
        "avatars": avatar_updates,
        "removed_avatar_ids": (
            world.avatar_manager.pop_removed()
            if hasattr(getattr(world, "avatar_manager", None), "pop_removed")
            else []
        ),
        "world_revision": world_revision,
        "poi_updates": world.poi_manager.pop_updates() if hasattr(world, "poi_manager") else [],
        "site_updates": _serialize_infrastructure_site_updates(world),
        "route_updates": _serialize_route_updates(world),
        "phenomenon": serialize_phenomenon(world.current_phenomenon),
        "active_domains": serialize_active_domains(world),
    }


def should_trigger_auto_save(*, world) -> tuple[bool, int, int]:
    """Return whether this tick should create an auto save."""
    auto_save_enabled = RuntimeConfigProvider(get_service=get_settings_service).auto_save_enabled()
    year = int(world.month_stamp.get_year())
    month = world.month_stamp.get_month().value
    should_save = auto_save_enabled and year % 10 == 0 and month == 1 and year > world.start_year
    return should_save, year, month


def build_auto_save_toast() -> dict[str, Any]:
    return {
        "type": "toast",
        "level": "info",
        "message": t("Game automatically saved"),
    }


async def run_game_loop_forever(
    *,
    game_instance: dict,
    runtime,
    manager,
    build_avatar_updates: Callable[[], list[dict[str, Any]]],
    build_tick_state: Callable[[list[dict[str, Any]], list[Any], Any], dict[str, Any]],
    should_trigger_auto_save: Callable[[Any], tuple[bool, int, int]],
    trigger_auto_save,
    build_auto_save_toast: Callable[[], dict[str, Any]],
    get_logger,
) -> None:
    """Run the background simulation loop forever once initialization succeeds."""
    runner = GameLoopRunner(
        game_instance=game_instance,
        runtime=runtime,
        manager=manager,
        tick_payload_builder=TickPayloadBuilder(
            build_avatar_updates=build_avatar_updates,
            build_tick_state=build_tick_state,
        ),
        should_trigger_auto_save=should_trigger_auto_save,
        trigger_auto_save=trigger_auto_save,
        build_auto_save_toast=build_auto_save_toast,
        get_logger=get_logger,
    )
    await runner.run_forever()

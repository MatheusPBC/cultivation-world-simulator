from __future__ import annotations

import json

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t


def phase_expire_graves(world) -> list[Event]:
    """Expire canonical graves with navigable evidence, without inferring effects."""
    manager = getattr(world, "poi_manager", None)
    if manager is None:
        return []
    events: list[Event] = []
    for grave in manager.pop_expired(int(world.month_stamp), kind="grave"):
        tile = getattr(getattr(world, "map", None), "tiles", {}).get(
            (int(grave.x), int(grave.y))
        )
        region_id = str(getattr(getattr(tile, "region", None), "id", ""))
        event = Event(
            world.month_stamp,
            t("The grave of {name} weathered away.", name=grave.deceased_name or grave.name),
            related_avatars=[grave.deceased_avatar_id] if grave.deceased_avatar_id else None,
            is_major=False,
            event_type="grave_expired",
            render_params={"poi_id": str(grave.id), "region_id": region_id},
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.DETERMINISTIC,
        )
        event.causal_payload = {"deltas": [StateDelta(
            event_id=event.id,
            owner_kind="poi",
            owner_id=str(grave.id),
            aspect="active_grave",
            before=json.dumps(grave.to_save_dict(), ensure_ascii=False, sort_keys=True),
            after=None,
        ).to_dict()]}
        if grave.source_event_id:
            event.causal_links.append(CausalLink(
                event_id=event.id,
                cause_event_id=grave.source_event_id,
                relation=CausalRelation.RESOLVES,
            ))
        events.append(event)
    return events


def phase_discover_pois(world, living_avatars) -> list[Event]:
    poi_manager = getattr(world, "poi_manager", None)
    if poi_manager is None:
        return []

    events: list[Event] = []
    current_month = int(getattr(world, "month_stamp", 0))
    for avatar in living_avatars:
        for poi in poi_manager.discover_nearby(avatar, current_month=current_month):
            if poi.kind == "grave":
                content = t(
                    "{avatar} discovered a grave at {location}: {poi}",
                    avatar=avatar.name,
                    location=f"({poi.x}, {poi.y})",
                    poi=poi.name,
                )
            elif poi.kind == "treasure":
                content = t(
                    "{avatar} discovered a treasure at {location}: {poi}",
                    avatar=avatar.name,
                    location=f"({poi.x}, {poi.y})",
                    poi=poi.name,
                )
            else:
                content = t(
                    "{avatar} discovered a point of interest at {location}: {poi}",
                    avatar=avatar.name,
                    location=f"({poi.x}, {poi.y})",
                    poi=poi.name,
                )
            events.append(Event(world.month_stamp, content, related_avatars=[avatar.id]))
    return events

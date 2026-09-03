from __future__ import annotations
from typing import TYPE_CHECKING
from src.classes.event import Event
if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar

def _event(owner: "Avatar", content: str, *, related_avatars: list[str] | None = None, is_major: bool = False, source_event_ids: tuple[str, ...] = ()) -> Event:
    event = Event(
        owner.world.month_stamp,
        content,
        related_avatars=related_avatars or [owner.id],
        is_major=is_major,
        event_type="opportunity",
    )
    if source_event_ids:
        from src.classes.causal_link import CausalLink, CausalRelation
        event.causal_links.extend(
            CausalLink(event_id=event.id, cause_event_id=source_event_id, relation=CausalRelation.ENABLED_BY)
            for source_event_id in dict.fromkeys(source_event_ids)
        )
    return event

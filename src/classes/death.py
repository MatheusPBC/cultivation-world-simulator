from __future__ import annotations
from typing import TYPE_CHECKING, Union

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.death_reason import DeathReason
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t

if TYPE_CHECKING:
    from src.classes.core.world import World
    from src.classes.core.avatar import Avatar

def build_death_event(world: World, avatar: Avatar, reason: Union[str, DeathReason]) -> Event:
    reason_str = str(reason)
    region = getattr(getattr(avatar, "tile", None), "region", None)
    event = Event(
        world.month_stamp,
        t("{avatar} — {reason}", avatar=avatar.name, reason=reason_str),
        related_avatars=[str(avatar.id)],
        is_major=True,
        event_type="death",
        render_params={
            "subject_name": avatar.name,
            "region_id": str(getattr(region, "id", "")),
        },
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
    )
    event.causal_payload = {
        "deltas": [
            StateDelta(
                event_id=event.id,
                owner_kind="avatar",
                owner_id=str(avatar.id),
                aspect="life_status",
                before="alive",
                after="dead",
                magnitude=1.0,
            ).to_dict()
        ],
        "decision": None,
    }
    return event


def _complete_death_event(event: Event, avatar: Avatar) -> Event:
    event.event_type = event.event_type or "death"
    event.is_major = True
    event.related_avatars = [str(avatar.id)]
    existing_render_params = event.render_params or {}
    event.render_params = {
        **existing_render_params,
        "subject_name": avatar.name,
        "region_id": str(
            existing_render_params.get("region_id")
            or getattr(
                getattr(getattr(avatar, "tile", None), "region", None),
                "id",
                "",
            )
        ),
    }
    event.fact_kind = FactKind.STATE_TRANSITION
    event.causal_origin = CausalOrigin.DETERMINISTIC
    payload = dict(event.causal_payload or {})
    deltas = list(payload.get("deltas", []))
    normalized_deltas: list[dict] = []
    life_status_seen = False
    for item in deltas:
        if not isinstance(item, dict):
            continue
        is_life_status = (
            item.get("owner_kind") == "avatar"
            and item.get("owner_id") == str(avatar.id)
            and item.get("aspect") == "life_status"
        )
        if is_life_status:
            if life_status_seen:
                continue
            item = dict(item)
            item["event_id"] = event.id
            life_status_seen = True
        normalized_deltas.append(item)
    deltas = normalized_deltas
    if not life_status_seen:
        deltas.append(
            StateDelta(
                event_id=event.id,
                owner_kind="avatar",
                owner_id=str(avatar.id),
                aspect="life_status",
                before="alive",
                after="dead",
                magnitude=1.0,
            ).to_dict()
        )
    payload["deltas"] = deltas
    payload.setdefault("decision", None)
    event.causal_payload = payload
    return event


def handle_death(
    world: World,
    avatar: Avatar,
    reason: Union[str, DeathReason],
    *,
    death_event: Event | None = None,
    cause_event_ids: tuple[str, ...] = (),
) -> Event:
    """
    处理角色死亡的统一入口。
    负责将角色标记为死亡，清理行动队列，但保留角色数据。
    
    Args:
        world: 世界对象
        avatar: 死亡的角色
        reason: 死亡原因（DeathReason对象或字符串）
    """
    event = _complete_death_event(
        death_event or build_death_event(world, avatar, reason),
        avatar,
    )
    for cause_event_id in dict.fromkeys(str(item) for item in cause_event_ids if str(item)):
        if not any(link.cause_event_id == cause_event_id for link in event.causal_links):
            event.causal_links.append(
                CausalLink(
                    event_id=event.id,
                    cause_event_id=cause_event_id,
                    relation=CausalRelation.TRIGGERED_BY,
                )
            )

    reason_str = str(reason)
    
    # 标记为死亡（软删除）
    avatar.set_dead(reason_str, world.month_stamp)

    # 在死亡坐标生成墓碑。战斗夺宝发生在 handle_death 前，因此这里只保留剩余装备。
    poi_manager = getattr(world, "poi_manager", None)
    if poi_manager is not None and hasattr(poi_manager, "create_grave_from_avatar"):
        poi_manager.create_grave_from_avatar(
            avatar,
            current_month=int(world.month_stamp),
            source_event_id=event.id,
        )
    
    # 从管理器中归档（硬移动），并记录变更
    world.avatar_manager.handle_death(avatar.id)

    # 记录已故档案（独立于 AvatarManager，不受 cleanup 影响）
    world.deceased_manager.record_death(avatar)
    
    return event

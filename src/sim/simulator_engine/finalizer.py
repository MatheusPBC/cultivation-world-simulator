from __future__ import annotations

from src.classes.event import Event
from src.classes.close_relation_event_service import append_close_relation_major_observations
from src.run.log import get_logger

from .context import SimulationStepContext


def log_events(events: list[Event]) -> None:
    logger = get_logger().logger
    for event in events:
        logger.info("EVENT: %s", str(event))


def finalize_step(ctx: SimulationStepContext) -> list[Event]:
    for avatar in ctx.world.avatar_manager.avatars.values():
        if avatar.enable_metrics_tracking:
            avatar.record_metrics()

    unique_events: dict[str, Event] = {}
    for event in ctx.events:
        if event.id not in unique_events:
            unique_events[event.id] = event
    final_events = list(unique_events.values())

    special_major_kinds = {
        "battle_kill",
        "bond_lovers_formed",
        "bond_sworn_sibling_formed",
        "bond_master_disciple_formed",
    }
    for event in final_events:
        if not event.is_major or event.is_story or event.event_type in special_major_kinds:
            continue
        for avatar_id in event.related_avatars or []:
            subject = ctx.world.avatar_manager.get_avatar(str(avatar_id))
            if subject is None:
                continue
            params = dict(event.render_params or {})
            params.setdefault("subject_name", getattr(subject, "name", "某人"))
            event.render_params = params
            append_close_relation_major_observations(
                event,
                subject=subject,
                propagation_kind="close_relation_major",
            )

    ctx.causal.attach_to(final_events)

    if ctx.world.event_manager:
        for event in final_events:
            ctx.world.event_manager.add_event(event)

    log_events(final_events)
    ctx.world.month_stamp = ctx.world.month_stamp + 1
    ctx.events = final_events
    # 清理桥接引用：因果记录器只在本轮 step 内有效，避免 step 之外的代码
    # （如 HTTP 请求处理）误读到上一轮遗留的记录器。
    ctx.world.step_causal_recorder = None
    return final_events

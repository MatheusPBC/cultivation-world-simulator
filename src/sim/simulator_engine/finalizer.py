from __future__ import annotations

from collections.abc import Mapping

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.close_relation_event_service import append_close_relation_major_observations
from src.run.log import get_logger

from .context import SimulationStepContext


class EventPersistenceError(RuntimeError):
    pass


class CausalIntegrityError(RuntimeError):
    pass


def _event_by_id(ctx: SimulationStepContext, current: dict[str, Event], event_id: str):
    event = current.get(event_id)
    if event is not None:
        return event
    manager = getattr(ctx.world, "event_manager", None)
    getter = getattr(manager, "get_event_by_id", None)
    return getter(event_id) if callable(getter) else None


def _deltas(event: Event) -> list[dict]:
    payload = event.causal_payload
    if not isinstance(payload, Mapping):
        return []
    raw = payload.get("deltas", [])
    if not isinstance(raw, list) or any(not isinstance(item, Mapping) for item in raw):
        raise CausalIntegrityError(f"event {event.id} has an invalid StateDelta payload")
    return [dict(item) for item in raw]


def validate_causal_integrity(
    ctx: SimulationStepContext, events: list[Event]
) -> None:
    """Reject inverted authorship before the event-store transaction begins."""
    current = {event.id: event for event in events}
    required_decision_fields = set(AgentDecision().to_dict())
    terminal_life_transitions: set[tuple[str, str, str]] = set()
    for event in events:
        deltas = _deltas(event)
        payload = event.causal_payload
        for delta in deltas:
            if str(delta.get("event_id", "")) != str(event.id):
                raise CausalIntegrityError(
                    f"StateDelta on event {event.id} must reference its owning event"
                )
            terminal_key = (
                str(delta.get("owner_kind", "")),
                str(delta.get("owner_id", "")),
                str(delta.get("aspect", "")),
            )
            if terminal_key[0] == "avatar" and terminal_key[2] == "life_status":
                if str(delta.get("after", "")) == "dead":
                    if terminal_key in terminal_life_transitions:
                        raise CausalIntegrityError(
                            f"avatar {terminal_key[1]} has duplicate death transitions"
                        )
                    terminal_life_transitions.add(terminal_key)
        if event.fact_kind is FactKind.DECISION:
            if not isinstance(payload, Mapping) or not isinstance(
                payload.get("decision"), Mapping
            ):
                raise CausalIntegrityError(
                    f"decision event {event.id} must contain AgentDecision"
                )
            decision_payload = dict(payload["decision"])
            if set(decision_payload) != required_decision_fields:
                raise CausalIntegrityError(
                    f"decision event {event.id} has an incomplete AgentDecision"
                )
            decision = AgentDecision.from_dict(decision_payload)
            if (
                not decision.id
                or not decision.subject_kind
                or not decision.subject_id
                or not decision.source
            ):
                raise CausalIntegrityError(
                    f"decision event {event.id} has an invalid AgentDecision"
                )
            if deltas:
                raise CausalIntegrityError(
                    f"decision event {event.id} cannot carry StateDelta"
                )
        if event.causal_origin is CausalOrigin.LLM_INTERPRETATION and deltas:
            raise CausalIntegrityError(
                f"LLM interpretation {event.id} cannot carry StateDelta"
            )
        if event.is_story:
            if deltas:
                raise CausalIntegrityError(f"story event {event.id} cannot mutate state")
            if not event.causal_links:
                raise CausalIntegrityError(
                    f"story event {event.id} requires a factual source"
                )
            for link in event.causal_links:
                cause = _event_by_id(ctx, current, link.cause_event_id)
                if (
                    link.relation is not CausalRelation.CONTRIBUTED_TO
                    or cause is None
                    or cause.is_story
                ):
                    raise CausalIntegrityError(
                        f"story event {event.id} must contribute to a real fact"
                    )
        if deltas:
            for link in event.causal_links:
                cause = _event_by_id(ctx, current, link.cause_event_id)
                if cause is not None and cause.is_story:
                    raise CausalIntegrityError(
                        f"story event {cause.id} cannot cause mutation {event.id}"
                    )
        if event.causal_origin is CausalOrigin.ACTOR_DECISION and deltas:
            has_decision = any(
                (cause := _event_by_id(ctx, current, link.cause_event_id)) is not None
                and cause.fact_kind is FactKind.DECISION
                for link in event.causal_links
            )
            if not has_decision:
                raise CausalIntegrityError(
                    f"actor transition {event.id} requires a real decision cause"
                )


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
    validate_causal_integrity(ctx, final_events)

    if ctx.world.event_manager:
        persisted = ctx.world.event_manager.commit_step(
            final_events,
            ctx.pending_chronicle_chapter,
        )
        if not persisted:
            failed_event_id = final_events[0].id if final_events else "unknown"
            raise EventPersistenceError(
                f"failed to persist causal event {failed_event_id}; month was not advanced"
            )
        ctx.pending_chronicle_chapter = None

    log_events(final_events)
    ctx.world.month_stamp = ctx.world.month_stamp + 1
    ctx.events = final_events
    # 清理桥接引用：因果记录器只在本轮 step 内有效。主要清理职责在
    # SimulationPhaseRunner.run 的 finally 块（覆盖成功/abort/异常三种收尾），
    # 这里的清理只是幂等的兜底，保留是为了 finalize_step 单独被调用
    # （例如测试直接调用 finalize_step(ctx)）时行为依旧正确。
    ctx.world.step_causal_recorder = None
    ctx.world.step_invalidations = None
    return final_events

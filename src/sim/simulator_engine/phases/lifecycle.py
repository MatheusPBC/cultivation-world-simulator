from __future__ import annotations

import asyncio

from src.classes.backstory import process_avatar_backstory
from src.classes.birth import process_births
from src.classes.core.avatar import Avatar
from src.classes.death import build_death_event, handle_death
from src.classes.death_reason import DeathReason, DeathType
from src.classes.event import Event, FactKind
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.state_delta import StateDelta
from src.classes.long_term_objective import process_avatar_long_term_objective
from src.classes.nickname import process_avatar_nickname
from src.i18n import t
from src.sim.avatar_awake import process_awakening


def phase_resolve_death(world, living_avatars: list[Avatar]) -> list[Event]:
    # 死亡结算除了生成死亡事件，还要同步维护 living_avatars。
    # 后续 phase 会继续复用这份列表，因此这里必须把死者原地移除。
    events: list[Event] = []
    dead_avatars: list[Avatar] = []

    for avatar in living_avatars:
        # Repair worlds created before all creation paths used handle_death().
        # They may contain an already-dead avatar in the active collection,
        # which otherwise leaves an avatar portrait on the map with no grave.
        if avatar.is_dead:
            death_event = build_death_event(
                world,
                avatar,
                str((getattr(avatar, "death_info", None) or {}).get("reason") or DeathReason(DeathType.OLD_AGE)),
            )
            handle_death(
                world,
                avatar,
                str((getattr(avatar, "death_info", None) or {}).get("reason") or DeathReason(DeathType.OLD_AGE)),
                death_event=death_event,
            )
            events.append(death_event)
            dead_avatars.append(avatar)
            continue

        is_dead = False
        death_reason: DeathReason | None = None

        if avatar.hp.cur <= 0:
            is_dead = True
            death_reason = DeathReason(DeathType.SERIOUS_INJURY)
        elif avatar.death_by_old_age():
            is_dead = True
            death_reason = DeathReason(DeathType.OLD_AGE)

        if is_dead and death_reason:
            death_event = build_death_event(world, avatar, death_reason)
            handle_death(world, avatar, death_reason, death_event=death_event)
            events.append(death_event)
            dead_avatars.append(avatar)

    # 统一在循环后移除，避免边遍历边修改列表。
    for dead in dead_avatars:
        if dead in living_avatars:
            living_avatars.remove(dead)

    return events


def phase_update_age_and_birth(world, living_avatars: list[Avatar]) -> list[Event]:
    events: list[Event] = []
    for avatar in living_avatars:
        avatar.update_age(world.month_stamp)

    # 凡人管理器和修真者主列表是两套管理链路，这里顺手清一次凡人侧的死者。
    world.mortal_manager.cleanup_dead_mortals(world.month_stamp)

    # 先处理觉醒，再处理出生，保持与旧模拟器相同的时序。
    awakening_events = process_awakening(world)
    if awakening_events:
        events.extend(awakening_events)

    birth_events = process_births(world)
    if birth_events:
        events.extend(birth_events)

    return events


async def phase_backstory_generation(living_avatars: list[Avatar]) -> None:
    # 身世只生成一次；已有 backstory 的角色直接跳过。
    avatars_to_process = [avatar for avatar in living_avatars if avatar.backstory is None]
    if not avatars_to_process:
        return

    await asyncio.gather(*[process_avatar_backstory(avatar) for avatar in avatars_to_process])


async def phase_nickname_generation(living_avatars: list[Avatar]) -> list[Event]:
    # 外号生成允许全量并发，结果里只有真正产出了事件的角色会留下记录。
    results = await asyncio.gather(*[process_avatar_nickname(avatar) for avatar in living_avatars])
    return [event for event in results if event]


def phase_resolve_individual_consequences(living_avatars: list[Avatar]) -> list[Event]:
    events: list[Event] = []
    for avatar in living_avatars:
        summary = avatar.individual_consequences.resolve_if_recovered(
            month=int(avatar.world.month_stamp), current_hp=avatar.hp.cur, max_hp=avatar.hp.max
        )
        if summary is None:
            continue
        event = Event(
            avatar.world.month_stamp,
            t(
                "{avatar_name}'s {severity} injury has recovered.",
                avatar_name=avatar.name,
                severity=summary["severity"],
            ),
            related_avatars=[avatar.id], fact_kind=FactKind.DERIVED_CONDITION,
            causal_payload={"deltas": [
                StateDelta(
                    event_id="",
                    owner_kind="avatar",
                    owner_id=str(avatar.id),
                    aspect="active_injury",
                    before=str(summary),
                    after=None,
                ).to_dict(),
                StateDelta(
                    event_id="",
                    owner_kind="avatar",
                    owner_id=str(avatar.id),
                    aspect="recovery",
                    before=str({"hp": avatar.hp.cur, "active_injury": summary}),
                    after=str({"hp": avatar.hp.cur, "active_injury": None}),
                    magnitude=0.0,
                ).to_dict(),
            ], "decision": None},
        )
        for delta in event.causal_payload["deltas"]:
            delta["event_id"] = event.id
        event.causal_links = [CausalLink(event_id=event.id, cause_event_id=cause_id, relation=CausalRelation.RESOLVES) for cause_id in summary["cause_event_ids"]]
        events.append(event)
    return events


async def phase_long_term_objective_thinking(living_avatars: list[Avatar]) -> list[Event]:
    # 长期目标思考是月度例行更新，不要求角色处于空闲状态。
    results = await asyncio.gather(
        *[process_avatar_long_term_objective(avatar) for avatar in living_avatars]
    )
    return [event for event in results if event]

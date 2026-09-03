from __future__ import annotations

import asyncio

from src.classes.core.avatar import Avatar
from src.classes.celestial_phenomenon import get_random_celestial_phenomenon
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.classes.observe import get_avatar_observation_radius
from src.i18n import t
from src.systems.autonomous_custom_content_service import try_trigger_autonomous_custom_creation
from src.systems.fortune import try_trigger_fortune, try_trigger_misfortune
from src.systems.opportunity import phase_check_opportunities, phase_generate_opportunities  # noqa: F401
from src.systems.world_secret import phase_world_secret_discovery  # noqa: F401
from src.systems.fate_revelation import try_trigger_fate_revelation
from src.systems.treasure import phase_treasure_lifecycle as run_treasure_lifecycle
from src.systems.time import Month
from src.systems.gu import process_avatar_gu_effects
from src.classes.official_rank import (
    OFFICIAL_NONE,
    apply_official_reputation_delta,
    get_monthly_reputation_decay,
    get_official_rank_name,
    resolve_rank_changes,
)


def _observed_regions_this_tick(world, avatar: Avatar) -> set:
    # 按观察半径重新计算“本 tick 可见”的区域集合。角色在同一月内的位置
    # 不会在 decide_actions 之前发生变化（移动发生在更晚的 execute_actions），
    # 所以在感知 phase 和占地 phase 里各自独立调用本函数，对同一位置总是
    # 得到相同结果——这正是让占地 phase 可以安全重跑的原因，而不必依赖
    # 角色终身累积的 known_regions。
    radius = get_avatar_observation_radius(avatar)

    # 先按包围盒缩小搜索范围，再用曼哈顿距离判断真正可见区域。
    start_x = max(0, avatar.pos_x - radius)
    end_x = min(world.map.width - 1, avatar.pos_x + radius)
    start_y = max(0, avatar.pos_y - radius)
    end_y = min(world.map.height - 1, avatar.pos_y + radius)

    observed_regions = set()
    for x in range(start_x, end_x + 1):
        for y in range(start_y, end_y + 1):
            if abs(x - avatar.pos_x) + abs(y - avatar.pos_y) > radius:
                continue

            tile = world.map.get_tile(x, y)
            if tile.region:
                observed_regions.add(tile.region)

    return observed_regions


def phase_update_perception_and_knowledge(world, living_avatars: list[Avatar]) -> list[Event]:
    # 只做一件事：按观察半径刷新 known_regions。这是纯粹的集合并集操作，
    # 天然幂等——重复执行不会产生任何可观察差异，因此可以安全地留在
    # decide_actions 之前。
    #
    # Knowledge only exposes the existing Occupy action. Discovery itself never
    # mutates territorial ownership.
    for avatar in living_avatars:
        for region in _observed_regions_this_tick(world, avatar):
            avatar.known_regions.add(region.id)

    return []


async def phase_passive_effects(world, living_avatars: list[Avatar]) -> list[Event]:
    events: list[Event] = []
    for avatar in living_avatars:
        # 先处理本地状态副作用，再统一并发世界事件。
        avatar.process_elixir_expiration(int(world.month_stamp))
        events.extend(process_avatar_gu_effects(avatar, int(world.month_stamp)))
        avatar.update_time_effect()

    target_avatars = [avatar for avatar in living_avatars if avatar.can_trigger_world_event]
    results = await asyncio.gather(
        *[try_trigger_fortune(avatar) for avatar in target_avatars],
        *[try_trigger_misfortune(avatar) for avatar in target_avatars],
        *[try_trigger_fate_revelation(avatar, world) for avatar in target_avatars],
    )
    events.extend([event for result in results if result for event in result])
    events.extend(await phase_generate_opportunities(world, target_avatars))
    return events


async def phase_autonomous_custom_creation(world, living_avatars: list[Avatar]) -> list[Event]:
    target_avatars = [avatar for avatar in living_avatars if avatar.can_trigger_world_event]
    results = await asyncio.gather(
        *[try_trigger_autonomous_custom_creation(avatar, world) for avatar in target_avatars]
    )
    return [event for result in results for event in result]


def phase_treasure_lifecycle(world) -> list[Event]:
    return run_treasure_lifecycle(world)


async def phase_process_gatherings(world) -> list[Event]:
    # 开局年份不触发聚会，避免世界尚未稳定时就生成大规模社交事件。
    if world.month_stamp.get_year() <= world.start_year:
        return []

    return await world.gathering_manager.check_and_run_all(world)


def phase_update_celestial_phenomenon(world) -> list[Event]:
    # 天象只在初始化时生成一次，或在每年一月检查是否到期切换。
    events: list[Event] = []
    current_year = world.month_stamp.get_year()
    current_month = world.month_stamp.get_month()

    should_update = False
    is_init = False

    if world.current_phenomenon is None:
        should_update = True
        is_init = True
    elif current_month == Month.JANUARY:
        elapsed_years = current_year - world.phenomenon_start_year
        if elapsed_years >= world.current_phenomenon.duration_years:
            should_update = True

    if not should_update:
        return events

    old_phenomenon = world.current_phenomenon
    new_phenomenon = get_random_celestial_phenomenon()
    if not new_phenomenon:
        return events

    # 切换世界级环境状态后，再补一条公开事件供前端和历史系统消费。
    world.current_phenomenon = new_phenomenon
    world.phenomenon_start_year = current_year

    if is_init:
        desc = t(
            "world_creation_phenomenon",
            name=new_phenomenon.name,
            desc=new_phenomenon.desc,
        )
    else:
        desc = t(
            "phenomenon_change",
            old_name=old_phenomenon.name,
            new_name=new_phenomenon.name,
            new_desc=new_phenomenon.desc,
        )

    events.append(Event(world.month_stamp, desc, related_avatars=None))
    return events


# Natural logistic growth is continuous background state. The chronicle only
# needs a population transition once residents would notice a material shift.
POPULATION_EVENT_MIN_ABSOLUTE_CHANGE = 25.0


def phase_update_city_population(world, causal=None, invalidations=None) -> list[Event]:
    # 城市人口使用 logistic 公式按月自然变化。
    # `causal` 是可选的 CausalRecorder（见 causal_recorder.py）：
    # 缺省为 None 时行为与本次改动之前完全一致，不产生任何事件。
    events: list[Event] = []
    for region in world.map.regions.values():
        if isinstance(region, CityRegion):
            before = region.population
            region.update_population_monthly()
            after = region.population
            source_event_id = None
            if causal is not None and abs(after - before) >= POPULATION_EVENT_MIN_ABSOLUTE_CHANGE:
                event = Event(
                    world.month_stamp,
                    t(
                        "{region} population changed from {before} to {after}",
                        region=region.name,
                        before=f"{before:.1f}",
                        after=f"{after:.1f}",
                    ),
                    related_avatars=None,
                    is_major=False,
                    fact_kind=FactKind.STATE_TRANSITION,
                )
                causal.record_delta(
                    event.id,
                    StateDelta(
                        owner_kind="region",
                        owner_id=str(region.id),
                        aspect="population",
                        before=str(before),
                        after=str(after),
                        magnitude=after - before,
                    ),
                )
                events.append(event)
                source_event_id = event.id
            if invalidations is not None and after != before:
                from src.sim.simulator_engine.domain_invalidation import (
                    DomainInvalidation,
                    DomainInvalidationLayer,
                    DomainInvalidationReason,
                )

                invalidations.mark(DomainInvalidation(
                    layer=DomainInvalidationLayer.MECHANICAL,
                    domain="population",
                    target_kind="region",
                    target_id=str(region.id),
                    reason=DomainInvalidationReason.POPULATION_CHANGED,
                    source_event_ids=(source_event_id,) if source_event_id else (),
                    revision=source_event_id or f"population:{region.id}:{world.month_stamp}",
                ))
    return events


def phase_update_dynasty(world) -> list[Event]:
    dynasty = getattr(world, "dynasty", None)
    if dynasty is None:
        return []

    from src.systems.imperial_crisis_service import ensure_succession_crisis

    ensure_succession_crisis(world)
    return []


def phase_update_official_system(world, living_avatars: list[Avatar]) -> list[Event]:
    events: list[Event] = []
    current_month = int(world.month_stamp)
    for avatar in living_avatars:
        rank_key = str(getattr(avatar, "official_rank", OFFICIAL_NONE) or OFFICIAL_NONE)
        if rank_key == OFFICIAL_NONE:
            continue
        last_governance_month = getattr(avatar, "last_governance_month", None)
        if last_governance_month is None:
            continue
        if current_month - int(last_governance_month) <= 6:
            continue

        decay = get_monthly_reputation_decay(rank_key)
        if decay <= 0:
            continue

        old_rank = rank_key
        apply_official_reputation_delta(avatar, -decay)
        _old_rank, new_rank = resolve_rank_changes(avatar)
        if new_rank != old_rank:
            avatar.recalc_effects()
            events.append(
                Event(
                    month_stamp=world.month_stamp,
                    content=t(
                        "{avatar} neglected governance for too long, losing court reputation and falling from {old_rank} to {new_rank}.",
                        avatar=avatar.name,
                        old_rank=get_official_rank_name(old_rank),
                        new_rank=get_official_rank_name(new_rank),
                    ),
                    related_avatars=[avatar.id],
                    is_major=True,
                )
            )
    return events

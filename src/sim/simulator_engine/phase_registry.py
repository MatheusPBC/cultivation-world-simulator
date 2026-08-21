from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .finalizer import finalize_step
from .phases import actions, annual, lifecycle, poi, sect_war, social, world as world_phases


PhaseHandler = Callable[[Any, Any], Any]


@dataclass(frozen=True, slots=True)
class SimulationPhase:
    name: str
    index: int
    handler_name: str
    handler: PhaseHandler
    reset_check_after: bool = True


def update_perception_and_knowledge(simulator, ctx):
    ctx.add_events(world_phases.phase_update_perception_and_knowledge(simulator.world, ctx.living_avatars))


async def decide_actions(simulator, ctx):
    ctx.add_events(await actions.phase_decide_actions(simulator.world, ctx.living_avatars))


async def long_term_objective_thinking(_simulator, ctx):
    # 移到 decide_actions 之后：`process_avatar_long_term_objective` 会真实
    # 写入 avatar.long_term_objective（且不是 union 式合并，可能替换旧目标），
    # 一旦在 decide_actions 之前写入而随后触发 RequiredDecisionFailed，
    # 整月从 phase 1 重跑时 `can_generate_long_term_objective` 会因为
    # “距离上次设定 <5 年”而判定不需要重新生成——目标已经在活的 World 里
    # 生效，但描述它的 Event 已随失败批次一起丢弃，永远补不回来。这与占地
    # （残留问题 a）同一类残留，此前 spec §6.4 第 3 行错误地把它标注为
    # “Yes——overwritten on re-run”，见 docs/specs/causal-world-kernel.md §13.3a。
    # 代价与占地/聚会一致：决策提示（`avatar.get_expanded_info` 里的
    # long_term_objective 字段）会晚一个月看到新目标，这是本任务已经接受的
    # 同类信息滞后，不是新增的行为退化。
    ctx.add_events(await lifecycle.phase_long_term_objective_thinking(ctx.living_avatars))


def claim_ownerless_regions(simulator, ctx):
    # 占地（曾经是 update_perception_and_knowledge 的一部分）和聚会
    # （曾经在 decide_actions 之前）都移到这里：两者都会做真实且不可逆的
    # 状态变更，如果留在 decide_actions 之前，一次 RequiredDecisionFailed
    # 触发的整月重跑会把它们再执行一次。见
    # docs/specs/causal-world-kernel.md §6.4 残留问题 (a)(b)。
    ctx.add_events(world_phases.phase_claim_ownerless_regions(simulator.world, ctx.living_avatars))


async def process_gatherings(simulator, ctx):
    ctx.add_events(await world_phases.phase_process_gatherings(simulator.world))


def commit_next_plans(_simulator, ctx):
    ctx.add_events(actions.phase_commit_next_plans(ctx.living_avatars))


async def execute_actions(_simulator, ctx):
    ctx.add_events(await actions.phase_execute_actions(ctx.living_avatars))


async def check_opportunities(simulator, ctx):
    ctx.add_events(await world_phases.phase_check_opportunities(simulator.world, ctx.living_avatars))


async def world_secret_discovery(simulator, ctx):
    ctx.add_events(await world_phases.phase_world_secret_discovery(simulator.world, ctx.living_avatars))


def handle_interactions(simulator, ctx):
    social.phase_handle_interactions(simulator.world.avatar_manager, ctx.events, ctx.processed_event_ids)


async def evolve_relations(simulator, ctx):
    ctx.add_events(await social.phase_evolve_relations(simulator.world.avatar_manager, ctx.living_avatars))


def resolve_death(simulator, ctx):
    ctx.add_events(lifecycle.phase_resolve_death(simulator.world, ctx.living_avatars))


def discover_pois(simulator, ctx):
    ctx.add_events(poi.phase_discover_pois(simulator.world, ctx.living_avatars))


def treasure_lifecycle(simulator, ctx):
    ctx.add_events(world_phases.phase_treasure_lifecycle(simulator.world))


def update_age_and_birth(simulator, ctx):
    ctx.add_events(lifecycle.phase_update_age_and_birth(simulator.world, ctx.living_avatars))


async def backstory_generation(_simulator, ctx):
    await lifecycle.phase_backstory_generation(ctx.living_avatars)


async def passive_effects(simulator, ctx):
    ctx.add_events(await world_phases.phase_passive_effects(simulator.world, ctx.living_avatars))


async def autonomous_custom_creation(simulator, ctx):
    ctx.add_events(await world_phases.phase_autonomous_custom_creation(simulator.world, ctx.living_avatars))


async def random_minor_events(simulator, ctx):
    ctx.add_events(await world_phases.phase_random_minor_events(simulator.world, ctx.living_avatars))


def background_npc_events(simulator, ctx):
    ctx.add_events(world_phases.phase_background_npc_events(simulator.world, ctx.living_avatars))


async def sect_random_event(simulator, ctx):
    ctx.add_events(await world_phases.phase_sect_random_event(simulator.world))


async def sect_wars(simulator, ctx):
    ctx.add_events(await sect_war.phase_handle_sect_wars(simulator, ctx.living_avatars))


async def nickname_generation(_simulator, ctx):
    ctx.add_events(await lifecycle.phase_nickname_generation(ctx.living_avatars))


def update_celestial_phenomenon(simulator, ctx):
    ctx.add_events(world_phases.phase_update_celestial_phenomenon(simulator.world))


def update_city_population(simulator, ctx):
    # 唯一需要转发 ctx（因果记录器）的 wrapper：该 flow 此前完全丢弃 ctx，
    # 现在把 ctx.causal 转发给 owner，使其能在人口变化后记录 StateDelta。
    ctx.add_events(world_phases.phase_update_city_population(simulator.world, ctx.causal))


def update_dynasty_and_officials(simulator, ctx):
    ctx.add_events(world_phases.phase_update_dynasty(simulator.world))
    ctx.add_events(world_phases.phase_update_official_system(simulator.world, ctx.living_avatars))


def update_calculated_relations(simulator, ctx):
    social.phase_update_calculated_relations(simulator.world, ctx.living_avatars)


async def annual_maintenance(simulator, ctx):
    await annual.run_annual_maintenance(simulator, ctx)


def finalize_step_phase(_simulator, ctx):
    return finalize_step(ctx)


SIMULATION_PHASES: tuple[SimulationPhase, ...] = (
    SimulationPhase("update_perception_and_knowledge", 1, "update_perception_and_knowledge", update_perception_and_knowledge),
    SimulationPhase("decide_actions", 2, "decide_actions", decide_actions),
    SimulationPhase("long_term_objective_thinking", 3, "long_term_objective_thinking", long_term_objective_thinking),
    SimulationPhase("claim_ownerless_regions", 4, "claim_ownerless_regions", claim_ownerless_regions),
    SimulationPhase("process_gatherings", 5, "process_gatherings", process_gatherings),
    SimulationPhase("commit_next_plans", 6, "commit_next_plans", commit_next_plans),
    SimulationPhase("execute_actions", 7, "execute_actions", execute_actions),
    SimulationPhase("check_opportunities", 8, "check_opportunities", check_opportunities),
    SimulationPhase("world_secret_discovery", 9, "world_secret_discovery", world_secret_discovery),
    SimulationPhase("handle_interactions_first", 10, "handle_interactions", handle_interactions),
    SimulationPhase("evolve_relations", 11, "evolve_relations", evolve_relations),
    SimulationPhase("resolve_death", 12, "resolve_death", resolve_death),
    SimulationPhase("treasure_lifecycle", 13, "treasure_lifecycle", treasure_lifecycle),
    SimulationPhase("discover_pois", 14, "discover_pois", discover_pois),
    SimulationPhase("update_age_and_birth", 15, "update_age_and_birth", update_age_and_birth),
    SimulationPhase("backstory_generation", 16, "backstory_generation", backstory_generation),
    SimulationPhase("passive_effects", 17, "passive_effects", passive_effects),
    SimulationPhase("autonomous_custom_creation", 18, "autonomous_custom_creation", autonomous_custom_creation),
    SimulationPhase("random_minor_events", 19, "random_minor_events", random_minor_events),
    SimulationPhase("background_npc_events", 20, "background_npc_events", background_npc_events),
    SimulationPhase("sect_random_event", 21, "sect_random_event", sect_random_event),
    SimulationPhase("sect_wars", 22, "sect_wars", sect_wars),
    SimulationPhase("nickname_generation", 23, "nickname_generation", nickname_generation),
    SimulationPhase("update_celestial_phenomenon", 24, "update_celestial_phenomenon", update_celestial_phenomenon),
    SimulationPhase("update_city_population", 25, "update_city_population", update_city_population),
    SimulationPhase("update_dynasty_and_officials", 26, "update_dynasty_and_officials", update_dynasty_and_officials),
    SimulationPhase("handle_interactions_second", 27, "handle_interactions", handle_interactions),
    SimulationPhase("update_calculated_relations", 28, "update_calculated_relations", update_calculated_relations),
    SimulationPhase("annual_maintenance", 29, "annual_maintenance", annual_maintenance),
    SimulationPhase("finalize_step", 30, "finalize_step", finalize_step_phase, reset_check_after=False),
)


def get_simulation_phases() -> tuple[SimulationPhase, ...]:
    return SIMULATION_PHASES

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .finalizer import finalize_step
from .phases import actions, annual, appraisal, lifecycle, poi, social, world as world_phases


PhaseHandler = Callable[[Any, Any], Any]


@dataclass(frozen=True, slots=True)
class SimulationPhase:
    name: str
    index: int
    handler_name: str
    handler: PhaseHandler
    reset_check_after: bool = True


def expire_region_formations(_simulator, ctx):
    from src.systems.formation import cleanup_expired_region_formations

    ctx.add_events(
        cleanup_expired_region_formations(
            ctx.world,
            int(ctx.month_stamp or ctx.world.month_stamp),
        )
    )


def expire_graves(_simulator, ctx):
    ctx.add_events(poi.phase_expire_graves(ctx.world))


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


def resolve_individual_consequences(_simulator, ctx):
    ctx.add_events(lifecycle.phase_resolve_individual_consequences(ctx.living_avatars))


async def backstory_generation(_simulator, ctx):
    await lifecycle.phase_backstory_generation(ctx.living_avatars)


async def passive_effects(simulator, ctx):
    ctx.add_events(await world_phases.phase_passive_effects(simulator.world, ctx.living_avatars))


async def autonomous_custom_creation(simulator, ctx):
    ctx.add_events(await world_phases.phase_autonomous_custom_creation(simulator.world, ctx.living_avatars))


async def nickname_generation(_simulator, ctx):
    ctx.add_events(await lifecycle.phase_nickname_generation(ctx.living_avatars))


def update_celestial_phenomenon(simulator, ctx):
    ctx.add_events(world_phases.phase_update_celestial_phenomenon(simulator.world))


def update_city_population(simulator, ctx):
    # 唯一需要转发 ctx（因果记录器）的 wrapper：该 flow 此前完全丢弃 ctx，
    # 现在把 ctx.causal 转发给 owner，使其能在人口变化后记录 StateDelta。
    ctx.add_events(world_phases.phase_update_city_population(
        simulator.world,
        ctx.causal,
        ctx.invalidations,
    ))


def update_regional_economy(simulator, ctx):
    from src.systems.regional_economy import phase_update_regional_economy
    ctx.add_events(phase_update_regional_economy(
        simulator.world,
        ctx.causal,
        ctx.invalidations,
    ))


async def react_economy(simulator, ctx):
    from src.systems.economy_reactivity import process_economy_reactivity

    ctx.add_events(await process_economy_reactivity(
        simulator.world,
        current_events=ctx.events,
        invalidations=ctx.invalidations,
        budget=ctx.causal_budget,
    ))


def advance_urban_capacity_projects(simulator, ctx):
    from src.systems.urban_capacity_project import advance_urban_capacity_projects as advance

    ctx.add_events(advance(simulator.world, invalidations=ctx.invalidations))


def update_dynasty_and_officials(simulator, ctx):
    ctx.add_events(world_phases.phase_update_dynasty(simulator.world))
    ctx.add_events(world_phases.phase_update_official_system(simulator.world, ctx.living_avatars))


def update_calculated_relations(simulator, ctx):
    social.phase_update_calculated_relations(simulator.world, ctx.living_avatars)


async def process_dao_rites(simulator, ctx):
    from src.systems.celestial_dao_service import process_grounded_dao_rites

    ctx.add_events(await process_grounded_dao_rites(simulator.world, ctx.events))


async def annual_maintenance(simulator, ctx):
    await annual.run_annual_maintenance(simulator, ctx)


def update_regional_climate(simulator, ctx):
    from src.systems.regional_climate import advance_regional_climate

    ctx.add_events(
        advance_regional_climate(
            simulator.world,
            invalidations=ctx.invalidations,
        )
    )


def update_regional_floods(simulator, ctx):
    from src.systems.regional_floods import advance_regional_floods

    ctx.add_events(
        advance_regional_floods(
            simulator.world,
            invalidations=ctx.invalidations,
        )
    )


def resolve_material_hazard_impacts(simulator, ctx):
    from src.systems.material_hazard_impacts import process_material_hazard_impacts

    ctx.add_events(
        process_material_hazard_impacts(
            simulator.world,
            current_events=ctx.events,
            invalidations=ctx.invalidations,
        )
    )


async def restore_infrastructure_sites(simulator, ctx):
    from src.systems.infrastructure_restoration import process_infrastructure_restoration

    ctx.add_events(
        await process_infrastructure_restoration(
            simulator.world,
            current_events=ctx.events,
            invalidations=ctx.invalidations,
            budget=ctx.causal_budget,
        )
    )


def update_route_infrastructure_dependencies(simulator, ctx):
    from src.systems.route_infrastructure_dependency import (
        process_route_infrastructure_dependencies,
    )

    ctx.add_events(
        process_route_infrastructure_dependencies(
            simulator.world,
            current_events=ctx.events,
            invalidations=ctx.invalidations,
        )
    )


async def evaluate_semantic_world(simulator, ctx):
    from src.systems.semantic_world.service import evaluate_semantic_world as evaluate
    from src.systems.city_reactivity import enqueue_city_transitions
    from src.systems.government_reactivity import enqueue_government_transitions
    from src.systems.organization_reactivity import enqueue_organization_transitions
    from src.systems.population_reactivity import enqueue_population_transitions
    from src.sim.simulator_engine.domain_invalidation import (
        DomainInvalidationLayer,
        DomainInvalidationReason,
    )

    mechanical = ctx.invalidations.drain(layer=DomainInvalidationLayer.MECHANICAL)
    sources_by_target: dict[str, list[str]] = {}
    climate_sources_by_target: dict[str, list[str]] = {}
    for item in mechanical:
        if item.reason is DomainInvalidationReason.REGIONAL_HAZARD_CHANGED:
            # The active hazard changes the region fingerprint and actor context,
            # but must not become generic evidence for unrelated semantic rules.
            continue
        destination = (
            climate_sources_by_target
            if item.reason is DomainInvalidationReason.CLIMATE_CHANGED
            else sources_by_target
        )
        for source_event_id in item.source_event_ids:
            destination.setdefault(
                f"{item.target_kind}:{item.target_id}",
                [],
            ).append(source_event_id)
    health_sources_by_target: dict[str, list[str]] = {}
    spiritual_sources_by_target: dict[str, list[str]] = {}
    avatars_by_id = {
        str(avatar.id): avatar
        for avatar in simulator.world.avatar_manager.get_living_avatars()
    }
    for event in ctx.events:
        if event.event_type in {
            "death",
            "formation_set",
            "formation_expired",
            "grave_expired",
            "treasure_spawned",
            "treasure_expired",
            "treasure_claimed",
        }:
            params = event.render_params if isinstance(event.render_params, dict) else {}
            region_id = str(params.get("region_id", "")).strip()
            if region_id:
                target_ref = f"region:{region_id}"
                pending = spiritual_sources_by_target.setdefault(target_ref, [])
                if event.id not in pending:
                    pending.append(event.id)
        payload = event.causal_payload if isinstance(event.causal_payload, dict) else {}
        for delta in payload.get("deltas", []):
            if not isinstance(delta, dict):
                continue
            if delta.get("owner_kind") != "avatar" or delta.get("aspect") not in {
                "hp",
                "active_injury",
                "recovery",
            }:
                continue
            avatar = avatars_by_id.get(str(delta.get("owner_id", "")))
            region = getattr(getattr(avatar, "tile", None), "region", None)
            if region is None:
                continue
            target_ref = f"region:{region.id}"
            pending = health_sources_by_target.setdefault(target_ref, [])
            if event.id not in pending:
                pending.append(event.id)
    events = await evaluate(
        simulator.world,
        source_event_ids_by_target=sources_by_target,
        climate_source_event_ids_by_target=climate_sources_by_target,
        health_source_event_ids_by_target=health_sources_by_target,
        spiritual_source_event_ids_by_target=spiritual_sources_by_target,
        budget=ctx.causal_budget,
    )
    enqueue_government_transitions(simulator.world, events, ctx.invalidations)
    enqueue_organization_transitions(simulator.world, events, ctx.invalidations)
    enqueue_city_transitions(simulator.world, events, ctx.invalidations)
    enqueue_population_transitions(simulator.world, events, ctx.invalidations)
    ctx.add_events(events)


async def react_government(simulator, ctx):
    from src.systems.institution_bootstrap import synchronize_institutional_authority
    from src.systems.government_reactivity import (
        enqueue_pending_petitions,
        enqueue_pending_stoppages,
        enqueue_unreacted_government_conditions,
        process_government_reactivity,
    )

    ctx.add_events(
        synchronize_institutional_authority(
            simulator.world,
            current_events=ctx.events,
        )
    )
    enqueue_unreacted_government_conditions(simulator.world, ctx.invalidations)
    # This phase runs before the population's, so a petition filed last month
    # is answered here, on the next cycle. The step's own events are offered
    # too, so a petition already produced this month is not missed.
    enqueue_pending_petitions(
        simulator.world, ctx.invalidations, current_events=ctx.events
    )
    # A public work stoppage the government knows about asks for an answer the
    # same way, whether or not its cycle is already over.
    enqueue_pending_stoppages(simulator.world, ctx.invalidations)
    ctx.add_events(await process_government_reactivity(
        simulator.world,
        current_events=ctx.events,
        invalidations=ctx.invalidations,
        budget=ctx.causal_budget,
    ))


async def react_organization(simulator, ctx):
    from src.systems.organization_reactivity import (
        enqueue_unreacted_organization_conditions,
        process_organization_reactivity,
    )

    enqueue_unreacted_organization_conditions(simulator.world, ctx.invalidations)
    ctx.add_events(await process_organization_reactivity(
        simulator.world,
        current_events=ctx.events,
        invalidations=ctx.invalidations,
        budget=ctx.causal_budget,
    ))


async def react_city(simulator, ctx):
    from src.systems.city_reactivity import (
        enqueue_unreacted_city_conditions,
        process_city_reactivity,
    )

    enqueue_unreacted_city_conditions(simulator.world, ctx.invalidations)
    ctx.add_events(await process_city_reactivity(
        simulator.world,
        current_events=ctx.events,
        invalidations=ctx.invalidations,
        budget=ctx.causal_budget,
    ))


async def react_population(simulator, ctx):
    from src.systems.population_reactivity import (
        enqueue_unreacted_population_conditions,
        process_population_reactivity,
    )

    enqueue_unreacted_population_conditions(simulator.world, ctx.invalidations)
    ctx.add_events(await process_population_reactivity(
        simulator.world,
        current_events=ctx.events,
        invalidations=ctx.invalidations,
        budget=ctx.causal_budget,
    ))


def carry_forward_mechanical_invalidations(simulator, ctx):
    """Persist late mechanical evidence for next month's semantic pass."""
    from src.sim.simulator_engine.domain_invalidation import DomainInvalidationLayer

    pending = simulator.world.mechanical_language.pending_target_source_event_ids
    affinity_pending = (
        simulator.world.mechanical_language.pending_affinity_source_event_ids
    )
    events_by_id = {event.id: event for event in ctx.events}
    for item in ctx.invalidations.drain(layer=DomainInvalidationLayer.MECHANICAL):
        target_ref = f"{item.target_kind}:{item.target_id}"
        capability_id = next(
            (
                str(event.render_params.get("capability_id", "")).strip()
                for source_id in item.source_event_ids
                if (event := events_by_id.get(source_id)) is not None
                and isinstance(event.render_params, dict)
                and str(event.render_params.get("capability_id", "")).strip()
            ),
            "",
        )
        if capability_id:
            source_ids = affinity_pending.setdefault(target_ref, {}).setdefault(
                f"urban_service:{capability_id}",
                [],
            )
            source_ids.extend(
                source_id
                for source_id in item.source_event_ids
                if source_id not in source_ids
            )
            continue
        source_ids = pending.setdefault(target_ref, [])
        source_ids.extend(
            source_id
            for source_id in item.source_event_ids
            if source_id not in source_ids
        )


async def generate_event_appraisals(_simulator, ctx):
    # 紧挨 finalizer 之前：此时本月所有事件都已经产生并进入 ctx.events，
    # 但还没有落库，所以解读可以直接挂到事件上，由 finalize_step 与事件
    # 主体在同一个事务里一起写入。
    await appraisal.phase_generate_event_appraisals(ctx.world, ctx.events)


async def generate_chronicle(_simulator, ctx):
    from src.systems.chronicle_service import ChronicleService

    # Chronicle sees this step's causal facts before finalizer persistence;
    # finalizer attaches again idempotently as its normal storage boundary.
    ctx.causal.attach_to(ctx.events)
    ctx.pending_chronicle_chapter = await ChronicleService().maybe_generate_chapter(ctx.world, ctx.events)


def finalize_step_phase(_simulator, ctx):
    return finalize_step(ctx)


SIMULATION_PHASES: tuple[SimulationPhase, ...] = (
    SimulationPhase("update_perception_and_knowledge", 1, "update_perception_and_knowledge", update_perception_and_knowledge),
    SimulationPhase("expire_region_formations", 2, "expire_region_formations", expire_region_formations),
    SimulationPhase("expire_graves", 3, "expire_graves", expire_graves),
    SimulationPhase("decide_actions", 4, "decide_actions", decide_actions),
    SimulationPhase("long_term_objective_thinking", 5, "long_term_objective_thinking", long_term_objective_thinking),
    SimulationPhase("process_gatherings", 6, "process_gatherings", process_gatherings),
    SimulationPhase("commit_next_plans", 7, "commit_next_plans", commit_next_plans),
    SimulationPhase("execute_actions", 8, "execute_actions", execute_actions),
    SimulationPhase("check_opportunities", 9, "check_opportunities", check_opportunities),
    SimulationPhase("world_secret_discovery", 10, "world_secret_discovery", world_secret_discovery),
    SimulationPhase("handle_interactions_first", 11, "handle_interactions", handle_interactions),
    SimulationPhase("evolve_relations", 12, "evolve_relations", evolve_relations),
    SimulationPhase("resolve_death", 13, "resolve_death", resolve_death),
    SimulationPhase("treasure_lifecycle", 14, "treasure_lifecycle", treasure_lifecycle),
    SimulationPhase("discover_pois", 15, "discover_pois", discover_pois),
    SimulationPhase("update_age_and_birth", 16, "update_age_and_birth", update_age_and_birth),
    SimulationPhase("backstory_generation", 17, "backstory_generation", backstory_generation),
    SimulationPhase("passive_effects", 18, "passive_effects", passive_effects),
    SimulationPhase("resolve_individual_consequences", 19, "resolve_individual_consequences", resolve_individual_consequences),
    SimulationPhase("autonomous_custom_creation", 20, "autonomous_custom_creation", autonomous_custom_creation),
    SimulationPhase("nickname_generation", 21, "nickname_generation", nickname_generation),
    SimulationPhase("update_celestial_phenomenon", 22, "update_celestial_phenomenon", update_celestial_phenomenon),
    SimulationPhase("update_city_population", 23, "update_city_population", update_city_population),
    SimulationPhase("update_regional_economy", 24, "update_regional_economy", update_regional_economy),
    SimulationPhase("react_economy", 25, "react_economy", react_economy),
    SimulationPhase("advance_urban_capacity_projects", 26, "advance_urban_capacity_projects", advance_urban_capacity_projects),
    SimulationPhase("update_dynasty_and_officials", 27, "update_dynasty_and_officials", update_dynasty_and_officials),
    SimulationPhase("handle_interactions_second", 28, "handle_interactions", handle_interactions),
    SimulationPhase("update_calculated_relations", 29, "update_calculated_relations", update_calculated_relations),
    SimulationPhase("process_dao_rites", 30, "process_dao_rites", process_dao_rites),
    SimulationPhase("annual_maintenance", 31, "annual_maintenance", annual_maintenance),
    SimulationPhase("update_regional_climate", 32, "update_regional_climate", update_regional_climate),
    SimulationPhase("update_regional_floods", 33, "update_regional_floods", update_regional_floods),
    SimulationPhase("resolve_material_hazard_impacts", 34, "resolve_material_hazard_impacts", resolve_material_hazard_impacts),
    SimulationPhase("restore_infrastructure_sites", 35, "restore_infrastructure_sites", restore_infrastructure_sites),
    SimulationPhase("update_route_infrastructure_dependencies", 36, "update_route_infrastructure_dependencies", update_route_infrastructure_dependencies),
    SimulationPhase("evaluate_semantic_world", 37, "evaluate_semantic_world", evaluate_semantic_world),
    SimulationPhase("react_government", 38, "react_government", react_government),
    SimulationPhase("react_organization", 39, "react_organization", react_organization),
    SimulationPhase("react_city", 40, "react_city", react_city),
    SimulationPhase("react_population", 41, "react_population", react_population),
    SimulationPhase("carry_forward_mechanical_invalidations", 42, "carry_forward_mechanical_invalidations", carry_forward_mechanical_invalidations),
    SimulationPhase("generate_event_appraisals", 43, "generate_event_appraisals", generate_event_appraisals),
    SimulationPhase("generate_chronicle", 44, "generate_chronicle", generate_chronicle),
    SimulationPhase("finalize_step", 45, "finalize_step", finalize_step_phase, reset_check_after=False),
)


def get_simulation_phases() -> tuple[SimulationPhase, ...]:
    return SIMULATION_PHASES

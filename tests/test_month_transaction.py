from __future__ import annotations

import random

import pytest

from src.classes.environment.region import CityRegion
from src.classes.environment.city_state import CityDistrict, CityGovernance, CityState, UrbanAsset
from src.classes.event import Event, FactKind
from src.classes.agent_decision import AgentDecision
from src.classes.causal_origin import CausalOrigin
from src.classes.individual_consequence import record_hp_change_from_event
from src.classes.mechanical_language import ConditionInstance
from src.classes.regional_economy import RegionalEconomyState
from src.sim.simulator import Simulator
from src.sim.simulator_engine.finalizer import EventPersistenceError, finalize_step
from src.sim.simulator_engine.phase_registry import SimulationPhase
from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner
from src.systems.urban_capacity_project import advance_urban_capacity_projects, start_urban_capacity_project


@pytest.mark.asyncio
async def test_failed_event_commit_restores_canonical_month_state(
    base_world,
    monkeypatch,
):
    """A failed month commit must not leave canonical or semantic mutations."""
    base_world.map.regions[302] = CityRegion(
        id=302,
        name="Transactional City",
        desc="",
        population=100,
        population_capacity=120,
    )
    region = base_world.map.regions[302]
    before_population = region.population
    before_month = base_world.month_stamp
    before_dirty_targets = list(base_world.mechanical_language.dirty_targets)

    def mutate(simulator, ctx):
        simulator.world.map.regions[302].change_population(25)
        simulator.world.mechanical_language.dirty_targets.append("region:302")
        ctx.add_events(
            [
                Event(
                    simulator.world.month_stamp,
                    "population changed before persistence failed",
                    fact_kind=FactKind.STATE_TRANSITION,
                )
            ]
        )

    def commit(_simulator, ctx):
        return finalize_step(ctx)

    phases = (
        SimulationPhase("mutate", 1, "mutate", mutate),
        SimulationPhase(
            "finalize_step",
            2,
            "finalize_step",
            commit,
            reset_check_after=False,
        ),
    )
    monkeypatch.setattr(
        base_world.event_manager,
        "commit_step",
        lambda _events, _chapter: False,
    )

    with pytest.raises(EventPersistenceError):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert base_world.map.regions[302].population == before_population
    assert base_world.mechanical_language.dirty_targets == before_dirty_targets
    assert base_world.month_stamp == before_month


@pytest.mark.asyncio
async def test_failed_health_commit_restores_hp_injury_and_semantic_state(
    base_world,
    dummy_avatar,
    monkeypatch,
):
    dummy_avatar.weapon = None
    base_world.avatar_manager.register_avatar(dummy_avatar)
    before_hp = dummy_avatar.hp.cur
    before_consequences = dummy_avatar.individual_consequences.to_dict()
    before_conditions = dict(base_world.mechanical_language.condition_instances)
    before_streaks = dict(base_world.mechanical_language.pending_streaks)
    before_event_count = base_world.event_manager.count()
    before_month = base_world.month_stamp

    def mutate(simulator, ctx):
        avatar = simulator.world.avatar_manager.get_avatar(dummy_avatar.id)
        event = Event(
            simulator.world.month_stamp,
            "grounded non-fatal injury before persistence failed",
            related_avatars=[avatar.id],
            fact_kind=FactKind.STATE_TRANSITION,
        )
        hp_before = avatar.hp.cur
        avatar.hp.reduce(max(1, avatar.hp.max // 2))
        assert record_hp_change_from_event(avatar, event, hp_before)
        simulator.world.mechanical_language.add_condition_instance(
            ConditionInstance(
                id="rollback-health-condition",
                definition_id="strained_health_recovery",
                target_kind="region",
                target_id="302",
                label="strained health recovery",
                intensity=0.5,
                started_month=int(simulator.world.month_stamp),
                cause_event_id=event.id,
            )
        )
        simulator.world.mechanical_language.pending_streaks[
            "strained_health_recovery:region:302"
        ] = {"activate": 1, "resolve": 0}
        ctx.add_events([event])

    phases = (
        SimulationPhase("mutate", 1, "mutate", mutate),
        SimulationPhase(
            "finalize_step",
            2,
            "finalize_step",
            lambda _simulator, ctx: finalize_step(ctx),
            reset_check_after=False,
        ),
    )
    monkeypatch.setattr(
        base_world.event_manager,
        "commit_step",
        lambda _events, _chapter: False,
    )

    with pytest.raises(EventPersistenceError):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    restored = base_world.avatar_manager.get_avatar(dummy_avatar.id)
    assert restored.hp.cur == before_hp
    assert restored.individual_consequences.to_dict() == before_consequences
    assert base_world.mechanical_language.condition_instances == before_conditions
    assert base_world.mechanical_language.pending_streaks == before_streaks
    assert base_world.event_manager.count() == before_event_count
    assert base_world.month_stamp == before_month


@pytest.mark.asyncio
async def test_failed_project_commit_restores_capacity_project_and_events(base_world, monkeypatch):
    region = CityRegion(
        id=702,
        name="Transactional Works",
        desc="",
        cors=[(0, 0)],
        population=110,
        population_capacity=100,
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
            assets=(
                UrbanAsset("homes", "core", ("housing",), 100, 0.8, 0.9),
                UrbanAsset("works", "core", ("construction_work",), 10, 0.8, 0.9),
            ),
            governance=CityGovernance("dynasty", "house-1", 1.0),
        ),
        economy=RegionalEconomyState(
            stocks={"stone": 100.0},
            capacities={"stone": 200.0},
            access={"stone": 1.0},
            project_resources={"settlement_capacity_expansion": "stone"},
        ),
    )
    base_world.map.regions[region.id] = region
    before_capacity = region.population_capacity
    before_stock = region.economy.stocks["stone"]
    before_reservations = dict(region.economy.reservations)
    before_city_state = region.city_state
    before_economy = region.economy
    before_event_count = base_world.event_manager.count()
    before_event_ids = tuple(
        event.id
        for event in base_world.event_manager.get_events_between_months(-2**63, 2**63 - 1)
    )
    observed_events = []

    def mutate(simulator, ctx):
        decision = AgentDecision(
            month_stamp=int(simulator.world.month_stamp),
            subject_kind="city",
            subject_id=str(region.id),
            source="test",
            considered_count=1,
            chosen_chain=[
                {
                    "action_name": "settlement_capacity_expansion",
                    "params": {},
                }
            ],
        )
        decision_event = Event(
            simulator.world.month_stamp,
            "Transactional Works chose to expand settlement capacity.",
            fact_kind=FactKind.DECISION,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload={"deltas": [], "decision": decision.to_dict()},
        )
        ctx.add_events([decision_event])
        started = start_urban_capacity_project(
            simulator.world,
            region,
            decision_event_id=decision_event.id,
            trigger_event_id="condition-rollback",
            invalidations=ctx.invalidations,
        )
        ctx.add_events([started])
        observed_events.extend([started])
        progressed = advance_urban_capacity_projects(
            simulator.world,
            invalidations=ctx.invalidations,
        )
        observed_events.extend(progressed)
        ctx.add_events(progressed)

    phases = (
        SimulationPhase("mutate", 1, "mutate", mutate),
        SimulationPhase("finalize_step", 2, "finalize_step", lambda _sim, ctx: finalize_step(ctx), reset_check_after=False),
    )
    monkeypatch.setattr(base_world.event_manager, "commit_step", lambda _events, _chapter: False)

    with pytest.raises(EventPersistenceError):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert base_world.map.regions[region.id] is region
    assert observed_events[0].event_type == "urban_capacity_project_started"
    assert any(
        event.event_type == "urban_capacity_project_progressed"
        for event in observed_events
    )
    assert region.city_state is before_city_state
    assert region.economy is before_economy
    assert region.population_capacity == before_capacity
    assert region.city_state.capacity_projects == ()
    assert region.economy.stocks["stone"] == before_stock
    assert region.economy.reservations == before_reservations == {}
    assert base_world.event_manager.count() == before_event_count
    assert tuple(
        event.id
        for event in base_world.event_manager.get_events_between_months(-2**63, 2**63 - 1)
    ) == before_event_ids
    assert base_world.month_stamp == 12


@pytest.mark.asyncio
async def test_aborted_month_restores_existing_object_identity_and_rng(base_world):
    region = CityRegion(
        id=303,
        name="Abort City",
        desc="",
        population=80,
        population_capacity=100,
    )
    base_world.map.regions[303] = region
    before_random_state = random.getstate()

    def mutate_then_abort(simulator, _ctx):
        simulator.world.map.regions[303].change_population(20)
        random.random()
        from src.sim.simulator_engine.phase_runner import SimulationStepAborted

        raise SimulationStepAborted()

    phases = (SimulationPhase("mutate", 1, "mutate", mutate_then_abort),)

    result = await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert result == []
    assert base_world.map.regions[303] is region
    assert region.population == 80
    assert random.getstate() == before_random_state


@pytest.mark.asyncio
async def test_successful_month_keeps_canonical_mutations(base_world):
    region = CityRegion(
        id=304,
        name="Committed City",
        desc="",
        population=60,
        population_capacity=100,
    )
    base_world.map.regions[304] = region

    def mutate(simulator, _ctx):
        simulator.world.map.regions[304].change_population(10)

    phases = (SimulationPhase("mutate", 1, "mutate", mutate),)

    assert await SimulationPhaseRunner(Simulator(base_world), phases=phases).run() == []
    assert base_world.map.regions[304] is region
    assert region.population == 70


@pytest.mark.asyncio
async def test_failed_commit_restores_relations_receipts_calendar_events_and_rng(
    base_world,
    dummy_avatar,
    monkeypatch,
):
    from src.classes.mechanical_language import DomainReactionReceipt
    from src.classes.relation.relation import RelationState

    base_world.avatar_manager.register_avatar(dummy_avatar)
    before_month = base_world.month_stamp
    before_event_count = base_world.event_manager.count()
    before_rng = random.getstate()
    before_relations = dict(dummy_avatar.relations)
    before_receipts = dict(base_world.mechanical_language.reaction_receipts)
    before_institutional = (
        base_world.institutional_authority.to_dict(),
        base_world.institutional_knowledge.to_dict(),
        base_world.institutional_relations.to_dict(),
    )

    def mutate(simulator, ctx):
        from src.classes.institution import (
            Institution,
            InstitutionalFactKnowledge,
            InstitutionalMemory,
            InstitutionKind,
            KnowledgeChannel,
        )
        from src.classes.mechanical_language import EntityRef

        dummy_avatar.relations[dummy_avatar] = RelationState(friendliness=42)
        receipt = DomainReactionReceipt.create(
            "rollback-condition",
            "population",
            "rollback-trigger",
            decision="maintain",
            affordance_id=None,
            decision_event_ids=("rollback-decision",),
        )
        simulator.world.mechanical_language.reaction_receipts[receipt.id] = receipt
        authority = simulator.world.institutional_authority
        institution = Institution(
            kind=InstitutionKind.DYNASTY,
            owner_ref=EntityRef("dynasty", "rollback-house"),
            founded_month=0,
        )
        authority.add_institution(institution)
        knowledge = InstitutionalFactKnowledge(
            institution_id=institution.id,
            event_id="rollback-fact",
            learned_month=int(simulator.world.month_stamp),
            channel=KnowledgeChannel.OWN_ACTION,
            learned_from_event_id="rollback-fact",
        )
        simulator.world.institutional_knowledge.record(knowledge, authority)
        simulator.world.institutional_relations.add_memory(
            InstitutionalMemory(
                institution_id=institution.id,
                event_id=knowledge.event_id,
                salience=0.8,
                recorded_month=int(simulator.world.month_stamp),
                last_reinforced_month=int(simulator.world.month_stamp),
                factors=(("institutional_change", 0.5),),
            ),
            simulator.world.institutional_knowledge,
            authority,
        )
        random.random()
        ctx.add_events([Event(simulator.world.month_stamp, "will not persist")])

    phases = (
        SimulationPhase("mutate", 1, "mutate", mutate),
        SimulationPhase(
            "finalize_step",
            2,
            "finalize_step",
            lambda _simulator, ctx: finalize_step(ctx),
            reset_check_after=False,
        ),
    )
    monkeypatch.setattr(
        base_world.event_manager,
        "commit_step",
        lambda _events, _chapter: False,
    )

    with pytest.raises(EventPersistenceError):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert dummy_avatar.relations == before_relations
    assert base_world.mechanical_language.reaction_receipts == before_receipts
    assert (
        base_world.institutional_authority.to_dict(),
        base_world.institutional_knowledge.to_dict(),
        base_world.institutional_relations.to_dict(),
    ) == before_institutional
    assert base_world.month_stamp == before_month
    assert base_world.event_manager.count() == before_event_count
    assert random.getstate() == before_rng


@pytest.mark.asyncio
async def test_failed_month_restores_reactive_sect_support_in_place(base_world):
    from src.systems.sect_member_support import execute_sect_member_support
    from tests.test_organization_reactivity_integration import _setup

    sect, avatar, city, trigger, _condition = _setup(base_world)
    before_sect_stones = sect.magic_stone
    before_avatar_stones = avatar.magic_stone.value

    def mutate_then_fail(simulator, _ctx):
        event = execute_sect_member_support(
            simulator.world,
            sect,
            member_id=avatar.id,
            region_id=str(city.id),
            decision_event_id="organization-decision",
            condition_event_id=trigger.id,
        )
        assert event.event_type == "sect_member_support_completed"
        raise RuntimeError("abort institutional reaction")

    phases = (SimulationPhase("mutate", 1, "mutate", mutate_then_fail),)

    with pytest.raises(RuntimeError, match="abort institutional reaction"):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert sect.magic_stone == before_sect_stones
    assert avatar.magic_stone.value == before_avatar_stones
    assert sect.members[avatar.id] is avatar


@pytest.mark.asyncio
async def test_failed_month_restores_registered_avatar_in_place(
    base_world,
    dummy_avatar,
):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    dummy_avatar.magic_stone = 40

    def mutate_then_fail(_simulator, _ctx):
        dummy_avatar.magic_stone = 5
        raise RuntimeError("abort avatar mutation")

    phases = (SimulationPhase("mutate", 1, "mutate", mutate_then_fail),)

    with pytest.raises(RuntimeError, match="abort avatar mutation"):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert base_world.avatar_manager.get_avatar(dummy_avatar.id) is dummy_avatar
    assert dummy_avatar.world is base_world
    assert dummy_avatar.magic_stone == 40


@pytest.mark.asyncio
async def test_failed_month_restores_global_custom_content_id_state(base_world):
    from types import SimpleNamespace

    from src.classes.custom_content import CustomContentRegistry
    from src.classes.technique import techniques_by_id, techniques_by_name

    before_next_ids = dict(CustomContentRegistry.next_ids)
    transient_id = 999_991
    transient_name = "Rollback Technique"

    def allocate_then_fail(_simulator, _ctx):
        CustomContentRegistry.allocate_id("technique")
        CustomContentRegistry.register_technique(
            SimpleNamespace(id=transient_id, name=transient_name)
        )
        raise RuntimeError("abort custom content")

    phases = (SimulationPhase("mutate", 1, "mutate", allocate_then_fail),)

    with pytest.raises(RuntimeError, match="abort custom content"):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert CustomContentRegistry.next_ids == before_next_ids
    assert transient_id not in CustomContentRegistry.custom_techniques_by_id
    assert transient_id not in techniques_by_id
    assert transient_name not in techniques_by_name


@pytest.mark.asyncio
async def test_failed_month_restores_active_global_sect_in_place(base_world):
    from src.classes.core.sect import sects_by_id

    sect = next(iter(sects_by_id.values()))
    before_magic_stone = sect.magic_stone

    def mutate_then_fail(_simulator, _ctx):
        sect.magic_stone += 777
        raise RuntimeError("abort sect mutation")

    phases = (SimulationPhase("mutate", 1, "mutate", mutate_then_fail),)

    with pytest.raises(RuntimeError, match="abort sect mutation"):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert sects_by_id[sect.id] is sect
    assert sect.magic_stone == before_magic_stone

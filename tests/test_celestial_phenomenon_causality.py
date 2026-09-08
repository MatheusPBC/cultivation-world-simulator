from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.celestial_phenomenon import CelestialPhenomenon
from src.classes.event import FactKind
from src.classes.event_storage import EventStorage
from src.classes.rarity import RARITY_CONFIGS, RarityLevel
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.finalizer import finalize_step
from src.sim.simulator_engine.finalizer import EventPersistenceError
from src.sim.simulator_engine.phase_registry import SimulationPhase
from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner
from src.sim.simulator import Simulator
from src.sim.simulator_engine.phases import world as world_phases
from src.systems.time import Month, Year, create_month_stamp


def _phenomenon(identifier: int, duration: int = 5) -> CelestialPhenomenon:
    return CelestialPhenomenon(
        id=identifier,
        name=f"omen-{identifier}",
        rarity=RARITY_CONFIGS[RarityLevel.N],
        effects={},
        effect_desc="",
        desc=f"description-{identifier}",
        duration_years=duration,
    )


def _finalized(world):
    world.event_manager = None
    ctx = SimulationStepContext.create(world)
    ctx.add_events(world_phases.phase_update_celestial_phenomenon(world))
    finalize_step(ctx)
    return ctx.events


def test_init_records_typed_world_transition_and_round_trips(tmp_path: Path, base_world, monkeypatch):
    selected = _phenomenon(17, duration=4)
    monkeypatch.setattr(world_phases, "get_random_celestial_phenomenon", lambda: selected)

    events = _finalized(base_world)

    assert len(events) == 1
    event = events[0]
    assert event.causal_origin is CausalOrigin.EXTERNAL_EVENT
    assert event.fact_kind is FactKind.STATE_TRANSITION
    deltas = event.causal_payload["deltas"]
    assert {(d["aspect"], d["before"], d["after"]) for d in deltas} == {
        ("current_phenomenon_id", None, "17"),
        ("phenomenon_start_year", "0", "1"),
    }
    assert event.causal_payload["cause"]["kind"] == "stochastic_catalog_sampling"
    assert event.causal_payload["sampling"]["selected_id"] == 17

    storage = EventStorage(tmp_path / "events.db")
    assert storage.add_event(event)
    restored = storage.get_event_by_id(event.id)
    assert restored is not None
    assert restored.causal_payload == event.causal_payload
    storage.close()


def test_expiry_same_id_only_records_changed_start_year(base_world, monkeypatch):
    old = _phenomenon(17, duration=5)
    selected = _phenomenon(17, duration=5)
    base_world.current_phenomenon = old
    base_world.phenomenon_start_year = 1
    base_world.month_stamp = create_month_stamp(Year(6), Month.JANUARY)
    monkeypatch.setattr(world_phases, "get_random_celestial_phenomenon", lambda: selected)

    events = _finalized(base_world)

    assert len(events) == 1
    event = events[0]
    assert event.fact_kind is FactKind.STATE_TRANSITION
    deltas = event.causal_payload["deltas"]
    assert len(deltas) == 1
    assert deltas[0]["aspect"] == "phenomenon_start_year"
    assert deltas[0]["before"] == "1"
    assert deltas[0]["after"] == "6"


def test_expiry_with_no_changed_field_is_an_occurrence(base_world, monkeypatch):
    old = _phenomenon(17, duration=0)
    base_world.current_phenomenon = old
    base_world.phenomenon_start_year = 1
    base_world.month_stamp = create_month_stamp(Year(1), Month.JANUARY)
    monkeypatch.setattr(world_phases, "get_random_celestial_phenomenon", lambda: _phenomenon(17, duration=0))

    events = _finalized(base_world)

    assert len(events) == 1
    assert events[0].fact_kind is FactKind.OCCURRENCE
    assert events[0].causal_payload["deltas"] == []


def test_non_january_unexpired_and_empty_catalog_are_noops(base_world, monkeypatch):
    active = _phenomenon(17, duration=5)
    base_world.current_phenomenon = active
    base_world.phenomenon_start_year = 1
    base_world.month_stamp = create_month_stamp(Year(2), Month.FEBRUARY)

    monkeypatch.setattr(world_phases, "get_random_celestial_phenomenon", lambda: _phenomenon(18))
    assert world_phases.phase_update_celestial_phenomenon(base_world) == []
    assert base_world.current_phenomenon is active
    assert base_world.phenomenon_start_year == 1

    base_world.month_stamp = create_month_stamp(Year(2), Month.JANUARY)
    sampler = Mock(return_value=_phenomenon(18))
    monkeypatch.setattr(world_phases, "get_random_celestial_phenomenon", sampler)
    assert world_phases.phase_update_celestial_phenomenon(base_world) == []
    sampler.assert_not_called()

    base_world.current_phenomenon = None
    monkeypatch.setattr(world_phases, "get_random_celestial_phenomenon", lambda: None)
    assert world_phases.phase_update_celestial_phenomenon(base_world) == []
    assert base_world.current_phenomenon is None


async def _run_phenomenon_month(base_world):
    def update(_simulator, ctx):
        ctx.add_events(world_phases.phase_update_celestial_phenomenon(base_world))

    phases = (
        SimulationPhase(
            "update_celestial_phenomenon",
            1,
            "update_celestial_phenomenon",
            update,
        ),
        SimulationPhase(
            "finalize_step",
            2,
            "finalize_step",
            lambda _simulator, ctx: finalize_step(ctx),
            reset_check_after=False,
        ),
    )
    return await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()


@pytest.mark.asyncio
async def test_failed_commit_restores_phenomenon_state_event_count_and_rng(base_world, monkeypatch):
    selected = _phenomenon(17)
    alternate = _phenomenon(18)
    sampled_ids = []

    def sample():
        chosen = random.choice([selected, alternate])
        sampled_ids.append(chosen.id)
        return chosen

    monkeypatch.setattr(world_phases, "get_random_celestial_phenomenon", sample)
    original_commit = base_world.event_manager.commit_step
    failed_once = False

    def commit_once_then_persist(events, chapter):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            return False
        return original_commit(events, chapter)

    monkeypatch.setattr(
        base_world.event_manager,
        "commit_step",
        commit_once_then_persist,
    )
    before_rng = random.getstate()
    before_month = base_world.month_stamp
    before_event_count = base_world.event_manager.count()

    with pytest.raises(EventPersistenceError):
        await _run_phenomenon_month(base_world)

    assert base_world.current_phenomenon is None
    assert base_world.phenomenon_start_year == 0
    assert base_world.month_stamp == before_month
    assert base_world.event_manager.count() == before_event_count
    assert random.getstate() == before_rng

    events = await _run_phenomenon_month(base_world)

    assert len(events) == 1
    assert base_world.current_phenomenon is not None
    assert base_world.phenomenon_start_year == 1
    assert base_world.month_stamp == before_month + 1
    assert base_world.event_manager.count() == before_event_count + 1
    assert sampled_ids[0] == sampled_ids[1]

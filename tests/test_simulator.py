import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.classes.action.move_to_direction import MoveToDirection
from src.classes.action_runtime import ActionInstance
from src.classes.core.avatar import Avatar, Gender
from src.classes.event import Event
from src.classes.root import Root
from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.sect_decider import SectDecisionResult
from src.classes.sect_ranks import get_rank_from_realm
from src.server.runtime import DEFAULT_GAME_STATE, GameSessionRuntime
from src.sim.simulator import Simulator
from src.sim.simulator_engine.causal_recorder import CausalRecorder
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner
from src.sim.simulator_engine.phases import annual, world as world_phases
from src.classes.core.sect import Sect, SectHeadQuarter
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.classes.observe import is_within_observation
from src.systems.institutional_diplomacy import are_sects_at_war, set_formal_war
from src.systems.time import Month, Year, create_month_stamp
from src.utils.llm.client import call_llm_with_task_name


@pytest.mark.asyncio
async def test_simulator_step_moves_avatar_and_sets_tile(base_world, dummy_avatar, mock_llm_managers):
    dummy_avatar.pos_x = 1
    dummy_avatar.pos_y = 1
    dummy_avatar.tile = base_world.map.get_tile(1, 1)

    sim = Simulator(base_world)
    base_world.avatar_manager.avatars[dummy_avatar.id] = dummy_avatar

    action = MoveToDirection(dummy_avatar, base_world)
    direction = "East"
    action.start(direction=direction)
    dummy_avatar.current_action = ActionInstance(action=action, params={"direction": direction})

    await sim.step()

    assert dummy_avatar.pos_x == 3
    assert dummy_avatar.pos_y == 1
    assert dummy_avatar.tile is not None
    assert dummy_avatar.tile.x == 3
    assert dummy_avatar.tile.y == 1


@pytest.mark.asyncio
async def test_simulator_step_enforces_world_test_mode_for_direct_calls(
    base_world,
    monkeypatch,
):
    base_world.run_config_snapshot = {"test_mode": True}
    provider = AsyncMock(side_effect=AssertionError("real provider must not run"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)

    async def _run(_runner):
        return [await call_llm_with_task_name(
            "action_decision",
            "unused-template.txt",
            {"avatar_name": "DirectStep"},
        )]

    monkeypatch.setattr(SimulationPhaseRunner, "run", _run)

    result = await Simulator(base_world).step()

    assert result[0]["DirectStep"]["action_name_params_pairs"] == []
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_simulator_interaction_events_do_not_use_legacy_counting(base_world, dummy_avatar, mock_llm_managers):
    sim = Simulator(base_world)

    other_avatar = Avatar(
        world=base_world,
        name="OtherAvatar",
        id="other_id",
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement),
        gender=Gender.FEMALE,
        pos_x=0,
        pos_y=0,
        root=Root.WOOD,
        alignment=Alignment.NEUTRAL,
    )

    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.avatar_manager.register_avatar(other_avatar)

    ev1 = Event(base_world.month_stamp, "phase1 interaction", related_avatars=[dummy_avatar.id, other_avatar.id])
    ev2 = Event(base_world.month_stamp, "phase2 interaction", related_avatars=[dummy_avatar.id, other_avatar.id])

    with patch(
        "src.sim.simulator_engine.phases.actions.phase_execute_actions",
        new=AsyncMock(return_value=[ev1]),
    ), patch(
        "src.sim.simulator_engine.phases.world.phase_passive_effects",
        new=AsyncMock(return_value=[ev2]),
    ):

        await sim.step()

    count = dummy_avatar.relation_interaction_states[other_avatar.id]["count"]
    assert count == 0


@pytest.mark.asyncio
async def test_phase_passive_effects_collects_fate_revelation_event(base_world, dummy_avatar):
    event = Event(
        base_world.month_stamp,
        "命格显现",
        related_avatars=[dummy_avatar.id],
        is_major=True,
        event_type="fate_revelation",
    )

    with patch(
        "src.sim.simulator_engine.phases.world.try_trigger_fortune",
        new=AsyncMock(return_value=[]),
    ), patch(
        "src.sim.simulator_engine.phases.world.try_trigger_misfortune",
        new=AsyncMock(return_value=[]),
    ), patch(
        "src.sim.simulator_engine.phases.world.try_trigger_fate_revelation",
        new=AsyncMock(return_value=[event]),
    ) as mock_fate:
        events = await world_phases.phase_passive_effects(base_world, [dummy_avatar])

    assert events == [event]
    mock_fate.assert_awaited_once_with(dummy_avatar, base_world)


@pytest.mark.asyncio
async def test_simulator_event_deduplication(base_world, dummy_avatar, mock_llm_managers):
    sim = Simulator(base_world)
    base_world.avatar_manager.register_avatar(dummy_avatar)

    ev = Event(base_world.month_stamp, "duplicate event")
    ev_id = ev.id

    with patch(
        "src.sim.simulator_engine.phases.actions.phase_execute_actions",
        new=AsyncMock(return_value=[ev]),
    ), patch(
        "src.sim.simulator_engine.phases.world.phase_passive_effects",
        new=AsyncMock(return_value=[ev]),
    ):

        base_world.event_manager.commit_step = MagicMock(return_value=True)
        await sim.step()

    persisted_events = [
        event
        for call in base_world.event_manager.commit_step.call_args_list
        for event in call.args[0]
        if event.id == ev_id
    ]
    assert len(persisted_events) == 1


@pytest.mark.asyncio
async def test_simulator_step_stops_at_phase_boundary_when_reset_requested(base_world, mock_llm_managers):
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    base_world.runtime = runtime
    sim = Simulator(base_world)

    async def _request_reset(_living_avatars):
        runtime.request_reset()
        return []

    process_gatherings = AsyncMock(return_value=[])

    with patch(
        "src.sim.simulator_engine.phases.lifecycle.phase_long_term_objective_thinking",
        new=AsyncMock(side_effect=_request_reset),
    ), patch(
        "src.sim.simulator_engine.phases.world.phase_process_gatherings",
        new=process_gatherings,
    ):
        events = await sim.step()

    assert events == []
    process_gatherings.assert_not_awaited()


@pytest.mark.asyncio
async def test_simulator_periodic_sect_thinking_runs_after_sect_update(base_world, mock_llm_managers):
    sim = Simulator(base_world)
    call_order = []

    def _update_sects():
        call_order.append("update_sects")
        return []

    async def _sect_decision(_simulator):
        call_order.append("sect_decision")
        return []

    async def _periodic_thinking(_simulator):
        call_order.append("periodic_thinking")
        return []

    with patch.object(sim.sect_manager, "update_sects", side_effect=_update_sects), patch(
        "src.sim.simulator_engine.phases.annual.phase_sect_periodic_decision",
        new=AsyncMock(side_effect=_sect_decision),
    ), patch(
        "src.sim.simulator_engine.phases.annual.phase_sect_periodic_thinking",
        new=AsyncMock(side_effect=_periodic_thinking),
    ):
        await sim.step()

    assert call_order == ["update_sects", "sect_decision", "periodic_thinking"]


@pytest.mark.asyncio
async def test_simulator_periodic_sect_thinking_not_run_in_non_january(base_world, mock_llm_managers):
    base_world.month_stamp = create_month_stamp(Year(1), Month.FEBRUARY)
    sim = Simulator(base_world)

    with patch.object(sim.sect_manager, "update_sects") as mock_update_sects, patch(
        "src.sim.simulator_engine.phases.annual.phase_sect_periodic_decision",
        new=AsyncMock(),
    ) as mock_sect_decision, patch(
        "src.sim.simulator_engine.phases.annual.phase_sect_periodic_thinking",
        new=AsyncMock(),
    ) as mock_periodic_thinking:
        await sim.step()

    mock_update_sects.assert_not_called()
    mock_sect_decision.assert_not_awaited()
    mock_periodic_thinking.assert_not_awaited()


@pytest.mark.asyncio
async def test_phase_sect_periodic_thinking_generates_event_with_related_sect(base_world, mock_llm_managers):
    base_world.start_year = 1
    base_world.month_stamp = create_month_stamp(Year(6), Month.JANUARY)

    sim = Simulator(base_world)
    sect = MagicMock()
    sect.id = 77
    sect.name = "Test Sect"
    sect.periodic_thinking = ""
    sect.last_decision_summary = "招徕散修 1 人。"

    base_world.existed_sects = [sect]
    base_world.event_manager._storage = MagicMock()
    base_world.event_manager._storage.get_events.return_value = ([], None)

    with patch.object(annual.CONFIG.sect, "thinking_interval_years", 5), patch(
        "src.classes.core.sect.get_sect_decision_context", return_value=MagicMock()
    ), patch(
        "src.sim.simulator_engine.phases.annual.SectThinker.think",
        new=AsyncMock(return_value="secure borders first"),
    ), patch(
        "src.sim.simulator_engine.phases.annual.t",
        side_effect=lambda key, **kwargs: "{sect_name} sect thinking: {thinking}".format(**kwargs)
        if key == "game.sect_thinking_event"
        else key,
    ):
        events = await annual.phase_sect_periodic_thinking(sim)

    assert len(events) == 1
    event = events[0]
    assert event.related_sects == [77]
    assert "Test Sect sect thinking:" in event.content
    assert "secure borders first" in event.content


@pytest.mark.asyncio
async def test_phase_sect_periodic_thinking_skips_non_interval_year(base_world, mock_llm_managers):
    base_world.start_year = 1
    base_world.month_stamp = create_month_stamp(Year(4), Month.JANUARY)

    sim = Simulator(base_world)
    sect = MagicMock()
    sect.id = 77
    sect.name = "Test Sect"
    sect.periodic_thinking = ""

    base_world.existed_sects = [sect]
    base_world.event_manager._storage = MagicMock()
    base_world.event_manager._storage.get_events.return_value = ([], None)

    with patch.object(annual.CONFIG.sect, "thinking_interval_years", 5), patch(
        "src.classes.core.sect.get_sect_decision_context", return_value=MagicMock()
    ), patch(
        "src.sim.simulator_engine.phases.annual.SectThinker.think",
        new=AsyncMock(return_value="should not happen"),
    ) as mock_decide:
        events = await annual.phase_sect_periodic_thinking(sim)

    assert events == []
    mock_decide.assert_not_awaited()


@pytest.mark.asyncio
async def test_phase_sect_periodic_decision_emits_summary_event(base_world, mock_llm_managers):
    base_world.start_year = 1
    base_world.month_stamp = create_month_stamp(Year(6), Month.JANUARY)

    sim = Simulator(base_world)
    sect = MagicMock()
    sect.id = 77
    sect.name = "Test Sect"
    sect.last_decision_summary = ""

    base_world.existed_sects = [sect]
    base_world.event_manager._storage = MagicMock()
    base_world.event_manager._storage.get_events.return_value = ([], None)

    with patch.object(annual.CONFIG.sect, "decision_interval_years", 5), patch(
        "src.classes.core.sect.get_sect_decision_context", return_value=MagicMock()
    ), patch(
        "src.sim.simulator_engine.phases.annual.SectDecider.decide",
        new=AsyncMock(
            return_value=SectDecisionResult(
                events=[],
                recruitment_count=1,
                summary_text="Test Sect 本轮宗门决策：招徕散修 1 人。",
            )
        ),
    ):
        events = await annual.phase_sect_periodic_decision(sim)

    assert len(events) == 1
    assert events[0].related_sects == [77]
    assert "招徕散修 1 人" in events[0].content
    assert sect.last_decision_summary == "Test Sect 本轮宗门决策：招徕散修 1 人。"


@pytest.mark.asyncio
async def test_wartime_colocation_alone_never_forces_combat_or_teleport(base_world, mock_llm_managers):
    """Sect war is an institutional relationship, not a combat trigger.

    Two members of formally warring sects stand one tile apart and the whole
    canonical month runs. Nobody chose `Attack`, so the month must not damage
    anyone, must not move anyone to a headquarters, and must not pay war
    contribution or weariness. This asserts the material outcome through the
    real `Simulator.step()` path instead of the absence of a phase name.
    """
    from src.classes.environment.sect_region import SectRegion
    from pathlib import Path

    region_a = SectRegion(id=2001, name="甲宗总部", desc="", sect_id=1, sect_name="甲宗", cors=[(0, 0)])
    region_b = SectRegion(id=2002, name="乙宗总部", desc="", sect_id=2, sect_name="乙宗", cors=[(4, 4)])
    base_world.map.regions[2001] = region_a
    base_world.map.region_cors[2001] = [(0, 0)]
    base_world.map.regions[2002] = region_b
    base_world.map.region_cors[2002] = [(4, 4)]
    base_world.map.update_sect_regions()

    sect_a = Sect(
        id=1,
        name="甲宗",
        desc="",
        member_act_style="",
        alignment=Alignment.RIGHTEOUS,
        headquarter=SectHeadQuarter(name="甲宗总部", desc="", image=Path("")),
        technique_names=[],
    )
    sect_b = Sect(
        id=2,
        name="乙宗",
        desc="",
        member_act_style="",
        alignment=Alignment.EVIL,
        headquarter=SectHeadQuarter(name="乙宗总部", desc="", image=Path("")),
        technique_names=[],
    )
    base_world.existed_sects = [sect_a, sect_b]
    base_world.sect_context.from_existed_sects(base_world.existed_sects)
    bootstrap_institutional_authority(base_world)
    set_formal_war(
        base_world, 1, 2, current_month=int(base_world.month_stamp),
        evidence_event_ids=("event:existing-war",),
    )

    attacker = Avatar(
        world=base_world,
        name="甲修",
        id="war_a",
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement),
        gender=Gender.MALE,
        pos_x=1,
        pos_y=1,
        root=Root.GOLD,
        alignment=Alignment.RIGHTEOUS,
    )
    defender = Avatar(
        world=base_world,
        name="乙修",
        id="war_b",
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement),
        gender=Gender.FEMALE,
        pos_x=1,
        pos_y=2,
        root=Root.WOOD,
        alignment=Alignment.EVIL,
    )
    attacker.join_sect(sect_a, attacker.sect_rank or get_rank_from_realm(attacker.cultivation_progress.realm))
    defender.join_sect(sect_b, defender.sect_rank or get_rank_from_realm(defender.cultivation_progress.realm))
    attacker.tile = base_world.map.get_tile(attacker.pos_x, attacker.pos_y)
    defender.tile = base_world.map.get_tile(defender.pos_x, defender.pos_y)
    base_world.avatar_manager.avatars = {attacker.id: attacker, defender.id: defender}

    assert are_sects_at_war(base_world, 1, 2)
    assert is_within_observation(attacker, defender)
    for avatar in (attacker, defender):
        avatar.hp.cur = avatar.hp.max

    sim = Simulator(base_world)
    await sim.step()

    # No damage: co-location under a formal war is not itself a battle.
    assert attacker.hp.cur == attacker.hp.max
    assert defender.hp.cur == defender.hp.max
    # No teleport back to any headquarters.
    assert (attacker.pos_x, attacker.pos_y) == (1, 1)
    assert (defender.pos_x, defender.pos_y) == (1, 2)
    # No automatic war contribution and no war weariness from the encounter.
    assert attacker.sect_contribution == 0
    assert defender.sect_contribution == 0
    assert sect_a.war_weariness == 0
    assert sect_b.war_weariness == 0


# --- Task 3 acceptance: passive causal recorder must not alter step() behavior ---


def test_context_create_bridges_and_step_clears_the_causal_recorder(base_world):
    ctx = SimulationStepContext.create(base_world)

    assert isinstance(ctx.causal, CausalRecorder)
    assert base_world.step_causal_recorder is ctx.causal

    from src.sim.simulator_engine.finalizer import finalize_step

    finalize_step(ctx)

    assert base_world.step_causal_recorder is None


def test_finalize_does_not_advance_month_when_event_persistence_fails(base_world):
    from src.classes.event import Event
    from src.sim.simulator_engine.finalizer import EventPersistenceError, finalize_step

    class RejectingEventManager:
        def commit_step(self, _events, _chapter):
            return False

    before = base_world.month_stamp
    base_world.event_manager = RejectingEventManager()
    ctx = SimulationStepContext.create(base_world)
    ctx.events.append(Event(before, "must persist"))

    with pytest.raises(EventPersistenceError, match="month was not advanced"):
        finalize_step(ctx)

    assert base_world.month_stamp == before


def test_finalize_persists_sqlite_step_events_as_one_batch(base_world, tmp_path, monkeypatch):
    from src.classes.event_storage import EventStorage
    from src.sim.managers.event_manager import EventManager
    from src.sim.simulator_engine.finalizer import EventPersistenceError, finalize_step

    storage = EventStorage(tmp_path / "events.db")
    base_world.event_manager = EventManager(storage=storage)
    original_insert = storage._insert_event
    insert_count = 0

    def fail_on_second_event(event):
        nonlocal insert_count
        insert_count += 1
        if insert_count == 2:
            raise RuntimeError("injected finalizer failure")
        original_insert(event)

    monkeypatch.setattr(storage, "_insert_event", fail_on_second_event)
    before = base_world.month_stamp
    ctx = SimulationStepContext.create(base_world)
    first = Event(before, "first event")
    second = Event(before, "second event")
    ctx.events.extend([first, second])

    try:
        with pytest.raises(EventPersistenceError, match="month was not advanced"):
            finalize_step(ctx)
        assert storage.count() == 0
        assert base_world.month_stamp == before
    finally:
        storage.close()


@pytest.mark.asyncio
async def test_simulator_step_with_no_owner_recording_leaves_events_without_causal_metadata(
    base_world, dummy_avatar, mock_llm_managers
):
    """With an empty recorder (nothing recorded this step, since no
    breakthrough or population change happens here), step() must produce
    events that are indistinguishable from pre-Task-3 behavior: no
    causal_links, no causal_payload."""
    sim = Simulator(base_world)
    base_world.avatar_manager.register_avatar(dummy_avatar)

    events = await sim.step()

    assert events  # sanity: the step actually produced events to check
    for event in events:
        assert event.causal_links == []
        assert event.causal_payload is None

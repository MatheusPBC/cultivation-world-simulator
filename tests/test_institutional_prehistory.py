"""Fixed institutional prehistory before the playable January."""

from __future__ import annotations

import random
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.age import Age
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.dynasty import Dynasty
from src.classes.core.world import World
from src.classes.environment.city_state import CityGovernance
from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.institution import IdentityAnchorKind
from src.classes.mechanical_language import EntityRef
from src.classes.regional_economy import RegionalEconomyState
from src.server.init_flow import _create_save_slot, _generate_initial_events
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.sim.simulator_engine.prehistory import (
    PREHISTORY_MONTHS,
    PREHISTORY_PHASE_NAMES,
    PrehistoryError,
    genesis_month_stamp,
    prehistory_month_count,
    prehistory_phases,
    run_institutional_prehistory,
)
from src.systems import economy_reactivity, regional_economy
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.time import Month, MonthStamp, Year, create_month_stamp


PLAYABLE_START = create_month_stamp(Year(100), Month.JANUARY)


def _world(base_map, *, pressured: bool) -> World:
    """A world built at the genesis month, before any event exists."""
    world = World(map=base_map, month_stamp=genesis_month_stamp(PLAYABLE_START))
    world.run_config_snapshot = {
        "map_id": "classic",
        "test_mode": True,
        "provider": "test",
        "content_locale": "pt-BR",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.0,
        "world_lore": "",
    }
    emperor = Avatar(
        world=world,
        name="Prehistory Emperor",
        id="emperor",
        birth_month_stamp=create_month_stamp(Year(70), Month.JANUARY),
        age=Age(30, Realm.Qi_Refinement),
        gender=Gender.MALE,
    )
    world.avatar_manager.register_avatar(emperor)
    world.dynasty = Dynasty(1, "Prehistory Dynasty", "", current_emperor_id=emperor.id)

    def city(region_id: int, stock: float, demand: float) -> CityRegion:
        cell = (region_id % 10, 0)
        region = CityRegion(
            id=region_id,
            name=f"City {region_id}",
            desc="",
            cors=[cell],
            economy=RegionalEconomyState(
                stocks={"grain": stock},
                capacities={"grain": 20},
                demand_rates={"grain": demand},
                access={"grain": 1.0},
            ),
        )
        region.city_state.governance = CityGovernance("dynasty", "1", 1.0)
        world.map.regions[region_id] = region
        world.map.region_cors[region_id] = [cell]
        world.map.tiles[cell].region = region
        return region

    city(302, 18, 0)
    city(305, 0 if pressured else 18, 2 if pressured else 0)
    world.map.set_routes((Route("aid-road", (302, 305), "road", 2, 1.0, True),))
    bootstrap_institutional_authority(world)
    return world


async def _run(world: World):
    return await run_institutional_prehistory(
        Simulator(world), playable_start_month=PLAYABLE_START
    )


def _inject_government_choice(action_kind: str):
    """Make the real government interpreter select an offered option.

    Test-only, and it never invents an option: when the engine offers nothing
    of this kind the decision stays whatever the engine's own rule decided.
    """
    from contextlib import contextmanager
    from unittest.mock import patch

    from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
    import src.systems.government_interpreter as interpreter

    original = interpreter.interpret_domain_affordances

    async def choose(*args, **kwargs):
        options = tuple(kwargs.get("affordances") or ())
        chosen = next(
            (item for item in options if item.action_kind == action_kind), None
        )
        if chosen is None:
            return await original(*args, **kwargs)
        return await original(*args, **{
            **kwargs,
            "injected_decision": DomainDecision(
                DomainDecisionKind.ACT, "The city is repaired.", chosen.id
            ),
        })

    @contextmanager
    def _scope():
        with patch.object(interpreter, "interpret_domain_affordances", choose):
            yield

    return _scope()


def _declare_urban_pressure(world, *, integrity: float = 0.2) -> CityRegion:
    """A really damaged city and the engine-owned rules that read it.

    No `ConditionInstance` and no activation event are seeded: the rule and
    the material state are declared, and the real `evaluate_semantic_world`
    has to derive the condition itself. Otherwise the test would prove only
    that a hand-made instance can be answered.
    """
    from src.classes.environment.city_state import (
        CityDistrict,
        CityState,
        UrbanAsset,
        UrbanServiceDemand,
    )
    from src.classes.mechanical_language import (
        ConditionDefinition,
        DerivedMetricDefinition,
        PrimitiveDimension,
    )

    month = int(world.month_stamp)
    city = CityRegion(
        id=301,
        name="Strained City",
        desc="",
        cors=[(1, 1)],
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((1, 1),), 1.0),),
            assets=(UrbanAsset("clinic", "core", ("healing",), 10, 0.4, integrity),),
            service_demands=(UrbanServiceDemand("healing", 1.0),),
            governance=CityGovernance("dynasty", "1", 1.0),
        ),
    )
    city.population = 40
    city.population_capacity = 400
    world.map.regions[city.id] = city
    world.map.region_cors[city.id] = [(1, 1)]
    world.map.tiles[(1, 1)].region = city
    world.mechanical_language.derived_definitions["clinic-risk-metric"] = (
        DerivedMetricDefinition(
            id="clinic-risk-metric",
            concept_id="clinic-risk-metric",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={
                "op": "subtract",
                "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
                "right": {
                    "op": "metric",
                    "dimension": "quality",
                    "concept_id": "healing",
                },
            },
            unit="ratio",
            created_month=month,
        )
    )
    world.mechanical_language.condition_definitions["clinic-risk"] = (
        ConditionDefinition(
            id="clinic-risk",
            concept_id="clinic-risk",
            target_kind="region",
            metric_definition_id="clinic-risk-metric",
            activate_above=0.7,
            resolve_below=0.5,
            activate_after_months=1,
            resolve_after_months=1,
            created_month=month,
        )
    )
    return city


@pytest.mark.asyncio
async def test_a_pressured_city_is_answered_inside_the_prehistory(
    base_map, tmp_path
) -> None:
    """Urban pressure is derived, then answered, before play.

    Only material state and the engine-owned rule are declared; the condition
    itself is produced by the real semantic pass. The option is one the engine
    composed, and only the selection is injected.
    """
    world = _world(base_map, pressured=False)
    city = _declare_urban_pressure(world)
    assert world.mechanical_language.condition_instances == {}
    integrity_before = city.city_state.assets[0].integrity

    with _inject_government_choice("urban_maintenance"):
        events = await _run(world)

    # The semantic pass really derived the condition; nothing seeded it.
    activations = [
        event for event in events
        if event.event_type == "semantic_condition_activated"
        and str((event.render_params or {}).get("region_id")) == str(city.id)
    ]
    assert activations, "the semantic pass derived no condition from the damage"
    assert world.mechanical_language.condition_instances

    repairs = [
        event for event in events
        if event.event_type == "city_maintenance_completed"
    ]
    assert repairs, "the prehistory never answered the urban pressure"
    repair = repairs[0]

    # A real owner transition, and the asset really moved.
    delta = repair.causal_payload["deltas"][0]
    assert delta["aspect"] == "urban_asset_integrity"
    assert float(delta["after"]) > float(delta["before"])
    assert city.city_state.assets[0].integrity > integrity_before

    # Authored by the government's own decision, which is also a fact here.
    decisions = [
        event for event in events
        if event.fact_kind is FactKind.DECISION
        and any(
            link.cause_event_id == event_id
            for link in repair.causal_links
            for event_id in (event.id,)
        )
    ]
    assert decisions, "the repair cites no decision produced in the prehistory"

    # And the institution remembers having done it.
    institution_id = _dynasty_institution_id(world)
    remembered = [
        memory
        for memory in world.institutional_relations.memories_for(institution_id)
        if memory.event_id == repair.id
    ]
    assert remembered
    assert dict(remembered[0].factors)["relative_scale"] == pytest.approx(
        float(delta["after"]) - float(delta["before"])
    )

    # Everything stayed before the playable month.
    assert int(world.month_stamp) == int(PLAYABLE_START)
    for event in (repair, *decisions):
        assert int(event.month_stamp) < int(PLAYABLE_START)

    # And it survives the project's own save/load, memory included.
    save_path = tmp_path / "urban_prehistory.json"
    original_map = world.map
    success, _message = save_game(world, Simulator(world), [], save_path)
    assert success
    world.event_manager.close()
    with patch(
        "src.run.load_map.load_cultivation_world_map", return_value=original_map
    ):
        loaded, _simulator, _sects = load_game(save_path)
    # The material state, the memory and the causal chain all came back.
    restored_city = loaded.map.regions[city.id]
    assert restored_city.city_state.assets[0].integrity == pytest.approx(
        city.city_state.assets[0].integrity
    )
    restored_repair = loaded.event_manager.get_event_by_id(repair.id)
    assert restored_repair is not None
    assert restored_repair.causal_payload["deltas"][0]["after"] == delta["after"]
    remembered_after_load = [
        memory
        for memory in loaded.institutional_relations.memories_for(institution_id)
        if memory.event_id == repair.id
    ]
    assert remembered_after_load
    assert dict(remembered_after_load[0].factors) == dict(remembered[0].factors)
    # The decision that authored it, and the activation that motivated it, are
    # both still real facts in the store.
    assert loaded.event_manager.get_event_by_id(decisions[0].id) is not None
    assert loaded.event_manager.get_event_by_id(activations[0].id) is not None


@pytest.mark.asyncio
async def test_an_unclaimed_city_answers_through_react_city(base_map) -> None:
    """`react_city` really belongs to the window, not just `react_government`.

    Maintenance only, and deliberately small: the capacity-project lifecycle
    and the urban rollback are proven separately.
    """
    world = _world(base_map, pressured=False)
    city = _declare_urban_pressure(world)
    # Nobody governs it, so the city answers for itself.
    city.city_state = replace(
        city.city_state, governance=CityGovernance("", "", 0.8)
    )
    integrity_before = city.city_state.assets[0].integrity

    with _inject_city_choice("urban_maintenance"):
        events = await _run(world)

    repairs = [
        event for event in events
        if event.event_type == "city_maintenance_completed"
    ]
    assert repairs, "the unclaimed city answered nothing"
    assert city.city_state.assets[0].integrity > integrity_before
    assert int(world.month_stamp) == int(PLAYABLE_START)
    assert int(repairs[0].month_stamp) < int(PLAYABLE_START)


def _inject_city_choice(action_kind: str):
    """The same test-only selection, for the unclaimed-city interpreter."""
    from contextlib import contextmanager
    from unittest.mock import patch

    from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
    import src.systems.city_interpreter as interpreter

    original = interpreter.interpret_domain_affordances

    async def choose(*args, **kwargs):
        options = tuple(kwargs.get("affordances") or ())
        chosen = next(
            (item for item in options if item.action_kind == action_kind), None
        )
        if chosen is None:
            return await original(*args, **kwargs)
        return await original(*args, **{
            **kwargs,
            "injected_decision": DomainDecision(
                DomainDecisionKind.ACT, "The city builds.", chosen.id
            ),
        })

    @contextmanager
    def _scope():
        with patch.object(interpreter, "interpret_domain_affordances", choose):
            yield

    return _scope()


@pytest.mark.asyncio
async def test_a_quiet_prehistory_answers_nothing_urban(base_map) -> None:
    """No pressure, no repair: the new phases force no drama."""
    world = _world(base_map, pressured=False)

    events = await _run(world)

    assert not [
        event for event in events
        if event.event_type
        in ("city_maintenance_completed", "urban_capacity_project_started")
    ]


def _dynasty_institution_id(world) -> str:
    from src.classes.institution import Institution, InstitutionKind
    from src.classes.mechanical_language import EntityRef as _Ref

    return Institution.id_for(
        InstitutionKind.DYNASTY, _Ref("dynasty", str(world.dynasty.id))
    )


def test_prehistory_phases_are_a_filter_over_the_canonical_registry() -> None:
    selected = prehistory_phases()

    assert tuple(phase.name for phase in selected) == PREHISTORY_PHASE_NAMES
    assert selected[-1].name == "finalize_step"
    # Late mechanical evidence is persisted before the finalizer, so playable
    # months can still recompute from prehistory sources.
    assert "carry_forward_mechanical_invalidations" in PREHISTORY_PHASE_NAMES
    forbidden = {
        "decide_actions",
        "execute_actions",
        "update_age_and_birth",
        "resolve_death",
        "update_regional_climate",
        "generate_chronicle",
    }
    assert not forbidden.intersection(PREHISTORY_PHASE_NAMES)


@pytest.mark.parametrize(
    ("playable_start", "expected"),
    [(PLAYABLE_START, PREHISTORY_MONTHS), (0, 0), (2, 2), (5, 3)],
)
def test_month_count_clamps_to_the_calendar_that_exists(
    playable_start, expected
) -> None:
    assert prehistory_month_count(playable_start) == expected
    assert int(genesis_month_stamp(playable_start)) == int(playable_start) - expected


@pytest.mark.asyncio
async def test_natural_prehistory_reaches_playable_january_without_forcing_anything(
    base_map,
) -> None:
    world = _world(base_map, pressured=False)

    events = await _run(world)

    assert int(world.month_stamp) == int(PLAYABLE_START)
    assert all(int(event.month_stamp) < int(PLAYABLE_START) for event in events)
    # A quiet prehistory is a valid world: nothing is invented to fill a quota.
    assert world.institutional_relations.commitments == {}


@pytest.mark.asyncio
async def test_pressured_prehistory_builds_a_real_chain_through_the_same_owners(
    base_map,
) -> None:
    world = _world(base_map, pressured=True)

    events = await _run(world)

    types = [event.event_type for event in events]
    # Request and acceptance are independent decisions, and the material
    # transfer is executed by the canonical economy owner, not by prehistory.
    for required in (
        "regional_resource_shortage",
        "institutional_resource_request_interpretation_decision",
        "institutional_aid_requested",
        "institutional_resource_response_interpretation_decision",
        "institutional_aid_accepted",
        "regional_resource_transfer_completed",
        "institutional_commitment_term_fulfilled",
    ):
        assert required in types, f"{required} is missing from the prehistory"
    commitments = world.institutional_relations.commitments
    assert commitments, "the pressured prehistory produced no commitment"
    assert all(commitment.terms for commitment in commitments.values())
    memories = world.institutional_relations.memories
    assert memories, "the fulfilled aid left no institutional memory"
    known_ids = {str(event.id) for event in events}
    assert all(str(memory.event_id) in known_ids for memory in memories.values())
    assert int(world.month_stamp) == int(PLAYABLE_START)


@pytest.mark.asyncio
async def test_prehistory_facts_are_pre_playable_and_have_no_future_causes(
    base_map,
) -> None:
    world = _world(base_map, pressured=True)

    events = await _run(world)
    by_id = {str(event.id): event for event in events}

    assert events
    for event in events:
        assert int(event.month_stamp) < int(PLAYABLE_START)
        for link in event.causal_links or ():
            cause_id = str(link.cause_event_id)
            cause = by_id.get(cause_id) or world.event_manager.get_event_by_id(cause_id)
            assert cause is not None, f"cause {cause_id} does not resolve to a fact"
            assert not getattr(cause, "is_story", False)
            assert int(cause.month_stamp) <= int(event.month_stamp)
            assert int(cause.month_stamp) < int(PLAYABLE_START)


@pytest.mark.asyncio
async def test_decisions_carry_no_deltas_and_deltas_reference_their_own_event(
    base_map,
) -> None:
    world = _world(base_map, pressured=True)

    events = await _run(world)

    decisions = [event for event in events if event.fact_kind is FactKind.DECISION]
    assert decisions, "the pressured prehistory made no independent decision"
    for event in decisions:
        payload = event.causal_payload or {}
        assert payload.get("decision")
        assert not payload.get("deltas")
    for event in events:
        for delta in (event.causal_payload or {}).get("deltas") or ():
            assert str(delta["event_id"]) == str(event.id)


@pytest.mark.asyncio
async def test_test_mode_prehistory_never_calls_a_provider(base_map) -> None:
    world = _world(base_map, pressured=True)
    provider = AsyncMock(side_effect=AssertionError("prehistory called a provider"))

    with patch("src.utils.llm.client.call_llm_with_template", provider):
        await _run(world)

    assert provider.call_count == 0
    assert provider.await_count == 0


@pytest.mark.asyncio
async def test_failed_month_is_rolled_back_and_stops_the_window(
    base_map, monkeypatch
) -> None:
    world = _world(base_map, pressured=True)
    genesis = int(world.month_stamp)
    original_update = regional_economy.phase_update_regional_economy
    original_react = economy_reactivity.process_economy_reactivity
    month_starts: list[tuple[dict, tuple]] = []
    calls = {"count": 0}

    def recording_update(*args, **kwargs):
        # The economy update is the first phase, so this is the month's start.
        month_starts.append(
            (dict(world.map.regions[305].economy.stocks), random.getstate())
        )
        return original_update(*args, **kwargs)

    async def failing_react(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return await original_react(*args, **kwargs)
        random.random()
        raise RuntimeError("prehistory month failed")

    monkeypatch.setattr(
        regional_economy, "phase_update_regional_economy", recording_update
    )
    monkeypatch.setattr(
        economy_reactivity, "process_economy_reactivity", failing_react
    )

    with pytest.raises(RuntimeError, match="prehistory month failed"):
        await _run(world)

    # The failed month restored its own snapshot: clock, canonical state and
    # RNG cursor are exactly where that month started, and earlier months keep
    # their committed history.
    assert calls["count"] == 2
    assert int(world.month_stamp) == genesis + 1
    failed_month_stocks, failed_month_random = month_starts[1]
    assert dict(world.map.regions[305].economy.stocks) == failed_month_stocks
    assert random.getstate() == failed_month_random


@pytest.mark.asyncio
async def test_cancelled_month_is_rejected_instead_of_looping(base_map) -> None:
    world = _world(base_map, pressured=False)
    world.runtime = SimpleNamespace(is_reset_requested=lambda: True)

    with pytest.raises(PrehistoryError, match="did not advance"):
        await _run(world)

    assert int(world.month_stamp) == int(genesis_month_stamp(PLAYABLE_START))


@pytest.mark.asyncio
async def test_wrong_initial_cursor_is_rejected(base_map) -> None:
    world = _world(base_map, pressured=False)
    world.month_stamp = PLAYABLE_START

    with pytest.raises(PrehistoryError, match="must begin at month"):
        await _run(world)


@pytest.mark.asyncio
async def test_prehistory_history_survives_save_and_load(base_map, tmp_path) -> None:
    world = _world(base_map, pressured=True)
    await _run(world)
    before = world.institutional_relations.to_dict()
    assert before["commitments"]
    memories = world.institutional_relations.memories
    assert memories

    save_path = tmp_path / "prehistory.json"
    ok, message = save_game(world, Simulator(world), [], save_path=save_path)
    assert ok, message
    loaded_world, _, _ = load_game(save_path)

    assert loaded_world.institutional_relations.to_dict() == before
    assert int(loaded_world.month_stamp) == int(PLAYABLE_START)
    # The remembered facts are still real events in the loaded store, dated
    # before the playable month.
    for memory in loaded_world.institutional_relations.memories.values():
        remembered = loaded_world.event_manager.get_event_by_id(str(memory.event_id))
        assert remembered is not None, f"memory {memory.event_id} lost its fact"
        assert int(remembered.month_stamp) < int(PLAYABLE_START)


@pytest.mark.asyncio
async def test_first_playable_month_must_advance_the_clock() -> None:
    world = SimpleNamespace(month_stamp=MonthStamp(int(PLAYABLE_START)))

    async def advancing_step():
        world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
        return []

    await _generate_initial_events(sim=SimpleNamespace(world=world, step=advancing_step))
    assert int(world.month_stamp) == int(PLAYABLE_START) + 1

    async def cancelled_step():
        return []

    with pytest.raises(RuntimeError, match="did not advance"):
        await _generate_initial_events(
            sim=SimpleNamespace(world=world, step=cancelled_step)
        )


def test_same_minute_worlds_reserve_distinct_save_slots(tmp_path) -> None:
    from src.sim.load.load_game import get_events_db_path

    config = SimpleNamespace(paths=SimpleNamespace(saves=tmp_path))
    first_save, first_db = _create_save_slot(
        config=config, get_events_db_path=get_events_db_path
    )
    first_save.write_text("{}", encoding="utf-8")
    first_db.write_text("", encoding="utf-8")
    second_save, second_db = _create_save_slot(
        config=config, get_events_db_path=get_events_db_path
    )

    assert first_save != second_save
    assert first_db != second_db
    assert first_save.exists() and first_db.exists()


@pytest.mark.asyncio
async def test_real_initialization_wires_genesis_prehistory_and_publication(
    tmp_path,
) -> None:
    """One end-to-end init with the real World, Simulator and phases."""
    from src.classes.environment.map import Map
    from src.classes.environment.tile import TileType
    from src.config import RunConfig
    from src.server import main

    from pathlib import Path

    from src.classes.alignment import Alignment
    from src.classes.core.sect import Sect, SectHeadQuarter
    from src.classes.environment.sect_region import SectRegion

    anchored_sect = Sect(
        401,
        "Azure Peak Sect",
        "",
        "",
        Alignment.RIGHTEOUS,
        SectHeadQuarter("Azure Peak", "", Path("")),
        [],
        magic_stone=100,
    )

    def small_map(*_args, **_kwargs) -> Map:
        game_map = Map(width=3, height=2)
        for x in range(3):
            for y in range(2):
                game_map.create_tile(x, y, TileType.PLAIN)
        # A real declared headquarters region: the map, not the sect object,
        # is what names the seat, through `sect_id`. The region id is
        # deliberately different from the sect id, so confusing the two fails.
        seat = SectRegion(
            id=901, name="Azure Peak", desc="", cors=[(0, 0)],
            sect_id=anchored_sect.id, sect_name=anchored_sect.name,
        )
        game_map.regions[seat.id] = seat
        # A second sect region with no declared owner: nothing is inferred.
        unowned = SectRegion(id=902, name="Nameless Hall", desc="", cors=[(1, 0)])
        game_map.regions[unowned.id] = unowned
        return game_map

    previous_state = dict(main.game_instance)
    main.game_instance.update(
        {
            "world": None,
            "sim": None,
            "is_paused": True,
            "init_status": "idle",
            "init_error": None,
            "current_save_path": None,
            "run_config": RunConfig(
                content_locale="pt-BR",
                init_npc_num=0,
                sect_num=1,
                npc_awakening_rate_per_month=0.0,
                test_mode=True,
            ).model_dump(),
        }
    )
    provider = AsyncMock(side_effect=AssertionError("initialization called a provider"))
    try:
        with patch.object(main, "reload_all_static_data"), patch.object(
            main, "scan_avatar_assets", return_value={}
        ), patch.object(
            main, "load_cultivation_world_map", side_effect=small_map
        ), patch.object(
            main, "check_llm_connectivity", return_value=(True, "")
        ), patch(
            "src.server.main.CONFIG"
        ) as mock_config, patch(
            "src.server.main.sects_by_id", {401: anchored_sect}
        ), patch(
            "src.server.init_flow._prepare_initial_character_profiles",
            new=AsyncMock(),
        ), patch(
            "src.utils.llm.client.call_llm_with_template", provider
        ):
            mock_config.paths.saves = tmp_path
            mock_config.world.start_year = 100

            await main.init_game_async()

        assert main.game_instance["init_error"] is None
        assert main.game_instance["init_status"] == "ready"
        world = main.game_instance["world"]
        assert world is not None
        assert main.game_instance["sim"] is not None
        assert main.game_instance["current_save_path"] is not None
        assert main.game_instance["is_paused"] is True

        # Three prehistory months plus the first playable month.
        assert int(world.month_stamp) == int(PLAYABLE_START) + 1
        assert world.start_year == 100
        assert world.institutional_authority.institutions
        stored = world.event_manager.get_recent_events(limit=200)
        assert stored
        assert any(
            int(event.month_stamp) < int(PLAYABLE_START) for event in stored
        ), "initialization produced no pre-playable fact"
        assert all(
            int(event.month_stamp) <= int(PLAYABLE_START) for event in stored
        )
        assert provider.call_count == 0

        # The declared headquarters really became an anchor during this very
        # initialization: one for the region that names its owner, none for
        # the one that declares no `sect_id`, and none for the dynasty, which
        # declares neither capital nor founder anywhere.
        anchors = world.institutional_authority.identity_anchors
        assert len(anchors) == 1
        anchor = next(iter(anchors.values()))
        assert anchor.kind is IdentityAnchorKind.HEADQUARTERS
        assert anchor.subject == EntityRef("region", "901")
        assert not [
            item for item in anchors.values() if item.subject.id == "902"
        ]
        assert all(
            not item.institution_id.startswith("inst:dynasty")
            for item in anchors.values()
        )

        # Established at the exact genesis month, before the playable one.
        genesis = int(PLAYABLE_START) - prehistory_month_count(PLAYABLE_START)
        assert anchor.established_month == genesis

        # Its evidence is a real, still-published premise fact -- which is
        # what `_validate_institutional_evidence` demands at every save.
        assert len(anchor.evidence_event_ids) == 1
        premise = world.event_manager.get_event_by_id(anchor.evidence_event_ids[0])
        assert premise is not None
        assert premise.event_type == "institution_identity_anchored"
        assert premise.fact_kind is FactKind.STATE_TRANSITION
        assert premise.causal_origin is CausalOrigin.DETERMINISTIC
        assert int(premise.month_stamp) == genesis
        assert premise.render_params["premise"] == "world_genesis"
        assert premise.render_params["anchor_id"] == anchor.id
        assert premise.render_params["region_id"] == "901"
        assert premise.render_params["institution_id"] == anchor.institution_id
        delta = premise.causal_payload["deltas"][0]
        assert delta["owner_kind"] == "institutional_authority"
        assert delta["owner_id"] == anchor.institution_id
        assert delta["after"] == "established"
        # Nothing claims a founding happened now.
        assert "founded" not in premise.content.lower()
    finally:
        world = main.game_instance.get("world")
        manager = getattr(world, "event_manager", None) if world is not None else None
        if manager is not None and hasattr(manager, "close"):
            manager.close()
        main.game_instance.clear()
        main.game_instance.update(previous_state)

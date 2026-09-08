import json
import os
from pathlib import Path
import subprocess
from src.classes.items.magic_stone import MagicStone
import sys

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.environment.region import CityRegion
from src.classes.environment.city_state import (
    CityDistrict,
    CityState,
    UrbanAsset,
    UrbanServiceDemand,
)
from src.classes.environment.route import Route
from src.classes.event import FactKind
from src.classes.regional_economy import InfrastructureState, RegionalEconomyState
from src.run.load_map import load_cultivation_world_map
from src.server.runtime import DEFAULT_GAME_STATE, GameSessionRuntime
from src.server.serialization import serialize_events_for_client
from src.server.services.game_queries import get_event_causal_detail
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.causal_probe import (
    AvatarInjuryProbe,
    PopulationSurgeProbe,
    ResourceSupplyShockProbe,
    RouteInterruptionProbe,
    UrbanServiceStrainProbe,
    apply_causal_probe,
    build_causal_probe_schedule,
    prepare_health_recovery_strain_world,
    prepare_institutional_urban_strain_world,
)
from src.systems.causal_observatory import CausalTortureConfig, CausalTortureRunner
from src.systems.economy_reactivity import process_economy_reactivity
from src.systems.regional_economy import phase_update_regional_economy
from src.utils.llm.runtime_mode import llm_test_mode_scope


def _city(world, region_id: int, *, population: float, capacity: float) -> CityRegion:
    city = CityRegion(
        id=region_id,
        name=f"City {region_id}",
        desc="",
        cors=[(region_id, 0)],
        population=population,
        population_capacity=capacity,
    )
    world.map.regions[region_id] = city
    return city


def _economic_city(
    world,
    region_id: int,
    *,
    stock: float,
    production: float,
    demand: float,
) -> CityRegion:
    city = _city(world, region_id, population=40, capacity=100)
    city.economy = RegionalEconomyState(
        stocks={"grain": stock},
        capacities={"grain": 20},
        production_rates={"grain": production},
        demand_rates={"grain": demand},
        access={"grain": 0.8},
    )
    city.infrastructure = InfrastructureState(capacities={"transport": 5})
    return city


def _urban_service_city(
    world,
    region_id: int,
    *,
    population: float = 90,
    integrity: float = 0.8,
) -> CityRegion:
    city = _city(world, region_id, population=population, capacity=100)
    city.cors = [(0, 0)]
    city.center_loc = (0, 0)
    city.city_state = CityState(
        districts=(CityDistrict("core", "core", ((0, 0),), 1.0),),
        assets=(UrbanAsset("waterworks", "core", ("clean_water",), 100, 1.0, integrity),),
        service_demands=(UrbanServiceDemand("clean_water", 1.0),),
    )
    return city


def test_urban_service_strain_selects_grounded_city_service_and_commits_causal_delta(
    base_world,
):
    city = _urban_service_city(base_world, 931, integrity=0.8)
    population_before = city.population
    schedule = build_causal_probe_schedule(base_world, "urban_service_strain")

    assert schedule == (
        UrbanServiceStrainProbe(
            id="urban-service-strain:region:931:clean_water:waterworks",
            month_offset=0,
            region_id=931,
            capability_id="clean_water",
            asset_id="waterworks",
            remaining_integrity_fraction=0.5,
        ),
    )

    event = apply_causal_probe(base_world, schedule[0])

    strained_asset = city.city_state.assets[0]
    assert strained_asset.integrity == 0.4
    assert city.population == population_before
    assert event.event_type == "causal_probe_urban_service_strain"
    assert event.causal_origin is CausalOrigin.EXTERNAL_EVENT
    assert event.fact_kind is FactKind.STATE_TRANSITION
    delta = event.causal_payload["deltas"][0]
    assert delta["event_id"] == event.id
    assert delta["owner_kind"] == "region"
    assert delta["owner_id"] == "931"
    assert delta["aspect"] == "urban_asset_integrity"
    assert delta["before"] == "0.8"
    assert delta["after"] == "0.4"
    assert delta["magnitude"] == -0.4
    assert base_world.mechanical_language.pending_target_source_event_ids == {}
    assert base_world.mechanical_language.pending_affinity_source_event_ids == {
        "region:931": {"urban_service:clean_water": [event.id]},
    }
    assert base_world.event_manager.get_event_by_id(event.id) is event


def test_urban_service_strain_schedule_is_empty_without_grounded_substrate(base_world):
    city = _city(base_world, 932, population=90, capacity=100)
    city.city_state = CityState(
        districts=(CityDistrict("core", "core", ((0, 0),), 1.0),),
        service_demands=(UrbanServiceDemand("clean_water", 1.0),),
    )

    assert build_causal_probe_schedule(base_world, "urban_service_strain") == ()


def test_institutional_profile_reuses_dynamic_city_service_asset_selection(base_world):
    _urban_service_city(base_world, 934, population=90, integrity=0.8)
    selected = _urban_service_city(base_world, 935, population=99, integrity=0.8)

    schedule = build_causal_probe_schedule(base_world, "institutional_urban_strain")

    assert schedule == (
        UrbanServiceStrainProbe(
            id="institutional-urban-strain:region:935:clean_water:waterworks",
            month_offset=0,
            region_id=935,
            capability_id="clean_water",
            asset_id="waterworks",
            remaining_integrity_fraction=0.5,
        ),
    )
    assert selected.id == schedule[0].region_id


def test_institutional_world_setup_is_idempotent_and_uses_canonical_entities(base_world):
    city = _urban_service_city(base_world, 936)

    first = prepare_institutional_urban_strain_world(base_world)
    second = prepare_institutional_urban_strain_world(base_world)

    assert first.city is second.city is city
    assert first.dynasty is second.dynasty is base_world.dynasty
    assert first.sect is second.sect
    assert first.member is second.member
    assert len(base_world.existed_sects) == 1
    assert len(base_world.avatar_manager.avatars) == 1
    assert city.city_state.governance.controller_kind == "dynasty"
    assert city.city_state.governance.controller_id == str(first.dynasty.id)
    assert first.member.tile.region is city
    assert first.member.is_dead is False
    assert first.member.magic_stone.value == 0
    assert first.sect.magic_stone >= 600

    first.sect.magic_stone = 123
    first.member.magic_stone = MagicStone(77)
    third = prepare_institutional_urban_strain_world(base_world)

    assert third.sect.magic_stone == 123
    assert third.member.magic_stone.value == 77


def _health_service_city(
    world,
    region_id: int,
    *,
    population: float = 90,
    integrity: float = 0.8,
) -> CityRegion:
    city = _city(world, region_id, population=population, capacity=100)
    city.cors = [(0, 0)]
    city.center_loc = (0, 0)
    city.city_state = CityState(
        districts=(CityDistrict("core", "core", ((0, 0),), 1.0),),
        assets=(UrbanAsset("clinic", "core", ("healing",), 100, 1.0, integrity),),
        service_demands=(UrbanServiceDemand("healing", 1.0),),
    )
    return city


def test_health_profile_selects_grounded_city_and_records_nonfatal_avatar_injury(
    base_world,
):
    city = _health_service_city(base_world, 938)
    setup = prepare_health_recovery_strain_world(base_world)

    assert setup is not None
    assert setup.city is city
    schedule = build_causal_probe_schedule(base_world, "health_recovery_strain")
    assert schedule == (
        AvatarInjuryProbe(
            id="health-recovery-strain:avatar:causal-torture:health-avatar",
            month_offset=0,
            avatar_id="causal-torture:health-avatar",
            target_damage_ratio=0.4,
        ),
        UrbanServiceStrainProbe(
            id="health-recovery-strain:region:938:healing:clinic",
            month_offset=0,
            region_id=938,
            capability_id="healing",
            asset_id="clinic",
            remaining_integrity_fraction=0.5,
        ),
    )

    avatar = setup.avatar
    injury_event = apply_causal_probe(base_world, schedule[0])

    assert avatar.is_dead is False
    assert avatar.hp.cur == 60
    assert avatar.individual_consequences.active_injury is not None
    assert avatar.individual_consequences.active_injury.cause_event_ids == [
        injury_event.id
    ]
    assert injury_event.causal_origin is CausalOrigin.EXTERNAL_EVENT
    assert injury_event.fact_kind.value == "state_transition"
    assert {
        delta["aspect"] for delta in injury_event.causal_payload["deltas"]
    } == {"hp", "active_injury"}
    assert base_world.mechanical_language.pending_target_source_event_ids == {}


def test_health_profile_degrades_the_selected_healing_asset_and_rolls_back_failed_commit(
    base_world,
    monkeypatch,
):
    city = _health_service_city(base_world, 939)
    setup = prepare_health_recovery_strain_world(base_world)
    probe = build_causal_probe_schedule(base_world, "health_recovery_strain")[1]
    monkeypatch.setattr(base_world.event_manager, "commit_step", lambda events: False)

    with pytest.raises(RuntimeError, match="commit failed"):
        apply_causal_probe(base_world, probe)

    assert city.city_state.assets[0].integrity == 0.8
    assert setup.avatar.hp.cur == setup.avatar.hp.max
    assert setup.avatar.individual_consequences.active_injury is None
    assert base_world.mechanical_language.pending_target_source_event_ids == {}


@pytest.mark.asyncio
async def test_health_profile_runs_provider_free_and_discovers_recovery_strain(
    monkeypatch,
):
    from unittest.mock import AsyncMock

    provider = AsyncMock(side_effect=AssertionError("real provider must not run"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)

    report = await CausalTortureRunner(
        CausalTortureConfig(
            worlds=1,
            months=4,
            seed=73,
            probe_profile="health_recovery_strain",
        )
    ).run()

    run = report.runs[0]
    assert run.event_types["causal_probe_avatar_injury"] == 1
    assert run.event_types["causal_probe_urban_service_strain"] == 1
    assert run.event_types["semantic_condition_activated"] >= 1
    assert run.causal_chains["broken_events"] == 0
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_health_probe_cause_reaches_the_semantic_condition_event(base_world):
    _health_service_city(base_world, 940)
    setup = prepare_health_recovery_strain_world(base_world)
    schedule = build_causal_probe_schedule(base_world, "health_recovery_strain")
    injury_event = apply_causal_probe(base_world, schedule[0])
    service_event = apply_causal_probe(base_world, schedule[1])

    simulator = Simulator(base_world)
    with llm_test_mode_scope(True):
        for _ in range(4):
            await simulator.step()

    condition_event = next(
        event
        for event in base_world.event_manager.get_recent_events(500)
        if event.event_type == "semantic_condition_activated"
        and event.render_params["condition_definition_id"] == "strained_health_recovery"
    )
    assert setup.avatar.individual_consequences.active_injury is not None
    assert {link.cause_event_id for link in condition_event.causal_links}.issuperset(
        {injury_event.id, service_event.id}
    )
    settlement_event = next(
        event
        for event in base_world.event_manager.get_recent_events(500)
        if event.event_type == "semantic_condition_activated"
        and event.render_params["condition_definition_id"]
        == "overcrowded_settlement"
    )
    assert injury_event.id not in {
        link.cause_event_id for link in settlement_event.causal_links
    }
    assert service_event.id not in {
        link.cause_event_id for link in settlement_event.causal_links
    }

    setup.avatar.hp.cur = setup.avatar.hp.max
    with llm_test_mode_scope(True):
        for _ in range(2):
            await simulator.step()

    recovery_event = next(
        event
        for event in base_world.event_manager.get_recent_events(500)
        if any(
            delta.get("aspect") == "recovery"
            for delta in (event.causal_payload or {}).get("deltas", [])
            if isinstance(delta, dict)
        )
    )
    resolution_event = next(
        event
        for event in base_world.event_manager.get_recent_events(500)
        if event.event_type == "semantic_condition_resolved"
        and event.render_params["condition_definition_id"]
        == "strained_health_recovery"
    )
    assert setup.avatar.individual_consequences.active_injury is None
    assert {
        (link.cause_event_id, link.relation.value)
        for link in resolution_event.causal_links
    }.issuperset({
        (condition_event.id, "resolves"),
        (recovery_event.id, "enabled_by"),
    })


def test_causal_torture_json_mode_keeps_stdout_machine_readable(tmp_path):
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(repository / "tools" / "causal_torture_test.py"),
            "--worlds",
            "1",
            "--months",
            "1",
            "--seed",
            "73",
            "--profile",
            "institutional_urban_strain",
            "--json",
        ],
        cwd=repository,
        env={**os.environ, "CWS_DATA_DIR": str(tmp_path / "data")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["config"]["probe_profile"] == "institutional_urban_strain"
    assert payload["totals"]["worlds"] == 1


def test_causal_torture_cli_accepts_health_recovery_profile(tmp_path):
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(repository / "tools" / "causal_torture_test.py"),
            "--worlds",
            "1",
            "--months",
            "1",
            "--seed",
            "73",
            "--profile",
            "health_recovery_strain",
            "--json",
        ],
        cwd=repository,
        env={**os.environ, "CWS_DATA_DIR": str(tmp_path / "data")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["config"]["probe_profile"] == "health_recovery_strain"
    assert payload["runs"][0]["event_types"]["causal_probe_avatar_injury"] == 1


@pytest.mark.asyncio
async def test_institutional_profile_runs_with_real_entities_without_provider_or_storage(
    monkeypatch,
):
    from unittest.mock import AsyncMock

    provider = AsyncMock(side_effect=AssertionError("real provider must not run"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)

    report = await CausalTortureRunner(
        CausalTortureConfig(
            worlds=1,
            months=12,
            seed=73,
            probe_profile="institutional_urban_strain",
        )
    ).run()

    run = report.runs[0]
    assert run.event_types["causal_probe_urban_service_strain"] == 1
    assert run.material_events["institutional_support"] >= 1
    assert run.reactions["affordance_attempts"] >= 2
    assert run.reactions["post_attempt_lifecycle_events"] == 0
    assert run.causal_chains["broken_events"] == 0
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_institutional_runner_restores_the_supplied_world_after_observation(
    base_world,
):
    city = _urban_service_city(base_world, 937, integrity=0.8)
    dynasty_before = base_world.dynasty
    sects_before = tuple(getattr(base_world, "existed_sects", ()))
    avatars_before = tuple(base_world.avatar_manager.avatars)
    governance_before = city.city_state.governance
    event_ids_before = tuple(
        event.id
        for event in base_world.event_manager.get_events_between_months(
            -(2**63),
            2**63 - 1,
        )
    )

    report = await CausalTortureRunner(
        CausalTortureConfig(
            worlds=1,
            months=1,
            seed=74,
            probe_profile="institutional_urban_strain",
        )
    ).run(
        world_factory=lambda _world_index, _seed: base_world,
        step=lambda _world: (),
    )

    assert report.runs[0].event_types["causal_probe_urban_service_strain"] == 1
    assert base_world.dynasty is dynasty_before
    assert tuple(getattr(base_world, "existed_sects", ())) == sects_before
    assert tuple(base_world.avatar_manager.avatars) == avatars_before
    assert city.city_state.governance == governance_before
    assert city.city_state.assets[0].integrity == 0.8
    assert tuple(
        event.id
        for event in base_world.event_manager.get_events_between_months(
            -(2**63),
            2**63 - 1,
        )
    ) == event_ids_before


def test_urban_service_strain_rolls_back_asset_and_pending_source_when_commit_fails(
    base_world,
    monkeypatch,
):
    city = _urban_service_city(base_world, 933, integrity=0.8)
    probe = build_causal_probe_schedule(base_world, "urban_service_strain")[0]
    monkeypatch.setattr(base_world.event_manager, "commit_step", lambda events: False)

    with pytest.raises(RuntimeError, match="commit failed"):
        apply_causal_probe(base_world, probe)

    assert city.city_state.assets[0].integrity == 0.8
    assert base_world.mechanical_language.pending_target_source_event_ids == {}
    assert base_world.mechanical_language.pending_affinity_source_event_ids == {}


@pytest.mark.asyncio
async def test_urban_service_strain_profile_drives_grounded_maintenance_without_provider(
    monkeypatch,
):
    from unittest.mock import AsyncMock

    provider = AsyncMock(side_effect=AssertionError("real provider must not run"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)

    report = await CausalTortureRunner(
        CausalTortureConfig(
            worlds=1,
            months=12,
            seed=73,
            probe_profile="urban_service_strain",
        )
    ).run()

    run = report.runs[0]
    assert run.event_types["causal_probe_urban_service_strain"] == 1
    assert run.event_types["semantic_condition_activated"] >= 1
    assert run.event_types["city_interpretation_decision"] >= 1
    assert run.material_events["maintenance"] >= 1
    assert run.causal_chains["broken_events"] == 0
    assert max(
        int(depth) for depth in run.causal_telemetry["chain_depth_distribution"]
    ) >= 3
    provider.assert_not_awaited()


def test_population_pressure_probe_selects_by_world_state_and_commits_causal_evidence(
    base_world,
):
    pressured = _city(base_world, 901, population=80, capacity=100)
    _city(base_world, 902, population=20, capacity=100)
    base_world.map.set_routes([
        Route("route-probe", (901, 902), "road", 10, 1.0, True),
    ])

    schedule = build_causal_probe_schedule(base_world, "population_pressure")

    assert schedule == (
        PopulationSurgeProbe(
            id="population-pressure:region:901",
            month_offset=0,
            region_id=901,
            target_ratio=1.05,
        ),
    )

    event = apply_causal_probe(base_world, schedule[0])

    assert pressured.population == 105
    assert event.event_type == "causal_probe_population_surge"
    assert event.causal_origin is CausalOrigin.EXTERNAL_EVENT
    assert event.fact_kind is FactKind.STATE_TRANSITION
    delta = event.causal_payload["deltas"][0]
    assert delta["id"]
    assert {key: value for key, value in delta.items() if key != "id"} == {
        "event_id": event.id,
        "owner_kind": "region",
        "owner_id": "901",
        "aspect": "population",
        "before": "80.0",
        "after": "105.0",
        "magnitude": 25.0,
    }
    assert base_world.event_manager.get_event_by_id(event.id) is event
    assert base_world.mechanical_language.pending_target_source_event_ids == {
        "region:901": [event.id],
    }


def test_resource_probe_ignores_stock_fully_reserved_for_other_work(base_world):
    source = _economic_city(
        base_world,
        903,
        stock=12,
        production=0,
        demand=0,
    )
    _economic_city(
        base_world,
        904,
        stock=0,
        production=0,
        demand=3,
    )
    source.economy.reserve_stock("commercial-order", "grain", 12.0)
    base_world.map.set_routes([
        Route("reserved-route", (903, 904), "road", 10, 1.0, True),
    ])

    assert source.economy.available_stock("grain") == 0.0
    assert build_causal_probe_schedule(base_world, "resource_shortage") == ()


@pytest.mark.asyncio
async def test_population_pressure_profile_drives_a_complete_causal_chain_without_provider(
    monkeypatch,
):
    from unittest.mock import AsyncMock

    provider = AsyncMock(side_effect=AssertionError("real provider must not run"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)
    report = await CausalTortureRunner(CausalTortureConfig(
        worlds=1,
        months=4,
        seed=41,
        probe_profile="population_pressure",
    )).run()

    run = report.runs[0]
    assert run.event_types["causal_probe_population_surge"] == 1
    assert run.event_types["semantic_condition_activated"] >= 1
    assert run.event_types["population_interpretation_decision"] >= 1
    assert run.material_events["migration"] >= 1
    assert run.causal_chains["broken_events"] == 0
    assert max(int(depth) for depth in run.causal_telemetry["chain_depth_distribution"]) >= 3
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_resource_shortage_probe_preserves_its_cause_through_validated_transfer(
    base_world,
):
    source = _economic_city(
        base_world,
        911,
        stock=12,
        production=0,
        demand=0,
    )
    destination = _economic_city(
        base_world,
        912,
        stock=3,
        production=3,
        demand=3,
    )
    base_world.map.set_routes([
        Route("supply-route", (911, 912), "road", 2, 1.0, True),
    ])

    schedule = build_causal_probe_schedule(base_world, "resource_shortage")

    assert schedule == (
        ResourceSupplyShockProbe(
            id="resource-shortage:region:912:grain",
            month_offset=0,
            region_id=912,
            resource_id="grain",
            remaining_stock_fraction=0.0,
            production_fraction=0.0,
        ),
    )
    probe_event = apply_causal_probe(base_world, schedule[0])
    month_events = phase_update_regional_economy(base_world)
    shortage = next(
        event
        for event in month_events
        if event.event_type == "regional_resource_shortage"
    )

    assert destination.economy.stocks["grain"] == 0
    assert destination.economy.production_rates["grain"] == 0
    assert {link.cause_event_id for link in shortage.causal_links} == {probe_event.id}

    with llm_test_mode_scope(True):
        reaction_events = await process_economy_reactivity(
            base_world,
            current_events=month_events,
            invalidations=DomainInvalidationQueue(),
        )

    assert [event.event_type for event in reaction_events] == [
        "economy_interpretation_decision",
        "regional_resource_transfer_completed",
    ]
    assert source.economy.stocks["grain"] == 10
    assert destination.economy.stocks["grain"] == 2


@pytest.mark.asyncio
async def test_blocked_supply_profile_interrupts_the_selected_route_and_records_no_action(
    base_world,
):
    _economic_city(base_world, 921, stock=12, production=0, demand=0)
    destination = _economic_city(
        base_world,
        922,
        stock=3,
        production=3,
        demand=3,
    )
    route = Route("fragile-route", (921, 922), "road", 2, 1.0, True)
    base_world.map.set_routes([route])

    schedule = build_causal_probe_schedule(base_world, "blocked_resource_shortage")

    assert isinstance(schedule[0], RouteInterruptionProbe)
    assert isinstance(schedule[1], ResourceSupplyShockProbe)
    probe_events = [apply_causal_probe(base_world, probe) for probe in schedule]
    month_events = phase_update_regional_economy(base_world)
    shortage = next(
        event
        for event in month_events
        if event.event_type == "regional_resource_shortage"
    )
    with llm_test_mode_scope(True):
        reaction_events = await process_economy_reactivity(
            base_world,
            current_events=month_events,
            invalidations=DomainInvalidationQueue(),
        )

    assert route.enabled is False
    assert destination.economy.stocks["grain"] == 0
    assert {link.cause_event_id for link in shortage.causal_links} == {
        event.id for event in probe_events
    }
    assert [event.event_type for event in reaction_events] == [
        "economy_interpretation_decision",
    ]
    interpretation = reaction_events[0].causal_payload["interpretation"]
    assert interpretation["decision"] == "maintain"
    assert "selected_affordance_id" not in interpretation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "expected_probe_types", "expected_transfers", "expected_no_action"),
    [
        (
            "resource_shortage",
            {"causal_probe_resource_supply_shock"},
            1,
            0,
        ),
        (
            "blocked_resource_shortage",
            {
                "causal_probe_resource_supply_shock",
                "causal_probe_route_interruption",
            },
            0,
            2,
        ),
    ],
)
async def test_resource_probe_profiles_run_end_to_end_without_provider(
    monkeypatch,
    profile,
    expected_probe_types,
    expected_transfers,
    expected_no_action,
):
    from unittest.mock import AsyncMock

    provider = AsyncMock(side_effect=AssertionError("real provider must not run"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)

    report = await CausalTortureRunner(CausalTortureConfig(
        worlds=1,
        months=2,
        seed=43,
        probe_profile=profile,
    )).run()

    run = report.runs[0]
    assert expected_probe_types <= set(run.event_types)
    assert run.material_events["economic_transfer"] == expected_transfers
    assert run.reactions["no_action"] == expected_no_action
    assert run.causal_chains["broken_events"] == 0
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_population_probe_root_remains_navigable_after_save_load(
    base_world,
    tmp_path,
    monkeypatch,
):
    from unittest.mock import AsyncMock

    provider = AsyncMock(side_effect=AssertionError("real provider must not run"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)
    base_world.map = load_cultivation_world_map("classic")
    base_world.run_config_snapshot = {
        "content_locale": "zh-CN",
        "map_id": "classic",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.0,
        "world_lore": "",
        "test_mode": True,
        "semantic_discovery_budget_per_month": 2,
        "population_interpreter_llm_budget_per_month": 2,
        "economy_interpreter_llm_budget_per_month": 2,
        "city_interpreter_llm_budget_per_month": 2,
    }
    probe = build_causal_probe_schedule(base_world, "population_pressure")[0]
    root_event = apply_causal_probe(base_world, probe)
    simulator = Simulator(base_world)

    with llm_test_mode_scope(True):
        for _ in range(4):
            await simulator.step()

    transfer = next(
        event
        for event in base_world.event_manager.get_recent_events(500)
        if event.event_type == "population_transfer_completed"
    )
    save_path = tmp_path / "population-probe-causal-chain.json"
    success, message = save_game(base_world, simulator, [], save_path=save_path)
    assert success, message
    loaded_world, _, _ = load_game(save_path)

    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime.set_world_and_sim(loaded_world, None)
    detail = get_event_causal_detail(
        runtime,
        serialize_events_for_client=lambda items, **kwargs: serialize_events_for_client(
            items,
            world=loaded_world,
        ),
        event_id=transfer.id,
        depth=5,
        limit=100,
    )

    ancestor_ids = {
        edge["event"]["id"]
        for edge in detail["causes"]
        if edge["event"] is not None
    }
    ancestor_types = {
        loaded_world.event_manager.get_event_by_id(event_id).event_type
        for event_id in ancestor_ids
    }
    assert loaded_world.event_manager.get_event_by_id(root_event.id) is not None
    assert root_event.id in ancestor_ids
    assert "causal_probe_population_surge" in ancestor_types
    assert "semantic_condition_activated" in ancestor_types
    assert "population_interpretation_decision" in ancestor_types
    assert detail["truncated"] is False
    provider.assert_not_awaited()

from unittest.mock import AsyncMock

import pytest

from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.sim.simulator import Simulator
from src.sim.save.save_game import save_game
from src.sim.load.load_game import load_game
from src.run.load_map import load_cultivation_world_map
from src.server.runtime import DEFAULT_GAME_STATE, GameSessionRuntime
from src.server.serialization import serialize_events_for_client
from src.server.services.game_queries import get_event_causal_detail
from src.systems.population_reactivity import (
    enqueue_population_transitions,
    enqueue_unreacted_population_conditions,
    process_population_reactivity,
)
from src.systems.semantic_world.service import evaluate_semantic_world
from src.systems.time import MonthStamp
from src.utils.llm.runtime_mode import llm_test_mode_scope

from tests.test_semantic_world_service import _proposal


def _add_reactive_city(world, region_id: int, ratio: float, coordinate: tuple[int, int]):
    city = CityRegion(
        id=region_id,
        name=f"City {region_id}",
        desc="",
        cors=[coordinate],
        population=ratio * 100,
        population_capacity=100,
    )
    for existing in world.map.regions.values():
        if not isinstance(existing, CityRegion) or existing.id == city.id:
            continue
        route = Route(
            id=f"test-route-{min(existing.id, city.id)}-{max(existing.id, city.id)}",
            endpoint_region_ids=(existing.id, city.id),
            mode="road",
            capacity=100,
            quality=0.8,
            enabled=True,
        )
        world.map.routes[route.id] = route
    world.map.regions[region_id] = city
    return city


async def _activate_pressure(world, city_id: int = 302):
    llm = AsyncMock(return_value=_proposal())
    await evaluate_semantic_world(world, llm_call=llm)
    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
    events = await evaluate_semantic_world(world, llm_call=llm)
    return next(event for event in events if event.render_params["region_id"] == str(city_id))


@pytest.mark.asyncio
async def test_semantic_transition_drives_one_intent_and_deterministic_transfer(base_world):
    origin = _add_reactive_city(base_world, 302, 0.90, (1, 1))
    destination = _add_reactive_city(base_world, 305, 0.40, (4, 4))
    transition = await _activate_pressure(base_world)
    queue = DomainInvalidationQueue()
    enqueue_population_transitions(base_world, [transition], queue)
    total_before = origin.population + destination.population
    interpreter = AsyncMock(return_value={
        "decision": "act",
        "reason": "A lower-load city can receive population.",
        "action_intent": {
            "action_kind": "population_transfer",
            "preferences": ["lower_settlement_load", "available_capacity"],
        },
    })

    events = await process_population_reactivity(
        base_world,
        current_events=[transition],
        invalidations=queue,
        llm_call=interpreter,
    )

    assert interpreter.await_count == 1
    assert [event.event_type for event in events[:2]] == [
        "population_interpretation_decision",
        "population_transfer_completed",
    ]
    assert origin.population < 90
    assert destination.population > 40
    assert origin.population + destination.population == pytest.approx(total_before)
    assert events[1].causal_links[0].cause_event_id == events[0].id
    enqueue_population_transitions(base_world, [transition], queue)
    assert await process_population_reactivity(
        base_world,
        current_events=[*events, transition],
        invalidations=queue,
        llm_call=interpreter,
    ) == []
    assert interpreter.await_count == 1


@pytest.mark.asyncio
async def test_no_action_is_a_causal_decision_without_population_mutation(base_world):
    origin = _add_reactive_city(base_world, 302, 0.90, (1, 1))
    _add_reactive_city(base_world, 305, 0.40, (4, 4))
    transition = await _activate_pressure(base_world)
    queue = DomainInvalidationQueue()
    enqueue_population_transitions(base_world, [transition], queue)
    before = origin.population

    events = await process_population_reactivity(
        base_world,
        current_events=[transition],
        invalidations=queue,
        llm_call=AsyncMock(return_value={
            "decision": "maintain",
            "reason": "The pressure is tolerable for now.",
        }),
    )

    assert [event.event_type for event in events] == ["population_interpretation_decision"]
    assert events[0].causal_payload["decision"]["chosen_chain"] == []
    assert origin.population == before


@pytest.mark.asyncio
async def test_intent_can_be_blocked_when_no_destination_has_capacity(base_world):
    origin = _add_reactive_city(base_world, 302, 0.90, (1, 1))
    full = _add_reactive_city(base_world, 305, 1.0, (4, 4))
    transition = await _activate_pressure(base_world)
    base_world.run_config_snapshot = {
        "population_failed_transfer_retry_after_months": 6,
    }
    queue = DomainInvalidationQueue()
    enqueue_population_transitions(base_world, [transition], queue)
    before = (origin.population, full.population)

    events = await process_population_reactivity(
        base_world,
        current_events=[transition],
        invalidations=queue,
        llm_call=AsyncMock(return_value={
            "decision": "act",
            "reason": "Try to leave.",
            "action_intent": {
                "action_kind": "population_transfer",
                "preferences": ["available_capacity"],
            },
        }),
    )

    assert [event.event_type for event in events] == [
        "population_interpretation_decision",
        "population_transfer_blocked",
    ]
    assert (origin.population, full.population) == before
    receipt = next(iter(base_world.mechanical_language.reaction_receipts.values()))
    assert receipt.next_eligible_month == int(base_world.month_stamp) + 6
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    retry_queue = DomainInvalidationQueue()
    enqueue_unreacted_population_conditions(base_world, retry_queue)
    assert all(
        item.target_id != str(origin.id)
        for item in retry_queue.drain()
    )
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 5)
    enqueue_unreacted_population_conditions(base_world, retry_queue)
    assert any(
        item.target_id == str(origin.id)
        for item in retry_queue.drain()
    )


@pytest.mark.asyncio
async def test_partial_transfer_retries_next_month_while_condition_remains_active(base_world):
    _add_reactive_city(base_world, 302, 0.99, (1, 1))
    _add_reactive_city(base_world, 305, 0.84, (4, 4))
    transition = await _activate_pressure(base_world)
    queue = DomainInvalidationQueue()
    enqueue_population_transitions(base_world, [transition], queue)

    events = await process_population_reactivity(
        base_world,
        current_events=[transition],
        invalidations=queue,
        llm_call=AsyncMock(return_value={
            "decision": "act",
            "reason": "Use the available capacity.",
            "action_intent": {
                "action_kind": "population_transfer",
                "preferences": ["available_capacity"],
            },
        }),
    )

    transfer = next(
        event for event in events if event.event_type == "population_transfer_completed"
    )
    assert transfer.causal_payload["affordance"]["relief_complete"] is False
    receipt = next(iter(base_world.mechanical_language.reaction_receipts.values()))
    assert receipt.decision_event_ids
    assert receipt.next_eligible_month == int(base_world.month_stamp) + 1

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    retry_queue = DomainInvalidationQueue()
    enqueue_unreacted_population_conditions(base_world, retry_queue)
    assert len(retry_queue.drain()) == 1

    retry_queue = DomainInvalidationQueue()
    enqueue_unreacted_population_conditions(base_world, retry_queue)
    retry_events = await process_population_reactivity(
        base_world,
        current_events=[transition, *events],
        invalidations=retry_queue,
        llm_call=AsyncMock(return_value={
            "decision": "maintain",
            "reason": "No further move is warranted this month.",
        }),
    )
    assert [event.event_type for event in retry_events] == [
        "population_interpretation_decision"
    ]
    receipt = next(iter(base_world.mechanical_language.reaction_receipts.values()))
    assert len(receipt.decision_event_ids) == 2
    assert receipt.next_eligible_month is None
    assert receipt.completed is True


@pytest.mark.asyncio
async def test_llm_budget_zero_uses_rule_without_losing_the_transition(base_world):
    _add_reactive_city(base_world, 302, 0.90, (1, 1))
    _add_reactive_city(base_world, 305, 0.40, (4, 4))
    transition = await _activate_pressure(base_world)
    queue = DomainInvalidationQueue()
    enqueue_population_transitions(base_world, [transition], queue)
    base_world.run_config_snapshot = {"population_interpreter_llm_budget_per_month": 0}
    forbidden_llm = AsyncMock(side_effect=AssertionError("LLM budget is zero"))

    events = await process_population_reactivity(
        base_world,
        current_events=[transition],
        invalidations=queue,
        llm_call=forbidden_llm,
    )

    assert forbidden_llm.await_count == 0
    assert events[0].causal_payload["decision"]["source"] == "rule"
    assert events[1].event_type == "population_transfer_completed"
    assert queue.drain() == []


@pytest.mark.asyncio
async def test_population_reaction_budget_zero_performs_no_evaluations(base_world):
    _add_reactive_city(base_world, 302, 0.90, (1, 1))
    _add_reactive_city(base_world, 305, 0.40, (4, 4))
    transition = await _activate_pressure(base_world)
    queue = DomainInvalidationQueue()
    enqueue_population_transitions(base_world, [transition], queue)
    base_world.run_config_snapshot = {
        "test_mode": True,
        "population_reaction_evaluation_budget_per_month": 0,
    }
    interpreter = AsyncMock(side_effect=AssertionError("budget zero must skip evaluation"))

    events = await process_population_reactivity(
        base_world,
        current_events=[transition],
        invalidations=queue,
        llm_call=interpreter,
    )

    assert events == []
    assert interpreter.await_count == 0
    assert len(queue.drain()) == 1


@pytest.mark.asyncio
async def test_reaction_budget_stops_same_month_chain_and_unreacted_condition_is_retryable(base_world):
    _add_reactive_city(base_world, 302, 0.90, (1, 1))
    _add_reactive_city(base_world, 305, 0.91, (4, 4))
    discovery = AsyncMock(return_value=_proposal())
    await evaluate_semantic_world(base_world, llm_call=discovery)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    transitions = await evaluate_semantic_world(base_world, llm_call=discovery)
    first, second_event = transitions
    queue = DomainInvalidationQueue()
    enqueue_population_transitions(base_world, [first, second_event], queue)
    base_world.run_config_snapshot = {
        "population_reaction_evaluation_budget_per_month": 1,
        "population_interpreter_llm_budget_per_month": 0,
    }

    await process_population_reactivity(
        base_world,
        current_events=[first, second_event],
        invalidations=queue,
    )

    assert len(queue.drain()) == 1
    retry_queue = DomainInvalidationQueue()
    enqueue_unreacted_population_conditions(base_world, retry_queue)
    assert len(retry_queue.drain()) == 1


def test_only_grounded_settlement_pressure_transitions_enter_population_queue(base_world):
    queue = DomainInvalidationQueue()
    unrelated = CityRegion(
        id=302,
        name="City",
        desc="",
        cors=[(0, 0)],
        population=90,
        population_capacity=100,
    )
    base_world.map.regions[302] = unrelated

    enqueue_population_transitions(base_world, [], queue)

    assert queue.drain() == []


@pytest.mark.asyncio
async def test_monthly_smoke_uses_one_rule_decision_and_survives_save_load(
    base_world,
    tmp_path,
    monkeypatch,
):
    base_world.map = load_cultivation_world_map("classic")
    cities = [
        region
        for region in base_world.map.regions.values()
        if isinstance(region, CityRegion)
    ]
    for city in cities:
        city.population = city.population_capacity * 0.40
    origin = base_world.map.regions[302]
    destination = base_world.map.regions[305]
    origin.population = origin.population_capacity * 0.90
    provider = AsyncMock(side_effect=AssertionError("test mode must not call a real provider"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)
    base_world.run_config_snapshot = {
        "content_locale": "zh-CN",
        "map_id": "classic",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.01,
        "world_lore": "",
        "test_mode": True,
        "population_interpreter_llm_budget_per_month": 2,
        "population_transfer_max_fraction_per_reaction": 0.20,
    }
    simulator = Simulator(base_world)

    with llm_test_mode_scope(True):
        await simulator.step()
        events = await simulator.step()

    assert provider.await_count == 0
    assert [event.event_type for event in events].count("population_interpretation_decision") == 1
    transfer = next(event for event in events if event.event_type == "population_transfer_completed")
    assert origin.population < origin.population_capacity * 0.90
    assert destination.population > destination.population_capacity * 0.40
    decision_id = transfer.causal_links[0].cause_event_id
    decision = base_world.event_manager.get_event_by_id(decision_id)
    assert decision is not None
    assert decision.causal_links[0].cause_event_id in {
        event.id for event in events if event.event_type == "semantic_condition_activated"
    }

    save_path = tmp_path / "population-reactivity.json"
    ok, message = save_game(base_world, simulator, events, save_path=save_path)
    assert ok, message
    loaded_world, loaded_simulator, _ = load_game(save_path)

    loaded_origin = loaded_world.map.regions[302]
    loaded_destination = loaded_world.map.regions[305]
    assert loaded_origin.population == pytest.approx(origin.population)
    assert loaded_destination.population == pytest.approx(destination.population)
    loaded_receipt = next(
        receipt
        for receipt in loaded_world.mechanical_language.reaction_receipts.values()
        if receipt.domain == "population"
    )
    assert loaded_receipt.decision_event_ids == (decision_id,)
    loaded_transfer = loaded_world.event_manager.get_event_by_id(transfer.id)
    assert loaded_transfer is not None
    loaded_links = loaded_world.event_manager.get_causal_links_for_event(transfer.id)
    assert loaded_links[0].cause_event_id == decision_id
    loaded_decision = loaded_world.event_manager.get_event_by_id(decision_id)
    assert loaded_decision is not None
    assert loaded_decision.causal_payload["decision"]["subject_kind"] == "population"

    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime.set_world_and_sim(loaded_world, None)
    detail = get_event_causal_detail(
        runtime,
        serialize_events_for_client=lambda items, **kwargs: serialize_events_for_client(
            items,
            world=loaded_world,
        ),
        event_id=transfer.id,
    )
    assert detail["decision"]["subject_kind"] == "population"
    assert {edge["relation"] for edge in detail["causes"]} >= {
        "motivated_by",
        "response_to",
    }
    assert detail["measurements"]
    assert all(isinstance(reading["key"], dict) for reading in detail["measurements"])

    capacity_before_project = loaded_origin.population_capacity
    project = loaded_origin.city_state.capacity_projects[0]
    future_events = []
    with llm_test_mode_scope(True):
        for _ in range(project.required_months):
            future_events.extend(await loaded_simulator.step())

    completion = next(
        event
        for event in future_events
        if event.event_type == "urban_capacity_project_completed"
        and event.render_params["region_id"] == str(loaded_origin.id)
    )
    project_progress = [
        event
        for event in future_events
        if event.event_type == "urban_capacity_project_progressed"
        and event.render_params["region_id"] == str(loaded_origin.id)
    ]
    assert project_progress
    for progress in project_progress:
        progress_aspects = {
            delta["aspect"] for delta in progress.causal_payload["deltas"]
        }
        assert {
            f"resource_stock:{project.construction_resource_id}",
            f"resource_reservation:{project.id}:{project.construction_resource_id}",
            "urban_capacity_project_material",
        }.issubset(progress_aspects)
    assert loaded_origin.population_capacity == pytest.approx(
        capacity_before_project + project.capacity_increase
    )
    project_why = get_event_causal_detail(
        runtime,
        serialize_events_for_client=lambda items, **kwargs: serialize_events_for_client(
            items,
            world=loaded_world,
        ),
        event_id=completion.id,
    )
    project_ancestor_types = {
        loaded_world.event_manager.get_event_by_id(edge["event"]["id"]).event_type
        for edge in project_why["causes"]
        if edge["event"] is not None
    }
    assert {
        "urban_capacity_project_progressed",
        "urban_capacity_project_started",
        "city_interpretation_decision",
        "semantic_condition_activated",
    }.issubset(project_ancestor_types)
    progress_why = get_event_causal_detail(
        runtime,
        serialize_events_for_client=lambda items, **kwargs: serialize_events_for_client(
            items,
            world=loaded_world,
        ),
        event_id=project_progress[0].id,
    )
    assert {
        f"resource_stock:{project.construction_resource_id}",
        f"resource_reservation:{project.id}:{project.construction_resource_id}",
        "urban_capacity_project_material",
    }.issubset({delta["aspect"] for delta in progress_why["deltas"]})

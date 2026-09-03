from unittest.mock import AsyncMock

import pytest

from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.event import Event
from src.classes.regional_economy import InfrastructureState, RegionalEconomyState
from src.systems.economy_interpreter import interpret_resource_shortage
from src.utils.llm.runtime_mode import llm_test_mode_scope
from src.utils.llm.test_mode_fallbacks import registered_test_mode_tasks, resolve_test_mode_task


def _city(world, region_id: int, *, stock: float, demand: float) -> CityRegion:
    city = CityRegion(
        id=region_id,
        name=f"City {region_id}",
        desc="",
        cors=[(region_id % 10, region_id // 10)],
        economy=RegionalEconomyState(
            stocks={"grain": stock},
            capacities={"grain": 20},
            demand_rates={"grain": demand},
            access={"grain": 0.8},
        ),
        infrastructure=InfrastructureState(capacities={"transport": 4}),
    )
    world.map.regions[region_id] = city
    return city


def _shortage(world, city: CityRegion) -> Event:
    return Event(
        world.month_stamp,
        "Grain is scarce.",
        event_type="regional_resource_shortage",
        render_params={
            "region_id": str(city.id),
            "resource_id": "grain",
            "demand": 3.0,
            "available": 0.0,
        },
    )


def test_economy_fallback_is_registered_and_requires_a_grounded_route():
    assert "economy_interpreter" in registered_test_mode_tasks()
    result = resolve_test_mode_task(
        "economy_interpreter",
        {
            "destination": {"access": 0.8},
            "candidates": [{"stock": 12, "source_access": 0.9, "route": {"available": False}}],
        },
    )
    assert result["decision"] == "maintain"


@pytest.mark.asyncio
async def test_economy_interpreter_returns_typed_intent_without_engine_fields(base_world):
    destination = _city(base_world, 302, stock=0, demand=3)
    event = _shortage(base_world, destination)
    interpreter = AsyncMock(return_value={
        "decision": "act",
        "reason": "A canonical route may supply the shortage.",
        "action_intent": {
            "action_kind": "resource_transfer",
            "preferences": ["available_supply", "higher_route_quality"],
        },
    })

    decision, decision_event = await interpret_resource_shortage(
        base_world,
        event,
        llm_call=interpreter,
    )

    assert interpreter.await_count == 1
    assert decision.action_intent is not None
    assert decision.action_intent.resource_id == "grain"
    assert "destination" not in decision.action_intent.to_dict()
    assert "amount" not in decision.action_intent.to_dict()
    assert decision_event.event_type == "economy_interpretation_decision"
    assert decision_event.causal_links[0].cause_event_id == event.id


@pytest.mark.asyncio
async def test_test_mode_never_calls_provider_and_maintains_without_route(base_world):
    destination = _city(base_world, 302, stock=0, demand=3)
    event = _shortage(base_world, destination)
    provider = AsyncMock(side_effect=AssertionError("provider must not run in test mode"))

    with llm_test_mode_scope(True):
        decision, decision_event = await interpret_resource_shortage(
            base_world,
            event,
            llm_call=provider,
        )

    assert provider.await_count == 0
    assert decision.decision.value == "maintain"
    assert decision_event.causal_payload["decision"]["source"] == "rule"


@pytest.mark.asyncio
async def test_economy_context_reports_available_stock_not_reserved_stock(base_world):
    source = _city(base_world, 301, stock=12, demand=0)
    destination = _city(base_world, 302, stock=0, demand=3)
    source.economy.reserve_stock("commercial-order", "grain", 12.0)
    base_world.map.set_routes([
        Route("reserved-route", (301, 302), "road", 10, 1.0, True),
    ])
    event = _shortage(base_world, destination)
    interpreter = AsyncMock(return_value={
        "decision": "maintain",
        "reason": "No available supply is grounded.",
    })

    await interpret_resource_shortage(base_world, event, llm_call=interpreter)

    context = interpreter.await_args.args[2]
    candidate = next(item for item in context["candidates"] if item["id"] == "301")
    assert candidate["stock"] == 0.0


@pytest.mark.asyncio
async def test_economy_context_preserves_unknown_stock(base_world):
    destination = _city(base_world, 302, stock=0, demand=3)
    unknown_source = CityRegion(
        id=301,
        name="Unknown source",
        desc="",
        cors=[(1, 1)],
        infrastructure=InfrastructureState(capacities={"transport": 4}),
    )
    base_world.map.regions[301] = unknown_source
    base_world.map.set_routes([
        Route("unknown-route", (301, 302), "road", 10, 1.0, True),
    ])
    event = _shortage(base_world, destination)
    interpreter = AsyncMock(return_value={
        "decision": "maintain",
        "reason": "The source stock is unknown.",
    })

    await interpret_resource_shortage(base_world, event, llm_call=interpreter)

    context = interpreter.await_args.args[2]
    candidate = next(item for item in context["candidates"] if item["id"] == "301")
    assert candidate["stock"] is None

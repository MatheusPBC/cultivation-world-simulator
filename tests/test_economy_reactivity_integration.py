from unittest.mock import AsyncMock

import pytest

from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.event import Event
from src.classes.regional_economy import InfrastructureState, RegionalEconomyState
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.economy_reactivity import process_economy_reactivity
from src.utils.llm.runtime_mode import llm_test_mode_scope


def _city(world, region_id: int, stock: float, demand: float) -> CityRegion:
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
        infrastructure=InfrastructureState(capacities={"transport": 5}),
    )
    world.map.regions[region_id] = city
    return city


def _shortage(world, city: CityRegion) -> Event:
    return Event(
        world.month_stamp,
        "Grain is scarce.",
        event_type="regional_resource_shortage",
        render_params={"region_id": str(city.id), "resource_id": "grain"},
    )


@pytest.mark.asyncio
async def test_economy_reactivity_executes_only_explicit_route_and_marks_both_regions_dirty(base_world):
    source = _city(base_world, 302, 12, 0)
    destination = _city(base_world, 305, 0, 3)
    base_world.map.set_routes([
        Route("route-17", (302, 305), "road", 2, 1.0, True),
    ])
    shortage = _shortage(base_world, destination)
    interpreter = AsyncMock(return_value={
        "decision": "act",
        "reason": "The explicit route can carry grain.",
        "action_intent": {
            "action_kind": "resource_transfer",
            "preferences": ["available_supply"],
        },
    })
    invalidations = DomainInvalidationQueue()

    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=invalidations,
        llm_call=interpreter,
    )

    assert [event.event_type for event in events] == [
        "economy_interpretation_decision",
        "regional_resource_transfer_completed",
    ]
    assert source.economy.stocks["grain"] == 10
    assert destination.economy.stocks["grain"] == 2
    dirty = invalidations.drain()
    assert {item.target_id for item in dirty} == {"302", "305"}


@pytest.mark.asyncio
async def test_economy_reactivity_records_grounded_block_when_route_is_absent(base_world):
    source = _city(base_world, 302, 12, 0)
    destination = _city(base_world, 305, 0, 3)
    shortage = _shortage(base_world, destination)
    interpreter = AsyncMock(return_value={
        "decision": "act",
        "reason": "Attempt the supply action.",
        "action_intent": {
            "action_kind": "resource_transfer",
            "preferences": ["available_supply"],
        },
    })

    with llm_test_mode_scope(False):
        events = await process_economy_reactivity(
            base_world,
            current_events=[shortage],
            invalidations=DomainInvalidationQueue(),
            llm_call=interpreter,
        )

    blocked = events[-1]
    assert blocked.event_type == "regional_resource_transfer_blocked"
    assert blocked.render_params["reason"] == "route_unknown"
    assert source.economy.stocks["grain"] == 12


@pytest.mark.asyncio
async def test_economy_reaction_budget_zero_performs_no_evaluations(base_world):
    destination = _city(base_world, 305, stock=0, demand=3)
    shortage = _shortage(base_world, destination)
    interpreter = AsyncMock(side_effect=AssertionError("budget zero must skip evaluation"))

    base_world.run_config_snapshot = {
        "test_mode": True,
        "economy_reaction_evaluation_budget_per_month": 0,
    }
    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=interpreter,
    )

    assert events == []
    assert interpreter.await_count == 0

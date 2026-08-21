"""Task 6: bounded multi-month smoke test, and event-volume / `why`-cost
measurements called for by docs/superpowers/plans/2026-08-20-causal-world-kernel.md
Task 6 ("Run ... a bounded multi-month simulation smoke test. Measure event
volume and bounded `why` query cost.").

This intentionally does not re-prove per-endpoint correctness (depth clamp,
node-limit truncation, cycle protection, decision resolution are already
exhaustively covered by tests/test_event_causal_query_api.py from Task 5).
It only checks that running several months in a row is stable and that a
deep causal chain stays cheap to traverse.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import NULL_EVENT, Event, FactKind
from src.server.runtime import DEFAULT_GAME_STATE, GameSessionRuntime
from src.server.services.game_queries import get_event_causal_detail
from src.server.serialization import serialize_events_for_client
from src.sim.simulator import Simulator
from src.systems.time import Month, Year, create_month_stamp


@pytest.mark.asyncio
async def test_bounded_multi_month_smoke_with_real_decisions(base_world, mock_llm_managers):
    """Run a handful of months back-to-back with a small population where
    every avatar actually decides a (non-empty) action each month it is
    idle, so `FactKind.DECISION` events and their downstream action events
    are genuinely produced -- an earlier version of this test used the
    default mocked "empty decision" and measured a world where nothing
    happens, which proved nothing about causal-kernel event volume."""
    avatars = [_make_avatar(base_world, f"smoke-{i}", pos_x=i, pos_y=i) for i in range(3)]
    for avatar in avatars:
        base_world.avatar_manager.register_avatar(avatar)

    async def _decide(_world, avatars_to_decide):
        return {
            avatar: (
                [("MoveToDirection", {"direction": "East"})],
                "heading east",
                "explore the world",
                NULL_EVENT,
            )
            for avatar in avatars_to_decide
        }

    mock_llm_managers["ai"].decide = AsyncMock(side_effect=_decide)

    sim = Simulator(base_world)
    months_to_run = 6
    start_month = int(base_world.month_stamp)
    total_events = 0
    decision_events = 0

    for _ in range(months_to_run):
        events = await sim.step()
        total_events += len(events)
        decision_events += sum(1 for e in events if e.fact_kind == FactKind.DECISION)

    assert int(base_world.month_stamp) == start_month + months_to_run
    # Every avatar starts idle and `MoveToDirection` takes 6 months, so each
    # of the 3 avatars decides exactly once across this run -- the decision
    # event count must reflect that real activity, not be zero.
    assert decision_events == len(avatars), (
        f"expected exactly {len(avatars)} decision events (one per avatar "
        f"deciding once), got {decision_events}"
    )
    assert total_events > 0
    # No hard ceiling is prescribed by the spec; this only guards against a
    # gross blow-up (e.g. an accidental per-tile or per-pair event emission).
    assert total_events < 500, f"unexpectedly high event volume for {months_to_run} months: {total_events}"


def test_why_query_stays_cheap_on_a_moderately_deep_chain(base_world):
    """Build a 60-hop linear causal chain (well past the depth=5 clamp) and
    confirm the bounded traversal stays fast. The bound (2s) is generous on
    purpose -- this is a regression guard against an unbounded walk, not a
    tight performance budget."""
    events = _build_chain(base_world, 60)

    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime.set_world_and_sim(base_world, None)

    started = time.perf_counter()
    result = get_event_causal_detail(
        runtime,
        serialize_events_for_client=lambda evs, **kwargs: serialize_events_for_client(evs, world=base_world),
        event_id=events[-1].id,
    )
    elapsed = time.perf_counter() - started

    assert result["truncated"] is True
    assert elapsed < 2.0, f"why query took too long on a deep chain: {elapsed:.3f}s"


def _build_chain(world, length: int) -> list[Event]:
    events = [
        Event(month_stamp=create_month_stamp(Year(100), Month((i % 12) + 1)), content=f"e{i}")
        for i in range(length)
    ]
    for i in range(1, length):
        events[i].causal_links = [
            CausalLink(event_id=events[i].id, cause_event_id=events[i - 1].id, relation=CausalRelation.TRIGGERED_BY)
        ]
    for event in events:
        world.event_manager.add_event(event)
    return events


def _make_avatar(world, name: str, *, pos_x: int, pos_y: int):
    from src.classes.age import Age
    from src.classes.core.avatar import Avatar, Gender
    from src.classes.alignment import Alignment
    from src.classes.root import Root
    from src.systems.cultivation import Realm
    from unittest.mock import MagicMock

    avatar = Avatar(
        world=world,
        name=name,
        id=name,
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement, innate_max_lifespan=80),
        gender=Gender.MALE,
        pos_x=pos_x,
        pos_y=pos_y,
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )
    avatar.weapon = MagicMock()
    avatar.weapon.get_detailed_info.return_value = ""
    avatar.weapon_proficiency = 0.0
    avatar.personas = []
    avatar.technique = None
    avatar.recalc_effects()
    return avatar

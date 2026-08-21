"""Task 6 residue fixes from docs/specs/causal-world-kernel.md section 6.4.

Region claiming (`avatar.occupy_region`) used to run inside
`phase_update_perception_and_knowledge`, before `phase_decide_actions`. That
made it a non-idempotent, irreversible mutation sitting before the point
where a required-decision failure can abort the month -- a retried month
could claim the same region twice, or claim it for the wrong avatar after
a partial, discarded run. It is now split into its own phase and moved
after `decide_actions`, alongside `process_gatherings`.

`long_term_objective_thinking` has the same hazard and was moved for the
same reason during re-review: `process_avatar_long_term_objective` writes a
real `avatar.long_term_objective` (replacing any existing one), and
`can_generate_long_term_objective` treats "years since it was last set" as
the guard -- so a version set during a failed, discarded step is never
regenerated on the retry (`years_passed < 5`), even though its describing
`Event` was thrown away with the rest of that failed batch.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.classes.environment.region import CultivateRegion, EssenceType
from src.sim.simulator import Simulator
from src.sim.simulator_engine.phase_registry import get_simulation_phases
from src.sim.simulator_engine.phases.world import (
    phase_claim_ownerless_regions,
    phase_update_perception_and_knowledge,
)
from src.sim.simulator_engine.phases.actions import RequiredDecisionFailed
from src.utils.llm.exceptions import LLMError


def _phase_index(name: str) -> int:
    for phase in get_simulation_phases():
        if phase.name == name:
            return phase.index
    raise AssertionError(f"phase {name!r} not registered")


def test_decide_actions_runs_before_region_claiming_and_gatherings():
    decide_index = _phase_index("decide_actions")
    claim_index = _phase_index("claim_ownerless_regions")
    gatherings_index = _phase_index("process_gatherings")
    commit_index = _phase_index("commit_next_plans")

    assert decide_index < claim_index < commit_index
    assert decide_index < gatherings_index < commit_index


def test_decide_actions_runs_before_long_term_objective_thinking():
    decide_index = _phase_index("decide_actions")
    lto_index = _phase_index("long_term_objective_thinking")
    commit_index = _phase_index("commit_next_plans")

    assert decide_index < lto_index < commit_index


@pytest.mark.asyncio
async def test_required_decision_failure_leaves_long_term_objective_unset(
    base_world, dummy_avatar, mock_llm_managers
):
    """The actual residue scenario: with `long_term_objective_thinking`
    registered after `decide_actions`, a required-decision failure must
    abort the step before that phase ever runs, so no `long_term_objective`
    is silently written for an event batch that gets discarded.

    The `lto` mock is given a real side effect here (it normally just
    returns `None` and would make this pass trivially regardless of phase
    order) so this test actually fails if `long_term_objective_thinking`
    were moved back ahead of `decide_actions`."""
    from src.classes.event import Event
    from src.classes.long_term_objective import LongTermObjective

    base_world.avatar_manager.register_avatar(dummy_avatar)
    assert dummy_avatar.long_term_objective is None

    async def _set_long_term_objective(avatar):
        avatar.long_term_objective = LongTermObjective(
            content="become immortal", origin="llm", set_year=int(base_world.month_stamp.get_year())
        )
        return Event(base_world.month_stamp, "objective set")

    mock_llm_managers["lto"].side_effect = _set_long_term_objective
    mock_llm_managers["ai"].decide = AsyncMock(side_effect=LLMError("boom"))

    sim = Simulator(base_world)
    with pytest.raises(RequiredDecisionFailed):
        await sim.step()

    assert dummy_avatar.long_term_objective is None


def test_perception_phase_no_longer_claims_regions(base_world, dummy_avatar):
    region = CultivateRegion(
        id=2001,
        name="Unclaimed Cave",
        desc="test",
        essence_type=EssenceType.GOLD,
        essence_density=10,
    )
    base_world.map.regions[region.id] = region
    base_world.map.get_tile(dummy_avatar.pos_x, dummy_avatar.pos_y).region = region
    base_world.avatar_manager.register_avatar(dummy_avatar)

    events = phase_update_perception_and_knowledge(base_world, [dummy_avatar])

    assert events == []
    assert region.host_avatar is None
    assert region.id in dummy_avatar.known_regions


def test_claim_ownerless_regions_occupies_and_emits_event(base_world, dummy_avatar):
    region = CultivateRegion(
        id=2002,
        name="Unclaimed Cave",
        desc="test",
        essence_type=EssenceType.GOLD,
        essence_density=10,
    )
    base_world.map.regions[region.id] = region
    base_world.map.get_tile(dummy_avatar.pos_x, dummy_avatar.pos_y).region = region
    base_world.avatar_manager.register_avatar(dummy_avatar)

    events = phase_claim_ownerless_regions(base_world, [dummy_avatar])

    assert len(events) == 1
    assert region.host_avatar is dummy_avatar


def test_claim_ownerless_regions_is_safe_to_rerun_within_the_same_month(base_world, dummy_avatar):
    """This is the actual retry scenario: a required-decision failure aborts
    the month right after `decide_actions`, and the month is re-run from the
    first phase. Region claiming, now positioned after `decide_actions`,
    must not double-claim or emit a second event on that re-run."""
    region = CultivateRegion(
        id=2003,
        name="Unclaimed Cave",
        desc="test",
        essence_type=EssenceType.GOLD,
        essence_density=10,
    )
    base_world.map.regions[region.id] = region
    base_world.map.get_tile(dummy_avatar.pos_x, dummy_avatar.pos_y).region = region
    base_world.avatar_manager.register_avatar(dummy_avatar)

    first_events = phase_claim_ownerless_regions(base_world, [dummy_avatar])
    second_events = phase_claim_ownerless_regions(base_world, [dummy_avatar])

    assert len(first_events) == 1
    assert second_events == []
    assert region.host_avatar is dummy_avatar
    assert dummy_avatar.owned_regions.count(region) == 1

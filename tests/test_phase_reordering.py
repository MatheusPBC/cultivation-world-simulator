"""Causal phase ordering and the absence of autonomous territorial claims."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.classes.environment.region import CultivateRegion, EssenceType
from src.sim.simulator import Simulator
from src.sim.simulator_engine.phase_registry import get_simulation_phases
from src.sim.simulator_engine.phases.world import (
    phase_update_perception_and_knowledge,
)
from src.sim.simulator_engine.phases.actions import RequiredDecisionFailed
from src.utils.llm.exceptions import LLMError


def _phase_index(name: str) -> int:
    for phase in get_simulation_phases():
        if phase.name == name:
            return phase.index
    raise AssertionError(f"phase {name!r} not registered")


def test_no_autonomous_region_claim_phase_and_gatherings_follow_decision():
    decide_index = _phase_index("decide_actions")
    gatherings_index = _phase_index("process_gatherings")
    commit_index = _phase_index("commit_next_plans")

    assert "claim_ownerless_regions" not in {
        phase.name for phase in get_simulation_phases()
    }
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

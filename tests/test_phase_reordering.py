"""Task 6 residue fixes from docs/specs/causal-world-kernel.md section 6.4.

Region claiming (`avatar.occupy_region`) used to run inside
`phase_update_perception_and_knowledge`, before `phase_decide_actions`. That
made it a non-idempotent, irreversible mutation sitting before the point
where a required-decision failure can abort the month -- a retried month
could claim the same region twice, or claim it for the wrong avatar after
a partial, discarded run. It is now split into its own phase and moved
after `decide_actions`, alongside `process_gatherings`.
"""
from __future__ import annotations

import pytest

from src.classes.environment.region import CultivateRegion, EssenceType
from src.sim.simulator_engine.phase_registry import get_simulation_phases
from src.sim.simulator_engine.phases.world import (
    phase_claim_ownerless_regions,
    phase_update_perception_and_knowledge,
)


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
    the month after phase 4, and the month is re-run from phase 1. Region
    claiming, now positioned after phase 4, must not double-claim or emit a
    second event on that re-run."""
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

"""Fixed institutional prehistory that runs before the playable month.

V1 is deliberately not a simulation of the world's past life.  It runs a fixed,
short window over the institutional subset of the canonical phases so the
playable January starts with real institutional history instead of an empty
one: regional economy is updated, economy reactivity offers the existing aid
affordances, late mechanical evidence is persisted, and the canonical
finalizer commits the month.  No avatar action, birth, death, war, climate or
narration runs here, and nothing forces resources, pressure, or a positive
decision -- a prehistory where every institution stays quiet is a valid world.
"""

from __future__ import annotations

from typing import Any

from src.classes.event import Event
from src.systems.time import MonthStamp
from src.utils.llm.runtime_mode import is_world_test_mode, llm_test_mode_scope

from .phase_registry import SimulationPhase, get_simulation_phases
from .phase_runner import SimulationPhaseRunner


PREHISTORY_MONTHS = 3

# A filter over SIMULATION_PHASES, never a hand-written list: the canonical
# registry stays the only source of phase identity and order.
PREHISTORY_PHASE_NAMES = (
    "update_regional_economy",
    "react_economy",
    "carry_forward_mechanical_invalidations",
    "finalize_step",
)


class PrehistoryError(RuntimeError):
    """The prehistory window could not be produced exactly as specified."""


def prehistory_phases() -> tuple[SimulationPhase, ...]:
    """Select the institutional phases, keeping the canonical relative order."""
    wanted = set(PREHISTORY_PHASE_NAMES)
    selected = tuple(
        phase for phase in get_simulation_phases() if phase.name in wanted
    )
    if tuple(phase.name for phase in selected) != PREHISTORY_PHASE_NAMES:
        raise PrehistoryError(
            "institutional prehistory phases are missing or reordered in the "
            "canonical phase registry"
        )
    return selected


def prehistory_month_count(playable_start_month: int) -> int:
    """Three months, clamped to the calendar that exists before play.

    A world whose playable January is year 0 has no earlier calendar, and zero
    prehistory months is a legitimate outcome rather than an error.
    """
    return max(0, min(PREHISTORY_MONTHS, int(playable_start_month)))


def genesis_month_stamp(playable_start_month: int) -> MonthStamp:
    """The month the world is constructed in, before any event exists."""
    return MonthStamp(
        int(playable_start_month) - prehistory_month_count(playable_start_month)
    )


async def run_institutional_prehistory(
    simulator: Any,
    *,
    playable_start_month: int,
) -> list[Event]:
    """Advance the world month by month up to, and only up to, playable start."""
    world = simulator.world
    playable = int(playable_start_month)
    expected_genesis = int(genesis_month_stamp(playable))
    if int(world.month_stamp) != expected_genesis:
        raise PrehistoryError(
            f"prehistory must begin at month {expected_genesis}, "
            f"world is at {int(world.month_stamp)}"
        )

    phases = prehistory_phases()
    events: list[Event] = []
    while int(world.month_stamp) < playable:
        month = int(world.month_stamp)
        # Each month gets its own CausalBudget and test-mode isolation, exactly
        # like a normal step, because the budget lives in the step context.
        if is_world_test_mode(world):
            with llm_test_mode_scope(True):
                month_events = await SimulationPhaseRunner(simulator, phases).run()
        else:
            month_events = await SimulationPhaseRunner(simulator, phases).run()
        if int(world.month_stamp) != month + 1:
            # A cancelled or non-advancing month must stop the window instead of
            # looping forever against an unchanged cursor.
            raise PrehistoryError(
                f"prehistory month {month} did not advance the world clock"
            )
        events.extend(month_events)
    return events


__all__ = [
    "PREHISTORY_MONTHS",
    "PREHISTORY_PHASE_NAMES",
    "PrehistoryError",
    "genesis_month_stamp",
    "prehistory_month_count",
    "prehistory_phases",
    "run_institutional_prehistory",
]

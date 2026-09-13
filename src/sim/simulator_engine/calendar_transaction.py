from collections.abc import Callable
from typing import Any

from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint
from src.systems.calendar_agenda import ScheduledSituation
from src.systems.calendar_scheduler import CalendarJump, CalendarScheduler


class CalendarAdvanceTransaction:
    """Apply a jump with in-memory rollback; callbacks must not commit external IO."""

    def __init__(self, world: Any):
        self.world = world

    def advance(
        self,
        *,
        resolve_situations: Callable[[tuple[ScheduledSituation, ...]], None] | None = None,
        run_monthly: Callable[[], None] | None = None,
    ) -> CalendarJump:
        """Advance to the next agenda deadline or monthly boundary.

        When both are due on the target day, the dated situations resolve
        before the monthly aggregation. Any exception restores the complete
        canonical world graph through the existing simulation checkpoint.
        """
        due_days = self.world.agenda.due_days
        if any(day <= self.world.clock.absolute_day for day in due_days):
            raise ValueError("Resolve pending current/past situations before advancing")
        jump = CalendarScheduler.next_jump(self.world.clock, due_days)
        if jump.agenda_due and resolve_situations is None:
            raise ValueError("An active situation requires a resolver")
        checkpoint = SimulationMonthCheckpoint.capture(self.world)
        try:
            self.world.clock = self.world.clock.advance(jump.elapsed_days)

            if jump.agenda_due:
                situations = self.world.agenda.pop_due(jump.to_day)
                if resolve_situations is not None:
                    resolve_situations(situations)

            if jump.monthly_boundary and run_monthly is not None:
                run_monthly()

            return jump
        except BaseException:
            checkpoint.restore()
            raise

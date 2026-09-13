from collections.abc import Iterable
from dataclasses import dataclass

from src.systems.time import WorldClock


@dataclass(frozen=True, slots=True)
class CalendarJump:
    """The next simulation interval and the work due at its end."""

    from_day: int
    to_day: int
    monthly_boundary: bool
    agenda_due: bool

    @property
    def elapsed_days(self) -> int:
        return self.to_day - self.from_day


class CalendarScheduler:
    """Choose between the next monthly boundary and active-situation deadlines."""

    @staticmethod
    def next_jump(clock: WorldClock, due_days: Iterable[int]) -> CalendarJump:
        """Return the earliest future boundary or agenda deadline.

        Entries on the current day are intentionally excluded: the caller must
        resolve them before asking for another jump, avoiding zero-day loops.
        """
        future_due_days: list[int] = []
        for due_day in due_days:
            if isinstance(due_day, bool) or not isinstance(due_day, int):
                raise TypeError("due_days must contain integers")
            if due_day > clock.absolute_day:
                future_due_days.append(due_day)

        next_month_day = (
            (clock.absolute_day // WorldClock.DAYS_PER_MONTH) + 1
        ) * WorldClock.DAYS_PER_MONTH
        next_agenda_day = min(future_due_days, default=None)
        target_day = min(next_month_day, next_agenda_day) if next_agenda_day else next_month_day

        return CalendarJump(
            from_day=clock.absolute_day,
            to_day=target_day,
            monthly_boundary=target_day == next_month_day,
            agenda_due=target_day == next_agenda_day,
        )

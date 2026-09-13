import pytest
import random

from src.sim.simulator_engine.calendar_transaction import CalendarAdvanceTransaction
from src.systems.calendar_agenda import ScheduledSituation
from src.systems.time import WorldClock


def test_calendar_transaction_advances_to_due_situation_and_consumes_it(base_world):
    """A travel deadline advances the clock and leaves no duplicate future work."""
    base_world.clock = WorldClock(4)
    base_world.agenda.schedule(ScheduledSituation("caravan:1", "travel", 8))
    resolved = []

    jump = CalendarAdvanceTransaction(base_world).advance(
        resolve_situations=lambda situations: resolved.extend(situations)
    )

    assert jump.to_day == 8
    assert base_world.clock == WorldClock(8)
    assert resolved == [ScheduledSituation("caravan:1", "travel", 8)]
    assert base_world.agenda.due_days == ()


def test_calendar_transaction_rolls_back_clock_and_agenda_when_resolution_fails(base_world):
    """A failed ritual cannot consume its deadline or leave the world on day 8."""
    base_world.clock = WorldClock(4)
    ritual = ScheduledSituation("ritual:1", "ritual", 8)
    base_world.agenda.schedule(ritual)

    def fail(_situations):
        raise RuntimeError("ritual resolution failed")

    with pytest.raises(RuntimeError, match="ritual resolution failed"):
        CalendarAdvanceTransaction(base_world).advance(resolve_situations=fail)

    assert base_world.clock == WorldClock(4)
    assert base_world.agenda.get("ritual:1") == ritual


def test_calendar_transaction_runs_monthly_work_only_on_month_boundary(base_world):
    """Stable worlds aggregate monthly work once at the next calendar boundary."""
    base_world.clock = WorldClock(4)
    monthly_runs = []

    jump = CalendarAdvanceTransaction(base_world).advance(
        run_monthly=lambda: monthly_runs.append(base_world.clock.absolute_day)
    )

    assert jump.to_day == 30
    assert base_world.clock == WorldClock(30)
    assert monthly_runs == [30]


def test_missing_resolver_must_not_discard_an_active_situation(base_world):
    base_world.agenda.schedule(ScheduledSituation("caravan:1", "travel", 8))
    with pytest.raises(ValueError, match="resolver"):
        CalendarAdvanceTransaction(base_world).advance()
    assert base_world.clock.absolute_day == 0
    assert base_world.agenda.get("caravan:1") is not None


def test_overdue_work_must_not_be_silently_skipped(base_world):
    base_world.clock = WorldClock(8)
    base_world.agenda.schedule(ScheduledSituation("caravan:1", "travel", 8))
    with pytest.raises(ValueError, match="pending"):
        CalendarAdvanceTransaction(base_world).advance()
    assert base_world.clock.absolute_day == 8


def test_failed_month_boundary_restores_resolved_work_and_randomness(base_world):
    base_world.clock = WorldClock(28)
    base_world.agenda.schedule(ScheduledSituation("caravan:1", "travel", 30))
    agenda = base_world.agenda
    before_random = random.getstate()
    order = []

    def resolve(_situations):
        order.append("travel")
        base_world.start_year = 500
        base_world.agenda.schedule(ScheduledSituation("caravan:2", "travel", 40))
        random.random()

    def monthly():
        order.append("month")
        raise RuntimeError("monthly failure")

    before_year = base_world.start_year
    with pytest.raises(RuntimeError, match="monthly failure"):
        CalendarAdvanceTransaction(base_world).advance(
            resolve_situations=resolve, run_monthly=monthly
        )
    assert order == ["travel", "month"]
    assert base_world.clock.absolute_day == 28
    assert base_world.agenda is agenda
    assert base_world.agenda.due_days == (30,)
    assert base_world.start_year == before_year
    assert random.getstate() == before_random

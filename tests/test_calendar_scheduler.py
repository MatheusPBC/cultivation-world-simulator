from src.systems.calendar_scheduler import CalendarJump, CalendarScheduler
from src.systems.time import WorldClock


def test_scheduler_skips_directly_to_next_month_when_no_situation_is_active():
    """An empty agenda must not force thirty daily simulation ticks."""
    jump = CalendarScheduler.next_jump(WorldClock(4), ())

    assert jump == CalendarJump(
        from_day=4,
        to_day=30,
        monthly_boundary=True,
        agenda_due=False,
    )
    assert jump.elapsed_days == 26


def test_scheduler_stops_on_the_nearest_active_situation_before_month_end():
    """A deadline on day 8 takes precedence over the month boundary on day 30."""
    jump = CalendarScheduler.next_jump(WorldClock(4), (8, 17))

    assert jump == CalendarJump(
        from_day=4,
        to_day=8,
        monthly_boundary=False,
        agenda_due=True,
    )
    assert jump.elapsed_days == 4


def test_scheduler_marks_both_causes_when_a_situation_hits_the_month_boundary():
    """The monthly economy and the active situation must both run on day 30."""
    jump = CalendarScheduler.next_jump(WorldClock(29), (30,))

    assert jump == CalendarJump(
        from_day=29,
        to_day=30,
        monthly_boundary=True,
        agenda_due=True,
    )


def test_scheduler_ignores_situations_already_processed_at_the_current_day():
    """Past/current agenda entries cannot create a zero-day simulation loop."""
    jump = CalendarScheduler.next_jump(WorldClock(30), (29, 30, 61))

    assert jump == CalendarJump(
        from_day=30,
        to_day=60,
        monthly_boundary=True,
        agenda_due=False,
    )

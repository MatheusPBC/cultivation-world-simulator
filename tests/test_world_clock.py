import pytest

from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.systems.time import WorldClock


@pytest.mark.parametrize(
    ("absolute_day", "expected"),
    [
        (0, (0, 1, 1)),
        (29, (0, 1, 30)),
        (30, (0, 2, 1)),
        (359, (0, 12, 30)),
        (360, (1, 1, 1)),
    ],
)
def test_world_clock_derives_calendar_date_from_absolute_day(absolute_day, expected):
    """Break caught: a wrong divisor or one-based offset misdates every event."""
    assert WorldClock(absolute_day).calendar_date == expected


def test_world_clock_advance_returns_a_new_clock_without_changing_the_original():
    """Break caught: advancing a task mutates the date captured by an earlier event."""
    start = WorldClock(359)

    advanced = start.advance(2)

    assert start.absolute_day == 359
    assert advanced.absolute_day == 361
    assert advanced.calendar_date == (1, 1, 2)


def test_world_clock_rejects_dates_and_advances_before_world_start():
    """Break caught: a malformed task creates events before the world exists."""
    with pytest.raises(ValueError, match="absolute_day"):
        WorldClock(-1)

    with pytest.raises(ValueError, match="days"):
        WorldClock(0).advance(-1)


def test_world_has_a_daily_clock_when_created(base_world):
    """Break caught: a new world has no canonical date for daily tasks."""
    assert base_world.clock == WorldClock(0)


def test_world_clock_round_trips_through_a_save(base_world, tmp_path):
    """Break caught: resuming a world rewinds scheduled daily work to day zero."""
    base_world.clock = WorldClock(367)
    save_path = tmp_path / "daily-clock.json"

    saved, _ = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    loaded_world, _, _ = load_game(save_path)

    assert saved is True
    assert loaded_world.clock == WorldClock(367)

import pytest

from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.systems.calendar_agenda import ScheduledSituation, WorldAgenda


def test_agenda_returns_due_situations_in_id_order_and_keeps_future_work():
    """Resolving day 8 must not also consume a campaign due on day 12."""
    agenda = WorldAgenda()
    agenda.schedule(ScheduledSituation("trade-negotiation", "negotiation", 8))
    agenda.schedule(ScheduledSituation("border-campaign", "campaign", 12))

    assert agenda.due_days == (8, 12)
    assert agenda.pop_due(8) == (
        ScheduledSituation("trade-negotiation", "negotiation", 8),
    )
    assert agenda.due_days == (12,)


def test_agenda_rejects_duplicate_situation_ids():
    """An overwritten ID would silently lose an active situation."""
    agenda = WorldAgenda()
    agenda.schedule(ScheduledSituation("ritual:7", "ritual", 7))

    with pytest.raises(ValueError, match="already scheduled"):
        agenda.schedule(ScheduledSituation("ritual:7", "ritual", 9))


def test_world_agenda_round_trips_through_a_save(base_world, tmp_path):
    """A loaded world must retain pending work that controls its next time jump."""
    base_world.agenda.schedule(ScheduledSituation("caravan:1", "travel", 43))
    save_path = tmp_path / "agenda-save.json"

    saved, _ = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    loaded_world, _, _ = load_game(save_path)

    assert saved is True
    assert loaded_world.agenda.due_days == (43,)
    assert loaded_world.agenda.get("caravan:1") == ScheduledSituation(
        "caravan:1", "travel", 43
    )

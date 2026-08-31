from src.classes.core.dynasty import Dynasty
from src.sim.simulator_engine.phases import world as world_phases


def test_phase_update_dynasty_keeps_reigning_avatar(base_world, dummy_avatar):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.dynasty = Dynasty(
        id=1,
        name="晋",
        desc="",
        royal_surname="司马",
        current_emperor_id=dummy_avatar.id,
    )

    events = world_phases.phase_update_dynasty(base_world)

    assert events == []
    assert base_world.dynasty.current_emperor_id == dummy_avatar.id
    assert base_world.avatar_manager.get_avatar(dummy_avatar.id) is dummy_avatar


def test_phase_update_dynasty_generates_avatar_if_missing(base_world):
    base_world.dynasty = Dynasty(
        id=1,
        name="秦",
        desc="",
        royal_surname="上官",
    )

    events = world_phases.phase_update_dynasty(base_world)

    assert len(events) == 1
    assert "新君" in events[0].content
    emperor = base_world.avatar_manager.get_avatar(base_world.dynasty.current_emperor_id)
    assert emperor is not None
    assert emperor.name.startswith("上官")

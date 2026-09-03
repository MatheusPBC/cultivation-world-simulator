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


def test_phase_update_dynasty_opens_succession_without_generating_emperor(base_world):
    base_world.dynasty = Dynasty(
        id=1,
        name="秦",
        desc="",
        royal_surname="上官",
    )

    events = world_phases.phase_update_dynasty(base_world)

    assert events == []
    assert base_world.dynasty.current_emperor_id is None
    assert base_world.dynasty.imperial_crisis is not None
    assert base_world.dynasty.imperial_crisis.kind == "succession"
    assert base_world.dynasty.imperial_crisis.claims == []

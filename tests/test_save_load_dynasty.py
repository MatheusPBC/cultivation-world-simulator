from pathlib import Path

from src.classes.celestial_dao import DaoPetition, DaoTradition
from src.classes.core.dynasty import Dynasty, ImperialCrisis
from src.sim.simulator import Simulator
from src.sim.save.save_game import save_game
from src.sim.load.load_game import load_game


def test_save_and_load_preserves_avatar_sovereign_crisis_and_petition(base_world, dummy_avatar, tmp_path):
    dummy_avatar.name = "上官景天"
    dummy_avatar.weapon = None
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.dynasty = Dynasty(
        id=2,
        name="宋",
        desc="重文轻武，典章繁密，民间书院兴盛。",
        royal_surname="上官",
        current_emperor_id=dummy_avatar.id,
        imperial_crisis=ImperialCrisis(dummy_avatar.id, "claimant", int(base_world.month_stamp), status="stalemate"),
    )
    base_world.dao_petitions = [DaoPetition("avatar", dummy_avatar.id, 7, DaoTradition.BALANCE, content="Hear me")]

    simulator = Simulator(base_world)
    save_path = Path(tmp_path) / "dynasty_save.json"
    success, _ = save_game(base_world, simulator, existed_sects=[], save_path=save_path)

    assert success

    new_world, _new_sim, _new_sects = load_game(save_path)
    assert new_world.dynasty is not None
    assert new_world.dynasty.name == "宋"
    assert new_world.dynasty.royal_surname == "上官"
    assert new_world.dynasty.title == "宋朝"
    assert new_world.dynasty.current_emperor_id == dummy_avatar.id
    assert new_world.avatar_manager.get_avatar(dummy_avatar.id).name == "上官景天"
    assert new_world.dynasty.imperial_crisis.status == "stalemate"
    assert new_world.dao_petitions[0].tradition is DaoTradition.BALANCE

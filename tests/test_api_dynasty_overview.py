from src.classes.core.dynasty import Dynasty, ImperialCrisis
from src.server.assemblers.dynasty_detail import build_dynasty_detail
from src.server.assemblers.dynasty_overview import build_dynasty_overview


def test_dynasty_overview_is_empty_without_world():
    assert build_dynasty_overview(None)["current_emperor"] is None


def test_dynasty_overview_resolves_sovereign_avatar(base_world, dummy_avatar):
    dummy_avatar.name = "司马承安"
    dummy_avatar.weapon = None
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.dynasty = Dynasty(id=2, name="晋", desc="", royal_surname="司马", current_emperor_id=dummy_avatar.id)
    data = build_dynasty_overview(base_world)
    assert data["current_emperor"]["id"] == dummy_avatar.id
    assert data["current_emperor"]["name"] == "司马承安"
    assert data["current_emperor"]["age"] == 20


def test_dynasty_detail_exposes_imperial_crisis(base_world, dummy_avatar):
    supporter = type("Supporter", (), {"id": "support", "name": "Cao Xu"})()
    dummy_avatar.weapon = None
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.avatar_manager.register_avatar(supporter)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=dummy_avatar.id,
        imperial_crisis=ImperialCrisis(dummy_avatar.id, "claimant", 12, support_avatar_ids=["support"], evidence_event_ids=["evidence"], legitimacy_factors={"office": 60, "total": 60}),
    )
    data = build_dynasty_detail(base_world)
    assert data["imperial_crisis"]["emperor"]["id"] == dummy_avatar.id
    assert data["imperial_crisis"]["support_count"] == 1
    assert data["imperial_crisis"]["supporters"] == [{"id": "support", "name": "Cao Xu"}]
    assert data["imperial_crisis"]["evidence_event_ids"] == ["evidence"]
    assert data["imperial_crisis"]["legitimacy_factors"]["total"] == 60

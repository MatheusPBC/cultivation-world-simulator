from src.classes.core.dynasty import Dynasty, ImperialClaim, ImperialCrisis
from src.server.assemblers.dynasty_detail import build_dynasty_detail
from src.server.assemblers.dynasty_overview import build_dynasty_overview


def test_dynasty_overview_is_empty_without_world():
    assert build_dynasty_overview(None)["current_emperor"] is None


def test_dynasty_overview_resolves_sovereign_avatar(base_world, dummy_avatar):
    dummy_avatar.name = "司马承安"
    dummy_avatar.weapon = None
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.dynasty = Dynasty(id=2, name="晋", desc="", royal_surname="司马", current_emperor_id=dummy_avatar.id, royal_house_member_ids=[dummy_avatar.id], royal_blood_member_ids=[dummy_avatar.id])
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
        royal_house_member_ids=[dummy_avatar.id, "claimant"],
        royal_blood_member_ids=[dummy_avatar.id, "claimant"],
        imperial_crisis=ImperialCrisis(
            kind="challenge",
            incumbent_id=dummy_avatar.id,
            opened_month=12,
            claims=[ImperialClaim(
                candidate_id="claimant",
                opened_month=12,
                evidence_event_ids=["evidence"],
                political_positions={"support": "support"},
            )],
        ),
    )
    data = build_dynasty_detail(base_world)
    assert data["imperial_crisis"]["kind"] == "challenge"
    assert data["imperial_crisis"]["incumbent"]["id"] == dummy_avatar.id
    claim = data["imperial_crisis"]["claims"][0]
    assert claim["candidate"]["id"] == "claimant"
    assert claim["support_count"] == 1
    assert claim["supporters"] == [{"id": "support", "name": "Cao Xu"}]
    assert claim["evidence_event_ids"] == ["evidence"]

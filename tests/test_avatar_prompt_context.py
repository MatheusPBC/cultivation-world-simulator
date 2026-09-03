from copy import copy

from src.classes.core.avatar.prompt_context import build_avatar_prompt_context
from src.classes.core.dynasty import Dynasty
from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR
from src.systems.imperial_crisis_service import open_imperial_claim, support_imperial_claim


def test_court_official_receives_active_imperial_crisis_as_observation(base_world, dummy_avatar):
    emperor = dummy_avatar
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    emperor.court_reputation = 700
    claimant = copy(emperor)
    claimant.id = "claimant"
    claimant.name = "Claimant"
    supporter = copy(emperor)
    supporter.id = "supporter"
    supporter.name = "Supporter"
    base_world.avatar_manager.register_avatar(emperor)
    base_world.avatar_manager.register_avatar(claimant)
    base_world.avatar_manager.register_avatar(supporter)
    base_world.dynasty = Dynasty(id=1, name="Test", desc="", current_emperor_id=emperor.id)

    open_imperial_claim(base_world, claimant.id)
    support_imperial_claim(base_world, supporter.id, claimant.id)

    context = build_avatar_prompt_context(supporter)

    crisis = context["court_context"]["active_imperial_crisis"]
    assert crisis["role"] == "court_official"
    assert crisis["incumbent"] == {"id": emperor.id, "name": emperor.name}
    assert crisis["claims"][0]["candidate_name"] == claimant.name
    assert crisis["claims"][0]["positions"] == {supporter.id: "support"}


def test_non_official_does_not_receive_court_crisis_context(base_world, dummy_avatar):
    emperor = copy(dummy_avatar)
    emperor.id = "emperor"
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    emperor.court_reputation = 700
    claimant = copy(emperor)
    claimant.id = "claimant"
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.avatar_manager.register_avatar(emperor)
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(id=1, name="Test", desc="", current_emperor_id=emperor.id)
    open_imperial_claim(base_world, claimant.id)

    assert build_avatar_prompt_context(dummy_avatar)["court_context"] == {"active_imperial_crisis": None}

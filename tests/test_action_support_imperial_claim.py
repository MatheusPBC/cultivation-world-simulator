from copy import copy

from src.classes.action.support_imperial_claim import SupportImperialClaim
from src.classes.actions import get_action_infos
from src.classes.core.dynasty import Dynasty
from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR
from src.systems.imperial_crisis_service import open_imperial_claim


def test_court_official_can_support_active_imperial_claim(base_world, dummy_avatar):
    emperor = dummy_avatar
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    emperor.court_reputation = 700
    claimant = copy(emperor)
    claimant.id = "claimant"
    supporter = copy(emperor)
    supporter.id = "supporter"
    supporter.name = "Supporter"
    base_world.avatar_manager.register_avatar(emperor)
    base_world.avatar_manager.register_avatar(claimant)
    base_world.avatar_manager.register_avatar(supporter)
    base_world.dynasty = Dynasty(id=1, name="Test", desc="", current_emperor_id=emperor.id)
    crisis = open_imperial_claim(base_world, claimant.id)

    assert "SupportImperialClaim" in get_action_infos(supporter)
    supporter.load_decide_result_chain([("SupportImperialClaim", {})], "I back the claimant.", "Declare support")
    assert supporter.commit_next_plan() is None

    assert crisis.support_avatar_ids == [supporter.id]
    support_event = base_world.event_manager.get_event_by_id(crisis.evidence_event_ids[-1])
    assert support_event is not None
    assert support_event.causal_links[0].cause_event_id == crisis.evidence_event_ids[0]
    assert "SupportImperialClaim" not in get_action_infos(supporter)

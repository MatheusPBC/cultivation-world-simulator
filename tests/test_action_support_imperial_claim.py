from copy import copy

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
    claim_event = open_imperial_claim(base_world, claimant.id)
    base_world.event_manager.add_event(claim_event)
    crisis = base_world.dynasty.imperial_crisis

    assert "SupportImperialClaim" in get_action_infos(supporter)
    supporter.load_decide_result_chain(
        [("SupportImperialClaim", {"candidate_id": claimant.id})],
        "I back the claimant.",
        "Declare support",
    )
    support_event = supporter.commit_next_plan()

    assert crisis.get_claim(claimant.id).political_positions == {
        supporter.id: "support"
    }
    assert support_event is not None
    assert base_world.event_manager.get_event_by_id(support_event.id) is None
    assert support_event.causal_links[1].cause_event_id == claim_event.id
    assert "SupportImperialClaim" not in get_action_infos(supporter)

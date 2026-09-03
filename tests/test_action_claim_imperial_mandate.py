from copy import copy

from src.classes.action.claim_imperial_mandate import ClaimImperialMandate
from src.classes.actions import get_action_infos
from src.classes.core.dynasty import Dynasty
from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR


def _install_eligible_crisis_pair(base_world, dummy_avatar):
    emperor = dummy_avatar
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    emperor.court_reputation = 700
    claimant = copy(emperor)
    claimant.id = "claimant"
    claimant.name = "Claimant"
    base_world.avatar_manager.register_avatar(emperor)
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(id=1, name="Test", desc="", current_emperor_id=emperor.id)
    return emperor, claimant


def test_claim_imperial_mandate_is_offered_only_to_eligible_avatar(base_world, dummy_avatar):
    _emperor, claimant = _install_eligible_crisis_pair(base_world, dummy_avatar)

    assert "ClaimImperialMandate" in get_action_infos(claimant)
    assert "ClaimImperialMandate" not in get_action_infos(dummy_avatar)


def test_claim_imperial_mandate_opens_crisis_via_avatar_plan(base_world, dummy_avatar):
    _emperor, claimant = _install_eligible_crisis_pair(base_world, dummy_avatar)
    claimant.load_decide_result_chain([("ClaimImperialMandate", {})], "I will claim the mandate.", "Claim the throne")

    start_event = claimant.commit_next_plan()

    assert start_event is not None
    assert base_world.dynasty.imperial_crisis is not None
    assert base_world.dynasty.imperial_crisis.get_claim(claimant.id) is not None
    claim_event = start_event
    assert base_world.event_manager.get_event_by_id(claim_event.id) is None
    delta = claim_event.causal_payload["deltas"][0]
    assert delta["owner_kind"] == "dynasty"
    assert delta["owner_id"] == "1"
    assert delta["aspect"] == "imperial_claims"
    assert delta["before"] == "[]"
    assert claimant.id in delta["after"]
    assert ClaimImperialMandate(claimant, base_world).can_possibly_start() is False

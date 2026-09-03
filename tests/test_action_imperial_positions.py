from copy import copy

from src.classes.actions import get_action_infos
from src.classes.core.dynasty import Dynasty
from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.phases.actions import phase_commit_next_plans
from src.sim.simulator_engine.finalizer import finalize_step
from src.systems.imperial_crisis_service import open_imperial_claim


def _active_crisis(base_world, dummy_avatar):
    emperor = dummy_avatar
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    emperor.court_reputation = 700
    claimant = copy(emperor)
    claimant.id = "claimant"
    official = copy(emperor)
    official.id = "official"
    official.name = "Official"
    for avatar in (emperor, claimant, official):
        base_world.avatar_manager.register_avatar(avatar)
    base_world.dynasty = Dynasty(
        id=1,
        name="Test",
        desc="",
        current_emperor_id=emperor.id,
    )
    claim_event = open_imperial_claim(base_world, claimant.id)
    base_world.event_manager.add_event(claim_event)
    return base_world.dynasty.imperial_crisis, claimant, official


def test_court_official_can_take_one_causal_opposition(base_world, dummy_avatar):
    crisis, _, official = _active_crisis(base_world, dummy_avatar)

    assert "OpposeImperialClaim" in get_action_infos(official)
    official.load_decide_result_chain(
        [("OpposeImperialClaim", {"candidate_id": "claimant"})],
        "Public position",
        "Court policy",
    )
    position_event = official.commit_next_plan()

    claim = crisis.get_claim("claimant")
    assert claim.political_positions[official.id] == "oppose"
    event = position_event
    assert event is not None
    assert base_world.event_manager.get_event_by_id(event.id) is None
    assert event.causal_links[1].cause_event_id == claim.evidence_event_ids[0]
    assert event.causal_payload["deltas"][0]["after"] == "oppose"
    assert "OpposeImperialClaim" not in get_action_infos(official)


def test_only_claimant_can_withdraw_and_end_active_pretension(base_world, dummy_avatar):
    crisis, claimant, official = _active_crisis(base_world, dummy_avatar)

    assert "WithdrawImperialClaim" in get_action_infos(claimant)
    assert "WithdrawImperialClaim" not in get_action_infos(official)
    claimant.load_decide_result_chain(
        [("WithdrawImperialClaim", {})],
        "I withdraw the claim.",
        "End pretension",
    )
    withdrawal_event = claimant.commit_next_plan()

    assert crisis.status == "active"
    assert crisis.get_claim(claimant.id).status == "withdrawn"
    event = withdrawal_event
    assert event is not None
    assert base_world.event_manager.get_event_by_id(event.id) is None
    assert event.causal_payload["deltas"][0]["before"] == "active"
    assert event.causal_payload["deltas"][0]["after"] == "withdrawn"
    assert "WithdrawImperialClaim" not in get_action_infos(claimant)


def test_imperial_action_event_uses_step_pipeline_before_persistence(
    base_world, dummy_avatar
):
    crisis, _, official = _active_crisis(base_world, dummy_avatar)
    official.load_decide_result_chain(
        [("OpposeImperialClaim", {"candidate_id": "claimant"})],
        "I oppose the claim.",
        "Defend the throne",
    )

    ctx = SimulationStepContext.create(base_world)
    events = phase_commit_next_plans([official])

    assert len(events) == 1
    event = events[0]
    assert event.id == crisis.get_claim("claimant").evidence_event_ids[-1]
    assert base_world.event_manager.get_event_by_id(event.id) is None

    ctx.events.extend(events)
    finalize_step(ctx)

    assert base_world.event_manager.get_event_by_id(event.id) is event

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.server.assemblers.avatar_detail import build_avatar_detail
from src.server.assemblers.institutional_chain import build_institutional_chain
from src.server.services.game_queries import get_event_causal_detail
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from tests.domain_reactivity_fixtures import setup_government_condition


def _endorsement_events(world, avatar):
    city, trigger, condition = setup_government_condition(world)
    bootstrap_institutional_authority(world)
    dynasty = world.institutional_authority.get_institution_for_owner(
        EntityRef("dynasty", "1")
    )
    petition = Event(
        world.month_stamp,
        "The people petition their government.",
        id="endorsement-source-petition",
        event_type="civil_public_petition",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"civil_petition": {
            "region_id": str(city.id),
            "condition_instance_id": str(condition.id),
            "addressed_institution_id": dynasty.id,
            "addressed_institution_ref": {"kind": "dynasty", "id": "1"},
        }},
    )
    decision = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="avatar",
        subject_id=str(avatar.id),
        source="llm",
        considered_count=1,
        chosen_chain=[{"action_name": "EndorsePublicPetition", "params": {
            "cause_event_id": petition.id,
        }}],
    )
    decision_event = Event(
        world.month_stamp,
        "Avatar chooses to endorse the petition.",
        id="endorsement-avatar-decision",
        related_avatars=[str(avatar.id)],
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"deltas": [], "decision": decision.to_dict()},
    )
    endorsement = Event(
        world.month_stamp,
        "An avatar publicly endorses the petition.",
        id="endorsement-fact",
        related_avatars=[str(avatar.id)],
        event_type="civil_public_petition_endorsed",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={"region_id": str(city.id), "avatar_id": str(avatar.id)},
        causal_payload={"deltas": [], "civic_endorsement": {
            "avatar_id": str(avatar.id),
            "avatar_name": str(avatar.name),
            "region_id": str(city.id),
            "condition_instance_id": str(condition.id),
            "petition_event_id": petition.id,
            "addressed_institution_id": dynasty.id,
            "addressed_institution_ref": {"kind": "dynasty", "id": "1"},
        }},
    )
    endorsement.causal_links.extend((
        CausalLink(event_id=endorsement.id, cause_event_id=petition.id, relation=CausalRelation.RESPONSE_TO),
        CausalLink(event_id=endorsement.id, cause_event_id=decision_event.id, relation=CausalRelation.MOTIVATED_BY),
    ))
    response = Event(
        world.month_stamp + 1,
        "The government acknowledges the endorsement.",
        id="endorsement-government-response",
        event_type="government_interpretation_decision",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        causal_payload={"deltas": [], "decision": AgentDecision(
            month_stamp=int(world.month_stamp) + 1,
            subject_kind="dynasty", subject_id="1", source="llm",
            chosen_chain=[{"action_name": "maintain", "params": {}}],
        ).to_dict()},
    )
    response.causal_links.append(
        CausalLink(event_id=response.id, cause_event_id=endorsement.id, relation=CausalRelation.RESPONSE_TO)
    )
    for event in (trigger, petition, decision_event, endorsement, response):
        world.event_manager.add_event(event)
    return city, petition, decision_event, endorsement, response, dynasty


def test_endorsement_and_response_project_to_historical_offices(base_world, dummy_avatar):
    city, petition, decision, endorsement, response, dynasty = _endorsement_events(
        base_world, dummy_avatar
    )
    chain = build_institutional_chain(base_world, owner_kind="dynasty", owner_id="1")
    rows = {row["event_id"]: row for row in chain["events"]}
    assert endorsement.id in rows and response.id in rows
    assert rows[endorsement.id]["source_event_ids"] == [petition.id, decision.id]
    assert rows[response.id]["source_event_ids"] == [endorsement.id]
    assert dynasty.id in {item["id"] for item in chain["institutions"]}
    assert f"inst:city:{city.id}" in {item["id"] for item in chain["institutions"]}


def test_endorsement_history_and_why_are_avatar_scoped(base_world, dummy_avatar):
    _city, petition, decision, endorsement, _response, _dynasty = _endorsement_events(
        base_world, dummy_avatar
    )
    activity = build_avatar_detail(
        dummy_avatar, resolve_avatar_pic_id=lambda _avatar: 0
    )["activity"]
    assert endorsement.id in {item["event_id"] for item in activity["events"]}
    def serialize(events, **_kwargs):
        return [event.to_dict() for event in events]
    why = get_event_causal_detail(
        {"world": base_world}, serialize_events_for_client=serialize,
        event_id=endorsement.id,
    )
    assert {item["event"]["id"] for item in why["causes"]} == {petition.id, decision.id}


def test_story_and_malformed_endorsements_are_not_projected(base_world, dummy_avatar):
    _city, petition, _decision, endorsement, _response, _dynasty = _endorsement_events(
        base_world, dummy_avatar
    )
    for event in (
        Event.from_dict({**endorsement.to_dict(), "id": "endorsement-story", "is_story": True}),
        Event.from_dict({**endorsement.to_dict(), "id": "endorsement-malformed", "related_avatars": []}),
    ):
        world = base_world
        world.event_manager.add_event(event)
    chain = build_institutional_chain(base_world, owner_kind="dynasty", owner_id="1")
    rows = {row["event_id"] for row in chain["events"]}
    assert "endorsement-story" not in rows
    assert "endorsement-malformed" not in rows

"""Read-model coverage for factual civil petitions and their responses."""

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.agent_decision import AgentDecision
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.server.assemblers.institutional_chain import build_institutional_chain
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from tests.domain_reactivity_fixtures import setup_government_condition


def _civil_events(world):
    city, trigger, condition = setup_government_condition(world)
    bootstrap_institutional_authority(world)
    city_institution = world.institutional_authority.get_institution_for_owner(
        EntityRef("region", str(city.id))
    )
    dynasty_institution = world.institutional_authority.get_institution_for_owner(
        EntityRef("dynasty", "1")
    )
    petition = Event(
        world.month_stamp,
        "The people petition their government.",
        id="civil-petition-read-model",
        event_type="civil_public_petition",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={
            "deltas": [],
            "civil_petition": {
                "region_id": str(city.id),
                "condition_instance_id": str(condition.id),
                "addressed_institution_id": dynasty_institution.id,
                "addressed_institution_ref": {"kind": "dynasty", "id": "1"},
                "evidence_event_ids": [trigger.id],
            },
        },
    )
    petition.causal_links.append(CausalLink(
        event_id=petition.id,
        cause_event_id=trigger.id,
        relation=CausalRelation.MOTIVATED_BY,
    ))
    response = Event(
        world.month_stamp + 1,
        "Urban maintenance completed.",
        id="civil-response-read-model",
        event_type="city_maintenance_completed",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={"region_id": str(city.id)},
        causal_payload={"deltas": [{"owner_kind": "region", "owner_id": str(city.id)}]},
    )
    response.causal_links.append(CausalLink(
        event_id=response.id,
        cause_event_id=petition.id,
        relation=CausalRelation.RESPONSE_TO,
    ))
    world.event_manager.add_event(trigger)
    world.event_manager.add_event(petition)
    world.event_manager.add_event(response)
    return city, petition, response, city_institution, dynasty_institution


def test_civil_petition_and_material_response_are_institutional_facts(base_world):
    _city, petition, response, _city_institution, dynasty_institution = _civil_events(base_world)

    chain = build_institutional_chain(base_world, owner_kind="dynasty", owner_id="1")
    rows = {row["event_id"]: row for row in chain["events"]}

    assert petition.id in rows
    assert response.id in rows
    assert rows[response.id]["source_event_ids"] == [petition.id]
    assert dynasty_institution.id in {item["id"] for item in chain["institutions"]}
    # The city is factual from the petition/transition region, not inferred
    # from whichever government happens to control it now.
    assert any(item["kind"] == "city" for item in chain["institutions"])


def test_story_and_malformed_civil_payloads_are_not_projected(base_world):
    _city, petition, _response, _city_institution, _dynasty_institution = _civil_events(base_world)
    story = Event(
        base_world.month_stamp,
        "A story about a petition.",
        id="civil-story",
        event_type="civil_public_petition",
        is_story=True,
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.EXTERNAL_EVENT,
        causal_payload=petition.causal_payload,
    )
    malformed = Event(
        base_world.month_stamp,
        "Malformed petition.",
        id="civil-malformed",
        event_type="civil_public_petition",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"civil_petition": {"region_id": "301"}},
    )
    decision = Event(
        base_world.month_stamp,
        "A valid institutional decision.",
        id="civil-ancestor-decision",
        event_type="government_interpretation_decision",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={
            "decision": {
                "subject_kind": "dynasty",
                "subject_id": "1",
            }
        },
    )
    malformed.causal_links.append(CausalLink(
        event_id=malformed.id,
        cause_event_id=decision.id,
        relation=CausalRelation.RESPONSE_TO,
    ))
    base_world.event_manager.add_event(story)
    base_world.event_manager.add_event(malformed)
    base_world.event_manager.add_event(decision)

    chain = build_institutional_chain(base_world, owner_kind="dynasty", owner_id="1")
    ids = {row["event_id"] for row in chain["events"]}
    assert petition.id in ids
    assert "civil-story" not in ids
    assert "civil-malformed" not in ids


def test_petition_keeps_historical_address_after_government_changes(base_world):
    city, petition, _response, _city_institution, dynasty_institution = _civil_events(base_world)
    from src.classes.environment.city_state import CityGovernance

    city.city_state.governance = CityGovernance("dynasty", "2", 1.0)
    chain = build_institutional_chain(base_world, owner_kind="dynasty", owner_id="1")
    ids = {item["id"] for item in chain["institutions"]}
    assert petition.id in {row["event_id"] for row in chain["events"]}
    assert dynasty_institution.id in ids
    assert any(item["kind"] == "city" for item in chain["institutions"])


def test_work_stoppage_chain_projects_start_end_and_forgone_output(base_world):
    city, petition, _response, _city_institution, _dynasty_institution = _civil_events(base_world)
    decision = Event(
        base_world.month_stamp,
        "The people decide to stop working.",
        id="civil-stoppage-decision",
        event_type="population_interpretation_decision",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision": {"subject_kind": "region", "subject_id": str(city.id)}},
    )
    start = Event(
        base_world.month_stamp,
        "Work stoppage starts.",
        id="civil-stoppage-start",
        event_type="civil_work_stoppage_started",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"civil_work_stoppage": {
            "region_id": str(city.id),
            "condition_instance_id": "government-condition",
            "petition_event_id": petition.id,
        }},
    )
    # Link order is deliberately decision, petition, condition: projection
    # must select typed canonical causes rather than the first ancestor.
    start.causal_links.extend((
        CausalLink(event_id=start.id, cause_event_id=decision.id, relation=CausalRelation.TRIGGERED_BY),
        CausalLink(event_id=start.id, cause_event_id=petition.id, relation=CausalRelation.MOTIVATED_BY),
        CausalLink(event_id=start.id, cause_event_id="government-trigger", relation=CausalRelation.ENABLED_BY),
    ))
    ended = Event(
        base_world.month_stamp + 1,
        "Work stoppage ends.",
        id="civil-stoppage-end",
        event_type="civil_work_stoppage_ended",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
        causal_payload={"deltas": []},
    )
    forgone = Event(
        base_world.month_stamp,
        "Production is forgone.",
        id="civil-production-forgone",
        event_type="regional_production_forgone",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.DETERMINISTIC,
        causal_payload={"deltas": []},
    )
    ended.causal_links.append(CausalLink(
        event_id=ended.id,
        cause_event_id=start.id,
        relation=CausalRelation.RESOLVES,
    ))
    forgone.causal_links.append(CausalLink(
        event_id=forgone.id,
        cause_event_id=start.id,
        relation=CausalRelation.TRIGGERED_BY,
    ))
    government_response = Event(
        base_world.month_stamp + 1,
        "The government responds to the work stoppage.",
        id="civil-stoppage-government-response",
        event_type="government_interpretation_decision",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        causal_payload={
            "deltas": [],
            "decision": AgentDecision(
                month_stamp=int(base_world.month_stamp + 1),
                subject_kind="dynasty",
                subject_id="1",
                source="llm",
                considered_count=1,
                chosen_chain=[],
                thinking="Address the stoppage through the current government.",
                short_term_objective="Respond to the affected population.",
                rejected=[],
            ).to_dict(),
            "interpretation": {"decision": "maintain", "source": "llm"},
        },
    )
    government_response.causal_links.append(CausalLink(
        event_id=government_response.id,
        cause_event_id=start.id,
        relation=CausalRelation.RESPONSE_TO,
    ))
    malformed_start = Event(
        base_world.month_stamp,
        "Malformed stoppage.",
        id="civil-stoppage-self-reference",
        event_type="civil_work_stoppage_started",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"civil_work_stoppage": {
            "region_id": str(city.id),
            "condition_instance_id": "government-condition",
            "petition_event_id": "civil-stoppage-self-reference",
        }},
    )
    base_world.event_manager.add_event(decision)
    base_world.event_manager.add_event(start)
    base_world.event_manager.add_event(ended)
    base_world.event_manager.add_event(forgone)
    base_world.event_manager.add_event(government_response)
    base_world.event_manager.add_event(malformed_start)

    chain = build_institutional_chain(base_world, owner_kind="dynasty", owner_id="1")
    ids = {row["event_id"] for row in chain["events"]}
    assert {start.id, ended.id, forgone.id, government_response.id}.issubset(ids)
    assert malformed_start.id not in ids
    response_row = next(row for row in chain["events"] if row["event_id"] == government_response.id)
    assert start.id in response_row["source_event_ids"]

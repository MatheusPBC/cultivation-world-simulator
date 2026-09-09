from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.server.assemblers.institutional_chain import build_institutional_chain
from src.systems.city_damage import execute_crowd_damage
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from tests.test_civil_riot_owner_boundary import _decision, _riot_setup


def _record_riot(world):
    city, trigger, condition, context, option = _riot_setup(world)
    decision = _decision(context, option, event_id="riot-chain-decision")
    riot = execute_crowd_damage(
        context,
        option,
        decision_event_id=decision.id,
        decision_event=decision,
    )
    bootstrap_institutional_authority(world)
    world.event_manager.add_event(trigger)
    world.event_manager.add_event(decision)
    world.event_manager.add_event(riot)
    return city, trigger, decision, riot


def test_canonical_riot_and_government_response_are_institutional_chain_facts(base_world):
    city, _trigger, _decision_event, riot = _record_riot(base_world)
    response = Event(
        base_world.month_stamp + 1,
        "The government answers the urban damage.",
        id="riot-chain-government-response",
        event_type="government_interpretation_decision",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        render_params={
            "domain": "government",
            "actor_kind": "dynasty",
            "actor_id": "1",
            "decision": "maintain",
        },
        causal_payload={
            "deltas": [],
            "decision": AgentDecision(
                month_stamp=int(base_world.month_stamp + 1),
                subject_kind="dynasty",
                subject_id="1",
                source="llm",
                considered_count=1,
                thinking="Keep the city response within existing maintenance.",
                short_term_objective="Restore urban service without inventing a new action.",
            ).to_dict(),
            "interpretation": {"decision": "maintain", "source": "llm"},
        },
    )
    response.causal_links.append(CausalLink(
        event_id=response.id,
        cause_event_id=riot.id,
        relation=CausalRelation.RESPONSE_TO,
    ))
    base_world.event_manager.add_event(response)

    chain = build_institutional_chain(base_world, owner_kind="dynasty", owner_id="1")
    rows = {row["event_id"]: row for row in chain["events"]}

    assert riot.id in rows
    assert response.id in rows
    assert riot.id in rows[response.id]["source_event_ids"]
    assert any(item["kind"] == "city" and item["id"] == f"inst:city:{city.id}" for item in chain["institutions"])


def test_story_and_malformed_riot_facts_are_fail_closed(base_world):
    _city, trigger, decision, riot = _record_riot(base_world)
    story = Event(
        base_world.month_stamp,
        "A story of a riot.",
        id="riot-chain-story",
        event_type="civil_riot_occurred",
        is_story=True,
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload=riot.causal_payload,
    )
    malformed = Event(
        base_world.month_stamp,
        "Malformed riot.",
        id="riot-chain-malformed",
        event_type="civil_riot_occurred",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"civil_riot": {"region_id": "301"}},
    )
    for event in (story, malformed):
        event.causal_links.extend((
            CausalLink(event_id=event.id, cause_event_id=decision.id, relation=CausalRelation.TRIGGERED_BY),
            CausalLink(event_id=event.id, cause_event_id=trigger.id, relation=CausalRelation.ENABLED_BY),
        ))
        base_world.event_manager.add_event(event)

    riot_payload = dict(riot.causal_payload)
    riot_payload["civil_riot"] = dict(riot_payload["civil_riot"])
    forged_decision = Event(
        base_world.month_stamp,
        "A decision for another region.",
        id="riot-chain-wrong-region-decision",
        event_type="population_interpretation_decision",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        causal_payload={
            "deltas": [],
            "decision": AgentDecision(
                month_stamp=int(base_world.month_stamp),
                subject_kind="population",
                subject_id="region:999",
                source="llm",
                considered_count=1,
                chosen_chain=[{
                    "selected_affordance_id": riot_payload["affordance_id"],
                }],
            ).to_dict(),
        },
    )
    wrong_condition = Event(
        base_world.month_stamp,
        "A condition in another region.",
        id="riot-chain-wrong-region-condition",
        event_type="semantic_condition_activated",
        fact_kind=FactKind.DERIVED_CONDITION,
        render_params={"region_id": "999"},
    )
    for suffix, decision_cause, condition_cause in (
        ("decision", forged_decision, trigger),
        ("condition", decision, wrong_condition),
    ):
        forged = Event(
            base_world.month_stamp,
            "A forged riot chain.",
            id=f"riot-chain-forged-{suffix}",
            event_type="civil_riot_occurred",
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload=riot_payload,
        )
        forged.causal_links.extend((
            CausalLink(event_id=forged.id, cause_event_id=decision_cause.id, relation=CausalRelation.TRIGGERED_BY),
            CausalLink(event_id=forged.id, cause_event_id=condition_cause.id, relation=CausalRelation.ENABLED_BY),
        ))
        base_world.event_manager.add_event(forged)
    base_world.event_manager.add_event(forged_decision)
    base_world.event_manager.add_event(wrong_condition)

    chain = build_institutional_chain(base_world, owner_kind="dynasty", owner_id="1")
    ids = {row["event_id"] for row in chain["events"]}
    assert "riot-chain-story" not in ids
    assert "riot-chain-malformed" not in ids
    assert "riot-chain-forged-decision" not in ids
    assert "riot-chain-forged-condition" not in ids

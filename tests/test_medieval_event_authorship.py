import pytest

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.state_delta import StateDelta
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import record_event, validate_history


def test_actor_transition_rejects_payload_that_does_not_match_its_decision():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    decision = record_event(
        world, "authorship_decided", "Uma decisão material foi tomada.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision={"action": "test_action", "actor_ref": actor.to_dict(),
                  "selected_affordance_id": "affordance:current"},
    )
    transition = record_event(
        world, "authorship_transition", "Uma transição material foi aplicada.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={
            "decision_event_id": decision.id,
            "actor_ref": actor.to_dict(),
            "selected_affordance_id": "affordance:current",
        },
        deltas=(StateDelta(owner_kind="test_owner", owner_id="one", aspect="value",
                           before="0", after="1"),),
        cause_ids=(decision.id,),
    )
    world.events[-1] = transition.model_copy(update={
        "causal_payload": {
            "decision_event_id": decision.id,
            "actor_ref": actor.to_dict(),
            "selected_affordance_id": "affordance:forged",
        }
    })

    with pytest.raises(ValueError, match="authorship does not match"):
        validate_history(world.events, world.clock.absolute_day)


def test_record_event_rejects_actor_transition_before_append_without_payload():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    decision = record_event(
        world, "authorship_decided", "Uma decisão material foi tomada.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision={"action": "test_action", "actor_ref": actor.to_dict(),
                  "selected_affordance_id": "affordance:current"},
    )

    with pytest.raises(ValueError, match="causal authorship payload"):
        record_event(
            world, "authorship_transition", "Uma transição material foi aplicada.",
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            deltas=(StateDelta(owner_kind="test_owner", owner_id="one", aspect="value",
                               before="0", after="1"),),
            cause_ids=(decision.id,),
        )
    assert len(world.events) == 1


def test_actor_transition_requires_an_actor_decision_not_owner_authorization():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    authorization = record_event(
        world, "owner_authorized", "Owner recomputou e autorizou os termos.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.DETERMINISTIC,
        decision={"action": "test_action", "actor_ref": actor.to_dict(),
                  "selected_affordance_id": "affordance:current"},
    )

    with pytest.raises(ValueError, match="same-day real decision cause"):
        record_event(
            world, "actor_transition", "Uma mutação não pode atribuir-se ao actor pela autorização.",
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload={"decision_event_id": authorization.id,
                            "actor_ref": actor.to_dict(),
                            "selected_affordance_id": "affordance:current"},
            deltas=(StateDelta(owner_kind="test_owner", owner_id="one", aspect="value",
                               before="0", after="1"),),
            cause_ids=(authorization.id,),
        )
    assert len(world.events) == 1


def test_record_event_rejects_a_stale_actor_decision_before_append():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    decision = record_event(
        world, "authorship_decided", "A escolha foi feita no dia anterior.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision={"action": "test_action", "actor_ref": actor.to_dict(),
                  "selected_affordance_id": "affordance:current"},
    )
    world.clock = world.clock.advance(1)

    with pytest.raises(ValueError, match="same-day real decision cause"):
        record_event(
            world, "authorship_transition", "Tentativa de aplicar escolha antiga.",
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload={"decision_event_id": decision.id,
                            "actor_ref": actor.to_dict(),
                            "selected_affordance_id": "affordance:current"},
            deltas=(StateDelta(owner_kind="test_owner", owner_id="one", aspect="value",
                               before="0", after="1"),),
            cause_ids=(decision.id,),
        )

    assert len(world.events) == 1


def test_validate_history_rejects_actor_transition_without_decision_source():
    world = create_medieval_world(73)
    source = record_event(world, "material_source", "Uma ocorrência material foi registrada.")
    transition = record_event(
        world, "actor_transition", "Uma transição foi registrada para a regressão.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
        deltas=(StateDelta(owner_kind="test_owner", owner_id="one", aspect="value",
                           before="0", after="1"),),
        cause_ids=(source.id,),
    )
    forged = transition.model_copy(update={
        "causal_origin": CausalOrigin.ACTOR_DECISION,
        "causal_payload": {
            "decision_event_id": "event:999",
            "actor_ref": {"kind": "polity", "id": "auren"},
            "selected_affordance_id": "affordance:forged",
        },
    })
    world.events[-1] = forged

    with pytest.raises(ValueError, match="real decision cause|authorship"):
        validate_history(world.events, world.clock.absolute_day)


def test_actor_decision_requires_source_before_it_is_appended():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")

    with pytest.raises(ValueError, match="requires a decision source"):
        record_event(
            world, "unsourced_decision", "Escolha sem autoria.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            decision={"action": "test_action", "actor_ref": actor.to_dict(),
                      "selected_affordance_id": "affordance:current"},
        )

    assert world.events == []


def test_actor_decision_rejects_provider_receipt_for_another_selection():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    receipt = record_event(
        world, "ai_decision_interpreted", "Interpretação recebida.",
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        causal_payload={"selection": {"actor_ref": actor.to_dict(),
                                       "selected_affordance_id": "affordance:other"}},
    )

    with pytest.raises(ValueError, match="does not match actor and affordance"):
        record_event(
            world, "provider_decision", "Escolha divergente.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            decision={"action": "test_action", "actor_ref": actor.to_dict(),
                      "selected_affordance_id": "affordance:current"},
            causal_payload={"decision_source": {"kind": "provider",
                                                "receipt_event_id": receipt.id}},
            cause_ids=(receipt.id,),
        )

    assert [event.id for event in world.events] == [receipt.id]


def test_actor_decision_rejects_provider_receipt_from_an_earlier_day():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    receipt = record_event(
        world, "ai_decision_interpreted", "Interpretação do dia anterior.",
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        causal_payload={"selection": {"actor_ref": actor.to_dict(),
                                       "selected_affordance_id": "affordance:current"}},
    )
    world.clock = world.clock.advance(1)

    with pytest.raises(ValueError, match="prior causal receipt"):
        record_event(
            world, "provider_decision", "Decisão baseada em receipt stale.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            decision={"action": "test_action", "actor_ref": actor.to_dict(),
                      "selected_affordance_id": "affordance:current"},
            causal_payload={"decision_source": {"kind": "provider",
                                                "receipt_event_id": receipt.id}},
            cause_ids=(receipt.id,),
        )

    assert [event.id for event in world.events] == [receipt.id]


def test_validate_history_rejects_a_transition_authored_on_an_earlier_day():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    decision = record_event(
        world, "authorship_decided", "A escolha ocorreu no dia zero.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision={"action": "test_action", "actor_ref": actor.to_dict(),
                  "selected_affordance_id": "affordance:current"},
    )
    world.clock = world.clock.advance(1)
    deterministic = record_event(
        world, "deterministic_transition", "Fato para adulterar no teste.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind="test_owner", owner_id="one", aspect="value",
                           before="0", after="1"),),
        cause_ids=(decision.id,),
    )
    world.events[-1] = deterministic.model_copy(update={
        "causal_origin": CausalOrigin.ACTOR_DECISION,
        "causal_payload": {"decision_event_id": decision.id,
                           "actor_ref": actor.to_dict(),
                           "selected_affordance_id": "affordance:current"},
    })

    with pytest.raises(ValueError, match="same-day real decision cause"):
        validate_history(world.events, world.clock.absolute_day)


def test_validate_history_rejects_a_forward_causal_link():
    world = create_medieval_world(73)
    first = record_event(world, "first_fact", "Fato anterior.")
    effect = record_event(world, "effect", "Efeito ligado a fato anterior.",
                          cause_ids=(first.id,))
    future = record_event(world, "future_fact", "Fato posterior.")
    world.events[effect.sequence - 1] = effect.model_copy(update={
        "causal_links": (CausalLink(
            id=f"{effect.id}:cause:0", event_id=effect.id,
            cause_event_id=future.id, relation=CausalRelation.TRIGGERED_BY,
        ),),
    })

    with pytest.raises(ValueError, match="causal links must point to an earlier event"):
        validate_history(world.events, world.clock.absolute_day)


def test_validate_history_rejects_tampered_actor_decision_source():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    decision = record_event(
        world, "authorship_decided", "Escolha via API.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision={"action": "test_action", "actor_ref": actor.to_dict(),
                  "selected_affordance_id": "affordance:current"},
    )
    world.events[-1] = decision.model_copy(update={"causal_payload": None})

    with pytest.raises(ValueError, match="requires a decision source"):
        validate_history(world.events, world.clock.absolute_day)

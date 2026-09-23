import pytest

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
        fact_kind=FactKind.DECISION,
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
        fact_kind=FactKind.DECISION,
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

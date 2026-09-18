"""Generic contract of InstitutionalDecisionTurn, independent of any one
vertical's semantics -- exercised through toy adapters, not real options."""

import json

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.institutional_decision_turn import (
    DECLINED_DECISION_EVENT_TYPE,
    DiscretionaryAdapter,
    review_institutional_decision_turn,
    review_institutional_decision_turn_with_provider,
)

AUREN = EntityRef("polity", "auren")


def enable(world, *, per_step=8, maximum=1000):
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": per_step, "ai_max_calls": maximum})
    return world


def provider(monkeypatch, answer):
    async def call_llm_json(prompt, *args, **kwargs):
        return answer
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


def toy_adapter(name, *, ids=("toy:1",), claim=None, executed=None):
    """A minimal, self-contained adapter with no real domain meaning."""
    class ToyOption:
        def __init__(self, id_):
            self.id = id_

        def decision(self):
            return {"action": name, "toy_id": self.id}

    def options_fn(world, actor):
        return tuple(ToyOption(i) for i in ids) if actor == AUREN else ()

    def execute_fn(world, actor, option_id, decision_event_id):
        if executed is not None:
            executed.append(option_id)

    return DiscretionaryAdapter(
        name=name, options_fn=options_fn, label_fn=lambda option: f"Fazer {option.id}.",
        causes_fn=lambda world, option: (), execute_fn=execute_fn,
        claim_fn=(lambda option: (claim, option.id)) if claim else (lambda option: None))


async def test_two_adapters_compose_into_one_menu_and_one_provider_call(monkeypatch):
    world = enable(create_medieval_world(73))
    calls = []

    async def call_llm_json(prompt, *args, **kwargs):
        calls.append(prompt)
        payload = json.loads(prompt[prompt.index("{"):])
        assert {c["id"] for c in payload["choices"]} == {"a:1", "b:1"}
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)

    adapters = (toy_adapter("a", ids=("a:1",)), toy_adapter("b", ids=("b:1",)))
    claims, covered = await review_institutional_decision_turn(world, AUREN, adapters)

    assert len(calls) == 1, "one composed consultation, not one per adapter"
    assert covered is True
    assert claims == {}


async def test_situation_fn_overrides_the_default_actor_dossier(monkeypatch):
    world = enable(create_medieval_world(73))
    seen = {}

    async def call_llm_json(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        seen["situation"] = payload["situation"]
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    adapters = (toy_adapter("a", ids=("a:1", "a:2")),)

    def situation_fn(world, actor, options):
        return {"only_these_ids": sorted(option.id for option in options)}

    await review_institutional_decision_turn(world, AUREN, adapters, situation_fn=situation_fn)

    assert seen["situation"] == {"only_these_ids": ["a:1", "a:2"]}
    assert "known_settlement_reports" not in seen["situation"], \
        "a custom situation_fn must fully replace the generic dossier, not merge with it"


async def test_composed_situation_namespaces_one_fragment_per_family(monkeypatch):
    world = enable(create_medieval_world(73))
    seen = {}

    async def call_llm_json(prompt, *args, **kwargs):
        seen["situation"] = json.loads(prompt[prompt.index("{"):])["situation"]
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)

    def fragment(label):
        return lambda world, actor, options: {label: sorted(option.id for option in options)}

    a = DiscretionaryAdapter(name="a1", family="fam_a", options_fn=toy_adapter("a", ids=("a:1",)).options_fn,
                             label_fn=lambda option: "a", causes_fn=lambda world, option: (),
                             execute_fn=lambda *args: None, situation_fn=fragment("mine"))
    b = DiscretionaryAdapter(name="b1", family="fam_b", options_fn=toy_adapter("b", ids=("b:1",)).options_fn,
                             label_fn=lambda option: "b", causes_fn=lambda world, option: (),
                             execute_fn=lambda *args: None, situation_fn=fragment("mine"))

    await review_institutional_decision_turn(world, AUREN, (a, b))

    # Each family keeps its own key, so identical fragment shapes cannot
    # overwrite one another, and the generic dossier is still the base.
    assert seen["situation"]["fam_a"] == {"mine": ["a:1"]}
    assert seen["situation"]["fam_b"] == {"mine": ["b:1"]}
    assert "known_settlement_reports" in seen["situation"]


async def test_claim_fn_none_never_appears_in_claims(monkeypatch):
    world = enable(create_medieval_world(73))
    provider(monkeypatch, {"selected_id": ai_decider.NO_ACTION})
    adapters = (toy_adapter("no_claim", claim=None),)

    claims, covered = await review_institutional_decision_turn(world, AUREN, adapters)

    assert claims == {} and covered is True


async def test_claim_fn_aggregates_by_kind_across_adapters(monkeypatch):
    world = enable(create_medieval_world(73))
    provider(monkeypatch, {"selected_id": ai_decider.NO_ACTION})
    adapters = (toy_adapter("x", ids=("x:1", "x:2"), claim="kind_x"),
               toy_adapter("y", ids=("y:1",), claim="kind_y"))

    claims, covered = await review_institutional_decision_turn(world, AUREN, adapters)

    assert claims == {"kind_x": {"x:1", "x:2"}, "kind_y": {"y:1"}}
    assert covered is True


async def test_unavailable_provider_claims_nothing_generic(monkeypatch):
    world = enable(create_medieval_world(73))
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    adapters = (toy_adapter("x", claim="kind_x"),)

    claims, covered = await review_institutional_decision_turn(world, AUREN, adapters)

    assert claims == {} and covered is False


async def test_selected_option_dispatches_to_its_own_adapter_executor(monkeypatch):
    world = enable(create_medieval_world(73))
    executed = []
    adapters = (toy_adapter("a", ids=("a:1",), executed=executed),
               toy_adapter("b", ids=("b:1",), executed=executed))
    provider(monkeypatch, {"selected_id": "b:1"})

    claims, covered = await review_institutional_decision_turn(world, AUREN, adapters)

    assert executed == ["b:1"], "only the chosen option's own adapter executes"
    decision = next(e for e in world.events if e.event_type == "institutional_decision_turn_decided")
    assert decision.fact_kind == FactKind.DECISION
    assert decision.decision == {"action": "b", "toy_id": "b:1"}


async def test_no_action_records_decision_only_when_actually_askable(monkeypatch):
    # Deliberate refusal: the actor was consultable, was asked, and answered
    # NO_ACTION -- a decision fact must exist, carrying the menu's causes and
    # the affordances it turned down.
    world = enable(create_medieval_world(73))
    provider(monkeypatch, {"selected_id": ai_decider.NO_ACTION})
    adapters = (toy_adapter("a", ids=("a:1",)), toy_adapter("b", ids=("b:1",)))

    claims, covered = await review_institutional_decision_turn(world, AUREN, adapters)

    assert covered is True
    declined = [e for e in world.events if e.event_type == DECLINED_DECISION_EVENT_TYPE]
    assert len(declined) == 1
    decision = declined[0]
    assert decision.fact_kind == FactKind.DECISION
    assert decision.causal_origin == CausalOrigin.ACTOR_DECISION
    assert decision.deltas == ()
    assert decision.decision["declined_option_ids"] == ("a:1", "b:1")
    assert decision.decision["actor_ref"] == AUREN.to_dict()
    # ai_decision_declined stays the receipt of the consultation, untouched.
    assert any(e.event_type == "ai_decision_declined" for e in world.events)

    # Technical failure: no provider means the actor was never actually
    # consulted -- no decision of either kind, and nothing is claimed.
    world2 = enable(create_medieval_world(73))
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    adapters2 = (toy_adapter("a", ids=("a:1",), claim="kind_a"),)

    claims2, covered2 = await review_institutional_decision_turn(world2, AUREN, adapters2)

    assert claims2 == {} and covered2 is False
    assert not any(e.event_type == DECLINED_DECISION_EVENT_TYPE for e in world2.events)
    assert not any(e.fact_kind == FactKind.DECISION for e in world2.events)


async def test_with_provider_rotates_and_only_counts_polities_with_options(monkeypatch):
    world = enable(create_medieval_world(73))
    provider(monkeypatch, {"selected_id": ai_decider.NO_ACTION})
    adapters = (toy_adapter("only_auren", claim="k"),)

    claims, covered = await review_institutional_decision_turn_with_provider(world, adapters)

    assert covered == {AUREN}
    assert claims == {"k": {"toy:1"}}

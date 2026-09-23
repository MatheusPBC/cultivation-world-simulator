"""Generic contract of InstitutionalDecisionTurn, independent of any one
vertical's semantics -- exercised through toy adapters, not real options."""

import json

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.institutional_decision_turn import (
    DECLINED_DECISION_EVENT_TYPE,
    DiscretionaryAdapter,
    NO_AFFORDANCE_EVENT_TYPE,
    STALE_AFFORDANCE_EVENT_TYPE,
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


async def test_no_affordance_records_deterministic_receipt_without_provider(monkeypatch):
    world = enable(create_medieval_world(73))
    called = False

    async def call_llm_json(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("no-affordance turns must not call the provider")

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    adapter = toy_adapter("only_other_actor")

    claims, covered = await review_institutional_decision_turn(world, EntityRef("polity", "other"), (adapter,))

    assert claims == {} and covered is False and called is False
    receipt = next(event for event in world.events if event.event_type == NO_AFFORDANCE_EVENT_TYPE)
    assert receipt.fact_kind == FactKind.OCCURRENCE
    assert receipt.deltas == ()
    assert "polity:other" in receipt.content


async def test_claim_fn_aggregates_by_kind_across_adapters(monkeypatch):
    world = enable(create_medieval_world(73))
    provider(monkeypatch, {"selected_id": ai_decider.NO_ACTION})
    adapters = (toy_adapter("x", ids=("x:1", "x:2"), claim="kind_x"),
               toy_adapter("y", ids=("y:1",), claim="kind_y"))

    claims, covered = await review_institutional_decision_turn(world, AUREN, adapters)

    assert claims == {"kind_x": {"x:1", "x:2"}, "kind_y": {"y:1"}}
    assert covered is True


async def test_unavailable_provider_requires_a_paused_decision(monkeypatch):
    world = enable(create_medieval_world(73))
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    adapters = (toy_adapter("x", claim="kind_x"),)

    with pytest.raises(ProviderDecisionRequired):
        await review_institutional_decision_turn(world, AUREN, adapters)


async def test_selected_option_dispatches_to_its_own_adapter_executor(monkeypatch):
    world = enable(create_medieval_world(73))
    executed = []
    recompositions = {"a": 0, "b": 0}
    a = toy_adapter("a", ids=("a:1",), executed=executed)
    b = toy_adapter("b", ids=("b:1",), executed=executed)
    adapters = tuple(
        DiscretionaryAdapter(
            name=adapter.name,
            options_fn=lambda world, actor, key=adapter.name, fn=adapter.options_fn:
                (recompositions.__setitem__(key, recompositions[key] + 1) or fn(world, actor)),
            label_fn=adapter.label_fn, causes_fn=adapter.causes_fn,
            execute_fn=adapter.execute_fn, claim_fn=adapter.claim_fn,
        )
        for adapter in (a, b)
    )
    provider(monkeypatch, {"selected_id": "b:1"})

    claims, covered = await review_institutional_decision_turn(world, AUREN, adapters)

    assert executed == ["b:1"], "only the chosen option's own adapter executes"
    assert recompositions == {"a": 1, "b": 2}, \
        "revalidation recomposes only the selected option's owner adapter"
    decision = next(e for e in world.events if e.event_type == "institutional_decision_turn_decided")
    assert decision.fact_kind == FactKind.DECISION
    assert decision.decision == {"action": "b", "toy_id": "b:1"}


async def test_selected_id_that_becomes_stale_pauses_ai_without_material_mutation(monkeypatch):
    world = enable(create_medieval_world(73))
    state = {"open": True}
    executed = []

    class Option:
        id = "volatile:1"

        def decision(self):
            return {"action": "volatile", "selected_affordance_id": self.id}

    def options_fn(_world, actor):
        return (Option(),) if actor == AUREN and state["open"] else ()

    async def call_llm_json(prompt, *args, **kwargs):
        state["open"] = False
        return {"selected_id": "volatile:1"}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    adapter = DiscretionaryAdapter(name="volatile", options_fn=options_fn,
                                   label_fn=lambda option: "Opção volátil.",
                                   causes_fn=lambda world, option: (),
                                   execute_fn=lambda *args: executed.append(True))

    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, AUREN, (adapter,))

    assert executed == []
    assert not any(event.event_type == STALE_AFFORDANCE_EVENT_TYPE for event in world.events)
    assert not any(event.event_type == "institutional_decision_turn_decided" for event in world.events)


async def test_invented_id_is_rejected_without_recomposing_any_owner(monkeypatch):
    world = enable(create_medieval_world(73))
    recompositions = {"a": 0, "b": 0}
    executed = []

    def adapter(name, option_id):
        def options_fn(_world, _actor):
            recompositions[name] += 1
            class Option:
                id = option_id

                def decision(self):
                    return {"action": name, "selected_affordance_id": self.id}
            return (Option(),)

        return DiscretionaryAdapter(
            name=name, options_fn=options_fn, label_fn=lambda option: option.id,
            causes_fn=lambda *_args: (),
            execute_fn=lambda *_args: executed.append(name))

    provider(monkeypatch, {"selected_id": "invented:999"})

    with pytest.raises(ProviderDecisionRequired, match="selected affordance is unknown"):
        await review_institutional_decision_turn(
            world, AUREN, (adapter("a", "a:1"), adapter("b", "b:1")))

    assert recompositions == {"a": 1, "b": 1}
    assert executed == []
    assert not any(event.deltas for event in world.events)
    assert not any(event.event_type == "institutional_decision_turn_decided"
                   for event in world.events)


async def test_owner_rejection_pauses_ai_instead_of_becoming_silent_no_action(monkeypatch):
    world = enable(create_medieval_world(73))
    provider(monkeypatch, {"selected_id": "rejected:1"})

    class Option:
        id = "rejected:1"

        def decision(self):
            return {"action": "rejected", "selected_affordance_id": self.id}

    adapter = DiscretionaryAdapter(
        name="rejected", options_fn=lambda _world, _actor: (Option(),),
        label_fn=lambda _option: "Opção rejeitada.", causes_fn=lambda *_args: (),
        execute_fn=lambda *_args: (_ for _ in ()).throw(ValueError("owner rejected")),
    )

    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, AUREN, (adapter,))


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

    # Technical failure now aborts the AI candidate; the runtime owns the
    # pause/error surface instead of silently treating it as a missed turn.
    world2 = enable(create_medieval_world(73))
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    adapters2 = (toy_adapter("a", ids=("a:1",), claim="kind_a"),)

    with pytest.raises(ProviderDecisionRequired):
        await review_institutional_decision_turn(world2, AUREN, adapters2)
    assert not any(e.event_type == DECLINED_DECISION_EVENT_TYPE for e in world2.events)
    assert not any(e.fact_kind == FactKind.DECISION for e in world2.events)


async def test_with_provider_rotates_and_only_counts_polities_with_options(monkeypatch):
    world = enable(create_medieval_world(73))
    provider(monkeypatch, {"selected_id": ai_decider.NO_ACTION})
    adapters = (toy_adapter("only_auren", claim="k"),)

    claims, covered = await review_institutional_decision_turn_with_provider(world, adapters)

    assert covered == {AUREN}
    assert claims == {"k": {"toy:1"}}

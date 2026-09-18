"""The composed monthly turn: one consultation per institution, every family."""

import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.institutional_agenda import (monthly_actors, monthly_adapters,
                                                   review_monthly_institutional_turn)
from src.sim.medieval.institutional_decision_turn import _by_id
from tests.test_medieval_concurrent_civil_decision import civil_pressure_world

AUREN = EntityRef("polity", "auren")


def _provider(monkeypatch, answer, prompts):
    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        return {"selected_id": answer}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


def _actor_of(prompt):
    return json.dumps(json.loads(prompt[prompt.index("{"):])["you_are"], sort_keys=True)


def test_one_menu_carries_several_families_at_once():
    world = civil_pressure_world()
    by_id = _by_id(world, AUREN, monthly_adapters())

    assert len({adapter.family_key() for adapter, _ in by_id.values()}) > 1, \
        "the composed menu must merge families, not show one vertical at a time"


async def test_each_institution_answers_at_most_one_consultation_per_boundary(monkeypatch):
    world = civil_pressure_world()
    prompts = []
    _provider(monkeypatch, ai_decider.NO_ACTION, prompts)

    await review_monthly_institutional_turn(world)

    assert prompts, "the pressured world must offer at least one institution a menu"
    per_actor = {}
    for prompt in prompts:
        per_actor[_actor_of(prompt)] = per_actor.get(_actor_of(prompt), 0) + 1
    assert max(per_actor.values()) == 1, f"an institution was consulted more than once: {per_actor}"


async def test_the_single_decision_names_one_affordance_and_runs_its_own_executor(monkeypatch):
    world = civil_pressure_world()
    by_id = _by_id(world, AUREN, monthly_adapters())
    chosen = sorted(by_id)[0]
    prompts = []
    _provider(monkeypatch, chosen, prompts)

    claims, covered = await review_monthly_institutional_turn(world)

    assert AUREN in covered
    decisions = [event for event in world.events
                 if event.fact_kind == FactKind.DECISION
                 and event.event_type == "institutional_decision_turn_decided"]
    assert len(decisions) == 1
    assert decisions[0].decision == by_id[chosen][1].decision()


async def test_never_asked_actors_claim_nothing_so_automatic_passes_still_run(monkeypatch):
    world = civil_pressure_world()
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)

    claims, covered = await review_monthly_institutional_turn(world)

    assert claims == {} and covered == set()


def test_every_actor_of_every_family_is_included_once():
    world = civil_pressure_world()
    actors = monthly_actors(world)

    assert len(actors) == len(set(actors)), "an actor must not appear twice in one boundary"
    assert AUREN in actors

"""Fail-closed audit of the knowledge and intrigue verticals in provider mode.

Research sponsorship, technology sale, technique copying, technology theft and
espionage all reach the actor through the same composed institutional turn.
This module checks the contract that turn promises for each of them: when the
selected affordance no longer exists at revalidation, or the canonical owner
rejects it, an ``ai_enabled`` world must stop with ``ProviderDecisionRequired``
and must not keep any material mutation of the vertical it selected.
"""

import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.espionage import espionage_adapters, espionage_options
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn
from src.sim.medieval.persistence import world_snapshot
from src.sim.medieval.research_policy import (execute_research_option, research_adapters,
                                              research_options)
from src.sim.medieval.technique_copy_policy import technique_copy_adapters
from src.sim.medieval.technique_copy import technique_copy_options
from src.sim.medieval.technology_sale import (record_technology_sale_request,
                                              technology_sale_acceptance_options,
                                              technology_sale_options)
from src.sim.medieval.technology_sale_policy import technology_sale_adapters
from src.sim.medieval.technology_theft import technology_theft_adapters, technology_theft_options

from tests.test_medieval_espionage import prepared_world as espionage_world
from tests.test_medieval_technique_copy import access_world
from tests.test_medieval_technology_sale import researched_world
from tests.test_medieval_technology_theft import prepared_world as theft_world


AUREN = EntityRef("polity", "auren")
ESCARLIA = EntityRef("polity", "escarlia")


def test_research_executor_requires_the_selected_current_decision():
    world = create_medieval_world(73)
    option = research_options(world, AUREN)[0]
    unrelated = record_event(
        world, "unrelated_decision", "Outra decisão.", fact_kind=FactKind.DECISION,
        decision={"action": "maintain", "actor_ref": AUREN.to_dict(),
                  "selected_affordance_id": "other:affordance"})
    before = world_snapshot(world)

    with pytest.raises(ValueError, match="current actor decision"):
        execute_research_option(world, AUREN, option.id, unrelated.id)

    assert world_snapshot(world) == before
    selected = record_event(
        world, "institutional_decision_turn_decided", "Escolher pesquisa.",
        fact_kind=FactKind.DECISION, decision=option.decision())
    execute_research_option(world, AUREN, option.id, selected.id)

    project = next(iter(world.research.projects.values()))
    started = world.events[-1]
    assert project.sponsor_decision_id == started.causal_links[0].cause_event_id
    sponsor = next(event for event in world.events if event.id == project.sponsor_decision_id)
    assert selected.id in {link.cause_event_id for link in sponsor.causal_links}


def enable_ai(world):
    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 1000})
    return world


def answer_with(monkeypatch, label_prefix, sabotage):
    """A provider that picks one labelled affordance and, in the same call,
    lets the world change underneath it -- exactly the race the composed turn
    must catch when it recomposes the menu before executing.

    Returns the list of IDs it actually chose.  ``select_option`` converts any
    exception raised here into ``ProviderDecisionRequired``, so a test that
    never found its own affordance would otherwise pass for the wrong reason;
    every test below asserts the choice was really offered and taken.
    """
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    chosen = []

    async def answer(prompt, *_args, **_kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        picked = next((item["id"] for item in payload["choices"]
                       if item["label"].startswith(label_prefix)), None)
        if picked is None:
            return {"selected_id": ai_decider.NO_ACTION}
        chosen.append(picked)
        sabotage()
        return {"selected_id": picked}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", answer)
    return chosen


async def test_stale_research_sponsorship_pauses_without_authorizing(monkeypatch):
    world = enable_ai(create_medieval_world(73))
    option = research_options(world, AUREN)[0]

    def sabotage():
        account = world.economy.accounts[option.account_id]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})

    chosen = answer_with(monkeypatch, "Financiar pesquisa de ", sabotage)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, AUREN, research_adapters())
    assert len(chosen) == 1
    assert not world.research.projects
    assert not [item for item in world.events if item.event_type.startswith("research_")]


async def test_owner_rejection_of_research_leaves_no_authorization_receipt(monkeypatch):
    """The owner is the only judge of its own terms.  Whatever makes
    ``start_research`` refuse, the refusal must leave the world exactly as the
    actor found it and reach the simulator as a decision wait."""
    world = enable_ai(create_medieval_world(73))

    def reject(*_args, **_kwargs):
        raise ValueError("research unavailable: owner rejected the terms")

    monkeypatch.setattr("src.sim.medieval.research_policy.start_research", reject)
    chosen = answer_with(monkeypatch, "Financiar pesquisa de ", lambda: None)
    events_before = len(world.events)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, AUREN, research_adapters())
    assert len(chosen) == 1
    assert not world.research.projects
    decisions = [item.event_type for item in world.events[events_before:]
                 if item.event_type in {"research_authorized", "research_accepted"}]
    assert decisions == []


async def test_stale_technology_sale_acceptance_pauses_without_paying(monkeypatch):
    world = enable_ai(researched_world())
    option = technology_sale_options(world, AUREN)[0]
    record_technology_sale_request(world, AUREN, option.id)
    assert technology_sale_acceptance_options(world, ESCARLIA)
    balances = {key: value.balance for key, value in world.economy.accounts.items()}

    def sabotage():
        account = world.economy.accounts[option.buyer_account_id]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})

    chosen = answer_with(monkeypatch, "Aceitar venda de técnica", sabotage)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, ESCARLIA, technology_sale_adapters())
    assert len(chosen) == 1
    assert not world.knowledge.knows(AUREN, "metallurgy")
    assert {key: value.balance for key, value in world.economy.accounts.items()
            if key != option.buyer_account_id} == {key: value for key, value in balances.items()
                                                   if key != option.buyer_account_id}
    assert not [item for item in world.events if item.event_type == "technology_sale_completed"]


async def test_a_selected_purchase_request_is_materialized_by_its_own_decision(monkeypatch):
    """The buyer branch has no executor: its dated decision event is the
    request the holder later answers.  Locking this in keeps the deliberate
    no-op from being read as a turn that silently did nothing."""
    world = enable_ai(researched_world())
    assert technology_sale_options(world, AUREN)

    chosen = answer_with(monkeypatch, "Comprar técnica observada", lambda: None)
    await review_institutional_decision_turn(world, AUREN, technology_sale_adapters())
    assert len(chosen) == 1
    assert technology_sale_acceptance_options(world, ESCARLIA)
    assert not world.knowledge.knows(AUREN, "metallurgy")
    assert not [item for item in world.events if item.event_type == "payment_completed"]


async def test_stale_technique_copy_pauses_without_opening_dated_work(monkeypatch):
    world, _sighting, repair = access_world()
    enable_ai(world)
    assert technique_copy_options(world, AUREN)

    chosen = answer_with(monkeypatch, "Copiar a técnica observada",
                lambda: world.economy.payrolls.pop(repair.id))
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, AUREN, technique_copy_adapters())
    assert len(chosen) == 1
    assert not world.research.technique_copies
    assert not world.knowledge.knows(AUREN, "metallurgy")


async def test_stale_technology_theft_pauses_without_learning(monkeypatch):
    world, _agent = theft_world()
    enable_ai(world)
    assert technology_theft_options(world, AUREN)

    chosen = answer_with(monkeypatch, "Tentar obter a técnica ",
                world.knowledge.technology_sightings.clear)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, AUREN, technology_theft_adapters())
    assert len(chosen) == 1
    assert not world.knowledge.technology_theft_findings
    assert not world.knowledge.knows(AUREN, "metallurgy")


async def test_stale_espionage_pauses_without_recording_a_finding(monkeypatch):
    world, agent, _option = espionage_world()
    enable_ai(world)
    assert espionage_options(world, AUREN)

    def sabotage():
        world.society.characters[agent.id] = world.society.characters[agent.id].model_copy(
            update={"location_id": "auren-alta"})

    chosen = answer_with(monkeypatch, "Enviar agente para obter", sabotage)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, AUREN, espionage_adapters())
    assert len(chosen) == 1
    assert not world.knowledge.espionage_findings


async def test_simulator_discards_the_whole_candidate_when_the_owner_rejects(monkeypatch):
    """End to end: the wait reaches ``MedievalSimulator`` and the published
    world keeps nothing of the failed month.

    The engine runs the turn on its own isolated candidate, so the rejection
    is injected at the canonical owner rather than by mutating this world.
    """
    world, _sighting, _repair = access_world(progress=False)
    enable_ai(world)
    before = world_snapshot(world)

    def reject(*_args, **_kwargs):
        raise ValueError("technique copy option is stale or unknown")

    monkeypatch.setattr("src.sim.medieval.technique_copy_policy.open_technique_copy", reject)
    chosen = answer_with(monkeypatch, "Copiar a técnica observada", lambda: None)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await MedievalSimulator(world).step()
    assert len(chosen) == 1
    assert world_snapshot(world) == before

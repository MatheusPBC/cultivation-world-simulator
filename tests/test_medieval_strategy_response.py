"""A known occupation may create intent, never an automatic army."""

import asyncio
import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.force import raise_options
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.strategy_response import (defense_action_options, defense_adoption_options,
                                                 review_strategy_responses_with_provider)


OWNER = EntityRef("polity", "auren")
OCCUPIER = EntityRef("polity", "escarlia")
SOURCE = "campomanso"
TARGET = "pedraclara"


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def occupied_response_world():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == SOURCE)
    soldiers_id = f"pop:{SOURCE}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 20})
    settlement = world.society.settlements[TARGET]
    occupation = record_event(
        world, "test_strategy_occupation", "Fixture factual de ocupação observável.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("settlement", TARGET, "occupier_id", None, OCCUPIER.id),))
    world.society.set_occupation(TARGET, OCCUPIER.id)
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    report = world.knowledge.settlement_report(OWNER, TARGET)
    assert report is not None and report.occupier_id == OCCUPIER.id
    return world, occupation.id, report


def choose_first(monkeypatch):
    async def call_llm_json(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


def test_provider_adopts_then_existing_raise_marches_with_causal_chain(monkeypatch):
    world, occupation_id, report = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2, "ai_max_calls": 10})
    choose_first(monkeypatch)

    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))
    objective = world.strategy.objectives[plan.objective_id]
    assert objective.kind == "defend_occupied_settlement" and plan.stage == "adopted"
    adoption = next(event for event in world.events if event.event_type == "strategy_defense_adopted")
    assert report.event_id in {link.cause_event_id for link in adoption.causal_links}
    assert occupation_id not in {link.cause_event_id for link in adoption.causal_links}
    assert not world.society.detachments

    due = tick(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    raised = next(item for item in world.society.detachments.values() if item.owner_ref == OWNER)
    assert raised.stage == "marching" and raised.destination_id == TARGET
    assert world.strategy.plans[plan.id].stage == "closed"
    force_decision = next(event for event in world.events if event.event_type == "strategy_defense_force_decided")
    material = next(event for event in world.events if event.event_type == "detachment_raised")
    assert force_decision.id in {link.cause_event_id for link in material.causal_links}
    assert all(delta.owner_kind not in {"stock", "account", "detachment"} for delta in adoption.deltas)


def test_missing_stale_forged_or_no_action_never_adopts(monkeypatch):
    empty = create_medieval_world(73)
    assert not defense_adoption_options(empty, OWNER)

    world, _, _ = occupied_response_world()
    option = defense_adoption_options(world, OWNER)[0]
    before = world_snapshot(world)
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def forged(prompt, *args, **kwargs):
        return {"selected_id": option.id + ":forged"}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", forged)
    assert not asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    assert not world.strategy.plans and world_snapshot(world)["society"] == before["society"]

    silent, _, _ = occupied_response_world()
    silent.config = silent.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})

    async def no_action(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    assert not asyncio.run(review_strategy_responses_with_provider(silent, allow_adoptions=True))
    assert not silent.strategy.plans

    stale, _, _ = occupied_response_world()
    stale.clock = stale.clock.advance(31)
    assert not defense_adoption_options(stale, OWNER)


def test_saved_plan_and_changed_authority_route_or_occupation_block_executor_atomically(tmp_path, monkeypatch):
    def saved_adopted(label):
        world, _, _ = occupied_response_world()
        world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2, "ai_max_calls": 10})
        choose_first(monkeypatch)
        asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
        plan = next(iter(world.strategy.plans.values()))
        path = tmp_path / f"strategy-response-{label}.mws"
        save_world(world, path)
        restored = load_world(path)
        assert world_snapshot(load_world(path)) == world_snapshot(restored)
        return restored, restored.strategy.plans[plan.id]

    world, plan = saved_adopted("occupation")

    # The provider saw a real raise affordance, but the canonical condition
    # changed before its selected ID reached the force owner.
    async def close_occupation_then_choose(prompt, *args, **kwargs):
        world.society.set_occupation(TARGET, None)
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", close_occupation_then_choose)
    due = tick(world)
    before = world_snapshot(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    assert world.strategy.plans[plan.id].stage == "closed"
    assert not world.society.detachments
    assert world_snapshot(world)["economy"] == before["economy"]
    assert not defense_action_options(world, OWNER, plan.id)

    authority_world, authority_plan = saved_adopted("authority")

    async def remove_authority_then_choose(prompt, *args, **kwargs):
        office = authority_world.authority.offices["office:polity:auren"]
        authority_world.authority.offices[office.id] = office.model_copy(
            update={"scopes": tuple(scope for scope in office.scopes if scope != "military")})
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", remove_authority_then_choose)
    authority_due = tick(authority_world)
    authority_economy = world_snapshot(authority_world)["economy"]
    assert asyncio.run(review_strategy_responses_with_provider(authority_world, authority_due))
    assert authority_world.strategy.plans[authority_plan.id].stage == "blocked"
    assert not authority_world.society.detachments
    assert world_snapshot(authority_world)["economy"] == authority_economy

    route_world, route_plan = saved_adopted("route")
    original = defense_action_options(route_world, OWNER, route_plan.id)[0]

    async def close_selected_route_then_choose(prompt, *args, **kwargs):
        for route_id in original.route_ids:
            route_world.map.routes[route_id].update_runtime(enabled=False)
        return {"selected_id": original.id}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", close_selected_route_then_choose)
    route_due = tick(route_world)
    route_economy = world_snapshot(route_world)["economy"]
    assert asyncio.run(review_strategy_responses_with_provider(route_world, route_due))
    assert route_world.strategy.plans[route_plan.id].stage == "blocked"
    assert not route_world.society.detachments
    assert world_snapshot(route_world)["economy"] == route_economy

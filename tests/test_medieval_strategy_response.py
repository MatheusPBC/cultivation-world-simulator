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
from src.sim.medieval.field_engagement import _fatigue_level
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
    assert world.strategy.plans[plan.id].stage == "mobilized"
    assert world.strategy.plans[plan.id].detachment_id == raised.id
    force_decision = next(event for event in world.events if event.event_type == "strategy_defense_force_decided")
    material = next(event for event in world.events if event.event_type == "detachment_raised")
    assert force_decision.id in {link.cause_event_id for link in material.causal_links}
    assert all(delta.owner_kind not in {"stock", "account", "detachment"} for delta in adoption.deltas)


def test_defense_menu_can_choose_sustained_column_with_real_daily_rations(monkeypatch, tmp_path):
    world, _, _ = occupied_response_world()
    stock = next(item for item in world.economy.stocks.values()
                 if item.owner_ref == OWNER and item.location_id == SOURCE)
    before_food = stock.goods.get("food", 0)
    premise = record_event(
        world, "test_defense_food_premise", "Premissa factual de estoque para expedição prolongada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("stock", stock.id, "food", before_food, before_food + 3000),))
    world.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, "food": before_food + 3000},
        "last_event_ids": {**stock.last_event_ids, "food": premise.id}})
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))
    options = defense_action_options(world, OWNER, plan.id)
    assert {item.days for item in options} == {10, 40}
    sustained = next(item for item in options if item.days == 40)

    async def choose_sustained(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        assert any("40 dias" in choice["label"] for choice in payload["choices"])
        return {"selected_id": sustained.id}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_sustained)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    column = world.society.detachments[world.strategy.plans[plan.id].detachment_id]
    assert column.provisions == column.count * 40
    raised = next(event for event in world.events if event.event_type == "detachment_raised")
    assert premise.id in {link.cause_event_id for link in raised.causal_links}
    assert world.economy.stocks[stock.id].goods["food"] == before_food + 3000 - column.provisions

    for _ in range(30):
        tick(world)
    current = world.society.detachments[column.id]
    assert current.stage == "present" and current.location_id == TARGET
    assert current.provisions == column.count * 10
    assert _fatigue_level(world, current) == 1
    assert sum(event.event_type == "detachment_supplied" and any(
        delta.owner_kind == "detachment" and delta.owner_id == column.id and delta.aspect == "provisions"
        for delta in event.deltas) for event in world.events) == 30
    path = tmp_path / "sustained-defense-column.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_mobilized_plan_survives_load_and_reconsiders_lost_column(monkeypatch, tmp_path):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    due = tick(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    plan = next(iter(world.strategy.plans.values()))
    assert plan.stage == "mobilized" and plan.detachment_id is not None
    assert world.agenda.get(f"strategy-response-review:{plan.id}").due_day == 31
    path = tmp_path / "mobilized-plan.mws"
    save_world(world, path)
    world = load_world(path)
    # Only dated force laws and the owner's own monthly observation run here;
    # no provider is asked to maintain or replace the army automatically.
    world.config = world.config.model_copy(update={"ai_enabled": False})
    for day in range(2, 32):
        due = tick(world)
        if day == 30:
            refresh_settlement_reports(world)
        if day == 31:
            assert world.strategy.plans[plan.id].stage == "mobilized"
            assert asyncio.run(review_strategy_responses_with_provider(world, due))
    current = world.strategy.plans[plan.id]
    assert world.society.detachments[plan.detachment_id].stage == "disbanded"
    assert current.stage == "adopted" and current.detachment_id is None
    assert current.blocker == "coluna indisponível; reconsiderar meios"
    assert world.agenda.get(f"strategy-response-review:{plan.id}").due_day == 32
    final_path = tmp_path / "reconsidered-plan.mws"
    save_world(world, final_path)
    assert world_snapshot(load_world(final_path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(final_path)["ok"] is True


@pytest.mark.parametrize("occupier_after", [None, OWNER.id])
def test_mobilized_plan_closes_only_after_own_fresh_report(monkeypatch, tmp_path, occupier_after):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    plan = next(iter(world.strategy.plans.values()))
    assert plan.stage == "mobilized"

    # The earlier column may lapse without supply. Resolve the occupation at
    # the observation boundary, as a separate explicit material fixture fact.
    assert world.strategy.plans[plan.id].stage == "mobilized"
    for day in range(2, 31):
        tick(world)
    end = record_event(
        world, "test_strategy_occupation_resolved", "Fixture factual do fim da ocupação estrangeira.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("settlement", TARGET, "occupier_id", OCCUPIER.id, occupier_after),))
    world.society.set_occupation(TARGET, occupier_after)
    refresh_settlement_reports(world)
    report = world.knowledge.settlement_report(OWNER, TARGET)
    assert report is not None and report.occupier_id == occupier_after
    events = world.event_index()
    frontier = [report.event_id]
    seen = set()
    while frontier:
        event_id = frontier.pop()
        if event_id in seen:
            continue
        seen.add(event_id)
        frontier.extend(link.cause_event_id for link in events[event_id].causal_links)
    assert end.id in seen

    due = tick(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    closed = world.strategy.plans[plan.id]
    assert closed.stage == "closed" and closed.detachment_id is None
    receipt = world.event_index()[closed.last_event_id]
    assert report.event_id in {link.cause_event_id for link in receipt.causal_links}
    path = tmp_path / "observed-campaign-end.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_reoccupation_after_clear_report_blocks_stale_closure(monkeypatch):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    plan = next(iter(world.strategy.plans.values()))
    record_event(world, "test_strategy_occupation_ended", "Fixture factual do fim da ocupação.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("settlement", TARGET, "occupier_id", OCCUPIER.id, None),))
    world.society.set_occupation(TARGET, None)
    for day in range(2, 31):
        tick(world)
        if day == 30:
            refresh_settlement_reports(world)
    assert world.knowledge.settlement_report(OWNER, TARGET).occupier_id is None
    record_event(world, "test_strategy_reoccupation", "Fixture factual de nova ocupação.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("settlement", TARGET, "occupier_id", None, OCCUPIER.id),))
    world.society.set_occupation(TARGET, OCCUPIER.id)

    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    current = world.strategy.plans[plan.id]
    assert current.stage == "blocked" and current.detachment_id == plan.detachment_id
    assert current.blocker == "relatório local contradito; aguardar nova observação"
    assert world.agenda.get(f"strategy-response-review:{plan.id}").due_day == 61
    world.strategy.validate(world)


def test_blocked_defense_reopens_when_material_means_return(monkeypatch, tmp_path):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))
    own_stocks = tuple(item for item in world.economy.stocks.values() if item.owner_ref == OWNER)
    original_food = {stock.id: stock.goods.get("food", 0) for stock in own_stocks}
    removed = record_event(
        world, "test_defense_food_unavailable", "Premissa material de falta de provisões.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(_delta("stock", stock.id, "food", original_food[stock.id], 0)
                     for stock in own_stocks))
    for stock in own_stocks:
        world.economy.stocks[stock.id] = stock.model_copy(update={
            "goods": {**stock.goods, "food": 0},
            "last_event_ids": {**stock.last_event_ids, "food": removed.id}})

    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    assert world.strategy.plans[plan.id].stage == "blocked"
    assert world.strategy.plans[plan.id].detachment_id is None
    assert world.agenda.get(f"strategy-response-review:{plan.id}").due_day == 31
    assert not defense_action_options(world, OWNER, plan.id)

    restored = record_event(
        world, "test_defense_food_restored", "Premissa material de novas provisões.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(_delta("stock", stock.id, "food", 0, original_food[stock.id] + 3000)
                     for stock in own_stocks), cause_ids=(removed.id,))
    for stock in own_stocks:
        current_stock = world.economy.stocks[stock.id]
        world.economy.stocks[stock.id] = current_stock.model_copy(update={
            "goods": {**current_stock.goods, "food": original_food[stock.id] + 3000},
            "last_event_ids": {**current_stock.last_event_ids, "food": restored.id}})
    for day in range(2, 31):
        tick(world)
        if day == 30:
            refresh_route_reports(world)
            refresh_settlement_reports(world)
    assert defense_action_options(world, OWNER, plan.id)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    current = world.strategy.plans[plan.id]
    assert current.stage == "mobilized" and current.detachment_id in world.society.detachments
    material = world.event_index()[world.society.detachments[current.detachment_id].last_event_id]
    assert restored.id in {link.cause_event_id for link in material.causal_links}
    path = tmp_path / "blocked-defense-resumed.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_defense_no_action_preserves_a_later_choice(monkeypatch):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))

    async def no_action(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    assert not asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    assert world.strategy.plans[plan.id].stage == "adopted"
    assert not world.society.detachments
    assert world.agenda.get(f"strategy-response-review:{plan.id}").due_day == 31

    for day in range(2, 31):
        tick(world)
        if day == 30:
            refresh_route_reports(world)
            refresh_settlement_reports(world)
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    assert world.strategy.plans[plan.id].stage == "mobilized"


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
    with pytest.raises(ai_decider.ProviderDecisionRequired):
        asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
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
    assert world.strategy.plans[plan.id].stage == "blocked"
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
    with pytest.raises(ai_decider.ProviderDecisionRequired):
        asyncio.run(review_strategy_responses_with_provider(route_world, route_due))
    assert route_world.strategy.plans[route_plan.id].stage == "adopted"
    assert not route_world.society.detachments
    assert world_snapshot(route_world)["economy"] == route_economy

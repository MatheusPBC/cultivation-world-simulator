"""A military research shortfall may invite, but never create, new soldiers."""

import asyncio
from copy import deepcopy

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _delta, monthly_workforce
from src.sim.medieval.events import record_event
from src.sim.medieval.force import raise_detachment, raise_options
from src.sim.medieval.institutional_agenda import monthly_actors
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import progress_research
from src.sim.medieval.research_policy import execute_research_option, research_options
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.strategy_response import review_strategy_responses_with_provider
from src.sim.medieval.workforce import (accept_workforce_transition, authorize_military_recruitment,
                                        military_recruitment_adapters, military_recruitment_options,
                                        refresh_workforce_notices,
                                        workforce_transition_options)
from tools.medieval_causal_audit import audit
from tests.test_medieval_strategy_response import (OWNER, SOURCE, TARGET, choose_first,
                                                   occupied_response_world, tick)


ACTOR = EntityRef("polity", "auren")
WORKPLACE = "pontenegro"


def _advance_dated(world, days):
    for _ in range(days):
        world.clock = world.clock.advance(1)
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))


def test_real_mobilization_can_create_research_demand_then_group_recruits(tmp_path):
    world = create_medieval_world(73)
    people_before = world.society.total_population
    research = next(option for option in research_options(world, ACTOR)
                    if option.technology_id == "field_drill")
    assert world.economy.stocks[research.stock_id].location_id == WORKPLACE
    research_decision = record_event(
        world, "research_option_decided", "Financiar pesquisa militar.",
        fact_kind=FactKind.DECISION, decision=research.decision())
    execute_research_option(world, ACTOR, research.id, research_decision.id)
    project = next(iter(world.research.projects.values()))

    # Every local soldier leaves via the ordinary force owner, with food and
    # wages; none is erased from Society to fake the research shortage.
    refresh_route_reports(world)
    local_soldiers = tuple(sorted(group.id for group in world.society.population.values()
                                  if group.settlement_id == WORKPLACE and group.occupation == "soldier"))
    for group_id in local_soldiers:
        option = next(item for item in raise_options(world, ACTOR)
                      if item.group_id == group_id and item.destination_id == "pedraclara")
        decision = record_event(world, "force_decided", "Mobilizar soldados locais.",
                                fact_kind=FactKind.DECISION, decision=option.decision())
        raise_detachment(world, ACTOR, option.id, decision.id)
    assert all(world.society.available_count(group_id) == 0 for group_id in local_soldiers)
    assert world.society.total_population == people_before

    _advance_dated(world, 30)
    progress_research(world, monthly_workforce(world))
    project = world.research.projects[project.id]
    assert project.stage == "blocked" and project.blocker == "labor"
    source = world.event_index()[project.last_event_id]
    assert any(delta.owner_kind == "research" and delta.owner_id == project.id
               and delta.aspect == "labor_shortfall" and delta.after == "2"
               for delta in source.deltas)
    refresh_workforce_notices(world)
    demand = next(report for report in world.knowledge.workforce_demand_reports.values()
                  if report.work_kind == "research" and report.work_id == project.id)
    assert demand.source_event_id == source.id and demand.target_occupation == "soldier"
    option = next(option for group in world.society.population.values()
                  for option in workforce_transition_options(world, group.id)
                  if world.knowledge.workforce_offer_notices[option.notice_id].demand_id == demand.id)
    notice = world.knowledge.workforce_offer_notices[option.notice_id]
    assert notice.count == 2
    sponsor = world.economy.accounts[demand.account_id]
    household = world.economy.accounts[f"household:{option.group_id}"]
    balances_before = sponsor.balance, household.balance

    stale = deepcopy(world)
    stale.clock = stale.clock.advance(1)
    stale_decision = record_event(
        stale, "workforce_transition_decided", "O grupo tentou aceitar o aviso vencido.",
        fact_kind=FactKind.DECISION, decision=option.decision(), cause_ids=(notice.event_id,))
    with pytest.raises(ValueError, match="stale|selected"):
        accept_workforce_transition(stale, option.id, decision_event_id=stale_decision.id)
    assert stale.society.workforce_transitions == world.society.workforce_transitions

    decision = record_event(world, "workforce_transition_decided", "O grupo aceitou a formação militar.",
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=(notice.event_id,))
    transition = accept_workforce_transition(world, option.id, decision_event_id=decision.id)
    assert world.economy.accounts[demand.account_id].balance == balances_before[0] - 2 * notice.stipend_per_person
    assert world.economy.accounts[f"household:{option.group_id}"].balance == (
        balances_before[1] + 2 * notice.stipend_per_person)
    assert transition.due_day == 60
    assert not workforce_transition_options(world, option.group_id)

    path = tmp_path / "military-recruitment-pending.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)
    for branch in (world, resumed):
        _advance_dated(branch, 30)
        assert transition.id not in branch.society.workforce_transitions
        soldiers = branch.society.population[transition.target_group_id]
        assert soldiers.occupation == "soldier" and soldiers.count == 2
        assert branch.society.total_population == people_before
        progress_research(branch, monthly_workforce(branch))
        assert branch.research.projects[project.id].completed_units == 1
        completed = next(event for event in branch.events
                         if event.event_type == "workforce_transition_completed")
        assert decision.id in {link.cause_event_id for link in completed.causal_links}
        save_world(branch, path)
        assert audit(path)["ok"] is True
    assert world_snapshot(resumed) == world_snapshot(world)


def test_defense_plan_can_recruit_after_soldiers_are_committed_elsewhere(monkeypatch, tmp_path):
    world, _, _ = occupied_response_world()
    people_before = world.society.total_population
    sources = {SOURCE, "pontenegro"}
    own_stocks = tuple(stock for stock in world.economy.stocks.values()
                       if stock.owner_ref == OWNER and stock.location_id in sources)
    account = next(item for _, item in sorted(world.economy.accounts.items())
                   if item.owner_ref == OWNER)
    premise = record_event(
        world, "test_campaign_recruitment_means", "Premissa material de provisões e caixa para expedições.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(*(_delta("stock", stock.id, "food", stock.goods.get("food", 0),
                         stock.goods.get("food", 0) + 12000) for stock in own_stocks),
                _delta("account", account.id, "balance", account.balance, account.balance + 5000)))
    for stock in own_stocks:
        world.economy.stocks[stock.id] = stock.model_copy(update={
            "goods": {**stock.goods, "food": stock.goods.get("food", 0) + 12000},
            "last_event_ids": {**stock.last_event_ids, "food": premise.id}})
    world.economy.accounts[account.id] = account.model_copy(update={
        "balance": account.balance + 5000, "last_event_id": premise.id})

    # The soldiers remain people, but are unavailable because the force owner
    # physically dispatched and paid their columns to another destination.
    soldiers = tuple(sorted(group.id for group in world.society.population.values()
                            if group.settlement_id in sources and group.occupation == "soldier"))
    for group_id in soldiers:
        option = next(item for item in raise_options(world, OWNER, days=90)
                      if item.group_id == group_id and item.destination_id == "portovelho")
        decision = record_event(world, "force_decided", "Empregar soldados em outra expedição.",
                                fact_kind=FactKind.DECISION, decision=option.decision())
        raise_detachment(world, OWNER, option.id, decision.id, days=90)
    assert all(world.society.available_count(group_id) == 0 for group_id in soldiers)
    assert world.society.total_population == people_before

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    assert world.strategy.plans[plan.id].stage == "blocked"
    assert world.strategy.plans[plan.id].detachment_id is None

    for day in range(2, 31):
        tick(world)
        if day == 30:
            refresh_route_reports(world)
            refresh_settlement_reports(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    source = world.event_index()[world.strategy.plans[plan.id].last_event_id]
    assert any(delta.owner_kind == "military_recruitment" and delta.aspect == "labor_shortfall"
               and int(delta.after) > 0 for delta in source.deltas)
    refresh_workforce_notices(world)
    demand = next(report for report in world.knowledge.workforce_demand_reports.values()
                  if report.work_kind == "military_recruitment")
    assert demand.source_event_id == source.id and demand.target_occupation == "soldier"
    assert not any(item.demand_id == demand.id for item in world.knowledge.workforce_offer_notices.values())
    assert any(actor.kind == "population_group" and actor.id in {
        group.id for group in world.society.population.values()
        if group.settlement_id == demand.work_id and group.occupation != "soldier" and group.count >= 5
    } for actor in monthly_actors(world))

    async def decline(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", decline)
    _, covered = asyncio.run(review_institutional_decision_turn(
        world, OWNER, military_recruitment_adapters()))
    assert covered and not world.knowledge.workforce_offer_notices
    choose_first(monkeypatch)
    invitation = military_recruitment_options(world, OWNER)[0]
    invite_decision = record_event(
        world, "institutional_decision_turn_decided", "A instituição escolheu convidar voluntários.",
        fact_kind=FactKind.DECISION, decision=invitation.decision(), cause_ids=(demand.event_id,))
    with pytest.raises(ValueError, match="stale|selected"):
        authorize_military_recruitment(world, OWNER, invitation.id + ":forged", invite_decision.id)
    assert not world.knowledge.workforce_offer_notices
    authorize_military_recruitment(world, OWNER, invitation.id, invite_decision.id)
    assert not military_recruitment_options(world, OWNER)
    options = tuple(option for group in world.society.population.values()
                    for option in workforce_transition_options(world, group.id)
                    if world.knowledge.workforce_offer_notices[option.notice_id].demand_id == demand.id)
    assert options
    selected = max(options, key=lambda item: world.knowledge.workforce_offer_notices[item.notice_id].count)
    notice = world.knowledge.workforce_offer_notices[selected.notice_id]
    assert 0 < notice.count <= world.society.population[selected.group_id].count // 5
    assert not world.society.workforce_transitions

    # A once-valid offer cannot recruit from a source that no longer has
    # rations for the eventual column, even if the notice is still visible.
    starved = deepcopy(world)
    source_stock = next(stock for stock in starved.economy.stocks.values()
                        if stock.owner_ref == OWNER and stock.location_id == demand.work_id)
    spent = record_event(starved, "test_recruitment_food_spent", "Premissa de rações gastas.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("stock", source_stock.id, "food",
                                        source_stock.goods.get("food", 0), 0),))
    starved.economy.stocks[source_stock.id] = source_stock.model_copy(update={
        "goods": {**source_stock.goods, "food": 0},
        "last_event_ids": {**source_stock.last_event_ids, "food": spent.id}})
    assert selected not in workforce_transition_options(starved, selected.group_id)
    stale_decision = record_event(starved, "workforce_transition_decided", "Oferta antiga selecionada.",
                                  fact_kind=FactKind.DECISION, decision=selected.decision(),
                                  cause_ids=(notice.event_id,))
    with pytest.raises(ValueError, match="stale|selected"):
        accept_workforce_transition(starved, selected.id, decision_event_id=stale_decision.id)
    assert not starved.society.workforce_transitions

    decision = record_event(world, "workforce_transition_decided", "O grupo aceitou serviço militar.",
                            fact_kind=FactKind.DECISION, decision=selected.decision(),
                            cause_ids=(notice.event_id,))
    transition = accept_workforce_transition(world, selected.id, decision_event_id=decision.id)
    assert world.society.total_population == people_before
    path = tmp_path / "defense-recruitment-pending.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

    for day in range(32, 62):
        due = tick(world)
        if day == 60:
            refresh_route_reports(world)
            refresh_settlement_reports(world)
        if day == 61:
            assert transition.id not in world.society.workforce_transitions
            assert world.society.population[transition.target_group_id].count >= notice.count
            assert asyncio.run(review_strategy_responses_with_provider(world, due))
    mobilized = world.strategy.plans[plan.id]
    assert mobilized.stage == "mobilized" and mobilized.detachment_id is not None
    assert world.society.detachments[mobilized.detachment_id].source_group_id == transition.target_group_id
    assert world.society.total_population == people_before
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    assert audit(path)["ok"] is True

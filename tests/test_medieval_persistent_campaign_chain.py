"""One defensive intent must retain the same material column through a siege."""

import asyncio
import json
from copy import deepcopy

import pytest

from src.classes.event import FactKind
from src.classes.society.force import Detachment, Garrison
from src.sim.medieval.campaign_ceasefire import (campaign_ceasefire_fulfillment_options,
                                                  campaign_ceasefire_offer_options,
                                                  campaign_ceasefire_response_options,
                                                  fulfill_campaign_ceasefire,
                                                  offer_campaign_ceasefire,
                                                  respond_campaign_ceasefire)
from src.sim.medieval import ai_decider
from src.sim.medieval.campaign_supply import review_campaign_supplies
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.force import force_position_options, prepare_force_position
from src.sim.medieval.persistence import load_world, save_world
from src.sim.medieval.settlement_investment import (execute_settlement_investment_option,
                                                    settlement_investment_options)
from src.sim.medieval.siege_campaign import (begin_siege_campaign, occupy_after_siege_breach,
                                             siege_campaign_options, siege_campaign_withdrawal_options,
                                             siege_occupation_options)
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.strategy_response import review_strategy_responses_with_provider
from src.systems.calendar_agenda import ScheduledSituation

from tests.test_medieval_strategy_response import (OCCUPIER, OWNER, SOURCE, TARGET,
                                                   choose_first, occupied_response_world, tick)


def _foreign_garrison_premise(world):
    source = next(group for group in world.society.population.values()
                  if group.settlement_id == TARGET)
    soldier_id = f"pop:{TARGET}:{source.people}:soldier"
    world.society.population[soldier_id] = source.model_copy(
        update={"id": soldier_id, "occupation": "soldier", "count": 20})
    detachment_id = "detachment:foreign-garrison-premise"
    arrival = record_event(
        world, "test_foreign_garrison_arrived", "Premissa factual da guarnição ocupante.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment", detachment_id, "stage", None, "present"),))
    world.society.detachments[detachment_id] = Detachment(
        id=detachment_id, owner_ref=OCCUPIER, source_group_id=soldier_id, count=20,
        location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0,
        provisions=600, stage="present", started_day=world.clock.absolute_day,
        due_day=world.clock.absolute_day + 1, decision_event_id=arrival.id,
        last_event_id=arrival.id)
    world.agenda.schedule(ScheduledSituation(detachment_id, "force", world.clock.absolute_day + 1))
    account = next(item for item in world.economy.accounts.values() if item.owner_ref == OCCUPIER)
    garrison_id = f"garrison:{detachment_id}"
    decision = record_event(
        world, "test_foreign_garrison_decided", "Premissa de decisão ocupante.",
        fact_kind=FactKind.DECISION,
        decision={"action": "establish_garrison", "actor_ref": OCCUPIER.to_dict(),
                  "selected_affordance_id": f"garrison:{detachment_id}:premise"})
    established = record_event(
        world, "garrison_established", "Guarnição ocupante presente e abastecida.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("garrison", garrison_id, "stage", None, "active"),
                _delta("garrison", garrison_id, "settlement_id", None, TARGET),
                _delta("garrison", garrison_id, "detachment_id", None, detachment_id)),
        cause_ids=(decision.id, arrival.id))
    world.society.garrisons[garrison_id] = Garrison(
        id=garrison_id, detachment_id=detachment_id, settlement_id=TARGET,
        account_id=account.id, decision_event_id=decision.id,
        started_day=world.clock.absolute_day, last_event_id=established.id)
    return garrison_id


def _decide(world, option):
    return record_event(world, "test_campaign_decided", "Decisão institucional da fixture.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def _start_siege(monkeypatch, extra_food, *, dispatch_repeat_supply=True):
    world, _, _ = occupied_response_world()
    sustained = extra_food >= 12000
    source_group = max((group for group in world.society.population.values()
                        if group.settlement_id == SOURCE and group.occupation == "soldier"),
                       key=lambda group: group.count)
    world.society.population[source_group.id] = source_group.model_copy(update={"count": 60})
    if extra_food:
        source_stock = next(stock for stock in world.economy.stocks.values()
                            if stock.owner_ref == OWNER and stock.location_id == SOURCE)
        before_food = source_stock.goods.get("food", 0)
        stocked = record_event(
            world, "test_campaign_source_stock_premise", "Premissa factual de estoque da expedição.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("stock", source_stock.id, "food", before_food, before_food + extra_food),))
        world.economy.stocks[source_stock.id] = source_stock.model_copy(update={
            "goods": {**source_stock.goods, "food": before_food + extra_food},
            "last_event_ids": {**source_stock.last_event_ids, "food": stocked.id}})
    _foreign_garrison_premise(world)
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    world.config = world.config.model_copy(update={"ai_enabled": True,
                                                   "ai_calls_per_step": 2, "ai_max_calls": 20})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))

    async def choose_campaign(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        supplied = any(notice.state == "fulfilled"
                       for notice in world.knowledge.campaign_supply_notices.values())
        if not dispatch_repeat_supply and supplied and "supply_notice" in payload["situation"]:
            return {"selected_id": ai_decider.NO_ACTION}
        chosen = next((choice for choice in payload["choices"]
                       if (f":{source_group.id}:" in choice["id"]
                           and (not sustained or "40 dias" in choice["label"]))),
                      payload["choices"][0])
        return {"selected_id": chosen["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_campaign)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    plan = next(iter(world.strategy.plans.values()))
    own_id = plan.detachment_id
    assert own_id is not None

    for _ in range(16):
        due = tick(world)
        asyncio.run(review_campaign_supplies(world, due))
        column = world.society.detachments[own_id]
        supplied = sustained or any(notice.detachment_id == own_id and notice.state == "fulfilled"
                                   for notice in world.knowledge.campaign_supply_notices.values())
        if column.stage == "present" and column.provisions >= column.count * 4 and supplied:
            break
    column = world.society.detachments[own_id]
    assert column.stage == "present" and column.location_id == TARGET
    assert column.count >= 60 and column.provisions >= column.count * 4, {
        "day": world.clock.absolute_day,
        "notices": [(n.state, n.observed_provisions) for n in world.knowledge.campaign_supply_notices.values()
                    if n.detachment_id == own_id],
        "supply_events": [e.event_type for e in world.events if "campaign_supply" in e.event_type
                          or "campaign_provisions" in e.event_type],
    }
    assert plan.detachment_id == own_id
    if not sustained:
        assert any(event.event_type == "campaign_provisions_loaded" for event in world.events)
    position_option = force_position_options(world, OWNER, detachment_id=own_id)[0]
    prepare_force_position(world, OWNER, position_option.id, _decide(world, position_option).id)
    for _ in range(3):
        due = tick(world)
        asyncio.run(review_campaign_supplies(world, due))
    position = world.society.force_positions[f"force-position:{own_id}"]
    assert position.stage == "prepared"
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    investments = [option for option in settlement_investment_options(world, OWNER, detachment_id=own_id)
                   if option.kind == "invest"]
    assert investments, {"provisions": world.society.detachments[own_id].provisions,
                         "day": world.clock.absolute_day}
    investment = investments[0]
    execute_settlement_investment_option(world, OWNER, investment.id, _decide(world, investment).id)
    sieges = siege_campaign_options(world, OWNER, detachment_id=own_id)
    assert sieges
    siege = begin_siege_campaign(world, OWNER, sieges[0].id, _decide(world, sieges[0]).id)
    return world, plan, own_id, siege


@pytest.mark.parametrize("extra_food,expected_phase", [(0, "lapsed"), (12000, "breached")])
def test_plan_column_cannot_force_victory_without_supply(monkeypatch, tmp_path, extra_food, expected_phase):
    world, plan, own_id, siege = _start_siege(monkeypatch, extra_food)
    if not extra_food:
        assert any(order.destination_id.endswith(own_id) for order in world.economy.freight_orders.values())
    pending_parcels = tuple(parcel for parcel in world.economy.parcels.values()
                            if world.economy.freight_orders[parcel.order_id].destination_id.endswith(own_id))
    if not extra_food:
        assert pending_parcels
    if pending_parcels:
        assert not siege_campaign_withdrawal_options(world, OWNER)
        assert not campaign_ceasefire_offer_options(world, OWNER)
    if pending_parcels:
        forged = deepcopy(world)
        pending = forged.economy.freight_orders[pending_parcels[0].order_id]
        bag = forged.economy.stocks[pending.destination_id]
        forged.economy.stocks[bag.id] = bag.model_copy(update={"location_id": SOURCE})
        with pytest.raises(ValueError, match="pending cargo destination moved"):
            save_world(forged, tmp_path / "forged-mobile-baggage.mws")
    for _ in range(8):
        due = tick(world)
        asyncio.run(review_campaign_supplies(world, due))
        if world.society.siege_campaigns[siege.id].phase != "sieging":
            break
    assert world.society.siege_campaigns[siege.id].phase == expected_phase, {
        "phase": world.society.siege_campaigns[siege.id].phase,
        "provisions": world.society.detachments[own_id].provisions,
        "day": world.clock.absolute_day,
    }
    if expected_phase == "lapsed":
        assert world.society.settlements[TARGET].occupier_id == OCCUPIER.id
        assert not siege_occupation_options(world, OWNER)
        final_path = tmp_path / "undersupplied-campaign.mws"
        save_world(world, final_path)
        from tools.medieval_causal_audit import audit
        assert audit(final_path)["ok"] is True
        return
    refresh_settlement_reports(world)
    occupations = siege_occupation_options(world, OWNER)
    assert occupations
    occupation = occupy_after_siege_breach(world, OWNER, occupations[0].id,
                                           _decide(world, occupations[0]).id)
    assert world.society.settlements[TARGET].occupier_id == OWNER.id
    assert occupation.event_type == "settlement_occupied_after_siege"
    lift = next(option for option in settlement_investment_options(world, OWNER, detachment_id=own_id)
                if option.kind == "lift")
    execute_settlement_investment_option(world, OWNER, lift.id, _decide(world, lift).id)
    path = tmp_path / "retaken-campaign.mws"
    save_world(world, path)
    world = load_world(path)
    assert world.strategy.plans[plan.id].detachment_id == own_id
    while world.clock.absolute_day < 31:
        due = tick(world)
        asyncio.run(review_campaign_supplies(world, due))
        if world.clock.absolute_day == 30:
            refresh_settlement_reports(world)
        if world.clock.absolute_day == 31:
            assert asyncio.run(review_strategy_responses_with_provider(world, due))
    assert world.strategy.plans[plan.id].stage == "closed"
    assert world.society.settlements[TARGET].occupier_id == OWNER.id
    final_path = tmp_path / "retaken-campaign-final.mws"
    save_world(world, final_path)
    from tools.medieval_causal_audit import audit
    assert audit(final_path)["ok"] is True


def test_plan_column_can_negotiate_and_physically_withdraw(monkeypatch, tmp_path):
    world, plan, own_id, siege = _start_siege(monkeypatch, 1200, dispatch_repeat_supply=False)
    offers = [option for option in campaign_ceasefire_offer_options(world, OWNER)
              if option.campaign_id == siege.id and option.kind == "mutual"]
    assert offers, {"day": world.clock.absolute_day,
                    "notices": [(notice.state, notice.freight_id)
                                for notice in world.knowledge.campaign_supply_notices.values()
                                if notice.detachment_id == own_id]}
    proposal = offer_campaign_ceasefire(world, OWNER, offers[0].id, _decide(world, offers[0]).id)
    response = next(option for option in campaign_ceasefire_response_options(world, OCCUPIER)
                    if option.proposal_id == proposal.id and option.response == "accept")
    respond_campaign_ceasefire(world, OCCUPIER, response.id, _decide(world, response).id)
    attacker = next(option for option in campaign_ceasefire_fulfillment_options(world, OWNER)
                    if option.campaign_id == siege.id)
    fulfilled = fulfill_campaign_ceasefire(world, OWNER, attacker.id, _decide(world, attacker).id)
    assert fulfilled.status == "fulfilled"
    assert world.society.siege_campaigns[siege.id].phase == "withdrawn"
    assert world.society.detachments[own_id].stage == "marching"
    assert world.strategy.plans[plan.id].detachment_id == own_id
    assert world.society.settlements[TARGET].occupier_id == OCCUPIER.id
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    defender_options = [option for option in campaign_ceasefire_fulfillment_options(world, OCCUPIER)
                        if option.campaign_id == siege.id]
    assert defender_options
    defender = fulfill_campaign_ceasefire(world, OCCUPIER, defender_options[0].id,
                                          _decide(world, defender_options[0]).id)
    assert defender.status == "fulfilled"
    assert world.society.settlements[TARGET].occupier_id != OCCUPIER.id
    midpoint = tmp_path / "negotiated-campaign-midpoint.mws"
    save_world(world, midpoint)
    world = load_world(midpoint)
    while world.clock.absolute_day < 31:
        due = tick(world)
        asyncio.run(review_campaign_supplies(world, due))
        if world.clock.absolute_day == 30:
            refresh_settlement_reports(world)
        if world.clock.absolute_day == 31:
            assert asyncio.run(review_strategy_responses_with_provider(world, due))
    assert world.strategy.plans[plan.id].stage == "closed"
    final_path = tmp_path / "negotiated-campaign.mws"
    save_world(world, final_path)
    from tools.medieval_causal_audit import audit
    assert audit(final_path)["ok"] is True


def test_physical_route_closure_interrupts_the_same_campaign(monkeypatch, tmp_path):
    world, plan, own_id, siege = _start_siege(monkeypatch, 1200)
    investment = world.society.settlement_investments[siege.investment_id]
    route_id = investment.route_ids[0]
    route = world.map.routes[route_id]
    assert route.enabled
    closure = record_event(
        world, "test_route_closed_by_external_cause", "Premissa factual de passagem interrompida.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("route", route_id, "enabled", True, False),))
    route.update_runtime(enabled=False)
    due = tick(world)
    asyncio.run(review_campaign_supplies(world, due))
    current = world.society.settlement_investments[investment.id]
    assert current.stage == "lifted"
    assert world.society.siege_campaigns[siege.id].phase == "lapsed"
    lifted = world.event_index()[current.last_event_id]
    assert closure.id in {link.cause_event_id for link in lifted.causal_links}
    own_report = world.knowledge.route_report(OWNER, route_id)
    assert own_report is not None and own_report.operational_capacity == 0
    assert world.strategy.plans[plan.id].detachment_id == own_id
    assert world.society.settlements[TARGET].occupier_id == OCCUPIER.id
    assert not siege_occupation_options(world, OWNER)
    final_path = tmp_path / "route-closed-campaign.mws"
    save_world(world, final_path)
    from tools.medieval_causal_audit import audit
    assert audit(final_path)["ok"] is True

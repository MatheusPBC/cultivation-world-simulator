"""Campaign food travels by ordinary freight or the column simply lapses."""

import json
import pytest

from src.classes.event import FactKind
from src.classes.economy.models import Stock
from src.classes.governance.authority import headquarters_holder
from src.classes.governance.models import Objective, StrategicPlan
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.force import force_options, occupy_settlement, raise_detachment, raise_options
from src.sim.medieval.campaign_supply import (campaign_stock_id, review_campaign_supplies,
                                               campaign_supply_options, dispatch_campaign_supply,
                                               observe_campaign_supply_needs, _provision_capacity)
from src.sim.medieval.research import learn_technology
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.systems.calendar_agenda import ScheduledSituation
from tests.medieval_ai_helpers import provider_selection_stub


OWNER = EntityRef("polity", "auren")
HOME = "campomanso"
TARGET = "salgueiro"


def decide(world, option):
    return record_event(world, "campaign_test_decided", "Decisão de campanha para teste.",
                        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                        decision=option.decision(),
                        causal_payload={"decision_source": {"kind": "api"}})


async def campaign_world():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 20})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    option = next(item for item in raise_options(world, OWNER) if item.destination_id == TARGET)
    detachment = raise_detachment(world, OWNER, option.id, decide(world, option).id)
    while world.society.detachments[detachment.id].stage == "marching":
        await advance(world)
    detachment = world.society.detachments[detachment.id]
    assert campaign_stock_id(detachment.id) in world.economy.stocks
    refresh_route_reports(world)
    return world, detachment.id


def enable(world):
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                   "ai_max_calls": 10})


def provider(monkeypatch, answer, prompts):
    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        if answer == "first":
            payload = json.loads(prompt[prompt.index("{"):])
            return {"selected_id": payload["choices"][0]["id"]}
        return {"selected_id": answer}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


async def advance(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    await review_campaign_supplies(world, due)


def totals(world):
    food = (sum(stock.goods.get("food", 0) for stock in world.economy.stocks.values())
            + sum(detachment.provisions for detachment in world.society.detachments.values()
                  if detachment.stage != "disbanded")
            + sum(parcel.quantity for parcel in world.economy.parcels.values()
                  if world.economy.freight_orders[parcel.order_id].resource_id == "food"))
    return food, sum(account.balance for account in world.economy.accounts.values()), \
        sum(group.count for group in world.society.population.values())


async def make_low(world, detachment_id):
    # Arrival with the force's real ten-day ration creates the route-aware
    # early warning (home freight needs longer than the remaining field bag).
    return next(item for item in world.knowledge.campaign_supply_notices.values()
                if item.detachment_id == detachment_id and item.state == "open")


async def test_field_logistics_knowledge_alone_does_not_expand_column_capacity():
    world, detachment_id = await campaign_world()
    detachment = world.society.detachments[detachment_id]
    before = _provision_capacity(world, detachment)
    first = record_event(world, "field_logistics_prerequisite", "Ensino da doutrina de exercício.",
                         fact_kind=FactKind.DECISION,
                         decision={"action": "research", "actor_ref": OWNER.to_dict(),
                                   "technology_id": "field_drill"})
    learn_technology(world, OWNER, "field_drill", "teaching", (first.id,))
    second = record_event(world, "field_logistics_decided", "Ensino da logística de campanha.",
                          fact_kind=FactKind.DECISION,
                          decision={"action": "research", "actor_ref": OWNER.to_dict(),
                                    "technology_id": "field_logistics"})
    learn_technology(world, OWNER, "field_logistics", "teaching", (second.id, first.id))
    assert _provision_capacity(world, detachment) == before


async def test_campaign_supply_freight_arrives_loads_bag_and_round_trips(tmp_path, monkeypatch):
    world, detachment_id = await campaign_world()
    enable(world)
    prompts = []
    provider(monkeypatch, "first", prompts)
    notice = await make_low(world, detachment_id)
    before_food, before_money, before_people = totals(world)
    baseline_events = len(world.events)
    await advance(world)  # provider opens freight, force remains supplied.
    decision = next(event for event in reversed(world.events)
                    if event.event_type == "campaign_supply_decided")
    assert decision.causal_origin == CausalOrigin.ACTOR_DECISION
    headquarters = headquarters_holder(world, OWNER)
    assert decision.decision["actor_ref"] == headquarters.to_dict()
    assert decision.decision["institution_ref"] == OWNER.to_dict()
    order = next(iter(world.economy.freight_orders.values()))
    freight_receipt = world.event_index()[order.last_event_id]
    dispatched_notice = world.knowledge.campaign_supply_notices[notice.id]
    dispatch_receipt = world.event_index()[dispatched_notice.last_event_id]
    expected_authorship = {
        "decision_event_id": decision.id,
        "actor_ref": decision.decision["actor_ref"],
        "selected_affordance_id": decision.decision["selected_affordance_id"],
    }
    assert freight_receipt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert freight_receipt.causal_payload == expected_authorship
    assert dispatch_receipt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert dispatch_receipt.causal_payload == expected_authorship
    own_route_reports = [world.knowledge.route_report(headquarters, route_id)
                         for route_id in order.route_ids]
    assert all(report is not None for report in own_route_reports)
    assert all(report.event_id in {link.cause_event_id for link in decision.causal_links}
               for report in own_route_reports)
    source = decision.causal_payload["decision_source"]
    assert source["kind"] == "provider"
    assert source["receipt_event_id"] in {link.cause_event_id for link in decision.causal_links}
    assert order.destination_id == campaign_stock_id(detachment_id) and order.owner_ref == OWNER
    assert world.knowledge.campaign_supply_notices[notice.id].state == "dispatched"
    prompt = prompts[0]
    prompt_situation = json.loads(prompt[prompt.index("{"):])["situation"]
    assert prompt_situation["you_are"] == headquarters.to_dict()
    prompt_route_events = {item["evidence_event_id"]
                           for item in prompt_situation["known_route_readings"]}
    assert {report.event_id for report in own_route_reports} <= prompt_route_events
    assert prompt_route_events <= {report.event_id for report in world.knowledge.route_reports.values()
                                   if report.recipient_ref == headquarters}
    for private_value in ("stock:", "account", "balance", "route_ids"):
        assert private_value not in prompt

    for _ in range(12):
        if world.knowledge.campaign_supply_notices[notice.id].state == "fulfilled":
            break
        await advance(world)
    detachment = world.society.detachments[detachment_id]
    assert detachment.stage == "present"
    assert world.knowledge.campaign_supply_notices[notice.id].state == "fulfilled"
    loading = next(event for event in world.events[baseline_events:]
                   if event.event_type == "campaign_provisions_loaded")
    loaded = next(delta for delta in loading.deltas
                  if delta.owner_kind == "detachment" and delta.owner_id == detachment_id
                  and delta.aspect == "provisions")
    assert int(loaded.after) > int(loaded.before)
    after_food, after_money, after_people = totals(world)
    consumed = sum(detachment.count for event in world.events[baseline_events:]
                   if event.event_type == "detachment_supplied")
    assert after_food == before_food - consumed
    assert after_money == before_money and after_people == before_people
    interpretations = {event.id for event in world.events if event.causal_origin.value == "llm_interpretation"}
    freight = next(event for event in world.events if event.event_type == "freight_opened" and event.id == order.last_event_id)
    assert not interpretations & {link.cause_event_id for link in freight.causal_links}
    path = tmp_path / "campaign.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


@pytest.mark.asyncio
async def test_deterministic_choice_cannot_dispatch_campaign_supply():
    world, detachment_id = await campaign_world()
    notice = await make_low(world, detachment_id)
    option = next(item for item in campaign_supply_options(world, OWNER)
                  if item.notice_id == notice.id)
    decision = record_event(world, "campaign_supply_decided", "Intenção determinística de teste.",
                             fact_kind=FactKind.DECISION, decision=option.decision())
    before = world_snapshot(world)

    with pytest.raises(ValueError, match="current actor decision"):
        dispatch_campaign_supply(world, OWNER, option.id, decision.id)

    assert world_snapshot(world) == before


@pytest.mark.asyncio
async def test_a_real_cargo_delay_reopens_a_bounded_hq_supply_choice(monkeypatch):
    world, detachment_id = await campaign_world()
    enable(world)
    prompts = []
    provider(monkeypatch, "first", prompts)
    first_notice = await make_low(world, detachment_id)
    await advance(world)
    first_notice = world.knowledge.campaign_supply_notices[first_notice.id]
    first_order = world.economy.freight_orders[first_notice.freight_id]
    parcel = next(item for item in world.economy.parcels.values() if item.order_id == first_order.id)

    # Feed an actual logistics-owner delay receipt through the same immutable
    # parcel transition used by the daily freight resolver.
    from src.sim.medieval.logistics import _record_parcel

    world.agenda.cancel(parcel.id)
    delay = _record_parcel(
        world, parcel, parcel.model_copy(update={"due_day": world.clock.absolute_day + 2}),
        "cargo_delayed", "A vazão disponível não comportou a carga da campanha.",
    )
    notices = observe_campaign_supply_needs(world)
    second_notice = next(item for item in notices if item.detachment_id == detachment_id)
    assert observe_campaign_supply_needs(world) == ()
    assert delay.id in {link.cause_event_id
                        for link in world.event_index()[second_notice.event_id].causal_links}

    second_options = [option for option in campaign_supply_options(world, OWNER)
                      if option.notice_id == second_notice.id]
    assert second_options
    camp = world.economy.stocks[campaign_stock_id(detachment_id)]
    pending = sum(item.quantity for item in world.economy.parcels.values()
                  if world.economy.freight_orders[item.order_id].destination_id == camp.id)
    assert all(option.quantity <= max(
        0, (camp.capacity - world.economy.used_capacity(camp))
        // world.economy.resources["food"].bulk - pending
    ) for option in second_options)

    scheduled = world.agenda.get(f"campaign-supply-review:{second_notice.id}")
    assert scheduled is not None
    world.clock = world.clock.advance(scheduled.due_day - world.clock.absolute_day)
    world.agenda.cancel(scheduled.id)
    selected = second_options[0]

    async def choose_followup(prompt, *args, **kwargs):
        prompts.append(prompt)
        payload = json.loads(prompt[prompt.index("{"):])
        assert payload["situation"]["you_are"] == headquarters_holder(world, OWNER).to_dict()
        assert any(item["freight_id"] == first_order.id
                   and delay.id in item["delay_event_ids"]
                   for item in payload["situation"]["delayed_freights"])
        return {"selected_id": selected.id}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_followup)
    await review_campaign_supplies(world, (scheduled,))

    second_decision = next(event for event in reversed(world.events)
                           if event.event_type == "campaign_supply_decided")
    assert second_decision.decision["actor_ref"] == headquarters_holder(world, OWNER).to_dict()
    assert delay.id in {link.cause_event_id for link in second_decision.causal_links}
    second_freight = world.economy.freight_orders[
        world.knowledge.campaign_supply_notices[second_notice.id].freight_id]
    assert second_freight.id != first_order.id
    assert second_freight.quantity == selected.quantity
    assert world.economy.freight_orders[first_order.id].quantity == first_order.quantity


@pytest.mark.asyncio
async def test_partial_campaign_freight_does_not_fulfill_its_notice():
    from src.sim.medieval.campaign_supply import _transition_notice, load_campaign_baggage
    from src.sim.medieval.economy import _delta
    from src.sim.medieval.logistics import open_order, resolve_parcels

    world, detachment_id = await campaign_world()
    notice = await make_low(world, detachment_id)
    camp = world.economy.stocks[campaign_stock_id(detachment_id)]
    source_id = "stock:campaign-test-local-source"
    world.economy.stocks[source_id] = Stock(
        id=source_id, owner_ref=OWNER, location_id=camp.location_id,
        capacity=100, goods={"food": 100}, last_event_ids={"food": notice.event_id},
    )
    decision = record_event(
        world, "campaign_supply_decided", "O QG autorizou uma remessa local de teste.",
        fact_kind=FactKind.DECISION,
        decision={"action": "campaign_supply_test", "actor_ref": headquarters_holder(world, OWNER).to_dict()},
        cause_ids=(notice.event_id,),
    )
    order = open_order(world, source_id, camp.id, "food", 20, (),
                       decision_ids=(decision.id,), cause_ids=(notice.event_id,))
    dispatched = record_event(
        world, "campaign_supply_dispatched", "O despacho foi entregue à logística.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("campaign_supply_notice", notice.id, "state", "open", "dispatched"),),
        cause_ids=(decision.id, order.last_event_id),
    )
    _transition_notice(world, notice, "dispatched", dispatched, freight_id=order.id)

    # A cramped destination receives only five of the twenty physical units.
    world.economy.stocks[camp.id] = camp.model_copy(update={"capacity": 5})
    parcel = next(item for item in world.economy.parcels.values() if item.order_id == order.id)
    world.agenda.cancel(parcel.id)
    world.clock = world.clock.advance(1)
    resolve_parcels(world, (ScheduledSituation(parcel.id, "cargo", world.clock.absolute_day),))
    load_campaign_baggage(world)

    updated = world.economy.freight_orders[order.id]
    assert updated.delivered_quantity == 5
    assert any(item.order_id == order.id for item in world.economy.parcels.values())
    assert world.knowledge.campaign_supply_notices[notice.id].state == "dispatched"


async def test_resolved_delayed_freight_schedules_active_campaign_review_after_real_loading():
    from src.sim.medieval.campaign_supply import (_transition_notice, load_campaign_baggage,
                                                   observe_campaign_supply_needs)
    from src.sim.medieval.logistics import _record_parcel, open_order, resolve_parcels
    from src.sim.medieval.economy import _delta

    world, detachment_id = await campaign_world()
    notice = await make_low(world, detachment_id)
    detachment = world.society.detachments[detachment_id]
    campaign_stock = world.economy.stocks[campaign_stock_id(detachment_id)]
    source_id = "stock:campaign-delay-followup-source"
    world.economy.stocks[source_id] = Stock(
        id=source_id, owner_ref=OWNER, location_id=campaign_stock.location_id,
        capacity=100, goods={"food": 10}, last_event_ids={"food": notice.event_id})
    objective = Objective(id="objective:campaign-delay-review", actor_ref=OWNER,
                          settlement_id=TARGET, stock_id=campaign_stock.id,
                          kind="defend_occupied_settlement", motivation="Manter campanha abastecida.")
    plan = StrategicPlan(id="plan:campaign-delay-review", objective_id=objective.id, stage="mobilized",
                         detachment_id=detachment_id, last_review_day=world.clock.absolute_day,
                         last_event_id=detachment.last_event_id)
    world.strategy.objectives[objective.id] = objective
    world.strategy.plans[plan.id] = plan

    decision = record_event(
        world, "campaign_supply_decided", "O QG abriu a primeira remessa de campanha.",
        fact_kind=FactKind.DECISION,
        decision={"action": "campaign_supply_test", "actor_ref": headquarters_holder(world, OWNER).to_dict()},
        cause_ids=(notice.event_id,))
    first_order = open_order(world, source_id, campaign_stock.id, "food", 1, (),
                             decision_ids=(decision.id,), cause_ids=(notice.event_id,))
    dispatched = record_event(
        world, "campaign_supply_dispatched", "A primeira remessa foi entregue à logística.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("campaign_supply_notice", notice.id, "state", "open", "dispatched"),),
        cause_ids=(decision.id, first_order.last_event_id))
    _transition_notice(world, notice, "dispatched", dispatched, freight_id=first_order.id)
    first_parcel = next(item for item in world.economy.parcels.values() if item.order_id == first_order.id)
    world.agenda.cancel(first_parcel.id)
    world.clock = world.clock.advance(1)
    delay = _record_parcel(
        world, first_parcel,
        first_parcel.model_copy(update={"due_day": world.clock.absolute_day + 1}),
        "cargo_delayed", "A vazão real reteve a primeira remessa de campanha.")

    followup = next(item for item in observe_campaign_supply_needs(world)
                    if item.detachment_id == detachment_id)
    assert delay.id in {link.cause_event_id for link in world.event_index()[followup.event_id].causal_links}
    second_decision = record_event(
        world, "campaign_supply_decided", "O QG autorizou uma remessa de seguimento.",
        fact_kind=FactKind.DECISION,
        decision={"action": "campaign_supply_test", "actor_ref": headquarters_holder(world, OWNER).to_dict()},
        cause_ids=(followup.event_id, delay.id))
    second_order = open_order(world, source_id, campaign_stock.id, "food", 1, (),
                              decision_ids=(second_decision.id,), cause_ids=(followup.event_id, delay.id))
    second_dispatch = record_event(
        world, "campaign_supply_dispatched", "A remessa de seguimento entrou na logística.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("campaign_supply_notice", followup.id, "state", "open", "dispatched"),),
        cause_ids=(second_decision.id, second_order.last_event_id))
    _transition_notice(world, followup, "dispatched", second_dispatch, freight_id=second_order.id)

    second_parcel = next(item for item in world.economy.parcels.values() if item.order_id == second_order.id)
    world.clock = world.clock.advance(1)
    resolve_parcels(world, (ScheduledSituation(second_parcel.id, "cargo", world.clock.absolute_day),))
    load_campaign_baggage(world)

    assert world.knowledge.campaign_supply_notices[followup.id].state == "fulfilled"
    review = world.agenda.get(f"strategy-response-review:{plan.id}")
    assert review is not None and review.due_day == world.clock.absolute_day + 1
    assert world.economy.freight_orders[first_order.id].delivered_quantity == 0
    assert first_parcel.id in world.economy.parcels


async def test_noaction_or_blocked_cargo_never_forces_supply_and_the_force_lapses(monkeypatch):
    world, detachment_id = await campaign_world()
    enable(world)
    prompts = []
    provider(monkeypatch, ai_decider.NO_ACTION, prompts)
    occupy = next(option for option in force_options(world, OWNER) if option.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)
    await make_low(world, detachment_id)
    await advance(world)
    decline = next(event for event in reversed(world.events)
                   if event.event_type == "campaign_supply_decided")
    assert decline.decision["actor_ref"] == headquarters_holder(world, OWNER).to_dict()
    assert decline.decision["selected_affordance_id"] == ai_decider.NO_ACTION
    assert not world.economy.freight_orders
    while world.society.detachments[detachment_id].stage != "disbanded":
        await advance(world)
    assert world.society.settlements[TARGET].occupier_id is None

    delayed, delayed_id = await campaign_world()
    enable(delayed)
    provider(monkeypatch, "first", [])
    await make_low(delayed, delayed_id)
    await advance(delayed)
    order = next(iter(delayed.economy.freight_orders.values()))
    for route_id in order.route_ids:
        delayed.map.routes[route_id].update_runtime(enabled=False)
    while delayed.society.detachments[delayed_id].stage != "disbanded":
        await advance(delayed)
    assert any(event.event_type == "cargo_delayed" for event in delayed.events)
    assert delayed.society.detachments[delayed_id].stage == "disbanded"
    assert not any(event.event_type in {"battle_resolved", "casualties_taken", "loot_taken"}
                   for event in delayed.events)


async def test_campaign_supply_does_not_silently_skip_an_unavailable_provider(monkeypatch):
    world, detachment_id = await campaign_world()
    enable(world)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    await make_low(world, detachment_id)

    with pytest.raises(ProviderDecisionRequired):
        await advance(world)

    assert not world.economy.freight_orders


async def test_campaign_supply_stale_owner_rejection_pauses_and_rolls_back(monkeypatch):
    world, detachment_id = await campaign_world()
    enable(world)
    prompts = []
    provider(monkeypatch, "first", prompts)
    await make_low(world, detachment_id)
    def reject(*_args, **_kwargs):
        raise ValueError("campaign supply option is stale")

    monkeypatch.setattr("src.sim.medieval.campaign_supply.dispatch_campaign_supply", reject)
    with pytest.raises(ProviderDecisionRequired, match="campaign supply affordance became stale"):
        await advance(world)
    assert not world.economy.freight_orders


async def test_campaign_supply_review_compares_all_due_columns_once(monkeypatch, tmp_path):
    world, detachment_id = await campaign_world()
    # Build a second real column for the same owner with the normal raise and
    # march owners, so this proves one review compares distinct columns rather
    # than several stale notices for one column.
    first_group_id = world.society.detachments[detachment_id].source_group_id
    second_raise = next(item for item in raise_options(world, OWNER)
                        if item.destination_id == TARGET and item.settlement_id == HOME
                        and item.group_id != first_group_id)
    second_detachment = raise_detachment(world, OWNER, second_raise.id, decide(world, second_raise).id)
    while world.society.detachments[second_detachment.id].stage == "marching":
        await advance(world)
    second_detachment = world.society.detachments[second_detachment.id]
    assert second_detachment.id != detachment_id and second_detachment.location_id == TARGET
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    notices = {notice.detachment_id: notice
               for notice in world.knowledge.campaign_supply_notices.values()
               if notice.recipient_ref == OWNER and notice.state == "open"}
    assert {detachment_id, second_detachment.id} <= notices.keys()
    live_options = campaign_supply_options(world, OWNER)
    assert {item.detachment_id for item in live_options} >= {detachment_id, second_detachment.id}
    second_option = next(item for item in live_options if item.detachment_id == second_detachment.id)
    enable(world)
    situations = tuple(ScheduledSituation(f"campaign-supply-review:{notice.id}",
                                          "campaign_supply_review", world.clock.absolute_day)
                       for notice in notices.values())
    option_calls = []
    enumerated_options = []
    prompts = []
    dispatched = []
    current_options = campaign_supply_options
    current_dispatch = dispatch_campaign_supply

    def tracked_options(current_world, actor):
        option_calls.append(actor)
        options = current_options(current_world, actor)
        enumerated_options.append(options)
        return options

    def tracked_dispatch(current_world, actor, option_id, decision_id):
        current_dispatch(current_world, actor, option_id, decision_id)
        dispatched.append((actor, option_id, decision_id))

    async def select_option(_world, _actor, situation, choices, **_kwargs):
        prompts.append((situation, choices))
        choice_ids = {choice["id"] for choice in choices}
        return second_option.id if second_option.id in choice_ids else (
            choices[0]["id"] if choices else ai_decider.NO_ACTION)

    monkeypatch.setattr("src.sim.medieval.campaign_supply.campaign_supply_options", tracked_options)
    monkeypatch.setattr(ai_decider, "select_option", provider_selection_stub(select_option))
    monkeypatch.setattr("src.sim.medieval.campaign_supply.dispatch_campaign_supply", tracked_dispatch)

    await review_campaign_supplies(world, situations)

    assert option_calls == [OWNER, OWNER, OWNER]  # menu, selected-ID check, material owner check
    assert len(prompts) == 1
    due_notice_ids = {notice.id for notice in notices.values()}
    expected_options = {option.id for option in enumerated_options[0]
                        if option.notice_id in due_notice_ids}
    assert {choice["id"] for choice in prompts[0][1]} == expected_options
    assert second_option.id in expected_options
    assert {item["notice_id"] for item in prompts[0][0]["supply_needs"]} == {
        notices[detachment_id].id, notices[second_detachment.id].id}
    assert {item["detachment_id"] for item in prompts[0][0]["supply_needs"]} == {
        detachment_id, second_detachment.id}
    assert len(dispatched) == 1 and dispatched[0][:2] == (OWNER, second_option.id)
    deferred_review = world.agenda.get(f"campaign-supply-review:{notices[detachment_id].id}")
    assert deferred_review is not None
    assert deferred_review.due_day == world.clock.absolute_day + 1
    path = tmp_path / "deferred-campaign-supply.mws"
    save_world(world, path)
    loaded = load_world(path)
    assert world_snapshot(loaded) == world_snapshot(world)
    await advance(loaded)
    assert len(prompts) == 2
    assert len(option_calls) == 6
    deferred_choice_ids = {choice["id"] for choice in prompts[1][1]}
    deferred_options = {option.id: option for option in enumerated_options[3]
                        if option.notice_id == notices[detachment_id].id}
    assert deferred_choice_ids and deferred_choice_ids == deferred_options.keys()
    assert dispatched[-1][:2] == (OWNER, prompts[1][1][0]["id"])
    assert deferred_options[dispatched[-1][1]].detachment_id == detachment_id
    assert loaded.knowledge.campaign_supply_notices[notices[second_detachment.id].id].state == "dispatched"
    assert loaded.knowledge.campaign_supply_notices[notices[detachment_id].id].state == "dispatched"

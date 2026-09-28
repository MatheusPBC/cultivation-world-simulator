"""Focused proof for the bounded medieval regional-overflow vertical."""

from __future__ import annotations

import json
import sqlite3

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.economy.models import Stock
from src.classes.event import FactKind
from src.classes.governance.authority import headquarters_holder
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.campaign_supply import (campaign_supply_options,
                                               review_campaign_supplies)
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.force import raise_detachment, raise_options
from src.sim.medieval.logistics import queue_freight
from src.sim.medieval.persistence import load_world, save_world
from src.sim.medieval import regional_overflow


SITE_ID = "docas-de-portovelho"
REGION_ID = 802
AUREN = EntityRef("polity", "auren")


async def _advance_to(world, day: int) -> None:
    simulator = MedievalSimulator(world)
    while world.clock.absolute_day < day:
        await simulator.step()


@pytest.mark.asyncio
async def test_natural_seed_can_produce_a_sustained_peak_without_forcing_overflow(tmp_path):
    world = create_medieval_world(14)
    site = world.map.infrastructure_sites[SITE_ID]
    route_id = site.route_ids[0]

    await _advance_to(world, 240)

    first = next(event for event in world.events
                 if event.event_type == "regional_hydrologic_load_assessed"
                 and event.day == 210 and any(
                     delta.owner_id == "regional_overflow_assessment:801"
                     and delta.aspect == "load" and int(delta.after) >= 88
                     for delta in event.deltas
                 ))
    second = next(event for event in world.events
                  if event.event_type == "regional_hydrologic_load_assessed"
                  and event.day == 240 and any(
                      delta.owner_id == "regional_overflow_assessment:801"
                      and delta.aspect == "load" and int(delta.after) >= 88
                      for delta in event.deltas
                  ))
    occurrence = world.regional_overflow.occurrence(801)

    assert occurrence is not None
    assert occurrence.started_day == 240
    assert occurrence.damaged_site_id == SITE_ID
    assert first.id in {link.cause_event_id for link in second.causal_links}
    damage = next(event for event in world.events if event.id == occurrence.damage_event_id)
    assert damage.event_type == "site_overflow_damaged"
    assert occurrence.started_event_id in {link.cause_event_id for link in damage.causal_links}
    assert damage.causal_payload["hazard_kind"] == "regional_flood"
    assert any(delta.owner_kind == "site" and delta.owner_id == SITE_ID
               and delta.aspect == "integrity" for delta in damage.deltas)
    assert not any(event.event_type == "regional_overflow_started"
                   and event.day < 240 for event in world.events)

    integrity_delta = next(delta for delta in damage.deltas
                           if delta.owner_kind == "site" and delta.owner_id == SITE_ID
                           and delta.aspect == "integrity")
    before_integrity = float(integrity_delta.before)
    after_integrity = float(integrity_delta.after)
    before_capacity = world.map.get_route_operational_capacity(
        route_id,
        site_runtime_overrides={
            SITE_ID: (before_integrity, site.enabled, site.service_suspended),
        },
    )
    after_capacity = world.map.get_route_operational_capacity(route_id)
    assert before_integrity > after_integrity
    assert after_capacity < before_capacity

    # The Map owns route capacity; a current report makes the changed capacity
    # available to the maintainer without exposing canonical flood conditions.
    route_report = world.knowledge.route_report(site.maintainer_ref, route_id)
    assert route_report is not None and route_report.observed_day == 240
    assert route_report.operational_capacity == pytest.approx(after_capacity)
    route_observation = next(event for event in world.events if event.id == route_report.event_id)
    assert damage.id in {link.cause_event_id for link in route_observation.causal_links}

    path = tmp_path / "natural-overflow-route.mws"
    save_world(world, path)
    restored = load_world(path)
    assert restored.knowledge.route_report(site.maintainer_ref, route_id) == route_report
    from tools.medieval_causal_audit import audit

    assert audit(path)["ok"] is True


@pytest.mark.asyncio
async def test_natural_overflow_reduces_the_next_real_freight_dispatch(tmp_path):
    world = create_medieval_world(14)
    site = world.map.infrastructure_sites[SITE_ID]
    route_id = site.route_ids[0]
    intact_capacity = world.map.get_route_operational_capacity(route_id)

    await _advance_to(world, 240)

    damaged_capacity = world.map.get_route_operational_capacity(route_id)
    occurrence = world.regional_overflow.occurrence(801)
    assert occurrence is not None and occurrence.damage_event_id
    assert damaged_capacity < intact_capacity

    source = world.economy.stocks["stock:pedraclara"]
    destination_id = "depot:auren-portovelho"
    world.economy.stocks[destination_id] = Stock(
        id=destination_id, owner_ref=source.owner_ref, location_id="portovelho", capacity=1_000,
    )
    quantity = int(intact_capacity)
    decision = record_event(
        world, "freight_decided", "A instituição autorizou uma remessa pela rota existente.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision={"action": "freight", "source_id": source.id, "destination_id": destination_id,
                  "resource_id": "food", "quantity": quantity, "route_ids": [route_id],
                  "actor_ref": source.owner_ref.to_dict()},
    )
    order = queue_freight(world, source.id, destination_id, "food", quantity, (route_id,),
                          decision_event_id=decision.id)

    await MedievalSimulator(world).step()

    parcels = [item for item in world.economy.parcels.values() if item.order_id == order.id]
    departed = sum(item.quantity for item in parcels if item.stage == "traveling")
    waiting = sum(item.quantity for item in parcels if item.stage == "waiting")
    assert 0 < departed <= int(damaged_capacity) < quantity
    assert waiting == quantity - departed > 0
    parcel_ids = {item.id for item in parcels}
    dispatch = next(event for event in reversed(world.events)
                    if event.event_type == "cargo_departed"
                    and any(delta.owner_kind == "cargo" and delta.owner_id in parcel_ids
                            for delta in event.deltas))
    assert occurrence.damage_event_id in {link.cause_event_id for link in dispatch.causal_links}

    path = tmp_path / "overflow-delayed-freight.mws"
    save_world(world, path)
    loaded = load_world(path)
    assert loaded.economy.parcels.keys() == world.economy.parcels.keys()
    from tools.medieval_causal_audit import audit

    assert audit(path)["ok"] is True


@pytest.mark.asyncio
async def test_natural_overflow_limits_active_campaign_rations_on_its_known_route(monkeypatch, tmp_path):
    world = create_medieval_world(14)
    route_id = world.map.infrastructure_sites[SITE_ID].route_ids[0]
    await _advance_to(world, 230)
    intact_capacity = world.map.get_route_operational_capacity(route_id)
    assert world.regional_overflow.occurrence(801) is None
    pre_flood_route_reports = tuple(
        world.knowledge.route_report(AUREN, item)
        for item in ("road-campomanso-pedraclara", route_id)
    )
    assert all(report is not None and report.observed_day == 210
               for report in pre_flood_route_reports)

    # This column exists before the natural overflow. Its own military choice
    # uses dated route reports and spends its actual soldiers, rations and pay.
    raise_option = next(option for option in raise_options(world, AUREN, days=18)
                        if option.settlement_id == "campomanso"
                        and option.destination_id == "portovelho"
                        and option.route_ids == ("road-campomanso-pedraclara", route_id))
    raise_decision = record_event(
        world, "campaign_raise_decided", "Auren autorizou uma coluna pela rota observada.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision=raise_option.decision(),
        cause_ids=tuple(report.event_id for report in pre_flood_route_reports),
    )
    detachment = raise_detachment(
        world, AUREN, raise_option.id, raise_decision.id, days=18)
    await _advance_to(world, 239)
    detachment = world.society.detachments[detachment.id]
    assert detachment.stage == "present" and detachment.location_id == "portovelho"

    await _advance_to(world, 246)
    damaged_capacity = world.map.get_route_operational_capacity(route_id)
    occurrence = world.regional_overflow.occurrence(801)
    route_report = world.knowledge.route_report(AUREN, route_id)
    assert occurrence is not None and occurrence.damage_event_id and occurrence.started_day == 240
    assert route_report is not None and route_report.observed_day == 240
    assert route_report.operational_capacity == pytest.approx(damaged_capacity)
    assert damaged_capacity < intact_capacity
    assert world.society.detachments[detachment.id].stage == "present"

    notice = next(item for item in world.knowledge.campaign_supply_notices.values()
                  if item.detachment_id == detachment.id and item.state == "open")
    assert notice.learned_day == 246 and notice.observed_provisions == 5

    # The real notice schedules the institution's supply decision for the next
    # date. Auren already has the same dated route report that allowed the
    # column to march; resolving this day consumes one ration before the choice.
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    options = [option for option in campaign_supply_options(world, AUREN)
               if option.notice_id == notice.id and option.route_ids == (route_id,)]
    assert options, "Auren can still meet the physical delivery lead time"
    supply_option = options[0]

    # A prior ordinary shipment consumes enough of this same physical route
    # that the campaign parcel would fit under the intact capacity, but not
    # under the flood-damaged capacity.
    source_location = world.economy.stocks[supply_option.source_stock_id].location_id
    food_bulk = world.economy.resources["food"].bulk
    remaining_capacity = int(damaged_capacity // food_bulk)
    assert remaining_capacity > supply_option.quantity
    competitor_destination = "depot:auren-portovelho"
    world.economy.stocks[competitor_destination] = Stock(
        id=competitor_destination, owner_ref=AUREN, location_id="portovelho", capacity=1_000,
    )
    competitors = []
    sources = [stock for stock in sorted(world.economy.stocks.values(), key=lambda item: item.id)
               if stock.owner_ref == AUREN and stock.location_id == source_location
               and stock.id != supply_option.campaign_stock_id
               and stock.goods.get("food", 0) > 0]
    for source in sources:
        quantity = min(remaining_capacity, source.goods.get("food", 0))
        if quantity <= 0:
            continue
        competitor_decision = record_event(
            world, "freight_decided", "Auren priorizou outra carga pela rota.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload={"decision_source": {"kind": "api"}},
            decision={"action": "freight", "source_id": source.id,
                      "destination_id": competitor_destination, "resource_id": "food",
                      "quantity": quantity, "route_ids": list(supply_option.route_ids),
                      "actor_ref": AUREN.to_dict()},
        )
        competitors.append(queue_freight(
            world, source.id, competitor_destination, "food", quantity,
            supply_option.route_ids, decision_event_id=competitor_decision.id))
        remaining_capacity -= quantity
        if remaining_capacity == 0:
            break
    assert remaining_capacity == 0, "fixture must saturate the flood-reduced route with real freight"

    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 8, "ai_max_calls": 16,
    })

    async def select_campaign_supply(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        withdrawal = next((choice for choice in payload["choices"]
                           if choice["id"].startswith("campaign-delay-withdraw:standalone:")), None)
        if withdrawal is not None:
            assert followup.id in withdrawal["label"]
            assert any(route["affordance_id"] == withdrawal["id"]
                       and followup.id in route["lapsed_supply_notice_ids"]
                       for route in payload["situation"]["withdrawal_routes"])
            return {"selected_id": withdrawal["id"]}
        assert any(choice["id"] == supply_option.id for choice in payload["choices"])
        return {"selected_id": supply_option.id}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", select_campaign_supply)
    await review_campaign_supplies(world, due)
    campaign_decision = next(event for event in reversed(world.events)
                             if event.event_type == "campaign_supply_decided")
    assert campaign_decision.causal_origin == CausalOrigin.ACTOR_DECISION
    assert campaign_decision.causal_payload["decision_source"]["kind"] == "provider"
    headquarters = headquarters_holder(world, AUREN)
    route_reading = world.knowledge.route_report(headquarters, route_id)
    assert route_reading is not None and route_reading.observed_day == 240
    assert campaign_decision.decision["actor_ref"] == headquarters.to_dict()
    assert route_reading.event_id in {link.cause_event_id for link in campaign_decision.causal_links}
    supply = world.economy.freight_orders[world.knowledge.campaign_supply_notices[notice.id].freight_id]
    assert all(supply.id != competitor.id for competitor in competitors)

    world.clock = world.clock.advance(1)
    delayed_day = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, delayed_day)
    supply_parcels = [parcel for parcel in world.economy.parcels.values()
                      if parcel.order_id == supply.id]
    departed = sum(parcel.quantity for parcel in supply_parcels if parcel.stage == "traveling")
    waiting = sum(parcel.quantity for parcel in supply_parcels if parcel.stage == "waiting")
    assert departed == 0 and waiting == supply_option.quantity
    affected_receipts = [event for event in world.events
                         if event.event_type in {"cargo_departed", "cargo_delayed"}
                         and any(delta.owner_kind == "cargo"
                                 and delta.owner_id in {parcel.id for parcel in supply_parcels}
                                 for delta in event.deltas)]
    assert affected_receipts
    assert any(occurrence.damage_event_id in {
        link.cause_event_id for link in event.causal_links
    } for event in affected_receipts)
    delay_event = next(event for event in reversed(world.events)
                       if event.event_type == "cargo_delayed"
                       and any(delta.owner_kind == "cargo" and delta.owner_id in {
                           parcel.id for parcel in supply_parcels
                       } for delta in event.deltas))
    followup = next(item for item in world.knowledge.campaign_supply_notices.values()
                    if item.detachment_id == detachment.id and item.id != notice.id
                    and item.state == "open")
    assert delay_event.id in {link.cause_event_id
                              for link in world.event_index()[followup.event_id].causal_links}
    followup_options = [item for item in campaign_supply_options(world, AUREN)
                        if item.notice_id == followup.id]
    assert followup_options, "the bounded bag has room for a separate, owner-funded follow-up"

    # A second, independent HQ turn can choose a follow-up shipment. The
    # receipt retains the delay fact even if the first parcel starts moving
    # again during this day's dated logistics phase.
    world.clock = world.clock.advance(1)
    followup_day = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, followup_day)
    followup_options_now = [item for item in campaign_supply_options(world, AUREN)
                            if item.notice_id == followup.id]
    assert not followup_options_now, (
        "after the logistics tick, current provisions, route lead time, and source stock must be revalidated"
    )
    order_count_before_review = len(world.economy.freight_orders)
    await review_campaign_supplies(world, followup_day)
    assert len(world.economy.freight_orders) == order_count_before_review
    assert not any(event.event_type == "campaign_supply_decided"
                   and event.day == world.clock.absolute_day for event in world.events)
    second_notice = world.knowledge.campaign_supply_notices[followup.id]
    assert second_notice.state == "open"

    # The direct raise above has no StrategicPlan. Once its delayed parcel is
    # physically loaded, the same QG still gets an independent review turn.
    # The flood and cargo remain natural; only the provider response is fixed.
    from src.sim.medieval.strategy_response import review_strategy_responses_with_provider

    review_id = f"campaign-logistics-review:{detachment.id}"
    for _ in range(30):
        world.clock = world.clock.advance(1)
        arrival_day = world.agenda.pop_due(world.clock.absolute_day)
        resolve_dated(world, arrival_day)
        review = world.agenda.get(review_id)
        if review is not None:
            break
    else:
        pytest.fail("resolved delayed cargo did not schedule a standalone QG review")
    world.clock = world.clock.advance(review.due_day - world.clock.absolute_day)
    qg_review = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, qg_review)
    assert await review_strategy_responses_with_provider(world, qg_review)
    assert world.society.detachments[detachment.id].stage == "marching"
    assert world.knowledge.campaign_supply_notices[followup.id].state == "lapsed"
    withdrawal = next(event for event in reversed(world.events)
                      if event.event_type == "campaign_logistics_review_decided")
    assert withdrawal.decision["actor_ref"] == headquarters.to_dict()
    assert withdrawal.causal_origin == CausalOrigin.ACTOR_DECISION
    assert withdrawal.causal_payload["decision_source"]["kind"] == "provider"
    assert "operational_plan_id" not in withdrawal.decision
    assert not any(plan.detachment_id == detachment.id for plan in world.strategy.plans.values())
    assert delay_event.id in {link.cause_event_id for link in withdrawal.causal_links}
    lapsed_event = world.event_index()[world.knowledge.campaign_supply_notices[followup.id].last_event_id]
    assert withdrawal.id in {link.cause_event_id for link in lapsed_event.causal_links}

    path = tmp_path / "overflow-campaign-supply.mws"
    save_world(world, path)
    restored = load_world(path)
    assert restored.economy.freight_orders[supply.id].route_ids == (route_id,)
    assert restored.knowledge.campaign_supply_notices[followup.id].state == "lapsed"
    from tools.medieval_causal_audit import audit

    assert audit(path)["ok"] is True


@pytest.mark.asyncio
async def test_provider_can_choose_repair_after_a_natural_overflow_without_repairing_for_free(monkeypatch, tmp_path):
    world = create_medieval_world(14)
    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 10000})
    selected_repairs = []
    selected_material_purchases = []
    accepted_market_purchases = []

    async def choose_only_this_repair(prompt):
        payload = json.loads(prompt[prompt.index("{"):])
        option = next((choice for choice in payload["choices"]
                       if choice["label"] == f"Autorizar o reparo da instalação {SITE_ID}."), None)
        if option is None:
            option = next((choice for choice in payload["choices"]
                           if any(f"Pedir compra de {resource}" in choice["label"]
                                  for resource in ("stone", "tools"))), None)
            if option is not None:
                selected_material_purchases.append(option["id"])
        if option is None:
            option = next((choice for choice in payload["choices"]
                           if "Vender" in choice["label"]
                           and any(resource in choice["label"] for resource in ("stone", "tools"))), None)
            if option is not None:
                accepted_market_purchases.append(option["id"])
        if option is None:
            return {"selected_id": "NO_ACTION"}
        selected_repairs.append(option["id"])
        return {"selected_id": option["id"]}

    from src.sim.medieval import ai_decider

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_only_this_repair)

    await _advance_to(world, 240)

    site = world.map.infrastructure_sites[SITE_ID]
    occurrence = world.regional_overflow.occurrence(801)
    assert occurrence is not None and occurrence.damaged_site_id == SITE_ID
    assert selected_repairs
    project = next(project for project in world.economy.repairs.values() if project.site_id == SITE_ID)
    assert project.stage == "waiting" and project.restored_permille == 0
    assert site.integrity < 1.0
    damaged_integrity = site.integrity
    choice = next(event for event in world.events
                  if event.event_type == "institutional_decision_turn_decided"
                  and (event.decision or {}).get("selected_affordance_id") in selected_repairs)
    authorization = world.event_index()[project.decision_event_id]
    assert choice.causal_payload["decision_source"]["kind"] == "provider"
    assert authorization.causal_payload["decision_source"]["kind"] == "provider"
    assert choice.id in {link.cause_event_id for link in authorization.causal_links}
    site_report = world.knowledge.site_report(site.maintainer_ref, SITE_ID)
    route_report = world.knowledge.route_report(site.maintainer_ref, site.route_ids[0])
    assert site_report is not None and site_report.observed_day == 240
    assert route_report is not None and route_report.observed_day == 240
    assert site_report.event_id in {link.cause_event_id for link in choice.causal_links}
    assert occurrence.damage_event_id in {
        link.cause_event_id for link in world.event_index()[site_report.event_id].causal_links
    }
    assert occurrence.damage_event_id in {
        link.cause_event_id for link in world.event_index()[route_report.event_id].causal_links
    }

    await _advance_to(world, 270)

    project = world.economy.repairs[project.id]
    assert project.stage == "blocked" and project.blocker == "input:stone"
    assert site.integrity == damaged_integrity
    repair_event = world.event_index()[project.last_event_id]
    assert repair_event.event_type == "repair_progressed"
    assert any(delta.owner_kind == "repair" and delta.owner_id == project.id
               and delta.aspect == "blocker" and delta.after == "input:stone"
               for delta in repair_event.deltas)
    assert f"inputs:{project.stock_id}:stone" in world.strategy.objectives
    assert selected_material_purchases

    await _advance_to(world, 300)

    assert selected_material_purchases
    assert accepted_market_purchases
    stone_orders = [order for order in world.economy.freight_orders.values()
                    if order.resource_id == "stone" and order.destination_id == project.stock_id]
    assert stone_orders
    order = next(order for order in stone_orders if order.resource_id == "stone")
    buy_decision = world.event_index()[order.decision_ids[0]]
    seller_decision = world.event_index()[order.decision_ids[1]]
    buyer_request = next(event for event in world.events
                         if event.event_type == "institutional_decision_turn_decided"
                         and event.id in {link.cause_event_id for link in buy_decision.causal_links}
                         and (event.decision or {}).get("action") == "purchase_market_offer"
                         and (event.decision or {}).get("actor_ref") == site.maintainer_ref.to_dict())
    seller_choice = next(event for event in world.events
                         if event.event_type == "institutional_decision_turn_decided"
                         and (event.decision or {}).get("action") == "accept_market_purchase"
                         and event.id in {link.cause_event_id for link in seller_decision.causal_links}
                         and (event.decision or {}).get("actor_ref") == seller_decision.decision["actor_ref"])
    payment = next(event for event in world.events
                   if event.event_type == "payment_completed"
                   and seller_decision.id in {link.cause_event_id for link in event.causal_links})
    assert buyer_request.day == seller_decision.day
    assert buyer_request.causal_payload["decision_source"]["kind"] == "provider"
    assert seller_choice.causal_payload["decision_source"]["kind"] == "provider"
    assert seller_choice.id in {link.cause_event_id for link in seller_decision.causal_links}
    assert seller_decision.causal_origin.value == "actor_decision"
    assert buyer_request.id in {link.cause_event_id for link in seller_decision.causal_links}
    assert payment.causal_origin.value == "actor_decision"
    assert seller_decision.id in {link.cause_event_id for link in payment.causal_links}
    assert world.map.infrastructure_sites[SITE_ID].integrity == damaged_integrity

    await _advance_to(world, 390)

    project = world.economy.repairs[project.id]
    assert project.restored_permille > 0
    assert world.map.infrastructure_sites[SITE_ID].integrity > damaged_integrity
    tools_orders = [order for order in world.economy.freight_orders.values()
                    if order.resource_id == "tools" and order.destination_id == project.stock_id]
    assert tools_orders and any(order.delivered_quantity == order.quantity for order in tools_orders)
    final_save = tmp_path / "natural-overflow-repaired-through-market.mws"
    save_world(world, final_save)
    restored = load_world(final_save)
    assert restored.economy.repairs[project.id] == project
    from tools.medieval_causal_audit import audit

    audit_result = audit(final_save)
    assert audit_result["ok"] is True, audit_result


def test_seeded_quiet_world_can_remain_free_of_overflow_for_ten_years():
    from src.systems.time import WorldClock

    world = create_medieval_world(73)
    for day in range(30, 3601, 30):
        world.clock = WorldClock(day)
        regional_overflow.apply_monthly_regional_overflow(world)

    assert world.regional_overflow.active_occurrences == {}
    assert not any(event.event_type == "regional_overflow_started" for event in world.events)


def _force_load(monkeypatch, *, high: bool) -> None:
    monkeypatch.setattr(
        regional_overflow,
        "regional_hydrologic_load",
        lambda _world, region_id: 100 if high and region_id == REGION_ID else 0,
    )


def _provision_repair(world):
    site = world.map.infrastructure_sites[SITE_ID]
    stock = next(
        stock
        for _, stock in sorted(world.economy.stocks.items())
        if stock.owner_ref == site.maintainer_ref
        and world.society.settlements[stock.location_id].region_id in site.region_ids
    )
    blueprint = next(
        blueprint
        for _, blueprint in sorted(world.economy.repair_blueprints.items())
        if blueprint.site_kind == site.kind
    )
    world.economy.stocks[stock.id] = stock.model_copy(
        update={
            "goods": {
                **stock.goods,
                **{
                    resource_id: stock.goods.get(resource_id, 0) + amount * 10
                    for resource_id, amount in blueprint.inputs.items()
                },
            }
        }
    )


def test_site_overflow_reading_is_geography_only_before_any_assessment():
    world = create_medieval_world(73)
    reading = regional_overflow.site_overflow_reading(world, SITE_ID)

    assert reading["site_id"] == SITE_ID
    assert reading["vulnerability"] == regional_overflow.site_overflow_vulnerability(
        world, world.map.infrastructure_sites[SITE_ID])
    region = next(item for item in reading["regions"] if item["region_id"] == REGION_ID)
    assert region["last_assessed_load"] is None
    assert region["last_assessed_streak"] is None
    assert region["last_assessed_day"] is None
    assert region["assessment_event_id"] is None
    assert region["open_occurrence"] is None


def test_site_overflow_reading_of_an_unknown_site_is_none():
    world = create_medieval_world(73)
    assert regional_overflow.site_overflow_reading(world, "not-a-real-site") is None


@pytest.mark.asyncio
async def test_site_overflow_reading_projects_the_last_assessment_and_open_occurrence(monkeypatch):
    world = create_medieval_world(73)
    _force_load(monkeypatch, high=True)

    await _advance_to(world, 60)

    reading = regional_overflow.site_overflow_reading(world, SITE_ID)
    region = next(item for item in reading["regions"] if item["region_id"] == REGION_ID)
    assessment = world.regional_overflow.assessment(REGION_ID)
    occurrence = world.regional_overflow.occurrence(REGION_ID)

    assert region["last_assessed_load"] == assessment.load
    assert region["last_assessed_streak"] == assessment.streak
    assert assessment.streak >= regional_overflow.OVERFLOW_CONSECUTIVE_MONTHS
    assert region["last_assessed_day"] == 60
    assessment_event = next(item for item in world.events if item.id == region["assessment_event_id"])
    assert assessment_event.event_type == "regional_hydrologic_load_assessed"

    assert occurrence is not None
    assert region["open_occurrence"] == {
        "started_day": occurrence.started_day, "load": occurrence.load,
        "assessment_event_id": occurrence.assessment_event_id,
        "started_event_id": occurrence.started_event_id,
    }
    started_event = next(item for item in world.events if item.id == occurrence.started_event_id)
    assert started_event.event_type == "regional_overflow_started"
    # Only this site's own regions are read; nothing foreign or predicted.
    assert {item["region_id"] for item in reading["regions"]} == set(
        world.map.infrastructure_sites[SITE_ID].region_ids)


@pytest.mark.asyncio
async def test_nonrecurring_water_load_never_opens_an_overflow(monkeypatch):
    world = create_medieval_world(73)
    _force_load(monkeypatch, high=False)

    await _advance_to(world, 60)

    assert world.regional_overflow.active_occurrences == {}
    # A real cargo departure of 90 crossed this route, but ordinary operating
    # wear has an explicit 100-bulk monthly threshold.  Neither low activity
    # nor the absence of an overflow may manufacture physical damage.
    assert world.map.infrastructure_sites[SITE_ID].integrity == pytest.approx(1.0)
    assert not any(
        event.event_type == "site_worn"
        and any(delta.owner_kind == "site" and delta.owner_id == SITE_ID for delta in event.deltas)
        for event in world.events
    )
    assert not any(event.event_type == "regional_overflow_started" for event in world.events)


@pytest.mark.asyncio
async def test_later_hydrologic_assessment_retains_the_prior_month_receipt(monkeypatch):
    world = create_medieval_world(73)
    _force_load(monkeypatch, high=False)
    await _advance_to(world, 30)
    first = world.regional_overflow.assessment(REGION_ID).evidence_event_id

    await _advance_to(world, 60)
    second = next(event for event in world.events
                  if event.id == world.regional_overflow.assessment(REGION_ID).evidence_event_id)

    assert first in {link.cause_event_id for link in second.causal_links}


@pytest.mark.asyncio
async def test_sustained_load_damages_one_water_site_is_observed_and_enters_existing_repair_path(monkeypatch):
    world = create_medieval_world(73)
    _provision_repair(world)
    _force_load(monkeypatch, high=True)
    site = world.map.infrastructure_sites[SITE_ID]
    route = world.map.routes[site.route_ids[0]]
    nominal = route.capacity
    intact_operational = world.map.get_route_operational_capacity(route.id)

    await _advance_to(world, 30)
    assert world.regional_overflow.occurrence(REGION_ID) is None
    await _advance_to(world, 60)

    occurrence = world.regional_overflow.occurrence(REGION_ID)
    assert occurrence is not None and occurrence.damaged_site_id == SITE_ID
    # The registered flood interaction owns the bounded loss (0.075 here).
    # Cargo did traverse the dependent route, but only 90 bulk moved and the
    # independent operating-wear law requires 100, so it contributes no loss.
    assert world.map.infrastructure_sites[SITE_ID].integrity == pytest.approx(0.925)
    assert route.capacity == nominal
    assert world.map.get_route_operational_capacity(route.id) < intact_operational
    start = next(event for event in world.events if event.id == occurrence.started_event_id)
    damage = next(event for event in world.events if event.id == occurrence.damage_event_id)
    assert occurrence.assessment_event_id in {link.cause_event_id for link in start.causal_links}
    assert occurrence.started_event_id in {link.cause_event_id for link in damage.causal_links}
    assert any(delta.owner_kind == "site" and delta.owner_id == SITE_ID
               and delta.aspect == "integrity" for delta in damage.deltas)
    assert damage.causal_payload["hazard_kind"] == "regional_flood"
    assert damage.causal_payload["target_id"] == SITE_ID
    assert damage.causal_payload["magnitude"] == pytest.approx(0.075)

    # Reports were refreshed after the damage in the same boundary. The legacy
    # repair executor is merely offered/authorized by its standing policy; this
    # overflow code itself made neither a decision nor a repair mutation.
    report = world.knowledge.site_report(world.map.infrastructure_sites[SITE_ID].maintainer_ref, SITE_ID)
    assert report is not None and report.observed_day == 60 and report.integrity == pytest.approx(0.925)
    from src.server.medieval.queries import world_view

    observer = world_view(world)
    assert [item.id for item in observer.regional_overflows] == [occurrence.id]
    assert not hasattr(world.knowledge, "regional_overflows")
    project = next(project for project in world.economy.repairs.values() if project.site_id == SITE_ID)
    assert project.stage == "waiting"

    await _advance_to(world, 90)
    assert world.map.infrastructure_sites[SITE_ID].integrity > 0.84
    assert world.regional_overflow.occurrence(REGION_ID).damage_event_id == occurrence.damage_event_id
    assert len([event for event in world.events if event.event_type == "site_overflow_damaged"]) == 1


@pytest.mark.asyncio
async def test_overflow_never_repairs_when_the_maintainer_has_no_current_authority(monkeypatch):
    world = create_medieval_world(73)
    _force_load(monkeypatch, high=True)
    site = world.map.infrastructure_sites[SITE_ID]
    office = world.authority.offices[f"office:{site.maintainer_ref.kind}:{site.maintainer_ref.id}"]
    world.authority.offices[office.id] = office.model_copy(update={"ends_day": 0})

    await _advance_to(world, 60)
    assert world.map.infrastructure_sites[SITE_ID].integrity == pytest.approx(0.925)
    assert not any(project.site_id == SITE_ID for project in world.economy.repairs.values())

    # No overflow-specific decision/project was created. A later normal use
    # receipt may still wear the site; that distinct Map law is not a repair.
    from src.sim.medieval.economy import monthly_workforce
    from src.sim.medieval.infrastructure import progress_repairs

    integrity_after_damage = world.map.infrastructure_sites[SITE_ID].integrity
    progress_repairs(world, monthly_workforce(world))
    assert world.map.infrastructure_sites[SITE_ID].integrity == integrity_after_damage
    assert len([event for event in world.events if event.event_type == "site_overflow_damaged"]) == 1


@pytest.mark.asyncio
async def test_overflow_assessment_round_trips_before_the_second_month(tmp_path, monkeypatch):
    world = create_medieval_world(73)
    _force_load(monkeypatch, high=True)

    await _advance_to(world, 30)
    saved_assessment = world.regional_overflow.assessment(REGION_ID)
    assert saved_assessment is not None and saved_assessment.streak == 1
    path = tmp_path / "overflow.mws"
    save_world(world, path)
    restored = load_world(path)
    assert restored.regional_overflow.to_dict() == world.regional_overflow.to_dict()

    await _advance_to(restored, 60)
    occurrence = restored.regional_overflow.occurrence(REGION_ID)
    assert occurrence is not None and occurrence.damaged_site_id == SITE_ID
    assert restored.map.infrastructure_sites[SITE_ID].integrity == pytest.approx(0.925)


def test_schema_twenty_one_is_explicitly_rejected_without_migration(tmp_path):
    path = tmp_path / "schema-21.mws"
    save_world(create_medieval_world(73), path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET schema_version=21")
    with pytest.raises(ValueError, match="Unsupported Medieval World Simulator save"):
        load_world(path)

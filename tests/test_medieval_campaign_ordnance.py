"""Campaign ordnance stays ordinary stock, freight and siege endurance."""

from copy import deepcopy

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.economy.models import Stock
from src.classes.event import FactKind
from src.classes.governance.authority import headquarters_holder
from src.sim.medieval.campaign_ordnance import (
    BOMBARD_ACTION,
    DISPATCH_ACTION,
    campaign_ordnance_options,
    execute_campaign_ordnance_option,
)
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.campaign_supply import (campaign_baggage_ready_for_departure,
                                               campaign_stock_id, observe_campaign_supply_needs)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import learn_technology
from src.sim.medieval.force import disband_detachment, force_options
from src.sim.medieval.route_interdiction import (execute_route_interdiction_option,
                                                  route_interdiction_options)
from src.sim.medieval.settlement_investment import (execute_settlement_investment_option,
                                                     settlement_investment_options)
from src.sim.medieval.siege_campaign import (begin_siege_campaign, siege_campaign_options,
                                             siege_campaign_withdrawal_options,
                                             withdraw_siege_campaign)
from tests.test_medieval_siege_campaign import (ATTACKER, DEFENDER, TARGET, ROAD, decide,
                                                 siege_world, tick)


def _record_equipment_stock(world, location=TARGET):
    stock_id = "stock:campaign-ordnance-fixture"
    stock = Stock(id=stock_id, owner_ref=ATTACKER, location_id=location,
                  capacity=100, goods={})
    world.economy.stocks[stock_id] = stock
    premise = record_event(
        world, "campaign_ordnance_fixture_stock", "Premissa material da fixture de cerco.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "campaign_ordnance_test_stock",
            "source_refs": [{"kind": "scenario", "id": "campaign_ordnance_fixture"},
                            {"kind": "stock", "id": stock_id}],
            "observed_day": world.clock.absolute_day,
        }},
        deltas=(_delta("stock", stock_id, "artillery", 0, 1),
                _delta("stock", stock_id, "gunpowder", 0, 3)))
    world.economy.stocks[stock_id] = stock.model_copy(update={
        "goods": {"artillery": 1, "gunpowder": 3},
        "last_event_ids": {"artillery": premise.id, "gunpowder": premise.id},
    })
    learn_technology(world, ATTACKER, "metallurgy", "teaching", (premise.id,))
    metallurgy_event_id = world.knowledge.technologies[
        f"technology:{ATTACKER.kind}:{ATTACKER.id}:metallurgy"].event_id
    # learn_technology is intentionally used only as a prepared-world premise:
    # E300's separate acceptance still requires paid research/production.
    learn_technology(world, ATTACKER, "gunpowder", "teaching",
                     (premise.id, metallurgy_event_id))
    return stock_id


def _arm_campaign(world, campaign_option):
    campaign = begin_siege_campaign(
        world, ATTACKER, campaign_option.id, decide(world, campaign_option).id)
    _record_equipment_stock(world)
    return campaign


def _decision(world, action, option_id):
    return record_event(
        world, "campaign_ordnance_decided", "Decisão atual de equipamento de cerco.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision={"action": action, "actor_ref": ATTACKER.to_dict(),
                  "selected_affordance_id": option_id},
        causal_payload={"decision_source": {"kind": "api"}})


def test_ordnance_uses_known_freight_before_investment_then_fires_in_siege():
    world, attacker_id, garrison_id, _ = siege_world(
        attacker_count=40, attacker_provisions=2000, invest=False)
    bag_id = f"stock:camp:{attacker_id}"
    observe_campaign_supply_needs(world)  # The existing observer establishes the bag.
    source_id = _record_equipment_stock(world, location="pontenegro")

    headquarters = headquarters_holder(world, ATTACKER)
    report = world.knowledge.route_report(headquarters, ROAD)
    assert report is not None and report.observed_day == world.clock.absolute_day
    assert report.operational_capacity > 0
    artillery = next(option for option in campaign_ordnance_options(world, ATTACKER)
                     if option.kind == "dispatch" and option.resource_id == "artillery"
                     and option.source_stock_id == source_id)
    assert artillery.campaign_id is None
    assert artillery.detachment_id == attacker_id
    assert artillery.route_ids == (ROAD,)
    assert artillery.route_report_event_ids == (report.event_id,)

    decision = _decision(world, DISPATCH_ACTION, artillery.id)
    artillery_order = execute_campaign_ordnance_option(world, ATTACKER, artillery.id, decision.id)
    assert artillery_order.route_ids == (ROAD,)
    assert report.event_id in {link.cause_event_id
                               for link in world.event_index()[artillery_order.last_event_id].causal_links}
    powder = next(option for option in campaign_ordnance_options(world, ATTACKER)
                  if option.kind == "dispatch" and option.resource_id == "gunpowder"
                  and option.source_stock_id == source_id)
    execute_campaign_ordnance_option(
        world, ATTACKER, powder.id, _decision(world, DISPATCH_ACTION, powder.id).id)

    for _ in range(15):
        bag = world.economy.stocks[bag_id]
        if bag.goods.get("artillery", 0) == 1 and bag.goods.get("gunpowder", 0) == 3:
            break
        world.clock = world.clock.advance(1)
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))
    assert world.economy.stocks[bag_id].goods == {"artillery": 1, "gunpowder": 3}
    assert world.economy.freight_orders[artillery_order.id].delivered_quantity == 1

    investment = next(option for option in settlement_investment_options(
        world, ATTACKER, detachment_id=attacker_id) if option.kind == "invest")
    execute_settlement_investment_option(
        world, ATTACKER, investment.id, decide(world, investment).id)
    siege = next(option for option in siege_campaign_options(world, ATTACKER)
                 if option.defender_garrison_id == garrison_id)
    campaign = begin_siege_campaign(world, ATTACKER, siege.id, decide(world, siege).id)
    endurance_before = world.society.siege_campaigns[campaign.id].garrison_endurance
    bombard = next(option for option in campaign_ordnance_options(world, ATTACKER)
                   if option.kind == "bombard")
    execute_campaign_ordnance_option(
        world, ATTACKER, bombard.id, _decision(world, BOMBARD_ACTION, bombard.id).id)
    assert world.society.siege_campaigns[campaign.id].garrison_endurance == endurance_before - 2
    assert world.economy.stocks[bag_id].goods == {"artillery": 1, "gunpowder": 2}


def test_prepositioned_ordnance_option_expires_when_investment_closes_route():
    world, attacker_id, _, _ = siege_world(invest=False)
    observe_campaign_supply_needs(world)
    source_id = _record_equipment_stock(world, location="pontenegro")
    option = next(item for item in campaign_ordnance_options(world, ATTACKER)
                  if item.kind == "dispatch" and item.resource_id == "artillery"
                  and item.source_stock_id == source_id)
    decision = _decision(world, DISPATCH_ACTION, option.id)

    investment = next(item for item in settlement_investment_options(
        world, ATTACKER, detachment_id=attacker_id) if item.kind == "invest")
    execute_settlement_investment_option(
        world, ATTACKER, investment.id, decide(world, investment).id)
    assert world.map.get_route_operational_capacity(ROAD) == 0
    before_rejection = world_snapshot(world)
    with pytest.raises(ValueError, match="stale or unknown"):
        execute_campaign_ordnance_option(world, ATTACKER, option.id, decision.id)
    assert world_snapshot(world) == before_rejection


def test_ordnance_freight_route_interruption_has_paired_campaign_effects(tmp_path):
    """Paired route closure delays real ordnance for an already active siege."""
    world, attacker_id, garrison_id, siege_option = siege_world(
        attacker_count=40, attacker_provisions=2000, defender_provisions=2000,
        defender_prepared=True, invest=False)
    defender_detachment_id = world.society.garrisons[garrison_id].detachment_id
    observe_campaign_supply_needs(world)
    source_id = _record_equipment_stock(world, location="pontenegro")
    bag_id = f"stock:camp:{attacker_id}"
    artillery = next(item for item in campaign_ordnance_options(world, ATTACKER)
                     if item.kind == "dispatch" and item.resource_id == "artillery"
                     and item.source_stock_id == source_id and item.route_ids == (ROAD,))
    order = execute_campaign_ordnance_option(
        world, ATTACKER, artillery.id, _decision(world, DISPATCH_ACTION, artillery.id).id)
    parcel = next(item for item in world.economy.parcels.values() if item.order_id == order.id)
    powder = next(item for item in campaign_ordnance_options(world, ATTACKER)
                  if item.kind == "dispatch" and item.resource_id == "gunpowder"
                  and item.source_stock_id == source_id and item.route_ids == (ROAD,))
    powder_order = execute_campaign_ordnance_option(
        world, ATTACKER, powder.id, _decision(world, DISPATCH_ACTION, powder.id).id)
    powder_parcel = next(item for item in world.economy.parcels.values()
                         if item.order_id == powder_order.id)
    assert world.economy.stocks[source_id].goods == {"artillery": 0, "gunpowder": 0}
    assert world.economy.stocks[bag_id].goods.get("artillery", 0) == 0
    assert parcel.quantity == 1 and parcel.stage == "waiting"
    assert powder_parcel.quantity == 3 and powder_parcel.stage == "waiting"

    # The ordinary cargo phase genuinely departs before the other actor closes
    # its locally observed route.
    tick(world)
    parcel = world.economy.parcels[parcel.id]
    assert parcel.stage == "traveling" and parcel.quantity == 1
    powder_parcel = world.economy.parcels[powder_parcel.id]
    assert powder_parcel.stage == "traveling" and powder_parcel.quantity == 3
    art_parcel_id, powder_parcel_id = parcel.id, powder_parcel.id
    original_due_days = {parcel.id: parcel.due_day, powder_parcel.id: powder_parcel.due_day}
    original_deadline = max(original_due_days.values())
    control = deepcopy(world)

    # The control branch experiences exactly the same dated world, but the
    # route stays open: both real consignments arrive on their original dates.
    while control.clock.absolute_day < original_deadline:
        tick(control)
    control_bag = control.economy.stocks[bag_id]
    assert control_bag.goods == {"artillery": 1, "gunpowder": 3}
    assert control.economy.freight_orders[order.id].delivered_quantity == 1
    assert control.economy.freight_orders[powder_order.id].delivered_quantity == 3
    assert not any(event.event_type == "cargo_delayed"
                   and any(delta.owner_kind == "cargo"
                           and delta.owner_id in {art_parcel_id, powder_parcel_id}
                           for delta in event.deltas)
                   for event in control.events)
    control_investment = next(item for item in settlement_investment_options(
        control, ATTACKER, detachment_id=attacker_id) if item.kind == "invest")
    execute_settlement_investment_option(
        control, ATTACKER, control_investment.id,
        decide(control, control_investment).id)
    control_siege_option = next(item for item in siege_campaign_options(control, ATTACKER)
                                if item.defender_garrison_id == garrison_id)
    control_campaign = begin_siege_campaign(
        control, ATTACKER, control_siege_option.id, decide(control, control_siege_option).id)
    control_endurance_before = control_campaign.garrison_endurance
    control_bombard = next(item for item in campaign_ordnance_options(control, ATTACKER)
                           if item.kind == "bombard" and item.campaign_id == control_campaign.id)
    control_shot = execute_campaign_ordnance_option(
        control, ATTACKER, control_bombard.id,
        _decision(control, BOMBARD_ACTION, control_bombard.id).id)
    control_endurance_after = control.society.siege_campaigns[control_campaign.id].garrison_endurance
    assert control_endurance_after == control_endurance_before - 2
    assert control.economy.stocks[bag_id].goods["gunpowder"] == 2

    interdiction = next(item for item in route_interdiction_options(world, DEFENDER)
                        if item.kind == "interdict" and item.route_id == ROAD
                        and item.detachment_id == defender_detachment_id)
    blockade = execute_route_interdiction_option(
        world, DEFENDER, interdiction.id, decide(world, interdiction).id)
    assert world.map.get_route_operational_capacity(ROAD) == 0

    while world.clock.absolute_day < original_deadline:
        tick(world)
    parcel = world.economy.parcels[parcel.id]
    delayed = world.event_index()[parcel.last_event_id]
    assert delayed.event_type == "cargo_delayed"
    assert blockade.last_event_id in {link.cause_event_id for link in delayed.causal_links}
    assert parcel.quantity == 1 and parcel.stage == "traveling"
    powder_parcel = world.economy.parcels[powder_parcel.id]
    powder_delayed = world.event_index()[powder_parcel.last_event_id]
    assert powder_delayed.event_type == "cargo_delayed"
    assert blockade.last_event_id in {link.cause_event_id for link in powder_delayed.causal_links}
    assert powder_parcel.quantity == 3 and powder_parcel.stage == "traveling"
    assert world.economy.freight_orders[order.id].delivered_quantity == 0
    assert world.economy.freight_orders[powder_order.id].delivered_quantity == 0
    assert world.economy.stocks[bag_id].goods.get("artillery", 0) == 0
    assert world.economy.stocks[bag_id].goods.get("gunpowder", 0) == 0
    assert not world.society.siege_campaigns
    assert not any(item.kind == "invest" for item in settlement_investment_options(
        world, ATTACKER, detachment_id=attacker_id))
    assert not any(item.kind == "bombard" for item in campaign_ordnance_options(world, ATTACKER))
    assert control_endurance_after == control_endurance_before - 2

    blocked_snapshot = world_snapshot(world)
    blocked_path = tmp_path / "ordnance-interdicted-in-transit.mws"
    save_world(world, blocked_path)
    world = load_world(blocked_path)
    assert world_snapshot(world) == blocked_snapshot
    assert world.map.get_route_operational_capacity(ROAD) == 0
    assert world.economy.parcels[art_parcel_id].quantity == 1
    assert world.economy.parcels[powder_parcel_id].quantity == 3
    assert world.economy.freight_orders[order.id].delivered_quantity == 0
    assert world.economy.freight_orders[powder_order.id].delivered_quantity == 0

    lift = next(item for item in route_interdiction_options(world, DEFENDER)
                if item.kind == "lift" and item.interdiction_id == blockade.id)
    lifted = execute_route_interdiction_option(
        world, DEFENDER, lift.id, decide(world, lift).id)
    assert world.map.get_route_operational_capacity(ROAD) > 0
    for _ in range(30):
        bag = world.economy.stocks[bag_id]
        if bag.goods.get("artillery", 0) == 1 and bag.goods.get("gunpowder", 0) == 3:
            break
        tick(world)
    assert world.economy.stocks[bag_id].goods.get("artillery", 0) == 1
    assert world.economy.freight_orders[order.id].delivered_quantity == 1
    assert world.economy.stocks[bag_id].goods.get("gunpowder", 0) == 3
    assert world.economy.freight_orders[powder_order.id].delivered_quantity == 3
    investment = next(item for item in settlement_investment_options(
        world, ATTACKER, detachment_id=attacker_id) if item.kind == "invest")
    execute_settlement_investment_option(
        world, ATTACKER, investment.id, decide(world, investment).id)
    siege = next(item for item in siege_campaign_options(world, ATTACKER)
                 if item.defender_garrison_id == garrison_id)
    campaign = begin_siege_campaign(world, ATTACKER, siege.id, decide(world, siege).id)
    intervention_endurance_before = campaign.garrison_endurance
    arrival = world.event_index()[world.economy.stocks[bag_id].last_event_ids["artillery"]]
    events = world.event_index()

    def has_ancestor(event_id, ancestor_id):
        pending = [event_id]
        visited = set()
        while pending:
            current = pending.pop()
            if current == ancestor_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            event = events.get(current)
            if event is not None:
                pending.extend(link.cause_event_id for link in event.causal_links)
        return False

    assert has_ancestor(arrival.id, lifted.last_event_id)

    bombard = next(item for item in campaign_ordnance_options(world, ATTACKER)
                   if item.kind == "bombard" and item.campaign_id == campaign.id)
    shot = execute_campaign_ordnance_option(
        world, ATTACKER, bombard.id, _decision(world, BOMBARD_ACTION, bombard.id).id)
    assert world.economy.stocks[bag_id].goods["gunpowder"] == 2
    assert world.society.siege_campaigns[campaign.id].garrison_endurance == (
        intervention_endurance_before - 2)
    events = world.event_index()
    assert has_ancestor(shot.id, arrival.id)
    assert has_ancestor(arrival.id, delayed.id)
    validate_history(world.events, world.clock.absolute_day)
    validate_history(control.events, control.clock.absolute_day)
    assert control_shot.event_type == "siege_artillery_fired"


def test_siege_baggage_moves_with_withdrawing_column_and_survives_disbandment(tmp_path):
    world, attacker_id, _, siege_option = siege_world(attacker_provisions=2000)
    campaign = begin_siege_campaign(world, ATTACKER, siege_option.id,
                                    decide(world, siege_option).id)
    bag_id = campaign_stock_id(attacker_id)
    observe_campaign_supply_needs(world)
    source_id = _record_equipment_stock(world)

    artillery = next(item for item in campaign_ordnance_options(world, ATTACKER)
                     if item.kind == "dispatch" and item.resource_id == "artillery"
                     and item.source_stock_id == source_id)
    art_order = execute_campaign_ordnance_option(
        world, ATTACKER, artillery.id, _decision(world, DISPATCH_ACTION, artillery.id).id)
    powder = next(item for item in campaign_ordnance_options(world, ATTACKER)
                  if item.kind == "dispatch" and item.resource_id == "gunpowder"
                  and item.source_stock_id == source_id)
    powder_order = execute_campaign_ordnance_option(
        world, ATTACKER, powder.id, _decision(world, DISPATCH_ACTION, powder.id).id)
    for _ in range(3):
        tick(world)
    assert world.economy.freight_orders[art_order.id].delivered_quantity == 1
    assert world.economy.freight_orders[powder_order.id].delivered_quantity == 3
    bag = world.economy.stocks[bag_id]
    assert bag.location_id == TARGET and bag.goods == {"artillery": 1, "gunpowder": 3}

    # The campaign owner lifts its own route pressure as part of the current
    # withdrawal decision; no route capacity is edited by the fixture.
    from src.sim.medieval.route_intelligence import refresh_route_reports
    from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
    refresh_route_reports(world, route_ids=(ROAD,))
    refresh_settlement_reports(world)
    retreat = next(item for item in siege_campaign_withdrawal_options(world, ATTACKER)
                   if item.campaign_id == campaign.id and ROAD in item.route_ids)
    withdrawal = withdraw_siege_campaign(
        world, ATTACKER, retreat.id, decide(world, retreat).id)
    assert withdrawal.phase == "withdrawn"
    detachment = world.society.detachments[attacker_id]
    assert detachment.stage == "marching"
    assert world.economy.stocks[bag_id].location_id == TARGET
    for _ in range(30):
        if world.society.detachments[attacker_id].stage == "present":
            break
        tick(world)
    detachment = world.society.detachments[attacker_id]
    bag = world.economy.stocks[bag_id]
    assert detachment.stage == "present" and detachment.location_id == retreat.destination_id
    assert bag.location_id == detachment.location_id
    assert bag.goods == {"artillery": 1, "gunpowder": 3}
    movement = next(event for event in reversed(world.events)
                    if event.event_type == "detachment_arrived"
                    and any(delta.owner_kind == "stock" and delta.owner_id == bag_id
                            and delta.aspect == "location_id" for delta in event.deltas))
    lifted_investment = next(event for event in world.events
                             if event.event_type == "settlement_investment_lifted"
                             and any(delta.owner_kind == "route" and delta.owner_id == ROAD
                                     and delta.aspect == "operational_capacity" for delta in event.deltas))
    assert lifted_investment.id in {link.cause_event_id for link in movement.causal_links}

    disband = next(item for item in force_options(world, ATTACKER)
                   if item.kind == "disband" and item.detachment_id == attacker_id)
    disbanded = disband_detachment(world, ATTACKER, disband.id,
                                   decide(world, disband).id)
    assert disbanded.stage == "disbanded"
    assert world.economy.stocks[bag_id].owner_ref == ATTACKER
    assert world.economy.stocks[bag_id].location_id == retreat.destination_id
    assert world.economy.stocks[bag_id].goods == {"artillery": 1, "gunpowder": 3}
    assert bag.goods["artillery"] == 1 and bag.goods["gunpowder"] == 3
    validate_history(world.events, world.clock.absolute_day)
    save_path = tmp_path / "ordnance-after-disband.mws"
    save_world(world, save_path)
    loaded = load_world(save_path)
    assert world_snapshot(loaded) == world_snapshot(world)
    assert loaded.economy.stocks[bag_id].goods == {"artillery": 1, "gunpowder": 3}
    validate_history(loaded.events, loaded.clock.absolute_day)


def test_campaign_ordnance_requires_knowledge_equipment_and_powder():
    world, _, _, siege_option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, siege_option.id,
                                    decide(world, siege_option).id)
    assert not campaign_ordnance_options(world, ATTACKER)
    assert campaign.id in world.society.siege_campaigns


def test_ordnance_is_dispatched_by_freight_and_bombardment_is_material(tmp_path):
    world, _, _, siege_option = siege_world()
    campaign = _arm_campaign(world, siege_option)

    options = campaign_ordnance_options(world, ATTACKER)
    dispatches = {option.resource_id: option for option in options if option.kind == "dispatch"}
    assert set(dispatches) == {"artillery"}
    source_id = dispatches["artillery"].source_stock_id
    bag_id = f"stock:camp:{campaign.attacker_detachment_id}"
    before = world.economy.stocks[bag_id].goods.copy()

    artillery = dispatches["artillery"]
    artillery_decision = _decision(world, DISPATCH_ACTION, artillery.id)
    order = execute_campaign_ordnance_option(world, ATTACKER, artillery.id, artillery_decision.id)
    assert order.route_ids == ()
    assert world.economy.stocks[bag_id].goods == before
    assert world.economy.stocks[source_id].goods["artillery"] == 0
    world.clock = world.clock.advance(1)
    resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))

    powder = next(item for item in campaign_ordnance_options(world, ATTACKER)
                  if item.kind == "dispatch" and item.resource_id == "gunpowder")
    powder_decision = _decision(world, DISPATCH_ACTION, powder.id)
    powder_order = execute_campaign_ordnance_option(world, ATTACKER, powder.id, powder_decision.id)
    assert powder_order.route_ids == ()
    assert world.economy.stocks[bag_id].goods["artillery"] == 1
    assert world.economy.stocks[bag_id].goods.get("gunpowder", 0) == 0
    assert world.economy.stocks[source_id].goods["gunpowder"] == 0
    world.clock = world.clock.advance(1)
    resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))

    bag = world.economy.stocks[bag_id]
    assert bag.goods["artillery"] == 1
    assert bag.goods["gunpowder"] == 3
    detachment = world.society.detachments[campaign.attacker_detachment_id]
    assert campaign_baggage_ready_for_departure(world, detachment, ignore_notice=True)
    bombard = next(item for item in campaign_ordnance_options(world, ATTACKER)
                   if item.kind == "bombard")
    active = world.society.siege_campaigns[campaign.id]
    decision = _decision(world, BOMBARD_ACTION, bombard.id)
    receipt = execute_campaign_ordnance_option(world, ATTACKER, bombard.id, decision.id)
    after = world.society.siege_campaigns[campaign.id]
    assert after.garrison_endurance == max(0, active.garrison_endurance - 2)
    assert world.economy.stocks[bag_id].goods == {"artillery": 1, "gunpowder": 2}
    if after.garrison_endurance == 0:
        assert after.phase == "breached"
        assert world.society.garrisons[campaign.defender_garrison_id].stage == "collapsed"
        assert world.society.settlements[TARGET].occupier_id == DEFENDER.id
    assert receipt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert decision.id in {link.cause_event_id for link in receipt.causal_links}
    assert not any(item.kind == "bombard" for item in campaign_ordnance_options(world, ATTACKER))

    snapshot_after_shot = world_snapshot(world)
    stale = _decision(world, BOMBARD_ACTION, bombard.id)
    before_rejection = world_snapshot(world)
    with pytest.raises(ValueError, match="stale or unknown"):
        execute_campaign_ordnance_option(world, ATTACKER, bombard.id, stale.id)
    assert world_snapshot(world) == before_rejection
    assert snapshot_after_shot != before_rejection  # only the rejected attempt's decision was appended

    save = tmp_path / "campaign-ordnance.mws"
    save_world(world, save)
    loaded = load_world(save)
    assert world_snapshot(loaded) == world_snapshot(world)
    assert loaded.economy.stocks[bag_id].goods == {"artillery": 1, "gunpowder": 2}

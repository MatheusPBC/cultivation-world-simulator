"""The relief act: a real, dated choice by the granary's own owner, never a
standing rate. See docs/handoff/plano-consequencia-causal.md (Passo 4)."""

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import consume_monthly
from src.sim.medieval.events import record_event
from src.sim.medieval.institutional_aid import aid_request_options
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.relief import (distribute_relief, execute_relief_transfer,
                                     relief_settlement_options, relief_transfer_options)
from src.sim.medieval.relief_policy import FALLBACK_MIN_SHORTFALL, review_relief_fallback
from src.sim.medieval.concurrent_civil_decision import concurrent_civil_options
from src.systems.time import WorldClock

TARGET = "pedraclara"


def _prepared_shortage():
    """A real, unpaid shortfall this month: no household has any money."""
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    world.clock = WorldClock(30)
    stock = world.economy.stocks[f"stock:{TARGET}"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 1000}})
    consume_monthly(world)
    assert world.economy.needs[TARGET].missing_food > 0
    return world


def _decide(world, option):
    report = world.knowledge.settlement_reports[option.report_id]
    return record_event(world, "relief_distribution_decided", "Decisão: distribuir ajuda alimentar do próprio celeiro.",
                        fact_kind=FactKind.DECISION, decision=option.decision(), cause_ids=(report.event_id,))


def test_relief_act_moves_real_food_and_reduces_the_real_shortfall():
    world = _prepared_shortage()
    stock_before = world.economy.stocks[f"stock:{TARGET}"].goods.get("food", 0)
    need_before = world.economy.needs[TARGET]

    refresh_reports(world)
    options = relief_settlement_options(world, world.economy.stocks[need_before.stock_id].owner_ref.id)
    option = next(item for item in options if item.settlement_id == TARGET)
    assert option.quantity > 0
    decision = _decide(world, option)

    event = distribute_relief(world, option.id, decision_event_id=decision.id)
    assert event.event_type == "relief_distributed"
    assert event.fact_kind == FactKind.STATE_TRANSITION
    assert decision.id in {link.cause_event_id for link in event.causal_links}

    stock_after = world.economy.stocks[f"stock:{TARGET}"].goods.get("food", 0)
    need_after = world.economy.needs[TARGET]
    assert stock_after == stock_before - option.quantity
    assert need_after.missing_food == need_before.missing_food - option.quantity
    assert {(d.owner_kind, d.owner_id, d.aspect) for d in event.deltas} >= {
        ("stock", f"stock:{TARGET}", "food"), ("subsistence", TARGET, "missing_food")}
    household_food = sum(
        world.economy.stocks[f"household-stock:{group.id}"].goods.get("food", 0)
        for group in world.society.population.values()
        if group.settlement_id == TARGET and f"household-stock:{group.id}" in world.economy.stocks
    )
    assert household_food == option.quantity
    assert event.causal_payload["relief_distribution"]["quantity"] == option.quantity


def test_relief_only_reaches_households_with_unpaid_rations(tmp_path):
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    world.clock = WorldClock(30)
    group_ids = sorted(group.id for group in world.society.population.values()
                       if group.settlement_id == TARGET and group.count)
    fed_id = group_ids[0]
    for group_id in group_ids:
        account = world.economy.accounts[f"household:{group_id}"]
        world.economy.accounts[account.id] = account.model_copy(
            update={"balance": 10000 if group_id == fed_id else 0})
    consume_monthly(world)
    subsistence = next(event for event in reversed(world.events)
                       if event.event_type == "subsistence_resolved"
                       and event.causal_payload["subsistence"]["settlement_id"] == TARGET)
    unpaid = subsistence.causal_payload["subsistence"]["unmet_by_group"]
    assert fed_id not in unpaid
    assert sum(unpaid.values()) == world.economy.needs[TARGET].missing_food

    refresh_reports(world)
    need = world.economy.needs[TARGET]
    polity_id = world.economy.stocks[need.stock_id].owner_ref.id
    option = max((item for item in relief_settlement_options(world, polity_id)
                  if item.settlement_id == TARGET), key=lambda item: item.quantity)
    receipt = distribute_relief(world, option.id, decision_event_id=_decide(world, option).id)
    allocations = receipt.causal_payload["relief_distribution"]["household_allocations"]
    assert fed_id not in allocations
    assert sum(allocations.values()) == option.quantity
    assert all(amount <= unpaid[group_id] for group_id, amount in allocations.items())
    path = tmp_path / "targeted-relief.mws"
    save_world(world, path)
    loaded = load_world(path)
    assert world_snapshot(loaded) == world_snapshot(world)
    assert loaded.event_index()[receipt.id].causal_payload == receipt.causal_payload


def test_relief_recovers_condition_only_in_proportion_to_food_delivered():
    world = _prepared_shortage()
    refresh_reports(world)
    need_before = world.economy.needs[TARGET]
    polity_id = world.economy.stocks[need_before.stock_id].owner_ref.id
    option = next(item for item in relief_settlement_options(world, polity_id)
                  if item.settlement_id == TARGET)
    decision = _decide(world, option)

    event = distribute_relief(world, option.id, decision_event_id=decision.id)
    need_after = world.economy.needs[TARGET]
    covered = min(option.quantity, need_before.missing_food)
    expected_recovery = (20 * covered + need_before.missing_food - 1) // need_before.missing_food

    assert need_after.health == min(1000, need_before.health + expected_recovery)
    assert need_after.unrest == max(0, need_before.unrest - expected_recovery)
    assert {delta.aspect for delta in event.deltas if delta.owner_kind == "subsistence"} >= {
        "missing_food", "health", "unrest"}


def test_relief_pantries_are_consumed_before_next_monthly_purchase():
    world = _prepared_shortage()
    refresh_reports(world)
    need_before = world.economy.needs[TARGET]
    polity_id = world.economy.stocks[need_before.stock_id].owner_ref.id
    option = next(item for item in relief_settlement_options(world, polity_id)
                  if item.settlement_id == TARGET)
    distribute_relief(world, option.id, decision_event_id=_decide(world, option).id)

    world.clock = WorldClock(60)
    consume_monthly(world)

    pantry_food = sum(
        world.economy.stocks[item].goods.get("food", 0)
        for item in world.economy.stocks
        if item.startswith("household-stock:")
        and world.economy.stocks[item].location_id == TARGET
    )
    assert pantry_food == 0
    assert world.economy.needs[TARGET].missing_food == need_before.missing_food - option.quantity


def test_relief_act_replay_has_no_effect():
    world = _prepared_shortage()
    refresh_reports(world)
    need_before = world.economy.needs[TARGET]
    options = relief_settlement_options(world, world.economy.stocks[need_before.stock_id].owner_ref.id)
    option = next(item for item in options if item.settlement_id == TARGET)
    decision = _decide(world, option)
    distribute_relief(world, option.id, decision_event_id=decision.id)

    before = world_snapshot(world), list(world.events)

    # Same option, same decision: already executed.
    with pytest.raises(ValueError):
        distribute_relief(world, option.id, decision_event_id=decision.id)
    assert (world_snapshot(world), world.events) == before

    # Same option, a brand-new decision citing it: the option itself is stale
    # now (the report and the granary it was measured against have moved on).
    # Recording that decision is a legitimate fact on its own -- decisions
    # never carry deltas -- so only the material state is compared here.
    stock_before_replay = world.economy.stocks[f"stock:{TARGET}"].goods.get("food", 0)
    need_before_replay = world.economy.needs[TARGET].missing_food
    replay_decision = _decide(world, option)
    with pytest.raises(ValueError):
        distribute_relief(world, option.id, decision_event_id=replay_decision.id)
    assert world.economy.stocks[f"stock:{TARGET}"].goods.get("food", 0) == stock_before_replay
    assert world.economy.needs[TARGET].missing_food == need_before_replay


def test_relief_is_registered_in_the_composed_civil_menu():
    world = _prepared_shortage()
    refresh_reports(world)
    polity = world.economy.stocks[world.economy.needs[TARGET].stock_id].owner_ref
    options = concurrent_civil_options(world, polity)
    relief = [option for option in options if option.id.startswith("relief-distribute:")]
    assert relief
    assert all(option.decision()["selected_affordance_id"] == option.id for option in relief)


def test_offline_relief_fallback_selects_an_urgent_current_option_and_keeps_authorship():
    world = _prepared_shortage()
    refresh_reports(world)
    before = world.economy.needs[TARGET].missing_food

    events = review_relief_fallback(world)

    # One fallback action is permitted for each polity, not for every
    # settlement. This fixture pressures every polity, so locate the direct
    # act that owns the target rather than asserting a global count of one.
    assert 1 <= len(events) <= len(world.society.polities)
    effect = next(event for event in events
                  if event.causal_payload["relief_distribution"]["settlement_id"] == TARGET)
    assert effect.event_type == "relief_distributed"
    decision = next(event for event in world.events
                    if event.id in {link.cause_event_id for link in effect.causal_links}
                    and event.fact_kind == FactKind.DECISION)
    assert decision.causal_origin.value == "actor_decision"
    assert decision.decision["selected_affordance_id"].startswith("relief-distribute:")
    assert world.economy.needs[TARGET].missing_food < before


def test_offline_relief_fallback_maintains_when_only_a_tiny_remainder_is_observed():
    world = _prepared_shortage()
    for settlement_id, need in tuple(world.economy.needs.items()):
        world.economy.needs[settlement_id] = need.model_copy(
            update={"missing_food": FALLBACK_MIN_SHORTFALL - 1})
    refresh_reports(world)

    assert review_relief_fallback(world) == ()
    assert not any(event.event_type == "relief_distributed" for event in world.events)


def test_relief_refreshes_existing_local_knowledge_before_same_day_aid_options():
    world = _prepared_shortage()
    need = world.economy.needs[TARGET]
    world.economy.needs[TARGET] = need.model_copy(update={"missing_food": 300})
    refresh_reports(world)
    polity_id = world.economy.stocks[need.stock_id].owner_ref.id
    option = max((item for item in relief_settlement_options(world, polity_id)
                  if item.settlement_id == TARGET), key=lambda item: item.quantity)
    assert option.quantity == 300

    effect = distribute_relief(world, option.id, decision_event_id=_decide(world, option).id)

    report = world.knowledge.settlement_report(EntityRef("polity", polity_id), TARGET)
    assert report is not None
    assert report.missing_food == 0
    report_event = next(event for event in world.events if event.id == report.event_id)
    assert effect.id in {link.cause_event_id for link in report_event.causal_links}
    assert not any(option.requester_settlement_id == TARGET
                   for option in aid_request_options(world, EntityRef("polity", polity_id)))


def test_owner_can_choose_a_routed_surplus_transfer_between_own_settlements():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    source = world.economy.stocks["stock:pedraclara"]
    world.economy.stocks[source.id] = source.model_copy(update={"goods": {**source.goods, "food": 1000}})
    need = world.economy.needs["campomanso"]
    world.economy.needs[need.id] = need.model_copy(update={"missing_food": 300})
    refresh_reports(world)
    actor = source.owner_ref
    option = relief_transfer_options(world, actor)[0]
    decision = record_event(
        world, "relief_transfer_decided", "Decisão de enviar excedente alimentar por rota observada.",
        fact_kind=FactKind.DECISION, decision=option.decision(),
        cause_ids=(option.source_inventory_event_id,
                   world.knowledge.settlement_reports[option.destination_report_id].event_id))

    before = world.economy.stocks[option.source_stock_id].goods["food"]
    order = execute_relief_transfer(world, actor, option.id, decision.id)
    assert order.source_id == option.source_stock_id
    assert order.destination_id == option.destination_stock_id
    assert world.economy.stocks[option.source_stock_id].goods["food"] == before - option.quantity
    assert world.economy.needs["campomanso"].missing_food == 300
    assert any(event.event_type == "freight_opened" and decision.id in {
        link.cause_event_id for link in event.causal_links} for event in world.events)


def test_routed_relief_exposes_full_and_partial_engine_bounded_coverages():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    source = world.economy.stocks["stock:pedraclara"]
    world.economy.stocks[source.id] = source.model_copy(update={"goods": {**source.goods, "food": 1000}})
    need = world.economy.needs["campomanso"]
    world.economy.needs[need.id] = need.model_copy(update={"missing_food": 300})
    refresh_reports(world)

    quantities = {option.quantity for option in relief_transfer_options(world, source.owner_ref)
                  if option.destination_settlement_id == "campomanso"}
    assert quantities == {150, 300}
    first = next(option for option in relief_transfer_options(world, source.owner_ref)
                 if option.destination_settlement_id == "campomanso")
    assert first.quantity == 300


def test_routed_relief_keeps_origin_settlement_shortfall_reserved():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    source = world.economy.stocks["stock:pontenegro"]
    world.economy.stocks[source.id] = source.model_copy(update={"goods": {**source.goods, "food": 2500}})
    source_need = world.economy.needs["pontenegro"]
    world.economy.needs[source_need.id] = source_need.model_copy(update={"missing_food": 500})
    destination_need = world.economy.needs["campomanso"]
    world.economy.needs[destination_need.id] = destination_need.model_copy(update={"missing_food": 300})
    refresh_reports(world)

    options = tuple(option for option in relief_transfer_options(world, source.owner_ref)
                    if option.source_stock_id == source.id
                    and option.destination_settlement_id == "campomanso")
    assert options
    assert max(option.quantity for option in options) == 200


def test_routed_relief_never_enumerates_a_foreign_destination_stock():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    source = world.economy.stocks["stock:pedraclara"]
    world.economy.stocks[source.id] = source.model_copy(update={"goods": {**source.goods, "food": 1000}})
    actor = source.owner_ref
    foreign_need = next(need for need in world.economy.needs.values()
                        if world.economy.stocks[need.stock_id].owner_ref != actor)
    world.economy.needs[foreign_need.id] = foreign_need.model_copy(update={"missing_food": 300})
    settlement = world.society.settlements[foreign_need.id]
    # An administration can observe a settlement whose public stock belongs
    # elsewhere. Observation is not ownership, so this must still not create
    # an internal-transfer option.
    world.society.settlements[foreign_need.id] = settlement.model_copy(
        update={"administrator_id": actor.id})
    refresh_reports(world)

    options = relief_transfer_options(world, actor)

    assert any(report.settlement_id == foreign_need.id
               for report in world.knowledge.settlements_for_actor(actor))
    assert all(world.economy.stocks[option.destination_stock_id].owner_ref == actor
               for option in options)


def test_routed_relief_transfer_is_present_in_the_deterministic_civil_catalog():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    source = world.economy.stocks["stock:pedraclara"]
    world.economy.stocks[source.id] = source.model_copy(update={"goods": {**source.goods, "food": 1000}})
    need = world.economy.needs["campomanso"]
    world.economy.needs[need.id] = need.model_copy(update={"missing_food": 300})
    refresh_reports(world)
    options = concurrent_civil_options(world, source.owner_ref)
    assert any(option.id.startswith("relief-transfer:") for option in options)

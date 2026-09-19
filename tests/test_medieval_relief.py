"""The relief act: a real, dated choice by the granary's own owner, never a
standing rate. See docs/handoff/plano-consequencia-causal.md (Passo 4)."""

import pytest

from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import consume_monthly
from src.sim.medieval.events import record_event
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.persistence import world_snapshot
from src.sim.medieval.relief import (distribute_relief, execute_relief_transfer,
                                     relief_settlement_options, relief_transfer_options)
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

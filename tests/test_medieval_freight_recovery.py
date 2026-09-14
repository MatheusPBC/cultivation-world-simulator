"""A blocked shipment is history: recovery is a new order, never a rewrite."""

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.economy import _delta
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.freight_recovery import (execute_freight_recovery, freight_recovery_options)
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from tests.test_medieval_logistics import DEST, ROAD, SOURCE, cargo_world, ship, total_food

OWNER = EntityRef("polity", "auren")


def close_route(world, route_id=ROAD):
    """Prepared material fact; the executor never invents an interruption."""
    route = world.map.routes[route_id]
    fact = record_event(world, "landslide_closed_the_road", "Deslizamento interditou a estrada.",
                        fact_kind=FactKind.STATE_TRANSITION,
                        deltas=(_delta("route", route_id, "enabled", route.enabled, False),))
    route.update_runtime(enabled=False)
    return fact


async def blocked_world(quantity=40):
    world = cargo_world()
    stock = world.economy.stocks[SOURCE]
    # Prepared holdings so the owner could actually send a successor shipment.
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "food": stock.goods.get("food", 0) + 5000}})
    refresh_reports(world)
    order = ship(world, quantity)
    close_route(world)
    await MedievalSimulator(world).step()
    refresh_reports(world)
    assert world.economy.freight_orders[order.id].delivered_quantity == 0
    return world, world.economy.freight_orders[order.id]


def decide(world, option, *, origin=CausalOrigin.ACTOR_DECISION):
    return record_event(world, "freight_recovery_decided", "O proprietário escolheu uma opção de recuperação.",
                        fact_kind=FactKind.DECISION, causal_origin=origin, decision=option.decision())


async def test_a_blocked_order_offers_only_waiting_or_a_successor_over_another_route():
    world, order = await blocked_world()
    options = freight_recovery_options(world, OWNER)

    kinds = {option.kind for option in options}
    assert kinds == {"wait", "successor"}
    for option in options:
        assert option.order_id == order.id and option.order_last_event_id == order.last_event_id
        assert option.source_id == order.source_id and option.destination_id == order.destination_id
        assert option.resource_id == order.resource_id
        if option.kind == "successor":
            assert ROAD not in option.route_ids and option.route_ids
            assert option.quantity == order.quantity
    # Another owner reconstructs nothing from this cargo.
    assert freight_recovery_options(world, EntityRef("polity", "valedouro")) == ()


async def test_waiting_changes_nothing_material():
    world, order = await blocked_world()
    option = next(item for item in freight_recovery_options(world, OWNER) if item.kind == "wait")
    before = world_snapshot(world)

    assert execute_freight_recovery(world, option.id, decision_event_id=decide(world, option).id) is None

    after = world_snapshot(world)
    assert after["event_count"] == before["event_count"] + 1, "only the decision was recorded"
    assert {key: value for key, value in after.items() if key != "event_count"} == {
        key: value for key, value in before.items() if key != "event_count"}


async def test_a_successor_moves_new_cargo_and_leaves_the_original_untouched(tmp_path):
    world, order = await blocked_world()
    option = next(item for item in freight_recovery_options(world, OWNER) if item.kind == "successor")
    food = total_food(world)
    source_goods = world.economy.stocks[SOURCE].goods["food"]
    decision = decide(world, option)

    successor = execute_freight_recovery(world, option.id, decision_event_id=decision.id)

    assert successor.id != order.id and successor.route_ids == option.route_ids
    assert successor.quantity == option.quantity and successor.decision_ids == (decision.id,)
    assert successor.source_id == order.source_id and successor.destination_id == order.destination_id
    receipt = next(event for event in world.events if event.id == successor.last_event_id)
    causes = {link.cause_event_id for link in receipt.causal_links}
    assert decision.id in causes and order.last_event_id in causes

    kept = world.economy.freight_orders[order.id]
    assert (kept.route_ids, kept.quantity, kept.decision_ids, kept.delivered_quantity, kept.last_event_id) == (
        order.route_ids, order.quantity, order.decision_ids, 0, order.last_event_id)
    assert total_food(world) == food
    assert world.economy.stocks[SOURCE].goods["food"] == source_goods - option.quantity
    world.economy.validate(world)

    path = tmp_path / "recovery.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)
    assert resumed.economy.freight_orders[successor.id] == successor
    assert freight_recovery_options(resumed, OWNER) != ()


@pytest.mark.parametrize("rejection", ["invented", "stale", "replayed", "interpretation", "wrong_actor"])
async def test_recovery_rejects_stale_invented_or_narrated_selections(rejection):
    world, order = await blocked_world()
    option = next(item for item in freight_recovery_options(world, OWNER) if item.kind == "successor")
    if rejection == "replayed":
        decision = decide(world, option)
        execute_freight_recovery(world, option.id, decision_event_id=decision.id)
        before = world_snapshot(world)
        with pytest.raises(ValueError):
            execute_freight_recovery(world, option.id, decision_event_id=decision.id)
        assert world_snapshot(world) == before
        return
    if rejection == "stale":
        # A further day of delay replaces the receipt the option was built on.
        await MedievalSimulator(world).step()
        assert world.economy.freight_orders[order.id].last_event_id != option.order_last_event_id
    origin = CausalOrigin.LLM_INTERPRETATION if rejection == "interpretation" else CausalOrigin.ACTOR_DECISION
    chosen = option.model_copy(update={"id": "freight_recovery:invented"}) if rejection == "invented" else option
    if rejection == "wrong_actor":
        chosen = option.model_copy(update={"actor_ref": EntityRef("polity", "valedouro")})
    decision = decide(world, chosen, origin=origin)
    before, food = world_snapshot(world), total_food(world)
    with pytest.raises(ValueError):
        execute_freight_recovery(world, chosen.id, decision_event_id=decision.id)
    assert world_snapshot(world) == before
    assert total_food(world) == food


async def test_a_purchased_shipment_is_not_recoverable_without_a_bilateral_decision():
    from tests.test_medieval_markets import consent, terms
    world = cargo_world()
    refresh_reports(world)
    values = terms(world, quantity=20)
    from src.sim.medieval.markets import purchase
    order = purchase(world, *consent(world, values))
    close_route(world, order.route_ids[0])
    await MedievalSimulator(world).step()

    buyer = world.economy.stocks[order.destination_id].owner_ref
    assert not [item for item in freight_recovery_options(world, buyer) if item.order_id == order.id]


async def test_a_failed_save_rolls_back_the_successor(tmp_path, monkeypatch):
    world, order = await blocked_world()
    option = next(item for item in freight_recovery_options(world, OWNER) if item.kind == "successor")
    execute_freight_recovery(world, option.id, decision_event_id=decide(world, option).id)
    before, history = world_snapshot(world), list(world.events)
    from src.sim.medieval import engine

    def fail(*args, **kwargs):
        raise OSError("disk unavailable")
    monkeypatch.setattr(engine, "save_world", fail)
    with pytest.raises(OSError, match="disk"):
        await MedievalSimulator(world, save_path=tmp_path / "failed.mws").step()
    assert world_snapshot(world) == before and world.events == history

"""The Onda 1 acceptance chain, proven end to end as one causal sequence.

The roadmap asks for exactly this: an interrupted route changes stock, delivery
and population, and an alternative route can recover the situation without a
scripted battle.  Each hop already has its own focused test -- scarcity in
``test_medieval_route_scarcity``, the successor shipment in
``test_medieval_freight_recovery``, the distribution act in
``test_medieval_relief`` -- but nothing composes them, so the acceptance itself
was never exercised.

Nothing here invents food or money.  The premise is material: the origin
granary holds a real surplus, the destination holds none, and a recorded fact
closes the only direct passage.  Both discretionary acts go through the single
composed institutional turn, so the chain is the one a real actor would walk.
The recovery is deliberately partial: delivered food still has to be bought,
and the residual deficit is asserted rather than wished away.
"""

import json

import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.economy import transfer_money
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.routing import supply_path
from src.classes.event import FactKind

from tests.test_medieval_freight_recovery import close_route
from tests.test_medieval_logistics import DEST, ROAD, SOURCE, cargo_world, ship, total_food


AUREN = EntityRef("polity", "auren")
SETTLEMENT = "pedraclara"
# Larger than everything the destination's households can pay for, so the
# arrival cannot be entirely absorbed by ordinary purchases and a real public
# act is still needed.  It stays far below the origin's surplus.
SHIPMENT = 3000
SURPLUS = 8000

SUCCESSOR_LABEL = "Abrir uma remessa sucessora"
RELIEF_LABEL = "Distribuir "
RELIEF_TARGET = f"ao assentamento {SETTLEMENT} a partir do próprio estoque."
DECISION_EVENT = "institutional_decision_turn_decided"


def _is_successor(label):
    return label.startswith(SUCCESSOR_LABEL)


def _is_relief_here(label):
    return label.startswith(RELIEF_LABEL) and label.endswith(RELIEF_TARGET)


def prepared_world():
    """A real surplus, an empty destination and partly funded households."""
    world = cargo_world()
    source = world.economy.stocks[SOURCE]
    world.economy.stocks[SOURCE] = source.model_copy(
        update={"goods": {**source.goods, "food": source.goods.get("food", 0) + SURPLUS}})
    world.economy.stocks[DEST] = world.economy.stocks[DEST].model_copy(update={"goods": {}})
    # The prepared starting condition has a dated, conserved payment from the
    # local administration. Families can buy half a cycle's rations if cargo
    # arrives, while the other half still requires a later public decision.
    price = world.economy.markets[SETTLEMENT].prices["food"]
    for group in sorted(world.society.population.values(), key=lambda value: value.id):
        if group.settlement_id != SETTLEMENT:
            continue
        amount = (group.count // 2) * price
        account_id = f"household:{group.id}"
        decision = record_event(
            world, "payment_decided", "A administração destinou renda inicial ao domicílio.",
            fact_kind=FactKind.DECISION,
            decision={"action": "pay", "source_id": "treasury:auren",
                      "target_id": account_id, "amount": amount,
                      "actor_ref": AUREN.to_dict()},
        )
        transfer_money(world, "treasury:auren", account_id, amount,
                       decision_event_id=decision.id)
    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 4000})
    return world


def install_provider(monkeypatch):
    """One stub actor: reopen the blocked cargo first, then feed the town.

    Only the administration under test answers; every other institution
    declines, so the chain cannot be completed by a neighbour acting off
    screen.  It answers with an ID the engine itself enumerated, and matches on
    the label because an affordance ID carrying a private stock or treasury
    identifier reaches the prompt as an opaque alias.
    """
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    chosen = []
    state = {"recovery_selected": False}

    async def answer(prompt, *_args, **_kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        if payload["you_are"] != AUREN.to_dict():
            return {"selected_id": ai_decider.NO_ACTION}
        choices = payload["choices"]
        # Strict ordering, and never both in the same boundary: reopen the
        # delivery as soon as the engine offers that affordance, waiting as
        # long as it does not, and only then spend a later monthly act on
        # feeding the town.  The blocked order never unblocks, so its recovery
        # affordance keeps being offered; taking it once is enough.
        if not state["recovery_selected"]:
            picked = next((item for item in choices if _is_successor(item["label"])), None)
            if picked is None:
                return {"selected_id": ai_decider.NO_ACTION}
            state["recovery_selected"] = True
            chosen.append(picked["label"])
            return {"selected_id": picked["id"]}
        picked = next((item for item in choices if _is_relief_here(item["label"])), None)
        if picked is None:
            return {"selected_id": ai_decider.NO_ACTION}
        chosen.append(picked["label"])
        return {"selected_id": picked["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", answer)
    return chosen


def subsistence_readings(world):
    """Every dated affordability reading published for the destination."""
    return [(event.day, event.causal_payload["subsistence"]) for event in world.events
            if event.causal_payload and "subsistence" in event.causal_payload
            and event.causal_payload["subsistence"]["settlement_id"] == SETTLEMENT]


async def advance_to(world, engine, day):
    while world.clock.absolute_day < day:
        await engine.step()


@pytest.mark.asyncio
async def test_interrupted_route_recovers_through_an_alternative_path_and_a_public_act(monkeypatch, tmp_path):
    world = prepared_world()
    chosen = install_provider(monkeypatch)
    engine = MedievalSimulator(world)

    # A paired world keeps the same initial stock, shipment and actor policy.
    # The only material difference is that its direct passage remains open.
    open_world = prepared_world()
    direct = ship(open_world, SHIPMENT)
    await advance_to(open_world, MedievalSimulator(open_world), 30)
    assert open_world.economy.freight_orders[direct.id].delivered_quantity > 0

    interruption = close_route(world)
    blocked = ship(world, SHIPMENT)
    assert blocked.route_ids == (ROAD,)

    # 1. The closed passage becomes the settlement's dated material condition.
    await advance_to(world, engine, 30)
    need = world.economy.needs[SETTLEMENT]
    open_need = open_world.economy.needs[SETTLEMENT]
    assert need.missing_food > 0 and need.unrest > 0
    assert need.missing_food > open_need.missing_food
    assert need.health < open_need.health
    assert world.economy.freight_orders[blocked.id].delivered_quantity == 0
    assert world.economy.stocks[DEST].goods.get("food", 0) == 0
    scarcity = next(event for event in world.events
                    if event.event_type == "subsistence_resolved"
                    and any(delta.owner_id == SETTLEMENT for delta in event.deltas))
    assert interruption.id in {link.cause_event_id for link in scarcity.causal_links}

    # 2. The same boundary's single institutional turn reopened the delivery
    #    over a different passage.  One act per actor per boundary: relief was
    #    also on the menu and did not happen yet.
    assert chosen and _is_successor(chosen[0])
    successor = next(order for order in world.economy.freight_orders.values()
                     if order.id != blocked.id and order.resource_id == "food"
                     and order.destination_id == DEST)
    assert ROAD not in successor.route_ids and successor.route_ids
    assert successor.route_ids == supply_path(world, "campomanso", SETTLEMENT, "food")
    assert successor.source_id == blocked.source_id and successor.destination_id == blocked.destination_id
    assert not any(event.event_type == "relief_distributed" for event in world.events)
    decision = next(event for event in reversed(world.events) if event.event_type == DECISION_EVENT)
    assert set(decision.decision) == {"action", "actor_ref", "selected_affordance_id"}

    # 3. The original order is history: never rerouted, refunded or re-executed.
    kept = world.economy.freight_orders[blocked.id]
    assert (kept.route_ids, kept.quantity, kept.decision_ids, kept.delivered_quantity) == (
        (ROAD,), blocked.quantity, blocked.decision_ids, 0)

    # 4. Nothing is created in transit.  Between two monthly closings no ration
    #    is consumed, so every unit in flight is still accounted for -- in a
    #    granary, in a household pantry, or on the road.
    in_flight = total_food(world)
    await advance_to(world, engine, 59)
    assert total_food(world) == in_flight
    assert world.economy.stocks[DEST].goods.get("food", 0) > 0

    # 5. The alternative has finite throughput: its first arrivals permit
    #    real purchases, but have not yet covered demand. Later, once more
    #    stock arrives, the remaining household income becomes a separate
    #    constraint that freight alone cannot solve.
    await advance_to(world, engine, 60)
    arrival_day, arrival = subsistence_readings(world)[-1]
    assert arrival_day == 60
    assert 0 < arrival["purchased_quantity"] < arrival["required"]
    assert 0 < arrival["missing_food"] < scarcity.causal_payload["subsistence"]["missing_food"]

    # 6. The public act closes the chain: the owner gives away its own arrived
    #    food, and the settlement's condition improves by exactly what moved.
    await advance_to(world, engine, 90)
    relief = next((event for event in world.events if event.event_type == "relief_distributed"), None)
    assert relief is not None and relief.day >= 60, "a distribuição veio depois da entrega"
    assert any(_is_relief_here(label) for label in chosen)
    turn_decisions = {event.id for event in world.events if event.event_type == DECISION_EVENT}
    assert {link.cause_event_id for link in relief.causal_links} & turn_decisions, (
        "a distribuição veio do turno institucional")

    moved = {delta.owner_id: (int(delta.before), int(delta.after)) for delta in relief.deltas
             if delta.owner_kind == "stock" and delta.aspect == "food"}
    granary_before, granary_after = moved[DEST]
    pantries = sum(after - before for key, (before, after) in moved.items() if key != DEST)
    assert granary_before - granary_after > 0
    assert pantries == granary_before - granary_after, "a ajuda moveu comida, não a criou"
    assert all(key.startswith("household-stock:") for key in moved if key != DEST)

    shortfall = next((int(delta.before), int(delta.after)) for delta in relief.deltas
                     if delta.owner_kind == "subsistence" and delta.aspect == "missing_food")
    assert shortfall[1] < shortfall[0], "a condição material do assentamento melhorou"
    health = next((int(delta.before), int(delta.after)) for delta in relief.deltas
                  if delta.owner_kind == "subsistence" and delta.aspect == "health")
    assert health[1] > health[0], "a recuperação atingiu a saúde, não só o relatório de fome"

    # 7. The recovery is real and partial.  Routes and delivery were never the
    #    whole cause: what the households still cannot buy stays missing, and
    #    the next closing shows the pressure has not been scripted away.
    await advance_to(world, engine, 120)
    residual_day, residual = subsistence_readings(world)[-1]
    assert residual_day == 120
    assert residual["missing_food"] > 0, "o déficit de renda permanece; a rota não era a causa inteira"
    assert sum(residual["unaffordable_by_group"].values()) > 0
    # The granary still holds food nobody can buy: the remaining shortfall is
    # an income fact, not a delivery one.
    assert world.economy.stocks[DEST].goods.get("food", 0) > 0

    path = tmp_path / "route-recovery.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)
    assert resumed.events == world.events
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True

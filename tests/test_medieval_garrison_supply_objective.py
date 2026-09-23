"""A standing military duty an institution chose to sustain.

Objectives could reserve materials for production, subsistence and works, but
never for a garrison: military upkeep was reactive, notice by notice, so a
column's rations competed on equal footing with everything else every month.
This objective only declares priority over food that already exists in the
settlement's own public stock. It buys nothing, recruits nobody, marches no
one, and keeps no duty alive: an unpaid garrison still lapses on its own owner.
"""

import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.demand import garrison_demand, reserve_quantity
from src.sim.medieval.events import record_event
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.strategy_response import (execute_garrison_supply, garrison_supply_adapters,
                                                garrison_supply_blocker, garrison_supply_options)

from tests.test_medieval_garrison_policy import OWNER, _decision


def garrisoned_world():
    """Auren marches on Salgueiro, occupies it and pays a standing garrison."""
    from src.run.medieval_world import create_medieval_world
    from src.sim.medieval.dated import resolve_dated
    from src.sim.medieval.force import force_options, occupy_settlement, raise_detachment, raise_options
    from src.sim.medieval.garrison_policy import garrison_adapters
    from src.sim.medieval.route_intelligence import refresh_route_reports
    from src.sim.medieval.settlement_intelligence import refresh_settlement_reports

    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == "campomanso")
    world.society.population[f"pop:campomanso:{group.people}:soldier"] = group.model_copy(
        update={"id": f"pop:campomanso:{group.people}:soldier", "occupation": "soldier", "count": 20})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    raise_option = next(item for item in raise_options(world, OWNER) if item.destination_id == "salgueiro")
    raise_detachment(world, OWNER, raise_option.id, _decision(world, raise_option).id)
    while next(iter(world.society.detachments.values())).stage == "marching":
        world.clock = world.clock.advance(1)
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))
    refresh_settlement_reports(world)
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, _decision(world, occupy).id)
    refresh_settlement_reports(world)
    option = next(item for item in force_options(world, OWNER) if item.kind == "garrison")
    garrison_adapters()[0].execute_fn(world, OWNER, option.id, _decision(world, option).id)
    garrison = world.society.garrisons[f"garrison:{option.detachment_id}"]
    assert garrison.stage == "active"
    return world, garrison


def only_option(world, kind="adopt"):
    options = [item for item in garrison_supply_options(world, OWNER) if item.kind == kind]
    assert len(options) == 1, [item.id for item in options]
    return options[0]


def adopt(world):
    option = only_option(world)
    execute_garrison_supply(world, OWNER, option.id, _decision(world, option).id)
    return option


def test_adopting_reserves_the_column_rations_without_creating_any(tmp_path):
    world, garrison = garrisoned_world()
    stock_id = world.economy.needs[garrison.settlement_id].stock_id
    detachment = world.society.detachments[garrison.detachment_id]
    before = reserve_quantity(world, stock_id, "food")
    goods_before = sum(item.goods.get("food", 0) for item in world.economy.stocks.values())
    assert garrison_demand(world, stock_id, "food") == 0

    option = adopt(world)
    objective = world.strategy.objectives[f"garrison-supply:{OWNER.kind}:{OWNER.id}:{garrison.id}"]
    assert objective.kind == "maintain_garrison_supply" and objective.garrison_id == garrison.id
    assert objective.stock_id == stock_id and objective.resource_id == "food"

    # Priority over food that already exists, and not one ration more.
    expected = detachment.count * 30 * objective.reserve_months
    assert garrison_demand(world, stock_id, "food") == expected
    assert reserve_quantity(world, stock_id, "food") == before + expected
    assert sum(item.goods.get("food", 0) for item in world.economy.stocks.values()) == goods_before
    assert not world.economy.freight_orders and not world.economy.parcels

    world.strategy.validate(world)
    world.economy.validate(world)
    path = tmp_path / "garrison-supply.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)
    assert resumed.strategy.objectives[objective.id].garrison_id == garrison.id
    assert garrison_demand(resumed, stock_id, "food") == expected
    assert option.settlement_id == garrison.settlement_id


def test_abandoning_returns_the_priority_and_leaves_the_duty_alone():
    world, garrison = garrisoned_world()
    stock_id = world.economy.needs[garrison.settlement_id].stock_id
    before = reserve_quantity(world, stock_id, "food")
    adopt(world)
    assert reserve_quantity(world, stock_id, "food") > before

    # Adopting twice is not offered; only the reverse act is.
    assert not [item for item in garrison_supply_options(world, OWNER) if item.kind == "adopt"]
    option = only_option(world, "abandon")
    execute_garrison_supply(world, OWNER, option.id, _decision(world, option).id)

    assert reserve_quantity(world, stock_id, "food") == before
    assert garrison_demand(world, stock_id, "food") == 0
    assert world.society.garrisons[garrison.id].stage == "active", "o dever segue por conta própria"
    world.strategy.validate(world)


@pytest.mark.parametrize("missing", ["garrison", "column", "occupation", "authority"])
def test_every_material_term_of_the_duty_is_required(missing):
    world, garrison = garrisoned_world()
    if missing == "garrison":
        world.society.garrisons[garrison.id] = garrison.model_copy(update={"stage": "lapsed"})
    elif missing == "column":
        detachment = world.society.detachments[garrison.detachment_id]
        world.society.detachments[detachment.id] = detachment.model_copy(update={"stage": "returning"})
    elif missing == "occupation":
        settlement = world.society.settlements[garrison.settlement_id]
        world.society.settlements[settlement.id] = settlement.model_copy(update={"occupier_id": None})
    else:
        world.authority.offices = {key: office for key, office in world.authority.offices.items()
                                   if office.institution_ref != OWNER}

    current = world.society.garrisons[garrison.id]
    assert garrison_supply_blocker(world, OWNER, current, kind="adopt") is not None
    assert not garrison_supply_options(world, OWNER)


def test_the_reserve_does_not_keep_an_unpaid_duty_alive():
    """Priority is not money: the existing owner still ends the duty."""
    from src.sim.medieval.force import _maintain_garrison

    world, garrison = garrisoned_world()
    adopt(world)
    account = world.economy.accounts[garrison.account_id]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})

    detachment = world.society.detachments[garrison.detachment_id]
    _maintain_garrison(world, detachment)

    assert world.society.garrisons[garrison.id].stage == "lapsed"
    assert any(event.event_type == "garrison_lapsed" for event in world.events)


@pytest.mark.parametrize("broken", ["occupation", "column_left", "column_returning",
                                    "duty_lapsed", "foreign_column"])
def test_a_persisted_objective_never_asserts_more_than_the_owner_would(broken):
    """Validation must refuse exactly what the owner would refuse to create."""
    world, garrison = garrisoned_world()
    adopt(world)
    world.strategy.validate(world)

    detachment = world.society.detachments[garrison.detachment_id]
    settlement = world.society.settlements[garrison.settlement_id]
    if broken == "occupation":
        world.society.settlements[settlement.id] = settlement.model_copy(update={"occupier_id": None})
    elif broken == "column_left":
        world.society.detachments[detachment.id] = detachment.model_copy(
            update={"location_id": "campomanso"})
    elif broken == "column_returning":
        world.society.detachments[detachment.id] = detachment.model_copy(update={"stage": "returning"})
    elif broken == "duty_lapsed":
        world.society.garrisons[garrison.id] = garrison.model_copy(update={"stage": "lapsed"})
    else:
        world.society.detachments[detachment.id] = detachment.model_copy(
            update={"owner_ref": EntityRef("polity", "escarlia")})

    with pytest.raises(ValueError, match="garrison objective requires"):
        world.strategy.validate(world)

    # The same broken state is exactly what the owner refuses to adopt.
    current = world.society.garrisons[garrison.id]
    assert garrison_supply_blocker(world, OWNER, current, kind="adopt") is not None


def test_civil_objectives_keep_their_own_weight():
    """Regression: the new kind must not change existing reserves."""
    world, garrison = garrisoned_world()
    stock_id = world.economy.needs[garrison.settlement_id].stock_id
    others = {item.id: reserve_quantity(world, item.stock_id, item.resource_id)
              for item in world.strategy.objectives.values()
              if item.kind != "maintain_garrison_supply"}
    adopt(world)
    for objective_id, value in others.items():
        objective = world.strategy.objectives[objective_id]
        if objective.stock_id == stock_id and objective.resource_id == "food":
            continue  # same stock: the garrison term is additive by design
        assert reserve_quantity(world, objective.stock_id, objective.resource_id) == value


async def test_the_objective_reaches_the_composed_menu_and_stale_fails_closed(monkeypatch):
    from src.sim.medieval.institutional_agenda import monthly_actors, monthly_adapters

    world, garrison = garrisoned_world()
    adapters = monthly_adapters()
    assert [adapter.name for adapter in adapters].count("garrison_supply") == 1
    assert OWNER in monthly_actors(world)

    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 1000})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    chosen = []

    async def answer(prompt, *_args, **_kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        picked = next((item for item in payload["choices"]
                       if item["label"].startswith("Sustentar as rações")), None)
        if picked is None:
            return {"selected_id": ai_decider.NO_ACTION}
        chosen.append(picked["id"])
        # The duty lapses while the actor answers.
        world.society.garrisons[garrison.id] = world.society.garrisons[garrison.id].model_copy(
            update={"stage": "lapsed"})
        return {"selected_id": picked["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", answer)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, OWNER, garrison_supply_adapters())
    assert len(chosen) == 1
    assert not [item for item in world.strategy.objectives.values()
                if item.kind == "maintain_garrison_supply"]

"""Compare one explicit workshop response with no action from the same save.

This is a controlled diagnostic, not an autonomous actor or a new economic
policy. Decisions use current owner terms and are injected only in the
intervention branch; both branches then advance through MedievalSimulator.
"""

import argparse
import asyncio
import json
from pathlib import Path

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.expansion import (
    _construction_terms,
    site_construction_options,
    start_site_construction,
)
from src.sim.medieval.market_purchase_policy import (
    market_purchase_acceptance_options,
    market_purchase_adapters,
)
from src.sim.medieval.persistence import load_world
from src.sim.medieval.procurement import market_purchase_options


def _decision(world, terms, content, *, event_type="economic_probe_decided"):
    return record_event(
        world, event_type, content,
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=terms,
        causal_payload={"decision_source": {"kind": "api"}},
    )


def _intervene(world, actor, settlement_id):
    options = [
        item for item in site_construction_options(world, actor)
        if item.settlement_id == settlement_id
        and item.blueprint_id == "craft-workshop-construction"
    ]
    if len(options) != 1:
        raise ValueError("exactly one current craft-workshop option is required")
    option = options[0]
    decision = _decision(world, _construction_terms(option), "Obra escolhida pelo cenário controlado.")
    project = start_site_construction(world, option, decision_event_id=decision.id)
    wood = world.economy.stocks[option.stock_id].goods.get("wood", 0)
    blueprint = world.economy.expansion_blueprints[option.blueprint_id]
    required = blueprint.inputs["wood"] * blueprint.required_units
    if wood >= required:
        return project.id, None

    purchases = [
        item for item in market_purchase_options(world, actor)
        if item.destination_id == option.stock_id and item.resource_id == "wood"
        and item.quantity >= required - wood
    ]
    if not purchases:
        raise ValueError("project has no current bilateral wood purchase covering its need")
    purchase = min(purchases, key=lambda item: (len(item.route_ids), item.total_price, item.id))
    request = _decision(
        world, purchase.decision(), "Compra de madeira escolhida pelo cenário controlado.",
        event_type="institutional_decision_turn_decided",
    )
    seller = world.economy.accounts[purchase.seller_account_id].owner_ref
    acceptance = next(
        (item for item in market_purchase_acceptance_options(world, seller)
         if item.request_event_id == request.id), None
    )
    if acceptance is None:
        raise ValueError("seller has no current acceptance option for the selected request")
    response = _decision(
        world, acceptance.decision(), "Vendedor aceitou no cenário controlado.",
        event_type="institutional_decision_turn_decided",
    )
    adapter = next(item for item in market_purchase_adapters()
                   if item.name == "market_purchase_acceptance")
    adapter.execute_fn(world, seller, acceptance.id, response.id)
    return project.id, {"seller": seller.to_dict(), "quantity": purchase.quantity,
                        "total_price": purchase.total_price, "route_ids": purchase.route_ids}


async def _branch(save_path, actor, settlement_id, days, *, intervention):
    world = load_world(save_path)
    if world.config.ai_enabled:
        raise ValueError("the source save must use an offline decision policy")
    start_day = world.clock.absolute_day
    project_id, purchase = (_intervene(world, actor, settlement_id)
                            if intervention else (None, None))
    engine = MedievalSimulator(world)
    while world.clock.absolute_day < start_day + days:
        await engine.step()
    need = world.economy.needs[settlement_id]
    project = world.economy.expansions.get(project_id) if project_id else None
    payroll = world.economy.payrolls.get(project_id) if project_id else None
    subsistence = next(
        event for event in reversed(world.events)
        if event.event_type == "subsistence_resolved"
        and event.causal_payload.get("subsistence", {}).get("settlement_id") == settlement_id
    )
    return {
        "day": world.clock.absolute_day,
        "missing_food": need.missing_food,
        "health": need.health,
        "subsistence_event_id": subsistence.id,
        "project_id": project_id,
        "project_stage": project.stage if project else None,
        "project_completed_units": project.completed_units if project else None,
        "project_event_id": project.last_event_id if project else None,
        "project_payroll_gross": payroll.gross if payroll else None,
        "project_workers_by_group": payroll.workers_by_group if payroll else None,
        "purchase": purchase,
    }


async def compare(save_path, settlement_id, days):
    baseline = load_world(save_path)
    administrator = baseline.society.settlements[settlement_id].administrator_id
    if administrator is None:
        raise ValueError("the target settlement has no current administration")
    actor = EntityRef("polity", administrator)
    del baseline
    intervention = await _branch(save_path, actor, settlement_id, days, intervention=True)
    control = await _branch(save_path, actor, settlement_id, days, intervention=False)
    return {"save": str(save_path), "settlement_id": settlement_id,
            "actor_ref": actor.to_dict(), "days": days,
            "intervention": intervention, "control": control,
            "missing_food_difference": control["missing_food"] - intervention["missing_food"],
            "health_difference": intervention["health"] - control["health"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", required=True, type=Path)
    parser.add_argument("--settlement", required=True)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    if args.days <= 0 or args.days % 30:
        parser.error("--days must be a positive multiple of 30")
    print(json.dumps(asyncio.run(compare(args.save, args.settlement, args.days)),
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

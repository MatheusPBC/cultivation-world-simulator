"""Compare a natural food-payroll opportunity with and without voluntary credit.

The source world is generated and advanced with the offline engine. At the
first current production receipt where food output is blocked only by payroll,
the consultation is intercepted before the actor acts. One intervention branch
then receives an explicit API request and one local household's independent
loan choice; both branches continue under the same routine offline policy.
This is a controlled counterfactual, not evidence of provider behavior.
"""

import argparse
import asyncio
import copy
import json

import src.sim.medieval.engine as engine_module
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import validate_history
from src.sim.medieval.family_loans import (
    LEND_ACTION,
    REQUEST_ACTION,
    family_loan_options,
    family_loan_request_options,
    lend_to_polity,
    record_family_loan_decision,
    request_family_loan,
)


class _CaptureOpportunity(Exception):
    pass


def _weighted_health(world):
    population = sum(group.count for group in world.society.population.values())
    weighted = sum(
        need.health * sum(group.count for group in world.society.population.values()
                          if group.settlement_id == need.id)
        for need in world.economy.needs.values()
    )
    return round(weighted / max(1, population), 2)


def _food_output(events):
    return sum(
        max(0, int(delta.after) - int(delta.before))
        for event in events
        if event.event_type == "production_completed"
        and isinstance(event.causal_payload, dict)
        and isinstance(event.causal_payload.get("production"), dict)
        and event.causal_payload["production"].get("batches", 0) > 0
        for delta in event.deltas
        if delta.owner_kind == "stock" and delta.aspect == "food"
    )


def _food_batches_by_facility(events):
    totals = {}
    for event in events:
        production = (event.causal_payload.get("production")
                      if isinstance(event.causal_payload, dict) else None)
        if (event.event_type == "production_completed" and isinstance(production, dict)
                and production.get("batches", 0) > 0):
            food_delta = sum(
                max(0, int(delta.after) - int(delta.before))
                for delta in event.deltas
                if delta.owner_kind == "stock" and delta.aspect == "food"
            )
            if food_delta:
                facility_id = production["facility_id"]
                totals[facility_id] = totals.get(facility_id, 0) + production["batches"]
    return dict(sorted(totals.items()))


def _target_batches(events, facility_id):
    return sum(
        event.causal_payload["production"]["batches"]
        for event in events
        if isinstance(event.causal_payload, dict)
        and isinstance(event.causal_payload.get("production"), dict)
        and event.causal_payload["production"].get("facility_id") == facility_id
    )


async def _advance(world, start_day, days, *, facility_id, account_id, lender_id,
                   settlement_id, loan_id=None):
    simulator = MedievalSimulator(world)
    checkpoints = []
    history_start = len(world.events)
    while world.clock.absolute_day < start_day + days:
        await simulator.step()
        if world.clock.absolute_day % 30 == 0:
            target = world.economy.facilities[facility_id]
            target_event = world.event_index().get(target.last_event_id)
            production = (target_event.causal_payload.get("production")
                          if target_event is not None
                          and isinstance(target_event.causal_payload, dict) else None)
            checkpoints.append({
                "day": world.clock.absolute_day,
                "missing_food": sum(item.missing_food for item in world.economy.needs.values()),
                "unrest": sum(item.unrest for item in world.economy.needs.values()),
                "health_weighted": _weighted_health(world),
                "borrower_balance": world.economy.accounts[account_id].balance,
                "target_facility_batches": target.last_batches,
                "target_facility_limitations": list(target.last_limitations),
                "target_receipt": target_event.event_type if target_event is not None else None,
                "target_payroll_limit": (production.get("limits", {}).get("payroll_funds")
                                          if isinstance(production, dict) else None),
            })
    world.economy.validate(world)
    world.knowledge.validate(world)
    validate_history(world.events, world.clock.absolute_day)
    events = world.events[history_start:]
    lender_group = world.society.population[lender_id]
    lender_account = world.economy.accounts[f"household:{lender_id}"]
    lender_reserve = lender_group.count * world.economy.markets[settlement_id].prices["food"]
    return {
        "day": world.clock.absolute_day,
        "checkpoints": checkpoints,
        "food_produced_during_branch": _food_output(events),
        "food_production_batches_by_facility": _food_batches_by_facility(events),
        "target_batches_during_branch": _target_batches(events, facility_id),
        "final_missing_food": sum(item.missing_food for item in world.economy.needs.values()),
        "final_unrest": sum(item.unrest for item in world.economy.needs.values()),
        "lender_balance": lender_account.balance,
        "lender_one_day_food_reserve": lender_reserve,
        "lender_settlement_missing_food": world.economy.needs[settlement_id].missing_food,
        "borrower_balance": world.economy.accounts[account_id].balance,
        "loan_status": (world.economy.family_loans[loan_id].status
                        if loan_id in world.economy.family_loans else None),
        "total_money": sum(account.balance for account in world.economy.accounts.values()),
        "event_count": len(events),
    }


async def compare(seed=73, days=180, max_source_day=900):
    capture = {}
    original = engine_module.review_monthly_institutional_turn

    async def intercept(world, **kwargs):
        choices = []
        for identity in sorted(world.society.polities):
            choices.extend(family_loan_request_options(world, EntityRef("polity", identity)))
        choices = [item for item in choices if item.purpose == "food_production_payroll"]
        if choices:
            capture["world"] = copy.deepcopy(world)
            capture["choices"] = choices
            raise _CaptureOpportunity()
        return await original(world, **kwargs)

    engine_module.review_monthly_institutional_turn = intercept
    natural = create_medieval_world(seed)
    try:
        simulator = MedievalSimulator(natural)
        while natural.clock.absolute_day < max_source_day:
            try:
                await simulator.step()
            except _CaptureOpportunity:
                break
        else:
            raise ValueError(f"no natural food-payroll opportunity through day {max_source_day}")
    finally:
        engine_module.review_monthly_institutional_turn = original

    base = capture["world"]
    base.economy.validate(base)
    base.knowledge.validate(base)
    choice = min(capture["choices"], key=lambda item: (item.principal, item.id))
    control = copy.deepcopy(base)
    intervention = copy.deepcopy(base)
    source = intervention.event_index()[choice.source_event_id]

    request_decision = record_family_loan_decision(
        intervention, choice.actor_ref, choice.id, action=REQUEST_ACTION,
        decision_source={"kind": "api"},
    )
    request = request_family_loan(
        intervention, choice.actor_ref, choice.id, request_decision.id
    )
    lenders = []
    for group in intervention.society.population.values():
        if group.settlement_id != choice.settlement_id:
            continue
        lender = EntityRef("population_group", group.id)
        offers = [item for item in family_loan_options(intervention, lender)
                  if item.request_id == request.id]
        if offers:
            lenders.append((max(item.principal for item in offers), group.id, lender, offers))
    if not lenders:
        raise ValueError("natural food-payroll opportunity has no local lendable household")
    _, lender_id, lender_ref, offers = max(lenders, key=lambda item: (item[0], item[1]))
    offer = max(offers, key=lambda item: item.principal)
    lender_decision = record_family_loan_decision(
        intervention, lender_ref, offer.id, action=LEND_ACTION,
        decision_source={"kind": "api"},
    )
    money_before = sum(account.balance for account in intervention.economy.accounts.values())
    loan = lend_to_polity(intervention, lender_ref, offer.id, lender_decision.id)
    if intervention.economy.facilities[choice.production_facility_id].last_batches != 0:
        raise ValueError("loan request unexpectedly executed production")

    start_day = base.clock.absolute_day
    common = {
        "facility_id": choice.production_facility_id,
        "account_id": choice.account_id,
        "lender_id": lender_id,
        "settlement_id": choice.settlement_id,
    }
    control_result = await _advance(control, start_day, days, **common)
    intervention_result = await _advance(intervention, start_day, days,
                                         loan_id=loan.id, **common)
    return {
        "seed": seed,
        "source_day": start_day,
        "end_day": start_day + days,
        "provider": "none; routine offline policy after controlled API choices",
        "source_event_id": source.id,
        "source_event_type": source.event_type,
        "borrower": choice.actor_ref.to_dict(),
        "purpose": choice.purpose,
        "facility_id": choice.production_facility_id,
        "one_batch_principal": choice.principal,
        "request_id": request.id,
        "lender": lender_ref.to_dict(),
        "loan_principal": loan.principal,
        "money_before_loan": money_before,
        "control": control_result,
        "intervention": intervention_result,
        "shortage_reduction_control_minus_intervention": (
            control_result["final_missing_food"] - intervention_result["final_missing_food"]
        ),
        "production_gain_intervention_minus_control": (
            intervention_result["food_produced_during_branch"]
            - control_result["food_produced_during_branch"]
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--max-source-day", type=int, default=900)
    args = parser.parse_args()
    if args.days <= 0 or args.days % 30:
        parser.error("--days must be a positive multiple of 30")
    print(json.dumps(asyncio.run(compare(args.seed, args.days, args.max_source_day)),
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

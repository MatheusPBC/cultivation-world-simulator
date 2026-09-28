"""Trace a natural food-payroll opportunity and controlled causal interventions.

The source world is generated and advanced with the offline engine. At the
first current production receipt where food output is blocked only by payroll,
the consultation is intercepted before the actor acts. Optional API-controlled
branches exercise a household loan, a production priority, or relief while the
controls continue under the same routine offline policy. This is a controlled
counterfactual, not evidence of provider behavior.
"""

import argparse
import asyncio
import copy
import json
import sys

import src.sim.medieval.engine as engine_module
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import validate_history
from src.sim.medieval.events import record_event
from src.sim.medieval import ai_decider
from src.sim.medieval.institutional_decision_turn import (
    NO_AFFORDANCE_EVENT_TYPE,
)
from src.sim.medieval.institutional_agenda import monthly_adapters, monthly_actors
from src.sim.medieval.family_loans import (
    LEND_ACTION,
    REQUEST_ACTION,
    family_loan_options,
    family_loan_request_options,
    lend_to_polity,
    record_family_loan_decision,
    request_family_loan,
)
from src.sim.medieval.relief import relief_settlement_options
from src.sim.medieval.relief_policy import FALLBACK_MIN_SHORTFALL
from src.sim.medieval.production_priority import production_priority_options
from src.sim.medieval.production_priority import set_production_priority


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


def _settlement_outcomes(world):
    return {
        need_id: {
            "missing_food": need.missing_food,
            "health": need.health,
            "unrest": need.unrest,
            "public_food": world.economy.stocks[need.stock_id].goods.get("food", 0),
        }
        for need_id, need in sorted(world.economy.needs.items())
    }


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
                   settlement_id, loan_id=None, trace_payroll_pool=False):
    simulator = MedievalSimulator(world)
    checkpoints = []
    history_start = len(world.events)
    shared_facilities = {
        item.id
        for item in world.economy.facilities.values()
        if item.payroll_account_id == account_id
    }
    pool_balance = world.economy.accounts[account_id].balance
    traced_account_events = []
    traced_production_events = []
    first_boundary_trace = None
    while world.clock.absolute_day < start_day + days:
        event_start = len(world.events)
        await simulator.step()
        if trace_payroll_pool and first_boundary_trace is None:
            boundary_events = world.events[event_start:]
            for event in boundary_events:
                production = (
                    event.causal_payload.get("production")
                    if isinstance(event.causal_payload, dict) else None
                )
                if (isinstance(production, dict)
                        and production.get("facility_id") in shared_facilities
                        and event.event_type in {"production_completed", "production_limited"}):
                    traced_production_events.append({
                        "event_id": event.id,
                        "facility_id": production["facility_id"],
                        "event_type": event.event_type,
                        "batches": production.get("batches"),
                        "limitations": production.get("limitations", []),
                        "payroll_funds": production.get("limits", {}).get("payroll_funds"),
                        "account_balance_at_evaluation": pool_balance,
                    })
                for delta in event.deltas:
                    if (delta.owner_kind == "account" and delta.owner_id == account_id
                            and delta.aspect == "balance"):
                        before = int(delta.before)
                        after = int(delta.after)
                        traced_account_events.append({
                            "event_id": event.id,
                            "event_type": event.event_type,
                            "before": before,
                            "after": after,
                            "delta": after - before,
                        })
                        pool_balance = after
            if (world.clock.absolute_day > start_day
                    and world.clock.absolute_day % 30 == 0):
                need = world.economy.needs[settlement_id]
                local_stock = world.economy.stocks[need.stock_id]
                local_groups = [group for group in world.society.population.values()
                                if group.settlement_id == settlement_id]
                local_household_accounts = {f"household:{group.id}" for group in local_groups}
                food_receipts = []
                subsistence_receipts = []
                household_balances = []
                for event in boundary_events:
                    food_deltas = [
                        {"owner_kind": delta.owner_kind, "owner_id": delta.owner_id,
                         "aspect": delta.aspect, "before": delta.before, "after": delta.after}
                        for delta in event.deltas
                        if ((delta.owner_kind == "stock" and delta.owner_id == need.stock_id
                             and delta.aspect == "food")
                            or (delta.owner_kind == "account"
                                and delta.owner_id in local_household_accounts))
                    ]
                    if event.event_type == "household_purchase_completed" and food_deltas:
                        food_receipts.append({"event_id": event.id, "deltas": food_deltas,
                                              "cause_event_ids": sorted(
                                                  link.cause_event_id for link in event.causal_links)})
                    if (event.event_type == "subsistence_resolved"
                            and isinstance(event.causal_payload, dict)
                            and isinstance(event.causal_payload.get("subsistence"), dict)
                            and event.causal_payload.get("subsistence", {}).get("settlement_id") == settlement_id):
                        subsistence_receipts.append({
                            "event_id": event.id,
                            **event.causal_payload["subsistence"],
                            "cause_event_ids": sorted(link.cause_event_id for link in event.causal_links),
                        })
                for group in sorted(local_groups, key=lambda item: item.id):
                    household_id = f"household:{group.id}"
                    account = world.economy.accounts.get(household_id)
                    household_balances.append({
                        "group_id": group.id,
                        "present_count": group.count,
                        "available_count": world.society.available_count(group.id),
                        "account_id": household_id if account else None,
                        "balance": account.balance if account else None,
                        "account_event_id": account.last_event_id if account else None,
                    })
                settlement_food_trace = {
                    "settlement_id": settlement_id,
                    "missing_food": need.missing_food,
                    "health": need.health,
                    "unrest": need.unrest,
                    "subsistence_event_id": need.last_event_id,
                    "stock_id": local_stock.id,
                    "food_stock": local_stock.goods.get("food", 0),
                    "food_stock_capacity": local_stock.capacity,
                    "market_food_price": world.economy.markets[settlement_id].prices["food"],
                    "households": household_balances,
                    "household_purchases": food_receipts,
                    "subsistence_receipts": subsistence_receipts,
                }
                from src.sim.medieval.relief import relief_settlement_options
                settlement_food_trace["current_relief_affordances"] = [
                    {"id": item.id, "quantity": item.quantity, "report_id": item.report_id}
                    for item in relief_settlement_options(
                        world, local_stock.owner_ref.id, settlement_id=settlement_id
                    )
                ]
                first_boundary_trace = {
                    "day": world.clock.absolute_day,
                    "payroll_account_id": account_id,
                    "shared_facility_ids": sorted(shared_facilities),
                    "account_events": traced_account_events,
                    "production_events": traced_production_events,
                    "balance_after_boundary": pool_balance,
                    "target_settlement_food_trace": settlement_food_trace,
                }
        if world.clock.absolute_day % 30 == 0:
            target = world.economy.facilities[facility_id]
            target_event = world.event_index().get(target.last_event_id)
            production = (target_event.causal_payload.get("production")
                          if target_event is not None
                          and isinstance(target_event.causal_payload, dict) else None)
            checkpoints.append({
                "day": world.clock.absolute_day,
                "missing_food": sum(item.missing_food for item in world.economy.needs.values()),
                "target_settlement_missing_food": world.economy.needs[settlement_id].missing_food,
                "target_settlement_pantry_food": sum(
                    world.economy.stocks.get(f"household-stock:{group.id}").goods.get("food", 0)
                    for group in world.society.population.values()
                    if group.settlement_id == settlement_id
                    and world.economy.stocks.get(f"household-stock:{group.id}") is not None
                ),
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
    result = {
        "day": world.clock.absolute_day,
        "checkpoints": checkpoints,
        "food_produced_during_branch": _food_output(events),
        "food_production_batches_by_facility": _food_batches_by_facility(events),
        "target_batches_during_branch": _target_batches(events, facility_id),
        "final_missing_food": sum(item.missing_food for item in world.economy.needs.values()),
        "final_target_settlement_missing_food": world.economy.needs[settlement_id].missing_food,
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
    if trace_payroll_pool:
        result["first_boundary_payroll_pool_trace"] = first_boundary_trace
    return result


async def _six_cycle_relief_branch(world, *, settlement_id, loan_id, common,
                                   choose_relief):
    """Run one API-selected option from each actor's complete monthly menu.

    All other actors explicitly choose NO_ACTION. This keeps the treatment and
    control on the same provider-enabled engine path without allowing network
    calls, offline fallbacks, or post-turn material actions.
    """
    decisions = []
    target_menus = []
    original_turn = engine_module.review_monthly_institutional_turn
    original_consultable = ai_decider.consultable
    original_select_option = ai_decider.select_option
    imported_selectors = {}
    world.config = world.config.model_copy(update={"ai_enabled": True})

    def claim_for(adapter, option, claims):
        claim = adapter.claim_fn(option)
        if claim is not None:
            kind, target_id = claim
            claims.setdefault(kind, set()).add(target_id)

    async def controlled_monthly_turn(current, *, allow_offers=True):
        claims, covered = {}, set()
        adapters = monthly_adapters(allow_offers=allow_offers)
        for actor in monthly_actors(current):
            by_id = {}
            for adapter in adapters:
                for option in adapter.options_fn(current, actor):
                    by_id[option.id] = (adapter, option)
            if not by_id:
                record_event(
                    current, NO_AFFORDANCE_EVENT_TYPE,
                    f"Nenhuma affordance material estava disponível para {actor.kind}:{actor.id}.",
                    fact_kind=FactKind.OCCURRENCE,
                )
                continue
            for adapter, option in by_id.values():
                claim_for(adapter, option, claims)
            available = sorted(by_id)
            selected_id = None
            target_relief = [(adapter, option) for adapter, option in by_id.values()
                             if adapter.name == "relief" and option.settlement_id == settlement_id]
            if actor == target_actor:
                target_menus.append({
                    "day": current.clock.absolute_day,
                    "affordance_count": len(target_relief),
                    "offered_quantities": sorted(option.quantity for _, option in target_relief),
                })
            if choose_relief and actor == target_actor:
                if target_relief:
                    selected_id = max(target_relief,
                                      key=lambda pair: (pair[1].quantity, pair[1].id))[1].id
            causes = tuple(sorted({
                cause for adapter, option in by_id.values()
                for cause in adapter.causes_fn(current, option) if cause
            }))
            if selected_id is None:
                decision = {
                    "action": "no_action", "actor_ref": actor.to_dict(),
                    "selected_affordance_id": "NO_ACTION",
                    "declined_option_ids": tuple(available),
                }
                record_event(
                    current, "institutional_decision_turn_declined",
                    "No contrafactual controlado, o ator escolheu NO_ACTION no menu institucional composto.",
                    fact_kind=FactKind.DECISION,
                    causal_origin=CausalOrigin.ACTOR_DECISION,
                    causal_payload={"decision_source": {"kind": "api"}},
                    decision=decision, cause_ids=causes,
                )
            else:
                adapter, _ = by_id[selected_id]
                option = next((item for item in adapter.options_fn(current, actor)
                               if item.id == selected_id), None)
                if option is None:
                    raise ValueError("selected relief affordance went stale before owner execution")
                decision_event = record_event(
                    current, "institutional_decision_turn_decided",
                    "No contrafactual controlado, o ator escolheu alívio entre opções do menu composto atual.",
                    fact_kind=FactKind.DECISION,
                    causal_origin=CausalOrigin.ACTOR_DECISION,
                    causal_payload={"decision_source": {"kind": "api"}},
                    decision=option.decision(),
                    cause_ids=adapter.causes_fn(current, option),
                )
                before_food = sum(stock.goods.get("food", 0)
                                  for stock in current.economy.stocks.values())
                before_money = sum(account.balance for account in current.economy.accounts.values())
                prior_event_count = len(current.events)
                adapter.execute_fn(current, actor, selected_id, decision_event.id)
                after_food = sum(stock.goods.get("food", 0)
                                 for stock in current.economy.stocks.values())
                after_money = sum(account.balance for account in current.economy.accounts.values())
                if before_food != after_food or before_money != after_money:
                    raise ValueError("relief must conserve food and money in the controlled choice")
                receipt = next((event for event in current.events[prior_event_count:]
                                if event.event_type == "relief_distributed"
                                and any(link.cause_event_id == decision_event.id
                                        for link in event.causal_links)), None)
                if receipt is None:
                    raise ValueError("relief owner did not emit a receipt for its decision")
                distribution = receipt.causal_payload["relief_distribution"]
                decisions.append({
                    "day": current.clock.absolute_day,
                    "actor": actor.to_dict(),
                    "affordance_id": selected_id,
                    "decision_event_id": decision_event.id,
                    "receipt_event_id": receipt.id,
                    "quantity": option.quantity,
                    "report_id": option.report_id,
                    "household_allocations": distribution["household_allocations"],
                    "full_menu_option_count": len(by_id),
                    "food_conserved": True,
                    "money_conserved": True,
                })
            covered.add(actor)
        return claims, covered

    async def no_provider_selection(*_args, **_kwargs):
        return None

    ai_decider.consultable = lambda *_args, **_kwargs: False
    ai_decider.select_option = no_provider_selection
    for module_name, module in tuple(sys.modules.items()):
        if (module_name.startswith("src.sim.medieval")
                and getattr(module, "select_option", None) is original_select_option):
            imported_selectors[module] = original_select_option
            module.select_option = no_provider_selection
    engine_module.review_monthly_institutional_turn = controlled_monthly_turn
    need = world.economy.needs[settlement_id]
    target_actor = world.economy.stocks[need.stock_id].owner_ref
    start_day = world.clock.absolute_day
    try:
        end = await _advance(
            world, start_day, 180, loan_id=loan_id,
            **{**common, "trace_payroll_pool": False},
        )
    finally:
        engine_module.review_monthly_institutional_turn = original_turn
        ai_decider.consultable = original_consultable
        ai_decider.select_option = original_select_option
        for module, selector in imported_selectors.items():
            module.select_option = selector
    world.economy.validate(world)
    world.knowledge.validate(world)
    validate_history(world.events, world.clock.absolute_day)
    final_need = world.economy.needs[settlement_id]
    final_stock = world.economy.stocks[final_need.stock_id]
    settlement_outcomes = _settlement_outcomes(world)
    boundary_days = list(range(((start_day // 30) + 1) * 30,
                               world.clock.absolute_day + 1, 30))
    return {
        "start_day": start_day,
        "end_day": world.clock.absolute_day,
        "requested_relief_opportunities": 6,
        "monthly_turn_days": boundary_days,
        "target_relief_menus": target_menus,
        "world_ai_enabled_during_controlled_window": True,
        "provider_egress_calls": 0,
        "provider_selection_patched": True,
        "api_decisions": decisions,
        "final_missing_food": final_need.missing_food,
        "final_target_settlement_missing_food": final_need.missing_food,
        "aggregate_missing_food": sum(need.missing_food for need in world.economy.needs.values()),
        "final_health": final_need.health,
        "final_unrest": final_need.unrest,
        "final_public_food": final_stock.goods.get("food", 0),
        "missing_food_by_settlement": settlement_outcomes,
        "total_money": sum(account.balance for account in world.economy.accounts.values()),
        "event_count_during_branch": end["event_count"],
    }


async def compare(seed=73, days=180, max_source_day=900, *, trace_next_boundary=False,
                  priority_facility_id=None, relief_settlement_id=None,
                  six_cycle_relief=False):
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
    priority_options = production_priority_options(base, choice.actor_ref)
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

    priority_intervention = None
    selected_priority = None
    if priority_facility_id is not None:
        selected_priority = next(
            (item for item in production_priority_options(intervention, choice.actor_ref)
             if item.facility_id == priority_facility_id),
            None,
        )
        if selected_priority is None:
            raise ValueError(f"facility has no current production-priority affordance: {priority_facility_id}")
        priority_intervention = copy.deepcopy(intervention)
        priority_decision = record_event(
            priority_intervention, "institutional_decision_turn_decided",
            "A instituição escolheu uma prioridade de produção para o próximo ciclo.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload={"decision_source": {"kind": "api"}},
            decision=selected_priority.decision(),
        )
        priority_record = set_production_priority(
            priority_intervention, choice.actor_ref, selected_priority.id,
            decision_event_id=priority_decision.id,
        )

    start_day = base.clock.absolute_day
    common = {
        "facility_id": choice.production_facility_id,
        "account_id": choice.account_id,
        "lender_id": lender_id,
        "settlement_id": choice.settlement_id,
        "trace_payroll_pool": trace_next_boundary,
    }
    control_result = await _advance(control, start_day, days, **common)
    followup_day = start_day + days
    offline_followup = copy.deepcopy(control)
    offline_event_start = len(offline_followup.events)
    offline_followup_result = await _advance(
        offline_followup, followup_day, 30, loan_id=None,
        **{**common, "trace_payroll_pool": False},
    )
    offline_relief_receipts = [
        event.id for event in offline_followup.events[offline_event_start:]
        if event.event_type == "relief_distributed"
        and event.causal_payload.get("relief_distribution", {}).get("settlement_id") == choice.settlement_id
    ]
    offline_relief_options = relief_settlement_options(
        offline_followup, choice.actor_ref.id, settlement_id=choice.settlement_id
    )
    intervention_result = await _advance(intervention, start_day, days,
                                         loan_id=loan.id, **common)
    result = {
        "seed": seed,
        "source_day": start_day,
        "end_day": start_day + days,
        "provider": "none; routine offline policy after controlled API choices",
        "world_ai_enabled": bool(base.config.ai_enabled),
        "source_event_id": source.id,
        "source_event_type": source.event_type,
        "borrower": choice.actor_ref.to_dict(),
        "purpose": choice.purpose,
        "facility_id": choice.production_facility_id,
        "production_priority_options_at_source": [
            {
                "id": item.id,
                "facility_id": item.facility_id,
                "settlement_id": item.settlement_id,
                "payroll_account_id": item.payroll_account_id,
                "occupation": item.occupation,
                "output_names": list(item.output_names),
            }
            for item in priority_options
        ],
        "one_batch_principal": choice.principal,
        "request_id": request.id,
        "lender": lender_ref.to_dict(),
        "loan_principal": loan.principal,
        "money_before_loan": money_before,
        "control": control_result,
        "offline_followup": offline_followup_result,
        "offline_followup_relief": {
            "policy": "routine-rules",
            "fallback_min_shortfall": FALLBACK_MIN_SHORTFALL,
            "relief_receipt_ids": offline_relief_receipts,
            "current_affordance_ids_after_followup": [item.id for item in offline_relief_options],
            "target_settlement_missing_food": offline_followup.economy.needs[
                choice.settlement_id
            ].missing_food,
        },
        "intervention": intervention_result,
        "shortage_reduction_control_minus_intervention": (
            control_result["final_missing_food"] - intervention_result["final_missing_food"]
        ),
        "production_gain_intervention_minus_control": (
            intervention_result["food_produced_during_branch"]
            - control_result["food_produced_during_branch"]
        ),
    }
    if priority_intervention is not None:
        priority_result = await _advance(priority_intervention, start_day, days,
                                         loan_id=loan.id, **common)
        result["selected_production_priority"] = {
            "affordance_id": selected_priority.id,
            "facility_id": selected_priority.facility_id,
            "settlement_id": selected_priority.settlement_id,
            "effective_day": priority_record.effective_day,
            "decision_event_id": priority_record.decision_event_id,
            "priority_event_id": priority_record.last_event_id,
        }
        result["priority_intervention"] = priority_result
        result["priority_vs_loan_only"] = {
            "food_production_delta": (
                priority_result["food_produced_during_branch"]
                - intervention_result["food_produced_during_branch"]
            ),
            "target_batches_delta": (
                priority_result["target_batches_during_branch"]
                - intervention_result["target_batches_during_branch"]
            ),
            "final_missing_food_delta": (
                priority_result["final_missing_food"]
                - intervention_result["final_missing_food"]
            ),
            "final_unrest_delta": (
                priority_result["final_unrest"] - intervention_result["final_unrest"]
            ),
            "target_settlement_missing_food_delta": (
                priority_result["final_target_settlement_missing_food"]
                - intervention_result["final_target_settlement_missing_food"]
            ),
        }
        if relief_settlement_id is not None and not six_cycle_relief:
            relief_base = copy.deepcopy(priority_intervention)
            relief_actor = relief_base.economy.stocks[
                relief_base.economy.needs[relief_settlement_id].stock_id
            ].owner_ref
            relief_options = relief_settlement_options(
                relief_base, relief_actor.id, settlement_id=relief_settlement_id
            )
            relief_option = next((item for item in relief_options
                                  if item.quantity == relief_base.economy.needs[
                                      relief_settlement_id
                                  ].missing_food), None)
            if relief_option is None:
                raise ValueError("no current relief affordance is available for the one-cycle probe")
            relief_decision = record_event(
                relief_base, "institutional_decision_turn_decided",
                "A instituição escolheu distribuir o alimento observado como necessário.",
                fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                causal_payload={"decision_source": {"kind": "api"}},
                decision=relief_option.decision(),
            )
            relief_receipt = distribute_relief(
                relief_base, relief_option.id, decision_event_id=relief_decision.id
            )
            followup_day = start_day + days
            priority_followup = copy.deepcopy(priority_intervention)
            next_common = {**common, "trace_payroll_pool": False}
            priority_followup_result = await _advance(
                priority_followup, followup_day, 30, loan_id=loan.id, **next_common
            )
            relief_result = await _advance(
                relief_base, followup_day, 30, loan_id=loan.id, **next_common
            )
            result["relief_api_decision"] = {
                "selected_affordance_id": relief_option.id,
                "decision_event_id": relief_decision.id,
                "relief_event_id": relief_receipt.id,
                "quantity": relief_option.quantity,
                "followup_end_day": followup_day + 30,
                "cause_event_ids": sorted(link.cause_event_id for link in relief_receipt.causal_links),
                "food_deltas": [
                    {"owner_id": delta.owner_id, "before": delta.before, "after": delta.after}
                    for delta in relief_receipt.deltas
                    if delta.aspect == "food"
                ],
            }
            result["priority_no_relief_followup"] = priority_followup_result
            result["relief_intervention_followup"] = relief_result
            result["relief_vs_no_relief_followup"] = {
                "target_settlement_missing_food_delta": (
                    relief_result["final_target_settlement_missing_food"]
                    - priority_followup_result["final_target_settlement_missing_food"]
                ),
                "target_settlement_health_delta": (
                    relief_base.economy.needs[relief_settlement_id].health
                    - priority_followup.economy.needs[relief_settlement_id].health
                ),
                "target_settlement_unrest_delta": (
                    relief_base.economy.needs[relief_settlement_id].unrest
                    - priority_followup.economy.needs[relief_settlement_id].unrest
                ),
                "total_money_delta": (
                    relief_result["total_money"] - priority_followup_result["total_money"]
                ),
            }
    if six_cycle_relief and relief_settlement_id is not None and priority_intervention is not None:
        six_control = copy.deepcopy(priority_intervention)
        six_treatment = copy.deepcopy(priority_intervention)
        if six_control.clock.absolute_day != six_treatment.clock.absolute_day:
            raise ValueError("six-cycle relief branches did not start at the same day")
        control_need = six_control.economy.needs[relief_settlement_id]
        treatment_need = six_treatment.economy.needs[relief_settlement_id]
        control_stock = six_control.economy.stocks[control_need.stock_id]
        treatment_stock = six_treatment.economy.stocks[treatment_need.stock_id]
        if (six_control.clock.absolute_day != six_treatment.clock.absolute_day
                or control_need.missing_food != treatment_need.missing_food
                or control_need.health != treatment_need.health
                or control_need.unrest != treatment_need.unrest
                or control_stock.goods != treatment_stock.goods
                or sum(item.balance for item in six_control.economy.accounts.values())
                != sum(item.balance for item in six_treatment.economy.accounts.values())):
            raise ValueError("six-cycle relief branches did not start from an equivalent boundary")
        control_rest = await _six_cycle_relief_branch(
            six_control, settlement_id=relief_settlement_id,
            loan_id=loan.id, common=common, choose_relief=False,
        )
        treatment_result = await _six_cycle_relief_branch(
            six_treatment, settlement_id=relief_settlement_id,
            loan_id=loan.id, common=common, choose_relief=True,
        )
        offline_control = copy.deepcopy(priority_intervention)
        offline_initial_day = offline_control.clock.absolute_day
        offline_receipt_start = len(offline_control.events)
        offline_followup = await _advance(
            offline_control, offline_control.clock.absolute_day, 180,
            loan_id=loan.id, **{**common, "trace_payroll_pool": False},
        )
        offline_relief_receipts = [
            event for event in offline_control.events[offline_receipt_start:]
            if event.event_type == "relief_distributed"
        ]
        offline_need = offline_control.economy.needs[relief_settlement_id]
        offline_public_food = offline_control.economy.stocks[
            offline_need.stock_id
        ].goods.get("food", 0)
        offline_relief_quantity = sum(
            int(event.causal_payload["relief_distribution"]["quantity"])
            for event in offline_relief_receipts
        )
        offline_settlement_outcomes = _settlement_outcomes(offline_control)
        result["six_cycle_relief"] = {
            "selection_source": "API policy in the composed monthly menu; current affordance only",
            "control_policy": "API NO_ACTION on every available composed menu",
            "provider_egress": "disabled by intercepting all loaded selectors",
            "control": {
                "day": control_rest["end_day"],
                "target_settlement_missing_food": control_rest["final_target_settlement_missing_food"],
                "aggregate_missing_food": control_rest["aggregate_missing_food"],
                "health": six_control.economy.needs[relief_settlement_id].health,
                "unrest": six_control.economy.needs[relief_settlement_id].unrest,
                "public_food": six_control.economy.stocks[
                    six_control.economy.needs[relief_settlement_id].stock_id
                ].goods.get("food", 0),
                "total_money": sum(account.balance for account in six_control.economy.accounts.values()),
                "event_count": control_rest["event_count_during_branch"],
                "provider_egress_calls": control_rest["provider_egress_calls"],
                "missing_food_by_settlement": control_rest["missing_food_by_settlement"],
            },
            "treatment": treatment_result,
            "offline_control": {
                "day": offline_followup["day"],
                "initial_boundary_day": offline_initial_day,
                "aggregate_missing_food": offline_followup["final_missing_food"],
                "target_settlement_missing_food": offline_followup[
                    "final_target_settlement_missing_food"],
                "health": offline_need.health,
                "unrest": offline_need.unrest,
                "public_food": offline_public_food,
                "total_money": offline_followup["total_money"],
                "relief_receipt_count": len(offline_relief_receipts),
                "relief_quantity": offline_relief_quantity,
                "event_count": offline_followup["event_count"],
                "missing_food_by_settlement": offline_settlement_outcomes,
            },
            "difference_treatment_minus_control": {
                "target_settlement_missing_food": (
                    treatment_result["final_target_settlement_missing_food"]
                    - control_rest["final_target_settlement_missing_food"]),
                "aggregate_missing_food": (treatment_result["aggregate_missing_food"]
                                           - control_rest["aggregate_missing_food"]),
                "health": (treatment_result["final_health"]
                           - six_control.economy.needs[relief_settlement_id].health),
                "unrest": (treatment_result["final_unrest"]
                           - six_control.economy.needs[relief_settlement_id].unrest),
                "public_food": (treatment_result["final_public_food"]
                                - six_control.economy.stocks[
                                    six_control.economy.needs[relief_settlement_id].stock_id
                                ].goods.get("food", 0)),
                "total_money": (treatment_result["total_money"]
                                - sum(account.balance for account in six_control.economy.accounts.values())),
                "missing_food_by_settlement": {
                    settlement_id: treatment_result["missing_food_by_settlement"][
                        settlement_id]["missing_food"]
                        - control_rest["missing_food_by_settlement"][settlement_id]["missing_food"]
                    for settlement_id in treatment_result["missing_food_by_settlement"]
                },
            },
            "difference_treatment_minus_offline": {
                "aggregate_missing_food": treatment_result["aggregate_missing_food"]
                                          - offline_followup["final_missing_food"],
                "target_settlement_missing_food": treatment_result[
                    "final_target_settlement_missing_food"]
                                - offline_followup["final_target_settlement_missing_food"],
                "health": treatment_result["final_health"] - offline_need.health,
                "unrest": treatment_result["final_unrest"] - offline_need.unrest,
                "public_food": treatment_result["final_public_food"] - offline_public_food,
                "total_money": treatment_result["total_money"] - offline_followup["total_money"],
                "missing_food_by_settlement": {
                    settlement_id: treatment_result["missing_food_by_settlement"][
                        settlement_id]["missing_food"]
                        - offline_settlement_outcomes[settlement_id]["missing_food"]
                    for settlement_id in treatment_result["missing_food_by_settlement"]
                },
            },
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--max-source-day", type=int, default=900)
    parser.add_argument(
        "--trace-next-boundary",
        action="store_true",
        help="include account movements and shared-facility production at the first later monthly boundary",
    )
    parser.add_argument(
        "--priority-facility-id",
        help="select this currently offered facility through an explicit API decision and compare against loan-only",
    )
    parser.add_argument(
        "--relief-settlement-id",
        help="after the priority boundary, select the exact current full-shortfall relief option and compare one more cycle",
    )
    parser.add_argument(
        "--six-cycle-relief", action="store_true",
        help="after the first priority boundary, compare six monthly current relief choices with an offline control",
    )
    args = parser.parse_args()
    if args.days <= 0 or args.days % 30:
        parser.error("--days must be a positive multiple of 30")
    print(json.dumps(asyncio.run(compare(
        args.seed, args.days, args.max_source_day,
        trace_next_boundary=args.trace_next_boundary,
        priority_facility_id=args.priority_facility_id,
        relief_settlement_id=args.relief_settlement_id,
        six_cycle_relief=args.six_cycle_relief,
    )),
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

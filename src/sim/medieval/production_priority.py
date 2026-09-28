"""Actor-selected ordering for facilities sharing production constraints.

This module only enumerates and revalidates a production-priority decision.  It
does not change production, stock, or payroll. The root
integration is expected to persist the returned :class:`ProductionPriorityDraft`
and let ``produce_monthly`` consume that record at the next boundary.

The important boundary is deliberate: a priority is offered only for a
demonstrated local workforce conflict or a dated payroll shortfall in a shared
account. Food deficit, prices, and prose are not hidden triggers.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from src.classes.causal_origin import CausalOrigin
from src.classes.economy.models import ProductionPriority
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue

from .economy import _causes, _delta
from .events import record_event
from .institutional_decision_turn import DiscretionaryAdapter


ACTION = "set_production_priority"
SCOPE = "trade"


class ProductionPriorityOption(SocietyValue):
    """One facility an owner may place first in a real payroll conflict."""

    id: str
    actor_ref: EntityRef
    scope: Literal["local_workforce", "shared_payroll_pool"]
    facility_id: str
    owner_ref: EntityRef
    payroll_account_id: str
    settlement_id: str
    settlement_name: str
    occupation: str
    facility_name: str
    output_names: tuple[str, ...]

    def decision(self):
        # Keep the decision contract intentionally closed.  The engine derives
        # the facility and all allocation terms by recomposing this ID.
        return {"action": ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class ProductionPriorityDraft:
    """Validated hand-off for the Economy owner, not a persisted model.

    Root integration should turn this draft into the versioned Economy-owned
    ``ProductionPriority`` record.  Keeping the bridge local prevents this
    vertical from inventing a second persistence or planner system.
    """

    id: str
    owner_ref: EntityRef
    payroll_account_id: str
    scope: Literal["local_workforce", "shared_payroll_pool"]
    settlement_id: str
    occupation: str
    facility_id: str
    decision_event_id: str
    selected_affordance_id: str
    created_day: int
    effective_day: int


def _facility_context(world, facility):
    economy = world.economy
    stock = economy.stocks.get(facility.stock_id)
    recipe = economy.recipes.get(facility.recipe_id)
    if stock is None or recipe is None:
        return None
    return stock, recipe


def _conflict_key(facility, stock, recipe):
    return (stock.owner_ref, facility.payroll_account_id,
            stock.location_id, recipe.occupation)


def _labor_availability_causes(world, groups):
    """Facts currently reducing Society's available count for these cohorts."""
    group_ids = {group.id for group in groups}
    sources = {group.last_event_id for group in groups if group.last_event_id}
    sources.update(item.last_event_id for item in world.society.migrations.values()
                   if item.source_group_id in group_ids)
    sources.update(item.last_event_id for item in world.society.workforce_transitions.values()
                   if item.source_group_id in group_ids)
    sources.update(item.last_event_id for item in world.society.detachments.values()
                   if item.source_group_id in group_ids and item.stage != "disbanded")
    sources.update(item.last_event_id for item in world.society.civic_protests.values()
                   if item.group_id in group_ids and item.stage == "open")
    sources.update(item.last_event_id for item in world.society.civic_movements.values()
                   if item.stage in {"active", "rebellion", "revolution", "negotiating"}
                   and group_ids.intersection(item.participants_by_group))
    sources.update(item.last_event_id for item in world.society.civic_strikes.values()
                   if item.stage == "active" and group_ids.intersection(item.participants_by_group))
    return tuple(sorted(source for source in sources if source))


def production_priority_options(world, actor_ref):
    """Recompose every currently valid facility-priority affordance.

    ``actor_ref`` must be the facility owner's institutional reference.  A
    facility with no valid stock/recipe is not an option, and a solitary line
    never creates a choice merely because it is under-producing.
    """
    if not isinstance(actor_ref, EntityRef) or not can_actor_act_for(world, actor_ref, actor_ref, SCOPE):
        return ()
    grouped = {}
    contexts = {}
    for facility in world.economy.facilities.values():
        context = _facility_context(world, facility)
        if context is None:
            continue
        stock, recipe = context
        key = _conflict_key(facility, stock, recipe)
        contexts[facility.id] = (facility, stock, recipe, key)
        if stock.owner_ref == actor_ref:
            grouped.setdefault(key, []).append(facility.id)

    next_boundary = ((world.clock.absolute_day // 30) + 1) * 30
    scheduled_accounts = {
        item.payroll_account_id
        for item in getattr(world.economy, "production_priorities", {}).values()
        if item.effective_day == next_boundary
    }
    by_account = {}
    for facility_id, (facility, stock, recipe, _key) in contexts.items():
        if stock.owner_ref == actor_ref:
            by_account.setdefault(facility.payroll_account_id, []).append(
                (facility, stock, recipe)
            )

    options = []
    for account_id, account_facilities in sorted(by_account.items()):
        if account_id in scheduled_accounts or len(account_facilities) < 2:
            continue
        pool_conflict = any(
            _current_payroll_shortfall(world, facility)
            for facility, _stock, _recipe in account_facilities
        )
        if pool_conflict:
            groups = [("shared_payroll_pool", account_facilities)]
        else:
            local_groups = {}
            for item in account_facilities:
                facility, stock, recipe = item
                local_groups.setdefault(_conflict_key(facility, stock, recipe), []).append(item)
            groups = [
                ("local_workforce", items)
                for _key, items in sorted(local_groups.items(), key=lambda pair: repr(pair[0]))
                if len(items) > 1
            ]
        for scope, eligible in groups:
            for facility, stock, recipe in sorted(eligible, key=lambda item: item[0].id):
                settlement_id = stock.location_id
                site = getattr(world, "map", None)
                site = getattr(site, "infrastructure_sites", {}).get(facility.site_id)
                facility_name = getattr(site, "name", facility.id)
                recipe_outputs = getattr(recipe, "outputs", {})
                outputs = tuple(world.economy.resources[resource_id].name
                                for resource_id in sorted(recipe_outputs)
                                if resource_id in getattr(world.economy, "resources", {}))
                settlement = getattr(getattr(world, "society", None), "settlements", {}).get(
                    settlement_id
                )
                if scope == "shared_payroll_pool":
                    option_id = (f"production-priority:pool:{actor_ref.kind}:{actor_ref.id}:"
                                 f"{facility.payroll_account_id}:{next_boundary}:{facility.id}")
                else:
                    option_id = (f"production-priority:{actor_ref.kind}:{actor_ref.id}:"
                                 f"{settlement_id}:{recipe.occupation}:{next_boundary}:{facility.id}")
                options.append(ProductionPriorityOption(
                    id=option_id, actor_ref=actor_ref, scope=scope,
                    facility_id=facility.id, owner_ref=stock.owner_ref,
                    payroll_account_id=facility.payroll_account_id,
                    settlement_id=settlement_id,
                    settlement_name=getattr(settlement, "name", settlement_id),
                    occupation=recipe.occupation,
                    facility_name=facility_name,
                    output_names=outputs or tuple(sorted(recipe_outputs))))
    return tuple(options)


def _current_payroll_shortfall(world, facility):
    event_index = getattr(world, "event_index", None)
    if not callable(event_index):
        return False
    receipt = event_index().get(facility.last_event_id)
    payload = (receipt.causal_payload.get("production")
               if receipt is not None and isinstance(receipt.causal_payload, dict) else None)
    return bool(
        receipt is not None
        and receipt.day == world.clock.absolute_day
        and receipt.event_type == "production_limited"
        and isinstance(payload, dict)
        and payload.get("facility_id") == facility.id
        and payload.get("observed_day") == world.clock.absolute_day
        and isinstance(payload.get("limitations"), list)
        and "payroll_funds" in payload["limitations"]
        and isinstance(payload.get("limits"), dict)
        and type(payload["limits"].get("payroll_funds")) is int
    )


def _decision_event(world, decision_event_id, expected):
    event = next((item for item in world.events if item.id == decision_event_id), None)
    if (event is None or event.fact_kind != FactKind.DECISION
            or event.causal_origin is not CausalOrigin.ACTOR_DECISION
            or event.day != world.clock.absolute_day
            or event.decision != expected):
        raise ValueError("production priority requires the exact current actor decision")
    return event


def execute_production_priority(world, actor_ref, option_id, decision_event_id):
    """Validate a selected option and return an Economy-owned draft.

    No state is mutated here.  The caller must persist the draft through the
    Economy owner, which can then be consumed by the next production boundary.
    """
    options = production_priority_options(world, actor_ref)
    option = next((item for item in options if item.id == option_id), None)
    if option is None:
        raise ValueError("stale production priority affordance")
    if not can_actor_act_for(world, actor_ref, option.owner_ref, SCOPE):
        raise ValueError("current trade authority no longer permits production priority")
    decision = _decision_event(world, decision_event_id, option.decision())
    next_boundary = ((world.clock.absolute_day // 30) + 1) * 30
    return ProductionPriorityDraft(
        id=_priority_id(option, next_boundary),
        owner_ref=option.owner_ref,
        payroll_account_id=option.payroll_account_id,
        scope=option.scope,
        settlement_id=option.settlement_id,
        occupation=option.occupation,
        facility_id=option.facility_id,
        decision_event_id=decision.id,
        selected_affordance_id=option.id,
        created_day=world.clock.absolute_day,
        effective_day=next_boundary,
    )


def _priority_id(option, effective_day):
    if option.scope == "shared_payroll_pool":
        return (f"production-priority:pool:{option.owner_ref.kind}:{option.owner_ref.id}:"
                f"{option.payroll_account_id}:{effective_day}")
    return (f"production-priority:local:{option.owner_ref.kind}:{option.owner_ref.id}:"
            f"{option.payroll_account_id}:{option.settlement_id}:{option.occupation}:{effective_day}")


def _provenance(world, draft):
    """Only canonical facts that informed this local scheduling choice."""
    if draft.scope == "shared_payroll_pool":
        facilities = tuple(
            facility for facility in world.economy.facilities.values()
            if facility.payroll_account_id == draft.payroll_account_id
            and (context := _facility_context(world, facility)) is not None
            and context[0].owner_ref == draft.owner_ref
        )
    else:
        facilities = tuple(
            facility for facility in world.economy.facilities.values()
            if _facility_context(world, facility) is not None
            and _conflict_key(facility, *_facility_context(world, facility))
            == (draft.owner_ref, draft.payroll_account_id, draft.settlement_id, draft.occupation)
        )
    account = world.economy.accounts[draft.payroll_account_id]
    settlement_reports = tuple(
        report for settlement_id in sorted({
            world.economy.stocks[facility.stock_id].location_id for facility in facilities
        })
        if (report := world.knowledge.settlement_report(draft.owner_ref, settlement_id)) is not None
    )
    labor_groups = tuple(
        group for group in world.society.population.values()
        if (group.settlement_id, group.occupation) in {
            (world.economy.stocks[facility.stock_id].location_id,
             world.economy.recipes[facility.recipe_id].occupation)
            for facility in facilities
        }
    )
    return _causes(
        account.last_event_id,
        *(item.event_id for item in settlement_reports),
        *_labor_availability_causes(world, labor_groups),
        *(facility.last_event_id for facility in facilities),
        *(world.economy.stocks[facility.stock_id].last_event_ids.get(resource)
          for facility in facilities
          for resource in world.economy.recipes[facility.recipe_id].inputs),
    )


def _priority_situation(world, actor_ref, options):
    """Show owned payroll conflicts and only the actor's dated local readings."""
    groups = {}
    for option in options:
        key = (option.scope, option.payroll_account_id,
               option.settlement_id if option.scope == "local_workforce" else None,
               option.occupation if option.scope == "local_workforce" else None)
        groups.setdefault(key, []).append(option)

    conflicts = []
    for (scope, account_id, settlement_id, occupation), group_options in sorted(groups.items()):
        pool_scope = scope == "shared_payroll_pool"
        settlement_ids = sorted({item.settlement_id for item in group_options})
        labor_groups = tuple(
            group for group in world.society.population.values()
            if ((group.settlement_id, group.occupation) in {
                (item.settlement_id, item.occupation) for item in group_options
            })
        )
        labor_sources = _labor_availability_causes(world, labor_groups)
        account = world.economy.accounts[account_id]
        matching_priorities = tuple(
            priority for priority in world.economy.production_priorities.values()
            if priority.owner_ref == actor_ref
            and priority.payroll_account_id == account_id
            and priority.scope == scope
            and (pool_scope or (priority.settlement_id, priority.occupation)
                 == (settlement_id, occupation))
        )
        last_applied = max(
            (item for item in matching_priorities if item.effective_day <= world.clock.absolute_day),
            key=lambda item: item.effective_day,
            default=None,
        )
        scheduled = min(
            (item for item in matching_priorities if item.effective_day > world.clock.absolute_day),
            key=lambda item: item.effective_day,
            default=None,
        )
        next_boundary = ((world.clock.absolute_day // 30) + 1) * 30
        facility_names = {option.facility_id: option.facility_name for option in group_options}
        lines = []
        for option in sorted(group_options, key=lambda item: item.facility_id):
            facility = world.economy.facilities[option.facility_id]
            recipe = world.economy.recipes[facility.recipe_id]
            stock = world.economy.stocks[facility.stock_id]
            settlement = world.society.settlements[option.settlement_id]
            production_event = world.event_index().get(facility.last_event_id)
            production = (
                production_event.causal_payload.get("production")
                if production_event is not None and isinstance(production_event.causal_payload, dict)
                else None
            )
            resource_names = {
                resource_id: world.economy.resources[resource_id].name
                for resource_id in set(recipe.inputs) | set(recipe.outputs)
                if resource_id in world.economy.resources
            }
            resource_units = {
                resource_id: world.economy.resources[resource_id].unit
                for resource_id in set(recipe.inputs) | set(recipe.outputs)
                if resource_id in world.economy.resources
            }
            lines.append({
                "affordance_id": option.id,
                "facility_id": facility.id,
                "facility_name": option.facility_name,
                "settlement_id": option.settlement_id,
                "settlement_name": settlement.name,
                "occupation": option.occupation,
                "outputs_per_batch": [
                    {"resource_id": resource_id, "resource_name": resource_names.get(resource_id, resource_id),
                     "unit": resource_units.get(resource_id), "quantity": quantity}
                    for resource_id, quantity in sorted(recipe.outputs.items())
                ],
                "inputs_per_batch": [
                    {"resource_id": resource_id, "resource_name": resource_names.get(resource_id, resource_id),
                     "unit": resource_units.get(resource_id), "quantity": quantity,
                     "available": stock.goods.get(resource_id, 0),
                     "source_event_id": stock.last_event_ids.get(resource_id)}
                    for resource_id, quantity in sorted(recipe.inputs.items())
                ],
                "capacity_batches": facility.max_batches,
                "last_batches": facility.last_batches,
                "last_limitations": list(facility.last_limitations),
                "production_receipt_event_id": facility.last_event_id,
                "production_receipt_day": production.get("observed_day")
                if isinstance(production, dict) else None,
                "workers_per_batch": recipe.workers,
                "wage_per_worker": facility.wage_per_worker,
                "wage_per_batch": recipe.workers * facility.wage_per_worker,
            })
        conflict = {
            "scope": scope,
            "settlement_id": None if pool_scope else settlement_id,
            "settlement_name": "Múltiplos assentamentos" if pool_scope
            else world.society.settlements[settlement_id].name,
            "occupation": None if pool_scope else occupation,
            "shared_payroll": True,
            "observed_day": world.clock.absolute_day,
            "payroll_balance": account.balance,
            "payroll_source_event_id": account.last_event_id,
            "labor_source_event_ids": sorted(labor_sources),
            "next_effective_day": next_boundary,
            "lines": lines,
            "last_applied_priority": ({
                "facility_id": last_applied.facility_id,
                "facility_name": facility_names.get(last_applied.facility_id,
                                                     last_applied.facility_id),
                "effective_day": last_applied.effective_day,
                "event_id": last_applied.last_event_id,
            } if last_applied is not None else None),
            "scheduled_priority": ({
                "facility_id": scheduled.facility_id,
                "facility_name": facility_names.get(scheduled.facility_id,
                                                     scheduled.facility_id),
                "effective_day": scheduled.effective_day,
                "event_id": scheduled.last_event_id,
            } if scheduled is not None else None),
            "settlement_report": None,
        }
        if pool_scope:
            available_by_settlement = {}
            for group in labor_groups:
                key = (group.settlement_id, group.occupation)
                available_by_settlement[key] = (
                    available_by_settlement.get(key, 0)
                    + world.society.available_count(group.id)
                )
            conflict["society_available_workers_by_settlement"] = [
                {"settlement_id": settlement, "occupation": occupation_name,
                 "available_workers": count}
                for (settlement, occupation_name), count in sorted(available_by_settlement.items())
            ]
            conflict["settlement_reports"] = [
                {
                    "settlement_id": report.settlement_id,
                    "event_id": report.event_id,
                    "observed_day": report.observed_day,
                    "age_days": max(0, world.clock.absolute_day - report.observed_day),
                    "health": report.health,
                    "missing_food": report.missing_food,
                    "unrest": report.unrest,
                    "population": report.present_population,
                }
                for settlement_id in settlement_ids
                if (report := world.knowledge.settlement_report(actor_ref, settlement_id)) is not None
            ]
        else:
            # This is current Society availability, not a forecast of labour
            # left after other owners run at the upcoming boundary.
            conflict["society_available_workers"] = sum(
                world.society.available_count(group.id) for group in labor_groups
            )
            report = world.knowledge.settlement_report(actor_ref, settlement_id)
        if not pool_scope and report is not None:
            conflict["settlement_report"] = {
                "event_id": report.event_id,
                "observed_day": report.observed_day,
                "age_days": max(0, world.clock.absolute_day - report.observed_day),
                "health": report.health,
                "missing_food": report.missing_food,
                "unrest": report.unrest,
                "population": report.present_population,
            }
        conflicts.append(conflict)
    return {"today": world.clock.absolute_day, "payroll_competition": conflicts}


def set_production_priority(world, actor_ref, option_id, *, decision_event_id):
    """Persist one decision-backed priority for the next monthly production.

    The caller has already made the actor decision.  Economy stores only the
    validated local ordering intent; it neither produces goods nor reserves
    workers here.  A defensive candidate keeps direct owner calls atomic.
    """
    candidate = deepcopy(world)
    draft = execute_production_priority(candidate, actor_ref, option_id, decision_event_id)
    previous = candidate.economy.production_priorities.get(draft.id)
    causes = _causes(draft.decision_event_id, previous.last_event_id if previous else None,
                     *_provenance(candidate, draft))
    event = record_event(
        candidate, "production_priority_selected",
        ("A instituição definiu a precedência de uma linha no caixa de folha compartilhado para o próximo ciclo."
         if draft.scope == "shared_payroll_pool"
         else "A instituição definiu a precedência local de uma linha produtiva para o próximo ciclo."),
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": draft.decision_event_id,
                        "actor_ref": draft.owner_ref.to_dict(),
                        "selected_affordance_id": draft.selected_affordance_id,
                        "scope": draft.scope,
                        "facility_id": draft.facility_id,
                        "effective_day": draft.effective_day},
        deltas=(_delta("production_priority", draft.id, "selected_affordance_id",
                       previous.selected_affordance_id if previous else None,
                       draft.selected_affordance_id),
                _delta("production_priority", draft.id, "scope",
                       previous.scope if previous else None, draft.scope),
                _delta("production_priority", draft.id, "facility_id",
                       previous.facility_id if previous else None, draft.facility_id),
                _delta("production_priority", draft.id, "effective_day",
                       previous.effective_day if previous else None, draft.effective_day)),
        cause_ids=causes,
    )
    candidate.economy.production_priorities[draft.id] = ProductionPriority(
        id=draft.id, owner_ref=draft.owner_ref,
        payroll_account_id=draft.payroll_account_id, scope=draft.scope,
        settlement_id=draft.settlement_id,
        occupation=draft.occupation, facility_id=draft.facility_id,
        effective_day=draft.effective_day, decision_event_id=draft.decision_event_id,
        selected_affordance_id=draft.selected_affordance_id, last_event_id=event.id,
    )
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.economy.production_priorities[draft.id]


def _option_causes(world, option):
    draft = ProductionPriorityDraft(
        id=_priority_id(option, ((world.clock.absolute_day // 30) + 1) * 30),
        owner_ref=option.owner_ref, payroll_account_id=option.payroll_account_id,
        scope=option.scope,
        settlement_id=option.settlement_id, occupation=option.occupation,
        facility_id=option.facility_id, decision_event_id="pending",
        selected_affordance_id=option.id, created_day=world.clock.absolute_day,
        effective_day=((world.clock.absolute_day // 30) + 1) * 30,
    )
    return _provenance(world, draft)


def production_priority_adapters():
    return (DiscretionaryAdapter(
        # This context is intentionally separate from construction's
        # production context; the composed agenda keeps one situation builder
        # per family key, so sharing the key would hide payroll tradeoffs.
        name="production_priority", family="production_priority",
        options_fn=production_priority_options,
        label_fn=lambda option: (
            (f"Avaliar primeiro {', '.join(option.output_names)} em {option.facility_name} "
             f"({option.settlement_name}) frente às outras instalações no mesmo caixa de folha; "
             "não reserva dinheiro nem garante lote, no próximo ciclo."
             if option.scope == "shared_payroll_pool"
             else f"Priorizar {', '.join(option.output_names)} em {option.facility_name} "
                  f"({option.settlement_name}) no conflito local de mão de obra, no próximo ciclo.")),
        causes_fn=_option_causes,
        execute_fn=lambda world, actor, option_id, decision_event_id:
            set_production_priority(world, actor, option_id, decision_event_id=decision_event_id),
        situation_fn=_priority_situation,
    ),)

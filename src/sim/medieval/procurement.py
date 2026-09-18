"""Monthly supply intentions and independent seller decisions over real executors."""

import copy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.governance.models import StrategicPlan
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity
from .economy import _causes, _delta
from .events import record_event
from .intelligence import reserve_quantity
from .logistics import queue_freight
from .markets import purchase
from .routing import fiscal_route_options, known_supply_path
from .demand import objective_target
from .tariffs import export_fee

SUPPLY_OBJECTIVE_ACTION = "execute_supply_objective"


def _account(world, actor_ref):
    return next((a for _, a in sorted(world.economy.accounts.items()) if a.owner_ref == actor_ref), None)


def consider_sale(world, terms, buy_decision_id):
    """Seller may refuse: buyer intent neither authorizes nor forces its response."""
    source = world.economy.stocks[terms["source_id"]]
    actor = source.owner_ref
    resource_id = terms["resource_id"]
    market = world.economy.markets[source.location_id]
    available = max(0, source.goods.get(resource_id, 0) - reserve_quantity(world, source.id, resource_id))
    reason = None
    if not can_actor_act_for(world, actor, actor, "trade"):
        reason = "sem autoridade comercial"
    elif available < terms["quantity"]:
        reason = "a venda comprometeria a reserva local"
    elif market.updated_day != terms["quote_day"] or market.prices[resource_id] != terms["unit_price"]:
        reason = "cotação desatualizada"
    action = "refuse_sale" if reason else "sell"
    event = record_event(world, "sale_refused" if reason else "sell_decided",
                         f"{(world.society.polities if actor.kind == 'polity' else world.society.organizations)[actor.id].name}: "
                         f"{reason or 'venda aceita, preservando a reserva local'}.",
                         fact_kind=FactKind.DECISION,
                         decision={**terms, "action": action, "actor_ref": actor.to_dict()},
                         cause_ids=_causes(buy_decision_id, source.last_event_ids.get(resource_id), market.last_event_id))
    return None if reason else event.id


def _set_plan(world, objective, stage, *, blocker=None, order_ids=(), causes=()):
    identity = f"plan:{objective.id}"
    previous = world.strategy.plans.get(identity)
    event = record_event(world, "supply_plan_updated",
                         f"Abastecimento de {world.society.settlements[objective.settlement_id].name} "
                         f"({world.economy.resources[objective.resource_id].name}): "
                         + {"satisfied": "reserva atendida.", "acquire": "buscando fornecimento.",
                            "await_delivery": "aguardando carga física.", "blocked": f"impedimento: {blocker}."}[stage],
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("plan", identity, "stage", previous.stage if previous else None, stage),),
                         cause_ids=_causes(previous.last_event_id if previous else None, *causes))
    plan = StrategicPlan(id=identity, objective_id=objective.id, stage=stage, blocker=blocker,
                         order_ids=tuple(order_ids), last_review_day=world.clock.absolute_day, last_event_id=event.id)
    world.strategy.plans[identity] = plan
    return plan


def _pending_orders(world, stock_id, resource_id):
    return tuple(o for _, o in sorted(world.economy.freight_orders.items())
                 if o.destination_id == stock_id and o.resource_id == resource_id and o.quantity > o.delivered_quantity)


def _route_evidence(option):
    """The exact dated receipts that made this selected path available."""
    return (*option.route_report_ids, *option.fiscal_route_report_ids)


def _offers(world, objective, inventory, reasons):
    """Candidate choices use only the actor's reports, never foreign inventory."""
    result, evidence = [], []
    for report in world.knowledge.for_actor(objective.actor_ref):
        if (report.resource_id != objective.resource_id or report.stock_id == inventory.stock_id
                or world.clock.absolute_day - report.observed_day >= 30):
            continue
        source = world.economy.stocks[report.stock_id]  # public identity/location, not goods
        if source.owner_ref != report.publisher_ref:
            continue
        amount = report.quantity
        if report.kind == "inventory":
            amount -= reserve_quantity(world, source.id, objective.resource_id)
        if amount <= 0:
            continue
        route_options = fiscal_route_options(world, objective.actor_ref, source.id, inventory.stock_id,
                                             objective.resource_id, 1)
        if not route_options:
            # Preserve the pre-existing physical-report explanation: if no
            # route report supports a path, fiscal policy cannot invent one.
            consulted = []
            known_supply_path(world, objective.actor_ref, source.location_id,
                              objective.settlement_id, objective.resource_id, consulted=consulted)
            reasons.append("sem rota conhecida até a origem")
            evidence.extend(consulted)
            continue
        route_option = route_options[0]
        rate = (0 if report.export_collector_ref is not None
                and report.export_collector_ref.id == world.society.settlements[objective.settlement_id].administrator_id
                else report.export_rate_permille)
        price = 0 if source.owner_ref == objective.actor_ref else report.unit_price
        # Compare the buyer's known all-in marginal quote, retaining base price
        # separately for the material executor's one-order ceiling calculation.
        result.append((price * (1000 + rate) + route_option.estimated_customs_fee * 1000,
                       len(route_option.route_ids), report.stock_id, amount, route_option, report))
    return sorted(result, key=lambda value: value[:3]), tuple(dict.fromkeys(evidence))


def _review_objective(world, objective):
    actor = objective.actor_ref
    resource_id = objective.resource_id
    stock = world.economy.stocks[objective.stock_id]
    if (stock.owner_ref != actor or (objective.kind == "maintain_food_reserve"
            and world.society.settlements[objective.settlement_id].administrator_id != actor.id)
            or not can_actor_act_for(world, actor, actor, "supply")):
        _set_plan(world, objective, "blocked", blocker="sem autoridade de abastecimento")
        return
    inventory = next((r for r in world.knowledge.for_actor(actor) if r.stock_id == stock.id and r.kind == "inventory"
                      and r.resource_id == resource_id and r.observed_day == world.clock.absolute_day), None)
    if inventory is None:
        _set_plan(world, objective, "blocked", blocker="sem relatório local atualizado")
        return
    target = objective_target(world, objective)
    pending = _pending_orders(world, stock.id, resource_id)
    if inventory.quantity >= target:
        _set_plan(world, objective, "satisfied", order_ids=[o.id for o in pending], causes=(inventory.event_id,))
        return
    missing = max(0, target - inventory.quantity - sum(o.quantity - o.delivered_quantity for o in pending))
    plan = _set_plan(world, objective, "acquire", order_ids=[o.id for o in pending], causes=(inventory.event_id,))
    order_ids, reasons, response_causes = list(plan.order_ids), [], []
    offers, closed_routes = _offers(world, objective, inventory, reasons)
    for _, _, source_id, available, _, report in offers:
        if missing <= 0:
            break
        quantity = min(missing, available)
        source = world.economy.stocks[source_id]
        price = report.unit_price
        if source.owner_ref == actor:
            # Local administrative execution rechecks stock already known to its owner.
            quantity = min(quantity, max(0, source.goods.get(resource_id, 0) - reserve_quantity(world, source_id, resource_id)))
            if quantity <= 0:
                continue
            route_option = fiscal_route_options(world, actor, source_id, stock.id, resource_id, quantity)
            if not route_option:
                reasons.append("sem rota conhecida até a origem")
                continue
            route_option = route_option[0]
            path, evidence = route_option.route_ids, _route_evidence(route_option)
            decision_terms = {"action": "freight", "actor_ref": actor.to_dict(), "source_id": source_id,
                              "destination_id": stock.id, "resource_id": resource_id, "quantity": quantity,
                              "route_ids": list(path)}
            if route_option.fiscal_route_report_ids:
                decision_terms["route_option_id"] = route_option.id
            decision = record_event(world, "freight_decided", f"Remeter {quantity} de {world.economy.resources[resource_id].name} para {world.society.settlements[objective.settlement_id].name}.",
                                    fact_kind=FactKind.DECISION,
                                    decision=decision_terms,
                                    cause_ids=_causes(plan.last_event_id, report.event_id, *evidence))
            order = queue_freight(world, source_id, stock.id, resource_id, quantity, path, decision_event_id=decision.id)
        else:
            buyer, seller = _account(world, actor), _account(world, source.owner_ref)
            if buyer is None or seller is None or not can_actor_act_for(world, actor, actor, "trade"):
                reasons.append("sem conta ou autoridade comercial")
                continue
            destination_admin = world.society.settlements[stock.location_id].administrator_id
            quote = {"export_rate_permille": report.export_rate_permille,
                     "export_policy_event_id": report.export_policy_event_id,
                     "export_collector_ref": (report.export_collector_ref.to_dict()
                                              if report.export_collector_ref is not None else None)}
            # The buyer knows its own settlement's administration. A quote from
            # that same administration is domestic and explicitly has no export fee.
            if quote["export_collector_ref"] is not None and quote["export_collector_ref"]["id"] == destination_admin:
                quote = {"export_rate_permille": 0, "export_policy_event_id": None, "export_collector_ref": None}
            quantity = min(quantity, buyer.balance * 1000 // (price * (1000 + quote["export_rate_permille"])))
            if quantity <= 0:
                reasons.append("saldo insuficiente")
                continue
            route_option = fiscal_route_options(world, actor, source_id, stock.id, resource_id, quantity)
            if not route_option:
                reasons.append("sem rota conhecida até a origem")
                continue
            route_option = route_option[0]
            path, evidence = route_option.route_ids, _route_evidence(route_option)
            fee = export_fee(quantity, price, quote["export_rate_permille"])
            terms = {"source_id": source_id, "destination_id": stock.id, "resource_id": resource_id, "quantity": quantity,
                     "unit_price": price, "quote_day": report.quote_day, "route_ids": list(path),
                     "buyer_account_id": buyer.id, "seller_account_id": seller.id,
                     **quote, "total_price": quantity * price + fee}
            if route_option.fiscal_route_report_ids:
                terms["route_option_id"] = route_option.id
            decision = record_event(world, "buy_decided", f"Propor compra de {quantity} de {world.economy.resources[resource_id].name} para {world.society.settlements[objective.settlement_id].name}.",
                                    fact_kind=FactKind.DECISION,
                                    decision={**terms, "action": "buy", "actor_ref": actor.to_dict()},
                                    cause_ids=_causes(plan.last_event_id, report.event_id, buyer.last_event_id, *evidence))
            accepted = consider_sale(world, terms, decision.id)
            response_causes.append(world.events[-1].id)
            if accepted is None:
                reasons.append("fornecedor recusou a proposta")
                continue
            order = purchase(world, decision.id, accepted)
        order_ids.append(order.id)
        missing -= quantity
    blocker = "; ".join(sorted(set(reasons))) if reasons else "sem oferta acessível suficiente"
    _set_plan(world, objective, "await_delivery" if order_ids else "blocked",
              blocker=blocker if missing else None, order_ids=order_ids,
              causes=[*response_causes, *(closed_routes if missing else ()),
                      *(world.economy.freight_orders[oid].last_event_id for oid in order_ids)])


def review_supply(world, *, exclude_objective_ids=()):
    """Monthly policy boundary; no RNG, LLM calls or required quota of conflicts.

    ``exclude_objective_ids`` lets a concurrent, actor-facing review claim an
    objective for this same boundary; the automatic pass then leaves it alone
    instead of silently executing behind a menu the actor already saw.
    """
    for objective in sorted((item for item in world.strategy.objectives.values()
                             if item.kind != "defend_occupied_settlement"
                             and item.id not in exclude_objective_ids),
                            key=lambda o: (o.kind != "maintain_food_reserve", o.id)):
        _review_objective(world, objective)


@dataclass(frozen=True)
class SupplyObjectiveOption:
    """Transient engine option. A decider may only select this ID.

    It names only the objective; procurement's own executor recomposes and
    revalidates the source, quantity and route at execution time. No supplier,
    quantity or route is ever exposed here.
    """

    id: Identity
    actor_ref: EntityRef
    objective_id: Identity

    def decision(self):
        return {"action": SUPPLY_OBJECTIVE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "objective_id": self.objective_id}


def _would_open_an_order(world, objective_id):
    """Preview only: run the real policy on an isolated copy and discard it.

    This reuses ``_review_objective`` verbatim so the preview can never drift
    from what the real executor does; nothing here duplicates the buy/freight
    selection logic.
    """
    candidate = copy.deepcopy(world)
    _review_objective(candidate, candidate.strategy.objectives[objective_id])
    plan = candidate.strategy.plans.get(f"plan:{objective_id}")
    return plan is not None and plan.stage == "await_delivery"


def supply_objective_options(world, actor):
    """Objectives whose current plan would materially open an order today.

    Scoped to the actor's own currently food-pressured settlements (the same
    condition institutional aid already gates on), so this never turns routine
    production-input procurement into an actor-facing decision.
    """
    from .institutional_aid_policy import _pressured_settlements
    if not isinstance(actor, EntityRef) or actor.kind != "polity":
        return ()
    options = []
    for settlement_id in _pressured_settlements(world, actor):
        objective = next((item for item in world.strategy.objectives.values()
                          if item.actor_ref == actor and item.settlement_id == settlement_id
                          and item.resource_id == "food"), None)
        if objective is None or not _would_open_an_order(world, objective.id):
            continue
        options.append(SupplyObjectiveOption(
            id=f"supply-objective:{actor.kind}:{actor.id}:{objective.id}:{world.clock.absolute_day}",
            actor_ref=actor, objective_id=objective.id))
    return tuple(options)


def execute_supply_objective_option(world, actor, option_id, decision_event_id):
    """Revalidate everything, then run the same, unmodified procurement policy."""
    decision = next((event for event in world.events if event.id == decision_event_id), None)
    option = next((item for item in supply_objective_options(world, actor) if item.id == option_id), None)
    if (option is None or decision is None or decision.fact_kind != FactKind.DECISION
            or decision.day != world.clock.absolute_day or decision.decision != option.decision()):
        raise ValueError("supply objective option is stale or unknown")
    _review_objective(world, world.strategy.objectives[option.objective_id])
    return world.strategy.plans[f"plan:{option.objective_id}"]


def progress_supply(world):
    """Delivery receipts can satisfy a goal; pending orders never count as reserves."""
    for plan in list(world.strategy.plans.values()):
        if plan.stage != "await_delivery":
            continue
        objective = world.strategy.objectives[plan.objective_id]
        stock = world.economy.stocks[objective.stock_id]
        if stock.owner_ref == objective.actor_ref and stock.goods.get(objective.resource_id, 0) >= objective_target(world, objective):
            _set_plan(world, objective, "satisfied", order_ids=plan.order_ids,
                      causes=_causes(stock.last_event_ids.get(objective.resource_id)))

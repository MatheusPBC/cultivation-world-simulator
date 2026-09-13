"""Monthly supply intentions and independent seller decisions over real executors."""

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.governance.models import StrategicPlan
from .economy import _causes, _delta
from .events import record_event
from .intelligence import reserve_quantity
from .logistics import queue_freight
from .markets import purchase
from .routing import supply_path
from .demand import objective_target


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


def _offers(world, objective, inventory):
    """Candidate choices use only the actor's reports, never foreign inventory."""
    result = []
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
        path = supply_path(world, source.location_id, objective.settlement_id, objective.resource_id)
        if path is not None:
            price = 0 if source.owner_ref == objective.actor_ref else report.unit_price
            result.append((price, len(path), report.stock_id, amount, path, report))
    return sorted(result, key=lambda value: value[:3])


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
    for price, _, source_id, available, path, report in _offers(world, objective, inventory):
        if missing <= 0:
            break
        quantity = min(missing, available)
        source = world.economy.stocks[source_id]
        if source.owner_ref == actor:
            # Local administrative execution rechecks stock already known to its owner.
            quantity = min(quantity, max(0, source.goods.get(resource_id, 0) - reserve_quantity(world, source_id, resource_id)))
            if quantity <= 0:
                continue
            decision = record_event(world, "freight_decided", f"Remeter {quantity} de {world.economy.resources[resource_id].name} para {world.society.settlements[objective.settlement_id].name}.",
                                    fact_kind=FactKind.DECISION,
                                    decision={"action": "freight", "actor_ref": actor.to_dict(), "source_id": source_id,
                                              "destination_id": stock.id, "resource_id": resource_id, "quantity": quantity,
                                              "route_ids": list(path)},
                                    cause_ids=(plan.last_event_id, report.event_id))
            order = queue_freight(world, source_id, stock.id, resource_id, quantity, path, decision_event_id=decision.id)
        else:
            buyer, seller = _account(world, actor), _account(world, source.owner_ref)
            if buyer is None or seller is None or not can_actor_act_for(world, actor, actor, "trade"):
                reasons.append("sem conta ou autoridade comercial")
                continue
            quantity = min(quantity, buyer.balance // price)
            if quantity <= 0:
                reasons.append("saldo insuficiente")
                continue
            terms = {"source_id": source_id, "destination_id": stock.id, "resource_id": resource_id, "quantity": quantity,
                     "unit_price": price, "quote_day": report.quote_day, "route_ids": list(path),
                     "buyer_account_id": buyer.id, "seller_account_id": seller.id}
            decision = record_event(world, "buy_decided", f"Propor compra de {quantity} de {world.economy.resources[resource_id].name} para {world.society.settlements[objective.settlement_id].name}.",
                                    fact_kind=FactKind.DECISION,
                                    decision={**terms, "action": "buy", "actor_ref": actor.to_dict()},
                                    cause_ids=_causes(plan.last_event_id, report.event_id, buyer.last_event_id))
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
              causes=[*response_causes, *(world.economy.freight_orders[oid].last_event_id for oid in order_ids)])


def review_supply(world):
    """Monthly policy boundary; no RNG, LLM calls or required quota of conflicts."""
    for objective in sorted(world.strategy.objectives.values(), key=lambda o: (o.kind != "maintain_food_reserve", o.id)):
        _review_objective(world, objective)


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

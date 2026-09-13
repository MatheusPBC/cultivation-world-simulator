"""Material executors. Caller owns the world mutation transaction, not prose."""

from collections import defaultdict
import math

from src.classes.event import FactKind
from src.classes.governance.authority import require_authority, can_actor_act_for
from src.classes.state_delta import StateDelta
from .events import record_event


def _delta(kind, owner_id, aspect, before, after):
    return StateDelta(owner_kind=kind, owner_id=owner_id, aspect=aspect,
                      before=str(before), after=str(after))


def _causes(*values):
    return tuple(sorted({value for value in values if value}))


def _apply_stock(world, stock, goods, event_type, content, *, extra_deltas=(), cause_ids=()):
    changed = sorted(r for r in set(stock.goods) | set(goods) if stock.goods.get(r, 0) != goods.get(r, 0))
    deltas = tuple(_delta("stock", stock.id, r, stock.goods.get(r, 0), goods.get(r, 0)) for r in changed)
    causes = _causes(*cause_ids, *(stock.last_event_ids.get(r) for r in changed))
    updated = stock.model_copy(update={"goods": goods})
    # Do not append history if the candidate stock cannot be committed.
    type(stock).model_validate(updated.model_dump(mode="json"))
    if world.economy.used_capacity(updated) > updated.capacity:
        raise ValueError("storage capacity exceeded")
    event = record_event(world, event_type, content,
                         fact_kind=FactKind.STATE_TRANSITION if deltas or extra_deltas else FactKind.OCCURRENCE,
                         deltas=(*deltas, *extra_deltas), cause_ids=causes)
    provenance = {**stock.last_event_ids, **{r: event.id for r in changed}}
    world.economy.stocks[stock.id] = updated.model_copy(update={"last_event_ids": provenance})
    return event


def monthly_workforce(world):
    available = {g.id: g.count for g in world.society.population.values()}
    for payroll in world.economy.payrolls.values():
        if payroll.day == world.clock.absolute_day:
            for group_id, count in payroll.workers_by_group.items():
                available[group_id] = max(0, available[group_id] - count)
    return available


def produce_monthly(world, available=None) -> None:
    from .labor import settle_labor
    economy = world.economy
    economy.validate(world)
    workers = defaultdict(int)
    if available is None:
        available = monthly_workforce(world)
    for group in world.society.population.values():
        workers[group.settlement_id, group.occupation] += available[group.id]
    for facility in sorted(economy.facilities.values(), key=lambda item: item.id):
        payroll = economy.payrolls.get(facility.id)
        if payroll is not None and payroll.day == world.clock.absolute_day:
            continue
        site = world.map.infrastructure_sites[facility.site_id]
        recipe = economy.recipes[facility.recipe_id]
        stock = economy.stocks[facility.stock_id]
        workforce = (stock.location_id, recipe.occupation)
        limits = {"capacity": facility.max_batches,
                  "site_integrity": math.floor(facility.max_batches * site.integrity),
                  "labor": workers[workforce] // recipe.workers,
                  "payroll_funds": economy.accounts[facility.payroll_account_id].balance // (recipe.workers * facility.wage_per_worker)}
        if not can_actor_act_for(world, stock.owner_ref, stock.owner_ref, "trade"):
            limits["employer_authority"] = 0
        if not site.enabled:
            limits["site_disabled"] = 0
        if recipe.required_technology_id and not world.knowledge.knows(stock.owner_ref, recipe.required_technology_id):
            limits['knowledge'] = 0
        for rid, amount in recipe.inputs.items():
            limits[f"input:{rid}"] = stock.goods.get(rid, 0) // amount
        net_bulk = (sum(economy.resources[r].bulk * q for r, q in recipe.outputs.items())
                    - sum(economy.resources[r].bulk * q for r, q in recipe.inputs.items()))
        if net_bulk > 0:
            limits["storage"] = (stock.capacity - economy.used_capacity(stock)) // net_bulk
        batches = min(limits.values())
        limitations = tuple(sorted(k for k, limit in limits.items() if limit == batches and limit < facility.max_batches))
        goods = dict(stock.goods)
        if batches:
            for rid, amount in recipe.inputs.items():
                goods[rid] -= amount * batches
            for rid, amount in recipe.outputs.items():
                goods[rid] = goods.get(rid, 0) + amount * batches
        updated = facility.model_copy(update={"last_batches": batches, "last_limitations": limitations})
        changes = tuple(_delta("production", facility.id, name, getattr(facility, name), getattr(updated, name))
                        for name in ("last_batches", "last_limitations") if getattr(facility, name) != getattr(updated, name))
        event = _apply_stock(world, stock, goods, "production_completed" if batches else "production_limited",
                             f"{site.name}: {batches} lotes de produção concluídos.",
                             cause_ids=_causes(site.last_event_id, facility.last_event_id,
                                               economy.accounts[facility.payroll_account_id].last_event_id,
                                               *(stock.last_event_ids.get(r) for r in recipe.inputs)),
                             extra_deltas=changes)
        economy.facilities[facility.id] = updated.model_copy(update={"last_event_id": event.id})
        settle_labor(world, facility, batches, available, event.id)
        workers[workforce] -= batches * recipe.workers


def consume_monthly(world) -> None:
    from .consumption import purchase_monthly_rations
    economy = world.economy
    economy.validate(world)
    events = {e.id: e for e in world.events}
    for need in sorted(economy.needs.values(), key=lambda item: item.id):
        previous = events.get(need.last_event_id)
        if previous is not None and previous.day == world.clock.absolute_day and previous.event_type == "subsistence_resolved":
            continue
        stock = economy.stocks[need.stock_id]
        required = world.society.population_at(need.id)
        consumed = min(required, stock.goods.get("food", 0))
        missing = required - consumed
        pressure = math.ceil(100 * missing / required) if required else 0
        health = max(0, need.health - pressure) if missing else min(1000, need.health + 20)
        unrest = min(1000, need.unrest + pressure) if missing else max(0, need.unrest - 20)
        updated = need.model_copy(update={"health": health, "unrest": unrest, "missing_food": missing})
        deltas = tuple(_delta("subsistence", need.id, field, getattr(need, field), getattr(updated, field))
                       for field in ("health", "unrest", "missing_food") if getattr(need, field) != getattr(updated, field))
        paid, receipts = purchase_monthly_rations(world, need, consumed)
        stock = economy.stocks[need.stock_id]
        relief = consumed - paid
        goods = {**stock.goods, "food": stock.goods.get("food", 0) - relief}
        settlement = world.society.settlements[need.id]
        event = _apply_stock(world, stock, goods, "subsistence_resolved",
                             f"{settlement.name}: {consumed}/{required} rações atendidas; {paid} compradas, "
                             f"{relief} de ajuda pública; déficit de {missing}.",
                             extra_deltas=deltas, cause_ids=_causes(need.last_event_id, stock.last_event_ids.get("food"), *receipts,
                                 *(f.last_event_id for f in economy.facilities.values() if f.stock_id == stock.id
                                   and "food" in economy.recipes[f.recipe_id].outputs),
                                 *(o.last_event_id for o in economy.freight_orders.values() if o.destination_id == stock.id
                                   and o.resource_id == "food" and o.delivered_quantity < o.quantity)))
        economy.needs[need.id] = updated.model_copy(update={"last_event_id": event.id})


def transfer_money(world, source_id: str, target_id: str, amount: int, *, decision_event_id: str) -> None:
    """Execute the account owner's payment once, with a current trading mandate."""
    economy = world.economy
    economy.validate(world)
    if type(amount) is not int or amount <= 0 or source_id == target_id:
        raise ValueError("payment requires distinct accounts and a positive integer")
    if source_id not in economy.accounts or target_id not in economy.accounts:
        raise ValueError("unknown payment account")
    source, target = economy.accounts[source_id], economy.accounts[target_id]
    if source.balance < amount:
        raise ValueError("insufficient money")
    event = next((e for e in world.events if e.id == decision_event_id), None)
    intent = event.decision if event is not None else None
    if (event is None or event.fact_kind != FactKind.DECISION or intent is None
            or intent != {"action": "pay", "source_id": source_id,
                          "target_id": target_id, "amount": amount,
                          "actor_ref": source.owner_ref.to_dict()}
            or decision_event_id in economy.payments):
        raise ValueError("payment needs a matching unexecuted decision")
    require_authority(world, source.owner_ref, "trade")
    effect = record_event(world, "payment_completed", f"Pagamento de {amount} unidades monetárias concluído.",
                          fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(_delta("account", source.id, "balance", source.balance, source.balance - amount),
                                  _delta("account", target.id, "balance", target.balance, target.balance + amount)),
                          cause_ids=_causes(decision_event_id, source.last_event_id, target.last_event_id))
    economy.accounts[source.id] = source.model_copy(update={"balance": source.balance - amount, "last_event_id": effect.id})
    economy.accounts[target.id] = target.model_copy(update={"balance": target.balance + amount, "last_event_id": effect.id})
    economy.payments[decision_event_id] = effect.id

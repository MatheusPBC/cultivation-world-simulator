"""Bounded local reference prices and bilateral prepaid purchases."""

from collections import defaultdict
import copy

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from .economy import _causes, _delta
from .events import record_event
from .logistics import check_freight, open_order
from .tariffs import export_fee, export_quote


def update_markets(world):
    economy = world.economy
    economy.validate(world)
    day = world.clock.absolute_day
    for market in sorted(economy.markets.values(), key=lambda m: m.id):
        if market.updated_day >= day:
            continue
        supply = defaultdict(int)
        demand = defaultdict(int)
        demand["food"] = world.society.population_at(market.id)
        causes = [market.last_event_id, economy.needs[market.id].last_event_id]
        for stock in economy.stocks.values():
            if stock.location_id == market.id:
                for rid, amount in stock.goods.items():
                    supply[rid] += amount
                causes.extend(stock.last_event_ids.values())
        for facility in economy.facilities.values():
            if economy.stocks[facility.stock_id].location_id == market.id:
                for rid, amount in economy.recipes[facility.recipe_id].inputs.items():
                    demand[rid] += amount * facility.max_batches
        prices = {}
        from .demand import construction_demand, repair_demand, research_demand
        for stock in economy.stocks.values():
            if stock.location_id == market.id:
                for rid in economy.resources:
                    demand[rid] += (construction_demand(world, stock.id, rid)
                                    + research_demand(world, stock.id, rid)
                                    + repair_demand(world, stock.id, rid))
                for project in economy.repairs.values():
                    if project.stock_id != stock.id or project.stage == "completed":
                        continue
                    causes.append(project.last_event_id)
                    report = world.knowledge.site_report(project.maintainer_ref, project.site_id)
                    if report is not None:
                        causes.append(report.event_id)
        for rid, resource in economy.resources.items():
            desired = resource.base_price * (2 * max(1, demand[rid]) + 1) // (supply[rid] + 1)
            desired = min(resource.base_price * 4, max((resource.base_price + 3) // 4, desired))
            old = market.prices[rid]
            step = max(1, (old + 9) // 10)
            prices[rid] = min(old + step, desired) if desired >= old else max(old - step, desired)
        changes = tuple(_delta("market", market.id, rid, market.prices[rid], prices[rid])
                        for rid in sorted(prices) if market.prices[rid] != prices[rid])
        event = record_event(world, "market_updated", f"Preços de {world.society.settlements[market.id].name} revisados.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(*changes, _delta("market", market.id, "updated_day", market.updated_day, day)),
                             cause_ids=_causes(*causes))
        economy.markets[market.id] = market.model_copy(update={"prices": prices, "updated_day": day, "last_event_id": event.id})


def _purchase_terms(world, buy_id, sell_id):
    events = {e.id: e for e in world.events}
    buy, sell = events.get(buy_id), events.get(sell_id)
    if (buy_id == sell_id or buy is None or sell is None or buy.fact_kind != FactKind.DECISION
            or sell.fact_kind != FactKind.DECISION or buy.decision is None or sell.decision is None):
        raise ValueError("purchase requires independent bilateral consent")
    if buy.day != world.clock.absolute_day or sell.day != world.clock.absolute_day:
        raise ValueError("trade decision is stale; consent must be given today")
    keys = {"source_id", "destination_id", "resource_id", "quantity", "unit_price", "quote_day", "route_ids",
            "seller_account_id", "buyer_account_id", "export_rate_permille", "export_policy_event_id",
            "export_collector_ref", "total_price"}
    if (set(buy.decision) != keys | {"action", "actor_ref"} or set(sell.decision) != keys | {"action", "actor_ref"}
            or buy.decision["action"] != "buy" or sell.decision["action"] != "sell"
            or any(buy.decision[k] != sell.decision[k] for k in keys)):
        raise ValueError("trade consent does not agree on terms")
    terms = {k: buy.decision[k] for k in keys}
    for field in ("quantity", "unit_price", "quote_day", "export_rate_permille", "total_price"):
        minimum = 0 if field in {"quote_day", "export_rate_permille"} else 1
        if type(terms[field]) is not int or terms[field] < minimum:
            raise ValueError("invalid trade quantity, price or quote date")
    for field in ("source_id", "destination_id", "resource_id", "seller_account_id", "buyer_account_id"):
        if not isinstance(terms[field], str) or not terms[field]:
            raise ValueError("invalid trade reference")
    if not isinstance(terms["route_ids"], list) or any(not isinstance(r, str) for r in terms["route_ids"]):
        raise ValueError("invalid trade path")
    check_freight(world, terms["source_id"], terms["destination_id"], terms["resource_id"], terms["quantity"], terms["route_ids"])
    economy = world.economy
    source, destination = economy.stocks[terms["source_id"]], economy.stocks[terms["destination_id"]]
    seller = economy.accounts.get(terms["seller_account_id"])
    buyer = economy.accounts.get(terms["buyer_account_id"])
    if (source.owner_ref == destination.owner_ref or seller is None or buyer is None
            or seller.owner_ref != source.owner_ref or buyer.owner_ref != destination.owner_ref
            or sell.decision["actor_ref"] != seller.owner_ref.to_dict() or buy.decision["actor_ref"] != buyer.owner_ref.to_dict()):
        raise ValueError("trade consent must come from stock and account owners")
    market = economy.markets[source.location_id]
    require_authority(world, buyer.owner_ref, "trade")
    require_authority(world, seller.owner_ref, "trade")
    if terms["unit_price"] != market.prices[terms["resource_id"]] or terms["quote_day"] != market.updated_day:
        raise ValueError("trade price quote is stale or invalid")
    quote = export_quote(world, terms["source_id"], terms["destination_id"])
    if any(terms[field] != value for field, value in quote.items()):
        raise ValueError("export tariff quote is stale or invalid")
    fee = export_fee(terms["quantity"], terms["unit_price"], terms["export_rate_permille"])
    amount = terms["quantity"] * terms["unit_price"]
    if terms["total_price"] != amount + fee:
        raise ValueError("trade total does not match the quoted export tariff")
    collector = None
    if quote["export_collector_ref"] is not None:
        from src.classes.mechanical_language import EntityRef
        collector_ref = EntityRef.from_dict(quote["export_collector_ref"])
        policy = world.authority.tax_policies.get(collector_ref.id)
        collector = economy.accounts.get(policy.account_id) if policy is not None else None
        if (collector is None or collector.owner_ref != collector_ref
                or not can_actor_act_for(world, collector_ref, collector_ref, "taxation")):
            raise ValueError("export tax authority or collector changed")
    if buyer.balance < terms["total_price"]:
        raise ValueError("insufficient purchase funds")
    if buy_id in economy.payments or any({buy_id, sell_id}.intersection(o.decision_ids) for o in economy.freight_orders.values()):
        raise ValueError("trade decision already executed")
    return terms, fee, collector


def purchase(world, buy_decision_id, sell_decision_id):
    """Publish cash and cargo together; a later delivery is independent of payment."""
    world.economy.validate(world)
    terms, fee, collector = _purchase_terms(world, buy_decision_id, sell_decision_id)
    candidate = copy.deepcopy(world)
    order = open_order(candidate, terms["source_id"], terms["destination_id"], terms["resource_id"], terms["quantity"],
                       terms["route_ids"], decision_ids=(buy_decision_id, sell_decision_id))
    economy = candidate.economy
    buyer, seller = economy.accounts[terms["buyer_account_id"]], economy.accounts[terms["seller_account_id"]]
    amount = terms["quantity"] * terms["unit_price"]
    deltas_by_account = {buyer.id: -terms["total_price"], seller.id: amount}
    if fee:
        deltas_by_account[collector.id] = deltas_by_account.get(collector.id, 0) + fee
    event_type = "export_tariff_collected" if fee else "payment_completed"
    event = record_event(candidate, event_type,
                         (f"Compra à vista: {amount} unidades monetárias pagas."
                          if not fee else f"Compra à vista: {amount} ao vendedor e {fee} de tarifa de exportação."),
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=tuple(_delta("account", account_id, "balance", economy.accounts[account_id].balance,
                                             economy.accounts[account_id].balance + change)
                                      for account_id, change in sorted(deltas_by_account.items()) if change),
                         cause_ids=_causes(buy_decision_id, sell_decision_id, order.last_event_id,
                                           buyer.last_event_id, seller.last_event_id,
                                           collector.last_event_id if collector else None,
                                           terms["export_policy_event_id"]))
    for account_id, change in deltas_by_account.items():
        account = economy.accounts[account_id]
        economy.accounts[account_id] = account.model_copy(update={"balance": account.balance + change, "last_event_id": event.id})
    economy.payments[buy_decision_id] = event.id
    economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.economy.freight_orders[order.id]

"""Explicit administrative reports and public surplus bulletins for supply policy.

This first channel abstracts institutional market communication per monthly
review. It is not a global event feed: secret stocks, balances and actions of
other actors are never copied to recipients.
"""

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.governance.models import KnowledgeReport
from src.classes.mechanical_language import EntityRef
from .economy import _causes
from .events import record_event
from .routing import supply_path
from .route_intelligence import refresh_route_reports, refresh_site_reports
from .settlement_intelligence import refresh_settlement_reports
from .demand import reserve_quantity


def refresh_reports(world):
    """Operating public stores/workshops disclose offers, not foreign inventories."""
    day = world.clock.absolute_day
    refresh_site_reports(world)
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    refresh_trade_reports(world)


def refresh_trade_reports(world, *, replace_today=False):
    """Refresh only public inventory/offer quotes after a same-day tariff decision."""
    day = world.clock.absolute_day
    recipients = {o.actor_ref for o in world.strategy.objectives.values()}
    recipients |= {EntityRef("population_group", group_id) for group_id in world.society.population
                   if world.society.available_count(group_id) > 0}
    stocks = {n.stock_id for n in world.economy.needs.values()} | {f.stock_id for f in world.economy.facilities.values()}
    stocks |= {p.stock_id for p in world.research.projects.values() if p.stage not in {'completed', 'superseded'}}
    stocks |= {p.stock_id for p in world.economy.repairs.values() if p.stage != 'completed'}
    resources = {"food", *(o.resource_id for o in world.strategy.objectives.values())}
    for stock_id in sorted(stocks):
        for resource_id in sorted(resources):
            _report_resource(world, stock_id, resource_id, day, recipients, replace_today=replace_today)


def _export_metadata(world, stock):
    """Public source-jurisdiction quote only; never a collector balance."""
    administrator_id = world.society.settlements[stock.location_id].administrator_id
    collector = EntityRef("polity", administrator_id) if administrator_id is not None else None
    policy = world.authority.tax_policies.get(administrator_id) if administrator_id is not None else None
    if administrator_id is None:
        return 0, None, collector
    if policy is None:
        raise ValueError("administered export origin requires a tax policy")
    return policy.export_rate_permille, policy.export_policy_event_id, collector


def _report_resource(world, stock_id, resource_id, day, recipients, *, replace_today=False):
    stock = world.economy.stocks[stock_id]
    owner = stock.owner_ref
    if not can_actor_act_for(world, owner, owner, "supply"):
        return
    market = world.economy.markets[stock.location_id]
    quantity = stock.goods.get(resource_id, 0)
    surplus = max(0, quantity - reserve_quantity(world, stock.id, resource_id))
    export_rate, export_policy_event_id, export_collector_ref = _export_metadata(world, stock)
    key = f"inventory:{owner.kind}:{owner.id}:{stock.id}:{resource_id}"
    previous = world.knowledge.reports.get(key)
    if previous is not None and previous.observed_day == day and not replace_today:
        return
    name = world.economy.resources[resource_id].name
    place = world.society.settlements[stock.location_id].name
    event = record_event(world, "inventory_reported", f"Relatório de {place}: {quantity} de {name} em reserva.",
                         cause_ids=_causes(stock.last_event_ids.get(resource_id), export_policy_event_id))
    report = KnowledgeReport(id=key, recipient_ref=owner, publisher_ref=owner, stock_id=stock.id,
                             resource_id=resource_id, kind="inventory", channel="administrative_report", observed_day=day,
                             quantity=quantity, population=world.society.population_at(stock.location_id),
                             unit_price=market.prices[resource_id], quote_day=market.updated_day, event_id=event.id,
                             export_rate_permille=export_rate, export_policy_event_id=export_policy_event_id,
                             export_collector_ref=export_collector_ref)
    world.knowledge.reports[key] = report
    if not can_actor_act_for(world, owner, owner, "trade"):
        return
    # Zero offers explicitly retract last month's disclosure at connected markets.
    decision = record_event(world, "offer_published", f"Oferta pública: até {surplus} de {name} em {place}.",
                            fact_kind=FactKind.DECISION,
                            decision={"action": "publish_offer", "actor_ref": owner.to_dict(), "resource_id": resource_id,
                                      "stock_id": stock.id, "quantity": surplus, "unit_price": market.prices[resource_id],
                                      "export_rate_permille": export_rate,
                                      "export_policy_event_id": export_policy_event_id,
                                      "export_collector_ref": (export_collector_ref.to_dict()
                                                               if export_collector_ref is not None else None)},
                            cause_ids=_causes(event.id, market.last_event_id, export_policy_event_id))
    for recipient in sorted(recipients, key=lambda r: (r.kind, r.id)):
        if recipient == owner:
            continue
        if recipient.kind == "population_group" and resource_id != "food":
            continue
        if recipient.kind == "population_group":
            group = world.society.population.get(recipient.id)
            targets = [stock.location_id] if (group is not None and group.settlement_id == stock.location_id
                                               and world.society.available_count(group.id) > 0) else []
        else:
            targets = [o.settlement_id for o in world.strategy.objectives.values()
                       if o.actor_ref == recipient and o.resource_id == resource_id]
        if not any(supply_path(world, stock.location_id, target, resource_id) is not None for target in targets):
            continue
        key = f"offer:{recipient.kind}:{recipient.id}:{stock.id}:{resource_id}"
        world.knowledge.reports[key] = report.model_copy(update={
            "id": key, "recipient_ref": recipient, "quantity": surplus,
            "kind": "offer", "channel": "market_bulletin", "event_id": decision.id})

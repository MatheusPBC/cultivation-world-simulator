"""Origin-administered export tariffs over already-consented market sales."""

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity, SocietyValue
from .demand import reserve_quantity
from .economy import _causes, _delta
from .events import record_event


EXPORT_RATE_PERMILLE = 50


class ExportTariffOption(SocietyValue):
    """A current fiscal affordance, derived only from the polity's own records."""

    id: Identity
    polity_id: Identity
    export_rate_permille: int
    account_id: Identity
    inventory_report_id: Identity

    def decision(self):
        return {"action": "set_export_tariff", "actor_ref": EntityRef("polity", self.polity_id).to_dict(),
                "option_id": self.id, "polity_id": self.polity_id,
                "export_rate_permille": self.export_rate_permille}


def _administrator(world, stock_id):
    settlement = world.society.settlements[world.economy.stocks[stock_id].location_id]
    return settlement.administrator_id


def export_quote(world, source_id, destination_id):
    """Current legal quote; no route or transit restriction is implied here."""
    source_admin = _administrator(world, source_id)
    destination_admin = _administrator(world, destination_id)
    if source_admin is None or source_admin == destination_admin:
        return {"export_rate_permille": 0, "export_policy_event_id": None, "export_collector_ref": None}
    policy = world.authority.tax_policies.get(source_admin)
    collector = EntityRef("polity", source_admin)
    if policy is None or policy.account_id not in world.economy.accounts:
        raise ValueError("exporting administration lacks a tax policy")
    return {"export_rate_permille": policy.export_rate_permille,
            "export_policy_event_id": policy.export_policy_event_id,
            "export_collector_ref": collector.to_dict()}


def export_fee(quantity, unit_price, rate):
    """One order has one rounded fee; parcels never round separately."""
    return (quantity * unit_price * rate + 999) // 1000


def tariff_options(world, polity_id):
    """Legal alternatives backed by current own fiscal and reserve readings."""
    policy = world.authority.tax_policies.get(polity_id)
    actor = EntityRef("polity", polity_id)
    if policy is None or not can_actor_act_for(world, actor, actor, "taxation"):
        return ()
    treasury = world.economy.accounts.get(policy.account_id)
    if treasury is None:
        return ()
    reports = [report for report in world.knowledge.for_actor(actor)
               if report.kind == "inventory" and report.observed_day == world.clock.absolute_day
               and world.economy.stocks[report.stock_id].owner_ref == actor]
    if not reports:
        return ()
    report = min(reports, key=lambda item: (item.resource_id, item.stock_id, item.id))
    stock = world.economy.stocks[report.stock_id]
    basis = (f"{policy.export_policy_event_id}:{treasury.last_event_id}:{treasury.balance}:{report.event_id}:{report.quantity}:"
             f"{stock.last_event_ids.get(report.resource_id)}:{reserve_quantity(world, stock.id, report.resource_id)}")
    return tuple(ExportTariffOption(id=f"export-tariff:{polity_id}:{rate}:{basis}", polity_id=polity_id,
                                    export_rate_permille=rate, account_id=policy.account_id,
                                    inventory_report_id=report.id)
                 for rate in (0, EXPORT_RATE_PERMILLE) if rate != policy.export_rate_permille)


def _latest_own_payroll(world, policy):
    payrolls = [payroll for facility_id, payroll in world.economy.payrolls.items()
                if (facility := world.economy.facilities.get(facility_id)) is not None
                and facility.payroll_account_id == policy.account_id and payroll.gross > 0]
    return max(payrolls, key=lambda item: (item.day, item.id)) if payrolls else None


def _foreign_delivery_plan(world, actor):
    for plan in sorted(world.strategy.plans.values(), key=lambda item: item.id):
        objective = world.strategy.objectives.get(plan.objective_id)
        if objective is None or objective.actor_ref != actor or plan.stage not in {"acquire", "await_delivery"}:
            continue
        if any((order := world.economy.freight_orders.get(order_id)) is not None
               and order.delivered_quantity < order.quantity
               and world.economy.stocks[order.source_id].owner_ref != actor for order_id in plan.order_ids):
            return plan
    return None


def set_export_tariff(world, option_id, *, decision_event_id):
    """Apply an exact, current fiscal decision without moving any money itself."""
    decision = next((event for event in world.events if event.id == decision_event_id), None)
    polity_id = (decision.decision or {}).get("polity_id") if decision is not None else None
    option = next((item for item in tariff_options(world, polity_id) if item.id == option_id), None)
    if (decision is None or decision.day != world.clock.absolute_day or decision.fact_kind != FactKind.DECISION or option is None
            or decision.decision != option.decision()):
        raise ValueError("export tariff option is stale")
    if any(event.event_type == "export_tariff_changed" and any(link.cause_event_id == decision.id
           for link in event.causal_links) for event in world.events):
        raise ValueError("export tariff decision already executed")
    actor = EntityRef("polity", option.polity_id)
    require_authority(world, actor, "taxation")
    policy = world.authority.tax_policies[option.polity_id]
    treasury = world.economy.accounts[policy.account_id]
    report = world.knowledge.reports.get(option.inventory_report_id)
    if report is None:
        raise ValueError("export tariff material reading changed")
    event = record_event(world, "export_tariff_changed",
                         f"Tarifa de exportação alterada para {option.export_rate_permille}/1000.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("tax_policy", policy.id, "export_rate_permille",
                                        policy.export_rate_permille, option.export_rate_permille),),
                         cause_ids=_causes(decision.id, policy.export_policy_event_id, policy.last_event_id, treasury.last_event_id,
                                           report.event_id))
    world.authority.tax_policies[policy.id] = policy.model_copy(
        update={"export_rate_permille": option.export_rate_permille,
                "export_policy_event_id": event.id, "last_event_id": event.id})
    return event


def review_export_tariffs(world):
    """A conservative engine policy may select, but never invent, an option."""
    changed = False
    for polity_id in sorted(world.authority.tax_policies):
        options = tariff_options(world, polity_id)
        if not options:
            continue
        policy = world.authority.tax_policies[polity_id]
        treasury = world.economy.accounts[policy.account_id]
        actor = EntityRef("polity", polity_id)
        payroll = _latest_own_payroll(world, policy)
        dependency = _foreign_delivery_plan(world, actor)
        report = world.knowledge.reports[options[0].inventory_report_id]
        surplus = report.quantity > reserve_quantity(world, report.stock_id, report.resource_id)
        target = (EXPORT_RATE_PERMILLE if policy.export_rate_permille == 0 and payroll is not None
                  and treasury.balance < payroll.gross and surplus and dependency is None else
                  0 if policy.export_rate_permille == EXPORT_RATE_PERMILLE and
                  (dependency is not None or (payroll is not None and treasury.balance >= payroll.gross)) else None)
        option = next((item for item in options if item.export_rate_permille == target), None)
        if option is None:
            continue
        event = record_event(world, "export_tariff_decided",
                             ("A administração protege a próxima folha com receita de exportação."
                              if target else "A administração reduz a tarifa diante da dependência comercial ou da caixa recomposta."),
                             fact_kind=FactKind.DECISION, decision=option.decision(),
                             cause_ids=_causes(payroll.last_event_id if payroll else None,
                                               world.knowledge.reports[option.inventory_report_id].event_id,
                                               world.economy.accounts[option.account_id].last_event_id,
                                               dependency.last_event_id if dependency else None))
        set_export_tariff(world, option.id, decision_event_id=event.id)
        changed = True
    return changed

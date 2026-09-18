"""Public food relief is an act the stock owner chooses, never a standing rate.

A polity that owns a settlement's public granary may give some of it away for
free, but only by an explicit, dated decision: how much to move is bounded by
what that same polity's own current report says the settlement still lacks,
and by what physically sits in the granary today. Nothing here creates food,
and nothing here repeats itself: a stale, invented or already-executed option
never moves anything.
"""

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Count, Identity, SocietyValue
from .economy import _apply_stock, _causes, _delta
from .events import record_event

# Fractions of the observed shortfall the owner may choose to cover. The
# actor picks *how much*, not only whether to act at all.
COVERAGE_FRACTIONS = (1, 2)


class ReliefDistributionOption(SocietyValue):
    """A current affordance to give away some of the granary's own owner's food.

    The actor is the stock's owner, never the settlement's administrator: it
    is whoever holds the food that gives up the revenue it could have sold
    it for. The quantity is bounded by that owner's own dated reading of the
    settlement and by what the granary physically holds right now.
    """

    id: Identity
    polity_id: Identity
    settlement_id: Identity
    stock_id: Identity
    quantity: Count
    report_id: Identity

    def decision(self):
        return {"action": "distribute_relief", "actor_ref": EntityRef("polity", self.polity_id).to_dict(),
                "option_id": self.id, "polity_id": self.polity_id, "settlement_id": self.settlement_id,
                "quantity": self.quantity}


def relief_settlement_options(world, polity_id, *, settlement_id=None):
    """Legal relief affordances backed by the owner's own current settlement report."""
    actor = EntityRef("polity", polity_id)
    if not can_actor_act_for(world, actor, actor, "supply"):
        return ()
    day = world.clock.absolute_day
    options = []
    for need_id in sorted(world.economy.needs):
        if settlement_id is not None and need_id != settlement_id:
            continue
        need = world.economy.needs[need_id]
        stock = world.economy.stocks[need.stock_id]
        if stock.owner_ref != actor:
            continue
        report = world.knowledge.settlement_report(actor, need_id)
        if (report is None or report.publisher_ref != actor or report.observed_day != day
                or report.missing_food <= 0):
            continue
        available = stock.goods.get("food", 0)
        if available <= 0:
            continue
        basis = f"{report.event_id}:{stock.last_event_ids.get('food')}"
        quantities = sorted({q for q in (min(report.missing_food // fraction, available)
                                         for fraction in COVERAGE_FRACTIONS) if q > 0}, reverse=True)
        for quantity in quantities:
            option_id = f"relief-distribute:{polity_id}:{need_id}:{quantity}:{basis}"
            options.append(ReliefDistributionOption(id=option_id, polity_id=polity_id, settlement_id=need_id,
                                                     stock_id=stock.id, quantity=quantity, report_id=report.id))
    return tuple(options)


def distribute_relief(world, option_id, *, decision_event_id):
    """Move real food out of the granary once, on an exact, current decision."""
    decision = next((event for event in world.events if event.id == decision_event_id), None)
    polity_id = (decision.decision or {}).get("polity_id") if decision is not None else None
    settlement_id = (decision.decision or {}).get("settlement_id") if decision is not None else None
    option = next((item for item in relief_settlement_options(world, polity_id, settlement_id=settlement_id)
                   if item.id == option_id), None)
    if (decision is None or decision.day != world.clock.absolute_day or decision.fact_kind != FactKind.DECISION
            or option is None or decision.decision != option.decision()):
        raise ValueError("relief distribution option is stale")
    if any(event.event_type == "relief_distributed" and any(link.cause_event_id == decision.id
           for link in event.causal_links) for event in world.events):
        raise ValueError("relief distribution decision already executed")
    actor = EntityRef("polity", option.polity_id)
    require_authority(world, actor, "supply")
    stock = world.economy.stocks[option.stock_id]
    need = world.economy.needs[option.settlement_id]
    report = world.knowledge.settlement_reports.get(option.report_id)
    if report is None:
        raise ValueError("relief material reading changed")
    quantity = option.quantity
    if quantity <= 0 or quantity > stock.goods.get("food", 0):
        raise ValueError("relief distribution exceeds the granary's real stock")
    updated_missing = max(0, need.missing_food - quantity)
    settlement = world.society.settlements[option.settlement_id]
    event = _apply_stock(
        world, stock, {**stock.goods, "food": stock.goods.get("food", 0) - quantity},
        "relief_distributed",
        f"{settlement.name}: {quantity} rações de ajuda distribuídas pela administração; déficit restante de {updated_missing}.",
        extra_deltas=(_delta("subsistence", need.id, "missing_food", need.missing_food, updated_missing),),
        cause_ids=_causes(decision.id, report.event_id, need.last_event_id),
    )
    world.economy.needs[need.id] = need.model_copy(update={"missing_food": updated_missing, "last_event_id": event.id})
    return event

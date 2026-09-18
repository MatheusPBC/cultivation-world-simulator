"""Shared test helper for the relief act (see docs/handoff/plano-consequencia-causal.md).

Since automatic public relief no longer exists, fixtures that used to rely on
every unpaid ration being covered for free must instead execute the real act:
a fresh own settlement report, then a dated decision, then ``distribute_relief``.
Nothing here bypasses validation or invents a shortcut -- it is exactly what a
provider-driven institutional turn would do, wired up directly so tests do not
need a mock AI provider just to make the granary give its own food away.
"""

from src.classes.event import FactKind
from src.sim.medieval.events import record_event
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.relief import distribute_relief, relief_settlement_options


def relieve_settlement(world, settlement_id, *, full=True):
    """Execute one real relief act covering as much of today's own reported
    shortfall as the granary currently holds (``full``) or half of it.

    Returns the resulting event, or ``None`` when there is nothing to relieve
    (no shortfall, no authority, or the settlement is not the stock owner's
    own to give away).
    """
    refresh_reports(world)
    need = world.economy.needs[settlement_id]
    owner = world.economy.stocks[need.stock_id].owner_ref
    options = [option for option in relief_settlement_options(world, owner.id)
               if option.settlement_id == settlement_id]
    if not options:
        return None
    option = max(options, key=lambda item: item.quantity) if full else min(options, key=lambda item: item.quantity)
    report = world.knowledge.settlement_reports[option.report_id]
    decision = record_event(
        world, "relief_distribution_decided", "Decisão de teste: distribuir ajuda alimentar do próprio celeiro.",
        fact_kind=FactKind.DECISION, decision=option.decision(), cause_ids=(report.event_id,))
    return distribute_relief(world, option.id, decision_event_id=decision.id)


def relieve_all_settlements(world, *, full=True):
    """Relieve every settlement whose own stock owner can currently do so."""
    events = []
    for settlement_id in sorted(world.economy.needs):
        event = relieve_settlement(world, settlement_id, full=full)
        if event is not None:
            events.append(event)
    return events

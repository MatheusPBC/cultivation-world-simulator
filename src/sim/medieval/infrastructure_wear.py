"""Deterministic operating wear for the Map-owned physical sites.

This is intentionally narrower than weather or hazards.  A site only loses
integrity after a real receipt proves that it carried enough work in the
completed month: productive batches at that exact site, or cargo departures
over a route that explicitly depends on it.  Economy records the receipts;
the Map remains the only owner of the resulting physical condition.

There is no maintenance fund, random draw, automatic repair, route rewrite,
or cargo mutation here.  One small state transition per site per monthly
boundary is enough for an owner to observe the new condition and choose the
already-existing repair affordance on a later material step.
"""

from __future__ import annotations

from collections import defaultdict

from src.classes.event import FactKind

from .economy import _causes, _delta
from .events import record_event


# These are engine laws, deliberately modest and inspectable rather than an
# actor- or LLM-authored maintenance budget.  Activity is aggregated over the
# just-finished 30-day calendar month; a site can wear at most once in it.
WEAR_WINDOW_DAYS = 30
MIN_PRODUCTIVE_BATCHES_PER_MONTH = 10
MIN_ROUTE_BULK_PER_MONTH = 100
MAX_MONTHLY_INTEGRITY_LOSS = 0.01


def _event_by_id(world, event_id):
    if not isinstance(event_id, str) or not event_id.startswith("event:"):
        return None
    _, _, suffix = event_id.partition(":")
    if not suffix.isdecimal():
        return None
    index = int(suffix) - 1
    if not 0 <= index < len(world.events):
        return None
    event = world.events[index]
    return event if event.id == event_id else None


def _month_start(day: int) -> int:
    """Inclusive first day of the completed calendar month ending at ``day``."""
    return day - WEAR_WINDOW_DAYS + 1


def _production_receipts(world, start_day: int, day: int):
    """Return verified current-cycle batches and receipts grouped by site.

    A facility's current receipt is canonical: ``produce_monthly`` replaces
    its ``last_event_id`` every month.  Rechecking its fact kind, type, date
    and identity prevents an arbitrary field assignment from becoming wear.
    """
    result = defaultdict(lambda: [0, set()])
    for facility in sorted(world.economy.facilities.values(), key=lambda value: value.id):
        event = _event_by_id(world, facility.last_event_id)
        if (
            event is None
            or event.fact_kind != FactKind.STATE_TRANSITION
            or event.event_type not in {"production_completed", "production_limited"}
            or not start_day <= event.day <= day
            or facility.last_batches <= 0
        ):
            continue
        # Production values are Map-bound through the facility's declared site;
        # a receipt is not inferred from a stock movement or prose.
        if facility.site_id not in world.map.infrastructure_sites:
            continue
        result[facility.site_id][0] += facility.last_batches
        result[facility.site_id][1].add(event.id)
    return result


def _departure_bulk(event, route_id: str) -> int:
    """Read one cargo departure's actual bulk from its canonical flow delta.

    ``RouteFlow.bulk`` is cumulative only within a day.  On a new day the
    before value belongs to the prior daily flow, so the after value is the
    departure; otherwise the difference is the departure.  Requiring the
    companion day delta makes this a receipt, not a similarly named event.
    """
    day_delta = next((delta for delta in event.deltas
                      if delta.owner_kind == "route_flow" and delta.owner_id == route_id
                      and delta.aspect == "day"), None)
    bulk_delta = next((delta for delta in event.deltas
                       if delta.owner_kind == "route_flow" and delta.owner_id == route_id
                       and delta.aspect == "bulk"), None)
    if day_delta is None or bulk_delta is None:
        return 0
    try:
        before_day = None if day_delta.before == "None" else int(day_delta.before)
        after_day = int(day_delta.after)
        before_bulk = int(bulk_delta.before)
        after_bulk = int(bulk_delta.after)
    except (TypeError, ValueError):
        return 0
    if after_day != event.day or after_bulk <= 0:
        return 0
    return after_bulk if before_day != after_day else max(0, after_bulk - before_bulk)


def _route_departure_receipts(world, start_day: int, day: int):
    """Return verified cargo bulk and receipts grouped by immutable route ID."""
    result = defaultdict(lambda: [0, set()])
    for event in world.events:
        if (
            event.fact_kind != FactKind.STATE_TRANSITION
            or event.event_type != "cargo_departed"
            or not start_day <= event.day <= day
        ):
            continue
        route_ids = {delta.owner_id for delta in event.deltas
                     if delta.owner_kind == "route_flow" and delta.aspect == "bulk"}
        for route_id in sorted(route_ids):
            bulk = _departure_bulk(event, route_id)
            if bulk:
                result[route_id][0] += bulk
                result[route_id][1].add(event.id)
    return result


def _already_worn(world, site_id: str, day: int) -> bool:
    """Persisted events are the idempotence guard; no duplicate runtime state."""
    return any(
        event.day == day
        and event.event_type == "site_worn"
        and any(delta.owner_kind == "site" and delta.owner_id == site_id
                and delta.aspect == "integrity" for delta in event.deltas)
        for event in world.events
    )


def apply_monthly_infrastructure_wear(world) -> tuple[str, ...]:
    """Apply one bounded, evidence-linked operating loss per active site.

    The caller must invoke this on a monthly boundary.  The function itself is
    deterministic and repeat-safe for a persisted world, which also makes the
    engine candidate rollback restore both the condition and the guard.
    """
    day = world.clock.absolute_day
    if day <= 0 or day % WEAR_WINDOW_DAYS:
        return ()
    start_day = _month_start(day)
    productive = _production_receipts(world, start_day, day)
    departures = _route_departure_receipts(world, start_day, day)
    worn: list[str] = []

    for site in sorted(world.map.infrastructure_sites.values(), key=lambda value: value.id):
        if site.integrity <= 0.0 or _already_worn(world, site.id, day):
            continue
        production_batches, production_causes = productive.get(site.id, (0, set()))
        route_bulk = 0
        route_causes: set[str] = set()
        for route_id in site.route_ids:
            bulk, causes = departures.get(route_id, (0, set()))
            route_bulk += bulk
            route_causes.update(causes)
        if (production_batches < MIN_PRODUCTIVE_BATCHES_PER_MONTH
                and route_bulk < MIN_ROUTE_BULK_PER_MONTH):
            continue
        before = float(site.integrity)
        after = max(0.0, before - MAX_MONTHLY_INTEGRITY_LOSS)
        if after >= before:  # defensive: the constants must never heal a site.
            continue
        evidence = _causes(*sorted(production_causes), *sorted(route_causes), site.last_event_id)
        event = record_event(
            world,
            "site_worn",
            f"{site.name}: uso material reduziu a integridade para {round(after * 100)}%.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("site", site.id, "integrity", before, after),),
            cause_ids=evidence,
        )
        world.map.update_infrastructure_site_runtime(site.id, integrity=after, last_event_id=event.id)
        worn.append(site.id)
    return tuple(worn)


__all__ = [
    "MAX_MONTHLY_INTEGRITY_LOSS",
    "MIN_PRODUCTIVE_BATCHES_PER_MONTH",
    "MIN_ROUTE_BULK_PER_MONTH",
    "WEAR_WINDOW_DAYS",
    "apply_monthly_infrastructure_wear",
]

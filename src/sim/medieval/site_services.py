"""Owner-controlled service at physical ports and mountain passages.

This is not a blockade: it never changes a route, seizes cargo, or creates a
guard force.  The Map keeps the physical asset and derives the route bottleneck
from the owner's current service choice.
"""

from typing import Literal

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity, SocietyValue

from .economy import _causes, _delta
from .events import record_event
from .infrastructure import current_observation


SERVICE_SITE_KINDS = frozenset({"port", "mountain_pass"})
SUSPEND_THRESHOLD = 0.35
RESUME_THRESHOLD = 0.70


class SiteServiceOption(SocietyValue):
    """One current owner affordance; the executor recomputes it verbatim."""

    id: Identity
    site_id: Identity
    actor_ref: EntityRef
    action: Literal["suspend_site_service", "resume_site_service"]
    report_id: Identity

    def decision(self) -> dict:
        return {"action": self.action, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _present_at_site(world, actor_ref, site) -> bool:
    """Local presence is a settlement administration or the owner's own stock."""
    for settlement in world.society.settlements.values():
        if settlement.region_id not in site.region_ids:
            continue
        if actor_ref.kind == "polity" and settlement.administrator_id == actor_ref.id:
            return True
        if any(stock.owner_ref == actor_ref and stock.location_id == settlement.id
               for stock in world.economy.stocks.values()):
            return True
    return False


def _option_id(site, actor_ref, report, action: str) -> str:
    """Tie an affordance to the reported reading and the current material state."""
    return (f"site-service:{action}:{site.id}:{actor_ref.kind}:{actor_ref.id}:"
            f"{report.id}:{report.event_id}:{site.last_event_id}:"
            f"{site.integrity:g}:{int(site.enabled)}:{int(site.service_suspended)}")


def _current_reading(report, site) -> bool:
    """An observation may be historically valid but no longer authorize action."""
    return (report.integrity == site.integrity and report.enabled == site.enabled
            and report.service_suspended == site.service_suspended)


def service_options(world, site_id, actor_ref):
    """Return the sole legal next state for a present, supply-authorized owner."""
    if not isinstance(actor_ref, EntityRef):
        return ()
    site = world.map.infrastructure_sites.get(site_id)
    if (site is None or site.kind not in SERVICE_SITE_KINDS or site.owner_ref != actor_ref
            or not can_actor_act_for(world, actor_ref, actor_ref, "supply")
            or not _present_at_site(world, actor_ref, site)):
        return ()
    report = current_observation(world, actor_ref, site_id)
    if report is None or not _current_reading(report, site):
        return ()
    action = "resume_site_service" if site.service_suspended else "suspend_site_service"
    return (SiteServiceOption(id=_option_id(site, actor_ref, report, action), site_id=site.id,
                              actor_ref=actor_ref, action=action, report_id=report.id),)


def _decision(world, decision_event_id):
    return next((event for event in world.events if event.id == decision_event_id), None)


def set_site_service(world, option_id, *, decision_event_id):
    """Apply one exact current owner decision without repairing or enabling a site."""
    decision = _decision(world, decision_event_id)
    payload = decision.decision if decision is not None else None
    try:
        actor_ref = EntityRef.from_dict(payload.get("actor_ref")) if isinstance(payload, dict) else None
    except (KeyError, TypeError, ValueError):
        actor_ref = None
    options = tuple(option for site in world.map.infrastructure_sites.values()
                    for option in service_options(world, site.id, actor_ref)) if actor_ref is not None else ()
    option = next((item for item in options if item.id == option_id), None)
    if (decision is None or decision.day != world.clock.absolute_day
            or decision.fact_kind != FactKind.DECISION or option is None
            or decision.decision != option.decision()):
        raise ValueError("site service option is stale")
    if any(event.event_type in {"site_service_suspended", "site_service_resumed"}
           and any(link.cause_event_id == decision.id for link in event.causal_links)
           for event in world.events):
        raise ValueError("site service decision already executed")

    site = world.map.infrastructure_sites[option.site_id]
    require_authority(world, option.actor_ref, "supply")
    if site.owner_ref != option.actor_ref or not _present_at_site(world, option.actor_ref, site):
        raise ValueError("site service requires its present owner")
    report = current_observation(world, option.actor_ref, option.site_id)
    if report is None or report.id != option.report_id or not _current_reading(report, site):
        raise ValueError("site service requires the owner's current observation")

    target = option.action == "suspend_site_service"
    event = record_event(
        world,
        "site_service_suspended" if target else "site_service_resumed",
        (f"{site.name}: o proprietário suspendeu o serviço próprio."
         if target else f"{site.name}: o proprietário retomou o serviço próprio."),
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("site", site.id, "service_suspended", site.service_suspended, target),),
        cause_ids=_causes(decision.id, report.event_id, site.last_event_id),
    )
    world.map.update_infrastructure_site_runtime(
        site.id, service_suspended=target, last_event_id=event.id,
    )
    return event


def review_site_services(world, *, excluded_actors=()) -> tuple[str, ...]:
    """Conservative owner policy for actors without a completed provider turn."""
    excluded = set(excluded_actors)
    changed: list[str] = []
    for site in sorted(world.map.infrastructure_sites.values(), key=lambda item: item.id):
        owner = site.owner_ref
        if owner is None or owner in excluded:
            continue
        options = service_options(world, site.id, owner)
        if not options:
            continue
        option = options[0]
        report = current_observation(world, owner, site.id)
        target = (
            option.action == "suspend_site_service" and report.integrity < SUSPEND_THRESHOLD
        ) or (
            option.action == "resume_site_service" and report.integrity >= RESUME_THRESHOLD
            and site.enabled
        )
        if not target:
            continue
        decision = record_event(
            world,
            "site_service_decided",
            (f"{site.name}: suspender serviço diante da integridade observada."
             if option.action == "suspend_site_service"
             else f"{site.name}: retomar serviço após recuperação observada."),
            fact_kind=FactKind.DECISION,
            decision=option.decision(),
            cause_ids=_causes(report.event_id, site.last_event_id),
        )
        set_site_service(world, option.id, decision_event_id=decision.id)
        changed.append(site.id)
    return tuple(changed)


def service_adapters():
    from .institutional_decision_turn import DiscretionaryAdapter

    def options(world, actor):
        if not isinstance(actor, EntityRef):
            return ()
        return tuple(option for site in world.map.infrastructure_sites.values()
                     for option in service_options(world, site.id, actor))

    def causes(world, option):
        report = current_observation(world, option.actor_ref, option.site_id)
        return (report.event_id,) if report is not None else ()

    def execute(world, actor, option_id, decision_event_id):
        return set_site_service(world, option_id, decision_event_id=decision_event_id)

    return (DiscretionaryAdapter(
        name="site_service", family="infrastructure", options_fn=options,
        label_fn=lambda option: ("Suspender" if option.action == "suspend_site_service" else "Retomar")
        + f" o serviço de {option.site_id}.",
        causes_fn=causes, execute_fn=execute),)


__all__ = ["RESUME_THRESHOLD", "SERVICE_SITE_KINDS", "SUSPEND_THRESHOLD",
           "SiteServiceOption", "review_site_services", "service_options", "service_adapters",
           "set_site_service"]

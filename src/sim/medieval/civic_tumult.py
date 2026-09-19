"""One bounded material rung between civic protest and organized rebellion.

A tumult is an actor decision by a local population group, not a random
incident. It requires a current local report, a recent refused civic demand
and a local site the group actually observed. Society owns the decision
receipt; Map owns the integrity change. There is no leader, faction or
automatic escalation to rebellion.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .civic_protest import _event, _own_report
from .economy import _causes, _delta
from .events import record_event

TUMULT_ACTION = "join_civic_tumult"
TUMULT_DAMAGE = 0.08
TUMULT_MIN_UNREST = 500
TUMULT_MAX_REFUSAL_AGE = 30


@dataclass(frozen=True)
class CivicTumultOption:
    id: Identity
    group_id: Identity
    settlement_id: Identity
    site_id: Identity
    site_integrity_before: float
    report_event_id: Identity
    site_report_event_id: Identity
    refusal_event_id: Identity

    def decision(self):
        return {"action": TUMULT_ACTION,
                "actor_ref": EntityRef("population_group", self.group_id).to_dict(),
                "selected_affordance_id": self.id}


def _recent_refusal(world, group_id, settlement_id):
    candidates = []
    for protest in world.society.civic_protests.values():
        if protest.group_id != group_id or protest.settlement_id != settlement_id or protest.stage != "refused":
            continue
        event = _event(world, protest.last_event_id)
        if event is None or event.event_type != "civic_protest_refused":
            continue
        if world.clock.absolute_day - event.day > TUMULT_MAX_REFUSAL_AGE:
            continue
        candidates.append(event)
    return max(candidates, key=lambda event: (event.day, event.id), default=None)


def _used(world, refusal_event_id, site_id=None):
    for event in world.events:
        if event.event_type != "civic_tumult_occurred":
            continue
        causes = {link.cause_event_id for link in event.causal_links}
        sites = {delta.owner_id for delta in event.deltas if delta.owner_kind == "site"}
        if refusal_event_id in causes and (site_id is None or site_id in sites):
            return True
    return False


def civic_tumult_options(world, group_id):
    current = _own_report(world, group_id)
    if current is None:
        return ()
    group, report = current
    if report.unrest < TUMULT_MIN_UNREST or world.society.available_count(group.id) <= 0:
        return ()
    refusal = _recent_refusal(world, group.id, group.settlement_id)
    if refusal is None:
        return ()
    actor = EntityRef("population_group", group.id)
    settlement = world.society.settlements[group.settlement_id]
    options = []
    for site_report in sorted(world.knowledge.site_reports.values(), key=lambda item: item.id):
        site = world.map.infrastructure_sites.get(site_report.site_id)
        if (site_report.recipient_ref != actor or site_report.publisher_ref != actor
                or site_report.observed_day != world.clock.absolute_day or site is None
                or site_report.integrity <= 0.0 or settlement.region_id not in site.region_ids
                or _used(world, refusal.id)):
            continue
        options.append(CivicTumultOption(
            id=f"civic-tumult:{group.id}:{refusal.id}:{site.id}:{site_report.event_id}",
            group_id=group.id, settlement_id=group.settlement_id, site_id=site.id,
            site_integrity_before=site_report.integrity, report_event_id=report.event_id,
            site_report_event_id=site_report.event_id, refusal_event_id=refusal.id))
    return tuple(sorted(options, key=lambda item: item.id))


def _decision(world, decision_event_id):
    decision = _event(world, decision_event_id)
    if (decision is None or decision.fact_kind != FactKind.DECISION or decision.day != world.clock.absolute_day
            or decision.decision is None or decision.decision.get("action") != TUMULT_ACTION
            or set(decision.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("civic tumult requires a current actor decision")
    return decision, EntityRef.from_dict(decision.decision["actor_ref"])


def execute_civic_tumult(world, group_id, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in civic_tumult_options(candidate, group_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("civic tumult option is stale or unknown")
    decision, actor = _decision(candidate, decision_event_id)
    if actor != EntityRef("population_group", group_id) or decision.decision != option.decision():
        raise ValueError("civic tumult has the wrong decision")
    site = candidate.map.infrastructure_sites.get(option.site_id)
    if site is None or site.integrity <= 0.0:
        raise ValueError("civic tumult site is no longer current")
    before = site.integrity
    after = max(0.0, before - TUMULT_DAMAGE)
    event = record_event(
        candidate, "civic_tumult_occurred",
        "Um tumulto cívico danificou uma instalação local observada pelo grupo.",
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        deltas=(_delta("site", site.id, "integrity", before, after),),
        cause_ids=_causes(decision.id, option.report_event_id, option.site_report_event_id,
                          option.refusal_event_id, site.last_event_id))
    candidate.map.update_infrastructure_site_runtime(site.id, integrity=after, last_event_id=event.id)
    from .route_intelligence import refresh_site_reports
    refresh_site_reports(candidate, site_ids=(site.id,))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return event


__all__ = ["CivicTumultOption", "TUMULT_ACTION", "civic_tumult_options", "execute_civic_tumult"]

"""Copying a technique from works one already reaches, as paid dated labour.

This is not espionage: there is no agent, no document, no secret and no roll.
The only capability admitted is the one the sabotage vertical already
validates as *work presence* — the actor pays people who work at that exact
site today. Armed presence is deliberately excluded: a column standing in a
town does not read a workshop's method, and allowing it would turn conquest
into technology transfer.

The holder loses nothing. Knowledge is not rival, so there is no theft of
inventory here and no notice to the victim: it may only learn later, if and
when the copier runs a line that requires the technique.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.research.models import TechniqueCopy
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _causes, _delta, monthly_workforce
from .events import record_event
from .labor import settle_work
from .research import learn_technology
from .sabotage import _work_presence

COPY_ACTION = "copy_technique"
COPY_DAYS = 30
COPY_WORKERS = 1
COPY_WAGE = 2
REPORT_MAX_AGE = 30


@dataclass(frozen=True)
class TechniqueCopyOption:
    """Transient option; the decider only ever selects this ID."""
    id: Identity
    actor_ref: EntityRef
    holder_ref: EntityRef
    technology_id: Identity
    site_id: Identity
    stock_id: Identity
    account_id: Identity
    sighting_event_id: Identity
    report_event_id: Identity
    access_kind: str
    access_id: Identity
    access_event_id: Identity

    def decision(self):
        return {"action": COPY_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _running_line(world, site_id, technology_id, holder_ref=None):
    """A facility at this site whose active recipe requires the technique."""
    site = world.map.infrastructure_sites.get(site_id)
    if site is None or not site.enabled or site.integrity <= 0 or site.service_suspended:
        return None
    return next((facility for _, facility in sorted(world.economy.facilities.items())
                 if facility.site_id == site_id
                 and (holder_ref is None
                      or world.economy.stocks[facility.stock_id].owner_ref == holder_ref)
                 and world.economy.recipes[facility.recipe_id].required_technology_id == technology_id), None)


def _current_site_report(world, actor, site_id):
    report = world.knowledge.site_report(actor, site_id)
    day = world.clock.absolute_day
    if report is None or report.site_id != site_id or not 0 <= day - report.observed_day < REPORT_MAX_AGE:
        return None
    return report


def _own_holdings(world, actor, settlement_id):
    stock = next((item for _, item in sorted(world.economy.stocks.items())
                  if item.owner_ref == actor and item.location_id == settlement_id), None)
    account = next((item for _, item in sorted(world.economy.accounts.items())
                    if item.owner_ref == actor), None)
    return stock, account


def _work_access(world, actor, site):
    """A durable local-work record, plus the factual receipt that proved it.

    A standalone payroll is deliberately insufficient after its day closes:
    the calendar resolves dated obligations before the next monthly payroll.
    Repairs and apprenticeships already model continuing, revalidatable work
    at a named site, so they are the narrow V1 access channels.
    """
    # Do not infer access from force, office, control, or a sighting.  The
    # sabotage helper is intentionally narrow and admits only actual work.
    if not _work_presence(world, actor, site):
        return None
    day = world.clock.absolute_day
    for repair in sorted(world.economy.repairs.values(), key=lambda item: item.id):
        payroll = world.economy.payrolls.get(repair.id)
        if (repair.site_id == site.id and repair.maintainer_ref == actor
                and repair.stage == "repairing" and repair.last_work_day == day
                and payroll is not None and payroll.day == day):
            return "repair", repair.id, payroll.last_event_id
    for contract in sorted(world.research.apprenticeships.values(), key=lambda item: item.id):
        if (contract.site_id == site.id and contract.host_ref == actor
                and contract.stage == "training"):
            return "apprenticeship", contract.id, contract.last_event_id
    return None


def _access_intact(world, copy_record):
    site = world.map.infrastructure_sites.get(copy_record.site_id)
    if copy_record.access_kind == "repair":
        repair = world.economy.repairs.get(copy_record.access_id)
        if (site is not None and site.maintainer_ref == copy_record.actor_ref
                and repair is not None and repair.site_id == copy_record.site_id
                and repair.maintainer_ref == copy_record.actor_ref
                and repair.stage == "repairing"
                # A monthly payroll is evidence of work through exactly this
                # copy window.  Dated conclusions run before the next monthly
                # batch, so requiring a second same-day payroll would make a
                # valid month of paid access impossible to conclude.
                and repair.last_work_day == copy_record.started_day
                and all(can_actor_act_for(world, copy_record.actor_ref, copy_record.actor_ref, scope)
                        for scope in ("supply", "trade"))):
            return True
    elif copy_record.access_kind == "apprenticeship":
        contract = world.research.apprenticeships.get(copy_record.access_id)
        if (site is not None and contract is not None and contract.site_id == copy_record.site_id
                and contract.host_ref == copy_record.actor_ref
                and contract.stage == "training"):
            return True
    return False


def _payroll_blocker(world, actor, site, stock_id, account_id, available):
    """Preflight the entire bounded copy wage before a dated fact is emitted."""
    stock = world.economy.stocks.get(stock_id)
    account = world.economy.accounts.get(account_id)
    settlement = world.society.settlements.get(stock.location_id) if stock is not None else None
    if (stock is None or account is None or stock.owner_ref != actor or account.owner_ref != actor
            or settlement is None or settlement.region_id not in site.region_ids):
        return "payroll_source"
    if account.balance < COPY_WORKERS * COPY_WAGE:
        return "payroll_funds"
    artisans = sum(available.get(group.id, 0) for group in world.society.population.values()
                   if group.settlement_id == stock.location_id and group.occupation == "artisan")
    return None if artisans >= COPY_WORKERS else "labor"


def _prepared(world, copy_record, available):
    """Every condition that must hold for the whole term, checked afresh."""
    actor, technology_id = copy_record.actor_ref, copy_record.technology_id
    day = world.clock.absolute_day
    if world.knowledge.knows(actor, technology_id):
        return "already_known"
    if not can_actor_act_for(world, actor, actor, "research"):
        return "authority"
    if not world.knowledge.has_current_technology_sighting(actor, copy_record.holder_ref, technology_id, day):
        return "evidence_lost"
    site = world.map.infrastructure_sites.get(copy_record.site_id)
    if site is None or _running_line(world, copy_record.site_id, technology_id, copy_record.holder_ref) is None:
        return "works_stopped"
    if not _access_intact(world, copy_record):
        return "access_lost"
    technology = world.research.technologies[technology_id]
    if any(not world.knowledge.knows(actor, prerequisite) for prerequisite in technology.prerequisites):
        return "qualification"
    return _payroll_blocker(world, actor, site, copy_record.stock_id, copy_record.account_id, available)


def technique_copy_options(world, actor):
    """Only sighted techniques, running works and the actor's own access."""
    if not isinstance(actor, EntityRef) or not can_actor_act_for(world, actor, actor, "research"):
        return ()
    day = world.clock.absolute_day
    available = monthly_workforce(world)
    options = []
    for sighting in world.knowledge.technology_sightings_for_actor(actor, current_day=day):
        technology = world.research.technologies.get(sighting.technology_id)
        if (technology is None or world.knowledge.knows(actor, sighting.technology_id)
                or any(not world.knowledge.knows(actor, item) for item in technology.prerequisites)):
            continue
        if any(item.stage == "copying" and item.actor_ref == actor
               and item.technology_id == sighting.technology_id for item in world.research.technique_copies.values()):
            continue
        for site_id, site in sorted(world.map.infrastructure_sites.items()):
            if _running_line(world, site_id, sighting.technology_id, sighting.holder_ref) is None:
                continue
            report = _current_site_report(world, actor, site_id)
            access = _work_access(world, actor, site)
            if report is None or access is None:
                continue
            settlement = next((item for _, item in sorted(world.society.settlements.items())
                               if item.region_id in site.region_ids), None)
            stock, account = _own_holdings(world, actor, settlement.id) if settlement else (None, None)
            if stock is None or account is None:
                continue
            if _payroll_blocker(world, actor, site, stock.id, account.id, available) is not None:
                continue
            access_kind, access_id, access_event_id = access
            options.append(TechniqueCopyOption(
                id=(f"technique-copy:{actor.kind}:{actor.id}:{sighting.technology_id}:{site_id}:"
                    f"{sighting.event_id}:{report.event_id}:{access_kind}:{access_id}:{access_event_id}"),
                actor_ref=actor, holder_ref=sighting.holder_ref, technology_id=sighting.technology_id,
                site_id=site_id, stock_id=stock.id, account_id=account.id,
                sighting_event_id=sighting.event_id, report_event_id=report.event_id,
                access_kind=access_kind, access_id=access_id, access_event_id=access_event_id))
    return tuple(options)


def _decision(world, decision_event_id):
    event = next((item for item in world.events if item.id == decision_event_id), None)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision is None or event.decision.get("action") != COPY_ACTION
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("technique copy requires a current actor decision")
    return event


def open_technique_copy(world, actor, option_id, decision_event_id):
    """Begin dated work; no knowledge exists and the holder is untouched."""
    candidate = deepcopy(world)
    decision = _decision(candidate, decision_event_id)
    option = next((item for item in technique_copy_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("technique copy option is stale or unknown")
    require_authority(candidate, actor, "research")
    identity = f"technique-copy:{decision.id}"
    if identity in candidate.research.technique_copies:
        raise ValueError("technique copy decision already used")
    day = candidate.clock.absolute_day
    event = record_event(candidate, "technique_copy_opened",
                         "Um trabalho pago de cópia de técnica começou junto a obras já alcançadas.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("technique_copy", identity, "stage", None, "copying"),),
                         cause_ids=_causes(decision.id, option.sighting_event_id, option.report_event_id,
                                           option.access_event_id))
    record = TechniqueCopy(id=identity, actor_ref=actor, holder_ref=option.holder_ref,
                           technology_id=option.technology_id, site_id=option.site_id,
                           stock_id=option.stock_id, account_id=option.account_id,
                           sighting_event_id=option.sighting_event_id, report_event_id=option.report_event_id,
                           access_kind=option.access_kind, access_id=option.access_id,
                           access_event_id=option.access_event_id,
                           started_day=day, due_day=day + COPY_DAYS, decision_event_id=decision.id,
                           last_event_id=event.id)
    candidate.research.technique_copies[record.id] = record
    candidate.agenda.schedule(ScheduledSituation(record.id, "technique_copy", record.due_day))
    candidate.research.validate(candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.research.technique_copies[record.id]


def resolve_technique_copies(world, situations):
    """Sustained access teaches; interrupted access costs the wages anyway."""
    available = monthly_workforce(world)
    for situation in sorted(situations, key=lambda item: item.id):
        record = world.research.technique_copies.get(situation.id)
        if (situation.kind != "technique_copy" or record is None or record.stage != "copying"
                or record.due_day != world.clock.absolute_day):
            raise ValueError("unknown or inconsistent dated technique copy")
        blocker = _prepared(world, record, available)
        if blocker is None:
            learn_technology(world, record.actor_ref, record.technology_id, "copied",
                             _causes(record.last_event_id, record.sighting_event_id, record.report_event_id,
                                     record.access_event_id))
            knowledge = next(item for item in world.knowledge.technologies.values()
                             if item.owner_ref == record.actor_ref and item.technology_id == record.technology_id)
            world.research.technique_copies[record.id] = record.model_copy(
                update={"stage": "completed", "last_event_id": knowledge.event_id})
            settle_work(world, work_id=record.id, account_id=record.account_id, stock_id=record.stock_id,
                        occupation="artisan", worker_count=COPY_WORKERS, wage=COPY_WAGE,
                        available=available, production_event_id=knowledge.event_id)
        else:
            event = record_event(world, "technique_copy_failed",
                                 f"A cópia não se sustentou ({blocker}); nenhuma técnica foi aprendida.",
                                 fact_kind=FactKind.STATE_TRANSITION,
                                 deltas=(_delta("technique_copy", record.id, "stage", "copying", "failed"),),
                                 cause_ids=_causes(record.last_event_id))
            world.research.technique_copies[record.id] = record.model_copy(
                update={"stage": "failed", "blocker": blocker, "last_event_id": event.id})
            # A lost work relation still pays its already-started month.  If
            # its own payroll prerequisites are what failed, no work can be
            # paid; the factual failure closes the agenda without a later
            # exception or invented debt.
            if blocker not in {"payroll_source", "payroll_funds", "labor"}:
                settle_work(world, work_id=record.id, account_id=record.account_id, stock_id=record.stock_id,
                            occupation="artisan", worker_count=COPY_WORKERS, wage=COPY_WAGE,
                            available=available, production_event_id=event.id)


__all__ = ["COPY_ACTION", "COPY_DAYS", "open_technique_copy", "resolve_technique_copies",
           "technique_copy_options"]

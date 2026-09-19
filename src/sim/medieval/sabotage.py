"""Bounded material sabotage and its paid, private investigation.

This vertical deliberately has no stealth score, random outcome, theft or
generic espionage. A local institution either has a prepared supplied column
or an independently auditable work presence, sees a real site report, spends
its own tools and lowers the Map-owned integrity by exactly ten percent.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.economy.investigation import Investigation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.models import InvestigationAccusationNotice, InvestigationFinding, SiteReport
from src.classes.governance.knowledge import investigation_accusation_notice_id
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _apply_stock, _causes, _delta, monthly_workforce
from .events import record_event
from .infrastructure import current_observation
from .institutional_memory import apply_memory_creation, memory_creation_deltas
from .labor import settle_work
from .institutional_decision_turn import DiscretionaryAdapter


SABOTAGE_ACTION = "sabotage_site"
INVESTIGATE_ACTION = "open_site_investigation"
SITE_REPORT_MAX_AGE = 3
SABOTAGE_TOOLS = 2
TOOLS_RESERVE = 1
INVESTIGATION_WORKERS = 1
INVESTIGATION_WAGE = 2
ACCUSE_ACTION = "accuse_investigation_subject"
ACCUSE_RESPONSE_ACTION = "respond_to_investigation_accusation"


@dataclass(frozen=True)
class SabotageOption:
    id: Identity
    actor_ref: EntityRef
    site_id: Identity
    stock_id: Identity
    presence_kind: str
    detachment_id: Identity | None
    report_event_id: Identity

    def decision(self):
        return {"action": SABOTAGE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class InvestigationOption:
    id: Identity
    actor_ref: EntityRef
    site_id: Identity
    damage_event_id: Identity
    report_event_id: Identity
    stock_id: Identity
    account_id: Identity

    def decision(self):
        return {"action": INVESTIGATE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class AccusationOption:
    id: Identity
    actor_ref: EntityRef
    investigation_id: Identity
    finding_event_id: Identity
    subject_ref: EntityRef
    site_id: Identity

    def decision(self):
        return {"action": ACCUSE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class AccusationResponseOption:
    id: Identity
    actor_ref: EntityRef
    notice_id: Identity
    accusation_event_id: Identity
    response: str

    def decision(self):
        return {"action": ACCUSE_RESPONSE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _event(world, event_id):
    return next((event for event in world.events if event.id == event_id), None)


def _current_site_report(world, actor, site_id):
    report = current_observation(world, actor, site_id)
    if report is None or world.clock.absolute_day - report.observed_day >= SITE_REPORT_MAX_AGE:
        return None
    return report


def _local_stocks(world, actor, site):
    return tuple(stock for _, stock in sorted(world.economy.stocks.items())
                 if stock.owner_ref == actor
                 and world.society.settlements[stock.location_id].region_id in site.region_ids)


def _local_account(world, actor):
    return next((account for _, account in sorted(world.economy.accounts.items())
                 if account.owner_ref == actor), None)


def _prepared_force_presence(world, actor, site):
    matches = []
    for detachment in sorted(world.society.detachments.values(), key=lambda item: item.id):
        if (detachment.owner_ref != actor or detachment.stage != "present"
                or detachment.provisions < detachment.count):
            continue
        settlement = world.society.settlements.get(detachment.location_id)
        position = world.society.force_positions.get(f"force-position:{detachment.id}")
        if (settlement is not None and settlement.region_id in site.region_ids and position is not None
                and position.stage == "prepared" and position.settlement_id == detachment.location_id):
            matches.append(detachment)
    return tuple(matches)


def _work_presence(world, actor, site):
    """Same-day paid work or an active apprenticeship at this exact site."""
    day = world.clock.absolute_day
    for payroll in world.economy.payrolls.values():
        if payroll.day != day:
            continue
        facility = world.economy.facilities.get(payroll.id)
        if facility is not None and facility.site_id == site.id and world.economy.stocks[facility.stock_id].owner_ref == actor:
            return True
        project = world.economy.expansions.get(payroll.id)
        expansion_facility = (world.economy.facilities.get(project.facility_id)
                              if project is not None else None)
        if (project is not None and expansion_facility is not None
                and expansion_facility.site_id == site.id and project.owner_ref == actor):
            return True
        repair = world.economy.repairs.get(payroll.id)
        if repair is not None and repair.site_id == site.id and repair.maintainer_ref == actor:
            return True
        project = world.research.projects.get(payroll.id)
        if project is not None and project.site_id == site.id and project.owner_ref == actor:
            return True
    return any(contract.stage == "training" and contract.site_id == site.id and contract.host_ref == actor
               for contract in world.research.apprenticeships.values())


def _eligible_sabotage_presence(world, actor, site):
    forces = _prepared_force_presence(world, actor, site)
    if forces and can_actor_act_for(world, actor, actor, "military"):
        return "force", forces[0].id
    if can_actor_act_for(world, actor, actor, "supply") and _work_presence(world, actor, site):
        return "work", None
    return None


def _sabotaged_by_actor_today(world, actor, site_id):
    for event in world.events:
        if event.event_type != "site_sabotaged" or event.day != world.clock.absolute_day:
            continue
        linked = [_event(world, link.cause_event_id) for link in event.causal_links]
        if any(decision is not None and decision.fact_kind == FactKind.DECISION
               and decision.decision is not None and decision.decision.get("action") == SABOTAGE_ACTION
               and decision.decision.get("actor_ref") == actor.to_dict()
               for decision in linked) and any(
                   delta.owner_kind == "site" and delta.owner_id == site_id and delta.aspect == "integrity"
                   for delta in event.deltas):
            return True
    return False


def sabotage_options(world, actor):
    if not isinstance(actor, EntityRef) or actor.kind not in {"polity", "organization"}:
        return ()
    options = []
    for site in sorted(world.map.infrastructure_sites.values(), key=lambda item: item.id):
        if actor in {site.owner_ref, site.maintainer_ref} or site.integrity <= 0 or _sabotaged_by_actor_today(world, actor, site.id):
            continue
        report = _current_site_report(world, actor, site.id)
        presence = _eligible_sabotage_presence(world, actor, site)
        if report is None or presence is None:
            continue
        stock = next((item for item in _local_stocks(world, actor, site)
                      if item.goods.get("tools", 0) >= TOOLS_RESERVE + SABOTAGE_TOOLS), None)
        if stock is None:
            continue
        kind, detachment_id = presence
        options.append(SabotageOption(
            id=f"site-sabotage:{actor.kind}:{actor.id}:{site.id}:{kind}:{detachment_id or stock.id}:{report.event_id}",
            actor_ref=actor, site_id=site.id, stock_id=stock.id, presence_kind=kind,
            detachment_id=detachment_id, report_event_id=report.event_id))
    return tuple(options)


def _decision(world, decision_event_id, action):
    event = _event(world, decision_event_id)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision is None or event.decision.get("action") != action
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("sabotage action requires a current actor decision")
    try:
        return event, EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("sabotage action has an invalid actor") from exc


def execute_sabotage_option(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in sabotage_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("sabotage option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id, SABOTAGE_ACTION)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("sabotage has the wrong decision")
    site = candidate.map.infrastructure_sites[option.site_id]
    stock = candidate.economy.stocks[option.stock_id]
    report = _current_site_report(candidate, actor, site.id)
    presence = _eligible_sabotage_presence(candidate, actor, site)
    if (stock.owner_ref != actor or report is None or report.event_id != option.report_event_id
            or presence is None or stock.goods.get("tools", 0) < TOOLS_RESERVE + SABOTAGE_TOOLS
            or _sabotaged_by_actor_today(candidate, actor, site.id)):
        raise ValueError("sabotage is no longer possible")
    kind, detachment_id = presence
    require_authority(candidate, actor, "military" if kind == "force" else "supply")
    after = max(0.0, round(site.integrity - 0.10, 6))
    goods = dict(stock.goods)
    goods["tools"] -= SABOTAGE_TOOLS
    event = _apply_stock(
        candidate, stock, goods, "site_sabotaged",
        f"{site.name}: dano material local reduziu a integridade da instalação.",
        extra_deltas=(
            _delta("site", site.id, "integrity", site.integrity, after),
            _delta("site_sabotage", f"{site.id}:{decision.id}", "actor_ref", None, f"{actor.kind}:{actor.id}"),
            _delta("site_sabotage", f"{site.id}:{decision.id}", "presence_kind", None, kind),
            _delta("site_sabotage", f"{site.id}:{decision.id}", "detachment_id", None, detachment_id),
        ),
        cause_ids=_causes(decision.id, report.event_id, site.last_event_id,
                          candidate.society.detachments[detachment_id].last_event_id if detachment_id else None),
    )
    candidate.map.update_infrastructure_site_runtime(site.id, integrity=after, last_event_id=event.id)
    from .route_intelligence import refresh_site_reports
    refresh_site_reports(candidate, site_ids=(site.id,))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.map.infrastructure_sites[site.id]


def sabotage_label(option):
    """Provider-safe label for the monthly institutional menu."""
    return "Danificar uma instalação estrangeira observada com meios próprios."


def sabotage_adapters():
    """Expose the existing sabotage owner to the shared monthly turn.

    This does not create a second planner or executor.  Contact/aftermath
    policies may still offer the same options; the adapter merely allows an
    institution with a valid local presence and current site report to choose
    sabotage during its ordinary monthly consultation.
    """
    return (
        DiscretionaryAdapter(
            name="site_sabotage", family="conflict", options_fn=sabotage_options,
            label_fn=sabotage_label,
            causes_fn=lambda _world, option: (option.report_event_id,),
            execute_fn=lambda world, actor, option_id, decision_event_id:
                execute_sabotage_option(world, actor, option_id, decision_event_id),
        ),
        DiscretionaryAdapter(
            name="site_investigation", family="conflict", options_fn=investigation_options,
            label_fn=lambda _option: "Investigar a causa de um dano material observado.",
            causes_fn=lambda _world, option: (option.damage_event_id, option.report_event_id),
            execute_fn=lambda world, actor, option_id, decision_event_id:
                open_investigation(world, actor, option_id, decision_event_id),
        ),
        DiscretionaryAdapter(
            name="investigation_accusation", family="conflict", options_fn=accusation_options,
            label_fn=lambda option: f"Notificar {option.subject_ref.id} da acusação baseada na apuração.",
            causes_fn=lambda _world, option: (option.finding_event_id,),
            execute_fn=lambda world, actor, option_id, decision_event_id:
                execute_accusation(world, actor, option_id, decision_event_id),
        ),
        DiscretionaryAdapter(
            name="investigation_accusation_response", family="conflict", options_fn=accusation_response_options,
            label_fn=lambda option: "Negar a acusação recebida." if option.response == "deny"
            else "Pedir revisão da acusação recebida.",
            causes_fn=lambda _world, option: (option.accusation_event_id,),
            execute_fn=lambda world, actor, option_id, decision_event_id:
                execute_accusation_response(world, actor, option_id, decision_event_id),
        ),
    )


def _damage_event(world, site, report):
    event = _event(world, site.last_event_id)
    report_event = _event(world, report.event_id) if report is not None else None
    if event is None or report_event is None or event.day > world.clock.absolute_day:
        return None
    if event.event_type not in {"site_sabotaged", "creature_damaged_site"}:
        return None
    if event.id not in {link.cause_event_id for link in report_event.causal_links}:
        return None
    return event


def _local_workers(world, stock_id):
    stock = world.economy.stocks[stock_id]
    available = monthly_workforce(world)
    return sum(available.get(group.id, 0) for group in world.society.population.values()
               if group.settlement_id == stock.location_id and group.occupation == "farmer")


def investigation_options(world, actor):
    if (not isinstance(actor, EntityRef) or actor.kind not in {"polity", "organization"}
            or not can_actor_act_for(world, actor, actor, "supply")):
        return ()
    options = []
    for site in sorted(world.map.infrastructure_sites.values(), key=lambda item: item.id):
        if actor not in {site.owner_ref, site.maintainer_ref}:
            continue
        report = _current_site_report(world, actor, site.id)
        if report is None or report.integrity >= 1.0:
            continue
        damage = _damage_event(world, site, report)
        if damage is None or any(item.site_id == site.id and item.stage == "open"
                                 for item in world.economy.investigations.values()):
            continue
        stock = next(iter(_local_stocks(world, actor, site)), None)
        account = _local_account(world, actor)
        if (stock is None or account is None or account.balance < INVESTIGATION_WAGE
                or _local_workers(world, stock.id) < INVESTIGATION_WORKERS):
            continue
        identity = f"investigation:{damage.id}:{world.clock.absolute_day}"
        if identity in world.economy.investigations:
            continue
        options.append(InvestigationOption(
            id=f"site-investigation:{actor.kind}:{actor.id}:{site.id}:{damage.id}:{report.event_id}:{stock.id}:{account.id}",
            actor_ref=actor, site_id=site.id, damage_event_id=damage.id, report_event_id=report.event_id,
            stock_id=stock.id, account_id=account.id))
    return tuple(options)


def accusation_options(world, actor):
    """Expose only attributed private findings owned by the accuser."""
    if (not isinstance(actor, EntityRef) or actor.kind not in {"polity", "organization"}
            or not can_actor_act_for(world, actor, actor, "diplomacy")):
        return ()
    options = []
    for investigation in sorted(world.economy.investigations.values(), key=lambda item: item.id):
        if investigation.investigator_ref != actor or investigation.stage != "attributed":
            continue
        finding = world.knowledge.investigation_finding(actor, investigation.id)
        if (finding is None or finding.result != "attributed" or finding.subject_ref is None
                or finding.subject_ref == actor
                or investigation_accusation_notice_id(investigation.id, finding.subject_ref)
                in world.knowledge.investigation_accusation_notices):
            continue
        options.append(AccusationOption(
            id=f"investigation-accusation:{actor.kind}:{actor.id}:{investigation.id}:{finding.event_id}",
            actor_ref=actor, investigation_id=investigation.id, finding_event_id=finding.event_id,
            subject_ref=finding.subject_ref, site_id=investigation.site_id))
    return tuple(options)


def accusation_response_options(world, actor):
    """Offer the accused a bounded factual response to a live notice.

    The response records agency for later interpretation; it neither proves
    guilt nor clears the subject and never mutates material state.
    """
    if (not isinstance(actor, EntityRef) or actor.kind not in {"polity", "organization"}
            or not can_actor_act_for(world, actor, actor, "diplomacy")):
        return ()
    options = []
    for notice in sorted(world.knowledge.investigation_accusations_for_actor(actor), key=lambda item: item.id):
        for response in ("deny", "request_review"):
            if any(event.event_type == "investigation_accusation_response"
                   and event.causal_payload
                   and event.causal_payload.get("notice_id") == notice.id
                   and event.causal_payload.get("response") == response
                   for event in world.events):
                continue
            options.append(AccusationResponseOption(
                id=f"investigation-accusation-response:{actor.kind}:{actor.id}:{notice.id}:{response}",
                actor_ref=actor, notice_id=notice.id, accusation_event_id=notice.event_id,
                response=response))
    return tuple(options)


def execute_accusation_response(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in accusation_response_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("accusation response option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id, ACCUSE_RESPONSE_ACTION)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("accusation response has the wrong decision")
    require_authority(candidate, actor, "diplomacy")
    notice = candidate.knowledge.investigation_accusation_notices.get(option.notice_id)
    if (notice is None or notice.recipient_ref != actor or notice.event_id != option.accusation_event_id):
        raise ValueError("accusation notice is no longer current")
    event = record_event(
        candidate, "investigation_accusation_response",
        "O acusado respondeu a uma acusação privada sem alterar a realidade material.",
        fact_kind=FactKind.OCCURRENCE, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"notice_id": notice.id, "actor_ref": actor.to_dict(), "response": option.response},
        cause_ids=_causes(decision.id, notice.event_id),
    )
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return event


def execute_accusation(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in accusation_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("accusation option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id, ACCUSE_ACTION)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("accusation has the wrong decision")
    require_authority(candidate, actor, "diplomacy")
    finding = candidate.knowledge.investigation_finding(actor, option.investigation_id)
    investigation = candidate.economy.investigations.get(option.investigation_id)
    if (finding is None or investigation is None or investigation.stage != "attributed"
            or finding.event_id != option.finding_event_id or finding.subject_ref != option.subject_ref):
        raise ValueError("investigation finding is no longer attributable")
    notice_id = investigation_accusation_notice_id(investigation.id, option.subject_ref)
    if notice_id in candidate.knowledge.investigation_accusation_notices:
        raise ValueError("investigation subject was already accused")
    event = record_event(
        candidate, "investigation_accusation",
        "Uma instituição notificou o sujeito identificado por uma apuração privada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("investigation_accusation_notice", notice_id, "finding_event_id",
                        None, finding.event_id),),
        cause_ids=_causes(decision.id, finding.event_id, investigation.last_event_id),
    )
    candidate.knowledge.investigation_accusation_notices[notice_id] = InvestigationAccusationNotice(
        id=notice_id, recipient_ref=option.subject_ref, accuser_ref=actor,
        investigation_id=investigation.id, site_id=investigation.site_id,
        subject_ref=option.subject_ref, finding_event_id=finding.event_id,
        event_id=event.id, learned_day=event.day)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.knowledge.investigation_accusation_notices[notice_id]


def open_investigation(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in investigation_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("investigation option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id, INVESTIGATE_ACTION)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("investigation has the wrong decision")
    require_authority(candidate, actor, "supply")
    site = candidate.map.infrastructure_sites[option.site_id]
    report = _current_site_report(candidate, actor, site.id)
    damage = _damage_event(candidate, site, report) if report is not None else None
    stock = candidate.economy.stocks.get(option.stock_id)
    account = candidate.economy.accounts.get(option.account_id)
    if (report is None or damage is None or damage.id != option.damage_event_id
            or report.event_id != option.report_event_id or stock is None or account is None
            or stock.owner_ref != actor or account.owner_ref != actor
            or _local_workers(candidate, stock.id) < INVESTIGATION_WORKERS
            or account.balance < INVESTIGATION_WAGE):
        raise ValueError("investigation is no longer possible")
    identity = f"investigation:{damage.id}:{candidate.clock.absolute_day}"
    if identity in candidate.economy.investigations:
        raise ValueError("damage investigation already exists")
    event = record_event(
        candidate, "investigation_opened", "A instituição contratou uma apuração local do dano observado.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("investigation", identity, "stage", None, "open"),),
        cause_ids=_causes(decision.id, damage.id, report.event_id, stock.last_event_ids.get("tools"), account.last_event_id),
    )
    investigation = Investigation(
        id=identity, site_id=site.id, investigator_ref=actor, damage_event_id=damage.id,
        report_event_id=report.event_id, stock_id=stock.id, account_id=account.id,
        opened_day=candidate.clock.absolute_day, due_day=candidate.clock.absolute_day + 30,
        workers=INVESTIGATION_WORKERS, wage_per_worker=INVESTIGATION_WAGE, last_event_id=event.id,
    )
    candidate.economy.investigations[identity] = investigation
    candidate.agenda.schedule(ScheduledSituation(identity, "investigation", investigation.due_day))
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.economy.investigations[identity]


def _sabotage_subject(world, investigation):
    """Attribution consumes no new information and never reads a hidden actor.

    The only admissible proof is a contact notice the investigator had before
    the damaging act: its standoff identifies a foreign column co-present with
    the exact detachment encoded in the canonical sabotage fact.
    """
    damage = _event(world, investigation.damage_event_id)
    if damage is None or damage.event_type != "site_sabotaged":
        return None
    detachment_id = next((delta.after for delta in damage.deltas
                          if delta.owner_kind == "site_sabotage" and delta.aspect == "detachment_id"
                          and delta.after != "None"), None)
    actor_value = next((delta.after for delta in damage.deltas
                        if delta.owner_kind == "site_sabotage" and delta.aspect == "actor_ref"), None)
    if not detachment_id or not actor_value or ":" not in actor_value:
        return None
    kind, actor_id = actor_value.split(":", 1)
    subject = EntityRef(kind, actor_id)
    for notice in world.knowledge.force_contact_notices.values():
        if (notice.recipient_ref != investigation.investigator_ref or notice.learned_day != damage.day
                or _event(world, notice.event_id) is None or _event(world, notice.event_id).sequence >= damage.sequence
                or notice.counterparty_ref != subject):
            continue
        standoff = world.society.force_standoffs.get(notice.standoff_id)
        own = world.society.detachments.get(notice.own_detachment_id)
        if (standoff is None or own is None or own.owner_ref != investigation.investigator_ref
                or detachment_id not in standoff.detachment_ids
                or standoff.settlement_id not in {settlement.id for settlement in world.society.settlements.values()
                                                   if settlement.region_id in world.map.infrastructure_sites[investigation.site_id].region_ids}):
            continue
        return subject
    return None


def _completion_blocker(world, investigation, available):
    site = world.map.infrastructure_sites.get(investigation.site_id)
    stock = world.economy.stocks.get(investigation.stock_id)
    account = world.economy.accounts.get(investigation.account_id)
    if site is None or investigation.investigator_ref not in {site.owner_ref, site.maintainer_ref}:
        return "site_authority"
    if any(not can_actor_act_for(world, investigation.investigator_ref, investigation.investigator_ref, scope)
           for scope in ("supply", "trade")):
        return "authority"
    if (stock is None or account is None or stock.owner_ref != investigation.investigator_ref
            or account.owner_ref != investigation.investigator_ref
            or world.society.settlements[stock.location_id].region_id not in site.region_ids):
        return "means"
    if account.balance < investigation.workers * investigation.wage_per_worker:
        return "payroll_funds"
    workers = sum(available.get(group.id, 0) for group in world.society.population.values()
                  if group.settlement_id == stock.location_id and group.occupation == "farmer")
    return None if workers >= investigation.workers else "labor"


def _complete_investigation(world, investigation, available):
    subject = _sabotage_subject(world, investigation)
    result = "attributed" if subject is not None else "inconclusive"
    finding_id = f"investigation_finding:{investigation.id}"
    remembering = (investigation.investigator_ref,) if subject is not None else ()
    event = record_event(
        world, "investigation_completed",
        "A apuração paga concluiu uma atribuição limitada." if subject else "A apuração paga terminou sem atribuição conclusiva.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(
            _delta("investigation", investigation.id, "stage", "open", result),
            _delta("investigation_finding", finding_id, "result", None, result),
            *memory_creation_deltas(world, remembering),
        ),
        cause_ids=_causes(investigation.last_event_id, investigation.damage_event_id,
                          investigation.report_event_id),
    )
    world.economy.investigations[investigation.id] = investigation.model_copy(
        update={"stage": result, "last_event_id": event.id})
    world.knowledge.investigation_findings[finding_id] = InvestigationFinding(
        id=finding_id, investigation_id=investigation.id, recipient_ref=investigation.investigator_ref,
        damage_event_id=investigation.damage_event_id, result=result, subject_ref=subject,
        learned_day=world.clock.absolute_day, event_id=event.id)
    if remembering:
        apply_memory_creation(world, remembering, event)
    settle_work(world, work_id=investigation.id, account_id=investigation.account_id,
                stock_id=investigation.stock_id, occupation="farmer", worker_count=investigation.workers,
                wage=investigation.wage_per_worker, available=available, production_event_id=event.id)


def _block_investigation(world, investigation, blocker):
    event = record_event(
        world, "investigation_blocked", "A apuração não pôde pagar seu trabalho local hoje.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("investigation", investigation.id, "stage", "open", "blocked"),),
        cause_ids=_causes(investigation.last_event_id, investigation.damage_event_id),
    )
    world.economy.investigations[investigation.id] = investigation.model_copy(
        update={"stage": "blocked", "last_event_id": event.id})


def resolve_investigations(world, situations):
    available = monthly_workforce(world)
    for situation in situations:
        investigation = world.economy.investigations.get(situation.id)
        if (situation.kind != "investigation" or investigation is None or investigation.stage != "open"
                or investigation.due_day != world.clock.absolute_day):
            raise ValueError("unknown or inconsistent dated investigation")
        blocker = _completion_blocker(world, investigation, available)
        if blocker is None:
            _complete_investigation(world, investigation, available)
        else:
            _block_investigation(world, investigation, blocker)


__all__ = ["SABOTAGE_ACTION", "INVESTIGATE_ACTION", "ACCUSE_ACTION", "ACCUSE_RESPONSE_ACTION",
           "SabotageOption", "InvestigationOption", "AccusationOption", "AccusationResponseOption",
           "sabotage_options", "execute_sabotage_option", "investigation_options", "open_investigation",
           "accusation_options", "execute_accusation", "accusation_response_options",
           "execute_accusation_response", "resolve_investigations"]

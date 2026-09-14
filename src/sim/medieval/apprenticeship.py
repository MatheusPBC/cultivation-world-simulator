"""Technique diffusion through a specialist who actually moved.

A named specialist who took part in completing a technique and who now lives in
a settlement administered by another institution may offer to instruct there.
The host decides separately, pays real wages to a local cohort, and only a
dated completion grants the institution the technique already in the catalog.

Knowledge is copied, never moved: the origin institution keeps its own, and no
person acquires a technique registry of their own. Knowing a technique unlocks
nothing by itself; construction and production keep every material gate.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.research.models import Apprenticeship
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _causes, _delta, monthly_workforce
from .events import record_event
from .labor import settle_work
from .research import learn_technology


OFFER_ACTION = "offer_apprenticeship"
SPONSOR_ACTION = "sponsor_apprenticeship"
APPRENTICESHIP_DAYS = 30


@dataclass(frozen=True)
class ApprenticeshipOfferOption:
    """Transient option of the specialist; only its ID is ever selected."""
    id: Identity
    specialist_id: Identity
    host_ref: EntityRef
    technology_id: Identity
    settlement_id: Identity
    site_id: Identity

    def decision(self):
        return {"action": OFFER_ACTION, "actor_ref": EntityRef("character", self.specialist_id).to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class ApprenticeshipSponsorOption:
    """Transient option of the host, recomposed from the delivered offer."""
    id: Identity
    host_ref: EntityRef
    offer_event_id: Identity
    specialist_id: Identity
    technology_id: Identity
    site_id: Identity
    stock_id: Identity
    account_id: Identity
    workers: int
    wage_per_worker: int

    def decision(self):
        return {"action": SPONSOR_ACTION, "actor_ref": self.host_ref.to_dict(),
                "selected_affordance_id": self.id}


def _event(world, event_id):
    if not isinstance(event_id, str) or not event_id.startswith("event:"):
        return None
    position = event_id.partition(":")[2]
    if not position.isdecimal() or not 1 <= int(position) <= len(world.events):
        return None
    event = world.events[int(position) - 1]
    return event if event.id == event_id else None


def _decision(world, decision_event_id, action):
    event = _event(world, decision_event_id)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision is None or event.decision.get("action") != action
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("apprenticeship requires a current actor decision")
    try:
        actor = EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("apprenticeship decision has an invalid actor") from exc
    return event, actor


def _residence(world, character):
    """Where this person actually lives now, and who administers that place."""
    group = world.society.population.get(character.population_group_id) if character.population_group_id else None
    settlement = world.society.settlements.get(group.settlement_id) if group is not None else None
    if settlement is None or settlement.administrator_id is None or character.location_id != settlement.id:
        return None, None
    return EntityRef("polity", settlement.administrator_id), settlement


def _has_migrated(world, character, settlement_id):
    """A completed journey moved this person here; residence alone is not enough."""
    return any(delta.owner_kind == "character" and delta.owner_id == character.id
               and delta.aspect == "location_id" and delta.after == settlement_id
               and delta.before != settlement_id
               for event in world.events for delta in event.deltas)


def _took_part(world, specialist_id, technology_id):
    return any(project.researcher_id == specialist_id and project.technology_id == technology_id
               and project.stage == "completed" for project in world.research.projects.values())


def _busy(world, specialist_id):
    return (any(item.character_id == specialist_id for item in world.activities.values())
            or any(item.specialist_id == specialist_id and item.stage == "training"
                   for item in world.research.apprenticeships.values()))


def _host_site(world, host, technology, settlement):
    return next((site for _, site in sorted(world.map.infrastructure_sites.items())
                 if site.owner_ref == host and settlement.region_id in site.region_ids
                 and technology.capability_id in site.capability_ids and site.enabled and site.integrity > 0), None)


def specialist_offer_options(world, specialist_id):
    """What this resident specialist could offer to instruct today."""
    character = world.society.characters.get(specialist_id)
    if character is None or character.death_day is not None or _busy(world, specialist_id):
        return ()
    host, settlement = _residence(world, character)
    if host is None or not _has_migrated(world, character, settlement.id):
        return ()
    day = world.clock.absolute_day
    options = []
    for technology_id, technology in sorted(world.research.technologies.items()):
        if (world.knowledge.knows(host, technology_id) or not _took_part(world, specialist_id, technology_id)
                or getattr(character.skills, technology.skill) < technology.min_skill
                or any(not world.knowledge.knows(host, other) for other in technology.prerequisites)):
            continue
        site = _host_site(world, host, technology, settlement)
        if site is None:
            continue
        options.append(ApprenticeshipOfferOption(
            id=f"apprenticeship-offer:{specialist_id}:{host.id}:{technology_id}:{settlement.id}:{site.id}:{day}",
            specialist_id=specialist_id, host_ref=host, technology_id=technology_id,
            settlement_id=settlement.id, site_id=site.id))
    return tuple(options)


def record_apprenticeship_offer(world, specialist_id, option_id):
    """The specialist's own decision; it carries no delta and binds nobody."""
    option = next((item for item in specialist_offer_options(world, specialist_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("apprenticeship offer option is stale or unknown")
    if any(event.fact_kind == FactKind.DECISION and event.decision == option.decision() for event in world.events):
        raise ValueError("apprenticeship offer decision already exists")
    return record_event(world, "apprenticeship_offered",
                        "Um especialista residente ofereceu instruir a instituição local.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def _sponsored(world, offer_event_id):
    return any(item.specialist_decision_id == offer_event_id for item in world.research.apprenticeships.values())


def _local_cohort(world, settlement_id, occupation, available):
    return sum(available.get(group.id, 0) for group in world.society.population.values()
               if group.settlement_id == settlement_id and group.occupation == occupation)


def apprenticeship_sponsor_options(world, host):
    """Offers delivered to this host that it could pay for from its own means."""
    if (not isinstance(host, EntityRef)
            or any(not can_actor_act_for(world, host, host, scope) for scope in ("research", "trade", "supply"))):
        return ()
    day = world.clock.absolute_day
    available = monthly_workforce(world)
    options = []
    for event in world.events:
        if (event.fact_kind != FactKind.DECISION or event.day != day
                or (event.decision or {}).get("action") != OFFER_ACTION or _sponsored(world, event.id)):
            continue
        specialist_id = (event.decision.get("actor_ref") or {}).get("id")
        offer = next((item for item in specialist_offer_options(world, specialist_id)
                      if item.decision() == event.decision), None)
        if offer is None or offer.host_ref != host:
            continue
        technology = world.research.technologies[offer.technology_id]
        stock = next((item for _, item in sorted(world.economy.stocks.items())
                      if item.owner_ref == host and item.location_id == offer.settlement_id), None)
        account = next((item for _, item in sorted(world.economy.accounts.items())
                        if item.owner_ref == host), None)
        workers = technology.assistants_per_unit
        if (stock is None or account is None
                or account.balance < workers * technology.wage_per_worker
                or _local_cohort(world, offer.settlement_id, technology.assistant_occupation, available) < workers):
            continue
        options.append(ApprenticeshipSponsorOption(
            id=f"apprenticeship-sponsor:{event.id}:{stock.id}:{account.id}:{workers}",
            host_ref=host, offer_event_id=event.id, specialist_id=offer.specialist_id,
            technology_id=offer.technology_id, site_id=offer.site_id, stock_id=stock.id,
            account_id=account.id, workers=workers, wage_per_worker=technology.wage_per_worker))
    return tuple(options)


def sponsor_apprenticeship(world, host, option_id, decision_event_id):
    """Bind a dated instruction contract. No wage, no knowledge, no shortcut."""
    candidate = deepcopy(world)
    decision, actor = _decision(candidate, decision_event_id, SPONSOR_ACTION)
    if actor != host:
        raise ValueError("apprenticeship sponsorship has the wrong actor")
    option = next((item for item in apprenticeship_sponsor_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("apprenticeship sponsorship option is stale or unknown")
    for scope in ("research", "trade", "supply"):
        require_authority(candidate, actor, scope)
    identity = f"apprenticeship:{decision.id}"
    if identity in candidate.research.apprenticeships:
        raise ValueError("apprenticeship decision already used")
    day = candidate.clock.absolute_day
    event = record_event(candidate, "apprenticeship_started",
                         "Instrução local contratada; nenhuma técnica foi adquirida ainda.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("apprenticeship", identity, "stage", None, "training"),),
                         cause_ids=_causes(option.offer_event_id, decision.id))
    contract = Apprenticeship(id=identity, host_ref=actor, technology_id=option.technology_id,
                              specialist_id=option.specialist_id, site_id=option.site_id,
                              stock_id=option.stock_id, account_id=option.account_id, workers=option.workers,
                              wage_per_worker=option.wage_per_worker, started_day=day,
                              due_day=day + APPRENTICESHIP_DAYS, specialist_decision_id=option.offer_event_id,
                              sponsor_decision_id=decision.id, last_event_id=event.id)
    candidate.research.apprenticeships[contract.id] = contract
    candidate.agenda.schedule(ScheduledSituation(contract.id, "apprenticeship", contract.due_day))
    candidate.economy.validate(candidate)
    candidate.research.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.research.apprenticeships[contract.id]


def _completion_blocker(world, contract, available):
    character = world.society.characters.get(contract.specialist_id)
    technology = world.research.technologies[contract.technology_id]
    stock = world.economy.stocks.get(contract.stock_id)
    account = world.economy.accounts.get(contract.account_id)
    site = world.map.infrastructure_sites.get(contract.site_id)
    if character is None or character.death_day is not None:
        return "specialist_absent"
    host, settlement = _residence(world, character)
    if host != contract.host_ref or settlement is None or stock is None or stock.location_id != settlement.id:
        return "specialist_absent"
    if getattr(character.skills, technology.skill) < technology.min_skill:
        return "qualification"
    if any(not can_actor_act_for(world, contract.host_ref, contract.host_ref, scope)
           for scope in ("research", "trade", "supply")):
        return "authority"
    if site is None or site.owner_ref != contract.host_ref or not site.enabled or site.integrity <= 0:
        return "site_unavailable"
    if world.knowledge.knows(contract.host_ref, contract.technology_id):
        return "already_known"
    if any(not world.knowledge.knows(contract.host_ref, other) for other in technology.prerequisites):
        return "prerequisites"
    if account is None or account.balance < contract.workers * contract.wage_per_worker:
        return "payroll_funds"
    if _local_cohort(world, settlement.id, technology.assistant_occupation, available) < contract.workers:
        return "labor"
    return None


def _close(world, contract, blocker):
    event = record_event(world, "apprenticeship_failed",
                         f"A instrução contratada não pôde ser concluída ({blocker}); "
                         "nenhuma técnica foi adquirida.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("apprenticeship", contract.id, "stage", "training", "failed"),),
                         cause_ids=_causes(contract.last_event_id, contract.sponsor_decision_id))
    world.research.apprenticeships[contract.id] = contract.model_copy(
        update={"stage": "failed", "last_event_id": event.id})
    return event


def _complete(world, contract, available):
    technology = world.research.technologies[contract.technology_id]
    event = record_event(world, "apprenticeship_completed",
                         f"{technology.name}: instrução local concluída e paga; instalações não foram criadas.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("apprenticeship", contract.id, "stage", "training", "completed"),),
                         cause_ids=_causes(contract.last_event_id, contract.sponsor_decision_id,
                                           contract.specialist_decision_id))
    world.research.apprenticeships[contract.id] = contract.model_copy(
        update={"stage": "completed", "last_event_id": event.id})
    settle_work(world, work_id=contract.id, account_id=contract.account_id, stock_id=contract.stock_id,
                occupation=technology.assistant_occupation, worker_count=contract.workers,
                wage=contract.wage_per_worker, available=available, production_event_id=event.id)
    learn_technology(world, contract.host_ref, contract.technology_id, "apprenticeship",
                     _causes(event.id, contract.specialist_decision_id, contract.sponsor_decision_id))
    return event


def resolve_apprenticeships(world, situations):
    """Dated completion: revalidate, pay real work, then grant the technique."""
    available = monthly_workforce(world)
    for situation in situations:
        contract = world.research.apprenticeships.get(situation.id)
        if (situation.kind != "apprenticeship" or contract is None
                or contract.due_day != world.clock.absolute_day):
            raise ValueError("unknown or inconsistent dated apprenticeship")
        blocker = _completion_blocker(world, contract, available)
        if blocker is None:
            _complete(world, contract, available)
        else:
            _close(world, contract, blocker)

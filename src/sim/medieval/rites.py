"""One authored restorative rite, performed as material work with witnesses.

There is no spell language, no summoning and no magical combat here. A rite is
an institution spending its own reagents and paying its own local assistants
while a qualified resident officiates at a capable site it owns. It relieves
the recorded health of that settlement by a bounded amount and creates nothing
else: no food, no money, no people, no capacity and no control.

The rite is public where it happens: a local report says only that one is
underway. Anyone with a supplied detachment standing there may interrupt it,
and the sponsor may call it off; either way the committed reagents are lost,
nothing changes hands and nobody is hurt.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.governance.knowledge import rite_observation_id
from src.classes.governance.models import RiteObservation
from src.classes.research.models import Rite, RiteRecovery, Ward
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .demand import reserve_quantity
from .economy import _apply_stock, _causes, _delta, monthly_workforce
from .events import record_event
from .labor import settle_work

OFFER_ACTION = "offer_rite"
SPONSOR_ACTION = "sponsor_rite"
CANCEL_ACTION = "cancel_rite"
HEALTH_THRESHOLD = 900
MAX_HEALTH = 1000
REPORT_MAX_AGE = 30


@dataclass(frozen=True)
class RiteOfferOption:
    """Transient option of the officiant; only the ID is ever selected."""
    id: Identity
    officiant_id: Identity
    sponsor_ref: EntityRef
    blueprint_id: Identity
    site_id: Identity
    settlement_id: Identity
    report_id: Identity
    report_event_id: Identity
    target_settlement_id: Identity | None = None
    route_id: Identity | None = None

    def decision(self):
        return {"action": OFFER_ACTION, "actor_ref": EntityRef("character", self.officiant_id).to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class RiteSponsorOption:
    id: Identity
    sponsor_ref: EntityRef
    offer_event_id: Identity
    officiant_id: Identity
    blueprint_id: Identity
    site_id: Identity
    settlement_id: Identity
    stock_id: Identity
    account_id: Identity
    target_settlement_id: Identity | None = None
    route_id: Identity | None = None

    def decision(self):
        return {"action": SPONSOR_ACTION, "actor_ref": self.sponsor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class RiteStopOption:
    id: Identity
    actor_ref: EntityRef
    rite_id: Identity
    kind: str

    def decision(self):
        return {"action": CANCEL_ACTION,
                "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


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
        raise ValueError("rite requires a current actor decision")
    try:
        actor = EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("rite decision has an invalid actor") from exc
    return event, actor


def _residence(world, character):
    group = world.society.population.get(character.population_group_id) if character.population_group_id else None
    settlement = world.society.settlements.get(group.settlement_id) if group is not None else None
    if settlement is None or character.location_id != settlement.id:
        return None
    return settlement


def _busy(world, officiant_id):
    recovery = world.research.rite_recoveries.get(officiant_id)
    return (any(item.character_id == officiant_id for item in world.activities.values())
            or (recovery is not None and recovery.until_day > world.clock.absolute_day)
            or any(item.officiant_id == officiant_id and item.stage == "officiating"
                   for item in world.research.rites.values())
            or any(item.specialist_id == officiant_id and item.stage == "training"
                   for item in world.research.apprenticeships.values()))


def ward_active(world, settlement_id, sponsor_ref=None):
    """A standing ward of somebody else over this place, if there is one."""
    day = world.clock.absolute_day
    return next((ward for _, ward in sorted(world.research.wards.items())
                 if ward.settlement_id == settlement_id and ward.until_day > day
                 and (sponsor_ref is None or ward.sponsor_ref != sponsor_ref)), None)


def _segment(world, origin_id, target_id):
    """The one existing, currently usable route between two places."""
    origin = world.society.settlements.get(origin_id)
    target = world.society.settlements.get(target_id)
    if origin is None or target is None or origin.id == target.id:
        return None
    return next((route_id for route_id, route in sorted(world.map.routes.items())
                 if route.connects(origin.region_id, target.region_id)
                 and world.map.get_route_operational_capacity(route_id) > 0), None)


def _reachable(world, sponsor, settlement):
    """Places the sponsor itself observes, one usable segment away from here."""
    day = world.clock.absolute_day
    for target_id in sorted(world.society.settlements):
        if target_id == settlement.id:
            continue
        route_id = _segment(world, settlement.id, target_id)
        report = world.knowledge.route_report(sponsor, route_id) if route_id else None
        if (route_id is None or report is None or report.operational_capacity <= 0
                or not 0 <= day - report.observed_day < REPORT_MAX_AGE):
            continue
        target_report = _sponsor_report(world, sponsor, target_id)
        if target_report is not None:
            yield target_id, route_id


def _sponsor_site(world, sponsor, blueprint, settlement):
    return next((site for _, site in sorted(world.map.infrastructure_sites.items())
                 if site.owner_ref == sponsor and settlement.region_id in site.region_ids
                 and blueprint.capability_id in site.capability_ids and site.enabled and site.integrity > 0), None)


def _sponsor_holdings(world, sponsor, settlement_id):
    stock = next((item for _, item in sorted(world.economy.stocks.items())
                  if item.owner_ref == sponsor and item.location_id == settlement_id), None)
    account = next((item for _, item in sorted(world.economy.accounts.items())
                    if item.owner_ref == sponsor), None)
    return stock, account


def _sponsors(world, settlement):
    for kind, registry in (("organization", world.society.organizations), ("polity", world.society.polities)):
        for identity in sorted(registry):
            yield EntityRef(kind, identity)


def _personal_report(world, character, settlement, *, require_ailing=True):
    """The officiant may act only on its own fresh, local aggregate reading."""
    actor = EntityRef("character", character.id)
    report = world.knowledge.settlement_report(actor, settlement.id)
    if (report is None or report.recipient_ref != actor or report.publisher_ref != actor
            or report.channel != "local_settlement_report" or report.settlement_id != settlement.id
            or report.observed_day > world.clock.absolute_day
            or world.clock.absolute_day - report.observed_day >= REPORT_MAX_AGE
            or (require_ailing and report.health >= HEALTH_THRESHOLD)):
        return None
    return report


def _sponsor_report(world, sponsor, settlement_id, *, require_ailing=True):
    """A sponsor judges an offer from its own dated reading of that place."""
    report = world.knowledge.settlement_report(sponsor, settlement_id)
    if (report is None or report.recipient_ref != sponsor or report.publisher_ref != sponsor
            or report.settlement_id != settlement_id or report.observed_day > world.clock.absolute_day
            or world.clock.absolute_day - report.observed_day >= REPORT_MAX_AGE
            or (require_ailing and report.health >= HEALTH_THRESHOLD)):
        return None
    return report


def rite_offer_options(world, officiant_id):
    """What this resident officiant could offer to perform where it lives."""
    character = world.society.characters.get(officiant_id)
    if character is None or character.death_day is not None or _busy(world, officiant_id):
        return ()
    settlement = _residence(world, character)
    if settlement is None:
        return ()
    report = _personal_report(world, character, settlement, require_ailing=False)
    if report is None:
        return ()
    options = []
    for blueprint_id, blueprint in sorted(world.research.rite_blueprints.items()):
        if getattr(character.skills, blueprint.skill) < blueprint.min_skill:
            continue
        for sponsor in _sponsors(world, settlement):
            site = _sponsor_site(world, sponsor, blueprint, settlement)
            stock, account = _sponsor_holdings(world, sponsor, settlement.id)
            if site is None or stock is None or account is None:
                continue
            if blueprint.kind == "ward":
                # One standing protection per place; a ward heals nobody, so
                # the local reading needs no distress at all.
                targets = () if ward_active(world, settlement.id) is not None else ((None, None),)
            elif blueprint.reach == "local":
                targets = () if report.health >= HEALTH_THRESHOLD else ((None, None),)
            else:
                targets = tuple(_reachable(world, sponsor, settlement))
            for target_id, route_id in targets:
                options.append(RiteOfferOption(
                    id=(f"rite-offer:{officiant_id}:{sponsor.kind}:{sponsor.id}:{blueprint_id}:{site.id}:"
                        f"{target_id or '-'}:{route_id or '-'}:{report.event_id}"),
                    officiant_id=officiant_id, sponsor_ref=sponsor, blueprint_id=blueprint_id,
                    site_id=site.id, settlement_id=settlement.id, report_id=report.id,
                    report_event_id=report.event_id, target_settlement_id=target_id, route_id=route_id))
    return tuple(options)


def record_rite_offer(world, officiant_id, option_id, *, cause_ids=()):
    """The officiant's own decision; it carries no delta and binds nobody."""
    option = next((item for item in rite_offer_options(world, officiant_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("rite offer option is stale or unknown")
    if any(event.fact_kind == FactKind.DECISION and event.decision == option.decision() for event in world.events):
        raise ValueError("rite offer decision already exists")
    return record_event(world, "rite_offered", "Um oficiante residente ofereceu conduzir um rito local.",
                        fact_kind=FactKind.DECISION, decision=option.decision(),
                        cause_ids=_causes(option.report_event_id, *cause_ids))


def _sponsored(world, offer_event_id):
    return any(item.officiant_decision_id == offer_event_id for item in world.research.rites.values())


def _local_cohort(world, settlement_id, occupation, available):
    return sum(available.get(group.id, 0) for group in world.society.population.values()
               if group.settlement_id == settlement_id and group.occupation == occupation)


def _affordable(world, blueprint, stock, account, settlement_id, available):
    if account.balance < blueprint.assistants * blueprint.wage_per_worker:
        return False
    if _local_cohort(world, settlement_id, blueprint.assistant_occupation, available) < blueprint.assistants:
        return False
    return all(stock.goods.get(resource_id, 0) - reserve_quantity(world, stock.id, resource_id) >= amount
               for resource_id, amount in blueprint.inputs.items())


def rite_sponsor_options(world, sponsor):
    """Offers this institution could pay for, judged on its own means and report."""
    if (not isinstance(sponsor, EntityRef)
            or any(not can_actor_act_for(world, sponsor, sponsor, scope) for scope in ("supply", "trade"))):
        return ()
    day = world.clock.absolute_day
    available = monthly_workforce(world)
    options = []
    for event in world.events:
        if (event.fact_kind != FactKind.DECISION or day - event.day not in {0, 1}
                or (event.decision or {}).get("action") != OFFER_ACTION or _sponsored(world, event.id)):
            continue
        officiant_id = (event.decision.get("actor_ref") or {}).get("id")
        offer = next((item for item in rite_offer_options(world, officiant_id)
                      if item.decision() == event.decision), None)
        if offer is None or offer.sponsor_ref != sponsor:
            continue
        blueprint = world.research.rite_blueprints[offer.blueprint_id]
        local = _sponsor_report(world, sponsor, offer.settlement_id, require_ailing=False)
        if local is None:
            continue
        if blueprint.kind == "restoration" and blueprint.reach == "local" and local.health >= HEALTH_THRESHOLD:
            continue
        # A reached place is judged by the sponsor's own dated reading of it.
        if offer.target_settlement_id is not None and _sponsor_report(
                world, sponsor, offer.target_settlement_id) is None:
            continue
        stock, account = _sponsor_holdings(world, sponsor, offer.settlement_id)
        if stock is None or account is None or not _affordable(world, blueprint, stock, account,
                                                               offer.settlement_id, available):
            continue
        options.append(RiteSponsorOption(
            id=f"rite-sponsor:{event.id}:{stock.id}:{account.id}",
            sponsor_ref=sponsor, offer_event_id=event.id, officiant_id=offer.officiant_id,
            blueprint_id=offer.blueprint_id, site_id=offer.site_id, settlement_id=offer.settlement_id,
            stock_id=stock.id, account_id=account.id,
            target_settlement_id=offer.target_settlement_id, route_id=offer.route_id))
    return tuple(options)


def sponsor_rite(world, sponsor, option_id, decision_event_id):
    """Bind the rite. Nothing is consumed and no health changes at the start."""
    candidate = deepcopy(world)
    decision, actor = _decision(candidate, decision_event_id, SPONSOR_ACTION)
    if actor != sponsor:
        raise ValueError("rite sponsorship has the wrong actor")
    option = next((item for item in rite_sponsor_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("rite sponsorship option is stale or unknown")
    for scope in ("supply", "trade"):
        require_authority(candidate, actor, scope)
    identity = f"rite:{decision.id}"
    if identity in candidate.research.rites:
        raise ValueError("rite decision already used")
    blueprint = candidate.research.rite_blueprints[option.blueprint_id]
    day = candidate.clock.absolute_day
    event = record_event(candidate, "rite_started",
                         f"{blueprint.name}: rito iniciado; nada foi consumido nem curado ainda.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("rite", identity, "stage", None, "officiating"),),
                         cause_ids=_causes(option.offer_event_id, decision.id))
    rite = Rite(id=identity, sponsor_ref=actor, blueprint_id=option.blueprint_id,
                officiant_id=option.officiant_id, site_id=option.site_id, settlement_id=option.settlement_id,
                stock_id=option.stock_id, account_id=option.account_id, started_day=day,
                target_settlement_id=option.target_settlement_id, route_id=option.route_id,
                due_day=day + blueprint.days, officiant_decision_id=option.offer_event_id,
                sponsor_decision_id=decision.id, last_event_id=event.id)
    candidate.research.rites[rite.id] = rite
    candidate.agenda.schedule(ScheduledSituation(rite.id, "rite", rite.due_day))
    observe_rites(candidate, settlement_id=rite.settlement_id)
    candidate.research.validate(candidate)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.research.rites[rite.id]


def rite_stop_options(world, actor):
    """A sponsor may still call off only its own material commitment.

    A hostile local column does not interrupt a rite directly.  It can instead
    deny assembly using its own bounded observation; the dated rite owner then
    applies the existing forfeiture path on the following tick.
    """
    options = []
    for _, rite in sorted(world.research.rites.items()):
        if rite.stage != "officiating":
            continue
        base = f"rite-stop:{rite.id}:{rite.last_event_id}"
        if rite.sponsor_ref == actor:
            options.append(RiteStopOption(f"{base}:cancel", actor, rite.id, "cancel"))
    return tuple(options)


def _forfeit(world, rite, event_type, content, *, stage, causes=()):
    """Committed reagents are lost where they stood; nothing changes hands."""
    blueprint = world.research.rite_blueprints[rite.blueprint_id]
    stock = world.economy.stocks[rite.stock_id]
    goods = {**stock.goods}
    for resource_id, amount in blueprint.inputs.items():
        goods[resource_id] = max(0, goods.get(resource_id, 0) - amount)
    until = _recovery_until(world, rite)
    event = _apply_stock(world, stock, goods, event_type, content,
                         extra_deltas=(_delta("rite", rite.id, "stage", rite.stage, stage),
                                       _delta("rite_recovery", rite.officiant_id, "until_day", None, until)),
                         cause_ids=_causes(rite.last_event_id, *causes))
    world.research.rites[rite.id] = rite.model_copy(update={"stage": stage, "last_event_id": event.id})
    _recover(world, rite, event.id, until)
    world.agenda.cancel(rite.id)
    return event


def stop_rite(world, actor, option_id, decision_event_id):
    """One explicit decision ends a rite; it never takes anything from anyone."""
    candidate = deepcopy(world)
    option = next((item for item in rite_stop_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("rite stop option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id, CANCEL_ACTION)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("rite stop decision does not match its option")
    rite = candidate.research.rites[option.rite_id]
    _forfeit(candidate, rite, "rite_failed",
             "O patrocinador encerrou o rito; os reagentes comprometidos se perderam.",
             stage="failed", causes=(decision.id,))
    candidate.research.validate(candidate)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.research.rites[option.rite_id]


def _assistants_band(assistants):
    if assistants <= 2:
        return "1-2"
    if assistants <= 5:
        return "3-5"
    return "6+"


def _observers_for_rite(world, rite):
    """Only local, factual paths yield the deliberately redacted reading."""
    settlement = world.society.settlements.get(rite.settlement_id)
    site = world.map.infrastructure_sites.get(rite.site_id)
    if settlement is None or site is None or settlement.region_id not in site.region_ids:
        return ()
    observers = []
    if settlement.administrator_id is not None:
        admin = EntityRef("polity", settlement.administrator_id)
        report = world.knowledge.settlement_report(admin, settlement.id)
        if report is not None and report.observed_day == world.clock.absolute_day and report.rite_underway:
            observers.append((admin, (report.event_id,)))
    for owner in (site.owner_ref, site.maintainer_ref):
        if owner is not None:
            observers.append((owner, ()))
    for detachment in world.society.detachments.values():
        if detachment.stage == "present" and detachment.location_id == settlement.id:
            observers.append((detachment.owner_ref, (detachment.last_event_id,)))
    unique = {}
    for observer, causes in observers:
        unique.setdefault(observer, causes)
    return tuple((observer, unique[observer]) for observer in sorted(unique, key=lambda item: (item.kind, item.id)))


def observe_rites(world, *, settlement_id=None):
    """Record bounded local sightings; no observation creates a decision.

    The canonical rite remains in ResearchState.  Knowledge receives no rite
    identifier or contract terms, so a later force decision can only select a
    local assembly-denial affordance the owner recomposes from this receipt.
    """
    for rite in tuple(world.research.rites.values()):
        if rite.stage != "officiating" or (settlement_id is not None and rite.settlement_id != settlement_id):
            continue
        band = _assistants_band(world.research.rite_blueprints[rite.blueprint_id].assistants)
        for observer, presence_causes in _observers_for_rite(world, rite):
            identity = rite_observation_id(observer, rite.site_id)
            previous = world.knowledge.rite_observations.get(identity)
            if (previous is not None and previous.observed_day == world.clock.absolute_day
                    and previous.stage == "underway" and previous.assistants_band == band):
                continue
            event = record_event(
                world, "rite_observed", "Um rito em curso foi observado localmente sem revelar seus termos.",
                fact_kind=FactKind.STATE_TRANSITION,
                deltas=(_delta("rite_observation", identity, "stage", previous.stage if previous else None, "underway"),
                        _delta("rite_observation", identity, "assistants_band",
                               previous.assistants_band if previous else None, band)),
                cause_ids=_causes(rite.last_event_id, *presence_causes))
            world.knowledge.rite_observations[identity] = RiteObservation(
                id=identity, recipient_ref=observer, settlement_id=rite.settlement_id, site_id=rite.site_id,
                stage="underway", observed_day=world.clock.absolute_day, assistants_band=band, event_id=event.id)


def _completion_blocker(world, rite, available):
    blueprint = world.research.rite_blueprints[rite.blueprint_id]
    character = world.society.characters.get(rite.officiant_id)
    stock = world.economy.stocks.get(rite.stock_id)
    account = world.economy.accounts.get(rite.account_id)
    site = world.map.infrastructure_sites.get(rite.site_id)
    settlement = world.society.settlements.get(rite.settlement_id)
    if character is None or character.death_day is not None or _residence(world, character) != settlement:
        return "officiant_absent"
    if getattr(character.skills, blueprint.skill) < blueprint.min_skill:
        return "qualification"
    if any(not can_actor_act_for(world, rite.sponsor_ref, rite.sponsor_ref, scope) for scope in ("supply", "trade")):
        return "authority"
    if (site is None or site.owner_ref != rite.sponsor_ref or not site.enabled or site.integrity <= 0
            or blueprint.capability_id not in site.capability_ids):
        return "site_unavailable"
    if stock is None or account is None or not _affordable(world, blueprint, stock, account,
                                                           rite.settlement_id, available):
        return "means"
    if rite.target_settlement_id is not None:
        # The reach is one segment of the real map, now: a closed river, an
        # interdicted road or a ruined site ends the working.
        if _segment(world, rite.settlement_id, rite.target_settlement_id) != rite.route_id:
            return "reach_lost"
        if ward_active(world, rite.target_settlement_id, rite.sponsor_ref) is not None:
            return "warded"
    return None


def _recovery_until(world, rite):
    blueprint = world.research.rite_blueprints[rite.blueprint_id]
    return world.clock.absolute_day + max(1, blueprint.days // 2)


def _recover(world, rite, event_id, until):
    """Officiating spends a real person for a declared term."""
    world.research.rite_recoveries[rite.officiant_id] = RiteRecovery(
        id=rite.officiant_id, character_id=rite.officiant_id, until_day=until,
        rite_id=rite.id, last_event_id=event_id)


def _complete(world, rite, available):
    blueprint = world.research.rite_blueprints[rite.blueprint_id]
    stock = world.economy.stocks[rite.stock_id]
    goods = {**stock.goods}
    for resource_id, amount in blueprint.inputs.items():
        goods[resource_id] = goods.get(resource_id, 0) - amount
    until = _recovery_until(world, rite)
    recovery = _delta("rite_recovery", rite.officiant_id, "until_day", None, until)
    stage = _delta("rite", rite.id, "stage", "officiating", "completed")
    if blueprint.kind == "ward":
        identity = f"ward:{rite.id}"
        ward_until = world.clock.absolute_day + blueprint.ward_days
        event = _apply_stock(world, stock, goods, "rite_completed",
                             f"{blueprint.name}: proteção erguida até o dia {ward_until}; ninguém foi curado.",
                             extra_deltas=(stage, recovery,
                                           _delta("ward", identity, "until_day", None, ward_until)),
                             cause_ids=_causes(rite.last_event_id, rite.sponsor_decision_id,
                                               rite.officiant_decision_id))
        world.research.wards[identity] = Ward(
            id=identity, settlement_id=rite.settlement_id, sponsor_ref=rite.sponsor_ref, rite_id=rite.id,
            started_day=world.clock.absolute_day, until_day=ward_until, last_event_id=event.id)
    else:
        need = world.economy.needs[rite.target_settlement_id or rite.settlement_id]
        health = min(MAX_HEALTH, need.health + blueprint.health_gain_permille)
        event = _apply_stock(world, stock, goods, "rite_completed",
                             f"{blueprint.name}: rito concluído; alívio de {health - need.health} na saúde.",
                             extra_deltas=(stage, recovery,
                                           _delta("subsistence", need.id, "health", need.health, health)),
                             cause_ids=_causes(rite.last_event_id, rite.sponsor_decision_id,
                                               rite.officiant_decision_id, need.last_event_id))
        world.economy.needs[need.id] = need.model_copy(update={"health": health, "last_event_id": event.id})
    settle_work(world, work_id=rite.id, account_id=rite.account_id, stock_id=rite.stock_id,
                occupation=blueprint.assistant_occupation, worker_count=blueprint.assistants,
                wage=blueprint.wage_per_worker, available=available, production_event_id=event.id)
    world.research.rites[rite.id] = rite.model_copy(update={"stage": "completed", "last_event_id": event.id})
    _recover(world, rite, event.id, until)
    return event


def _fail(world, rite, blocker):
    until = _recovery_until(world, rite)
    event = record_event(world, "rite_failed",
                         f"O rito não pôde ser concluído ({blocker}); nenhuma cura foi produzida.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("rite", rite.id, "stage", "officiating", "failed"),
                                 _delta("rite_recovery", rite.officiant_id, "until_day", None, until)),
                         cause_ids=_causes(rite.last_event_id, rite.sponsor_decision_id))
    world.research.rites[rite.id] = rite.model_copy(update={"stage": "failed", "last_event_id": event.id})
    _recover(world, rite, event.id, until)
    return event


def resolve_rites(world, situations):
    """Dated resolution: revalidate, then spend, pay and relieve — in that order."""
    available = monthly_workforce(world)
    for situation in situations:
        if situation.kind == "rite_interruption":
            denial = world.society.assembly_denials.get(situation.id)
            if denial is None:
                continue
            rite = next((item for item in world.research.rites.values()
                         if item.stage == "officiating" and item.site_id == denial.id
                         and item.settlement_id == denial.settlement_id), None)
            if rite is not None:
                _forfeit(world, rite, "rite_interrupted",
                         "A assembleia negada impediu a conclusão do rito; os reagentes comprometidos se perderam.",
                         stage="interrupted", causes=(denial.last_event_id,))
            continue
        rite = world.research.rites.get(situation.id)
        if (situation.kind != "rite" or rite is None or rite.stage != "officiating"
                or rite.due_day != world.clock.absolute_day):
            raise ValueError("unknown or inconsistent dated rite")
        blocker = _completion_blocker(world, rite, available)
        if blocker is None:
            _complete(world, rite, available)
        else:
            _fail(world, rite, blocker)

"""Raising, marching and standing: the material floor under any campaign.

Nothing here resolves a battle, a siege or a morale check. A detachment is
people who left a real cohort with real provisions, walking real routes. While
it stands supplied somewhere, its owner may record occupation of that place —
a revocable settlement fact that grants no administration, no stock, no
account and no tax. When the provisions run out the presence lapses by its own
fact and the survivors return to a cohort where they actually are.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment, ForcePosition, ForceStandoff
from src.classes.governance.knowledge import force_contact_notice_id
from src.classes.governance.models import ForceContactNotice
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .demand import reserve_quantity
from .economy import _causes, _delta, monthly_workforce
from .events import record_event
from .labor import settle_work
from .routing import known_supply_path
from .travel import route_duration


RAISE_ACTION = "raise_detachment"
MARCH_ACTION = "march_detachment"
OCCUPY_ACTION = "occupy_settlement"
DISBAND_ACTION = "disband_detachment"
STAND_DOWN_ACTION = "stand_down_from_standoff"
WITHDRAW_ACTION = "withdraw_detachment"
PREPARE_POSITION_ACTION = "prepare_force_position"
RATIONS_PER_SOLDIER_DAY = 1
WAGE_PER_SOLDIER = 2
POSITION_PREPARATION_DAYS = 3


@dataclass(frozen=True)
class RaiseOption:
    id: Identity
    actor_ref: EntityRef
    group_id: Identity
    settlement_id: Identity
    stock_id: Identity
    account_id: Identity
    count: int
    provisions: int
    destination_id: Identity
    route_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": RAISE_ACTION, "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


@dataclass(frozen=True)
class ForceOption:
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    kind: str

    def decision(self):
        return {"action": {"march": MARCH_ACTION, "occupy": OCCUPY_ACTION, "disband": DISBAND_ACTION}[self.kind],
                "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


@dataclass(frozen=True)
class StandoffOption:
    """One owner may only dissolve its own present column at this contact."""
    id: Identity
    actor_ref: EntityRef
    standoff_id: Identity
    detachment_id: Identity

    def decision(self):
        return {"action": STAND_DOWN_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class WithdrawalOption:
    """A current, owner-known route from a standing column to own government."""
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    destination_id: Identity
    route_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": WITHDRAW_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class ForcePositionOption:
    """One own supplied column may prepare where it already stands."""
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    settlement_id: Identity
    anchor_site_id: Identity | None

    def decision(self):
        return {"action": PREPARE_POSITION_ACTION, "actor_ref": self.actor_ref.to_dict(),
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
        raise ValueError("force action requires a current actor decision")
    try:
        actor = EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("force decision has an invalid actor") from exc
    return event, actor


def _commands(world, actor):
    return isinstance(actor, EntityRef) and can_actor_act_for(world, actor, actor, "military")


def _own_stock(world, actor, settlement_id):
    return next((item for _, item in sorted(world.economy.stocks.items())
                 if item.owner_ref == actor and item.location_id == settlement_id), None)


def _own_account(world, actor):
    return next((item for _, item in sorted(world.economy.accounts.items()) if item.owner_ref == actor), None)


def raise_options(world, actor, days=10):
    """Detachments this institution could raise today from its own means."""
    if not _commands(world, actor):
        return ()
    options = []
    for group_id in sorted(world.society.population):
        group = world.society.population[group_id]
        settlement = world.society.settlements[group.settlement_id]
        if (group.occupation != "soldier" or settlement.administrator_id != actor.id
                or world.society.available_count(group_id) <= 0):
            continue
        stock = _own_stock(world, actor, group.settlement_id)
        account = _own_account(world, actor)
        if stock is None or account is None:
            continue
        free_food = stock.goods.get("food", 0) - reserve_quantity(world, stock.id, "food")
        for destination_id in sorted(world.society.settlements):
            if destination_id == group.settlement_id:
                continue
            route = known_supply_path(world, actor, group.settlement_id, destination_id, "food")
            if not route:
                continue
            count = min(world.society.available_count(group_id), max(0, free_food // (RATIONS_PER_SOLDIER_DAY * days)))
            provisions = count * RATIONS_PER_SOLDIER_DAY * days
            if count <= 0 or account.balance < count * WAGE_PER_SOLDIER:
                continue
            options.append(RaiseOption(
                id=(f"raise-detachment:{actor.id}:{group_id}:{destination_id}:{count}:{provisions}:"
                    f"{'-'.join(route)}"),
                actor_ref=actor, group_id=group_id, settlement_id=group.settlement_id, stock_id=stock.id,
                account_id=account.id, count=count, provisions=provisions, destination_id=destination_id,
                route_ids=tuple(route)))
    return tuple(sorted(options, key=lambda item: item.id))


def raise_detachment(world, actor, option_id, decision_event_id, *, days=10):
    """Soldiers and rations leave their owners; wages are paid at once."""
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, RAISE_ACTION)
    if decided_by != actor:
        raise ValueError("raising a detachment has the wrong actor")
    option = next((item for item in raise_options(candidate, actor, days=days) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("raise option is stale or unknown")
    require_authority(candidate, actor, "military")
    # The dated reports make this a valid choice for the actor, but the force
    # owner still cannot send people over a passage that has physically closed
    # since that observation.  Keep the selected route exact: a different
    # current route is a new affordance, never an implicit reroute.
    if not _route_is_current(candidate, option.settlement_id, option.destination_id, option.route_ids):
        raise ValueError("raise route is no longer possible")
    identity = f"detachment:{decision.id}"
    if identity in candidate.society.detachments:
        raise ValueError("raise decision already used")
    candidate.society._select_people(option.group_id, option.count, ())
    stock = candidate.economy.stocks[option.stock_id]
    food = stock.goods.get("food", 0)
    day = candidate.clock.absolute_day
    event = record_event(candidate, "detachment_raised",
                         f"{option.count} soldados partiram com {option.provisions} rações.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("stock", stock.id, "food", food, food - option.provisions),
                                 _delta("detachment", identity, "stage", None, "marching"),
                                 _delta("detachment", identity, "provisions", 0, option.provisions)),
                         cause_ids=_causes(decision.id, stock.last_event_ids.get("food")))
    candidate.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, "food": food - option.provisions},
        "last_event_ids": {**stock.last_event_ids, "food": event.id}})
    detachment = Detachment(id=identity, owner_ref=actor, source_group_id=option.group_id, count=option.count,
                            location_id=option.settlement_id, destination_id=option.destination_id,
                            route_ids=option.route_ids, provisions=option.provisions, stage="marching",
                            started_day=day, due_day=day + 1, decision_event_id=decision.id, last_event_id=event.id)
    candidate.society.detachments[detachment.id] = detachment
    # The detachment is already registered, so ``monthly_workforce`` correctly
    # removes its soldiers from ordinary local availability.  Initial military
    # payroll is nevertheless owed to those same soldiers; make that explicit
    # for this one receipt instead of making detached people available to other
    # employers.
    payroll_available = monthly_workforce(candidate)
    payroll_available[option.group_id] += option.count
    settle_work(candidate, work_id=detachment.id, account_id=option.account_id, stock_id=option.stock_id,
                occupation="soldier", worker_count=option.count, wage=WAGE_PER_SOLDIER,
                available=payroll_available, production_event_id=event.id)
    candidate.agenda.schedule(ScheduledSituation(detachment.id, "force", detachment.due_day))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachments[detachment.id]


def _rival_present(world, detachment):
    """Canonical, owner-side check: is another force actually standing here?

    This is never used to build an option. It only lets the material owner
    refuse an occupation that has become impossible, and it discloses nothing:
    the caller learns a refusal, not who is there or with what.
    """
    return any(item.location_id == detachment.location_id and item.owner_ref != detachment.owner_ref
               and item.stage != "disbanded" for item in world.society.detachments.values())


def _standoff_id(left_id, right_id):
    left_id, right_id = sorted((left_id, right_id))
    return f"force-standoff:{left_id}:{right_id}"


def _strength_band(count):
    if count <= 9:
        return "1-9"
    if count <= 24:
        return "10-24"
    if count <= 49:
        return "25-49"
    if count <= 99:
        return "50-99"
    return "100+"


def _sighting_posture(world, detachment_id, leaving_ids=()):
    if detachment_id in set(leaving_ids):
        return "leaving"
    position = world.society.force_positions.get(_position_id(detachment_id))
    return "fortified" if position is not None and position.stage == "prepared" else "present"


def observe_force_contact_sightings(world, standoff, *, leaving_ids=(), extra_cause_ids=()):
    """Refresh only changed bounded readings while Society retains the truth."""
    changes = []
    for notice in world.knowledge.force_contact_notices.values():
        if notice.standoff_id != standoff.id:
            continue
        other_id = next(item for item in standoff.detachment_ids if item != notice.own_detachment_id)
        other = world.society.detachments.get(other_id)
        if other is None:
            continue
        band, posture = _strength_band(other.count), _sighting_posture(world, other.id, leaving_ids)
        if (notice.counterparty_strength_band, notice.counterparty_posture) != (band, posture):
            changes.append((notice, band, posture))
    if not changes:
        return None
    event = record_event(
        world, "force_contact_sighting_observed", "A leitura limitada de uma coluna rival foi atualizada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(delta for notice, band, posture in changes for delta in (
            *(() if band == notice.counterparty_strength_band else
              (_delta("force_contact_notice", notice.id, "counterparty_strength_band",
                      notice.counterparty_strength_band, band),)),
            *(() if posture == notice.counterparty_posture else
              (_delta("force_contact_notice", notice.id, "counterparty_posture",
                      notice.counterparty_posture, posture),)),
            _delta("force_contact_notice", notice.id, "learned_day", notice.learned_day,
                   world.clock.absolute_day))),
        cause_ids=_causes(standoff.last_event_id,
                          *(world.society.detachments[item].last_event_id for item in standoff.detachment_ids
                            if item in world.society.detachments), *extra_cause_ids),
    )
    for notice, band, posture in changes:
        world.knowledge.force_contact_notices[notice.id] = notice.model_copy(update={
            "counterparty_strength_band": band, "counterparty_posture": posture,
            "learned_day": world.clock.absolute_day, "last_event_id": event.id})
    return event


def _active_pair(world, standoff):
    left_id, right_id = standoff.detachment_ids
    left = world.society.detachments.get(left_id)
    right = world.society.detachments.get(right_id)
    if (left is None or right is None or left.owner_ref == right.owner_ref
            or left.stage != "present" or right.stage != "present"
            or left.location_id != standoff.settlement_id or right.location_id != standoff.settlement_id):
        return None
    return left, right


def detect_force_standoffs(world, detachment_id=None):
    """Record actual co-presence as a fact, never as a battle or a demand."""
    candidates = (world.society.detachments.get(detachment_id),) if detachment_id is not None else tuple(
        item for _, item in sorted(world.society.detachments.items()))
    created = []
    for detachment in candidates:
        if detachment is None or detachment.stage != "present":
            continue
        rivals = tuple(item for _, item in sorted(world.society.detachments.items())
                       if item.id != detachment.id and item.stage == "present"
                       and item.location_id == detachment.location_id and item.owner_ref != detachment.owner_ref)
        for rival in rivals:
            identity = _standoff_id(detachment.id, rival.id)
            if identity in world.society.force_standoffs:
                observe_force_contact_sightings(world, world.society.force_standoffs[identity])
                continue
            left_id, right_id = sorted((detachment.id, rival.id))
            standoff = ForceStandoff(id=identity, detachment_ids=(left_id, right_id),
                                     settlement_id=detachment.location_id,
                                     started_day=world.clock.absolute_day, started_event_id="pending",
                                     last_event_id="pending")
            event = record_event(
                world, "armed_standoff_started", "Duas colunas rivais passaram a se encarar; nenhum combate ocorreu.",
                fact_kind=FactKind.STATE_TRANSITION,
                deltas=(_delta("force_standoff", identity, "stage", None, "active"),),
                cause_ids=_causes(detachment.last_event_id, rival.last_event_id),
            )
            standoff = standoff.model_copy(update={"started_event_id": event.id, "last_event_id": event.id})
            world.society.force_standoffs[identity] = standoff
            notices = []
            for own, other in ((detachment, rival), (rival, detachment)):
                notice = ForceContactNotice(
                    id=force_contact_notice_id(identity, own.owner_ref), recipient_ref=own.owner_ref,
                    standoff_id=identity, own_detachment_id=own.id, counterparty_ref=other.owner_ref,
                    settlement_id=detachment.location_id, event_id="pending", learned_day=world.clock.absolute_day,
                    counterparty_strength_band=_strength_band(other.count),
                    counterparty_posture=_sighting_posture(world, other.id),
                    last_event_id="pending",
                )
                notices.append(notice)
            observation = record_event(
                world, "armed_standoff_observed", "As duas colunas reconheceram uma presença armada rival.",
                fact_kind=FactKind.STATE_TRANSITION,
                deltas=tuple(delta for notice in notices for delta in (
                    _delta("force_contact_notice", notice.id, "observation", None, identity),
                    _delta("force_contact_notice", notice.id, "counterparty_strength_band", None,
                           notice.counterparty_strength_band),
                    _delta("force_contact_notice", notice.id, "counterparty_posture", None,
                           notice.counterparty_posture),
                    _delta("force_contact_notice", notice.id, "learned_day", None, notice.learned_day))),
                cause_ids=(event.id,),
            )
            for notice in notices:
                world.knowledge.force_contact_notices[notice.id] = notice.model_copy(
                    update={"event_id": observation.id, "last_event_id": observation.id})
            from .force_contact_policy import schedule_contact_review
            for notice in notices:
                schedule_contact_review(world, notice, world.clock.absolute_day + 1)
            created.append(world.society.force_standoffs[identity])
    return tuple(created)


def _resolve_standoffs_for(world, detachment_id, cause_event_id):
    """Removing physical co-presence closes its factual contact, never a war."""
    resolved = []
    for standoff in tuple(world.society.force_standoffs.values()):
        if standoff.stage != "active" or detachment_id not in standoff.detachment_ids:
            continue
        if _active_pair(world, standoff) is not None:
            continue
        # A voluntary withdrawal is the one material transition that a rival
        # can physically read as departure before the contact freezes.
        if world.society.detachments.get(detachment_id, None) is not None and \
                world.society.detachments[detachment_id].stage == "marching":
            sighting = observe_force_contact_sightings(world, standoff, leaving_ids=(detachment_id,))
            if sighting is not None:
                standoff = world.society.force_standoffs[standoff.id]
        event = record_event(
            world, "armed_standoff_resolved", "A co-presença armada cessou sem combate.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("force_standoff", standoff.id, "stage", "active", "resolved"),),
            cause_ids=_causes(cause_event_id, standoff.last_event_id),
        )
        world.society.force_standoffs[standoff.id] = standoff.model_copy(
            update={"stage": "resolved", "resolved_day": world.clock.absolute_day, "last_event_id": event.id})
        resolved.append(world.society.force_standoffs[standoff.id])
    return tuple(resolved)


def standoff_options(world, actor):
    """A known participant may stand down; it may not choose any harm."""
    if not _commands(world, actor):
        return ()
    options = []
    for notice in world.knowledge.force_contacts_for_actor(actor):
        standoff = world.society.force_standoffs.get(notice.standoff_id)
        if standoff is None or standoff.stage != "active":
            continue
        own = world.society.detachments.get(notice.own_detachment_id)
        if (own is None or own.owner_ref != actor or own.stage != "present"
                or own.location_id != standoff.settlement_id
                or notice.settlement_id != standoff.settlement_id):
            continue
        options.append(StandoffOption(
            id=f"force-standoff:{standoff.id}:{own.last_event_id}:{standoff.last_event_id}:stand-down",
            actor_ref=actor, standoff_id=standoff.id, detachment_id=own.id))
    return tuple(sorted(options, key=lambda item: item.id))


def force_options(world, actor):
    """What a standing detachment of this institution could decide today.

    Options are composed from the actor's own detachments and its own dated
    settlement reports. No foreign detachment is read here: an occupier seen in
    the actor's own report is valid knowledge, a rival column is not.
    """
    if not _commands(world, actor):
        return ()
    options = []
    for _, detachment in sorted(world.society.detachments.items()):
        if detachment.owner_ref != actor or detachment.stage == "disbanded":
            continue
        base = f"force:{detachment.id}:{detachment.last_event_id}"
        options.append(ForceOption(f"{base}:disband", actor, detachment.id, "disband"))
        settlement = world.society.settlements[detachment.location_id]
        report = world.knowledge.settlement_report(actor, detachment.location_id)
        if (detachment.stage == "present" and detachment.provisions > 0
                and settlement.administrator_id != actor.id
                and report is not None and report.settlement_id == detachment.location_id
                and report.occupier_id is None):
            options.append(ForceOption(f"{base}:occupy", actor, detachment.id, "occupy"))
    return tuple(options)


def _route_is_current(world, origin_id, destination_id, route_ids):
    """Owner-side Map revalidation for one exact selected route."""
    if not route_ids or origin_id not in world.society.settlements or destination_id not in world.society.settlements:
        return False
    region = world.society.settlements[origin_id].region_id
    target = world.society.settlements[destination_id].region_id
    seen = {region}
    for route_id in route_ids:
        route = world.map.routes.get(route_id)
        if (route is None or region not in route.endpoint_region_ids or not route.allows_resource("food")
                or world.map.get_route_operational_capacity(route_id) <= 0):
            return False
        region = next(item for item in route.endpoint_region_ids if item != region)
        if region in seen:
            return False
        seen.add(region)
    return region == target


def withdrawal_options(world, actor, *, detachment_id=None):
    """Only own present columns may choose a reported route to own government.

    The composition intentionally does not consult any foreign detachment,
    inventory, route plan or authority.  A real pending campaign shipment
    makes the option absent rather than relocating its cargo.
    """
    if not _commands(world, actor):
        return ()
    from .campaign_supply import campaign_baggage_ready_for_departure

    options = []
    for _, detachment in sorted(world.society.detachments.items()):
        if (detachment.owner_ref != actor or detachment.stage != "present" or detachment.provisions <= 0
                or (detachment_id is not None and detachment.id != detachment_id)
                or not campaign_baggage_ready_for_departure(world, detachment)):
            continue
        for destination_id, settlement in sorted(world.society.settlements.items()):
            if destination_id == detachment.location_id or settlement.administrator_id != actor.id:
                continue
            report = world.knowledge.settlement_report(actor, destination_id)
            if report is None or report.settlement_id != destination_id:
                continue
            route_ids = known_supply_path(world, actor, detachment.location_id, destination_id, "food")
            if not route_ids:
                continue
            options.append(WithdrawalOption(
                id=(f"withdraw:{detachment.id}:{detachment.last_event_id}:{destination_id}:{'-'.join(route_ids)}"),
                actor_ref=actor, detachment_id=detachment.id, destination_id=destination_id,
                route_ids=tuple(route_ids)))
    return tuple(sorted(options, key=lambda item: item.id))


def _position_id(detachment_id):
    return f"force-position:{detachment_id}"


def force_position_options(world, actor, *, detachment_id=None):
    """Current preparation choices, composed only from the owner's column and Map.

    The optional anchor is only an existing site in this settlement's region.
    It creates no terrain rule, defensive value, route restriction or control.
    """
    if not _commands(world, actor):
        return ()
    options = []
    for detachment in world.society.detachments.values():
        if (detachment.owner_ref != actor or detachment.stage != "present"
                or (detachment_id is not None and detachment.id != detachment_id)
                or _position_id(detachment.id) in world.society.force_positions
                or detachment.provisions < POSITION_PREPARATION_DAYS * detachment.count):
            continue
        settlement = world.society.settlements[detachment.location_id]
        anchors = (None, *sorted(site.id for site in world.map.infrastructure_sites.values()
                                 if settlement.region_id in site.region_ids))
        for anchor_site_id in anchors:
            anchor = anchor_site_id or "none"
            options.append(ForcePositionOption(
                id=f"force-position:{detachment.id}:{detachment.last_event_id}:{settlement.id}:{anchor}",
                actor_ref=actor, detachment_id=detachment.id, settlement_id=settlement.id,
                anchor_site_id=anchor_site_id))
    return tuple(sorted(options, key=lambda item: item.id))


def prepare_force_position(world, actor, option_id, decision_event_id):
    """Begin a three-day stationary preparation; only daily upkeep can finish it."""
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, PREPARE_POSITION_ACTION)
    if decided_by != actor:
        raise ValueError("force position has the wrong actor")
    option = next((item for item in force_position_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("force position option is stale or unknown")
    require_authority(candidate, actor, "military")
    detachment = candidate.society.detachments[option.detachment_id]
    position = ForcePosition(id=_position_id(detachment.id), detachment_id=detachment.id,
                             settlement_id=detachment.location_id, anchor_site_id=option.anchor_site_id,
                             started_day=candidate.clock.absolute_day,
                             ready_day=candidate.clock.absolute_day + POSITION_PREPARATION_DAYS,
                             last_event_id="pending")
    event = record_event(
        candidate, "force_position_preparing", "A coluna iniciou três dias de preparo no local onde está.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("force_position", position.id, "stage", None, "preparing"),
                _delta("force_position", position.id, "settlement_id", None, position.settlement_id),
                _delta("force_position", position.id, "anchor_site_id", None, position.anchor_site_id),
                _delta("force_position", position.id, "ready_day", None, position.ready_day)),
        cause_ids=_causes(decision.id, detachment.last_event_id))
    candidate.society.force_positions[position.id] = position.model_copy(update={"last_event_id": event.id})
    candidate.agenda.schedule(ScheduledSituation(position.id, "force_preparation", position.ready_day))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.force_positions[position.id]


def _abandon_force_position(world, detachment, *, cause_ids=()):
    """Leaving, lapsed supply or location change never erases preparation silently."""
    position = world.society.force_positions.get(_position_id(detachment.id))
    if position is None:
        return None
    from .assembly_denial import revoke_assembly_denials_for
    revoke_assembly_denials_for(world, detachment, cause_ids=_causes(position.last_event_id, *cause_ids))
    event = record_event(
        world, "force_position_abandoned", "A posição foi abandonada porque a coluna não permaneceu no local.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("force_position", position.id, "stage", position.stage, None),),
        cause_ids=_causes(position.last_event_id, detachment.last_event_id, *cause_ids))
    del world.society.force_positions[position.id]
    world.agenda.cancel(position.id)
    return event


def _refresh_position_sightings(world, detachment, event):
    for standoff in tuple(world.society.force_standoffs.values()):
        if standoff.stage == "active" and detachment.id in standoff.detachment_ids:
            observe_force_contact_sightings(world, standoff, extra_cause_ids=(event.id,))


def resolve_force_positions(world, situations):
    """A dated completion proves three supplied stationary days, nothing else."""
    for situation in sorted(situations, key=lambda item: item.id):
        if situation.kind != "force_preparation":
            raise ValueError("unknown force preparation")
        position = world.society.force_positions.get(situation.id)
        # A force resolver may have lapsed or dissolved the column earlier in
        # this same dated turn, recording the explicit abandonment itself.
        if position is None:
            continue
        if position.stage != "preparing" or position.ready_day != world.clock.absolute_day:
            raise ValueError("inconsistent force preparation deadline")
        detachment = world.society.detachments.get(position.detachment_id)
        if (detachment is None or detachment.stage != "present"
                or detachment.location_id != position.settlement_id):
            if detachment is not None:
                _abandon_force_position(world, detachment, cause_ids=(position.last_event_id,))
            continue
        event = record_event(
            world, "force_position_prepared", "A coluna concluiu o preparo sem ganhar território ou iniciar combate.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("force_position", position.id, "stage", "preparing", "prepared"),),
            cause_ids=_causes(position.last_event_id, detachment.last_event_id))
        world.society.force_positions[position.id] = position.model_copy(update={"stage": "prepared",
                                                                                   "last_event_id": event.id})
        _refresh_position_sightings(world, detachment, event)
        from .rites import observe_rites
        observe_rites(world, settlement_id=detachment.location_id)


def _record(world, detachment, updated, event_type, content, *, deltas=(), causes=()):
    lifted = ()
    assembly_lifted = ()
    command_released = None
    # A command is a real person's local duty, never a passenger hidden inside
    # a marching or dissolved record.  End it before the force transition so
    # both receipts explain the same physical change and the person remains at
    # the column's current location.
    if updated.stage != "present" or updated.location_id != detachment.location_id:
        from .force_command import revoke_detachment_command_for
        command_released = revoke_detachment_command_for(world, detachment, cause_ids=causes)
    if (updated.stage != "present" or updated.location_id != detachment.location_id
            or updated.provisions < updated.count * RATIONS_PER_SOLDIER_DAY):
        from .assembly_denial import revoke_assembly_denials_for
        assembly_lifted = revoke_assembly_denials_for(world, detachment, cause_ids=causes)
    if updated.stage != "present" or updated.location_id != detachment.location_id:
        # Departure, movement, dissolution and lapse end only this physical
        # route cause before the force transition itself is recorded.
        from .settlement_investment import revoke_settlement_investments_for
        from .route_interdiction import revoke_route_interdictions_for
        lifted = (*revoke_settlement_investments_for(world, detachment, cause_ids=causes),
                  *revoke_route_interdictions_for(world, detachment, cause_ids=causes))
    abandoned = None
    position = world.society.force_positions.get(_position_id(detachment.id))
    if position is not None and (updated.stage != "present" or updated.location_id != position.settlement_id):
        abandoned = _abandon_force_position(world, detachment, cause_ids=causes)
    event = record_event(world, event_type, content, fact_kind=FactKind.STATE_TRANSITION, deltas=deltas,
                         cause_ids=_causes(detachment.last_event_id, *causes,
                                            *(item.id for item in lifted),
                                            *(item.id for item in assembly_lifted),
                                            *((command_released.id,) if command_released is not None else ()),
                                            *((abandoned.id,) if abandoned is not None else ())))
    world.society.detachments[detachment.id] = updated.model_copy(update={"last_event_id": event.id})
    # A dated resolution has already popped the current situation.  Manual
    # receipts can also replace a pending one, so make rescheduling idempotent.
    world.agenda.cancel(detachment.id)
    if updated.stage == "disbanded":
        # The record stays as history, with its payroll; only the duty ends.
        pass
    else:
        world.agenda.schedule(ScheduledSituation(detachment.id, "force", updated.due_day))
    return event


def _return_home(world, detachment):
    """Survivors rejoin a real cohort exactly where the detachment stands."""
    group = world.society.population[detachment.source_group_id]
    if group.settlement_id == detachment.location_id:
        return ()
    target_id = world.society.transfer_people(detachment.source_group_id, detachment.location_id,
                                              "soldier", detachment.count)
    return (_delta("population_group", detachment.source_group_id, "count", group.count,
                   group.count - detachment.count),
            _delta("population_group", target_id, "count",
                   world.society.population[target_id].count - detachment.count,
                   world.society.population[target_id].count))


def _clear_occupation(world, detachment):
    settlement = world.society.settlements[detachment.location_id]
    if settlement.occupier_id != detachment.owner_ref.id:
        return ()
    world.society.set_occupation(settlement.id, None)
    return (_delta("settlement", settlement.id, "occupier_id", detachment.owner_ref.id, None),)


def _dissolve(world, detachment, event_type, content, causes=()):
    """One fact: occupation clears, people land, the duty ends."""
    deltas = (*_clear_occupation(world, detachment),)
    # People move before the receipt so the delta states the real counts.
    moved = _return_home(world, detachment)
    ended = detachment.model_copy(update={"stage": "disbanded", "provisions": 0,
                                          "due_day": world.clock.absolute_day})
    event = _record(world, detachment, ended, event_type, content,
                    deltas=(*deltas, *moved,
                            _delta("detachment", detachment.id, "stage", detachment.stage, "disbanded")),
                    causes=causes)
    # A campaign bag is an Economy stock, never a hidden field on a force.
    # Dispose of anything already co-located before this physical presence is
    # forgotten; later cargo is handled by the same campaign owner.
    from .campaign_supply import dispose_campaign_baggage
    dispose_campaign_baggage(world, detachment, event.id)
    _resolve_standoffs_for(world, detachment.id, event.id)
    return event


def execute_force_option(world, actor, option_id, decision_event_id, action):
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, action)
    if decided_by != actor:
        raise ValueError("force action has the wrong actor")
    option = next((item for item in force_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("force option is stale or unknown")
    require_authority(candidate, actor, "military")
    detachment = candidate.society.detachments[option.detachment_id]
    if option.kind == "occupy":
        settlement = candidate.society.settlements[detachment.location_id]
        # The owner revalidates the physical fact the actor cannot see; the
        # refusal states nothing about who else is standing there.
        if settlement.occupier_id is not None or _rival_present(candidate, detachment):
            raise ValueError("occupation is no longer possible at this place")
        candidate.society.set_occupation(settlement.id, actor.id)
        _record(candidate, detachment, detachment, "settlement_occupied",
                f"{settlement.name}: ocupada por presença armada; a administração não mudou.",
                deltas=(_delta("settlement", settlement.id, "occupier_id", None, actor.id),),
                causes=(decision.id,))
    else:
        _dissolve(candidate, detachment, "detachment_disbanded",
                  "O destacamento foi dissolvido; as pessoas voltaram a uma coorte local.",
                  causes=(decision.id,))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachments.get(option.detachment_id)


def occupy_settlement(world, actor, option_id, decision_event_id):
    return execute_force_option(world, actor, option_id, decision_event_id, OCCUPY_ACTION)


def disband_detachment(world, actor, option_id, decision_event_id):
    return execute_force_option(world, actor, option_id, decision_event_id, DISBAND_ACTION)


def stand_down_from_standoff(world, actor, option_id, decision_event_id):
    """A participant ends only its own real presence at a recognized contact."""
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, STAND_DOWN_ACTION)
    if decided_by != actor:
        raise ValueError("standoff action has the wrong actor")
    option = next((item for item in standoff_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("standoff option is stale or unknown")
    require_authority(candidate, actor, "military")
    detachment = candidate.society.detachments[option.detachment_id]
    standoff = candidate.society.force_standoffs[option.standoff_id]
    if _active_pair(candidate, standoff) is None:
        raise ValueError("armed contact is no longer current")
    _dissolve(candidate, detachment, "detachment_stood_down",
              "A coluna baixou as armas e foi dissolvida onde estava; nenhum território mudou de dono.",
              causes=(decision.id,))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachments[option.detachment_id]


def withdraw_detachment(world, actor, option_id, decision_event_id):
    """Begin a real withdrawal; later dated force ticks carry it home."""
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, WITHDRAW_ACTION)
    if decided_by != actor:
        raise ValueError("withdrawal has the wrong actor")
    option = next((item for item in withdrawal_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("withdrawal option is stale or unknown")
    _begin_withdrawal(candidate, actor, option, decision_event_id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachments[option.detachment_id]


def _begin_withdrawal(world, actor, option, decision_event_id):
    """Owner-side material start shared by direct and commitment fulfillment."""
    require_authority(world, actor, "military")
    detachment = world.society.detachments[option.detachment_id]
    destination = world.society.settlements[option.destination_id]
    if (destination.administrator_id != actor.id
            or not _route_is_current(world, detachment.location_id, option.destination_id, option.route_ids)):
        raise ValueError("withdrawal is no longer possible")
    from .campaign_supply import campaign_baggage_ready_for_departure
    if not campaign_baggage_ready_for_departure(world, detachment):
        raise ValueError("withdrawal is no longer possible")
    updated = detachment.model_copy(update={"destination_id": option.destination_id, "route_ids": option.route_ids,
                                             "route_index": 0, "stage": "marching",
                                             "due_day": world.clock.absolute_day + 1})
    event = _record(
        world, detachment, updated, "detachment_withdrawal_started",
        "A coluna deixou a ocupação e iniciou a retirada por uma rota conhecida até sua própria administração.",
        deltas=(*_clear_occupation(world, detachment),
                _delta("detachment", detachment.id, "destination_id", detachment.destination_id, option.destination_id),
                _delta("detachment", detachment.id, "route_ids", detachment.route_ids, option.route_ids),
                _delta("detachment", detachment.id, "route_index", detachment.route_index, 0),
                _delta("detachment", detachment.id, "stage", "present", "marching")),
        causes=(decision_event_id,))
    _resolve_standoffs_for(world, detachment.id, event.id)
    return event


def _advance(world, detachment):
    """One dated leg over a route that must still be physically usable."""
    route_id = detachment.route_ids[detachment.route_index]
    day = world.clock.absolute_day
    if world.map.get_route_operational_capacity(route_id) <= 0:
        return _record(world, detachment, detachment.model_copy(update={"due_day": day + 1}),
                       "detachment_held", "Passagem indisponível; a coluna aguarda.",
                       deltas=(_delta("detachment", detachment.id, "due_day", detachment.due_day, day + 1),))
    index = detachment.route_index + 1
    arrived = index >= len(detachment.route_ids)
    location = detachment.destination_id if arrived else detachment.location_id
    updated = detachment.model_copy(update={"route_index": index, "location_id": location,
                                            "stage": "present" if arrived else "marching",
                                            "due_day": day + (1 if arrived else route_duration(world, route_id))})
    event = _record(world, detachment, updated,
                    "detachment_arrived" if arrived else "detachment_marched",
                    "A coluna chegou ao destino." if arrived else "A coluna avançou um trecho.",
                    deltas=(_delta("detachment", detachment.id, "route_index", detachment.route_index, index),
                            _delta("detachment", detachment.id, "location_id", detachment.location_id, location),
                            _delta("detachment", detachment.id, "stage", detachment.stage, updated.stage),
                            *_move_empty_campaign_baggage(world, detachment, location)))
    if arrived:
        # Standing there is observation, not control: the owner learns the
        # place through its own dated report and gains nothing else.
        from .settlement_intelligence import observe_present_force
        observe_present_force(world, detachment.id)
        detect_force_standoffs(world, detachment.id)
    return event


def _move_empty_campaign_baggage(world, detachment, location_id):
    """The empty temporary bag follows its real column, never its cargo."""
    from .campaign_supply import campaign_baggage_ready_for_departure, campaign_stock_id

    stock = world.economy.stocks.get(campaign_stock_id(detachment.id))
    if stock is None or stock.location_id == location_id:
        return ()
    if not campaign_baggage_ready_for_departure(world, detachment):
        raise ValueError("a committed campaign bag cannot move with withdrawal")
    world.economy.stocks[stock.id] = stock.model_copy(update={"location_id": location_id})
    return (_delta("stock", stock.id, "location_id", stock.location_id, location_id),)


def resolve_forces(world, situations):
    """Daily upkeep: eat, then move. Arrival alone changes no control."""
    for situation in situations:
        detachment = world.society.detachments.get(situation.id)
        if (situation.kind != "force" or detachment is None
                or detachment.due_day != world.clock.absolute_day):
            raise ValueError("unknown or inconsistent dated force")
        eaten = detachment.count * RATIONS_PER_SOLDIER_DAY
        if detachment.provisions < eaten:
            _dissolve(world, detachment, "detachment_lapsed",
                      "Sem provisões, a presença armada cessou; nenhuma vitória foi produzida.")
            continue
        fed = detachment.model_copy(update={"provisions": detachment.provisions - eaten,
                                            "due_day": world.clock.absolute_day + 1})
        _record(world, detachment, fed, "detachment_supplied", f"A coluna consumiu {eaten} rações.",
                deltas=(_delta("detachment", detachment.id, "provisions", detachment.provisions, fed.provisions),))
        current = world.society.detachments[detachment.id]
        if current.stage == "marching":
            _advance(world, current)
        elif current.stage == "present":
            # A persisted physical contact remains a fact even when both
            # columns were loaded or arrived in a different resolver order.
            detect_force_standoffs(world, current.id)

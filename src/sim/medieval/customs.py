"""Material civil customs: presentation, declaration or attempted evasion.

This deliberately models neither blockade nor confiscation.  A checkpoint
holds one parcel while its owner decides, and never changes ownership, route
topology, quantity, or the parcel's agreed destination.
"""

import math

from src.classes.economy.customs import CargoManifest, CustomsCheckpoint
from src.classes.economy.models import MoneyAccount, Payroll
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.models import CustomsNotice
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity, SocietyValue
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _causes, _delta
from .events import record_event


CUSTOMS_SITE_KINDS = frozenset({"port", "mountain_pass"})
CUSTOMS_STAFF_WAGE = 1
CUSTOMS_FEE_PER_BULK = 1
# Both laws are fixed engine constants.  The actor can decide to attempt
# evasion, but cannot choose a probability, target, or result.
CUSTOMS_INSPECTIONS_PER_STAFF_PER_DAY = 2
CUSTOMS_DETECTION_PERMILLE = 350


def _current_cycle(day):
    """A payroll at the month boundary staffs the following dated cycle."""
    return day // 30


class CustomsOpenOption(SocietyValue):
    id: Identity
    site_id: Identity
    actor_ref: EntityRef
    account_id: Identity
    staff_group_id: Identity
    staff_count: int
    fee_per_bulk: int

    def decision(self):
        return {"action": "open_customs_checkpoint", "actor_ref": self.actor_ref.to_dict(),
                "option_id": self.id, "site_id": self.site_id, "account_id": self.account_id,
                "staff_group_id": self.staff_group_id, "staff_count": self.staff_count,
                "fee_per_bulk": self.fee_per_bulk}


class CustomsPaymentOption(SocietyValue):
    id: Identity
    notice_id: Identity
    parcel_id: Identity
    checkpoint_id: Identity
    actor_ref: EntityRef
    account_id: Identity
    fee: int

    def decision(self):
        return {"action": "pay_customs_fee", "actor_ref": self.actor_ref.to_dict(),
                "option_id": self.id, "notice_id": self.notice_id, "parcel_id": self.parcel_id,
                "checkpoint_id": self.checkpoint_id, "account_id": self.account_id, "fee": self.fee}


class CustomsCargoOption(SocietyValue):
    """One current, exact action over a presented parcel.

    ``action`` is deliberately an engine-selected verb; no editable amount,
    odds, route, or checkpoint ever reaches an actor decision.
    """
    id: Identity
    action: str
    notice_id: Identity
    checkpoint_id: Identity
    parcel_id: Identity
    order_id: Identity
    actor_ref: EntityRef
    resource_id: Identity
    quantity: int

    def decision(self):
        return {"action": self.action, "actor_ref": self.actor_ref.to_dict(), "option_id": self.id,
                "notice_id": self.notice_id, "checkpoint_id": self.checkpoint_id,
                "parcel_id": self.parcel_id, "order_id": self.order_id,
                "resource_id": self.resource_id, "quantity": self.quantity}


def _local_staff(world, site, actor):
    """The smallest local civil group that can staff this one-post V1 service."""
    groups = [group for group in world.society.population.values()
              if world.society.settlements[group.settlement_id].region_id in site.region_ids
              and world.society.available_count(group.id) > 0]
    # Merchant work is preferred but not magically required: the world may only
    # have residents with another current occupation at a valid checkpoint.
    groups.sort(key=lambda item: (item.occupation != "merchant", item.id))
    return groups[0] if groups else None


def _operator_can_run(world, actor):
    return all(can_actor_act_for(world, actor, actor, scope) for scope in ("supply", "trade", "taxation"))


def customs_open_options(world, site_id, actor_ref):
    """Exact opening affordances; terms are engine-owned rather than prose."""
    if not isinstance(actor_ref, EntityRef):
        return ()
    site = world.map.infrastructure_sites.get(site_id)
    if (site is None or site.kind not in CUSTOMS_SITE_KINDS or site.owner_ref != actor_ref
            or site_id in {item.site_id for item in world.economy.customs_checkpoints.values()}
            or not _operator_can_run(world, actor_ref)):
        return ()
    staff = _local_staff(world, site, actor_ref)
    if staff is None:
        return ()
    accounts = sorted((account for account in world.economy.accounts.values() if account.owner_ref == actor_ref),
                      key=lambda item: item.id)
    return tuple(
        CustomsOpenOption(
            id=(f"customs-open:{site.id}:{actor_ref.kind}:{actor_ref.id}:{account.id}:{staff.id}:"
                f"{site.last_event_id}:{account.last_event_id}:{staff.last_event_id}:"
                f"{site.integrity:g}:{int(site.enabled)}:{int(site.service_suspended)}"),
            site_id=site.id, actor_ref=actor_ref, account_id=account.id, staff_group_id=staff.id,
            staff_count=1, fee_per_bulk=CUSTOMS_FEE_PER_BULK,
        ) for account in accounts
    )


def _event(world, event_id):
    return next((event for event in world.events if event.id == event_id), None)


def open_customs_checkpoint(world, option_id, *, decision_event_id):
    decision = _event(world, decision_event_id)
    payload = decision.decision if decision is not None else None
    try:
        actor = EntityRef.from_dict(payload.get("actor_ref")) if isinstance(payload, dict) else None
    except (KeyError, TypeError, ValueError):
        actor = None
    site_id = payload.get("site_id") if isinstance(payload, dict) else None
    option = next((item for item in customs_open_options(world, site_id, actor) if item.id == option_id), None)
    if (decision is None or decision.day != world.clock.absolute_day or decision.fact_kind != FactKind.DECISION
            or option is None or decision.decision != option.decision()):
        raise ValueError("customs opening option is stale")
    if any(event.event_type == "customs_opened" and any(link.cause_event_id == decision.id for link in event.causal_links)
           for event in world.events):
        raise ValueError("customs opening decision already executed")
    require_authority(world, option.actor_ref, "supply")
    require_authority(world, option.actor_ref, "trade")
    require_authority(world, option.actor_ref, "taxation")
    site = world.map.infrastructure_sites[option.site_id]
    account = world.economy.accounts.get(option.account_id)
    staff = world.society.population.get(option.staff_group_id)
    if (site.owner_ref != option.actor_ref or account is None or account.owner_ref != option.actor_ref
            or staff is None or world.society.settlements[staff.settlement_id].region_id not in site.region_ids
            or world.society.available_count(staff.id) < option.staff_count):
        raise ValueError("customs opening no longer has a local operator, account, or staff")
    checkpoint = CustomsCheckpoint(id=f"customs:{site.id}", site_id=site.id, operator_ref=option.actor_ref,
                                   account_id=option.account_id, staff_group_id=option.staff_group_id,
                                   staff_count=option.staff_count, fee_per_bulk=option.fee_per_bulk,
                                   started_day=world.clock.absolute_day, last_staffed_day=world.clock.absolute_day,
                                   inspection_day=world.clock.absolute_day)
    event = record_event(world, "customs_opened", f"{site.name}: posto alfandegário civil aberto.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("customs_checkpoint", checkpoint.id, "opened", False, True),),
                         cause_ids=_causes(decision.id, site.last_event_id, account.last_event_id, staff.last_event_id))
    world.economy.customs_checkpoints[checkpoint.id] = checkpoint.model_copy(update={"last_event_id": event.id})
    return event


def checkpoint_active(world, checkpoint):
    """Current staffing and physical service are both required for inspection."""
    site = world.map.infrastructure_sites.get(checkpoint.site_id)
    account = world.economy.accounts.get(checkpoint.account_id)
    staff = world.society.population.get(checkpoint.staff_group_id)
    return bool(
        site is not None and site.kind in CUSTOMS_SITE_KINDS and site.owner_ref == checkpoint.operator_ref
        and site.integrity >= 1.0 and site.enabled and not site.service_suspended
        and account is not None and account.owner_ref == checkpoint.operator_ref
        and staff is not None and world.society.settlements[staff.settlement_id].region_id in site.region_ids
        and world.society.available_count(staff.id) >= checkpoint.staff_count
        and _current_cycle(checkpoint.last_staffed_day) == _current_cycle(world.clock.absolute_day)
        and (payroll := world.economy.payrolls.get(checkpoint.id)) is not None
        and payroll.day == checkpoint.last_staffed_day
        and payroll.workers_by_group == {checkpoint.staff_group_id: checkpoint.staff_count}
        and _operator_can_run(world, checkpoint.operator_ref)
    )


def staff_customs_checkpoints(world, available):
    """Pay and reserve each named local staff group for this exact monthly cycle."""
    for checkpoint in sorted(world.economy.customs_checkpoints.values(), key=lambda item: item.id):
        if checkpoint.last_staffed_day == world.clock.absolute_day:
            continue
        site = world.map.infrastructure_sites.get(checkpoint.site_id)
        account = world.economy.accounts.get(checkpoint.account_id)
        staff = world.society.population.get(checkpoint.staff_group_id)
        if (site is None or site.owner_ref != checkpoint.operator_ref or site.integrity < 1.0
                or not site.enabled or site.service_suspended or account is None
                or account.owner_ref != checkpoint.operator_ref or staff is None
                or world.society.settlements[staff.settlement_id].region_id not in site.region_ids
                or available.get(staff.id, 0) < checkpoint.staff_count
                or account.balance < checkpoint.staff_count * CUSTOMS_STAFF_WAGE
                or not _operator_can_run(world, checkpoint.operator_ref)):
            continue
        household_id = f"household:{staff.id}"
        if household_id not in world.economy.accounts:
            world.economy.accounts[household_id] = MoneyAccount(
                id=household_id, owner_ref=EntityRef("population_group", staff.id), balance=0)
        household = world.economy.accounts[household_id]
        if household.owner_ref != EntityRef("population_group", staff.id):
            raise ValueError("customs staff household account has the wrong owner")
        gross = checkpoint.staff_count * CUSTOMS_STAFF_WAGE
        event = record_event(
            world, "customs_staff_paid", f"{site.name}: {checkpoint.staff_count} trabalhador(es) mantiveram o posto.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(
                _delta("account", account.id, "balance", account.balance, account.balance - gross),
                _delta("account", household.id, "balance", household.balance, household.balance + gross),
                _delta("customs_checkpoint", checkpoint.id, "last_staffed_day", checkpoint.last_staffed_day,
                       world.clock.absolute_day),
            ),
            cause_ids=_causes(checkpoint.last_event_id, site.last_event_id, account.last_event_id,
                               household.last_event_id, staff.last_event_id),
        )
        world.economy.accounts[account.id] = account.model_copy(update={"balance": account.balance - gross, "last_event_id": event.id})
        world.economy.accounts[household.id] = household.model_copy(update={"balance": household.balance + gross, "last_event_id": event.id})
        world.economy.customs_checkpoints[checkpoint.id] = checkpoint.model_copy(
            update={"last_staffed_day": world.clock.absolute_day, "last_event_id": event.id})
        world.economy.payrolls[checkpoint.id] = Payroll(
            id=checkpoint.id, day=world.clock.absolute_day, wage_per_worker=CUSTOMS_STAFF_WAGE,
            workers_by_group={staff.id: checkpoint.staff_count}, gross=gross, tax=0, last_event_id=event.id,
        )
        available[staff.id] -= checkpoint.staff_count


def _checkpoint_for_route(world, route_id):
    candidates = [checkpoint for checkpoint in world.economy.customs_checkpoints.values()
                  if route_id in world.map.infrastructure_sites[checkpoint.site_id].route_ids
                  and checkpoint_active(world, checkpoint)]
    if len(candidates) > 1:
        # The V1 model has no spatial ordering of posts on a route.  This must
        # be rejected rather than silently changing a cargo's legal burden.
        raise ValueError("ambiguous active customs checkpoints on one route")
    return candidates[0] if candidates else None


def customs_fee(world, parcel, checkpoint):
    order = world.economy.freight_orders[parcel.order_id]
    return math.ceil(parcel.quantity * world.economy.resources[order.resource_id].bulk * checkpoint.fee_per_bulk)


def inspect_waiting_parcel(world, parcel, route_id):
    """Present one waiting parcel at a staffed checkpoint.

    Presentation is a factual receipt, not inspection and not a fee.  The
    owner receives exactly enough canonical information to select declaration
    or attempted fee evasion later.
    """
    if parcel.stage != "waiting":
        return None
    checkpoint = _checkpoint_for_route(world, route_id)
    if checkpoint is None:
        return None
    notice_id = f"customs_notice:{parcel.id}"
    if notice_id in world.knowledge.customs_notices:
        return None
    order = world.economy.freight_orders[parcel.order_id]
    updated = parcel.model_copy(update={"stage": "held", "held_checkpoint_id": checkpoint.id,
                                        "held_notice_id": notice_id})
    event = record_event(
        world, "customs_presented", "A carga foi apresentada ao posto civil e aguarda declaração.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(
            _delta("cargo", parcel.id, "stage", parcel.stage, updated.stage),
            _delta("cargo", parcel.id, "held_checkpoint_id", parcel.held_checkpoint_id, updated.held_checkpoint_id),
            _delta("cargo", parcel.id, "held_notice_id", parcel.held_notice_id, updated.held_notice_id),
            _delta("customs_notice", notice_id, "state", None, "presented"),
        ),
        cause_ids=_causes(parcel.last_event_id, order.last_event_id, checkpoint.last_event_id,
                           world.map.infrastructure_sites[checkpoint.site_id].last_event_id),
    )
    world.economy.parcels[parcel.id] = updated.model_copy(update={"last_event_id": event.id})
    world.economy.freight_orders[order.id] = order.model_copy(update={"last_event_id": event.id})
    world.knowledge.customs_notices[notice_id] = CustomsNotice(
        id=notice_id, checkpoint_id=checkpoint.id, parcel_id=parcel.id, order_id=order.id,
        resource_id=order.resource_id, quantity=parcel.quantity, recipient_ref=order.owner_ref,
        learned_day=world.clock.absolute_day, event_id=event.id, state_event_id=event.id, state="presented",
    )
    return event


def _matching_held_notice(world, notice):
    parcel = world.economy.parcels.get(notice.parcel_id)
    order = world.economy.freight_orders.get(notice.order_id)
    checkpoint = world.economy.customs_checkpoints.get(notice.checkpoint_id)
    if (parcel is None or order is None or checkpoint is None or parcel.order_id != order.id
            or parcel.stage != "held" or parcel.held_notice_id != notice.id
            or parcel.held_checkpoint_id != checkpoint.id or order.owner_ref != notice.recipient_ref
            or order.resource_id != notice.resource_id or parcel.quantity != notice.quantity):
        return None
    return parcel, order, checkpoint


def customs_cargo_options(world, actor_ref):
    """Current declaration/evasion affordances for cargo the actor owns.

    A detected parcel can still be legally declared, but may not make a second
    attempt.  A manifest is immutable and therefore removes declaration as an
    option once it has been created.
    """
    if not isinstance(actor_ref, EntityRef) or not can_actor_act_for(world, actor_ref, actor_ref, "trade"):
        return ()
    options = []
    # Civil inspections form one FIFO queue per checkpoint.  Declaration is
    # not an inspection and stays available for every presented parcel; only
    # attempts to evade consume the next paid inspection opportunity.
    first_presented = {}
    for candidate in sorted(world.knowledge.customs_notices.values(), key=lambda item: item.parcel_id):
        if candidate.state == "presented" and _matching_held_notice(world, candidate) is not None:
            first_presented.setdefault(candidate.checkpoint_id, candidate.id)
    for notice in sorted(world.knowledge.customs_for_actor(actor_ref), key=lambda item: item.id):
        linked = _matching_held_notice(world, notice)
        if linked is None:
            continue
        parcel, order, checkpoint = linked
        if not checkpoint_active(world, checkpoint):
            continue
        common = (f":{notice.id}:{parcel.last_event_id}:{checkpoint.last_event_id}:"
                  f"{checkpoint.inspection_day}:{checkpoint.inspection_slots_used}:{world.clock.absolute_day}")
        if notice.state in {"presented", "detected"} and notice.manifest_id is None:
            options.append(CustomsCargoOption(
                id=f"customs-declare{common}", action="declare_customs_manifest", notice_id=notice.id,
                checkpoint_id=checkpoint.id, parcel_id=parcel.id, order_id=order.id, actor_ref=actor_ref,
                resource_id=order.resource_id, quantity=parcel.quantity))
        if notice.state == "presented" and first_presented.get(checkpoint.id) == notice.id:
            options.append(CustomsCargoOption(
                id=f"customs-evade{common}", action="attempt_customs_fee_evasion", notice_id=notice.id,
                checkpoint_id=checkpoint.id, parcel_id=parcel.id, order_id=order.id, actor_ref=actor_ref,
                resource_id=order.resource_id, quantity=parcel.quantity))
    return tuple(options)


def _decision_option(world, option_id, decision_event_id, action):
    decision = _event(world, decision_event_id)
    payload = decision.decision if decision is not None else None
    try:
        actor = EntityRef.from_dict(payload.get("actor_ref")) if isinstance(payload, dict) else None
    except (KeyError, TypeError, ValueError):
        actor = None
    option = next((item for item in customs_cargo_options(world, actor)
                   if item.id == option_id and item.action == action), None)
    if (decision is None or decision.day != world.clock.absolute_day or decision.fact_kind != FactKind.DECISION
            or option is None or decision.decision != option.decision()):
        raise ValueError("customs cargo option is stale")
    if any(event.event_type in {"cargo_manifest_declared", "customs_fee_evaded", "customs_fee_evasion_detected"}
           and any(link.cause_event_id == decision.id for link in event.causal_links) for event in world.events):
        raise ValueError("customs cargo decision already executed")
    require_authority(world, option.actor_ref, "trade")
    linked = _matching_held_notice(world, world.knowledge.customs_notices[option.notice_id])
    if linked is None:
        raise ValueError("customs cargo is no longer held")
    parcel, order, checkpoint = linked
    if not checkpoint_active(world, checkpoint):
        raise ValueError("customs checkpoint is no longer active")
    return option, decision, parcel, order, checkpoint


def declare_customs_manifest(world, option_id, *, decision_event_id):
    option, decision, parcel, order, checkpoint = _decision_option(
        world, option_id, decision_event_id, "declare_customs_manifest")
    notice = world.knowledge.customs_notices[option.notice_id]
    manifest = CargoManifest(
        id=f"cargo_manifest:{parcel.id}", checkpoint_id=checkpoint.id, parcel_id=parcel.id,
        order_id=order.id, owner_ref=option.actor_ref, resource_id=order.resource_id,
        quantity=parcel.quantity, declared_day=world.clock.absolute_day, event_id="pending",
    )
    if manifest.id in world.economy.cargo_manifests:
        raise ValueError("customs cargo already has a manifest")
    fee = customs_fee(world, parcel, checkpoint)
    event = record_event(
        world, "cargo_manifest_declared", "A carga foi declarada para a taxa civil de passagem.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(
            _delta("cargo_manifest", manifest.id, "declared", False, True),
            _delta("customs_notice", notice.id, "state", notice.state, "fee_due"),
            _delta("customs_notice", notice.id, "fee", notice.fee, fee),
            _delta("customs_notice", notice.id, "manifest_id", notice.manifest_id, manifest.id),
        ),
        cause_ids=_causes(decision.id, notice.event_id, notice.state_event_id, parcel.last_event_id,
                          order.last_event_id, checkpoint.last_event_id),
    )
    world.economy.cargo_manifests[manifest.id] = manifest.model_copy(update={"event_id": event.id})
    world.knowledge.customs_notices[notice.id] = notice.model_copy(
        update={"state": "fee_due", "fee": fee, "manifest_id": manifest.id, "state_event_id": event.id})
    return event


def _release_undetected(world, notice, parcel, order, checkpoint, decision, *, inspection_deltas=(), cause_ids=()):
    updated = parcel.model_copy(update={"stage": "waiting", "due_day": world.clock.absolute_day + 1,
                                        "held_checkpoint_id": None, "held_notice_id": None})
    event = record_event(
        world, "customs_fee_evaded", "A carga deixou o posto sem taxa civil registrada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(
            *inspection_deltas,
            _delta("cargo", parcel.id, "stage", parcel.stage, updated.stage),
            _delta("cargo", parcel.id, "due_day", parcel.due_day, updated.due_day),
            _delta("cargo", parcel.id, "held_checkpoint_id", parcel.held_checkpoint_id, None),
            _delta("cargo", parcel.id, "held_notice_id", parcel.held_notice_id, None),
            _delta("customs_notice", notice.id, "state", notice.state, "evaded_undetected"),
        ),
        cause_ids=_causes(decision.id, notice.event_id, notice.state_event_id, parcel.last_event_id,
                          order.last_event_id, checkpoint.last_event_id, *cause_ids),
    )
    world.economy.parcels[parcel.id] = updated.model_copy(update={"last_event_id": event.id})
    world.economy.freight_orders[order.id] = order.model_copy(update={"last_event_id": event.id})
    world.knowledge.customs_notices[notice.id] = notice.model_copy(
        update={"state": "evaded_undetected", "state_event_id": event.id})
    world.agenda.schedule(ScheduledSituation(parcel.id, "cargo", updated.due_day))
    return event


def attempt_customs_fee_evasion(world, option_id, *, decision_event_id):
    """Resolve one attempted evasion under the checkpoint's paid capacity.

    No inspection capacity means no RNG draw: the attempt is factually
    undetected and the same parcel returns to the dated queue.  A consumed slot
    records its deterministic position plus the world RNG roll and threshold.
    """
    option, decision, parcel, order, checkpoint = _decision_option(
        world, option_id, decision_event_id, "attempt_customs_fee_evasion")
    notice = world.knowledge.customs_notices[option.notice_id]
    today = world.clock.absolute_day
    before_day = checkpoint.inspection_day
    before_slots = checkpoint.inspection_slots_used
    used = checkpoint.inspection_slots_used if checkpoint.inspection_day == today else 0
    capacity = checkpoint.staff_count * CUSTOMS_INSPECTIONS_PER_STAFF_PER_DAY
    if used >= capacity:
        return _release_undetected(world, notice, parcel, order, checkpoint, decision)
    slot = used + 1
    roll = world.rng.randrange(1000)
    detected = roll < CUSTOMS_DETECTION_PERMILLE
    updated_checkpoint = checkpoint.model_copy(update={"inspection_day": today, "inspection_slots_used": slot})
    deltas = (
        *((_delta("customs_checkpoint", checkpoint.id, "inspection_day", before_day, today),)
          if before_day != today else ()),
        _delta("customs_checkpoint", checkpoint.id, "inspection_slots_used", before_slots, slot),
        _delta("customs_inspection", f"{checkpoint.id}:{today}:{slot}", "roll_permille", None, roll),
        _delta("customs_inspection", f"{checkpoint.id}:{today}:{slot}", "threshold_permille", None,
               CUSTOMS_DETECTION_PERMILLE),
    )
    if not detected:
        # Persist checkpoint capacity before release; the release event owns the
        # factual outcome and causal evidence for the same attempt.
        event = _release_undetected(world, notice, parcel, order, updated_checkpoint, decision,
                                    inspection_deltas=deltas, cause_ids=(checkpoint.last_event_id,))
        world.economy.customs_checkpoints[checkpoint.id] = updated_checkpoint.model_copy(update={"last_event_id": event.id})
        return event
    event = record_event(
        world, "customs_fee_evasion_detected", "A tentativa de evitar a taxa civil foi detectada no posto.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(*deltas, _delta("customs_notice", notice.id, "state", notice.state, "detected")),
        cause_ids=_causes(decision.id, notice.event_id, notice.state_event_id, parcel.last_event_id,
                          order.last_event_id, checkpoint.last_event_id),
    )
    world.economy.customs_checkpoints[checkpoint.id] = updated_checkpoint.model_copy(update={"last_event_id": event.id})
    world.economy.parcels[parcel.id] = parcel.model_copy(update={"last_event_id": event.id})
    world.economy.freight_orders[order.id] = order.model_copy(update={"last_event_id": event.id})
    world.knowledge.customs_notices[notice.id] = notice.model_copy(update={"state": "detected", "state_event_id": event.id})
    return event


def customs_payment_options(world, actor_ref):
    if not isinstance(actor_ref, EntityRef) or not can_actor_act_for(world, actor_ref, actor_ref, "trade"):
        return ()
    options = []
    for notice in world.knowledge.customs_for_actor(actor_ref):
        parcel = world.economy.parcels.get(notice.parcel_id)
        checkpoint = world.economy.customs_checkpoints.get(notice.checkpoint_id)
        if (parcel is None or parcel.order_id != notice.order_id or parcel.stage != "held" or notice.state != "fee_due"
                or notice.fee is None or checkpoint is None or not checkpoint_active(world, checkpoint)):
            continue
        order = world.economy.freight_orders[notice.order_id]
        if order.owner_ref != actor_ref:
            continue
        for account in sorted((item for item in world.economy.accounts.values() if item.owner_ref == actor_ref),
                              key=lambda item: item.id):
            options.append(CustomsPaymentOption(
                id=(f"customs-pay:{notice.id}:{account.id}:{notice.event_id}:{parcel.last_event_id}:"
                    f"{checkpoint.last_event_id}:{checkpoint.last_staffed_day}:{account.last_event_id}:{account.balance}"),
                notice_id=notice.id, parcel_id=parcel.id, checkpoint_id=checkpoint.id,
                actor_ref=actor_ref, account_id=account.id, fee=notice.fee,
            ))
    return tuple(options)


def pay_customs_fee(world, option_id, *, decision_event_id):
    decision = _event(world, decision_event_id)
    payload = decision.decision if decision is not None else None
    try:
        actor = EntityRef.from_dict(payload.get("actor_ref")) if isinstance(payload, dict) else None
    except (KeyError, TypeError, ValueError):
        actor = None
    option = next((item for item in customs_payment_options(world, actor) if item.id == option_id), None)
    if (decision is None or decision.day != world.clock.absolute_day or decision.fact_kind != FactKind.DECISION
            or option is None or decision.decision != option.decision()):
        raise ValueError("customs payment option is stale")
    if decision.id in world.economy.payments:
        raise ValueError("customs payment decision already executed")
    require_authority(world, option.actor_ref, "trade")
    notice = world.knowledge.customs_notices[option.notice_id]
    parcel = world.economy.parcels.get(option.parcel_id)
    checkpoint = world.economy.customs_checkpoints.get(option.checkpoint_id)
    account = world.economy.accounts.get(option.account_id)
    if (parcel is None or parcel.stage != "held" or notice.state != "fee_due" or notice.fee is None
            or checkpoint is None or not checkpoint_active(world, checkpoint)
            or account is None or account.owner_ref != option.actor_ref or account.balance < option.fee
            or notice.manifest_id is None):
        raise ValueError("customs payment can no longer be executed")
    collector = world.economy.accounts.get(checkpoint.account_id)
    if collector is None or collector.owner_ref != checkpoint.operator_ref:
        raise ValueError("customs collector account is invalid")
    updated = parcel.model_copy(update={"stage": "waiting", "due_day": world.clock.absolute_day + 1,
                                        "held_checkpoint_id": None, "held_notice_id": None})
    order = world.economy.freight_orders[parcel.order_id]
    account_changes = {account.id: -option.fee}
    account_changes[collector.id] = account_changes.get(collector.id, 0) + option.fee
    event = record_event(
        world, "customs_fee_paid", "A taxa civil foi paga; a mesma carga voltou à fila de despacho.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(
            *(_delta("account", account_id, "balance", world.economy.accounts[account_id].balance,
                     world.economy.accounts[account_id].balance + change)
              for account_id, change in sorted(account_changes.items()) if change),
            _delta("cargo", parcel.id, "stage", parcel.stage, updated.stage),
            _delta("cargo", parcel.id, "due_day", parcel.due_day, updated.due_day),
            _delta("cargo", parcel.id, "held_checkpoint_id", parcel.held_checkpoint_id, None),
            _delta("cargo", parcel.id, "held_notice_id", parcel.held_notice_id, None),
            _delta("customs_notice", notice.id, "state", notice.state, "cleared"),
        ),
        cause_ids=_causes(decision.id, notice.event_id, parcel.last_event_id, order.last_event_id,
                           checkpoint.last_event_id, account.last_event_id, collector.last_event_id),
    )
    for account_id, change in account_changes.items():
        current = world.economy.accounts[account_id]
        world.economy.accounts[account_id] = current.model_copy(
            update={"balance": current.balance + change, "last_event_id": event.id})
    world.economy.parcels[parcel.id] = updated.model_copy(update={"last_event_id": event.id})
    world.economy.freight_orders[order.id] = order.model_copy(update={"last_event_id": event.id})
    world.economy.payments[decision.id] = event.id
    world.knowledge.customs_notices[notice.id] = notice.model_copy(update={"state": "cleared", "state_event_id": event.id})
    world.agenda.schedule(ScheduledSituation(parcel.id, "cargo", updated.due_day))
    return event


__all__ = ["CUSTOMS_DETECTION_PERMILLE", "CUSTOMS_FEE_PER_BULK", "CUSTOMS_INSPECTIONS_PER_STAFF_PER_DAY",
           "CUSTOMS_SITE_KINDS", "CUSTOMS_STAFF_WAGE", "CustomsCargoOption", "CustomsOpenOption",
           "CustomsPaymentOption", "attempt_customs_fee_evasion", "checkpoint_active", "customs_cargo_options",
           "customs_fee", "customs_open_options", "customs_payment_options", "declare_customs_manifest",
           "inspect_waiting_parcel", "open_customs_checkpoint", "pay_customs_fee", "staff_customs_checkpoints"]

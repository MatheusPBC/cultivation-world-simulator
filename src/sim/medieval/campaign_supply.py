"""Supply one standing detachment through the existing freight owner.

This adds no campaign planner or combat rule. A low bag earns a private,
provider-only chance to dispatch food to a real local campaign stock. Freight
then follows normal routes and customs; Society alone loads a co-located bag
into provisions or lets a hungry column lapse.
"""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256

from src.classes.economy.models import Stock
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.knowledge import campaign_supply_notice_id
from src.classes.governance.models import CampaignSupplyNotice
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .demand import reserve_quantity
from .economy import _causes, _delta
from .events import record_event
from .logistics import open_order
from .routing import known_supply_path
from .travel import route_duration


DISPATCH_ACTION = "dispatch_campaign_supply"
REVIEW_KIND = "campaign_supply_review"
RATIONS_PER_SOLDIER_DAY = 1
# A review happens tomorrow and even the column's known home road takes dated
# freight steps before it can unload.  Six days is the bounded early-warning
# reading; a column already nearer starvation can still lapse while waiting.
LOW_SUPPLY_DAYS = 6
LOAD_SUPPLY_DAYS = 10
MAX_BAG_DAYS = 20
FIELD_LOGISTICS_BONUS_DAYS = 5
_PREFIX = "campaign-supply-review:"


@dataclass(frozen=True)
class CampaignSupplyOption:
    id: Identity
    actor_ref: EntityRef
    notice_id: Identity
    detachment_id: Identity
    source_stock_id: Identity
    campaign_stock_id: Identity
    quantity: int
    route_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": DISPATCH_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def campaign_stock_id(detachment_id):
    return f"stock:camp:{detachment_id}"


def campaign_baggage_ready_for_departure(world, detachment):
    """An empty, uncommitted bag may physically travel with its own column.

    Pending supply remains at its existing place until ordinary freight
    resolves.  Withdrawal therefore never drags a stock or parcel across the
    map merely because a force changed plans.
    """
    stock = world.economy.stocks.get(campaign_stock_id(detachment.id))
    if stock is not None and any(quantity for quantity in stock.goods.values()):
        return False
    active_notice = any(
        notice.detachment_id == detachment.id and notice.recipient_ref == detachment.owner_ref
        and notice.state in {"open", "dispatched"}
        for notice in world.knowledge.campaign_supply_notices.values()
    )
    active_parcel = any(
        world.economy.freight_orders[parcel.order_id].destination_id == campaign_stock_id(detachment.id)
        for parcel in world.economy.parcels.values()
    )
    return not active_notice and not active_parcel


def _bag_capacity(world, detachment):
    days = MAX_BAG_DAYS + (FIELD_LOGISTICS_BONUS_DAYS
                           if world.knowledge.knows(detachment.owner_ref, "field_logistics") else 0)
    return detachment.count * days * world.economy.resources["food"].bulk


def _provision_capacity(world, detachment):
    days = LOAD_SUPPLY_DAYS + (FIELD_LOGISTICS_BONUS_DAYS
                               if world.knowledge.knows(detachment.owner_ref, "field_logistics") else 0)
    return detachment.count * days * RATIONS_PER_SOLDIER_DAY


def _threshold(detachment):
    return detachment.count * LOW_SUPPLY_DAYS * RATIONS_PER_SOLDIER_DAY


def _delivery_days_from_dispatch(world, route_ids):
    """Earliest dated arrival for the first usable parcel after dispatch.

    The next-day initial departure is a real logistics step. Every later leg
    has its own next-day departure after a waypoint. Capacity may split the
    order, but a physically usable first parcel is enough to avoid a
    rule-forced lapse.
    """
    return 1 + sum(route_duration(world, route_id) for route_id in route_ids) + max(0, len(route_ids) - 1)


def _warning_threshold(world, detachment):
    """Engine-owned early warning: known lead time plus one day of margin."""
    lead_days = []
    for _, stock in sorted(world.economy.stocks.items()):
        if stock.id == campaign_stock_id(detachment.id) or stock.owner_ref != detachment.owner_ref:
            continue
        if stock.goods.get("food", 0) - reserve_quantity(world, stock.id, "food") <= 0:
            continue
        route_ids = _known_campaign_route(world, detachment.owner_ref, detachment,
                                          stock.location_id, detachment.location_id)
        if route_ids:
            # The notice's provider turn is tomorrow; dispatch itself only
            # starts after that dated review.
            lead_days.append(_delivery_days_from_dispatch(world, route_ids) + 1)
    return detachment.count * max(LOW_SUPPLY_DAYS, (min(lead_days) + 1) if lead_days else LOW_SUPPLY_DAYS)


def _review_id(notice_id):
    return f"{_PREFIX}{notice_id}"


def _option_id(notice_id, source_id, campaign_id, quantity, route_ids):
    """Bind a transient choice without disclosing its private freight plan."""
    material = "|".join((notice_id, source_id, campaign_id, str(quantity), *route_ids))
    return f"campaign-supply:{notice_id}:{sha256(material.encode()).hexdigest()[:16]}"


def _schedule_review(world, notice, day):
    identity = _review_id(notice.id)
    if day > world.clock.absolute_day and world.agenda.get(identity) is None:
        world.agenda.schedule(ScheduledSituation(identity, REVIEW_KIND, day))


def _decision(world, decision_event_id):
    event = next((item for item in world.events if item.id == decision_event_id), None)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision is None or event.decision.get("action") != DISPATCH_ACTION
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("campaign supply requires a current actor decision")
    return event


def ensure_campaign_stock(world, detachment):
    """A present column has one empty bounded bag at the place it stands."""
    identity = campaign_stock_id(detachment.id)
    stock = world.economy.stocks.get(identity)
    if stock is not None:
        if stock.owner_ref != detachment.owner_ref or stock.location_id != detachment.location_id:
            raise ValueError("campaign bag is not co-located with its detachment")
        return stock
    capacity = _bag_capacity(world, detachment)
    event = record_event(
        world, "campaign_baggage_established", "Uma bagagem limitada foi preparada junto à coluna.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("stock", identity, "capacity", 0, capacity),),
        cause_ids=_causes(detachment.last_event_id),
    )
    stock = Stock(id=identity, owner_ref=detachment.owner_ref, location_id=detachment.location_id,
                  capacity=capacity, goods={}, last_event_ids={"food": event.id})
    world.economy.stocks[identity] = stock
    return stock


def _active_notice(world, detachment_id):
    return next((notice for _, notice in sorted(world.knowledge.campaign_supply_notices.items())
                 if notice.detachment_id == detachment_id and notice.state in {"open", "dispatched"}), None)


def _known_campaign_route(world, actor, detachment, source_location_id, destination_location_id):
    """Use a current report, or the column's own already-traversed route.

    The latter is not omniscience: this same owner materially sent this exact
    detachment over those route IDs and its origin still holds the soldiers'
    source cohort. ``open_order`` revalidates the physical Map path later.
    """
    route_ids = known_supply_path(world, actor, source_location_id, destination_location_id, "food")
    if route_ids:
        return route_ids
    source_group = world.society.population.get(detachment.source_group_id)
    if (source_group is not None and source_group.settlement_id == source_location_id
            and detachment.destination_id == destination_location_id and detachment.route_ids):
        return detachment.route_ids
    return ()


def observe_campaign_supply_needs(world):
    """A low real bag creates a fact and a future choice, never a shipment."""
    notices = []
    for _, detachment in sorted(world.society.detachments.items()):
        if detachment.stage != "present":
            continue
        ensure_campaign_stock(world, detachment)
        threshold = _warning_threshold(world, detachment)
        if detachment.provisions >= threshold or _active_notice(world, detachment.id) is not None:
            continue
        source_event_id = detachment.last_event_id
        # ``record_event`` allocates monotonically from the canonical event
        # ledger.  Reserve this receipt identity before recording it so the
        # private notice is keyed by its own factual observation, rather than
        # by the earlier ration receipt which happened to trigger it.
        observation_event_id = f"event:{len(world.events) + 1}"
        identity = campaign_supply_notice_id(detachment.id, observation_event_id)
        event = record_event(
            world, "campaign_supply_observed", "A coluna registrou que suas provisões ficaram abaixo do limite.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("campaign_supply_notice", identity, "state", None, "open"),),
            cause_ids=_causes(source_event_id),
        )
        if event.id != observation_event_id:
            raise ValueError("campaign supply observation receipt identity changed")
        notice = CampaignSupplyNotice(
            id=identity, recipient_ref=detachment.owner_ref, detachment_id=detachment.id,
            settlement_id=detachment.location_id, threshold=threshold,
            observed_provisions=detachment.provisions, event_id=event.id, learned_day=world.clock.absolute_day,
            last_event_id=event.id,
        )
        world.knowledge.campaign_supply_notices[notice.id] = notice
        _schedule_review(world, notice, world.clock.absolute_day + 1)
        notices.append(notice)
    return tuple(notices)


def campaign_supply_options(world, actor):
    """Only own fresh shortfall, own food and known valid paths become options."""
    if not isinstance(actor, EntityRef) or not can_actor_act_for(world, actor, actor, "supply"):
        return ()
    options = []
    for notice in world.knowledge.campaign_supplies_for_actor(actor):
        if notice.state != "open":
            continue
        detachment = world.society.detachments.get(notice.detachment_id)
        camp = world.economy.stocks.get(campaign_stock_id(notice.detachment_id))
        if (detachment is None or detachment.owner_ref != actor or detachment.stage != "present"
                or detachment.location_id != notice.settlement_id or detachment.provisions >= _warning_threshold(world, detachment)
                or camp is None or camp.owner_ref != actor or camp.location_id != detachment.location_id):
            continue
        headroom = max(0, (camp.capacity - world.economy.used_capacity(camp)) // world.economy.resources["food"].bulk)
        if headroom <= 0:
            continue
        desired = min(headroom, detachment.count * LOAD_SUPPLY_DAYS)
        for source_id, source in sorted(world.economy.stocks.items()):
            if source.id == camp.id or source.owner_ref != actor:
                continue
            free_food = source.goods.get("food", 0) - reserve_quantity(world, source.id, "food")
            route_ids = _known_campaign_route(world, actor, detachment, source.location_id, camp.location_id)
            quantity = min(desired, free_food)
            # A choice that cannot physically reach the column before the
            # current bag empties is not an affordance.  A later route closure
            # may still delay an already-open real order and cause a lapse.
            survive = (detachment.count * max(0, _delivery_days_from_dispatch(world, route_ids) - 1)
                       if route_ids else 0)
            if quantity <= 0 or not route_ids or detachment.provisions < survive:
                continue
            options.append(CampaignSupplyOption(
                id=_option_id(notice.id, source.id, camp.id, quantity, tuple(route_ids)),
                actor_ref=actor, notice_id=notice.id, detachment_id=detachment.id,
                source_stock_id=source.id, campaign_stock_id=camp.id, quantity=quantity,
                route_ids=tuple(route_ids)))
    return tuple(sorted(options, key=lambda item: item.id))


def dispatch_campaign_supply(world, actor, option_id, decision_event_id):
    """Open ordinary food freight; loading the bag waits for actual delivery."""
    candidate = deepcopy(world)
    decision = _decision(candidate, decision_event_id)
    try:
        decided_by = EntityRef.from_dict(decision.decision["actor_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("campaign supply decision has an invalid actor") from exc
    if decided_by != actor:
        raise ValueError("campaign supply has the wrong actor")
    option = next((item for item in campaign_supply_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("campaign supply option is stale or unknown")
    require_authority(candidate, actor, "supply")
    notice = candidate.knowledge.campaign_supply_notices[option.notice_id]
    order = open_order(candidate, option.source_stock_id, option.campaign_stock_id, "food", option.quantity,
                       option.route_ids, decision_ids=(decision.id,), cause_ids=(notice.event_id,))
    event = record_event(
        candidate, "campaign_supply_dispatched", "O abastecimento da coluna foi entregue à logística.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("campaign_supply_notice", notice.id, "state", "open", "dispatched"),),
        cause_ids=_causes(decision.id, notice.last_event_id, order.last_event_id),
    )
    candidate.knowledge.campaign_supply_notices[notice.id] = notice.model_copy(
        update={"state": "dispatched", "freight_id": order.id, "last_event_id": event.id})
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.society.validate(set(candidate.map.regions), candidate)
    world.__dict__.update(candidate.__dict__)
    return world.economy.freight_orders[order.id]


def _transition_notice(world, notice, state, event, *, freight_id=None):
    world.knowledge.campaign_supply_notices[notice.id] = notice.model_copy(update={
        "state": state, "freight_id": notice.freight_id if freight_id is None else freight_id,
        "last_event_id": event.id})


def load_campaign_baggage(world):
    """Delivered local food is loaded into the real co-located force bag."""
    loaded = []
    for _, detachment in sorted(world.society.detachments.items()):
        if detachment.stage != "present":
            continue
        stock = world.economy.stocks.get(campaign_stock_id(detachment.id))
        if stock is None or stock.location_id != detachment.location_id or stock.owner_ref != detachment.owner_ref:
            continue
        available = stock.goods.get("food", 0)
        amount = min(available, max(0, _provision_capacity(world, detachment) - detachment.provisions))
        if amount <= 0:
            continue
        updated = detachment.model_copy(update={"provisions": detachment.provisions + amount})
        fulfilled = [notice for notice in world.knowledge.campaign_supply_notices.values()
                     if notice.detachment_id == detachment.id and notice.state == "dispatched"
                     and notice.freight_id in world.economy.freight_orders
                     and world.economy.freight_orders[notice.freight_id].delivered_quantity > 0]
        event = record_event(
            world, "campaign_provisions_loaded", "Alimento entregue foi carregado na bagagem da coluna.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("stock", stock.id, "food", available, available - amount),
                    _delta("detachment", detachment.id, "provisions", detachment.provisions, updated.provisions),
                    *(_delta("campaign_supply_notice", notice.id, "state", "dispatched", "fulfilled")
                      for notice in fulfilled)),
            cause_ids=_causes(stock.last_event_ids.get("food"), detachment.last_event_id,
                              *(notice.last_event_id for notice in fulfilled)),
        )
        world.economy.stocks[stock.id] = stock.model_copy(update={
            "goods": {**stock.goods, "food": available - amount},
            "last_event_ids": {**stock.last_event_ids, "food": event.id}})
        world.society.detachments[detachment.id] = updated.model_copy(update={"last_event_id": event.id})
        for notice in fulfilled:
            _transition_notice(world, notice, "fulfilled", event)
        loaded.append(detachment.id)
    # A parcel can arrive after its column lapsed.  It must not become food in
    # an ownerless campaign bag: return it to a co-located own stock when it
    # fits, otherwise record the physical loss explicitly.
    for _, detachment in sorted(world.society.detachments.items()):
        if detachment.stage == "disbanded":
            stock = world.economy.stocks.get(campaign_stock_id(detachment.id))
            if stock is not None and stock.goods.get("food", 0) > 0:
                dispose_campaign_baggage(world, detachment, stock.last_event_ids.get("food"))
    return tuple(loaded)


def dispose_campaign_baggage(world, detachment, cause_event_id):
    """A dissolved column returns local food if possible; residue is explicit loss."""
    stock = world.economy.stocks.get(campaign_stock_id(detachment.id))
    if stock is None or stock.goods.get("food", 0) <= 0:
        _lapse_campaign_notices(world, detachment.id, cause_event_id)
        return None
    food = stock.goods["food"]
    targets = [item for _, item in sorted(world.economy.stocks.items())
               if item.id != stock.id and item.owner_ref == stock.owner_ref and item.location_id == stock.location_id]
    target = next((item for item in targets if item.capacity - world.economy.used_capacity(item)
                   >= food * world.economy.resources["food"].bulk), None)
    returned = food if target is not None else 0
    event = record_event(
        world, "campaign_baggage_returned" if returned else "campaign_baggage_lost",
        "A bagagem restante retornou ao estoque local." if returned else "A bagagem restante se perdeu após a dissolução.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("stock", stock.id, "food", food, 0),
                *(() if target is None else (_delta("stock", target.id, "food", target.goods.get("food", 0),
                                                     target.goods.get("food", 0) + food),))),
        cause_ids=_causes(cause_event_id, stock.last_event_ids.get("food")),
    )
    world.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, "food": 0}, "last_event_ids": {**stock.last_event_ids, "food": event.id}})
    if target is not None:
        world.economy.stocks[target.id] = target.model_copy(update={
            "goods": {**target.goods, "food": target.goods.get("food", 0) + food},
            "last_event_ids": {**target.last_event_ids, "food": event.id}})
    _lapse_campaign_notices(world, detachment.id, event.id)
    return event


def _lapse_campaign_notices(world, detachment_id, cause_event_id):
    notices = [notice for notice in world.knowledge.campaign_supply_notices.values()
               if notice.detachment_id == detachment_id and notice.state in {"open", "dispatched"}]
    if not notices:
        return None
    event = record_event(
        world, "campaign_supply_lapsed", "A necessidade de abastecimento cessou porque a coluna não permaneceu em campo.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(_delta("campaign_supply_notice", notice.id, "state", notice.state, "lapsed")
                     for notice in notices),
        cause_ids=_causes(cause_event_id, *(notice.last_event_id for notice in notices)),
    )
    for notice in notices:
        _transition_notice(world, notice, "lapsed", event)
    return event


async def review_campaign_supplies(world, situations):
    """One real-provider turn per owner; no provider means no shipment."""
    due = [item for item in situations if item.kind == REVIEW_KIND and item.id.startswith(_PREFIX)]
    if not due or not (ai_decider.provider_available() and ai_decider.within_budget(world)):
        return
    reviewed = set()
    for situation in sorted(due, key=lambda item: item.id):
        notice = world.knowledge.campaign_supply_notices.get(situation.id[len(_PREFIX):])
        if notice is None or notice.recipient_ref in reviewed:
            continue
        reviewed.add(notice.recipient_ref)
        options = tuple(item for item in campaign_supply_options(world, notice.recipient_ref)
                        if item.notice_id == notice.id)
        if not options:
            continue
        detachment = world.society.detachments[notice.detachment_id]
        situation_data = {"today": world.clock.absolute_day,
                          "your_detachment": {"id": detachment.id, "settlement_id": detachment.location_id,
                                               "provisions": detachment.provisions},
                          "supply_notice": {"settlement_id": notice.settlement_id,
                                            "threshold": notice.threshold}}
        selected = await ai_decider.select_option(
            world, notice.recipient_ref, situation_data,
            [{"id": option.id, "label": "Despachar alimento próprio para a bagagem local da coluna."}
             for option in options], causes=(notice.event_id,))
        if selected in (None, ai_decider.NO_ACTION):
            continue
        option = next((item for item in campaign_supply_options(world, notice.recipient_ref) if item.id == selected), None)
        if option is None:
            continue
        decision = record_event(world, "campaign_supply_decided", "A instituição escolheu uma opção de abastecimento.",
                                fact_kind=FactKind.DECISION, decision=option.decision(), cause_ids=(notice.event_id,))
        try:
            dispatch_campaign_supply(world, notice.recipient_ref, option.id, decision.id)
        except ValueError:
            continue


from . import ai_decider


__all__ = ["REVIEW_KIND", "campaign_stock_id", "campaign_supply_options", "dispatch_campaign_supply",
           "campaign_baggage_ready_for_departure", "dispose_campaign_baggage", "ensure_campaign_stock", "load_campaign_baggage",
           "observe_campaign_supply_needs", "review_campaign_supplies"]

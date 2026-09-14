"""Bilateral recovery of a prepaid purchase whose original freight is blocked.

The original order and payment remain immutable history.  A seller may accept
the buyer's current alternative route, which explicitly resolves the original
parcel and opens one new order from new seller stock without another payment.
"""

import copy
from typing import Literal

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Count, Identity, SocietyValue

from .demand import reserve_quantity
from .economy import _causes, _delta
from .events import record_event
from .freight_recovery import blocking_routes
from .logistics import open_order
from .routing import fiscal_route_options, validate_fiscal_route_option


REQUEST_ACTION = "request_paid_purchase_recovery"
RESPONSE_ACTION = "respond_paid_purchase_recovery"


class PurchaseRecoveryRequestOption(SocietyValue):
    id: Identity
    actor_ref: EntityRef
    order_id: Identity
    route_option_id: Identity
    route_ids: tuple[Identity, ...]
    quantity: Count

    def decision(self):
        return {"action": REQUEST_ACTION, "actor_ref": self.actor_ref.to_dict(), "option_id": self.id}


class PurchaseRecoveryResponseOption(SocietyValue):
    id: Identity
    actor_ref: EntityRef
    case_id: Identity
    kind: Literal["accept", "reject"]
    request_option_id: Identity
    route_option_id: Identity | None = None
    route_ids: tuple[Identity, ...] = ()

    def decision(self):
        return {"action": RESPONSE_ACTION, "actor_ref": self.actor_ref.to_dict(), "option_id": self.id}


def _event(world, event_id):
    return next((item for item in world.events if item.id == event_id), None)


def _purchase_parts(world, order):
    """Return the immutable purchase receipts and its one pending parcel."""
    parcels = [item for item in world.economy.parcels.values() if item.order_id == order.id]
    if (order.delivered_quantity != 0 or order.resolved_quantity != 0 or len(parcels) != 1
            or parcels[0].quantity != order.quantity or parcels[0].stage == "unloading"):
        return None
    decisions = [_event(world, item) for item in order.decision_ids]
    buy = next((item for item in decisions if item is not None and (item.decision or {}).get("action") == "buy"), None)
    sell = next((item for item in decisions if item is not None and (item.decision or {}).get("action") == "sell"), None)
    payment_id = world.economy.payments.get(buy.id) if buy is not None else None
    payment = _event(world, payment_id)
    source, destination = world.economy.stocks.get(order.source_id), world.economy.stocks.get(order.destination_id)
    # This deliberately starts with the smallest bilateral recovery contract:
    # the original sale had no export tariff and the replacement route has no
    # fiscal charge.  A tariff-bearing sale needs an explicit settlement model,
    # rather than silently treating the old tax receipt as interchangeable.
    if (buy is None or sell is None or payment is None or payment.event_type != "payment_completed"
            or source is None or destination is None or source.owner_ref == destination.owner_ref
            or source.owner_ref != EntityRef.from_dict(sell.decision.get("actor_ref"))
            or destination.owner_ref != EntityRef.from_dict(buy.decision.get("actor_ref"))
            or order.owner_ref != destination.owner_ref
            or not {buy.id, sell.id}.issubset({link.cause_event_id for link in payment.causal_links})):
        return None
    parcel = parcels[0]
    opened = next((item for item in world.events if item.event_type == "freight_opened"
                   and any(delta.owner_kind == "cargo" and delta.owner_id == parcel.id
                           and delta.aspect == "quantity" and delta.after == str(order.quantity)
                           for delta in item.deltas)), None)
    if opened is None:
        return None
    blocked = blocking_routes(world, order)
    if not blocked:
        return None
    blocked_events = []
    for route_id in blocked:
        found = next((item.id for item in reversed(world.events)
                      if any(delta.owner_kind == "route" and delta.owner_id == route_id for delta in item.deltas)), None)
        if found is not None:
            blocked_events.append(found)
    if not blocked_events:
        return None
    return buy, sell, payment, opened, parcel, tuple(blocked), tuple(sorted(set(blocked_events)))


def _active_case(world, order_id):
    return any(item.order_id == order_id and item.status in {"requested", "completed"}
               for item in world.economy.freight_recovery_cases.values())


def _free_route(world, option):
    if option.estimated_customs_fee:
        return False
    from .route_intelligence import fiscal_runtime
    return all(fiscal_runtime(world, route_id) is None for route_id in option.route_ids)


def _request_options_for_order(world, actor_ref, order, *, include_active=False):
    parts = _purchase_parts(world, order)
    if (parts is None or parts[0].decision.get("actor_ref") != actor_ref.to_dict()
            or order.owner_ref != actor_ref):
        return ()
    if not include_active and _active_case(world, order.id):
        return ()
    blocked = parts[5]
    options = []
    for route in fiscal_route_options(world, actor_ref, order.source_id, order.destination_id,
                                     order.resource_id, order.quantity):
        if set(route.route_ids).intersection(blocked) or not _free_route(world, route):
            continue
        option_id = f"purchase-recovery-request:{order.id}:{order.last_event_id}:{route.id}"
        options.append(PurchaseRecoveryRequestOption(id=option_id, actor_ref=actor_ref, order_id=order.id,
                                                     route_option_id=route.id, route_ids=route.route_ids,
                                                     quantity=order.quantity))
    return tuple(options)


def purchase_recovery_request_options(world, buyer_ref):
    if not isinstance(buyer_ref, EntityRef):
        return ()
    return tuple(option for _, order in sorted(world.economy.freight_orders.items())
                 for option in _request_options_for_order(world, buyer_ref, order))


def _request_option(world, case):
    order = world.economy.freight_orders.get(case.order_id)
    if order is None:
        return None
    return next((item for item in _request_options_for_order(world, case.buyer_ref, order, include_active=True)
                 if item.id == case.requested_option_id), None)


def _request_route(world, case, request):
    """Recompose the exact no-tariff path a buyer requested."""
    if request is None:
        return None
    return next((item for item in fiscal_route_options(
        world, case.buyer_ref, case.source_id, case.destination_id, case.resource_id, case.quantity
    ) if item.id == request.route_option_id), None)


def purchase_recovery_response_options(world, seller_ref):
    if not isinstance(seller_ref, EntityRef):
        return ()
    result = []
    for case in sorted(world.economy.freight_recovery_cases.values(), key=lambda item: item.id):
        if case.status != "requested" or case.seller_ref != seller_ref:
            continue
        reject_id = f"purchase-recovery-response:{case.id}:reject"
        result.append(PurchaseRecoveryResponseOption(id=reject_id, actor_ref=seller_ref, case_id=case.id,
                                                     kind="reject", request_option_id=case.requested_option_id))
        request = _request_option(world, case)
        route = _request_route(world, case, request)
        if route is not None and _free_route(world, route):
            source = world.economy.stocks.get(case.source_id)
            free = (source.goods.get(case.resource_id, 0) - reserve_quantity(world, source.id, case.resource_id)
                    if source is not None else 0)
            if free >= case.quantity:
                result.append(PurchaseRecoveryResponseOption(
                    id=f"purchase-recovery-response:{case.id}:accept", actor_ref=seller_ref,
                    case_id=case.id, kind="accept", request_option_id=case.requested_option_id,
                    route_option_id=request.route_option_id, route_ids=request.route_ids))
    return tuple(result)


def _decision(world, event_id, action):
    event = _event(world, event_id)
    if (event is None or event.fact_kind != FactKind.DECISION or event.causal_origin == CausalOrigin.LLM_INTERPRETATION
            or event.day != world.clock.absolute_day or event.decision is None
            or event.decision.get("action") != action or set(event.decision) != {"action", "actor_ref", "option_id"}):
        raise ValueError("purchase recovery requires a current actor decision")
    try:
        actor = EntityRef.from_dict(event.decision["actor_ref"])
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError("purchase recovery decision has an invalid actor") from exc
    return event, actor


def request_purchase_recovery(world, option_id, *, decision_event_id):
    world.economy.validate(world)
    decision, buyer = _decision(world, decision_event_id, REQUEST_ACTION)
    option = next((item for item in purchase_recovery_request_options(world, buyer) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("purchase recovery request option is stale or unknown")
    require_authority(world, buyer, "trade")
    order = world.economy.freight_orders[option.order_id]
    parts = _purchase_parts(world, order)
    route = next((item for item in fiscal_route_options(world, buyer, order.source_id, order.destination_id,
                                                       order.resource_id, order.quantity)
                  if item.id == option.route_option_id), None)
    if parts is None or route is None or not _free_route(world, route):
        raise ValueError("purchase recovery request is stale")
    validate_fiscal_route_option(world, route.id, buyer, order.source_id, order.destination_id,
                                 order.resource_id, order.quantity)
    candidate = copy.deepcopy(world)
    buy, sell, payment, opened, parcel, _, blocked_events = parts
    case_id = f"purchase-recovery:{order.id}:{decision_event_id}"
    if case_id in candidate.economy.freight_recovery_cases:
        raise ValueError("purchase recovery request already recorded")
    event = record_event(candidate, "purchase_recovery_requested", "O comprador solicitou o reenvio da compra bloqueada.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("freight_recovery_case", case_id, "status", None, "requested"),),
                         cause_ids=_causes(decision_event_id, payment.id, opened.id, order.last_event_id, *blocked_events))
    from src.classes.economy.models import FreightRecoveryCase
    candidate.economy.freight_recovery_cases[case_id] = FreightRecoveryCase(
        id=case_id, order_id=order.id, source_id=order.source_id, destination_id=order.destination_id,
        resource_id=order.resource_id, quantity=order.quantity, buyer_ref=buyer,
        seller_ref=EntityRef.from_dict(sell.decision["actor_ref"]),
        buy_decision_id=buy.id, sell_decision_id=sell.id, payment_event_id=payment.id,
        original_freight_event_id=opened.id, original_parcel_id=parcel.id, blocked_event_ids=blocked_events,
        requested_option_id=option.id, request_decision_id=decision_event_id, status="requested", last_event_id=event.id)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.economy.freight_recovery_cases[case_id]


def respond_purchase_recovery(world, option_id, *, decision_event_id):
    world.economy.validate(world)
    decision, seller = _decision(world, decision_event_id, RESPONSE_ACTION)
    option = next((item for item in purchase_recovery_response_options(world, seller) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("purchase recovery response option is stale or unknown")
    case = world.economy.freight_recovery_cases.get(option.case_id)
    if case is None or case.status != "requested":
        raise ValueError("purchase recovery case is closed")
    require_authority(world, seller, "trade")
    candidate = copy.deepcopy(world)
    order = candidate.economy.freight_orders.get(case.order_id)
    parts = _purchase_parts(candidate, order) if order is not None else None
    if parts is None:
        raise ValueError("purchase recovery case is stale")
    buy, sell, payment, opened, parcel, _, blocked_events = parts
    if option.kind == "reject":
        event = record_event(candidate, "purchase_recovery_rejected", "O vendedor recusou o reenvio da compra.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(_delta("freight_recovery_case", case.id, "status", "requested", "rejected"),),
                             cause_ids=_causes(decision_event_id, case.request_decision_id, payment.id,
                                               opened.id, order.last_event_id, *blocked_events))
        candidate.economy.freight_recovery_cases[case.id] = case.model_copy(
            update={"status": "rejected", "response_decision_id": decision_event_id, "last_event_id": event.id})
        candidate.economy.validate(candidate)
        world.__dict__.update(candidate.__dict__)
        return None
    request = _request_option(candidate, case)
    route = _request_route(candidate, case, request)
    if request is None or route is None or not _free_route(candidate, route):
        raise ValueError("purchase recovery route is stale")
    validate_fiscal_route_option(candidate, route.id, case.buyer_ref, case.source_id, case.destination_id,
                                 case.resource_id, case.quantity)
    source = candidate.economy.stocks[case.source_id]
    if source.goods.get(case.resource_id, 0) - reserve_quantity(candidate, source.id, case.resource_id) < case.quantity:
        raise ValueError("seller lacks replacement stock")
    successor = open_order(candidate, case.source_id, case.destination_id, case.resource_id, case.quantity,
                           route.route_ids, decision_ids=(decision_event_id,),
                           cause_ids=(case.request_decision_id, payment.id, opened.id, order.last_event_id, *blocked_events))
    # The buyer's already-paid parcel is not destroyed to make room for the
    # replacement.  The accepted re-shipment returns that physically pending
    # cargo to the seller's source stock in the same material resolution that
    # removes the old parcel.  The seller was checked *before* this return for
    # enough free current stock, so this cannot turn the old cargo into a
    # self-financing duplicate shipment.
    replacement_source = candidate.economy.stocks[case.source_id]
    returned_quantity = replacement_source.goods.get(case.resource_id, 0) + parcel.quantity
    if (candidate.economy.used_capacity(replacement_source)
            + parcel.quantity * candidate.economy.resources[case.resource_id].bulk
            > replacement_source.capacity):
        raise ValueError("seller cannot receive the original cargo")
    candidate.agenda.cancel(parcel.id)
    resolution = record_event(candidate, "purchase_recovery_completed",
                              "A carga bloqueada foi explicitamente resolvida e uma sucessora foi aberta.",
                              fact_kind=FactKind.STATE_TRANSITION,
                              deltas=(_delta("cargo", parcel.id, "quantity", parcel.quantity, 0),
                                      _delta("stock", replacement_source.id, case.resource_id,
                                             replacement_source.goods.get(case.resource_id, 0), returned_quantity),
                                      _delta("freight", order.id, "resolved_quantity", order.resolved_quantity,
                                             order.resolved_quantity + parcel.quantity),
                                      _delta("freight_recovery_case", case.id, "status", "requested", "completed")),
                              cause_ids=_causes(decision_event_id, case.request_decision_id, payment.id, opened.id,
                                                order.last_event_id, successor.last_event_id, *blocked_events))
    del candidate.economy.parcels[parcel.id]
    candidate.economy.stocks[replacement_source.id] = replacement_source.model_copy(update={
        "goods": {**replacement_source.goods, case.resource_id: returned_quantity},
        "last_event_ids": {**replacement_source.last_event_ids, case.resource_id: resolution.id},
    })
    candidate.economy.freight_orders[order.id] = order.model_copy(
        update={"resolved_quantity": order.resolved_quantity + parcel.quantity,
                "resolution_event_id": resolution.id, "last_event_id": resolution.id})
    candidate.economy.freight_recovery_cases[case.id] = case.model_copy(
        update={"status": "completed", "response_decision_id": decision_event_id,
                "successor_order_id": successor.id, "resolution_event_id": resolution.id, "last_event_id": resolution.id})
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return successor


__all__ = ["PurchaseRecoveryRequestOption", "PurchaseRecoveryResponseOption", "purchase_recovery_request_options",
           "purchase_recovery_response_options", "request_purchase_recovery", "respond_purchase_recovery"]

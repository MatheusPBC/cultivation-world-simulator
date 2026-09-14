"""Transient recovery options for freight the world has physically blocked.

A ``FreightOrder`` is history: its routes, quantity, decisions and receipts are
never rewritten, rerouted, refunded or re-executed here. While its cargo is
held by a passage without capacity, the owner may reconstruct two options from
what it currently knows: wait, or open a successor shipment over another valid
fiscal route. The engine derives destination, resource and the maximum
quantity; a decision only names an option ID.

Money is deliberately out of scope. A purchased shipment was already paid to a
counterparty, and nothing here may restitute or re-spend it without a material
decision of both owners, so only an unpaid, undelivered internal transfer is
recoverable. Recovering a purchase would need its own bilateral vertical.
"""

import math
from typing import Literal

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Count, Identity, SocietyValue

from .demand import reserve_quantity
from .logistics import open_order
from .routing import fiscal_route_options, validate_fiscal_route_option


RECOVERY_ACTION = "recover_blocked_freight"


class FreightRecoveryOption(SocietyValue):
    """Transient engine option. A decider may only select this ID."""

    id: Identity
    kind: Literal["wait", "successor"]
    actor_ref: EntityRef
    order_id: Identity
    order_last_event_id: Identity
    source_id: Identity
    destination_id: Identity
    resource_id: Identity
    quantity: Count = 0
    route_option_id: Identity | None = None
    route_ids: tuple[Identity, ...] = ()

    def decision(self):
        return {"action": RECOVERY_ACTION, "actor_ref": self.actor_ref.to_dict(), "option_id": self.id}


def blocking_routes(world, order):
    """Passages that currently hold this order's pending cargo without capacity."""
    bulk = world.economy.resources[order.resource_id].bulk
    held = set()
    for parcel in world.economy.parcels.values():
        if parcel.order_id != order.id or parcel.stage == "unloading":
            continue
        route_id = order.route_ids[parcel.route_index]
        route = world.map.routes[route_id]
        if (math.floor(world.map.get_route_operational_capacity(route_id)) < bulk
                or not route.allows_resource(order.resource_id)):
            held.add(route_id)
    return tuple(sorted(held))


def _recoverable(world, order, actor_ref):
    """Only the owner's own unpaid, undelivered internal transfer qualifies."""
    economy = world.economy
    source = economy.stocks.get(order.source_id)
    destination = economy.stocks.get(order.destination_id)
    return bool(source is not None and destination is not None
                and order.owner_ref == actor_ref and source.owner_ref == actor_ref
                and destination.owner_ref == actor_ref and not order.delivered_quantity
                and not any(item in economy.payments for item in order.decision_ids))


def _max_quantity(world, order):
    """Engine-owned quantity: never more than the held cargo or the free stock."""
    source = world.economy.stocks[order.source_id]
    free = source.goods.get(order.resource_id, 0) - reserve_quantity(world, order.source_id, order.resource_id)
    return max(0, min(order.quantity - order.delivered_quantity, free))


def freight_recovery_options(world, actor_ref):
    """Recompose the owner's current options; none of them is ever persisted."""
    if not isinstance(actor_ref, EntityRef):
        return ()
    options = []
    for _, order in sorted(world.economy.freight_orders.items()):
        if not _recoverable(world, order, actor_ref):
            continue
        blocked = blocking_routes(world, order)
        if not blocked:
            continue
        base = f"freight_recovery:{order.id}:{order.last_event_id}"
        common = {"actor_ref": actor_ref, "order_id": order.id, "order_last_event_id": order.last_event_id,
                  "source_id": order.source_id, "destination_id": order.destination_id,
                  "resource_id": order.resource_id}
        options.append(FreightRecoveryOption(id=f"{base}:wait", kind="wait", **common))
        quantity = _max_quantity(world, order)
        if not quantity:
            continue
        for route_option in fiscal_route_options(world, actor_ref, order.source_id, order.destination_id,
                                                 order.resource_id, quantity):
            # A path that keeps the blocked passage is not an alternative.
            if not route_option.route_ids or set(route_option.route_ids).intersection(blocked):
                continue
            options.append(FreightRecoveryOption(
                id=f"{base}:{quantity}:{route_option.id}", kind="successor", quantity=quantity,
                route_option_id=route_option.id, route_ids=route_option.route_ids, **common))
    return tuple(sorted(options, key=lambda item: item.id))


def execute_freight_recovery(world, option_id, *, decision_event_id):
    """Revalidate everything, then open a successor without touching the original."""
    world.economy.validate(world)
    decision = next((event for event in world.events if event.id == decision_event_id), None)
    if (decision is None or decision.fact_kind != FactKind.DECISION
            or decision.causal_origin == CausalOrigin.LLM_INTERPRETATION
            or decision.day != world.clock.absolute_day or not isinstance(decision.decision, dict)
            or decision.decision.get("action") != RECOVERY_ACTION):
        raise ValueError("freight recovery requires a current actor decision")
    try:
        actor_ref = EntityRef.from_dict(decision.decision.get("actor_ref"))
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError("freight recovery decision has an invalid actor") from exc
    option = next((item for item in freight_recovery_options(world, actor_ref) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("freight recovery option is stale or was not selected by this owner")
    if option.kind == "wait":
        # Waiting changes nothing material; the decision itself is the record.
        return None
    require_authority(world, actor_ref, "supply")
    # The selected path is revalidated against current capacity and current
    # customs posts, exactly as a new shipment would be.
    validate_fiscal_route_option(world, option.route_option_id, actor_ref, option.source_id,
                                 option.destination_id, option.resource_id, option.quantity)
    blocked = world.economy.freight_orders[option.order_id]
    return open_order(world, option.source_id, option.destination_id, option.resource_id, option.quantity,
                      option.route_ids, decision_ids=(decision_event_id,), cause_ids=(blocked.last_event_id,))

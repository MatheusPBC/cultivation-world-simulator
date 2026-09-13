"""Conservative freight executors over the world's canonical route graph."""

import math

from src.classes.economy.logistics import CargoParcel, FreightOrder, RouteFlow, path_regions
from src.classes.event import FactKind
from src.classes.governance.authority import require_authority
from src.systems.calendar_agenda import ScheduledSituation
from .economy import _causes, _delta
from .events import record_event
from .travel import route_duration


def check_freight(world, source_id, destination_id, resource_id, quantity, route_ids):
    if type(quantity) is not int or quantity <= 0 or resource_id not in world.economy.resources:
        raise ValueError("freight requires a known resource and positive integer quantity")
    path_regions(world, source_id, destination_id, route_ids, resource_id)
    if world.economy.stocks[source_id].goods.get(resource_id, 0) < quantity:
        raise ValueError("insufficient goods")


def open_order(world, source_id, destination_id, resource_id, quantity, route_ids, *, decision_ids):
    """Private material operation shared by approved internal transfers and purchases."""
    check_freight(world, source_id, destination_id, resource_id, quantity, route_ids)
    economy = world.economy
    if any(set(decision_ids).intersection(o.decision_ids) for o in economy.freight_orders.values()):
        raise ValueError("freight decision already executed")
    seq = len(world.events) + 1
    source = economy.stocks[source_id]
    order = FreightOrder(id=f"freight:{seq}", source_id=source_id, destination_id=destination_id,
                         resource_id=resource_id, quantity=quantity, owner_ref=economy.stocks[destination_id].owner_ref,
                         route_ids=tuple(route_ids), decision_ids=tuple(decision_ids),
                         created_day=world.clock.absolute_day, priority=seq)
    parcel = CargoParcel(id=f"parcel:{seq}", order_id=order.id, quantity=quantity,
                         stage="waiting" if route_ids else "unloading", due_day=world.clock.absolute_day + 1)
    if parcel.id in economy.parcels or world.agenda.get(parcel.id) is not None or order.id in economy.freight_orders:
        raise ValueError("cargo identity collision")
    available = source.goods.get(resource_id, 0)
    event = record_event(world, "freight_opened", f"Remessa de {quantity} unidades preparada.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("stock", source.id, resource_id, available, available - quantity),
                                 _delta("cargo", parcel.id, "quantity", 0, quantity)),
                         cause_ids=_causes(*decision_ids, source.last_event_ids.get(resource_id)))
    order = order.model_copy(update={"last_event_id": event.id})
    parcel = parcel.model_copy(update={"last_event_id": event.id})
    economy.stocks[source.id] = source.model_copy(update={
        "goods": {**source.goods, resource_id: available - quantity},
        "last_event_ids": {**source.last_event_ids, resource_id: event.id}})
    economy.freight_orders[order.id], economy.parcels[parcel.id] = order, parcel
    world.agenda.schedule(ScheduledSituation(parcel.id, "cargo", parcel.due_day))
    return order


def queue_freight(world, source_id, destination_id, resource_id, quantity, route_ids, *, decision_event_id):
    world.economy.validate(world)
    check_freight(world, source_id, destination_id, resource_id, quantity, route_ids)
    source, destination = world.economy.stocks[source_id], world.economy.stocks[destination_id]
    event = next((e for e in world.events if e.id == decision_event_id), None)
    expected = {"action": "freight", "source_id": source_id, "destination_id": destination_id,
                "resource_id": resource_id, "quantity": quantity, "route_ids": list(route_ids),
                "actor_ref": source.owner_ref.to_dict()}
    if (source.owner_ref != destination.owner_ref or event is None or event.fact_kind != FactKind.DECISION
            or event.decision != expected):
        raise ValueError("internal freight requires the owner's matching decision")
    require_authority(world, source.owner_ref, "supply")
    return open_order(world, source_id, destination_id, resource_id, quantity, route_ids,
                      decision_ids=(decision_event_id,))


def _route_causes(world, route_ids):
    """Derive provenance once for this batch; cargo cannot mutate routes/sites."""
    pending = set(route_ids)
    latest = {}
    if pending:
        for event in reversed(world.events):
            for delta in event.deltas:
                if delta.owner_kind == "route" and delta.owner_id in pending:
                    latest[delta.owner_id] = event.id
                    pending.remove(delta.owner_id)
            if not pending:
                break
    return {route_id: _causes(latest.get(route_id), *(s.last_event_id
            for s in world.map.infrastructure_sites.values() if route_id in s.route_ids))
            for route_id in route_ids}


def _record_parcel(world, parcel, updated, event_type, content, *, extra_deltas=(), cause_ids=(), remainder=None):
    changes = []
    if updated is None:
        changes.append(_delta("cargo", parcel.id, "quantity", parcel.quantity, 0))
    else:
        for name in ("quantity", "stage", "route_index", "due_day"):
            if getattr(parcel, name) != getattr(updated, name):
                changes.append(_delta("cargo", parcel.id, name, getattr(parcel, name), getattr(updated, name)))
    if remainder:
        changes.append(_delta("cargo", remainder.id, "quantity", 0, remainder.quantity))
    order = world.economy.freight_orders[parcel.order_id]
    event = record_event(world, event_type, content, fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(*changes, *extra_deltas),
                         cause_ids=_causes(parcel.last_event_id, order.last_event_id, *cause_ids))
    world.economy.freight_orders[order.id] = order.model_copy(update={"last_event_id": event.id})
    if updated is None:
        del world.economy.parcels[parcel.id]
    for value in (updated, remainder):
        if value is not None:
            value = value.model_copy(update={"last_event_id": event.id})
            world.economy.parcels[value.id] = value
            world.agenda.schedule(ScheduledSituation(value.id, "cargo", value.due_day))
    return event


def _unload(world, parcel):
    economy = world.economy
    order = economy.freight_orders[parcel.order_id]
    stock = economy.stocks[order.destination_id]
    capacity = max(0, (stock.capacity - economy.used_capacity(stock)) // economy.resources[order.resource_id].bulk)
    amount = min(parcel.quantity, capacity)
    remaining = parcel.quantity - amount
    updated = parcel.model_copy(update={"quantity": remaining, "stage": "unloading",
                                         "due_day": world.clock.absolute_day + 1}) if remaining else None
    deltas = ()
    if amount:
        deltas = (_delta("stock", stock.id, order.resource_id, stock.goods.get(order.resource_id, 0),
                          stock.goods.get(order.resource_id, 0) + amount),
                  _delta("freight", order.id, "delivered_quantity", order.delivered_quantity, order.delivered_quantity + amount))
    event = _record_parcel(world, parcel, updated, "cargo_delivered" if amount else "cargo_delayed",
                            f"Entrega: {amount} unidades descarregadas; {remaining} aguardando espaço.",
                            extra_deltas=deltas, cause_ids=_causes(stock.last_event_ids.get(order.resource_id)))
    if amount:
        economy.stocks[stock.id] = stock.model_copy(update={
            "goods": {**stock.goods, order.resource_id: stock.goods.get(order.resource_id, 0) + amount},
            "last_event_ids": {**stock.last_event_ids, order.resource_id: event.id}})
        economy.freight_orders[order.id] = economy.freight_orders[order.id].model_copy(
            update={"delivered_quantity": order.delivered_quantity + amount})


def _resolve_parcel(world, parcel, route_causes):
    economy = world.economy
    order = economy.freight_orders[parcel.order_id]
    day = world.clock.absolute_day
    if parcel.stage == "unloading":
        _unload(world, parcel)
        return
    route_id = order.route_ids[parcel.route_index]
    route = world.map.routes[route_id]
    capacity = math.floor(world.map.get_route_operational_capacity(route_id))
    causes = route_causes[route_id]
    if capacity <= 0 or not route.allows_resource(order.resource_id):
        _record_parcel(world, parcel, parcel.model_copy(update={"due_day": day + 1}),
                       "cargo_delayed", "Passagem indisponível; carga preservada.", cause_ids=causes)
        return
    if parcel.stage == "traveling":
        if parcel.route_index == len(order.route_ids) - 1:
            _unload(world, parcel)
        else:
            updated = parcel.model_copy(update={"route_index": parcel.route_index + 1, "stage": "waiting", "due_day": day + 1})
            _record_parcel(world, parcel, updated, "cargo_waypoint_reached", "Carga chegou ao próximo trecho.", cause_ids=causes)
        return
    old_flow = economy.route_flows.get(route_id)
    used = old_flow.bulk if old_flow is not None and old_flow.day == day else 0
    available = max(0, capacity - used)
    quantity = min(parcel.quantity, available // economy.resources[order.resource_id].bulk)
    if quantity == 0:
        _record_parcel(world, parcel, parcel.model_copy(update={"due_day": day + 1}),
                       "cargo_delayed", "Vazão diária insuficiente; carga aguarda despacho.", cause_ids=causes)
        return
    remaining = parcel.quantity - quantity
    remainder = (parcel.model_copy(update={"id": f"parcel:{len(world.events) + 1}:remainder", "quantity": remaining,
                                           "due_day": day + 1}) if remaining else None)
    updated = parcel.model_copy(update={"quantity": quantity, "stage": "traveling", "due_day": day + route_duration(world, route_id)})
    flow = RouteFlow(id=route_id, day=day, bulk=used + quantity * economy.resources[order.resource_id].bulk)
    deltas = (_delta("route_flow", route_id, "day", old_flow.day if old_flow else None, day),
              _delta("route_flow", route_id, "bulk", old_flow.bulk if old_flow else 0, flow.bulk))
    _record_parcel(world, parcel, updated, "cargo_departed", f"Carga de {quantity} unidades despachada.",
                   extra_deltas=deltas, cause_ids=causes, remainder=remainder)
    economy.route_flows[route_id] = flow


def resolve_parcels(world, situations):
    # Arrivals before departures; FIFO orders share each day's canonical route flow.
    parcels = []
    for situation in situations:
        parcel = world.economy.parcels.get(situation.id)
        if situation.kind != "cargo" or parcel is None or parcel.due_day != world.clock.absolute_day:
            raise ValueError("unknown or inconsistent dated cargo")
        parcels.append(parcel)
    route_causes = _route_causes(world, {
        world.economy.freight_orders[p.order_id].route_ids[p.route_index]
        for p in parcels if p.stage != "unloading"})
    for parcel in sorted(parcels, key=lambda p: (p.stage == "waiting", world.economy.freight_orders[p.order_id].priority, p.id)):
        _resolve_parcel(world, parcel, route_causes)

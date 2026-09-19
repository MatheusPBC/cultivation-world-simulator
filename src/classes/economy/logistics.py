"""Cargo quantities and scheduling; all spatial paths reference the canonical Map."""

from collections import defaultdict
from typing import Literal

from pydantic import model_validator

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Count, Identity, SocietyValue
from .models import Positive


class FreightOrder(SocietyValue):
    id: Identity
    source_id: Identity
    destination_id: Identity
    resource_id: Identity
    quantity: Positive
    delivered_quantity: Count = 0
    resolved_quantity: Count = 0
    owner_ref: EntityRef
    route_ids: tuple[Identity, ...]
    created_day: Count
    priority: Positive
    decision_ids: tuple[Identity, ...]
    last_event_id: Identity | None = None
    resolution_event_id: Identity | None = None


class CargoParcel(SocietyValue):
    id: Identity
    order_id: Identity
    quantity: Positive
    route_index: Count = 0
    stage: Literal["waiting", "held", "traveling", "unloading"] = "waiting"
    due_day: Count
    held_checkpoint_id: Identity | None = None
    held_notice_id: Identity | None = None
    last_event_id: Identity | None = None

    @model_validator(mode="after")
    def held_linkage_matches_stage(self):
        linked = self.held_checkpoint_id is not None and self.held_notice_id is not None
        if (self.stage == "held") != linked:
            raise ValueError("held cargo requires exactly its checkpoint and notice links")
        return self


class RouteFlow(SocietyValue):
    id: Identity  # Map route ID, shared across directions and all orders.
    day: Count
    bulk: Count


def path_regions(world, source_id, destination_id, route_ids, resource_id):
    economy = world.economy
    if source_id not in economy.stocks or destination_id not in economy.stocks or source_id == destination_id:
        raise ValueError("freight requires distinct existing stocks")
    start = world.society.settlements[economy.stocks[source_id].location_id].region_id
    end = world.society.settlements[economy.stocks[destination_id].location_id].region_id
    regions = [start]
    for route_id in route_ids:
        route = world.map.routes.get(route_id)
        if (route is None or regions[-1] not in route.endpoint_region_ids
                or route.mode not in {"road", "river"} or not route.allows_resource(resource_id)):
            raise ValueError("invalid freight route")
        target = next(r for r in route.endpoint_region_ids if r != regions[-1])
        if target in regions:
            raise ValueError("freight path cannot contain a cycle")
        regions.append(target)
    if regions[-1] != end:
        raise ValueError("freight path does not reach destination")
    return tuple(regions)


def validate_logistics(economy, world=None):
    quantities = defaultdict(int)
    used_decisions = set()
    for parcel in economy.parcels.values():
        if parcel.order_id not in economy.freight_orders:
            raise ValueError("unknown parcel order")
        order = economy.freight_orders[parcel.order_id]
        if (parcel.route_index >= len(order.route_ids) and order.route_ids
                or not order.route_ids and (parcel.route_index != 0 or parcel.stage != "unloading")
                or parcel.stage == "unloading" and parcel.route_index != max(0, len(order.route_ids) - 1)):
            raise ValueError("invalid cargo position")
        quantities[parcel.order_id] += parcel.quantity
    for order in economy.freight_orders.values():
        if order.quantity != order.delivered_quantity + order.resolved_quantity + quantities[order.id]:
            raise ValueError("freight quantity is not conserved")
        if order.resolved_quantity and order.resolution_event_id is None:
            raise ValueError("resolved freight quantity requires a resolution receipt")
        if order.resolution_event_id is not None and order.resolved_quantity == 0:
            raise ValueError("freight resolution receipt requires resolved quantity")
        if (order.resource_id not in economy.resources or order.source_id not in economy.stocks
                or order.destination_id not in economy.stocks):
            raise ValueError("unknown freight stock or resource")
        if order.owner_ref != economy.stocks[order.destination_id].owner_ref:
            raise ValueError("cargo belongs to destination owner")
        if (not order.decision_ids or len(set(order.decision_ids)) != len(order.decision_ids)
                or used_decisions.intersection(order.decision_ids)):
            raise ValueError("freight decisions must be unique")
        used_decisions.update(order.decision_ids)
    if world is None:
        return
    events = {e.id: e for e in world.events}
    for order in economy.freight_orders.values():
        path_regions(world, order.source_id, order.destination_id, order.route_ids, order.resource_id)
        if order.created_day > world.clock.absolute_day:
            raise ValueError("future freight creation")
        if any(d not in events or events[d].fact_kind != FactKind.DECISION for d in order.decision_ids):
            raise ValueError("missing freight decision")
        if order.resolution_event_id is not None:
            resolution = events.get(order.resolution_event_id)
            if (resolution is None or resolution.event_type not in {"purchase_recovery_completed", "contraband_returned", "contraband_seized"}
                    or not any(delta.owner_kind == "freight" and delta.owner_id == order.id
                               and delta.aspect == "resolved_quantity"
                               and delta.after == str(order.resolved_quantity)
                               for delta in resolution.deltas)):
                raise ValueError("invalid freight resolution provenance")
    for item in (*economy.freight_orders.values(), *economy.parcels.values()):
        if item.last_event_id is None or item.last_event_id not in events:
            raise ValueError("missing cargo provenance")
    for parcel in economy.parcels.values():
        scheduled = world.agenda.get(parcel.id)
        if parcel.stage == "held":
            if scheduled is not None:
                raise ValueError("held cargo cannot remain on the dated agenda")
        elif (scheduled is None or scheduled.kind != "cargo" or scheduled.due_day != parcel.due_day
              or parcel.due_day <= world.clock.absolute_day):
            raise ValueError("cargo agenda mismatch")
        if parcel.stage == "held":
            notice = world.knowledge.customs_notices.get(parcel.held_notice_id)
            checkpoint = world.economy.customs_checkpoints.get(parcel.held_checkpoint_id)
            if (notice is None or checkpoint is None or notice.state not in {"presented", "fee_due", "detected"}
                    or notice.parcel_id != parcel.id or notice.checkpoint_id != checkpoint.id):
                raise ValueError("held cargo lacks its canonical customs notice")
        elif parcel.held_checkpoint_id is not None or parcel.held_notice_id is not None:
            raise ValueError("unheld cargo cannot retain customs links")
    for scheduled in world.agenda.to_dict():
        if scheduled["kind"] == "cargo" and scheduled["id"] not in economy.parcels:
            raise ValueError("cargo agenda references missing parcel")
    for flow in economy.route_flows.values():
        if flow.id not in world.map.routes or flow.day > world.clock.absolute_day:
            raise ValueError("invalid route flow")

"""Transient route searches over Map routes and actors' dated route knowledge."""

import heapq

from src.classes.mechanical_language import EntityRef
from src.classes.economy.models import Positive
from src.classes.society.models import Identity, SocietyValue
from .travel import route_duration


def _search(world, origin_id, destination_id, cost_of):
    """Shared search over the canonical topology; only the cost source differs."""
    origin = world.society.settlements[origin_id].region_id
    destination = world.society.settlements[destination_id].region_id
    frontier, visited = [(0, (), origin)], set()
    while frontier:
        duration, path, region = heapq.heappop(frontier)
        if region == destination:
            return path
        if region in visited:
            continue
        visited.add(region)
        for rid, route in sorted(world.map.routes.items()):
            if region not in route.endpoint_region_ids:
                continue
            cost = cost_of(rid, route)
            if cost is None:
                continue
            other = next(r for r in route.endpoint_region_ids if r != region)
            if other not in visited:
                heapq.heappush(frontier, (duration + cost + 1, (*path, rid), other))
    return None


def supply_path(world, origin_id, destination_id, resource_id="food"):
    """Canonical physical reachability, owned by the map; not actor knowledge."""
    def cost_of(rid, route):
        if (not route.allows_resource(resource_id)
                or world.map.get_route_operational_capacity(rid) < world.economy.resources[resource_id].bulk):
            return None
        return route_duration(world, rid)
    return _search(world, origin_id, destination_id, cost_of)


def known_supply_path(world, actor_ref, origin_id, destination_id, resource_id="food", *, consulted=None):
    """Plan only over routes this actor observed recently.

    Topology, mode and allowed resources are public identity. Capacity and
    travel time come exclusively from the actor's own dated reports: an
    unobserved route is not an affordance, and neither is a closed one.

    ``consulted`` collects the event IDs of the reports this search actually
    rejected, including bottlenecks in the middle of a path. It is transient
    evidence for the caller, never a stored affordance.
    """
    day = world.clock.absolute_day
    bulk = world.economy.resources[resource_id].bulk
    reports = {r.route_id: r for r in world.knowledge.routes_for_actor(actor_ref)}

    def cost_of(rid, route):
        report = reports.get(rid)
        if (report is None or not 0 <= day - report.observed_day < 30 or report.travel_days is None
                or report.operational_capacity < bulk
                or route.mode not in {"road", "river"} or not route.allows_resource(resource_id)):
            if consulted is not None and report is not None:
                consulted.append(report.event_id)
            return None
        return report.travel_days
    return _search(world, origin_id, destination_id, cost_of)


def _fresh_fiscal_readings(world, actor_ref, resource_id):
    """Return routes with current route reports and any current fiscal receipt.

    A route without a reported checkpoint remains a legal route candidate. If
    a checkpoint is actually present by execution time, the owner will reject
    a selection that did not cite its dated fiscal receipt without telling the
    actor what changed.
    """
    day = world.clock.absolute_day
    bulk = world.economy.resources[resource_id].bulk
    readings = {}
    for route_id, route in world.map.routes.items():
        travel = world.knowledge.route_report(actor_ref, route_id)
        fiscal = world.knowledge.fiscal_route_report(actor_ref, route_id)
        if (travel is None or not 0 <= day - travel.observed_day < 30
                or (fiscal is not None and not 0 <= day - fiscal.observed_day < 30) or travel.travel_days is None
                or travel.operational_capacity < bulk or route.mode not in {"road", "river"}
                or not route.allows_resource(resource_id)):
            continue
        readings[route_id] = (travel, fiscal)
    return readings


def known_fiscal_supply_paths(world, actor_ref, origin_id, destination_id, resource_id="food"):
    """Every simple, currently-known route path with any fiscal reading retained.

    This intentionally does not call ``supply_path`` or inspect current route
    capacity. A physical change after an observation stays unknown until a
    report arrives; the owner executor revalidates the selected option later.
    """
    if resource_id not in world.economy.resources:
        return ()
    origin = world.society.settlements[origin_id].region_id
    destination = world.society.settlements[destination_id].region_id
    if origin == destination:
        return ((),)
    readings = _fresh_fiscal_readings(world, actor_ref, resource_id)
    paths = []

    def visit(region, path, seen):
        if region == destination:
            paths.append(path)
            return
        for route_id, route in sorted(world.map.routes.items()):
            if route_id not in readings or region not in route.endpoint_region_ids:
                continue
            other = next(item for item in route.endpoint_region_ids if item != region)
            if other not in seen:
                visit(other, (*path, route_id), seen | {other})

    visit(origin, (), {origin})
    return tuple(paths)


class FiscalRouteOption(SocietyValue):
    """A transient, actor-readable route choice before a new order exists."""
    id: Identity
    actor_ref: EntityRef
    source_id: Identity
    destination_id: Identity
    resource_id: Identity
    quantity: Positive
    route_ids: tuple[Identity, ...]
    route_report_ids: tuple[Identity, ...]
    fiscal_route_report_ids: tuple[Identity, ...]
    estimated_customs_fee: int

    def selection(self):
        return {"route_option_id": self.id, "route_ids": list(self.route_ids),
                "route_report_ids": list(self.route_report_ids),
                "fiscal_route_report_ids": list(self.fiscal_route_report_ids),
                "estimated_customs_fee": self.estimated_customs_fee}


def fiscal_route_options(world, actor_ref, source_id, destination_id, resource_id, quantity):
    """Enumerate the only fiscal paths an actor may select for a new freight.

    Quantity is engine-computed before this function is called; the caller may
    select an option ID, never invent a route or a fiscal total. Existing
    freight orders are not inputs and therefore cannot be rerouted here.
    """
    if (not isinstance(actor_ref, EntityRef) or type(quantity) is not int or quantity <= 0
            or resource_id not in world.economy.resources
            or source_id not in world.economy.stocks or destination_id not in world.economy.stocks):
        return ()
    source = world.economy.stocks[source_id]
    destination = world.economy.stocks[destination_id]
    bulk = world.economy.resources[resource_id].bulk
    options = []
    for path in known_fiscal_supply_paths(world, actor_ref, source.location_id, destination.location_id, resource_id):
        reports = tuple(world.knowledge.route_report(actor_ref, route_id) for route_id in path)
        fiscal_reports = tuple(world.knowledge.fiscal_route_report(actor_ref, route_id) for route_id in path)
        if any(report is None for report in reports):
            continue
        route_report_ids = tuple(report.event_id for report in reports)
        fiscal_report_ids = tuple(report.event_id for report in fiscal_reports if report is not None)
        estimated_fee = quantity * bulk * sum(report.fee_per_bulk for report in fiscal_reports if report is not None)
        basis = ":".join((*path, *route_report_ids, *fiscal_report_ids)) or "local"
        options.append(FiscalRouteOption(
            id=(f"fiscal-route:{actor_ref.kind}:{actor_ref.id}:{source_id}:{destination_id}:{resource_id}:"
                f"{quantity}:{estimated_fee}:{basis}"), actor_ref=actor_ref, source_id=source_id,
            destination_id=destination_id, resource_id=resource_id, quantity=quantity, route_ids=path,
            route_report_ids=route_report_ids, fiscal_route_report_ids=fiscal_report_ids,
            estimated_customs_fee=estimated_fee))
    return tuple(sorted(options, key=lambda item: (item.estimated_customs_fee, len(item.route_ids), item.route_ids, item.id)))


def validate_fiscal_route_option(world, option_id, actor_ref, source_id, destination_id, resource_id, quantity):
    """Owner-side revalidation of a selected path, including current material terms."""
    option = next((item for item in fiscal_route_options(world, actor_ref, source_id, destination_id, resource_id, quantity)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("fiscal route option is stale or unavailable")
    # The actor's evidence may still be fresh while a new post or closure has
    # happened since it was observed. Do not disclose that change; simply reject
    # the stale selection before any stock, cash, or order mutates.
    from .route_intelligence import fiscal_runtime
    from src.classes.economy.logistics import path_regions

    path_regions(world, source_id, destination_id, option.route_ids, resource_id)
    bulk = world.economy.resources[resource_id].bulk
    for route_id, fiscal_report in zip(option.route_ids, (world.knowledge.fiscal_route_report(actor_ref, item)
                                                          for item in option.route_ids), strict=True):
        route = world.map.routes[route_id]
        if world.map.get_route_operational_capacity(route_id) < bulk:
            raise ValueError("fiscal route option is stale or unavailable")
        checkpoint = fiscal_runtime(world, route_id)
        if checkpoint is not None and (fiscal_report is None
                                       or (checkpoint.id, checkpoint.fee_per_bulk)
                                       != (fiscal_report.checkpoint_id, fiscal_report.fee_per_bulk)):
            raise ValueError("fiscal route option is stale or unavailable")
        if checkpoint is None and fiscal_report is not None:
            raise ValueError("fiscal route option is stale or unavailable")
        if route.mode not in {"road", "river"} or not route.allows_resource(resource_id):
            raise ValueError("fiscal route option is stale or unavailable")
    return option

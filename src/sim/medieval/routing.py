"""Transient least-travel-time search on Map.routes; no second route registry."""

import heapq
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

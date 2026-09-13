"""Transient least-travel-time search on Map.routes; no second route registry."""

import heapq
from .travel import route_duration


def supply_path(world, origin_id, destination_id, resource_id="food"):
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
            if (region not in route.endpoint_region_ids or not route.allows_resource(resource_id)
                    or world.map.get_route_operational_capacity(rid) < world.economy.resources[resource_id].bulk):
                continue
            other = next(r for r in route.endpoint_region_ids if r != region)
            if other not in visited:
                heapq.heappush(frontier, (duration + route_duration(world, rid) + 1, (*path, rid), other))
    return None

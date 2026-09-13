"""Shared distance/time conversion for people and cargo on Map routes."""

import math


def route_duration(world, route_id: str) -> int:
    route = world.map.routes[route_id]
    if route.mode not in {"road", "river"} or route.quality <= 0:
        raise ValueError("route has no usable travel speed")
    origin, destination = (world.map.regions[r].center_loc for r in route.endpoint_region_ids)
    speed = 20 if route.mode == "road" else 40
    return max(1, math.ceil(math.dist(origin, destination) * 10 / (speed * route.quality)))

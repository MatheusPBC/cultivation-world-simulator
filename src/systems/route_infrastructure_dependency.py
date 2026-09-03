"""Causal projection from map-owned sites to route operational capacity."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
import uuid

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)


_EVENT_NAMESPACE = uuid.UUID("d5af3bb7-bfb0-4ad2-8f58-4a9a158ad40d")


def _parse_bool(value: Any, field_name: str) -> bool:
    if value is True or value == "True":
        return True
    if value is False or value == "False":
        return False
    raise ValueError(f"{field_name} must contain a boolean")


def _site_transition(
    world: Any,
    event: Event,
) -> tuple[str, dict[str, float | bool], dict[str, float | bool]]:
    payload = event.causal_payload
    if not isinstance(payload, dict):
        raise ValueError("infrastructure condition event must have a causal payload")
    site_id = str(payload.get("site_id", "")).strip()
    site = getattr(getattr(world, "map", None), "infrastructure_sites", {}).get(site_id)
    if site is None:
        raise ValueError("infrastructure condition event references an unknown site")

    before: dict[str, float | bool] = {
        "integrity": float(site.integrity),
        "enabled": bool(site.enabled),
    }
    after = dict(before)
    found = False
    for delta in payload.get("deltas", ()):
        if not isinstance(delta, dict):
            raise ValueError("infrastructure condition delta must be an object")
        if (
            str(delta.get("owner_kind")) != "infrastructure_site"
            or str(delta.get("owner_id")) != site_id
        ):
            continue
        aspect = str(delta.get("aspect"))
        if aspect == "integrity":
            before[aspect] = float(delta["before"])
            after[aspect] = float(delta["after"])
            found = True
        elif aspect == "enabled":
            before[aspect] = _parse_bool(delta.get("before"), "enabled before")
            after[aspect] = _parse_bool(delta.get("after"), "enabled after")
            found = True
    if not found:
        raise ValueError("infrastructure condition event has no site runtime delta")
    site.validate_runtime(
        integrity=float(before["integrity"]),
        enabled=bool(before["enabled"]),
    )
    site.validate_runtime(
        integrity=float(after["integrity"]),
        enabled=bool(after["enabled"]),
    )
    return site_id, before, after


def _runtime_pair(values: dict[str, float | bool]) -> tuple[float, bool]:
    return float(values["integrity"]), bool(values["enabled"])


def project_route_capacity_changes(
    world: Any,
    current_events: Iterable[Event],
) -> list[tuple[Event, str, float, float, tuple[str, ...]]]:
    """Project ordered route changes without mutating sites or routes."""
    source_events = [
        event
        for event in current_events
        if event.event_type
        in {"infrastructure_site_condition_changed", "infrastructure_site_restored"}
    ]
    transitions = [(event, *_site_transition(world, event)) for event in source_events]
    if not transitions:
        return []

    # Canonical sites already contain the final state. Reverse the event stream
    # once so projections remain correct when several dependencies changed in
    # the same month.
    virtual_runtime = {
        site_id: _runtime_pair(after)
        for _, site_id, _, after in transitions
    }
    for _, site_id, before, _ in reversed(transitions):
        virtual_runtime[site_id] = _runtime_pair(before)

    projected: list[tuple[Event, str, float, float, tuple[str, ...]]] = []
    for source_event, site_id, before, after in transitions:
        site = world.map.infrastructure_sites[site_id]
        if virtual_runtime[site_id] != _runtime_pair(before):
            raise ValueError("infrastructure condition events are not causally contiguous")
        before_overrides = dict(virtual_runtime)
        virtual_runtime[site_id] = _runtime_pair(after)
        for route_id in site.route_ids:
            before_capacity = world.map.get_route_operational_capacity(
                route_id,
                site_runtime_overrides=before_overrides,
            )
            after_capacity = world.map.get_route_operational_capacity(
                route_id,
                site_runtime_overrides=virtual_runtime,
            )
            if after_capacity == before_capacity:
                continue
            dependency_ids = tuple(
                item.id for item in world.map.get_route_dependency_sites(route_id)
            )
            projected.append(
                (source_event, route_id, before_capacity, after_capacity, dependency_ids)
            )
    for site_id in virtual_runtime:
        site = world.map.infrastructure_sites[site_id]
        if virtual_runtime[site_id] != (float(site.integrity), bool(site.enabled)):
            raise ValueError("infrastructure condition events do not reach canonical state")
    return projected


def process_route_infrastructure_dependencies(
    world: Any,
    *,
    current_events: Iterable[Event],
    invalidations: DomainInvalidationQueue,
) -> list[Event]:
    """Record meaningful changes in a route's derived usable capacity."""
    current_events = list(current_events)
    known_event_ids = {event.id for event in current_events}
    events: list[Event] = []
    for source_event, route_id, before, after, dependency_ids in (
        project_route_capacity_changes(world, current_events)
    ):
        event_id = str(
            uuid.uuid5(
                _EVENT_NAMESPACE,
                f"{source_event.id}:{route_id}:operational_capacity",
            )
        )
        if event_id in known_event_ids:
            continue
        route = world.map.routes[route_id]
        event = Event(
            world.month_stamp,
            t(
                "Route {route} changed operational capacity.",
                route=route.id,
            ),
            event_type="route_operational_capacity_changed",
            render_key="route_operational_capacity_changed",
            render_params={
                "route_id": route.id,
                "source_site_id": str((source_event.causal_payload or {}).get("site_id")),
                "endpoint_region_ids": [str(item) for item in route.endpoint_region_ids],
                "allowed_resource_ids": list(route.allowed_resource_ids),
            },
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.DETERMINISTIC,
            id=event_id,
        )
        delta = StateDelta(
            event_id=event.id,
            owner_kind="route",
            owner_id=route.id,
            aspect="operational_capacity",
            before=str(before),
            after=str(after),
            magnitude=after - before,
        )
        event.causal_payload = {
            "outcome": "changed",
            "route_id": route.id,
            "dependency_site_ids": list(dependency_ids),
            "deltas": [delta.to_dict()],
        }
        event.causal_links.append(
            CausalLink(
                event_id=event.id,
                cause_event_id=source_event.id,
                relation=CausalRelation.TRIGGERED_BY,
            )
        )
        for region_id in route.endpoint_region_ids:
            invalidations.mark(
                DomainInvalidation(
                    layer=DomainInvalidationLayer.MECHANICAL,
                    domain="region",
                    target_kind="region",
                    target_id=str(region_id),
                    reason=DomainInvalidationReason.ROUTE_CAPACITY_CHANGED,
                    source_event_ids=(event.id,),
                    revision=event.id,
                )
            )
        events.append(event)
        known_event_ids.add(event.id)
    return events


__all__ = [
    "process_route_infrastructure_dependencies",
    "project_route_capacity_changes",
]

"""Validated material changes to map-owned infrastructure sites."""

from __future__ import annotations

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


def change_infrastructure_site_condition(
    world: Any,
    *,
    site_id: str,
    source_event_id: str,
    invalidations: DomainInvalidationQueue,
    integrity: float | None = None,
    enabled: bool | None = None,
    event_id: str | None = None,
) -> Event:
    """Change physical condition without applying downstream effects.

    The caller supplies a causal source and a requested target state.  The map
    validates and owns the mutation; later domain evaluation decides whether
    the changed site matters to any route, city, organization, or population.
    """
    if not isinstance(site_id, str) or not site_id.strip():
        raise ValueError("site_id must be a non-empty string")
    if not isinstance(source_event_id, str) or not source_event_id.strip():
        raise ValueError("source_event_id must be a non-empty string")
    if integrity is None and enabled is None:
        raise ValueError("at least one runtime field must be provided")
    if event_id is not None and (
        not isinstance(event_id, str) or not event_id.strip()
    ):
        raise ValueError("event_id must be a non-empty string or null")

    game_map = getattr(world, "map", None)
    sites = getattr(game_map, "infrastructure_sites", None)
    if not isinstance(sites, dict) or site_id not in sites:
        raise KeyError(f"unknown infrastructure site: {site_id}")
    site = sites[site_id]

    before_integrity = float(site.integrity)
    before_enabled = bool(site.enabled)
    requested_integrity = before_integrity if integrity is None else integrity
    requested_enabled = before_enabled if enabled is None else enabled

    # Validate on the model before creating an event or touching the update
    # queue.  A failed command must leave the whole runtime unchanged.
    site.validate_runtime(integrity=requested_integrity, enabled=requested_enabled)
    if requested_integrity == before_integrity and requested_enabled is before_enabled:
        raise ValueError("infrastructure site update must change canonical state")

    event = Event(
        world.month_stamp,
        t(
            "Infrastructure site {site} changed physical condition.",
            site=site.name,
        ),
        event_type="infrastructure_site_condition_changed",
        render_key="infrastructure_site_condition_changed",
        render_params={
            "site_id": site.id,
            "site_name": site.name,
            "region_ids": [str(region_id) for region_id in site.region_ids],
            "source_event_id": source_event_id,
        },
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
        id=event_id or str(uuid.uuid4()),
    )

    deltas: list[StateDelta] = []
    if requested_integrity != before_integrity:
        deltas.append(StateDelta(
            event_id=event.id,
            owner_kind="infrastructure_site",
            owner_id=site.id,
            aspect="integrity",
            before=str(before_integrity),
            after=str(float(requested_integrity)),
            magnitude=float(requested_integrity) - before_integrity,
        ))
    if requested_enabled is not before_enabled:
        deltas.append(StateDelta(
            event_id=event.id,
            owner_kind="infrastructure_site",
            owner_id=site.id,
            aspect="enabled",
            before=str(before_enabled),
            after=str(requested_enabled),
        ))

    game_map.update_infrastructure_site_runtime(
        site.id,
        integrity=requested_integrity,
        enabled=requested_enabled,
        last_event_id=event.id,
    )
    event.causal_payload = {
        "outcome": "changed",
        "site_id": site.id,
        "deltas": [delta.to_dict() for delta in deltas],
    }
    event.causal_links.append(CausalLink(
        event_id=event.id,
        cause_event_id=source_event_id,
        relation=CausalRelation.TRIGGERED_BY,
    ))

    for region_id in site.region_ids:
        invalidations.mark(DomainInvalidation(
            layer=DomainInvalidationLayer.MECHANICAL,
            domain="region",
            target_kind="region",
            target_id=str(region_id),
            reason=DomainInvalidationReason.INFRASTRUCTURE_CHANGED,
            source_event_ids=(event.id,),
            revision=event.id,
        ))
    return event


__all__ = ["change_infrastructure_site_condition"]

"""Deterministic executor for grounded urban maintenance intents."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)


MAX_MAINTENANCE_IMPROVEMENT = 0.10


def _event(
    world: Any,
    region: CityRegion,
    *,
    event_type: str,
    content: str,
    capability_id: str,
    decision_event_id: str,
    trigger_event_id: str,
    payload: dict[str, Any],
    fact_kind: FactKind,
) -> Event:
    event = Event(
        world.month_stamp,
        content,
        event_type=event_type,
        render_key=event_type,
        render_params={
            "region_id": str(region.id),
            "capability_id": capability_id,
            "decision_event_id": decision_event_id,
            "trigger_event_id": trigger_event_id,
        },
        fact_kind=fact_kind,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload=payload,
    )
    if decision_event_id:
        event.causal_links.append(CausalLink(
            event_id=event.id,
            cause_event_id=decision_event_id,
            relation=CausalRelation.MOTIVATED_BY,
        ))
    if trigger_event_id and trigger_event_id != decision_event_id:
        event.causal_links.append(CausalLink(
            event_id=event.id,
            cause_event_id=trigger_event_id,
            relation=CausalRelation.TRIGGERED_BY,
        ))
    return event


def _blocked(
    world: Any,
    region: CityRegion,
    *,
    capability_id: str,
    decision_event_id: str,
    trigger_event_id: str,
    reason: str,
) -> Event:
    return _event(
        world,
        region,
        event_type="city_maintenance_blocked",
        content=t(
            "Urban maintenance in {region} was blocked: {reason}",
            region=region.name,
            reason=reason,
        ),
        capability_id=capability_id,
        decision_event_id=decision_event_id,
        trigger_event_id=trigger_event_id,
        payload={
            "deltas": [],
            "outcome": "blocked",
            "reason": reason,
            "capability_id": capability_id,
        },
        fact_kind=FactKind.OCCURRENCE,
    )


def execute_urban_maintenance(
    world: Any,
    region: CityRegion,
    *,
    capability_id: str,
    decision_event_id: str,
    trigger_event_id: str,
    invalidations: DomainInvalidationQueue | None = None,
) -> Event:
    """Apply one bounded maintenance operation to one existing urban asset.

    The executor owns the amount and the mutation.  The interpreter can only
    request a capability that is grounded by an asset in this city.
    """
    governance = region.city_state.governance
    if governance.administrative_capacity <= 0:
        return _blocked(
            world,
            region,
            capability_id=capability_id,
            decision_event_id=decision_event_id,
            trigger_event_id=trigger_event_id,
            reason="administrative capacity is unavailable",
        )

    candidates = sorted(
        (
            asset
            for asset in region.city_state.assets
            if capability_id in asset.capability_ids
        ),
        key=lambda asset: (asset.integrity, asset.id),
    )
    if not candidates:
        return _blocked(
            world,
            region,
            capability_id=capability_id,
            decision_event_id=decision_event_id,
            trigger_event_id=trigger_event_id,
            reason="the requested capability is not grounded in an urban asset",
        )

    asset = candidates[0]
    headroom = max(0.0, 1.0 - asset.integrity)
    improvement = min(
        MAX_MAINTENANCE_IMPROVEMENT,
        headroom,
        max(0.0, float(governance.administrative_capacity)) * MAX_MAINTENANCE_IMPROVEMENT,
    )
    if improvement <= 0:
        return _blocked(
            world,
            region,
            capability_id=capability_id,
            decision_event_id=decision_event_id,
            trigger_event_id=trigger_event_id,
            reason="the urban asset has no integrity headroom",
        )

    replacement = replace(asset, integrity=min(1.0, asset.integrity + improvement))
    replacements = tuple(
        replacement if current.id == asset.id else current
        for current in region.city_state.assets
    )
    region.city_state = replace(region.city_state, assets=replacements)

    delta = StateDelta(
        owner_kind="region",
        owner_id=str(region.id),
        aspect="urban_asset_integrity",
        before=str(asset.integrity),
        after=str(replacement.integrity),
        magnitude=improvement,
    )
    event = _event(
        world,
        region,
        event_type="city_maintenance_completed",
        content=t(
            "Urban maintenance improved {capability} in {region}.",
            capability=capability_id,
            region=region.name,
        ),
        capability_id=capability_id,
        decision_event_id=decision_event_id,
        trigger_event_id=trigger_event_id,
        payload={
            "deltas": [],
            "outcome": "completed",
            "capability_id": capability_id,
            "asset_id": asset.id,
            "improvement": improvement,
        },
        fact_kind=FactKind.STATE_TRANSITION,
    )
    # The same numbers the delta and the payload already state, promoted to
    # `render_params` because that is the only part of an event institutional
    # memory projects: `decision_context` never reads `causal_payload`, so a
    # remembered repair would otherwise reach a later prompt without saying
    # which asset improved or by how much.
    event.render_params.update({
        "asset_id": asset.id,
        "improvement": improvement,
        "integrity_before": asset.integrity,
        "integrity_after": replacement.integrity,
    })
    delta.event_id = event.id
    event.causal_payload["deltas"] = [delta.to_dict()]

    if invalidations is not None:
        invalidations.mark(DomainInvalidation(
            layer=DomainInvalidationLayer.MECHANICAL,
            domain="city",
            target_kind="region",
            target_id=str(region.id),
            reason=DomainInvalidationReason.INFRASTRUCTURE_CHANGED,
            source_event_ids=(event.id,),
            revision=event.id,
        ))
    return event


__all__ = ["MAX_MAINTENANCE_IMPROVEMENT", "execute_urban_maintenance"]

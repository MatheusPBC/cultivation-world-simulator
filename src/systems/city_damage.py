"""The one owner that lowers an urban asset's integrity.

Before this module the world could only repair a city: `city_maintenance`
raises integrity, and the only writer that lowered it was the causal probe
harness. This is its mirror.

It is deliberately **not** a generic "damage this asset by N" API. The public
entry point accepts an affordance context, the offered option and the actor's
real decision fact, then re-derives the target and the magnitude from current
canonical state and the declared crowd damage profile. A caller cannot supply
a magnitude, an event type or a decision id of its own choosing, so no path
exists for an arbitrary 1.0 or a NaN to reach the asset.

Nothing is mutated until the fact and its delta are fully built and every
check has passed, so a rejected attempt leaves no partial write behind.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.systems.domain_affordance_registry import (
    StaleAffordanceError,
    validate_actor_decision,
)


def _region(world: Any, region_id: str) -> CityRegion | None:
    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    region = regions.get(region_id)
    if region is None:
        try:
            region = regions.get(int(region_id))
        except (TypeError, ValueError):
            return None
    return region if isinstance(region, CityRegion) else None


def execute_crowd_damage(
    context: Any,
    option: Any,
    *,
    decision_event_id: str,
    decision_event: Any = None,
    invalidations: DomainInvalidationQueue | None = None,
) -> Event:
    """Apply one riot completely: damage, fact, knowledge and spent receipt.

    The whole operation, so there is exactly one public door. Raises
    `StaleAffordanceError` unless the actor's own canonical decision selected
    exactly this option, and the option still names a target the current law
    and the asset's declared profile really admit.
    """
    from src.systems.civil_riot import (
        RIOT_ACTION,
        RIOT_EVENT_TYPE,
        aggrieved_crowd_wan,
        service_shortfall,
    )

    # 1. Authorship. An id alone authorizes nothing, and validating one
    #    decision while citing another would leave the chain broken.
    validate_actor_decision(decision_event, context, option, label="public riot")
    if str(getattr(decision_event, "id", "")) != str(decision_event_id):
        raise StaleAffordanceError("public riot decision id does not match")
    if str(getattr(option, "action_kind", "")) != RIOT_ACTION:
        raise StaleAffordanceError("public riot option is not a riot")

    world = context.world
    condition = context.condition
    parameters = getattr(option, "parameters", None)
    if not isinstance(parameters, Mapping):
        raise StaleAffordanceError("public riot option carries no parameters")
    region = _region(world, str(parameters.get("region_id", "")))
    if (
        region is None
        or condition is None
        or str(condition.id) != str(parameters.get("condition_instance_id", ""))
    ):
        raise StaleAffordanceError("public riot grievance is absent or stale")

    # 2. The option must still be one the provider composes from current
    #    state, matched by its canonical id. Because `DomainAffordance.id` is
    #    derived from the whole content, this rejects a forged or tampered
    #    option -- including one whose `damage` was inflated -- and, since the
    #    provider refuses a grievance whose riot receipt is already spent, it
    #    also rejects a replay. Composition is read-only: nothing executes.
    from src.systems.domain_affordance_registry import DOMAIN_AFFORDANCES

    live = next(
        (
            item
            for item in DOMAIN_AFFORDANCES.compose(context)
            if str(item.action_kind) == RIOT_ACTION and str(item.id) == str(option.id)
        ),
        None,
    )
    if live is None or dict(live.parameters) != dict(parameters):
        raise StaleAffordanceError("public riot option is not currently offered")

    # 3. The magnitude is re-derived from the current world and the asset's
    #    declared profile. The option's own `damage` is never the amount
    #    applied; it only had to match the live composition above.
    asset_id = str(parameters.get("asset_id", ""))
    capability_id = str(parameters.get("capability_id", ""))
    asset = next(
        (item for item in region.city_state.assets if str(item.id) == asset_id),
        None,
    )
    profile = getattr(asset, "crowd_damage_profile", None) if asset else None
    if asset is None or profile is None:
        raise StaleAffordanceError("public riot target declares no crowd profile")
    loss = min(
        _recomputed_damage(world, region, asset, capability_id),
        float(asset.integrity),
    )
    if not loss > 0.0:
        raise StaleAffordanceError("public riot has no material basis now")

    # 4. Build the fact, its links and its delta completely, before writing.
    from src.i18n import t

    crowd_wan = aggrieved_crowd_wan(region, asset, capability_id)
    replacement = replace(asset, integrity=max(0.0, float(asset.integrity) - loss))
    event = Event(
        world.month_stamp,
        t(
            "A crowd in {region} broke into {asset}.",
            region=getattr(region, "name", str(region.id)),
            asset=asset_id,
        ),
        event_type=RIOT_EVENT_TYPE,
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "region_id": str(region.id),
            "asset_id": asset_id,
            "capability_id": capability_id,
            "damage": loss,
            "crowd_wan": crowd_wan,
        },
        causal_payload={
            "deltas": [],
            "affordance_id": str(option.id),
            "civil_riot": {
                "region_id": str(region.id),
                "condition_instance_id": str(condition.id),
                # The delta is owned by the region and named by aspect, exactly
                # as maintenance records it, so the payload must say which
                # asset moved or the target would be ambiguous.
                "asset_id": asset_id,
                "capability_id": capability_id,
                "crowd_wan": crowd_wan,
                "service_shortfall": service_shortfall(region, capability_id),
                "crowd_exposure": float(profile.crowd_exposure),
                "breach_effort_wan": float(profile.breach_effort_wan),
                "damage": loss,
            },
        },
    )
    event.causal_links.extend((
        CausalLink(
            event_id=event.id,
            cause_event_id=str(decision_event_id),
            relation=CausalRelation.TRIGGERED_BY,
        ),
        CausalLink(
            event_id=event.id,
            cause_event_id=str(condition.cause_event_id),
            relation=CausalRelation.ENABLED_BY,
        ),
    ))
    delta = StateDelta(
        event_id=event.id,
        owner_kind="region",
        owner_id=str(region.id),
        aspect="urban_asset_integrity",
        before=str(asset.integrity),
        after=str(replacement.integrity),
        magnitude=loss,
    )
    event.causal_payload["deltas"] = [delta.to_dict()]

    # 5. Only now is canonical state touched.
    region.city_state = replace(
        region.city_state,
        assets=tuple(
            replacement if current.id == asset.id else current
            for current in region.city_state.assets
        ),
    )
    if invalidations is not None:
        # The same mechanical layer and reason maintenance marks, so every
        # derived reading that multiplies by integrity is recomputed.
        invalidations.mark(DomainInvalidation(
            layer=DomainInvalidationLayer.MECHANICAL,
            domain="city",
            target_kind="region",
            target_id=str(region.id),
            reason=DomainInvalidationReason.INFRASTRUCTURE_CHANGED,
            source_event_ids=(event.id, str(context.trigger_event.id)),
            revision=event.id,
        ))
    # 6. The aftermath is part of the same operation, not a courtesy the
    #    caller may skip: knowledge of the public fact, and the spent receipt
    #    that makes this grievance unrepeatable. Leaving it to a wrapper would
    #    open a second door that writes damage without spending anything.
    from src.systems.civil_riot import record_riot_aftermath

    return record_riot_aftermath(
        world,
        region=region,
        condition=condition,
        event=event,
        decision_event_id=str(decision_event_id),
        affordance_id=str(option.id),
    )


def _recomputed_damage(
    world: Any, region: CityRegion, asset: Any, capability_id: str
) -> float:
    """The current law's own answer, never a caller-supplied amount."""
    from src.systems.civil_riot import riot_damage

    return float(riot_damage(region, asset, capability_id))


__all__ = ["execute_crowd_damage"]

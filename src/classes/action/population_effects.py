"""Causal population effects for legacy Avatar actions.

``CityRegion`` remains the sole owner of settlement population.  This module
only coordinates an action's already-decided amount with that owner and emits
the evidence consumed by the causal layer.
"""

from __future__ import annotations

from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta


def apply_avatar_population_effect(
    world: Any,
    avatar: Any,
    region: CityRegion,
    *,
    delta: float,
    affected_quantity: float,
    action_name: str,
    content: str,
) -> Event:
    """Apply one material action effect and return its causal result event."""
    before = float(region.population)
    region.change_population(float(delta))
    after = float(region.population)
    decision_event_id = str(getattr(avatar, "current_decision_event_id", "") or "")
    state_delta = StateDelta(
        event_id="",
        owner_kind="region",
        owner_id=str(region.id),
        aspect="population",
        before=str(before),
        after=str(after),
        magnitude=after - before,
    )
    event = Event(
        world.month_stamp,
        content,
        related_avatars=[str(avatar.id)],
        event_type="avatar_population_change",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "region_id": str(region.id),
            "action_name": action_name,
            "affected_quantity": affected_quantity,
            "decision_event_id": decision_event_id or None,
        },
        causal_payload={
            "deltas": [],
            "affected_quantity": affected_quantity,
            "decision_source": {
                "kind": "avatar_action",
                "action_name": action_name,
                "avatar_id": str(avatar.id),
                "decision_event_id": decision_event_id or None,
            },
        },
    )
    state_delta.event_id = event.id
    event.causal_payload["deltas"] = [state_delta.to_dict()]
    if decision_event_id:
        event.causal_links.append(
            CausalLink(
                event_id=event.id,
                cause_event_id=decision_event_id,
                relation=CausalRelation.MOTIVATED_BY,
            )
        )

    recorder = getattr(world, "step_causal_recorder", None)
    if recorder is not None:
        recorder.record_delta(event.id, state_delta)

    # The simulator context currently does not expose its invalidation queue
    # through World.  Honour either established bridge name when a caller
    # provides one; the phase/context integration is reported separately.
    invalidations = getattr(world, "step_invalidations", None)
    if invalidations is None:
        invalidations = getattr(world, "step_invalidation_queue", None)
    if invalidations is not None:
        from src.sim.simulator_engine.domain_invalidation import (
            DomainInvalidation,
            DomainInvalidationLayer,
            DomainInvalidationReason,
        )

        invalidations.mark(
            DomainInvalidation(
                layer=DomainInvalidationLayer.MECHANICAL,
                domain="population",
                target_kind="region",
                target_id=str(region.id),
                reason=DomainInvalidationReason.POPULATION_CHANGED,
                source_event_ids=(event.id,),
                revision=event.id,
            )
        )
    return event


__all__ = ["apply_avatar_population_effect"]

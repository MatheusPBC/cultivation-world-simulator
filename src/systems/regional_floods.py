"""Material regional flood lifecycle derived from grounded hydrology."""

from __future__ import annotations

import json
import uuid
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.environment.regional_flood import (
    DrainageObservation,
    FloodWindowEvidence,
    RegionalFloodOccurrence,
)
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import (
    MeasurementAvailability,
    MetricKey,
    MetricReading,
    PrimitiveDimension,
    ReadingKind,
)
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.systems.regional_hydrology import (
    DRAINAGE_CONCEPT,
    HYDROLOGY_QUALIFIERS,
    project_regional_hydrology,
)


FLOOD_ACTIVATION_RISK = 0.72
FLOOD_RESOLUTION_RISK = 0.45
FLOOD_ACTIVATION_MONTHS = 2
FLOOD_RESOLUTION_MONTHS = 2


def _event_id(world: Any, region_id: str, month: int, transition: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"cultivation-world:{world.playthrough_id}:regional-flood:{region_id}:{month}:{transition}",
        )
    )


def _observe_window(
    evidence_by_region: dict[str, FloodWindowEvidence],
    region_id: str,
    projection: Any,
) -> FloodWindowEvidence:
    """Record this month's evidence into the region's open transition window.

    Infrastructure history is kept for every month of the window because a
    site's last event changes while the window runs; keeping only the final
    month would silently drop the earlier evidence.
    """
    drainage = DrainageObservation(
        month=int(projection.month),
        drainage=projection.drainage,
        state_refs=projection.drainage_state_refs,
        source_event_ids=projection.flooding_context_event_ids,
    )
    observed = evidence_by_region.get(region_id)
    if observed is None:
        observed = FloodWindowEvidence(
            source_event_ids=projection.flooding_trigger_event_ids,
            drainage_observations=(drainage,),
        )
    else:
        observed = observed.extended(
            source_event_ids=projection.flooding_trigger_event_ids,
            drainage=drainage,
        )
    evidence_by_region[region_id] = observed
    return observed


def _clear_activation(state: Any, region_id: str) -> None:
    state.activation_streaks.pop(region_id, None)
    state.activation_evidence.pop(region_id, None)


def _clear_resolution(state: Any, region_id: str) -> None:
    state.resolution_streaks.pop(region_id, None)
    state.resolution_evidence.pop(region_id, None)


def _activation_event(
    world: Any,
    region: Any,
    *,
    risk: float,
    evidence: FloodWindowEvidence,
) -> tuple[Event, RegionalFloodOccurrence]:
    region_id = str(region.id)
    event_id = _event_id(world, region_id, int(world.month_stamp), "started")
    occurrence = RegionalFloodOccurrence(
        region_id=region_id,
        started_month=int(world.month_stamp),
        activation_risk=risk,
        source_event_ids=evidence.source_event_ids,
        last_event_id=event_id,
        drainage_observations=evidence.drainage_observations,
    )
    event = Event(
        month_stamp=world.month_stamp,
        content=t(
            "Persistent water pressure caused flooding in {region}.",
            region=region.name,
        ),
        event_type="regional_flood_started",
        render_key="regional_flood_started",
        render_params={
            "region_id": region_id,
            "region": region.name,
            "risk": risk,
            "hazard_kind": "regional_flood",
        },
        id=event_id,
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
        is_major=True,
    )
    delta = StateDelta(
        event_id=event.id,
        owner_kind="regional_flood",
        owner_id=region_id,
        aspect="active_occurrence",
        before=None,
        after=json.dumps(occurrence.to_dict(), ensure_ascii=False, sort_keys=True),
        magnitude=risk,
    )
    event.causal_payload = {
        "outcome": "started",
        "risk": risk,
        "deltas": [delta.to_dict()],
        "measurements": _drainage_measurements(region_id, evidence),
    }
    event.causal_links = [
        CausalLink(
            event_id=event.id,
            cause_event_id=source_id,
            relation=CausalRelation.TRIGGERED_BY,
        )
        for source_id in evidence.source_event_ids
    ]
    return event, occurrence


def _drainage_measurements(
    region_id: str,
    evidence: FloodWindowEvidence,
) -> list[dict[str, Any]]:
    """Publish the drainage read in each month of the window as measurements.

    Drainage works reach the reader through the reading that observed them,
    never through a causal link: maintenance does not cause a flood, and
    claiming it prevented a flood that did happen would be equally false.
    """
    key = MetricKey(
        PrimitiveDimension.CAPACITY,
        "region",
        region_id,
        DRAINAGE_CONCEPT,
        qualifiers=HYDROLOGY_QUALIFIERS,
    )
    return [
        MetricReading(
            key=key,
            value=observation.drainage,
            unit="ratio",
            availability=MeasurementAvailability.MEASURABLE,
            reading_kind=ReadingKind.DERIVED,
            calculated_month=observation.month,
            state_refs=list(observation.state_refs),
            source_event_ids=list(observation.source_event_ids),
        ).to_dict()
        for observation in evidence.drainage_observations
    ]


def _resolution_event(
    world: Any,
    region: Any,
    *,
    occurrence: RegionalFloodOccurrence,
    risk: float,
    evidence: FloodWindowEvidence,
) -> Event:
    region_id = str(region.id)
    event_id = _event_id(world, region_id, int(world.month_stamp), "resolved")
    event = Event(
        month_stamp=world.month_stamp,
        content=t(
            "Flood waters receded in {region}.",
            region=region.name,
        ),
        event_type="regional_flood_resolved",
        render_key="regional_flood_resolved",
        render_params={
            "region_id": region_id,
            "region": region.name,
            "risk": risk,
            "hazard_kind": "regional_flood",
        },
        id=event_id,
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
        is_major=True,
    )
    delta = StateDelta(
        event_id=event.id,
        owner_kind="regional_flood",
        owner_id=region_id,
        aspect="active_occurrence",
        before=json.dumps(occurrence.to_dict(), ensure_ascii=False, sort_keys=True),
        after=None,
        magnitude=-occurrence.activation_risk,
    )
    event.causal_payload = {
        "outcome": "resolved",
        "risk": risk,
        "deltas": [delta.to_dict()],
        "measurements": _drainage_measurements(region_id, evidence),
    }
    event.causal_links = [
        CausalLink(
            event_id=event.id,
            cause_event_id=occurrence.last_event_id,
            relation=CausalRelation.RESOLVES,
        ),
        *(
            CausalLink(
                event_id=event.id,
                cause_event_id=source_id,
                relation=CausalRelation.TRIGGERED_BY,
            )
            for source_id in evidence.source_event_ids
            if source_id != occurrence.last_event_id
        ),
    ]
    return event


def _mark_transition(
    invalidations: DomainInvalidationQueue,
    *,
    region_id: str,
    event: Event,
    transition: str,
    month: int,
) -> None:
    invalidations.mark(
        DomainInvalidation(
            layer=DomainInvalidationLayer.MECHANICAL,
            domain="region",
            target_kind="region",
            target_id=region_id,
            reason=DomainInvalidationReason.REGIONAL_HAZARD_CHANGED,
            source_event_ids=(event.id,),
            revision=f"regional-flood:{region_id}:{month}:{transition}",
        )
    )


def advance_regional_floods(
    world: Any,
    *,
    invalidations: DomainInvalidationQueue,
) -> list[Event]:
    """Advance physical flood occurrences once for the current month."""
    state = world.regional_flood_state
    month = int(world.month_stamp)
    if state.last_evaluated_month == month:
        return []
    if state.last_evaluated_month is not None and state.last_evaluated_month > month:
        raise ValueError("regional flood state cannot be evaluated backwards")
    if state.last_evaluated_month is not None and month != state.last_evaluated_month + 1:
        state.activation_streaks.clear()
        state.resolution_streaks.clear()
        state.activation_evidence.clear()
        state.resolution_evidence.clear()

    events: list[Event] = []
    for region_id, region in sorted(world.map.regions.items()):
        key = str(region_id)
        projection = project_regional_hydrology(world, region_id)
        if projection is None or not projection.flooding_trigger_event_ids:
            _clear_activation(state, key)
            _clear_resolution(state, key)
            continue

        active = state.active_by_region.get(key)
        if active is None:
            _clear_resolution(state, key)
            if projection.flooding < FLOOD_ACTIVATION_RISK:
                _clear_activation(state, key)
                continue
            state.activation_streaks[key] = state.activation_streaks.get(key, 0) + 1
            evidence = _observe_window(state.activation_evidence, key, projection)
            if state.activation_streaks[key] < FLOOD_ACTIVATION_MONTHS:
                continue
            event, occurrence = _activation_event(
                world,
                region,
                risk=projection.flooding,
                evidence=evidence,
            )
            state.active_by_region[key] = occurrence
            _clear_activation(state, key)
            events.append(event)
            _mark_transition(
                invalidations,
                region_id=key,
                event=event,
                transition="started",
                month=month,
            )
            continue

        _clear_activation(state, key)
        if projection.flooding >= FLOOD_RESOLUTION_RISK:
            _clear_resolution(state, key)
            continue
        state.resolution_streaks[key] = state.resolution_streaks.get(key, 0) + 1
        evidence = _observe_window(state.resolution_evidence, key, projection)
        if state.resolution_streaks[key] < FLOOD_RESOLUTION_MONTHS:
            continue
        event = _resolution_event(
            world,
            region,
            occurrence=active,
            risk=projection.flooding,
            evidence=evidence,
        )
        state.active_by_region.pop(key)
        _clear_resolution(state, key)
        events.append(event)
        _mark_transition(
            invalidations,
            region_id=key,
            event=event,
            transition="resolved",
            month=month,
        )

    state.last_evaluated_month = month
    return events


__all__ = [
    "FLOOD_ACTIVATION_MONTHS",
    "FLOOD_ACTIVATION_RISK",
    "FLOOD_RESOLUTION_MONTHS",
    "FLOOD_RESOLUTION_RISK",
    "advance_regional_floods",
]

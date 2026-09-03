"""Material regional flood lifecycle derived from grounded hydrology."""

from __future__ import annotations

import json
import uuid
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.environment.regional_flood import RegionalFloodOccurrence
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.systems.regional_hydrology import project_regional_hydrology


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


def _append_sources(
    sources: dict[str, tuple[str, ...]],
    region_id: str,
    new_sources: tuple[str, ...],
) -> tuple[str, ...]:
    combined = tuple(dict.fromkeys((*sources.get(region_id, ()), *new_sources)))
    sources[region_id] = combined
    return combined


def _clear_activation(state: Any, region_id: str) -> None:
    state.activation_streaks.pop(region_id, None)
    state.activation_sources.pop(region_id, None)


def _clear_resolution(state: Any, region_id: str) -> None:
    state.resolution_streaks.pop(region_id, None)
    state.resolution_sources.pop(region_id, None)


def _activation_event(
    world: Any,
    region: Any,
    *,
    risk: float,
    source_event_ids: tuple[str, ...],
) -> tuple[Event, RegionalFloodOccurrence]:
    region_id = str(region.id)
    event_id = _event_id(world, region_id, int(world.month_stamp), "started")
    occurrence = RegionalFloodOccurrence(
        region_id=region_id,
        started_month=int(world.month_stamp),
        activation_risk=risk,
        source_event_ids=source_event_ids,
        last_event_id=event_id,
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
    }
    event.causal_links = [
        CausalLink(
            event_id=event.id,
            cause_event_id=source_id,
            relation=CausalRelation.TRIGGERED_BY,
        )
        for source_id in source_event_ids
    ]
    return event, occurrence


def _resolution_event(
    world: Any,
    region: Any,
    *,
    occurrence: RegionalFloodOccurrence,
    risk: float,
    source_event_ids: tuple[str, ...],
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
            for source_id in source_event_ids
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
        state.activation_sources.clear()
        state.resolution_sources.clear()

    events: list[Event] = []
    for region_id, region in sorted(world.map.regions.items()):
        key = str(region_id)
        projection = project_regional_hydrology(world, region_id)
        if projection is None or not projection.source_event_ids:
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
            sources = _append_sources(
                state.activation_sources,
                key,
                projection.source_event_ids,
            )
            if state.activation_streaks[key] < FLOOD_ACTIVATION_MONTHS:
                continue
            event, occurrence = _activation_event(
                world,
                region,
                risk=projection.flooding,
                source_event_ids=sources,
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
        sources = _append_sources(
            state.resolution_sources,
            key,
            projection.source_event_ids,
        )
        if state.resolution_streaks[key] < FLOOD_RESOLUTION_MONTHS:
            continue
        event = _resolution_event(
            world,
            region,
            occurrence=active,
            risk=projection.flooding,
            source_event_ids=sources,
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

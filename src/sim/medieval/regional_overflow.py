"""A bounded natural overflow law for the medieval runtime.

This is deliberately a single vertical, not a generic hazard system.  The
engine derives a seasonal regional water load from the saved run seed, requires
two consecutive high readings, and may damage one already water-exposed,
explicitly maintained Map site.  It neither publishes climate knowledge to
actors nor repairs, enables, reroutes, or chooses maintenance work.
"""

from __future__ import annotations

import hashlib
from statistics import mean

from src.classes.environment.geography import WaterBodyKind
from src.classes.environment.regional_overflow import (
    RegionalOverflowAssessment,
    RegionalOverflowOccurrence,
)
from src.classes.event import FactKind

from .economy import _causes, _delta
from .events import record_event


MONTH_DAYS = 30
OVERFLOW_LOAD_THRESHOLD = 88
OVERFLOW_CONSECUTIVE_MONTHS = 2
MAX_OVERFLOW_INTEGRITY_LOSS = 0.15
MIN_SITE_VULNERABILITY = 55

# The high-water season is intentionally late enough that a new natural world
# cannot open with a scripted calamity.  A keyed monthly variation makes a
# high season a possibility, not a quota, and stays stable across save/load.
_SEASONAL_LOAD = (8, 10, 15, 23, 35, 51, 61, 57, 42, 28, 16, 10)
_WATER_EXPOSURE = {
    WaterBodyKind.RIVER: 42,
    WaterBodyKind.LAKE: 31,
    WaterBodyKind.SEA: 24,
}


def _stable_variation(seed: int, month: int, region_id: int) -> int:
    material = f"regional-overflow:v1:{seed}:{month}:{region_id}".encode("utf-8")
    return int.from_bytes(hashlib.blake2s(material, digest_size=2).digest(), "big") % 31


def regional_hydrologic_load(world, region_id: int) -> int:
    """Return the current region's engine-owned seasonal load on a 0..100 scale."""
    day = world.clock.absolute_day
    if day <= 0 or day % MONTH_DAYS:
        raise ValueError("regional hydrologic load is monthly only")
    month = day // MONTH_DAYS
    seasonal = _SEASONAL_LOAD[(month - 1) % len(_SEASONAL_LOAD)]
    return min(100, seasonal + _stable_variation(world.config.seed, month, region_id))


def site_overflow_vulnerability(world, site) -> int:
    """Derive immutable water exposure from declared geography, never runtime state.

    A site needs a declared water-body connection to be considered at all.  The
    score reads only those bodies, the site's geography cells and their
    elevation.  Integrity, routes, holdings, actor choices and previous damage
    intentionally cannot make a place newly vulnerable.
    """
    if not site.water_body_ids:
        return 0
    bodies = {body.id: body for body in world.map.geography.water_bodies}
    linked = [bodies[body_id] for body_id in site.water_body_ids if body_id in bodies]
    if not linked:
        return 0
    site_elevation = mean(world.map.get_elevation(*cell) for cell in site.cell_refs)
    water_elevations = [
        world.map.get_elevation(*cell)
        for body in linked
        for cell in body.cell_refs
    ]
    water_elevation = mean(water_elevations)
    # A site at or below its water body's mean is much more exposed.  The
    # bounded relief adjustment avoids inventing a hydrology solver here.
    relative_relief = max(0.0, site_elevation - water_elevation)
    lowland_exposure = max(0, min(30, round(30 - relative_relief / 4)))
    water_exposure = max(_WATER_EXPOSURE[body.kind] for body in linked)
    return min(100, water_exposure + lowland_exposure)


def _assessment(world, region_id: int, *, load: int, streak: int, prior, clears_occurrence):
    state = world.regional_overflow
    assessment_id = state.assessment_id(region_id)
    occurrence = state.occurrence(region_id)
    deltas = [
        _delta("regional_overflow", assessment_id, "load", prior.load if prior else None, load),
        _delta("regional_overflow", assessment_id, "streak", prior.streak if prior else None, streak),
    ]
    if clears_occurrence and occurrence is not None:
        deltas.append(_delta("regional_overflow", occurrence.id, "active", occurrence.id, None))
    event = record_event(
        world,
        "regional_hydrologic_load_assessed",
        f"Região {region_id}: carga hídrica sazonal avaliada em {load}/100.",
        # The reading is engine-derived, but this receipt changes the persisted
        # overflow owner's monthly assessment/streak, so it is a material state
        # transition rather than a prose-only derived condition.
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(deltas),
    )
    state.assessments[assessment_id] = RegionalOverflowAssessment(
        id=assessment_id,
        region_id=region_id,
        assessed_day=world.clock.absolute_day,
        load=load,
        streak=streak,
        evidence_event_id=event.id,
    )
    if clears_occurrence and occurrence is not None:
        del state.active_occurrences[occurrence.id]
    return state.assessments[assessment_id]


def _start_occurrence(world, assessment: RegionalOverflowAssessment):
    state = world.regional_overflow
    occurrence_id = state.occurrence_id(assessment.region_id)
    event = record_event(
        world,
        "regional_overflow_started",
        f"Região {assessment.region_id}: carga hídrica sustentada iniciou um transbordamento regional.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("regional_overflow", occurrence_id, "active", None, occurrence_id),),
        cause_ids=(assessment.evidence_event_id,),
    )
    occurrence = RegionalOverflowOccurrence(
        id=occurrence_id,
        region_id=assessment.region_id,
        started_day=world.clock.absolute_day,
        load=assessment.load,
        assessment_event_id=assessment.evidence_event_id,
        started_event_id=event.id,
    )
    state.active_occurrences[occurrence.id] = occurrence
    return occurrence


def _damage_one_exposed_site(world, occurrence: RegionalOverflowOccurrence):
    candidates = [
        (site_overflow_vulnerability(world, site), site)
        for site in world.map.infrastructure_sites.values()
        if occurrence.region_id in site.region_ids
        and site.water_body_ids
        and site.maintainer_ref is not None
        and site.integrity > 0.0
    ]
    candidates = [item for item in candidates if item[0] >= MIN_SITE_VULNERABILITY]
    if not candidates:
        return None
    _, site = min(candidates, key=lambda item: (-item[0], item[1].id))
    before = float(site.integrity)
    after = max(0.0, before - MAX_OVERFLOW_INTEGRITY_LOSS)
    if after >= before:
        return None
    event = record_event(
        world,
        "site_overflow_damaged",
        f"{site.name}: transbordamento regional reduziu a integridade para {round(after * 100)}%.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(
            _delta("site", site.id, "integrity", before, after),
            _delta("regional_overflow", occurrence.id, "damaged_site_id", None, site.id),
        ),
        cause_ids=_causes(occurrence.started_event_id, site.last_event_id),
    )
    # The Map is the sole owner of runtime integrity and queues the public map
    # projection itself.  This vertical never touches a route's nominal state.
    world.map.update_infrastructure_site_runtime(site.id, integrity=after, last_event_id=event.id)
    world.regional_overflow.active_occurrences[occurrence.id] = occurrence.model_copy(
        update={"damaged_site_id": site.id, "damage_event_id": event.id}
    )
    return site.id


def apply_monthly_regional_overflow(world) -> tuple[str, ...]:
    """Assess every map region and apply at most one physical hit per occurrence.

    The function is idempotent for a saved monthly boundary.  Natural worlds
    may never satisfy the two-month condition; no load value itself creates a
    story event, actor knowledge receipt, repair or maintenance decision.
    """
    day = world.clock.absolute_day
    if day <= 0 or day % MONTH_DAYS:
        return ()
    damaged_sites: list[str] = []
    state = world.regional_overflow
    for region_id in sorted(world.map.regions):
        prior = state.assessment(region_id)
        if prior is not None and prior.assessed_day == day:
            continue
        load = regional_hydrologic_load(world, region_id)
        consecutive_prior = prior is not None and prior.assessed_day == day - MONTH_DAYS
        streak = prior.streak + 1 if load >= OVERFLOW_LOAD_THRESHOLD and consecutive_prior else (
            1 if load >= OVERFLOW_LOAD_THRESHOLD else 0
        )
        clears_occurrence = load < OVERFLOW_LOAD_THRESHOLD
        assessment = _assessment(
            world,
            region_id,
            load=load,
            streak=streak,
            prior=prior,
            clears_occurrence=clears_occurrence,
        )
        occurrence = state.occurrence(region_id)
        if occurrence is None and streak >= OVERFLOW_CONSECUTIVE_MONTHS:
            occurrence = _start_occurrence(world, assessment)
            damaged = _damage_one_exposed_site(world, occurrence)
            if damaged is not None:
                damaged_sites.append(damaged)
    return tuple(damaged_sites)


__all__ = [
    "MAX_OVERFLOW_INTEGRITY_LOSS",
    "MIN_SITE_VULNERABILITY",
    "OVERFLOW_CONSECUTIVE_MONTHS",
    "OVERFLOW_LOAD_THRESHOLD",
    "apply_monthly_regional_overflow",
    "regional_hydrologic_load",
    "site_overflow_vulnerability",
]

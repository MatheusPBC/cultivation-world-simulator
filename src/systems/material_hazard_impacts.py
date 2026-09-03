"""Generic validation boundary from physical hazards to domain-owned impacts."""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable, Iterable
from typing import Any

from src.classes.environment.regional_flood import RegionalFloodOccurrence
from src.classes.event import Event
from src.classes.hazard_impact import (
    HazardExposure,
    HazardImpactEffect,
    HazardImpactProposal,
    HazardInteractionDefinition,
)
from src.classes.mechanical_language import EntityRef
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.infrastructure_site_condition import (
    change_infrastructure_site_condition,
)


FLOOD_SITE_IMPACT_EXPOSURE = 0.55

REGIONAL_FLOOD_SITE_INTERACTION = HazardInteractionDefinition(
    hazard_kind="regional_flood",
    target_kind="infrastructure_site",
    threshold=FLOOD_SITE_IMPACT_EXPOSURE,
    resistance_weights=(
        ("water_management", 0.20),
        ("drainage", 0.25),
        ("flood_control", 0.35),
    ),
    effect=HazardImpactEffect.REDUCE_INTEGRITY,
    minimum_magnitude=0.04,
    maximum_magnitude=0.25,
    curve_slope=0.50,
)

HAZARD_INTERACTIONS: dict[tuple[str, str], HazardInteractionDefinition] = {
    (
        REGIONAL_FLOOD_SITE_INTERACTION.hazard_kind,
        REGIONAL_FLOOD_SITE_INTERACTION.target_kind,
    ): REGIONAL_FLOOD_SITE_INTERACTION
}
HAZARD_EXPOSURE_PROJECTORS: dict[str, Callable[[Any, Any], list[HazardExposure]]] = {}
HAZARD_OCCURRENCE_RESOLVERS: dict[str, Callable[[Any, Event], Any | None]] = {}


def register_hazard_interaction(
    definition: HazardInteractionDefinition,
    *,
    occurrence_resolver: Callable[[Any, Event], Any | None],
    exposure_projector: Callable[[Any, Any], list[HazardExposure]],
) -> None:
    """Register one mechanical law and its canonical-state readers."""
    key = (definition.hazard_kind, definition.target_kind)
    existing = HAZARD_INTERACTIONS.get(key)
    if existing is not None and existing != definition:
        raise ValueError(f"hazard interaction already registered for {key}")
    existing_resolver = HAZARD_OCCURRENCE_RESOLVERS.get(definition.hazard_kind)
    existing_projector = HAZARD_EXPOSURE_PROJECTORS.get(definition.hazard_kind)
    if existing_resolver is not None and existing_resolver is not occurrence_resolver:
        raise ValueError(f"occurrence resolver already registered for {definition.hazard_kind}")
    if existing_projector is not None and existing_projector is not exposure_projector:
        raise ValueError(f"exposure projector already registered for {definition.hazard_kind}")
    HAZARD_INTERACTIONS[key] = definition
    HAZARD_OCCURRENCE_RESOLVERS[definition.hazard_kind] = occurrence_resolver
    HAZARD_EXPOSURE_PROJECTORS[definition.hazard_kind] = exposure_projector


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _water_cells(world: Any, region_id: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        dict.fromkeys(
            cell
            for body in world.map.get_water_bodies_touching_region(region_id)
            for cell in body.cell_refs
        )
    )


def _water_proximity(
    site_cells: tuple[tuple[int, int], ...],
    water_cells: tuple[tuple[int, int], ...],
) -> float:
    if not water_cells:
        return 0.0
    distance = min(
        abs(site_x - water_x) + abs(site_y - water_y)
        for site_x, site_y in site_cells
        for water_x, water_y in water_cells
    )
    return 1.0 / (1.0 + float(distance))


def _low_elevation(world: Any, cells: tuple[tuple[int, int], ...]) -> float:
    all_elevations = [
        float(value)
        for row in world.map.geography.elevation_rows
        for value in row
    ]
    site_elevations = [
        float(elevation)
        for x, y in cells
        if (elevation := world.map.get_elevation(x, y)) is not None
    ]
    if not all_elevations or not site_elevations:
        return 0.5
    elevation_range = max(all_elevations) - min(all_elevations)
    if elevation_range <= 0.0:
        return 0.5
    average = sum(site_elevations) / len(site_elevations)
    return _clamp(1.0 - (average - min(all_elevations)) / elevation_range)


def project_flood_site_exposures(
    world: Any,
    occurrence: RegionalFloodOccurrence,
) -> list[HazardExposure]:
    """Project spatial exposure without changing a site or inventing an impact."""
    try:
        region_id = int(occurrence.region_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("flood occurrence must target a numeric map region") from exc
    if world.map.regions.get(region_id) is None:
        raise ValueError("flood occurrence references an unknown region")

    water_cells = _water_cells(world, region_id)
    exposures: list[HazardExposure] = []
    for site in sorted(
        world.map.infrastructure_sites.values(),
        key=lambda item: item.id,
    ):
        if region_id not in site.region_ids or site.integrity <= 0.0:
            continue
        low_elevation = _low_elevation(world, site.cell_refs)
        water_proximity = _water_proximity(site.cell_refs, water_cells)
        spatial_exposure = 0.25 + low_elevation * 0.40 + water_proximity * 0.35
        exposure = _clamp(occurrence.activation_risk * spatial_exposure)
        state_refs = tuple(
            dict.fromkeys(
                (
                    f"regional_flood:region:{region_id}:active",
                    f"map:infrastructure_site:{site.id}:integrity",
                    *(f"map:geography:{x}:{y}:elevation" for x, y in site.cell_refs),
                    *(
                        f"map:water_body:{body.id}"
                        for body in world.map.get_water_bodies_touching_region(
                            region_id
                        )
                    ),
                    *(
                        f"map:infrastructure_site:{site.id}:capability:{item}"
                        for item in site.capability_ids
                    ),
                )
            )
        )
        exposures.append(
            HazardExposure(
                hazard_kind="regional_flood",
                occurrence_event_id=occurrence.last_event_id,
                target_ref=EntityRef("infrastructure_site", site.id),
                exposure=exposure,
                state_refs=state_refs,
                source_event_ids=tuple(
                    dict.fromkeys((occurrence.last_event_id, *occurrence.source_event_ids))
                ),
            )
        )
    return exposures


def propose_hazard_impacts(
    world: Any,
    exposures: Iterable[HazardExposure],
) -> list[HazardImpactProposal]:
    """Apply only registered engine laws to measurable target exposure."""
    proposals: list[HazardImpactProposal] = []
    for exposure in exposures:
        definition = HAZARD_INTERACTIONS.get(
            (exposure.hazard_kind, exposure.target_ref.kind)
        )
        if definition is None:
            continue
        capabilities: tuple[str, ...] = ()
        if exposure.target_ref.kind == "infrastructure_site":
            target = world.map.infrastructure_sites.get(exposure.target_ref.id)
            if target is None:
                continue
            capabilities = tuple(target.capability_ids)
        magnitude = definition.magnitude(exposure.exposure, capabilities)
        if magnitude is None:
            continue
        proposals.append(
            HazardImpactProposal(
                hazard_kind=exposure.hazard_kind,
                source_event_id=exposure.occurrence_event_id,
                target_ref=exposure.target_ref,
                effect=definition.effect,
                magnitude=magnitude,
                exposure=exposure.exposure,
            )
        )
    return proposals


def _regional_flood_occurrence(world: Any, source_event: Event):
    params = (
        source_event.render_params
        if isinstance(source_event.render_params, dict)
        else {}
    )
    if (
        source_event.event_type != "regional_flood_started"
        or params.get("hazard_kind") != "regional_flood"
    ):
        return None
    region_id = str(params.get("region_id", ""))
    occurrence = world.regional_flood_state.active_by_region.get(region_id)
    if occurrence is None or occurrence.last_event_id != source_event.id:
        return None
    return occurrence


register_hazard_interaction(
    REGIONAL_FLOOD_SITE_INTERACTION,
    occurrence_resolver=_regional_flood_occurrence,
    exposure_projector=project_flood_site_exposures,
)


def _validated_proposal(
    world: Any,
    proposal: HazardImpactProposal,
    source_event: Event,
) -> tuple[HazardImpactProposal, HazardExposure]:
    if proposal.source_event_id != source_event.id:
        raise ValueError("hazard impact source event does not match the proposal")
    resolver = HAZARD_OCCURRENCE_RESOLVERS.get(proposal.hazard_kind)
    projector = HAZARD_EXPOSURE_PROJECTORS.get(proposal.hazard_kind)
    if resolver is None or projector is None:
        raise ValueError("hazard interaction is not registered by the engine")
    occurrence = resolver(world, source_event)
    if occurrence is None:
        raise ValueError("hazard impact requires an active canonical occurrence")
    exposures = projector(world, occurrence)
    mechanically_afforded = propose_hazard_impacts(world, exposures)
    expected = next(
        (
            item
            for item in mechanically_afforded
            if item.target_ref == proposal.target_ref and item.effect is proposal.effect
        ),
        None,
    )
    if expected is None:
        raise ValueError("hazard impact target is not mechanically afforded")
    if not math.isclose(expected.exposure, proposal.exposure, abs_tol=1e-9):
        raise ValueError("hazard impact exposure does not match canonical geography")
    if not math.isclose(expected.magnitude, proposal.magnitude, abs_tol=1e-9):
        raise ValueError("hazard impact magnitude exceeds its mechanical affordance")
    exposure = next(
        item for item in exposures if item.target_ref == expected.target_ref
    )
    return expected, exposure


def _impact_event_id(proposal: HazardImpactProposal) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            ":".join(
                (
                    "cultivation-world",
                    "hazard-impact",
                    proposal.source_event_id,
                    proposal.target_ref.kind,
                    proposal.target_ref.id,
                    proposal.effect.value,
                )
            ),
        )
    )


def apply_hazard_impact_proposal(
    world: Any,
    proposal: HazardImpactProposal,
    *,
    source_event: Event,
    invalidations: DomainInvalidationQueue,
) -> Event | None:
    """Recompute the affordance, then ask the canonical target owner to mutate."""
    accepted, exposure = _validated_proposal(world, proposal, source_event)
    if accepted.target_ref.kind != "infrastructure_site":
        raise ValueError("unsupported hazard impact target owner")
    site = world.map.infrastructure_sites.get(accepted.target_ref.id)
    if site is None:
        raise ValueError("hazard impact target no longer exists")
    event_id = _impact_event_id(accepted)
    if site.last_event_id == event_id:
        return None
    integrity = max(0.0, float(site.integrity) - accepted.magnitude)
    event = change_infrastructure_site_condition(
        world,
        site_id=site.id,
        source_event_id=source_event.id,
        invalidations=invalidations,
        integrity=integrity,
        enabled=False if integrity <= 0.0 else None,
        event_id=event_id,
    )
    event.causal_payload["hazard_impact"] = accepted.to_dict()
    event.causal_payload["hazard_exposure"] = exposure.to_dict()
    event.render_params["hazard_kind"] = accepted.hazard_kind
    event.render_params["hazard_exposure"] = accepted.exposure
    return event


def process_material_hazard_impacts(
    world: Any,
    *,
    current_events: list[Event],
    invalidations: DomainInvalidationQueue,
) -> list[Event]:
    """Resolve every registered hazard without event-name dispatch."""
    effects: list[Event] = []
    for source_event in sorted(current_events, key=lambda item: item.id):
        params = (
            source_event.render_params
            if isinstance(source_event.render_params, dict)
            else {}
        )
        hazard_kind = str(params.get("hazard_kind", ""))
        resolver = HAZARD_OCCURRENCE_RESOLVERS.get(hazard_kind)
        projector = HAZARD_EXPOSURE_PROJECTORS.get(hazard_kind)
        if resolver is None or projector is None:
            continue
        occurrence = resolver(world, source_event)
        if occurrence is None:
            continue
        proposals = propose_hazard_impacts(world, projector(world, occurrence))
        for proposal in proposals:
            event = apply_hazard_impact_proposal(
                world,
                proposal,
                source_event=source_event,
                invalidations=invalidations,
            )
            if event is not None:
                effects.append(event)
    return effects


__all__ = [
    "FLOOD_SITE_IMPACT_EXPOSURE",
    "HAZARD_EXPOSURE_PROJECTORS",
    "HAZARD_INTERACTIONS",
    "HAZARD_OCCURRENCE_RESOLVERS",
    "REGIONAL_FLOOD_SITE_INTERACTION",
    "register_hazard_interaction",
    "apply_hazard_impact_proposal",
    "process_material_hazard_impacts",
    "project_flood_site_exposures",
    "propose_hazard_impacts",
]

"""Deterministic, grounded spiritual ecology projections.

This module is deliberately a read model.  It observes canonical facts that
already belong to regions, formations, points of interest, and the world.  It
does not create a spiritual reservoir, infer a danger from prose, or mutate
the world while building the view.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.classes.essence import EssenceType
from src.classes.mechanical_language import EntityRef


def _sorted_unique(values: list[str] | tuple[str, ...] | set[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _explicit_event_ids(value: Any) -> tuple[str, ...]:
    """Read only explicit provenance fields from an existing canonical fact."""
    if isinstance(value, dict):
        candidates = [
            value.get(key)
            for key in (
                "source_event_id",
                "source_event_ids",
                "event_id",
                "cause_event_id",
                "created_from_event_id",
            )
        ]
    else:
        candidates = [
            getattr(value, key, None)
            for key in (
                "source_event_id",
                "source_event_ids",
                "event_id",
                "cause_event_id",
                "created_from_event_id",
            )
        ]

    result: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, (list, tuple, set)):
            result.extend(str(item) for item in candidate if item is not None)
        elif candidate is not None:
            result.append(str(candidate))
    return _sorted_unique(result)


def _scalar_effects(value: Any) -> tuple[tuple[str, int | float | str | bool | None], ...]:
    """Expose formation effects without retaining a mutable mapping."""
    if not isinstance(value, dict):
        return ()
    effects: list[tuple[str, int | float | str | bool | None]] = []
    for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
        if item is None or isinstance(item, (bool, int, float, str)):
            effects.append((str(key), item))
    return tuple(effects)


@dataclass(frozen=True)
class EssenceObservation:
    """The canonical five-element essence profile of a CultivateRegion."""

    essence_type: str
    density: int
    densities: tuple[tuple[str, int], ...]
    state_refs: tuple[str, ...]
    source_event_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.essence_type,
            "density": self.density,
            "densities": {key: value for key, value in self.densities},
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }


@dataclass(frozen=True)
class FormationObservation:
    """An active formation already recorded for the target region."""

    formation_id: str
    formation_type: str
    started_month: int
    expires_month: int | None
    effects: tuple[tuple[str, int | float | str | bool | None], ...]
    state_refs: tuple[str, ...]
    source_event_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.formation_id,
            "type": self.formation_type,
            "started_month": self.started_month,
            "expires_month": self.expires_month,
            "effects": {key: value for key, value in self.effects},
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }


@dataclass(frozen=True)
class POIObservation:
    """A grave or treasure whose coordinates belong to the region footprint."""

    poi_id: str
    kind: str
    name: str
    location: tuple[int, int]
    created_month: int
    expires_month: int | None
    state_refs: tuple[str, ...]
    source_event_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.poi_id,
            "kind": self.kind,
            "name": self.name,
            "location": list(self.location),
            "created_month": self.created_month,
            "expires_month": self.expires_month,
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }


@dataclass(frozen=True)
class CelestialContext:
    """World-wide phenomenon context; it is never regional grounding."""

    phenomenon_id: str
    name: str
    description: str
    state_refs: tuple[str, ...] = ("world:current_celestial_phenomenon",)
    source_event_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.phenomenon_id,
            "name": self.name,
            "description": self.description,
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }


@dataclass(frozen=True)
class SpiritualEcologyView:
    """Immutable projection of grounded spiritual facts for one region.

    ``risk_level`` is intentionally ``None`` in this first vertical.  There
    is no canonical regional hazard field in the current world, so the view
    reports absence instead of turning essence, graves, or a formation into a
    made-up risk.
    """

    region_id: int
    grounding_status: str
    essence: EssenceObservation | None
    formations: tuple[FormationObservation, ...]
    graves: tuple[POIObservation, ...]
    treasures: tuple[POIObservation, ...]
    celestial_context: CelestialContext | None
    state_refs: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    risk_level: str | None = None

    @property
    def grounded(self) -> bool:
        return self.grounding_status == "grounded"

    @property
    def is_unknown(self) -> bool:
        return not self.grounded

    @property
    def status(self) -> str:
        """Short alias for consumers that use availability terminology."""
        return self.grounding_status

    @property
    def risk(self) -> str | None:
        return self.risk_level

    @property
    def facts(self) -> tuple[EssenceObservation | FormationObservation | POIObservation, ...]:
        return (
            (() if self.essence is None else (self.essence,))
            + self.formations
            + self.graves
            + self.treasures
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible data with deterministic collection order."""
        return {
            "schema_version": 1,
            "region_id": self.region_id,
            "grounding_status": self.grounding_status,
            "grounded": self.grounded,
            "risk_level": self.risk_level,
            "essence": self.essence.to_dict() if self.essence is not None else None,
            "formations": [formation.to_dict() for formation in self.formations],
            "graves": [grave.to_dict() for grave in self.graves],
            "treasures": [treasure.to_dict() for treasure in self.treasures],
            "celestial_context": (
                self.celestial_context.to_dict()
                if self.celestial_context is not None
                else None
            ),
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _region_for_id(world: Any, region_id: int | str) -> Any | None:
    game_map = getattr(world, "map", None)
    regions = getattr(game_map, "regions", {}) if game_map is not None else {}
    try:
        normalized_id = int(region_id)
    except (TypeError, ValueError):
        return None
    return regions.get(normalized_id)


def _region_contains_coordinate(world: Any, region: Any, coordinate: tuple[int, int]) -> bool:
    footprint = getattr(region, "cors", ()) or ()
    if coordinate in footprint:
        return True
    # A map tile is also a canonical relation when a caller has not copied the
    # footprint onto the region object.  Both paths are read-only.
    game_map = getattr(world, "map", None)
    tiles = getattr(game_map, "tiles", {}) if game_map is not None else {}
    tile = tiles.get(coordinate)
    return tile is not None and getattr(tile, "region", None) == region


def _active_formation(world: Any, region_id: int) -> tuple[str, dict[str, Any]] | None:
    game_map = getattr(world, "map", None)
    formations = getattr(game_map, "region_formations", {}) if game_map is not None else {}
    if not isinstance(formations, dict):
        return None
    formation = formations.get(region_id, formations.get(str(region_id)))
    if not isinstance(formation, dict):
        return None
    try:
        current_month = int(getattr(world, "month_stamp", 0))
        start_month = int(formation.get("start_month"))
        duration = int(formation.get("duration"))
    except (TypeError, ValueError):
        return None
    if duration <= 0 or current_month < start_month or current_month >= start_month + duration:
        return None
    formation_id = str(formation.get("id") or f"formation:{region_id}:{start_month}")
    return formation_id, formation


def _formation_observation(world: Any, region: Any, region_id: int) -> FormationObservation | None:
    active = _active_formation(world, region_id)
    if active is None:
        return None
    formation_id, formation = active
    formation_type = str(formation.get("formation_type") or formation.get("type") or "")
    start_month = int(formation["start_month"])
    duration = int(formation["duration"])
    source_ids = list(_explicit_event_ids(formation))
    semantic_state = getattr(world, "mechanical_language", None)
    conditions = (
        semantic_state.get_conditions_for_target(EntityRef("region", str(region_id)))
        if semantic_state is not None
        else ()
    )
    for condition in conditions:
        definition_id = str(getattr(condition, "definition_id", ""))
        target_id = str(getattr(condition, "target_id", ""))
        if (
            definition_id == f"formation:{formation_type}_formation"
            and target_id == str(region_id)
            and getattr(condition, "is_active", lambda _month: True)(int(getattr(world, "month_stamp", 0)))
        ):
            cause_event_id = getattr(condition, "cause_event_id", None)
            if cause_event_id:
                source_ids.append(str(cause_event_id))
    return FormationObservation(
        formation_id=formation_id,
        formation_type=formation_type,
        started_month=start_month,
        expires_month=start_month + duration,
        effects=_scalar_effects(formation.get("effects")),
        state_refs=(f"region:{region_id}", f"region:{region_id}:formation:{formation_id}"),
        source_event_ids=_sorted_unique(source_ids),
    )


def _essence_observation(region: Any, region_id: int) -> EssenceObservation | None:
    from src.classes.environment.region import CultivateRegion

    if not isinstance(region, CultivateRegion):
        return None
    essence = getattr(region, "essence", None)
    if essence is None:
        return None
    densities: list[tuple[str, int]] = []
    for essence_type in EssenceType:
        try:
            density = int(essence.get_density(essence_type))
        except (AttributeError, TypeError, ValueError):
            return None
        densities.append((essence_type.value, density))
    return EssenceObservation(
        essence_type=getattr(getattr(region, "essence_type", None), "value", str(getattr(region, "essence_type", ""))),
        density=int(getattr(region, "essence_density", 0)),
        densities=tuple(densities),
        state_refs=(f"region:{region_id}", f"region:{region_id}:essence"),
    )


def _poi_observations(world: Any, region: Any, region_id: int) -> tuple[tuple[POIObservation, ...], tuple[POIObservation, ...]]:
    manager = getattr(world, "poi_manager", None)
    pois = getattr(manager, "pois", {}) if manager is not None else {}
    if not isinstance(pois, dict):
        return (), ()
    current_month = int(getattr(world, "month_stamp", 0))
    observations: list[POIObservation] = []
    for poi_id, poi in pois.items():
        kind = str(getattr(poi, "kind", ""))
        if kind not in {"grave", "treasure"}:
            continue
        location = (_int_or_none(getattr(poi, "x", None)), _int_or_none(getattr(poi, "y", None)))
        if location[0] is None or location[1] is None:
            continue
        coordinate = (location[0], location[1])
        if not _region_contains_coordinate(world, region, coordinate):
            continue
        expires_month = _int_or_none(getattr(poi, "expires_month", None))
        if expires_month is not None and current_month >= expires_month:
            continue
        observations.append(
            POIObservation(
                poi_id=str(getattr(poi, "id", poi_id)),
                kind=kind,
                name=str(getattr(poi, "name", "")),
                location=coordinate,
                created_month=_int_or_none(getattr(poi, "created_month", 0)) or 0,
                expires_month=expires_month,
                state_refs=(f"region:{region_id}", f"poi:{getattr(poi, 'id', poi_id)}"),
                source_event_ids=_explicit_event_ids(poi),
            )
        )
    observations.sort(key=lambda item: (item.kind, item.poi_id))
    return (
        tuple(item for item in observations if item.kind == "grave"),
        tuple(item for item in observations if item.kind == "treasure"),
    )


def _celestial_context(world: Any) -> CelestialContext | None:
    phenomenon = getattr(world, "current_phenomenon", None)
    if phenomenon is None:
        return None
    return CelestialContext(
        phenomenon_id=str(getattr(phenomenon, "id", "")),
        name=str(getattr(phenomenon, "name", "")),
        description=str(getattr(phenomenon, "desc", "")),
        source_event_ids=_explicit_event_ids(phenomenon),
    )


def project_spiritual_ecology(world: Any, region_id: int | str) -> SpiritualEcologyView:
    """Build a stable, read-only spiritual ecology projection for a region."""
    region = _region_for_id(world, region_id)
    normalized_id = int(region_id) if str(region_id).lstrip("-").isdigit() else -1
    if region is None:
        return SpiritualEcologyView(
            region_id=normalized_id,
            grounding_status="unknown",
            essence=None,
            formations=(),
            graves=(),
            treasures=(),
            celestial_context=_celestial_context(world),
            state_refs=(),
            source_event_ids=(),
        )

    essence = _essence_observation(region, normalized_id)
    formation = _formation_observation(world, region, normalized_id)
    graves, treasures = _poi_observations(world, region, normalized_id)
    formations = (formation,) if formation is not None else ()
    celestial = _celestial_context(world)

    facts = (() if essence is None else (essence,)) + formations + graves + treasures
    context_refs = celestial.state_refs if celestial is not None else ()
    context_event_ids = celestial.source_event_ids if celestial is not None else ()
    state_refs = _sorted_unique(
        [f"region:{normalized_id}", *context_refs, *(ref for fact in facts for ref in fact.state_refs)]
    )
    source_event_ids = _sorted_unique(
        [*context_event_ids, *(event_id for fact in facts for event_id in fact.source_event_ids)]
    )
    return SpiritualEcologyView(
        region_id=normalized_id,
        grounding_status="grounded" if facts else "unknown",
        essence=essence,
        formations=formations,
        graves=graves,
        treasures=treasures,
        celestial_context=celestial,
        state_refs=state_refs,
        source_event_ids=source_event_ids,
    )


# Public aliases keep the projection discoverable without introducing a
# second implementation or another state owner.
build_spiritual_ecology_view = project_spiritual_ecology
get_spiritual_ecology_view = project_spiritual_ecology


__all__ = [
    "CelestialContext",
    "EssenceObservation",
    "FormationObservation",
    "POIObservation",
    "SpiritualEcologyView",
    "build_spiritual_ecology_view",
    "get_spiritual_ecology_view",
    "project_spiritual_ecology",
]

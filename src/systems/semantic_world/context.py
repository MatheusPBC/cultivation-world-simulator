from __future__ import annotations

from typing import Any

from src.classes.environment.sect_region import SectRegion
from src.i18n import t
from src.classes.mechanical_language import EntityRef
from src.systems.collective_health import project_collective_health
from src.systems.semantic_world.resolvers import (
    available_metric_keys,
    resolve_derived_metric,
    resolve_metric,
)
from src.systems.spiritual_ecology import project_spiritual_ecology


def build_region_semantic_context(world: Any, region: Any) -> dict[str, Any]:
    month = int(world.month_stamp)
    state = world.mechanical_language
    readings = [
        resolve_metric(
            world,
            key,
            target=region,
            calculated_month=month,
        ).to_dict()
        for key in available_metric_keys(world, region)
    ]

    definitions = []
    for definition in state.derived_definitions.values():
        if definition.target_kind != "region" or definition.lifecycle.value in {"deprecated", "merged", "dormant"}:
            continue
        reading = resolve_derived_metric(
            world,
            definition,
            target=region,
            calculated_month=month,
            definitions=state.derived_definitions,
        )
        readings.append(reading.to_dict())
        definitions.append({
            "id": definition.id,
            "concept_id": definition.concept_id,
            "dimension": definition.dimension.value,
            "unit": definition.unit,
            "lifecycle": definition.lifecycle.value,
        })

    flood = world.regional_flood_state.active_by_region.get(str(region.id))
    active_hazards = (
        [
            {
                "kind": "regional_flood",
                **flood.to_dict(),
            }
        ]
        if flood is not None
        else []
    )

    return {
        "readings": readings,
        "conditions": [
            item.to_dict()
            for item in state.get_active_conditions(
                EntityRef("region", str(region.id)),
                month,
            )
        ],
        "definitions": definitions,
        "active_hazards": active_hazards,
        "spiritual_ecology": project_spiritual_ecology(
            world,
            getattr(region, "id", -1),
        ).to_dict(),
        "collective_health": project_collective_health(
            world,
            getattr(region, "id", -1),
        ).to_dict(),
    }


def build_sect_semantic_context(world: Any, sect: Any) -> list[dict[str, Any]]:
    """Build the read-only semantic view for a sect's canonical regions.

    ``Map.regions`` is the map's semantic source of truth.  The canonical
    sect binding is ``SectRegion.sect_id``; using that field also supports
    multiple headquarters regions without adding another ownership registry.
    """
    game_map = getattr(world, "map", None)
    regions = getattr(game_map, "regions", {}) or {}
    sect_id = int(getattr(sect, "id", -1))
    canonical_regions = sorted(
        (
            region
            for region in regions.values()
            if isinstance(region, SectRegion)
            and int(getattr(region, "sect_id", -1)) == sect_id
        ),
        key=lambda region: int(getattr(region, "id", 0)),
    )

    return [
        {
            "region_id": int(region.id),
            "region_name": str(getattr(region, "name", "") or ""),
            **build_region_semantic_context(world, region),
        }
        for region in canonical_regions
    ]


def region_semantic_relevance(world: Any, region: Any) -> float:
    context = build_region_semantic_context(world, region)
    values = [
        float(item["value"])
        for item in context["readings"]
        if item.get("value") is not None
        and item["key"]["dimension"] in {"risk", "load", "quality"}
        and item.get("unit") == "ratio"
    ]
    values.extend(float(item.get("intensity", 0.0)) for item in context["conditions"])
    values.extend(
        float(item.get("activation_risk", 0.0))
        for item in context["active_hazards"]
    )
    return max(values, default=0.0)


def build_avatar_semantic_context(avatar: Any) -> str:
    region = getattr(getattr(avatar, "tile", None), "region", None)
    world = getattr(avatar, "world", None)
    if region is None or world is None:
        return t("No current region is available.")
    context = build_region_semantic_context(world, region)
    lines = [t("Region: {region}", region=region.name)]
    for reading in context["readings"]:
        key = reading["key"]
        group_suffix = (
            f"[{key['group_id']}]"
            if key.get("group_id")
            else ""
        )
        value = (
            t("Unknown measurement")
            if reading["value"] is None
            else f"{float(reading['value']):.3f} {reading['unit']}"
        )
        lines.append(
            f"{key['dimension']}({key['concept_id']}){group_suffix}: {value}"
        )
        if reading.get("source_event_ids"):
            lines.append(t("Causal evidence: {sources}", sources=", ".join(reading["source_event_ids"])))
    if context["conditions"]:
        lines.append(t("Active conditions: {conditions}", conditions=", ".join(item["label"] for item in context["conditions"])))
        causes = [item["cause_event_id"] for item in context["conditions"] if item.get("cause_event_id")]
        if causes:
            lines.append(t("Condition evidence: {sources}", sources=", ".join(causes)))
    for hazard in context["active_hazards"]:
        lines.append(
            t(
                "Active regional hazard: {hazard} (since month {month}).",
                hazard=hazard["kind"],
                month=hazard["started_month"],
            )
        )
        if hazard.get("source_event_ids"):
            lines.append(
                t(
                    "Causal evidence: {sources}",
                    sources=", ".join(hazard["source_event_ids"]),
                )
            )
    return "\n".join(lines)

"""Derived regional pressure and capability context.

This module only reads domain state.  It does not register capabilities or
mutate regions, which keeps the causal kernel observational.
"""

from __future__ import annotations

from typing import Any

from src.classes.environment.region import CityRegion, CultivateRegion, NormalRegion, Region
from src.classes.environment.sect_region import SectRegion


def _capability(kind: str, *, value: Any = True, reason: str = "") -> dict[str, Any]:
    item = {"kind": kind, "value": value}
    if reason:
        item["reason"] = reason
    return item


def resolve_region_capabilities(region: Region, world: Any | None = None) -> list[dict[str, Any]]:
    """Derive capabilities currently evidenced by ``region``.

    The optional world is used only to inspect already-existing formation
    state and living members; no capability registry is created.
    """
    capabilities: list[dict[str, Any]] = []
    if isinstance(region, CityRegion):
        capabilities.extend([
            _capability("population", value=region.population, reason="city population"),
            _capability("settlement", value=region.population_capacity, reason="city capacity"),
        ])
        store_items = getattr(region, "store_items", None) or []
        if store_items:
            capabilities.append(
                _capability("market", value=len(store_items), reason="items currently sold by settlement")
            )
    if isinstance(region, SectRegion):
        capabilities.append(_capability("sect_headquarters", reason="sect headquarters region"))
    if isinstance(region, NormalRegion):
        if getattr(region, "animals", None):
            capabilities.append(_capability("hunting", reason="animals in region"))
        if getattr(region, "plants", None):
            capabilities.append(_capability("harvesting", reason="plants in region"))
        if getattr(region, "lodes", None):
            capabilities.append(_capability("mining", reason="lodes in region"))
    if isinstance(region, (CultivateRegion, SectRegion)):
        capabilities.append(_capability("cultivation", reason="cultivation site"))

    # Formation state is already owned by Map and is read as-is.
    if world is not None:
        formations = getattr(getattr(world, "map", None), "region_formations", {}) or {}
        formation = formations.get(getattr(region, "id", None))
        if isinstance(formation, dict):
            kind = formation.get("formation_type") or formation.get("type") or formation.get("kind")
            if kind:
                capabilities.append(_capability(str(kind), reason="active regional formation"))
        avatar_manager = getattr(world, "avatar_manager", None)
        living = []
        if avatar_manager is not None and hasattr(avatar_manager, "get_living_avatars"):
            living = avatar_manager.get_living_avatars()
        elif hasattr(world, "avatars"):
            living = list(getattr(world, "avatars", {}).values())
        member_count = sum(
            1
            for avatar in living
            if getattr(getattr(avatar, "tile", None), "region", None) == region
            and not getattr(avatar, "is_dead", False)
        )
        if member_count:
            capabilities.append(_capability("members", value=member_count, reason="living avatars in region"))
    return capabilities


def summarize_regional_pressure(
    region: Region,
    current_month: int,
    phenomenon: Any | None = None,
    capabilities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a serializable pressure snapshot from current domain state."""
    occupancy_ratio = float(getattr(region, "population_ratio", 0.0)) if isinstance(region, CityRegion) else 0.0
    conditions = [c.to_dict() for c in region.get_active_conditions(current_month)]
    condition_pressure = min(1.0, sum(float(c["intensity"]) for c in conditions) * 0.25)
    pressure_value = max(occupancy_ratio, condition_pressure)
    level = "high" if pressure_value >= 0.85 else "medium" if pressure_value >= 0.60 else "low"
    phenomenon_data = None
    if phenomenon is not None:
        phenomenon_data = {"name": getattr(phenomenon, "name", ""), "desc": getattr(phenomenon, "desc", "")}
    return {
        "region_id": region.id,
        "region_name": region.name,
        "occupancy_ratio": occupancy_ratio,
        "condition_pressure": condition_pressure,
        "level": level,
        "conditions": conditions,
        "phenomenon": phenomenon_data,
        "capabilities": list(capabilities if capabilities is not None else resolve_region_capabilities(region)),
        "why": [
            {"kind": "occupancy", "value": occupancy_ratio, "source": "population/capacity"},
            *[{"kind": c["kind"], "cause_event_id": c["cause_event_id"]} for c in conditions],
        ],
    }


def build_avatar_regional_context(avatar: Any) -> str:
    """Render a compact, evidence-backed regional context for an avatar LLM."""
    region = getattr(getattr(avatar, "tile", None), "region", None)
    if region is None:
        return "No current region is available."
    world = getattr(avatar, "world", None)
    month = int(getattr(world, "month_stamp", 0) or 0)
    pressure = summarize_regional_pressure(
        region,
        month,
        phenomenon=getattr(world, "current_phenomenon", None),
        capabilities=resolve_region_capabilities(region, world),
    )
    lines = [f"Region: {region.name}", f"Regional pressure: {pressure['level']} ({pressure['occupancy_ratio']:.2f} occupancy)"]
    if pressure["phenomenon"]:
        lines.append(f"World phenomenon: {pressure['phenomenon']['name']} — {pressure['phenomenon']['desc']}")
    if pressure["conditions"]:
        lines.append("Active conditions: " + ", ".join(c["kind"] for c in pressure["conditions"]))
        causes = [c["cause_event_id"] for c in pressure["conditions"] if c.get("cause_event_id")]
        if causes:
            lines.append("Causal evidence: " + ", ".join(causes))
    capability_text = ", ".join(c["kind"] for c in pressure["capabilities"])
    lines.append("Available capabilities: " + (capability_text or "none"))
    return "\n".join(lines)

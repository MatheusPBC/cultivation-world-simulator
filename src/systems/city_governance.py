"""Initialization grounding for city governance."""

from typing import Any

from src.classes.environment.city_state import CityGovernance
from src.classes.environment.region import CityRegion


def ground_unclaimed_city_governance(world: Any) -> int:
    """Assign the current dynasty to cities that have no controller yet.

    This is an initialization premise for newly created worlds.  It does not
    represent a historical action and therefore must not emit an event.  An
    explicit controller, including a sect controller, is always preserved.

    Returns the number of cities grounded so callers and tests can observe the
    deterministic initialization result.
    """
    dynasty = getattr(world, "dynasty", None)
    if dynasty is None:
        raise ValueError("world dynasty is required to ground city governance")

    dynasty_id = str(dynasty.id)
    grounded_count = 0
    for region in getattr(getattr(world, "map", None), "regions", {}).values():
        if not isinstance(region, CityRegion):
            continue

        governance = region.city_state.governance
        if governance.controller_kind or governance.controller_id:
            continue

        region.city_state.governance = CityGovernance(
            controller_kind="dynasty",
            controller_id=dynasty_id,
            administrative_capacity=governance.administrative_capacity,
        )
        grounded_count += 1

    return grounded_count

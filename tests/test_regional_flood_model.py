from __future__ import annotations

import pytest

from src.classes.environment.regional_flood import (
    RegionalFloodOccurrence,
    RegionalFloodState,
)


def _occurrence() -> RegionalFloodOccurrence:
    return RegionalFloodOccurrence(
        region_id="101",
        started_month=14,
        activation_risk=0.82,
        source_event_ids=("rain-13", "rain-14", "rain-14"),
        last_event_id="flood-started",
    )


def test_regional_flood_state_round_trips_json_primitives() -> None:
    occurrence = _occurrence()
    state = RegionalFloodState(
        active_by_region={"101": occurrence},
        activation_streaks={"202": 1},
        resolution_streaks={"101": 1},
        activation_sources={"202": ("rain-14",)},
        resolution_sources={"101": ("dry-14",)},
        last_evaluated_month=14,
    )

    encoded = state.to_dict()
    restored = RegionalFloodState.from_dict(encoded)

    assert restored.to_dict() == encoded
    assert restored.active_by_region["101"].source_event_ids == (
        "rain-13",
        "rain-14",
    )


def test_regional_flood_state_rejects_obsolete_or_inconsistent_shape() -> None:
    with pytest.raises(ValueError, match="current schema"):
        RegionalFloodState.from_dict({"active_floods": {}})

    with pytest.raises(ValueError, match="source keys"):
        RegionalFloodState(
            activation_streaks={"101": 1},
            activation_sources={},
        )

    with pytest.raises(ValueError, match="between 0 and 1"):
        RegionalFloodOccurrence(
            region_id="101",
            started_month=14,
            activation_risk=1.2,
            source_event_ids=("rain-14",),
            last_event_id="flood-started",
        )

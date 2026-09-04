from __future__ import annotations

import pytest

from src.classes.environment.regional_flood import (
    DrainageObservation,
    FloodWindowEvidence,
    RegionalFloodOccurrence,
    RegionalFloodState,
)


def _drainage(month: int, *, source_event_ids: tuple[str, ...] = ()) -> DrainageObservation:
    return DrainageObservation(
        month=month,
        drainage=0.4,
        state_refs=("map:infrastructure_site:site:gate:integrity",),
        source_event_ids=source_event_ids,
    )


def _occurrence() -> RegionalFloodOccurrence:
    return RegionalFloodOccurrence(
        region_id="101",
        started_month=14,
        activation_risk=0.82,
        source_event_ids=("rain-13", "rain-14", "rain-14"),
        last_event_id="flood-started",
        drainage_observations=(
            _drainage(14, source_event_ids=("repair-14",)),
            _drainage(13, source_event_ids=("repair-13",)),
        ),
    )


def test_regional_flood_state_round_trips_json_primitives() -> None:
    occurrence = _occurrence()
    state = RegionalFloodState(
        active_by_region={"101": occurrence},
        activation_streaks={"202": 1},
        resolution_streaks={"101": 1},
        activation_evidence={
            "202": FloodWindowEvidence(
                source_event_ids=("rain-14",),
                drainage_observations=(_drainage(14),),
            )
        },
        resolution_evidence={
            "101": FloodWindowEvidence(
                source_event_ids=("dry-14",),
                drainage_observations=(_drainage(14),),
            )
        },
        last_evaluated_month=14,
    )

    encoded = state.to_dict()
    restored = RegionalFloodState.from_dict(encoded)

    assert restored.to_dict() == encoded
    assert restored.active_by_region["101"].source_event_ids == (
        "rain-13",
        "rain-14",
    )
    # Both months of the activation window survive, oldest first.
    assert [
        observation.month
        for observation in restored.active_by_region["101"].drainage_observations
    ] == [13, 14]
    assert restored.active_by_region["101"].infrastructure_context_event_ids == (
        "repair-13",
        "repair-14",
    )


def test_regional_flood_state_rejects_obsolete_or_inconsistent_shape() -> None:
    with pytest.raises(ValueError, match="current schema"):
        RegionalFloodState.from_dict({"active_floods": {}})

    with pytest.raises(ValueError, match="current schema"):
        RegionalFloodState.from_dict(
            {
                "active_by_region": {},
                "activation_streaks": {},
                "resolution_streaks": {},
                "activation_sources": {},
                "resolution_sources": {},
                "last_evaluated_month": None,
            }
        )

    with pytest.raises(ValueError, match="evidence keys"):
        RegionalFloodState(
            activation_streaks={"101": 1},
            activation_evidence={},
        )

    with pytest.raises(ValueError, match="one observation per month"):
        FloodWindowEvidence(
            source_event_ids=("rain-14",),
            drainage_observations=(_drainage(14), _drainage(14)),
        )

    with pytest.raises(ValueError, match="between 0 and 1"):
        RegionalFloodOccurrence(
            region_id="101",
            started_month=14,
            activation_risk=1.2,
            source_event_ids=("rain-14",),
            last_event_id="flood-started",
        )


@pytest.mark.parametrize(
    ("streak", "months", "last_evaluated_month", "message"),
    [
        (1, (13, 14), 14, "one observation per streak month"),
        (2, (12, 14), 14, "consecutive window"),
        (2, (12, 13), 14, "consecutive window"),
        (1, (14,), None, "requires an evaluated month"),
    ],
)
def test_pending_window_must_be_the_months_actually_evaluated(
    streak: int,
    months: tuple[int, ...],
    last_evaluated_month: int | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RegionalFloodState(
            activation_streaks={"101": streak},
            activation_evidence={
                "101": FloodWindowEvidence(
                    source_event_ids=("rain-14",),
                    drainage_observations=tuple(_drainage(month) for month in months),
                )
            },
            last_evaluated_month=last_evaluated_month,
        )

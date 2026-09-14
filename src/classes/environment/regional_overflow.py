"""Small, medieval-only state for naturally occurring regional overflow.

The state records the engine's monthly readings and active occurrences.  It
does *not* mirror map integrity, routes, economy, climate, or actor knowledge:
those remain with their canonical owners.  An occurrence only keeps IDs of the
facts and the one site it already affected, which makes the bounded physical
effect auditable without making this a second infrastructure model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _OverflowValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RegionalOverflowAssessment(_OverflowValue):
    """One deterministic hydrologic reading for a physical map region."""

    id: str
    region_id: int = Field(strict=True, gt=0)
    assessed_day: int = Field(strict=True, ge=0)
    load: int = Field(strict=True, ge=0, le=100)
    streak: int = Field(strict=True, ge=0)
    evidence_event_id: str


class RegionalOverflowOccurrence(_OverflowValue):
    """A still-active overflow and the one infrastructure consequence it caused."""

    id: str
    region_id: int = Field(strict=True, gt=0)
    started_day: int = Field(strict=True, ge=0)
    load: int = Field(strict=True, ge=0, le=100)
    assessment_event_id: str
    started_event_id: str
    damaged_site_id: str | None = None
    damage_event_id: str | None = None


@dataclass
class RegionalOverflowState:
    """Persisted observations and active regional overflow occurrences only."""

    assessments: dict[str, RegionalOverflowAssessment] = field(default_factory=dict)
    active_occurrences: dict[str, RegionalOverflowOccurrence] = field(default_factory=dict)

    @staticmethod
    def assessment_id(region_id: int) -> str:
        return f"regional_overflow_assessment:{region_id}"

    @staticmethod
    def occurrence_id(region_id: int) -> str:
        return f"regional_overflow:{region_id}"

    def assessment(self, region_id: int) -> RegionalOverflowAssessment | None:
        return self.assessments.get(self.assessment_id(region_id))

    def occurrence(self, region_id: int) -> RegionalOverflowOccurrence | None:
        return self.active_occurrences.get(self.occurrence_id(region_id))

    def validate(self, world=None) -> None:
        if not isinstance(self.assessments, dict) or not isinstance(self.active_occurrences, dict):
            raise ValueError("invalid regional overflow registries")
        known_regions = set(world.map.regions) if world is not None else None
        events = {event.id: event for event in world.events} if world is not None else {}
        for key, item in self.assessments.items():
            if (not isinstance(item, RegionalOverflowAssessment)
                    or key != self.assessment_id(item.region_id)
                    or item.assessed_day % 30):
                raise ValueError("invalid regional overflow assessment")
            RegionalOverflowAssessment.model_validate(item.model_dump(mode="json"))
            if known_regions is not None and item.region_id not in known_regions:
                raise ValueError("regional overflow assessment has an unknown region")
            if world is not None:
                event = events.get(item.evidence_event_id)
                if (event is None or event.day != item.assessed_day
                        or event.event_type != "regional_hydrologic_load_assessed"):
                    raise ValueError("regional overflow assessment requires its factual evidence")
        for key, item in self.active_occurrences.items():
            if (not isinstance(item, RegionalOverflowOccurrence)
                    or key != self.occurrence_id(item.region_id)):
                raise ValueError("invalid regional overflow occurrence")
            RegionalOverflowOccurrence.model_validate(item.model_dump(mode="json"))
            if (item.damaged_site_id is None) != (item.damage_event_id is None):
                raise ValueError("regional overflow damage references must be paired")
            if known_regions is not None and item.region_id not in known_regions:
                raise ValueError("regional overflow occurrence has an unknown region")
            if world is not None:
                started = events.get(item.started_event_id)
                assessment = events.get(item.assessment_event_id)
                if (assessment is None or assessment.event_type != "regional_hydrologic_load_assessed"
                        or started is None or started.day != item.started_day
                        or started.event_type != "regional_overflow_started"):
                    raise ValueError("regional overflow occurrence requires its start fact")
                if item.assessment_event_id not in {link.cause_event_id for link in started.causal_links}:
                    raise ValueError("regional overflow start requires its assessment evidence")
                if item.damaged_site_id is not None:
                    site = world.map.infrastructure_sites.get(item.damaged_site_id)
                    damaged = events.get(item.damage_event_id)
                    if (site is None or damaged is None or damaged.event_type != "site_overflow_damaged"
                            or not any(delta.owner_kind == "site" and delta.owner_id == site.id
                                       and delta.aspect == "integrity" for delta in damaged.deltas)):
                        raise ValueError("regional overflow occurrence requires its site damage fact")
                    if item.started_event_id not in {link.cause_event_id for link in damaged.causal_links}:
                        raise ValueError("regional overflow damage requires its occurrence start fact")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": 1,
            "assessments": {
                key: item.model_dump(mode="json") for key, item in sorted(self.assessments.items())
            },
            "active_occurrences": {
                key: item.model_dump(mode="json") for key, item in sorted(self.active_occurrences.items())
            },
        }

    @classmethod
    def from_dict(cls, data: Any) -> "RegionalOverflowState":
        expected = {"schema_version", "assessments", "active_occurrences"}
        if (not isinstance(data, dict) or set(data) != expected
                or type(data["schema_version"]) is not int or data["schema_version"] != 1
                or not isinstance(data["assessments"], dict)
                or not isinstance(data["active_occurrences"], dict)):
            raise ValueError("invalid regional overflow state schema")
        assessments: dict[str, RegionalOverflowAssessment] = {}
        for key, raw in data["assessments"].items():
            if not isinstance(key, str) or not isinstance(raw, dict):
                raise ValueError("invalid regional overflow assessment serialization")
            item = RegionalOverflowAssessment.model_validate(raw)
            assessments[key] = item
        occurrences: dict[str, RegionalOverflowOccurrence] = {}
        for key, raw in data["active_occurrences"].items():
            if not isinstance(key, str) or not isinstance(raw, dict):
                raise ValueError("invalid regional overflow occurrence serialization")
            item = RegionalOverflowOccurrence.model_validate(raw)
            occurrences[key] = item
        state = cls(assessments=assessments, active_occurrences=occurrences)
        state.validate()
        return state


__all__ = [
    "RegionalOverflowAssessment",
    "RegionalOverflowOccurrence",
    "RegionalOverflowState",
]

"""Canonical month-scoped regional weather owned by the world."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Real
from typing import Any


def _ratio(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return normalized


def _month(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True)
class RegionalWeather:
    """The physical weather reading for one region in one simulation month."""

    region_id: str
    month: int
    precipitation: float
    soil_saturation: float
    previous_soil_saturation: float
    source_event_id: str | None = None

    def __post_init__(self) -> None:
        region_id = str(self.region_id).strip()
        if not region_id:
            raise ValueError("region_id must be non-empty")
        object.__setattr__(self, "region_id", region_id)
        object.__setattr__(self, "month", _month(self.month, "month"))
        object.__setattr__(self, "precipitation", _ratio(self.precipitation, "precipitation"))
        object.__setattr__(self, "soil_saturation", _ratio(self.soil_saturation, "soil_saturation"))
        object.__setattr__(
            self,
            "previous_soil_saturation",
            _ratio(self.previous_soil_saturation, "previous_soil_saturation"),
        )
        if self.source_event_id is not None:
            source_event_id = str(self.source_event_id).strip()
            if not source_event_id:
                raise ValueError("source_event_id must be non-empty or null")
            object.__setattr__(self, "source_event_id", source_event_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "month": self.month,
            "precipitation": self.precipitation,
            "soil_saturation": self.soil_saturation,
            "previous_soil_saturation": self.previous_soil_saturation,
            "source_event_id": self.source_event_id,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "RegionalWeather":
        if not isinstance(data, dict):
            raise ValueError("Regional weather must be an object")
        required = {
            "region_id",
            "month",
            "precipitation",
            "soil_saturation",
            "previous_soil_saturation",
            "source_event_id",
        }
        if set(data) != required:
            raise ValueError("Regional weather fields do not match the current schema")
        return cls(**data)


@dataclass(slots=True)
class ClimateState:
    """World-owned weather state; geography remains map-owned and static."""

    regions: dict[str, RegionalWeather] = field(default_factory=dict)
    last_updated_month: int | None = None

    def __post_init__(self) -> None:
        normalized: dict[str, RegionalWeather] = {}
        for region_id, weather in self.regions.items():
            if not isinstance(weather, RegionalWeather):
                raise TypeError("climate regions must contain RegionalWeather values")
            key = str(region_id)
            if key != weather.region_id:
                raise ValueError("climate region key must match its weather region_id")
            normalized[key] = weather
        self.regions = normalized
        if self.last_updated_month is not None:
            self.last_updated_month = _month(
                self.last_updated_month,
                "last_updated_month",
            )

    def get(self, region_id: int | str, month: int | None = None) -> RegionalWeather | None:
        weather = self.regions.get(str(region_id))
        if weather is None or (month is not None and weather.month != int(month)):
            return None
        return weather

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_updated_month": self.last_updated_month,
            "regions": {
                region_id: weather.to_dict()
                for region_id, weather in sorted(self.regions.items())
            },
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ClimateState":
        if data in (None, {}):
            return cls()
        if not isinstance(data, dict) or set(data) != {"last_updated_month", "regions"}:
            raise ValueError("Climate state fields do not match the current schema")
        raw_regions = data["regions"]
        if not isinstance(raw_regions, dict):
            raise ValueError("Climate state regions must be an object")
        return cls(
            last_updated_month=data["last_updated_month"],
            regions={
                str(region_id): RegionalWeather.from_dict(weather)
                for region_id, weather in raw_regions.items()
            },
        )


__all__ = ["ClimateState", "RegionalWeather"]

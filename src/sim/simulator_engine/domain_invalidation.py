from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class DomainInvalidationLayer(StrEnum):
    MECHANICAL = "mechanical"
    SEMANTIC = "semantic"


class DomainInvalidationReason(StrEnum):
    POPULATION_CHANGED = "population_changed"
    RESOURCE_STOCK_CHANGED = "resource_stock_changed"
    INFRASTRUCTURE_CHANGED = "infrastructure_changed"
    URBAN_PROJECT_CHANGED = "urban_project_changed"
    POPULATION_CAPACITY_CHANGED = "population_capacity_changed"
    CONDITION_ACTIVATED = "condition_activated"
    CONDITION_RESOLVED = "condition_resolved"


@dataclass(frozen=True, slots=True)
class DomainInvalidation:
    layer: DomainInvalidationLayer
    domain: str
    target_kind: str
    target_id: str
    reason: DomainInvalidationReason
    source_event_ids: tuple[str, ...] = ()
    condition_instance_id: str | None = None
    revision: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_event_ids",
            tuple(dict.fromkeys(str(item) for item in self.source_event_ids if str(item))),
        )


@dataclass(slots=True)
class DomainInvalidationQueue:
    _items: list[DomainInvalidation] = field(default_factory=list)

    def mark(self, invalidation: DomainInvalidation) -> None:
        if invalidation not in self._items:
            self._items.append(invalidation)

    def drain(
        self,
        *,
        layer: DomainInvalidationLayer | None = None,
        domain: str | None = None,
    ) -> list[DomainInvalidation]:
        selected = [
            item
            for item in self._items
            if (layer is None or item.layer is layer)
            and (domain is None or item.domain == domain)
        ]
        self._items = [item for item in self._items if item not in selected]
        return selected

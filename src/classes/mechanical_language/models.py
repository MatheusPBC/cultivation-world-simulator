from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import math
from typing import Any
import uuid


class PrimitiveDimension(StrEnum):
    """Primitive mechanical grammar V1. Only engine code may extend it."""

    STOCK = "stock"
    FLOW = "flow"
    LOAD = "load"
    CAPACITY = "capacity"
    ACCESS = "access"
    QUALITY = "quality"
    RISK = "risk"
    INFLUENCE = "influence"
    DEPENDENCY = "dependency"


class MeasurementAvailability(StrEnum):
    MEASURABLE = "measurable"
    PARTIALLY_MEASURABLE = "partially_measurable"
    UNMEASURABLE = "unmeasurable"


class ReadingKind(StrEnum):
    EXACT = "exact"
    DERIVED = "derived"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class GroundingStatus(StrEnum):
    PROPOSED = "proposed"
    CLAIMED = "claimed"
    GROUNDED = "grounded"


class ConceptLifecycle(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DORMANT = "dormant"
    DEPRECATED = "deprecated"
    MERGED = "merged"


@dataclass(frozen=True, slots=True)
class Grounding:
    id: str
    concept_id: str
    subject_kind: str
    subject_id: str
    dimension: PrimitiveDimension
    metric_definition_id: str | None
    evidence_refs: tuple[str, ...]
    status: GroundingStatus
    created_month: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "concept_id": self.concept_id,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "dimension": self.dimension.value,
            "metric_definition_id": self.metric_definition_id,
            "evidence_refs": list(self.evidence_refs),
            "status": self.status.value,
            "created_month": self.created_month,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Grounding":
        return cls(
            id=str(data["id"]),
            concept_id=str(data["concept_id"]),
            subject_kind=str(data["subject_kind"]),
            subject_id=str(data["subject_id"]),
            dimension=PrimitiveDimension(str(data["dimension"])),
            metric_definition_id=(
                str(data["metric_definition_id"])
                if data.get("metric_definition_id") is not None
                else None
            ),
            evidence_refs=tuple(str(item) for item in data.get("evidence_refs", [])),
            status=GroundingStatus(str(data["status"])),
            created_month=int(data["created_month"]),
        )


@dataclass(frozen=True, slots=True)
class EntityRef:
    kind: str
    id: str

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.id.strip():
            raise ValueError("entity references require kind and id")

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityRef":
        return cls(kind=str(data["kind"]), id=str(data["id"]))


@dataclass(frozen=True, slots=True)
class MetricKey:
    dimension: PrimitiveDimension
    subject_kind: str
    subject_id: str
    concept_id: str
    related: EntityRef | None = None
    group_id: str | None = None
    qualifiers: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(
            sorted((str(name), str(value)) for name, value in self.qualifiers)
        )
        if len({name for name, _ in normalized}) != len(normalized):
            raise ValueError("metric qualifiers must have unique names")
        if any(not name.strip() or not value.strip() for name, value in normalized):
            raise ValueError("metric qualifiers require non-empty names and values")
        object.__setattr__(self, "qualifiers", normalized)

    @property
    def identity(self) -> tuple[Any, ...]:
        return (
            self.dimension,
            self.subject_kind,
            self.subject_id,
            self.concept_id,
            self.related,
            self.group_id,
            self.qualifiers,
        )

    def qualifier(self, name: str) -> str | None:
        return dict(self.qualifiers).get(name)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "dimension": self.dimension.value,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "concept_id": self.concept_id,
        }
        if self.related is not None:
            data["related"] = self.related.to_dict()
        if self.group_id is not None:
            data["group_id"] = self.group_id
        if self.qualifiers:
            data["qualifiers"] = dict(self.qualifiers)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetricKey":
        return cls(
            dimension=PrimitiveDimension(str(data["dimension"])),
            subject_kind=str(data["subject_kind"]),
            subject_id=str(data["subject_id"]),
            concept_id=str(data["concept_id"]),
            related=(
                EntityRef.from_dict(dict(data["related"]))
                if data.get("related") is not None
                else None
            ),
            group_id=(str(data["group_id"]) if data.get("group_id") is not None else None),
            qualifiers=tuple(
                (str(name), str(value))
                for name, value in dict(data.get("qualifiers", {})).items()
            ),
        )


@dataclass(frozen=True, slots=True)
class MetricReading:
    key: MetricKey
    value: float | None
    unit: str
    availability: MeasurementAvailability
    reading_kind: ReadingKind
    calculated_month: int = 0
    confidence: float | None = None
    derived_from: list[dict[str, str]] = field(default_factory=list)
    state_refs: list[str] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.value is not None and (
            isinstance(self.value, bool) or not math.isfinite(float(self.value))
        ):
            raise ValueError("metric values must be finite numbers")
        if self.reading_kind is ReadingKind.UNKNOWN and self.value is not None:
            raise ValueError("unknown readings cannot carry a numeric value")
        if self.reading_kind is ReadingKind.ESTIMATED:
            if self.confidence is None or not 0.0 <= self.confidence <= 1.0:
                raise ValueError("estimated readings require confidence in [0, 1]")
        elif self.confidence is not None:
            raise ValueError("confidence belongs only to estimated readings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key.to_dict(),
            "value": self.value,
            "unit": self.unit,
            "availability": self.availability.value,
            "reading_kind": self.reading_kind.value,
            "calculated_month": self.calculated_month,
            "confidence": self.confidence,
            "derived_from": list(self.derived_from),
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }


@dataclass(frozen=True, slots=True)
class Concept:
    id: str
    label: str
    concept_kind: str
    grounding_status: GroundingStatus = GroundingStatus.PROPOSED
    lifecycle: ConceptLifecycle = ConceptLifecycle.CANDIDATE
    grounded_by: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    created_month: int = 0
    last_used_month: int = 0
    merged_into: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["grounding_status"] = self.grounding_status.value
        data["lifecycle"] = self.lifecycle.value
        data["grounded_by"] = list(self.grounded_by)
        data["aliases"] = list(self.aliases)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Concept":
        return cls(
            id=str(data["id"]),
            label=str(data["label"]),
            concept_kind=str(data["concept_kind"]),
            grounding_status=GroundingStatus(str(data.get("grounding_status", "proposed"))),
            lifecycle=ConceptLifecycle(str(data.get("lifecycle", "candidate"))),
            grounded_by=tuple(str(item) for item in data.get("grounded_by", [])),
            aliases=tuple(str(item) for item in data.get("aliases", [])),
            created_month=int(data.get("created_month", 0)),
            last_used_month=int(data.get("last_used_month", 0)),
            merged_into=data.get("merged_into"),
        )


@dataclass(frozen=True, slots=True)
class DerivedMetricDefinition:
    id: str
    concept_id: str
    dimension: PrimitiveDimension
    target_kind: str
    expression: dict[str, Any]
    unit: str
    created_month: int
    lifecycle: ConceptLifecycle = ConceptLifecycle.CANDIDATE
    reuse_contexts: tuple[str, ...] = ()
    last_used_month: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "concept_id": self.concept_id,
            "dimension": self.dimension.value,
            "target_kind": self.target_kind,
            "expression": self.expression,
            "unit": self.unit,
            "created_month": self.created_month,
            "lifecycle": self.lifecycle.value,
            "reuse_contexts": list(self.reuse_contexts),
            "last_used_month": self.last_used_month,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DerivedMetricDefinition":
        return cls(
            id=str(data["id"]),
            concept_id=str(data["concept_id"]),
            dimension=PrimitiveDimension(str(data["dimension"])),
            target_kind=str(data["target_kind"]),
            expression=dict(data["expression"]),
            unit=str(data["unit"]),
            created_month=int(data["created_month"]),
            lifecycle=ConceptLifecycle(str(data.get("lifecycle", "candidate"))),
            reuse_contexts=tuple(str(item) for item in data.get("reuse_contexts", [])),
            last_used_month=int(data.get("last_used_month", 0)),
        )


@dataclass(frozen=True, slots=True)
class ConditionDefinition:
    id: str
    concept_id: str
    target_kind: str
    metric_definition_id: str
    activate_above: float
    resolve_below: float
    activate_after_months: int
    resolve_after_months: int
    created_month: int
    lifecycle: ConceptLifecycle = ConceptLifecycle.CANDIDATE

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in (self.resolve_below, self.activate_above)):
            raise ValueError("condition thresholds must be finite")
        if not 0.0 <= self.resolve_below < self.activate_above <= 1.0:
            raise ValueError("condition hysteresis requires normalized ordered thresholds")
        if not 1 <= self.activate_after_months <= 12 or not 1 <= self.resolve_after_months <= 12:
            raise ValueError("condition persistence must be between 1 and 12 months")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["lifecycle"] = self.lifecycle.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConditionDefinition":
        return cls(
            id=str(data["id"]),
            concept_id=str(data["concept_id"]),
            target_kind=str(data["target_kind"]),
            metric_definition_id=str(data["metric_definition_id"]),
            activate_above=float(data["activate_above"]),
            resolve_below=float(data["resolve_below"]),
            activate_after_months=int(data["activate_after_months"]),
            resolve_after_months=int(data["resolve_after_months"]),
            created_month=int(data["created_month"]),
            lifecycle=ConceptLifecycle(str(data.get("lifecycle", "candidate"))),
        )


@dataclass(frozen=True, slots=True)
class ConditionInstance:
    id: str
    definition_id: str
    target_kind: str
    target_id: str
    label: str
    intensity: float
    started_month: int
    cause_event_id: str
    source_readings: tuple[dict[str, Any], ...] = ()
    resolved_month: int | None = None
    resolution_event_id: str | None = None
    expires_month: int | None = None

    def __post_init__(self) -> None:
        if not self.definition_id.strip() or not self.label.strip():
            raise ValueError("condition definition and label are required")
        object.__setattr__(self, "intensity", max(0.0, min(1.0, float(self.intensity))))

    def is_active(self, current_month: int) -> bool:
        return self.resolved_month is None and (
            self.expires_month is None or int(current_month) < self.expires_month
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "definition_id": self.definition_id,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "label": self.label,
            "intensity": self.intensity,
            "started_month": self.started_month,
            "cause_event_id": self.cause_event_id,
            "source_readings": list(self.source_readings),
            "resolved_month": self.resolved_month,
            "resolution_event_id": self.resolution_event_id,
            "expires_month": self.expires_month,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConditionInstance":
        return cls(
            id=str(data["id"]),
            definition_id=str(data["definition_id"]),
            target_kind=str(data["target_kind"]),
            target_id=str(data["target_id"]),
            label=str(data["label"]),
            intensity=float(data.get("intensity", 1.0)),
            started_month=int(data.get("started_month", 0)),
            cause_event_id=str(data.get("cause_event_id", "")),
            source_readings=tuple(dict(item) for item in data.get("source_readings", [])),
            resolved_month=data.get("resolved_month"),
            resolution_event_id=data.get("resolution_event_id"),
            expires_month=data.get("expires_month"),
        )


@dataclass(frozen=True, slots=True)
class DomainReactionReceipt:
    id: str
    condition_instance_id: str
    domain: str
    trigger_revision: str
    decision_event_ids: tuple[str, ...] = ()
    next_eligible_month: int | None = None
    completed: bool = False

    @classmethod
    def create(
        cls,
        condition_instance_id: str,
        domain: str,
        trigger_revision: str,
        *,
        decision_event_ids: tuple[str, ...] = (),
        next_eligible_month: int | None = None,
        completed: bool = False,
    ) -> "DomainReactionReceipt":
        return cls(
            id=f"{condition_instance_id}|{domain}|{trigger_revision}",
            condition_instance_id=condition_instance_id,
            domain=domain,
            trigger_revision=trigger_revision,
            decision_event_ids=decision_event_ids,
            next_eligible_month=next_eligible_month,
            completed=completed,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "condition_instance_id": self.condition_instance_id,
            "domain": self.domain,
            "trigger_revision": self.trigger_revision,
            "decision_event_ids": list(self.decision_event_ids),
            "next_eligible_month": self.next_eligible_month,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DomainReactionReceipt":
        return cls(
            id=str(data["id"]),
            condition_instance_id=str(data["condition_instance_id"]),
            domain=str(data["domain"]),
            trigger_revision=str(data["trigger_revision"]),
            decision_event_ids=tuple(
                str(item) for item in data["decision_event_ids"]
            ),
            next_eligible_month=(
                int(data["next_eligible_month"])
                if data["next_eligible_month"] is not None
                else None
            ),
            completed=bool(data["completed"]),
        )


@dataclass(frozen=True, slots=True)
class MechanicProposal:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    concept: str = ""
    reason: str = ""
    unmeasurable_keys: tuple[dict[str, str], ...] = ()
    created_month: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "concept": self.concept,
            "reason": self.reason,
            "unmeasurable_keys": list(self.unmeasurable_keys),
            "created_month": self.created_month,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MechanicProposal":
        return cls(
            id=str(data["id"]),
            concept=str(data.get("concept", "")),
            reason=str(data.get("reason", "")),
            unmeasurable_keys=tuple(dict(item) for item in data.get("unmeasurable_keys", [])),
            created_month=int(data.get("created_month", 0)),
        )

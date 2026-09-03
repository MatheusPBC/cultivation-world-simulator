"""Transient, engine-owned options for collective-domain decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Mapping

from src.classes.mechanical_language import EntityRef


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) or not key for key in value):
            raise ValueError("affordance parameter keys must be non-empty strings")
        return {key: _json_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("affordance parameters must be finite JSON values")
        return value
    raise ValueError("affordance parameters must contain only JSON values")


@dataclass(frozen=True, slots=True)
class DomainAffordance:
    """One currently executable option, recomputed rather than persisted."""

    domain: str
    actor_ref: EntityRef
    action_kind: str
    target_refs: tuple[EntityRef, ...]
    parameters: Mapping[str, Any]
    urgency: float
    motivation_event_ids: tuple[str, ...]
    id: str = field(default="")

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain", _required_text(self.domain, "domain"))
        if not isinstance(self.actor_ref, EntityRef):
            raise ValueError("actor_ref must be an EntityRef")
        object.__setattr__(
            self, "action_kind", _required_text(self.action_kind, "action_kind")
        )
        targets = tuple(self.target_refs)
        if any(not isinstance(item, EntityRef) for item in targets):
            raise ValueError("target_refs must contain EntityRef values")
        if len(set(targets)) != len(targets):
            raise ValueError("target_refs must not contain duplicates")
        object.__setattr__(self, "target_refs", targets)
        params = _json_value(self.parameters)
        object.__setattr__(self, "parameters", MappingProxyType(params))
        if isinstance(self.urgency, bool) or not isinstance(self.urgency, (int, float)):
            raise ValueError("urgency must be a number")
        urgency = float(self.urgency)
        if not math.isfinite(urgency) or not 0.0 <= urgency <= 1.0:
            raise ValueError("urgency must be between 0 and 1")
        object.__setattr__(self, "urgency", urgency)
        motivation = tuple(
            dict.fromkeys(
                _required_text(item, "motivation_event_id")
                for item in self.motivation_event_ids
            )
        )
        if not motivation:
            raise ValueError("affordances require motivating evidence")
        object.__setattr__(self, "motivation_event_ids", motivation)
        expected_id = self.deterministic_id()
        if self.id and self.id != expected_id:
            raise ValueError("affordance id does not match its canonical content")
        object.__setattr__(self, "id", expected_id)

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "actor_ref": self.actor_ref.to_dict(),
            "action_kind": self.action_kind,
            "target_refs": [item.to_dict() for item in self.target_refs],
            "parameters": _json_value(self.parameters),
            "urgency": self.urgency,
            "motivation_event_ids": list(self.motivation_event_ids),
        }

    def deterministic_id(self) -> str:
        encoded = json.dumps(
            self._identity_payload(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "aff-" + hashlib.sha256(encoded).hexdigest()[:32]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, **self._identity_payload()}


class DomainDecisionKind(StrEnum):
    MAINTAIN = "maintain"
    ACT = "act"


@dataclass(frozen=True, slots=True)
class DomainDecision:
    """An actor may select one offered option or explicitly maintain state."""

    decision: DomainDecisionKind
    reason: str
    selected_affordance_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.decision, DomainDecisionKind):
            raise ValueError("decision must be maintain or act")
        object.__setattr__(self, "reason", _required_text(self.reason, "reason"))
        if self.decision is DomainDecisionKind.ACT:
            object.__setattr__(
                self,
                "selected_affordance_id",
                _required_text(
                    self.selected_affordance_id, "selected_affordance_id"
                ),
            )
        elif self.selected_affordance_id is not None:
            raise ValueError("maintain cannot select an affordance")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "decision": self.decision.value,
            "reason": self.reason,
        }
        if self.selected_affordance_id is not None:
            result["selected_affordance_id"] = self.selected_affordance_id
        return result


__all__ = ["DomainAffordance", "DomainDecision", "DomainDecisionKind"]

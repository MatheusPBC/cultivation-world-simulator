"""World-independent institutional knowledge registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .authority_state import InstitutionalAuthorityState
from .models import INSTITUTION_MODEL_VERSION, InstitutionalFactKnowledge


def _strict_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TypeError("knowledge state must be an object")
    fields = {"model_version", "known_facts"}
    missing = fields - set(data)
    unknown = set(data) - fields
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing {sorted(missing)}")
        if unknown:
            details.append(f"unknown {sorted(unknown)}")
        raise ValueError(f"knowledge state has invalid fields: {', '.join(details)}")
    if (
        type(data["model_version"]) is not int
        or data["model_version"] != INSTITUTION_MODEL_VERSION
    ):
        raise ValueError(
            f"unsupported knowledge state model_version: {data['model_version']!r}"
        )
    return data


@dataclass(slots=True)
class InstitutionalKnowledgeState:
    model_version: int = INSTITUTION_MODEL_VERSION
    known_facts: dict[str, InstitutionalFactKnowledge] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            type(self.model_version) is not int
            or self.model_version != INSTITUTION_MODEL_VERSION
        ):
            raise ValueError(
                f"unsupported knowledge state model_version: {self.model_version!r}"
            )
        if not isinstance(self.known_facts, dict):
            raise TypeError("known_facts must be a dictionary")
        for key, fact in self.known_facts.items():
            if not isinstance(key, str) or not isinstance(
                fact, InstitutionalFactKnowledge
            ):
                raise ValueError(
                    "known_facts must be keyed by InstitutionalFactKnowledge IDs"
                )
            if fact.id != key:
                raise ValueError("known_facts key does not match fact id")

    def record(
        self,
        fact: InstitutionalFactKnowledge,
        authority_state: InstitutionalAuthorityState,
    ) -> InstitutionalFactKnowledge:
        if not isinstance(fact, InstitutionalFactKnowledge):
            raise TypeError("fact must be an InstitutionalFactKnowledge")
        if not isinstance(authority_state, InstitutionalAuthorityState):
            raise TypeError("authority_state must be an InstitutionalAuthorityState")
        if authority_state.get_institution(fact.institution_id) is None:
            raise ValueError(
                f"fact references unknown institution: {fact.institution_id}"
            )
        existing = self.known_facts.get(fact.id)
        if existing is not None:
            # A fact can be learned through multiple channels, but its first
            # learned month is the durable knowledge boundary.
            return existing
        self.known_facts[fact.id] = fact
        return fact

    def get_fact(
        self, institution_id: str, event_id: str
    ) -> InstitutionalFactKnowledge | None:
        return self.known_facts.get(
            InstitutionalFactKnowledge.id_for(institution_id, event_id)
        )

    def contains(self, institution_id: str, event_id: str) -> bool:
        return self.get_fact(institution_id, event_id) is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "known_facts": {
                key: self.known_facts[key].to_dict() for key in sorted(self.known_facts)
            },
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        authority_state: InstitutionalAuthorityState,
    ) -> "InstitutionalKnowledgeState":
        raw = _strict_payload(data)
        known_facts_raw = raw["known_facts"]
        if not isinstance(known_facts_raw, dict):
            raise TypeError("known_facts must be an object keyed by ID")
        known_facts: dict[str, InstitutionalFactKnowledge] = {}
        for key, item in known_facts_raw.items():
            if (
                not isinstance(key, str)
                or not key.strip()
                or not isinstance(item, dict)
            ):
                raise ValueError(
                    "known_facts must contain object values keyed by non-empty IDs"
                )
            fact = InstitutionalFactKnowledge.from_dict(item)
            if fact.id != key:
                raise ValueError("known_facts key does not match fact id")
            if set(item) != set(fact.to_dict()):
                raise ValueError(f"known_facts[{key!r}] has invalid fields")
            known_facts[key] = fact
        state = cls(model_version=raw["model_version"])
        for fact in known_facts.values():
            state.record(fact, authority_state)
        return state


__all__ = ["InstitutionalKnowledgeState"]

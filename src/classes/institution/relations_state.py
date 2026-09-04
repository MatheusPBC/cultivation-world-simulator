"""World-independent institutional relations, obligations and memories."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .authority_state import InstitutionalAuthorityState
from .knowledge_state import InstitutionalKnowledgeState
from .models import (
    CommitmentTerm,
    CommitmentTermStatus,
    INSTITUTION_MODEL_VERSION,
    InstitutionalCommitment,
    InstitutionalMemory,
    InstitutionalRelation,
    RecognitionRecord,
)


_TERM_TRANSITIONS = {
    CommitmentTermStatus.PROPOSED: {
        CommitmentTermStatus.PROPOSED,
        CommitmentTermStatus.ACTIVE,
        CommitmentTermStatus.CANCELLED,
        CommitmentTermStatus.EXPIRED,
    },
    CommitmentTermStatus.ACTIVE: {
        CommitmentTermStatus.ACTIVE,
        CommitmentTermStatus.FULFILLED,
        CommitmentTermStatus.BREACHED,
        CommitmentTermStatus.CANCELLED,
        CommitmentTermStatus.EXPIRED,
    },
    CommitmentTermStatus.BREACHED: {
        CommitmentTermStatus.BREACHED,
        CommitmentTermStatus.REMEDIATION_PROPOSED,
        CommitmentTermStatus.CANCELLED,
        CommitmentTermStatus.EXPIRED,
    },
    CommitmentTermStatus.REMEDIATION_PROPOSED: {
        CommitmentTermStatus.REMEDIATION_PROPOSED,
        CommitmentTermStatus.REMEDIATED,
        CommitmentTermStatus.BREACHED,
        CommitmentTermStatus.CANCELLED,
        CommitmentTermStatus.EXPIRED,
    },
    CommitmentTermStatus.FULFILLED: {CommitmentTermStatus.FULFILLED},
    CommitmentTermStatus.REMEDIATED: {CommitmentTermStatus.REMEDIATED},
    CommitmentTermStatus.CANCELLED: {CommitmentTermStatus.CANCELLED},
    CommitmentTermStatus.EXPIRED: {CommitmentTermStatus.EXPIRED},
}


def _strict_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TypeError("relations state must be an object")
    fields = {"model_version", "relations", "commitments", "memories", "recognitions"}
    missing = fields - set(data)
    unknown = set(data) - fields
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing {sorted(missing)}")
        if unknown:
            details.append(f"unknown {sorted(unknown)}")
        raise ValueError(f"relations state has invalid fields: {', '.join(details)}")
    if (
        type(data["model_version"]) is not int
        or data["model_version"] != INSTITUTION_MODEL_VERSION
    ):
        raise ValueError(
            f"unsupported relations state model_version: {data['model_version']!r}"
        )
    return data


def _registry(data: Any, parser, label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TypeError(f"{label} must be an object keyed by ID")
    result: dict[str, Any] = {}
    for key, raw in data.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(raw, dict):
            raise ValueError(
                f"{label} must contain object values keyed by non-empty IDs"
            )
        item = parser(raw)
        if item.id != key:
            raise ValueError(f"{label}[{key!r}] id does not match its registry key")
        if set(raw) != set(item.to_dict()):
            raise ValueError(f"{label}[{key!r}] has invalid fields")
        result[key] = item
    return result


@dataclass(slots=True)
class InstitutionalRelationsState:
    model_version: int = INSTITUTION_MODEL_VERSION
    relations: dict[str, InstitutionalRelation] = field(default_factory=dict)
    commitments: dict[str, InstitutionalCommitment] = field(default_factory=dict)
    memories: dict[str, InstitutionalMemory] = field(default_factory=dict)
    recognitions: dict[str, RecognitionRecord] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            type(self.model_version) is not int
            or self.model_version != INSTITUTION_MODEL_VERSION
        ):
            raise ValueError(
                f"unsupported relations state model_version: {self.model_version!r}"
            )
        for name, registry in (
            ("relations", self.relations),
            ("commitments", self.commitments),
            ("memories", self.memories),
            ("recognitions", self.recognitions),
        ):
            if not isinstance(registry, dict):
                raise TypeError(f"{name} must be a dictionary")
            for key, item in registry.items():
                if not isinstance(key, str) or getattr(item, "id", None) != key:
                    raise ValueError(f"{name} key does not match item id")

    def add_relation(
        self,
        relation: InstitutionalRelation,
        authority_state: InstitutionalAuthorityState,
    ) -> None:
        if not isinstance(relation, InstitutionalRelation):
            raise TypeError("relation must be an InstitutionalRelation")
        self._require_institutions(
            authority_state, (relation.institution_a_id, relation.institution_b_id)
        )
        if relation.id in self.relations:
            raise ValueError(f"duplicate relation id: {relation.id}")
        self.relations[relation.id] = relation

    def add_commitment(
        self,
        commitment: InstitutionalCommitment,
        authority_state: InstitutionalAuthorityState,
    ) -> None:
        if not isinstance(commitment, InstitutionalCommitment):
            raise TypeError("commitment must be an InstitutionalCommitment")
        self._validate_commitment_refs(commitment, authority_state)
        if commitment.id in self.commitments:
            raise ValueError(f"duplicate commitment id: {commitment.id}")
        self.commitments[commitment.id] = commitment

    def add_recognition(
        self,
        recognition: RecognitionRecord,
        authority_state: InstitutionalAuthorityState,
    ) -> None:
        if not isinstance(recognition, RecognitionRecord):
            raise TypeError("recognition must be a RecognitionRecord")
        self._require_institutions(
            authority_state, (recognition.recognizer_institution_id,)
        )
        if (
            authority_state is None
            or authority_state.get_claim(recognition.claim_id) is None
        ):
            raise ValueError(
                f"recognition references unknown claim: {recognition.claim_id}"
            )
        if recognition.id in self.recognitions:
            raise ValueError(f"duplicate recognition id: {recognition.id}")
        self.recognitions[recognition.id] = recognition

    def add_memory(
        self,
        memory: InstitutionalMemory,
        knowledge_state: InstitutionalKnowledgeState,
        authority_state: InstitutionalAuthorityState,
    ) -> None:
        if not isinstance(memory, InstitutionalMemory):
            raise TypeError("memory must be an InstitutionalMemory")
        self._require_institutions(authority_state, (memory.institution_id,))
        if not isinstance(
            knowledge_state, InstitutionalKnowledgeState
        ) or not knowledge_state.contains(memory.institution_id, memory.event_id):
            raise ValueError(
                "institutional memory requires known fact: "
                f"{memory.institution_id}/{memory.event_id}"
            )
        if memory.id in self.memories:
            raise ValueError(f"duplicate memory id: {memory.id}")
        self.memories[memory.id] = memory

    @staticmethod
    def _require_institutions(
        authority_state: InstitutionalAuthorityState,
        institution_ids: tuple[str, ...],
    ) -> None:
        if not isinstance(authority_state, InstitutionalAuthorityState):
            raise TypeError("authority_state must be an InstitutionalAuthorityState")
        missing = [
            institution_id
            for institution_id in institution_ids
            if authority_state.get_institution(institution_id) is None
        ]
        if missing:
            raise ValueError(f"unknown institution reference: {', '.join(missing)}")

    def _validate_commitment_refs(
        self,
        commitment: InstitutionalCommitment,
        authority_state: InstitutionalAuthorityState,
    ) -> None:
        self._require_institutions(authority_state, commitment.party_ids)
        parties = set(commitment.party_ids)
        term_institutions = {
            institution_id
            for term in commitment.terms
            for institution_id in (
                term.obligor_institution_id,
                term.beneficiary_institution_id,
            )
        }
        self._require_institutions(authority_state, tuple(term_institutions))
        if not term_institutions.issubset(parties):
            raise ValueError(
                "commitment term references institution outside its parties"
            )

    def replace_relation(
        self,
        relation: InstitutionalRelation,
        authority_state: InstitutionalAuthorityState,
    ) -> None:
        if not isinstance(relation, InstitutionalRelation):
            raise TypeError("relation must be an InstitutionalRelation")
        if relation.id not in self.relations:
            raise KeyError(f"unknown relation: {relation.id}")
        self._require_institutions(
            authority_state, (relation.institution_a_id, relation.institution_b_id)
        )
        self.relations[relation.id] = relation

    def replace_commitment(
        self,
        commitment: InstitutionalCommitment,
        authority_state: InstitutionalAuthorityState,
    ) -> None:
        if not isinstance(commitment, InstitutionalCommitment):
            raise TypeError("commitment must be an InstitutionalCommitment")
        if commitment.id not in self.commitments:
            raise KeyError(f"unknown commitment: {commitment.id}")
        self._validate_commitment_refs(commitment, authority_state)
        self._validate_commitment_transition(
            self.commitments[commitment.id], commitment
        )
        self.commitments[commitment.id] = commitment

    @staticmethod
    def _validate_commitment_transition(
        current: InstitutionalCommitment,
        replacement: InstitutionalCommitment,
    ) -> None:
        if (
            replacement.party_ids != current.party_ids
            or replacement.opened_month != current.opened_month
            or replacement.origin_event_id != current.origin_event_id
            or tuple(term.id for term in replacement.terms)
            != tuple(term.id for term in current.terms)
        ):
            raise ValueError("commitment identity, parties, and term set are immutable")
        if (
            current.closed_month is not None
            and replacement.closed_month != current.closed_month
        ):
            raise ValueError("closed commitments cannot be reopened or reclosed")
        for old_term, new_term in zip(current.terms, replacement.terms, strict=True):
            InstitutionalRelationsState._validate_term_transition(old_term, new_term)

    @staticmethod
    def _validate_term_transition(
        current: CommitmentTerm, replacement: CommitmentTerm
    ) -> None:
        immutable = (
            "id",
            "index",
            "kind",
            "obligor_institution_id",
            "beneficiary_institution_id",
            "subject",
            "proposed_month",
            "due_month",
            "parameters",
        )
        if any(
            getattr(current, name) != getattr(replacement, name) for name in immutable
        ):
            raise ValueError("accepted commitment term parameters are immutable")
        if replacement.status not in _TERM_TRANSITIONS[current.status]:
            raise ValueError(
                f"invalid commitment term transition: {current.status.value} -> "
                f"{replacement.status.value}"
            )
        if not set(current.evidence_event_ids).issubset(replacement.evidence_event_ids):
            raise ValueError("commitment term evidence is append-only")
        if not set(current.breach_event_ids).issubset(replacement.breach_event_ids):
            raise ValueError("commitment breach history is append-only")
        if current.breached_month is not None and (
            replacement.breached_month != current.breached_month
        ):
            raise ValueError("commitment breach month is immutable once recorded")
        if current.remediation_of_term_id is not None and (
            replacement.remediation_of_term_id != current.remediation_of_term_id
        ):
            raise ValueError(
                "commitment remediation reference is immutable once recorded"
            )

    def replace_memory(
        self,
        memory: InstitutionalMemory,
        knowledge_state: InstitutionalKnowledgeState,
        authority_state: InstitutionalAuthorityState,
    ) -> None:
        if not isinstance(memory, InstitutionalMemory):
            raise TypeError("memory must be an InstitutionalMemory")
        if memory.id not in self.memories:
            raise KeyError(f"unknown memory: {memory.id}")
        self._require_institutions(authority_state, (memory.institution_id,))
        if not isinstance(
            knowledge_state, InstitutionalKnowledgeState
        ) or not knowledge_state.contains(memory.institution_id, memory.event_id):
            raise ValueError(
                "institutional memory requires known fact: "
                f"{memory.institution_id}/{memory.event_id}"
            )
        self.memories[memory.id] = memory

    def replace_recognition(
        self,
        recognition: RecognitionRecord,
        authority_state: InstitutionalAuthorityState,
    ) -> None:
        if not isinstance(recognition, RecognitionRecord):
            raise TypeError("recognition must be a RecognitionRecord")
        if recognition.id not in self.recognitions:
            raise KeyError(f"unknown recognition: {recognition.id}")
        self._require_institutions(
            authority_state, (recognition.recognizer_institution_id,)
        )
        if authority_state.get_claim(recognition.claim_id) is None:
            raise ValueError(
                f"recognition references unknown claim: {recognition.claim_id}"
            )
        self.recognitions[recognition.id] = recognition

    def get_relation(
        self, institution_a_id: str, institution_b_id: str
    ) -> InstitutionalRelation | None:
        return self.relations.get(
            InstitutionalRelation.id_for(institution_a_id, institution_b_id)
        )

    def commitments_for(
        self, institution_id: str
    ) -> tuple[InstitutionalCommitment, ...]:
        return tuple(
            sorted(
                (
                    commitment
                    for commitment in self.commitments.values()
                    if institution_id in commitment.party_ids
                ),
                key=lambda commitment: commitment.id,
            )
        )

    def memories_for(self, institution_id: str) -> tuple[InstitutionalMemory, ...]:
        return tuple(
            sorted(
                (
                    memory
                    for memory in self.memories.values()
                    if memory.institution_id == institution_id
                ),
                key=lambda memory: memory.id,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "relations": {
                key: self.relations[key].to_dict() for key in sorted(self.relations)
            },
            "commitments": {
                key: self.commitments[key].to_dict() for key in sorted(self.commitments)
            },
            "memories": {
                key: self.memories[key].to_dict() for key in sorted(self.memories)
            },
            "recognitions": {
                key: self.recognitions[key].to_dict()
                for key in sorted(self.recognitions)
            },
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        authority_state: InstitutionalAuthorityState,
        knowledge_state: InstitutionalKnowledgeState,
    ) -> "InstitutionalRelationsState":
        raw = _strict_payload(data)
        relations = _registry(
            raw["relations"], InstitutionalRelation.from_dict, "relations"
        )
        commitments = _registry(
            raw["commitments"], InstitutionalCommitment.from_dict, "commitments"
        )
        memories = _registry(raw["memories"], InstitutionalMemory.from_dict, "memories")
        recognitions = _registry(
            raw["recognitions"], RecognitionRecord.from_dict, "recognitions"
        )
        state = cls(model_version=raw["model_version"])
        for relation in relations.values():
            state.add_relation(relation, authority_state)
        for commitment in commitments.values():
            state.add_commitment(commitment, authority_state)
        for memory in memories.values():
            state.add_memory(memory, knowledge_state, authority_state)
        for recognition in recognitions.values():
            state.add_recognition(recognition, authority_state)
        return state


__all__ = ["InstitutionalRelationsState"]

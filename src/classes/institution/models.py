"""Frozen institutional value objects.

This module contains vocabulary and validation only.  It deliberately does
not import world/domain owners: references crossing domains are EntityRefs or
stable IDs, and canonical systems remain responsible for execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import math
from numbers import Real
from typing import Any

from src.classes.mechanical_language import EntityRef


INSTITUTION_MODEL_VERSION = 1


class InstitutionKind(StrEnum):
    DYNASTY = "dynasty"
    SECT = "sect"
    CITY = "city"


class AuthorityScope(StrEnum):
    URBAN_ADMINISTRATION = "urban_administration"
    RESOURCE_DISPOSITION = "resource_disposition"
    TREASURY_DISPOSITION = "treasury_disposition"
    COMMITMENT_NEGOTIATION = "commitment_negotiation"
    RECOGNITION = "recognition"
    FORCE_EMPLOYMENT = "force_employment"
    # Internal administration of an organization's own membership and the
    # standing it grants its members. Deliberately not `RECOGNITION`:
    # endorsing a public rite says nothing about who may end a membership or
    # replace what a member was taught.
    SECT_ADMINISTRATION = "sect_administration"


class AuthorityClaimStatus(StrEnum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    DEFEATED = "defeated"
    EXPIRED = "expired"


class RecognitionStance(StrEnum):
    RECOGNIZE = "recognize"
    REJECT = "reject"
    ABSTAIN = "abstain"


class InstitutionalRelationKind(StrEnum):
    NEUTRAL = "neutral"
    ALLIED = "allied"
    HOSTILE = "hostile"
    AT_WAR = "at_war"


class CommitmentTermKind(StrEnum):
    RESOURCE_TRANSFER = "resource_transfer"
    URBAN_PROJECT = "urban_project"
    NON_AGGRESSION = "non_aggression"
    RECOGNITION = "recognition"


class CommitmentTermStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    FULFILLED = "fulfilled"
    BREACHED = "breached"
    REMEDIATION_PROPOSED = "remediation_proposed"
    REMEDIATED = "remediated"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CommitmentAggregateStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    BREACHED = "breached"
    FULFILLED = "fulfilled"
    CLOSED = "closed"


class IdentityAnchorKind(StrEnum):
    FOUNDER = "founder"
    HEADQUARTERS = "headquarters"
    CORE_RELIC = "core_relic"
    SACRED_SITE = "sacred_site"
    FOUNDING_COMMITMENT = "founding_commitment"


class KnowledgeChannel(StrEnum):
    OWN_ACTION = "own_action"
    MEMBER_WITNESS = "member_witness"
    FORMAL_NOTICE = "formal_notice"
    PUBLIC_FACT = "public_fact"


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _month(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _optional_month(value: Any, name: str) -> int | None:
    return None if value is None else _month(value, name)


def _enum(value: Any, enum_type: type[StrEnum], name: str) -> StrEnum:
    if not isinstance(value, enum_type):
        raise ValueError(f"{name} must be a {enum_type.__name__}")
    return value


def _entity(
    value: Any, name: str, *, kinds: tuple[str, ...] | None = None
) -> EntityRef:
    if not isinstance(value, EntityRef):
        raise ValueError(f"{name} must be an EntityRef")
    _id(value.kind, f"{name}.kind")
    _id(value.id, f"{name}.id")
    if kinds is not None and value.kind not in kinds:
        raise ValueError(f"{name}.kind must be one of {kinds}")
    return value


def _ids(value: Any, name: str, *, nonempty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple")
    result = tuple(_id(item, f"{name} item") for item in value)
    if nonempty and not result:
        raise ValueError(f"{name} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _scopes(value: Any) -> tuple[AuthorityScope, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("scopes must be a non-empty list or tuple")
    scopes = tuple(_enum(item, AuthorityScope, "scope") for item in value)
    if len(set(scopes)) != len(scopes):
        raise ValueError("scopes must not contain duplicates")
    return tuple(sorted(scopes, key=lambda item: item.value))


def _number(value: Any, name: str, *, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def _scalar(value: Any, name: str) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        return value
    raise ValueError(f"{name} must be a JSON scalar")


def _parameters(value: Any) -> tuple[tuple[str, str | int | float | bool | None], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("parameters must be a list or tuple of pairs")
    result = []
    for pair in value:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("parameters must contain key/value pairs")
        result.append(
            (_id(pair[0], "parameter key"), _scalar(pair[1], "parameter value"))
        )
    result.sort(key=lambda item: item[0])
    if len({key for key, _ in result}) != len(result):
        raise ValueError("parameters must not contain duplicate keys")
    return tuple(result)


def _checked_id(value: str, expected: str, name: str = "id") -> str:
    value = _id(value, name)
    if value != expected:
        raise ValueError(f"{name} does not match its canonical value")
    return value


def _payload(data: Any, keys: set[str], name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TypeError(f"{name} must be a mapping")
    actual = set(data)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise ValueError(f"invalid {name} keys; missing={missing}, extra={extra}")
    return data


def _entity_from_dict(data: Any, name: str) -> EntityRef:
    payload = _payload(data, {"kind", "id"}, name)
    return EntityRef.from_dict(payload)


@dataclass(frozen=True, slots=True)
class Institution:
    kind: InstitutionKind
    owner_ref: EntityRef
    founded_month: int
    dissolved_month: int | None = None
    id: str = field(default="")

    @staticmethod
    def id_for(kind: InstitutionKind, owner_ref: EntityRef) -> str:
        return f"inst:{kind.value}:{owner_ref.id}"

    def __post_init__(self) -> None:
        kind = _enum(self.kind, InstitutionKind, "kind")
        owner_kinds = {
            InstitutionKind.DYNASTY: ("dynasty",),
            InstitutionKind.SECT: ("sect",),
            InstitutionKind.CITY: ("region",),
        }
        owner = _entity(self.owner_ref, "owner_ref", kinds=owner_kinds[kind])
        founded = _month(self.founded_month, "founded_month")
        dissolved = _optional_month(self.dissolved_month, "dissolved_month")
        if dissolved is not None and dissolved < founded:
            raise ValueError("dissolved_month must not precede founded_month")
        expected = self.id_for(kind, owner)
        object.__setattr__(
            self, "id", _checked_id(self.id, expected) if self.id else expected
        )
        object.__setattr__(self, "founded_month", founded)
        object.__setattr__(self, "dissolved_month", dissolved)

    def is_active(self, month: int) -> bool:
        current = _month(month, "month")
        return self.founded_month <= current and (
            self.dissolved_month is None or current < self.dissolved_month
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "owner_ref": self.owner_ref.to_dict(),
            "founded_month": self.founded_month,
            "dissolved_month": self.dissolved_month,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Institution":
        data = _payload(
            data,
            {"id", "kind", "owner_ref", "founded_month", "dissolved_month"},
            "Institution",
        )
        return cls(
            kind=InstitutionKind(data["kind"]),
            owner_ref=_entity_from_dict(data["owner_ref"], "Institution.owner_ref"),
            founded_month=data["founded_month"],
            dissolved_month=data["dissolved_month"],
            id=data["id"],
        )


@dataclass(frozen=True, slots=True)
class InstitutionalOffice:
    institution_id: str
    office_key: str
    scopes: tuple[AuthorityScope, ...]
    holder_ref: EntityRef | None = None
    holder_since_month: int | None = None
    id: str = field(default="")

    def __post_init__(self) -> None:
        institution_id = _id(self.institution_id, "institution_id")
        office_key = _id(self.office_key, "office_key")
        holder = (
            None
            if self.holder_ref is None
            else _entity(self.holder_ref, "holder_ref", kinds=("avatar",))
        )
        holder_since = _optional_month(self.holder_since_month, "holder_since_month")
        if (holder is None) != (holder_since is None):
            raise ValueError(
                "holder_ref and holder_since_month must be provided together"
            )
        object.__setattr__(self, "institution_id", institution_id)
        object.__setattr__(self, "office_key", office_key)
        object.__setattr__(self, "scopes", _scopes(self.scopes))
        object.__setattr__(self, "holder_ref", holder)
        object.__setattr__(self, "holder_since_month", holder_since)
        expected = f"office:{institution_id}:{office_key}"
        object.__setattr__(
            self, "id", _checked_id(self.id, expected) if self.id else expected
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "office_key": self.office_key,
            "scopes": [item.value for item in self.scopes],
            "holder_ref": self.holder_ref.to_dict() if self.holder_ref else None,
            "holder_since_month": self.holder_since_month,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstitutionalOffice":
        data = _payload(
            data,
            {
                "id",
                "institution_id",
                "office_key",
                "scopes",
                "holder_ref",
                "holder_since_month",
            },
            "InstitutionalOffice",
        )
        return cls(
            institution_id=data["institution_id"],
            office_key=data["office_key"],
            scopes=tuple(AuthorityScope(item) for item in data["scopes"]),
            holder_ref=(
                _entity_from_dict(data["holder_ref"], "InstitutionalOffice.holder_ref")
                if data["holder_ref"] is not None
                else None
            ),
            holder_since_month=data["holder_since_month"],
            id=data["id"],
        )


@dataclass(frozen=True, slots=True)
class AuthorityClaim:
    office_id: str
    claimant_ref: EntityRef
    opened_month: int
    status: AuthorityClaimStatus
    evidence_event_ids: tuple[str, ...]
    source_kind: str
    source_ref: EntityRef | None = None
    closed_month: int | None = None
    closed_event_id: str | None = None
    id: str = field(default="")

    def __post_init__(self) -> None:
        office_id = _id(self.office_id, "office_id")
        claimant = _entity(self.claimant_ref, "claimant_ref", kinds=("avatar",))
        opened = _month(self.opened_month, "opened_month")
        status = _enum(self.status, AuthorityClaimStatus, "status")
        evidence = _ids(self.evidence_event_ids, "evidence_event_ids")
        source_kind = _id(self.source_kind, "source_kind")
        source_ref = (
            None if self.source_ref is None else _entity(self.source_ref, "source_ref")
        )
        closed_month = _optional_month(self.closed_month, "closed_month")
        closed_event_id = (
            None
            if self.closed_event_id is None
            else _id(self.closed_event_id, "closed_event_id")
        )
        if status is AuthorityClaimStatus.ACTIVE:
            if closed_month is not None or closed_event_id is not None:
                raise ValueError("active claims cannot have closing fields")
        elif closed_month is None or closed_event_id is None:
            raise ValueError("closed claims require closed_month and closed_event_id")
        if closed_month is not None and closed_month < opened:
            raise ValueError("closed_month must not precede opened_month")
        for name, value in (
            ("office_id", office_id),
            ("opened_month", opened),
            ("status", status),
            ("evidence_event_ids", evidence),
            ("source_kind", source_kind),
            ("source_ref", source_ref),
            ("closed_month", closed_month),
            ("closed_event_id", closed_event_id),
            ("claimant_ref", claimant),
        ):
            object.__setattr__(self, name, value)
        expected = f"claim:{office_id}:{claimant.id}:{opened}"
        object.__setattr__(
            self, "id", _checked_id(self.id, expected) if self.id else expected
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "office_id": self.office_id,
            "claimant_ref": self.claimant_ref.to_dict(),
            "opened_month": self.opened_month,
            "status": self.status.value,
            "evidence_event_ids": list(self.evidence_event_ids),
            "source_kind": self.source_kind,
            "source_ref": self.source_ref.to_dict() if self.source_ref else None,
            "closed_month": self.closed_month,
            "closed_event_id": self.closed_event_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthorityClaim":
        data = _payload(
            data,
            {
                "id",
                "office_id",
                "claimant_ref",
                "opened_month",
                "status",
                "evidence_event_ids",
                "source_kind",
                "source_ref",
                "closed_month",
                "closed_event_id",
            },
            "AuthorityClaim",
        )
        return cls(
            office_id=data["office_id"],
            claimant_ref=_entity_from_dict(
                data["claimant_ref"], "AuthorityClaim.claimant_ref"
            ),
            opened_month=data["opened_month"],
            status=AuthorityClaimStatus(data["status"]),
            evidence_event_ids=tuple(data["evidence_event_ids"]),
            source_kind=data["source_kind"],
            source_ref=(
                _entity_from_dict(data["source_ref"], "AuthorityClaim.source_ref")
                if data["source_ref"] is not None
                else None
            ),
            closed_month=data["closed_month"],
            closed_event_id=data["closed_event_id"],
            id=data["id"],
        )


@dataclass(frozen=True, slots=True)
class InstitutionalRelation:
    institution_a_id: str
    institution_b_id: str
    kind: InstitutionalRelationKind
    friendliness: int
    since_month: int
    evidence_event_ids: tuple[str, ...]
    id: str = field(default="")

    @staticmethod
    def id_for(institution_a_id: str, institution_b_id: str) -> str:
        first, second = sorted(
            (
                _id(institution_a_id, "institution_a_id"),
                _id(institution_b_id, "institution_b_id"),
            )
        )
        if first == second:
            raise ValueError("relation institutions must be distinct")
        return f"relation:{first}:{second}"

    def __post_init__(self) -> None:
        first, second = (
            _id(self.institution_a_id, "institution_a_id"),
            _id(self.institution_b_id, "institution_b_id"),
        )
        if first == second:
            raise ValueError("relation institutions must be distinct")
        if first > second:
            raise ValueError("relation institution IDs must be normalized")
        kind = _enum(self.kind, InstitutionalRelationKind, "kind")
        if (
            isinstance(self.friendliness, bool)
            or not isinstance(self.friendliness, int)
            or not -100 <= self.friendliness <= 100
        ):
            raise ValueError("friendliness must be an integer between -100 and 100")
        since = _month(self.since_month, "since_month")
        evidence = _ids(
            self.evidence_event_ids,
            "evidence_event_ids",
            nonempty=kind is not InstitutionalRelationKind.NEUTRAL,
        )
        object.__setattr__(self, "institution_a_id", first)
        object.__setattr__(self, "institution_b_id", second)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "since_month", since)
        object.__setattr__(self, "evidence_event_ids", evidence)
        expected = self.id_for(first, second)
        object.__setattr__(
            self, "id", _checked_id(self.id, expected) if self.id else expected
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "institution_a_id": self.institution_a_id,
            "institution_b_id": self.institution_b_id,
            "kind": self.kind.value,
            "friendliness": self.friendliness,
            "since_month": self.since_month,
            "evidence_event_ids": list(self.evidence_event_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstitutionalRelation":
        data = _payload(
            data,
            {
                "id",
                "institution_a_id",
                "institution_b_id",
                "kind",
                "friendliness",
                "since_month",
                "evidence_event_ids",
            },
            "InstitutionalRelation",
        )
        return cls(
            institution_a_id=data["institution_a_id"],
            institution_b_id=data["institution_b_id"],
            kind=InstitutionalRelationKind(data["kind"]),
            friendliness=data["friendliness"],
            since_month=data["since_month"],
            evidence_event_ids=tuple(data["evidence_event_ids"]),
            id=data["id"],
        )


@dataclass(frozen=True, slots=True)
class CommitmentTerm:
    id: str
    index: int
    kind: CommitmentTermKind
    obligor_institution_id: str
    beneficiary_institution_id: str
    subject: EntityRef
    status: CommitmentTermStatus
    proposed_month: int
    due_month: int | None = None
    breached_month: int | None = None
    resolved_month: int | None = None
    parameters: tuple[tuple[str, str | int | float | bool | None], ...] = ()
    evidence_event_ids: tuple[str, ...] = ()
    breach_event_ids: tuple[str, ...] = ()
    remediation_of_term_id: str | None = None

    def __post_init__(self) -> None:
        term_id = _id(self.id, "id")
        if (
            isinstance(self.index, bool)
            or not isinstance(self.index, int)
            or self.index < 0
        ):
            raise ValueError("index must be a zero-based non-negative integer")
        kind = _enum(self.kind, CommitmentTermKind, "kind")
        obligor, beneficiary = (
            _id(self.obligor_institution_id, "obligor_institution_id"),
            _id(self.beneficiary_institution_id, "beneficiary_institution_id"),
        )
        if obligor == beneficiary:
            raise ValueError("term institutions must be distinct")
        subject_kinds = {
            CommitmentTermKind.RESOURCE_TRANSFER: ("resource",),
            CommitmentTermKind.URBAN_PROJECT: ("region",),
            CommitmentTermKind.NON_AGGRESSION: ("institution",),
            CommitmentTermKind.RECOGNITION: ("claim",),
        }
        subject = _entity(self.subject, "subject", kinds=subject_kinds[kind])
        status = _enum(self.status, CommitmentTermStatus, "status")
        proposed = _month(self.proposed_month, "proposed_month")
        due = _optional_month(self.due_month, "due_month")
        breached = _optional_month(self.breached_month, "breached_month")
        resolved = _optional_month(self.resolved_month, "resolved_month")
        if due is not None and due < proposed:
            raise ValueError("due_month must not precede proposed_month")
        if breached is not None and breached < proposed:
            raise ValueError("breached_month must not precede proposed_month")
        if resolved is not None and resolved < proposed:
            raise ValueError("resolved_month must not precede proposed_month")
        if resolved is not None and breached is not None and resolved < breached:
            raise ValueError("resolved_month must not precede breached_month")
        evidence = _ids(self.evidence_event_ids, "evidence_event_ids")
        breaches = _ids(self.breach_event_ids, "breach_event_ids", nonempty=False)
        resolved_statuses = {
            CommitmentTermStatus.FULFILLED,
            CommitmentTermStatus.REMEDIATED,
            CommitmentTermStatus.CANCELLED,
            CommitmentTermStatus.EXPIRED,
        }
        if (status in resolved_statuses) != (resolved is not None):
            raise ValueError("resolved_month exists exactly for resolved term statuses")
        breach_statuses = {
            CommitmentTermStatus.BREACHED,
            CommitmentTermStatus.REMEDIATION_PROPOSED,
            CommitmentTermStatus.REMEDIATED,
        }
        if status in breach_statuses and (breached is None or not breaches):
            raise ValueError("breach and remediation statuses require breach history")
        if (breached is None) != (not breaches):
            raise ValueError(
                "breached_month and breach_event_ids must be present together"
            )
        if status in {
            CommitmentTermStatus.PROPOSED,
            CommitmentTermStatus.ACTIVE,
            CommitmentTermStatus.FULFILLED,
        } and (breached is not None or breaches):
            raise ValueError("unbreached statuses cannot carry breach history")
        parameters = _parameters(self.parameters)
        parameter_map = dict(parameters)
        if kind is CommitmentTermKind.RESOURCE_TRANSFER:
            amount = parameter_map.get("amount")
            if (
                isinstance(amount, bool)
                or not isinstance(amount, Real)
                or not math.isfinite(float(amount))
                or float(amount) <= 0
            ):
                raise ValueError("resource transfer terms require a positive amount")
        remediation = (
            None
            if self.remediation_of_term_id is None
            else _id(self.remediation_of_term_id, "remediation_of_term_id")
        )
        if remediation is not None and status not in {
            CommitmentTermStatus.BREACHED,
            CommitmentTermStatus.REMEDIATION_PROPOSED,
            CommitmentTermStatus.REMEDIATED,
        }:
            raise ValueError(
                "remediation reference is only valid for remediation statuses"
            )
        for name, value in (
            ("id", term_id),
            ("index", self.index),
            ("kind", kind),
            ("obligor_institution_id", obligor),
            ("beneficiary_institution_id", beneficiary),
            ("subject", subject),
            ("status", status),
            ("proposed_month", proposed),
            ("due_month", due),
            ("breached_month", breached),
            ("resolved_month", resolved),
            ("parameters", parameters),
            ("evidence_event_ids", evidence),
            ("breach_event_ids", breaches),
            ("remediation_of_term_id", remediation),
        ):
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "kind": self.kind.value,
            "obligor_institution_id": self.obligor_institution_id,
            "beneficiary_institution_id": self.beneficiary_institution_id,
            "subject": self.subject.to_dict(),
            "status": self.status.value,
            "proposed_month": self.proposed_month,
            "due_month": self.due_month,
            "breached_month": self.breached_month,
            "resolved_month": self.resolved_month,
            "parameters": [[key, value] for key, value in self.parameters],
            "evidence_event_ids": list(self.evidence_event_ids),
            "breach_event_ids": list(self.breach_event_ids),
            "remediation_of_term_id": self.remediation_of_term_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommitmentTerm":
        data = _payload(
            data,
            {
                "id",
                "index",
                "kind",
                "obligor_institution_id",
                "beneficiary_institution_id",
                "subject",
                "status",
                "proposed_month",
                "due_month",
                "breached_month",
                "resolved_month",
                "parameters",
                "evidence_event_ids",
                "breach_event_ids",
                "remediation_of_term_id",
            },
            "CommitmentTerm",
        )
        return cls(
            id=data["id"],
            index=data["index"],
            kind=CommitmentTermKind(data["kind"]),
            obligor_institution_id=data["obligor_institution_id"],
            beneficiary_institution_id=data["beneficiary_institution_id"],
            subject=_entity_from_dict(data["subject"], "CommitmentTerm.subject"),
            status=CommitmentTermStatus(data["status"]),
            proposed_month=data["proposed_month"],
            due_month=data["due_month"],
            breached_month=data["breached_month"],
            resolved_month=data["resolved_month"],
            parameters=tuple(tuple(pair) for pair in data["parameters"]),
            evidence_event_ids=tuple(data["evidence_event_ids"]),
            breach_event_ids=tuple(data["breach_event_ids"]),
            remediation_of_term_id=data["remediation_of_term_id"],
        )


@dataclass(frozen=True, slots=True)
class InstitutionalCommitment:
    party_ids: tuple[str, ...]
    opened_month: int
    terms: tuple[CommitmentTerm, ...]
    origin_event_id: str
    closed_month: int | None = None
    id: str = field(default="")

    def __post_init__(self) -> None:
        parties = tuple(sorted(_ids(self.party_ids, "party_ids")))
        if len(parties) < 2:
            raise ValueError("commitment requires at least two parties")
        opened = _month(self.opened_month, "opened_month")
        if not isinstance(self.terms, (list, tuple)) or not self.terms:
            raise ValueError("commitment requires at least one term")
        terms = tuple(self.terms)
        if any(not isinstance(term, CommitmentTerm) for term in terms):
            raise ValueError("terms must contain CommitmentTerm values")
        if tuple(term.index for term in terms) != tuple(range(len(terms))):
            raise ValueError("term indexes must be contiguous and zero-based")
        if len({term.id for term in terms}) != len(terms):
            raise ValueError("commitment term IDs must be unique")
        for term in terms:
            if (
                term.obligor_institution_id not in parties
                or term.beneficiary_institution_id not in parties
            ):
                raise ValueError("term institutions must belong to commitment parties")
        origin = _id(self.origin_event_id, "origin_event_id")
        terminal = {
            CommitmentTermStatus.FULFILLED,
            CommitmentTermStatus.REMEDIATED,
            CommitmentTermStatus.CANCELLED,
            CommitmentTermStatus.EXPIRED,
        }
        closed = _optional_month(self.closed_month, "closed_month")
        all_closed = all(term.status in terminal for term in terms)
        if (closed is None) != (not all_closed):
            raise ValueError("closed_month exists exactly when all terms are terminal")
        if closed is not None and closed < opened:
            raise ValueError("closed_month must not precede opened_month")
        object.__setattr__(self, "party_ids", parties)
        object.__setattr__(self, "opened_month", opened)
        object.__setattr__(self, "terms", terms)
        object.__setattr__(self, "origin_event_id", origin)
        object.__setattr__(self, "closed_month", closed)
        expected = f"commitment:{origin}"
        object.__setattr__(
            self, "id", _checked_id(self.id, expected) if self.id else expected
        )

    @property
    def aggregate_status(self) -> CommitmentAggregateStatus:
        statuses = {term.status for term in self.terms}
        if CommitmentTermStatus.BREACHED in statuses:
            return CommitmentAggregateStatus.BREACHED
        if statuses & {
            CommitmentTermStatus.ACTIVE,
            CommitmentTermStatus.REMEDIATION_PROPOSED,
        }:
            return CommitmentAggregateStatus.ACTIVE
        if CommitmentTermStatus.PROPOSED in statuses:
            return CommitmentAggregateStatus.PROPOSED
        if statuses and statuses <= {
            CommitmentTermStatus.FULFILLED,
            CommitmentTermStatus.REMEDIATED,
        }:
            return CommitmentAggregateStatus.FULFILLED
        return CommitmentAggregateStatus.CLOSED

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "party_ids": list(self.party_ids),
            "opened_month": self.opened_month,
            "terms": [term.to_dict() for term in self.terms],
            "origin_event_id": self.origin_event_id,
            "closed_month": self.closed_month,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstitutionalCommitment":
        data = _payload(
            data,
            {
                "id",
                "party_ids",
                "opened_month",
                "terms",
                "origin_event_id",
                "closed_month",
            },
            "InstitutionalCommitment",
        )
        return cls(
            party_ids=tuple(data["party_ids"]),
            opened_month=data["opened_month"],
            terms=tuple(CommitmentTerm.from_dict(term) for term in data["terms"]),
            origin_event_id=data["origin_event_id"],
            closed_month=data["closed_month"],
            id=data["id"],
        )


@dataclass(frozen=True, slots=True)
class InstitutionalMemory:
    institution_id: str
    event_id: str
    salience: float
    recorded_month: int
    last_reinforced_month: int
    factors: tuple[tuple[str, float], ...]
    id: str = field(default="")

    def __post_init__(self) -> None:
        institution, event = (
            _id(self.institution_id, "institution_id"),
            _id(self.event_id, "event_id"),
        )
        salience = _number(self.salience, "salience", low=0.0, high=1.0)
        recorded, reinforced = (
            _month(self.recorded_month, "recorded_month"),
            _month(self.last_reinforced_month, "last_reinforced_month"),
        )
        if reinforced < recorded:
            raise ValueError("last_reinforced_month must not precede recorded_month")
        if not isinstance(self.factors, (list, tuple)):
            raise ValueError("factors must be a list or tuple of pairs")
        allowed = {
            "relative_scale",
            "institutional_change",
            "commitment_breach",
            "identity_anchor_impact",
        }
        normalized = []
        for pair in self.factors:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError("factors must contain key/value pairs")
            key = _id(pair[0], "factor key")
            if key not in allowed:
                raise ValueError("factor is not allowed")
            normalized.append(
                (key, _number(pair[1], f"factor {key}", low=0.0, high=1.0))
            )
        normalized.sort(key=lambda item: item[0])
        if len({key for key, _ in normalized}) != len(normalized):
            raise ValueError("factors must not contain duplicates")
        object.__setattr__(self, "institution_id", institution)
        object.__setattr__(self, "event_id", event)
        object.__setattr__(self, "salience", salience)
        object.__setattr__(self, "recorded_month", recorded)
        object.__setattr__(self, "last_reinforced_month", reinforced)
        object.__setattr__(self, "factors", tuple(normalized))
        expected = f"memory:{institution}:{event}"
        object.__setattr__(
            self, "id", _checked_id(self.id, expected) if self.id else expected
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "event_id": self.event_id,
            "salience": self.salience,
            "recorded_month": self.recorded_month,
            "last_reinforced_month": self.last_reinforced_month,
            "factors": [[key, value] for key, value in self.factors],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstitutionalMemory":
        data = _payload(
            data,
            {
                "id",
                "institution_id",
                "event_id",
                "salience",
                "recorded_month",
                "last_reinforced_month",
                "factors",
            },
            "InstitutionalMemory",
        )
        return cls(
            institution_id=data["institution_id"],
            event_id=data["event_id"],
            salience=data["salience"],
            recorded_month=data["recorded_month"],
            last_reinforced_month=data["last_reinforced_month"],
            factors=tuple(tuple(pair) for pair in data["factors"]),
            id=data["id"],
        )


@dataclass(frozen=True, slots=True)
class InstitutionalIdentityAnchor:
    institution_id: str
    kind: IdentityAnchorKind
    subject: EntityRef
    established_month: int
    evidence_event_ids: tuple[str, ...]
    id: str = field(default="")

    def __post_init__(self) -> None:
        institution = _id(self.institution_id, "institution_id")
        kind = _enum(self.kind, IdentityAnchorKind, "kind")
        expected_kinds = {
            IdentityAnchorKind.FOUNDER: ("avatar",),
            IdentityAnchorKind.HEADQUARTERS: ("region",),
            IdentityAnchorKind.SACRED_SITE: ("region",),
            IdentityAnchorKind.CORE_RELIC: ("item",),
            IdentityAnchorKind.FOUNDING_COMMITMENT: ("commitment",),
        }
        subject = _entity(self.subject, "subject", kinds=expected_kinds[kind])
        established = _month(self.established_month, "established_month")
        evidence = _ids(self.evidence_event_ids, "evidence_event_ids")
        object.__setattr__(self, "institution_id", institution)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "established_month", established)
        object.__setattr__(self, "evidence_event_ids", evidence)
        expected = f"anchor:{institution}:{kind.value}:{subject.kind}:{subject.id}"
        object.__setattr__(
            self, "id", _checked_id(self.id, expected) if self.id else expected
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "kind": self.kind.value,
            "subject": self.subject.to_dict(),
            "established_month": self.established_month,
            "evidence_event_ids": list(self.evidence_event_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstitutionalIdentityAnchor":
        data = _payload(
            data,
            {
                "id",
                "institution_id",
                "kind",
                "subject",
                "established_month",
                "evidence_event_ids",
            },
            "InstitutionalIdentityAnchor",
        )
        return cls(
            institution_id=data["institution_id"],
            kind=IdentityAnchorKind(data["kind"]),
            subject=_entity_from_dict(
                data["subject"], "InstitutionalIdentityAnchor.subject"
            ),
            established_month=data["established_month"],
            evidence_event_ids=tuple(data["evidence_event_ids"]),
            id=data["id"],
        )


@dataclass(frozen=True, slots=True)
class RecognitionRecord:
    recognizer_institution_id: str
    claim_id: str
    stance: RecognitionStance
    since_month: int
    evidence_event_ids: tuple[str, ...]
    id: str = field(default="")

    def __post_init__(self) -> None:
        recognizer, claim = (
            _id(self.recognizer_institution_id, "recognizer_institution_id"),
            _id(self.claim_id, "claim_id"),
        )
        stance = _enum(self.stance, RecognitionStance, "stance")
        since = _month(self.since_month, "since_month")
        evidence = _ids(self.evidence_event_ids, "evidence_event_ids")
        object.__setattr__(self, "recognizer_institution_id", recognizer)
        object.__setattr__(self, "claim_id", claim)
        object.__setattr__(self, "stance", stance)
        object.__setattr__(self, "since_month", since)
        object.__setattr__(self, "evidence_event_ids", evidence)
        expected = f"recognition:{recognizer}:{claim}"
        object.__setattr__(
            self, "id", _checked_id(self.id, expected) if self.id else expected
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "recognizer_institution_id": self.recognizer_institution_id,
            "claim_id": self.claim_id,
            "stance": self.stance.value,
            "since_month": self.since_month,
            "evidence_event_ids": list(self.evidence_event_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecognitionRecord":
        data = _payload(
            data,
            {
                "id",
                "recognizer_institution_id",
                "claim_id",
                "stance",
                "since_month",
                "evidence_event_ids",
            },
            "RecognitionRecord",
        )
        return cls(
            recognizer_institution_id=data["recognizer_institution_id"],
            claim_id=data["claim_id"],
            stance=RecognitionStance(data["stance"]),
            since_month=data["since_month"],
            evidence_event_ids=tuple(data["evidence_event_ids"]),
            id=data["id"],
        )


@dataclass(frozen=True, slots=True)
class InstitutionalFactKnowledge:
    institution_id: str
    event_id: str
    learned_month: int
    channel: KnowledgeChannel
    learned_from_event_id: str
    id: str = field(default="")

    @staticmethod
    def id_for(institution_id: str, event_id: str) -> str:
        return f"knowledge:{_id(institution_id, 'institution_id')}:{_id(event_id, 'event_id')}"

    def __post_init__(self) -> None:
        institution, event = (
            _id(self.institution_id, "institution_id"),
            _id(self.event_id, "event_id"),
        )
        learned = _month(self.learned_month, "learned_month")
        channel = _enum(self.channel, KnowledgeChannel, "channel")
        learned_from = _id(self.learned_from_event_id, "learned_from_event_id")
        object.__setattr__(self, "institution_id", institution)
        object.__setattr__(self, "event_id", event)
        object.__setattr__(self, "learned_month", learned)
        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "learned_from_event_id", learned_from)
        expected = self.id_for(institution, event)
        object.__setattr__(
            self, "id", _checked_id(self.id, expected) if self.id else expected
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "event_id": self.event_id,
            "learned_month": self.learned_month,
            "channel": self.channel.value,
            "learned_from_event_id": self.learned_from_event_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstitutionalFactKnowledge":
        data = _payload(
            data,
            {
                "id",
                "institution_id",
                "event_id",
                "learned_month",
                "channel",
                "learned_from_event_id",
            },
            "InstitutionalFactKnowledge",
        )
        return cls(
            institution_id=data["institution_id"],
            event_id=data["event_id"],
            learned_month=data["learned_month"],
            channel=KnowledgeChannel(data["channel"]),
            learned_from_event_id=data["learned_from_event_id"],
            id=data["id"],
        )


__all__ = [
    "INSTITUTION_MODEL_VERSION",
    "InstitutionKind",
    "AuthorityScope",
    "AuthorityClaimStatus",
    "RecognitionStance",
    "InstitutionalRelationKind",
    "CommitmentTermKind",
    "CommitmentTermStatus",
    "CommitmentAggregateStatus",
    "IdentityAnchorKind",
    "KnowledgeChannel",
    "Institution",
    "InstitutionalOffice",
    "AuthorityClaim",
    "InstitutionalRelation",
    "CommitmentTerm",
    "InstitutionalCommitment",
    "InstitutionalMemory",
    "InstitutionalIdentityAnchor",
    "RecognitionRecord",
    "InstitutionalFactKnowledge",
]

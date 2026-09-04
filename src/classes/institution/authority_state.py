"""World-independent authority state for institutional claims."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from .models import (
    INSTITUTION_MODEL_VERSION,
    AuthorityClaim,
    InstitutionalIdentityAnchor,
    InstitutionalOffice,
    Institution,
    AuthorityClaimStatus,
    AuthorityScope,
)
from src.classes.mechanical_language import EntityRef


_Item = TypeVar("_Item")


def _strict_state_payload(data: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TypeError(f"{label} must be an object")
    missing = fields - set(data)
    unknown = set(data) - fields
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing {sorted(missing)}")
        if unknown:
            details.append(f"unknown {sorted(unknown)}")
        raise ValueError(f"{label} has invalid fields: {', '.join(details)}")
    if (
        type(data["model_version"]) is not int
        or data["model_version"] != INSTITUTION_MODEL_VERSION
    ):
        raise ValueError(
            f"unsupported {label} model_version: {data['model_version']!r}"
        )
    return data


def _registry(
    data: Any, parser: Callable[[dict[str, Any]], _Item], label: str
) -> dict[str, _Item]:
    if not isinstance(data, dict):
        raise TypeError(f"{label} must be an object keyed by ID")
    result: dict[str, _Item] = {}
    for key, raw in data.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{label} keys must be non-empty strings")
        if not isinstance(raw, dict):
            raise TypeError(f"{label}[{key!r}] must be an object")
        item = parser(raw)
        item_id = getattr(item, "id", None)
        if item_id != key:
            raise ValueError(f"{label}[{key!r}] id does not match its registry key")
        if set(raw) != set(item.to_dict()):
            raise ValueError(f"{label}[{key!r}] has invalid fields")
        result[key] = item
    return result


@dataclass(slots=True)
class InstitutionalAuthorityState:
    """Mutable registry for institutions, offices, claims and anchors."""

    model_version: int = INSTITUTION_MODEL_VERSION
    institutions: dict[str, Institution] = field(default_factory=dict)
    offices: dict[str, InstitutionalOffice] = field(default_factory=dict)
    claims: dict[str, AuthorityClaim] = field(default_factory=dict)
    identity_anchors: dict[str, InstitutionalIdentityAnchor] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self._check_version()
        self._validate_registries()

    def _check_version(self) -> None:
        if (
            type(self.model_version) is not int
            or self.model_version != INSTITUTION_MODEL_VERSION
        ):
            raise ValueError(
                f"unsupported authority state model_version: {self.model_version!r}"
            )

    def _validate_registries(self) -> None:
        for registry_name, registry in (
            ("institutions", self.institutions),
            ("offices", self.offices),
            ("claims", self.claims),
            ("identity_anchors", self.identity_anchors),
        ):
            if not isinstance(registry, dict):
                raise TypeError(f"{registry_name} must be a dictionary")
            for key, item in registry.items():
                if not isinstance(key, str) or getattr(item, "id", None) != key:
                    raise ValueError(f"{registry_name} key does not match item id")
        for office in self.offices.values():
            self._validate_office_reference(office)
        for claim in self.claims.values():
            if claim.office_id not in self.offices:
                raise ValueError(f"claim references unknown office: {claim.office_id}")
        for anchor in self.identity_anchors.values():
            if anchor.institution_id not in self.institutions:
                raise ValueError(
                    f"identity anchor references unknown institution: {anchor.institution_id}"
                )
        self._validate_office_scopes()

    def _validate_office_reference(self, office: InstitutionalOffice) -> None:
        if office.institution_id not in self.institutions:
            raise ValueError(
                f"office references unknown institution: {office.institution_id}"
            )

    def _validate_office_scopes(self) -> None:
        seen: set[tuple[str, object]] = set()
        for office in self.offices.values():
            for scope in office.scopes:
                key = (office.institution_id, scope)
                if key in seen:
                    raise ValueError(
                        "an institution may have only one office per authority scope: "
                        f"{office.institution_id}/{scope.value}"
                    )
                seen.add(key)

    def add_institution(self, institution: Institution) -> None:
        if not isinstance(institution, Institution):
            raise TypeError("institution must be an Institution")
        if institution.id in self.institutions:
            raise ValueError(f"duplicate institution id: {institution.id}")
        self.institutions[institution.id] = institution

    def add_office(self, office: InstitutionalOffice) -> None:
        if not isinstance(office, InstitutionalOffice):
            raise TypeError("office must be an InstitutionalOffice")
        self._validate_office_reference(office)
        if office.id in self.offices:
            raise ValueError(f"duplicate office id: {office.id}")
        occupied = {
            scope
            for existing in self.offices.values()
            if existing.institution_id == office.institution_id
            for scope in existing.scopes
        }
        overlap = occupied.intersection(office.scopes)
        if overlap:
            values = ", ".join(sorted(scope.value for scope in overlap))
            raise ValueError(
                "an institution may have only one office per authority scope: "
                f"{office.institution_id}/{values}"
            )
        self.offices[office.id] = office

    def add_claim(self, claim: AuthorityClaim) -> None:
        if not isinstance(claim, AuthorityClaim):
            raise TypeError("claim must be an AuthorityClaim")
        if claim.office_id not in self.offices:
            raise ValueError(f"claim references unknown office: {claim.office_id}")
        if claim.id in self.claims:
            raise ValueError(f"duplicate claim id: {claim.id}")
        self.claims[claim.id] = claim

    def add_identity_anchor(self, anchor: InstitutionalIdentityAnchor) -> None:
        if not isinstance(anchor, InstitutionalIdentityAnchor):
            raise TypeError("identity anchor must be an InstitutionalIdentityAnchor")
        if anchor.institution_id not in self.institutions:
            raise ValueError(
                f"identity anchor references unknown institution: {anchor.institution_id}"
            )
        if anchor.id in self.identity_anchors:
            raise ValueError(f"duplicate identity anchor id: {anchor.id}")
        self.identity_anchors[anchor.id] = anchor

    def get_claim(self, claim_id: str) -> AuthorityClaim | None:
        return self.claims.get(str(claim_id))

    def get_institution(self, institution_id: str) -> Institution | None:
        return self.institutions.get(str(institution_id))

    def get_institution_for_owner(self, owner_ref: EntityRef) -> Institution | None:
        if not isinstance(owner_ref, EntityRef):
            raise TypeError("owner_ref must be an EntityRef")
        return next(
            (
                institution
                for institution in self.institutions.values()
                if institution.owner_ref == owner_ref
            ),
            None,
        )

    def offices_for(self, institution_id: str) -> tuple[InstitutionalOffice, ...]:
        return tuple(
            sorted(
                (
                    office
                    for office in self.offices.values()
                    if office.institution_id == institution_id
                ),
                key=lambda office: office.id,
            )
        )

    def office_for_scope(
        self, institution_id: str, scope: AuthorityScope
    ) -> InstitutionalOffice | None:
        if not isinstance(scope, AuthorityScope):
            raise TypeError("scope must be an AuthorityScope")
        matches = [
            office
            for office in self.offices_for(institution_id)
            if scope in office.scopes
        ]
        if len(matches) > 1:
            raise ValueError(
                "institution has multiple offices for authority scope: "
                f"{institution_id}/{scope.value}"
            )
        return matches[0] if matches else None

    def active_claims(self, office_id: str) -> tuple[AuthorityClaim, ...]:
        return tuple(
            sorted(
                (
                    claim
                    for claim in self.claims.values()
                    if claim.office_id == office_id
                    and claim.status is AuthorityClaimStatus.ACTIVE
                ),
                key=lambda claim: claim.id,
            )
        )

    def replace_office(self, office: InstitutionalOffice) -> None:
        if not isinstance(office, InstitutionalOffice):
            raise TypeError("office must be an InstitutionalOffice")
        if office.id not in self.offices:
            raise KeyError(f"unknown office: {office.id}")
        self._validate_office_reference(office)
        occupied = {
            scope
            for office_id, existing in self.offices.items()
            if office_id != office.id
            and existing.institution_id == office.institution_id
            for scope in existing.scopes
        }
        overlap = occupied.intersection(office.scopes)
        if overlap:
            values = ", ".join(sorted(scope.value for scope in overlap))
            raise ValueError(
                "an institution may have only one office per authority scope: "
                f"{office.institution_id}/{values}"
            )
        self.offices[office.id] = office

    def replace_claim(self, claim: AuthorityClaim) -> None:
        if not isinstance(claim, AuthorityClaim):
            raise TypeError("claim must be an AuthorityClaim")
        if claim.id not in self.claims:
            raise KeyError(f"unknown claim: {claim.id}")
        if claim.office_id not in self.offices:
            raise ValueError(f"claim references unknown office: {claim.office_id}")
        current = self.claims[claim.id]
        immutable = (
            "office_id",
            "claimant_ref",
            "opened_month",
            "source_kind",
            "source_ref",
        )
        if any(getattr(current, name) != getattr(claim, name) for name in immutable):
            raise ValueError("authority claim identity and source are immutable")
        if not set(current.evidence_event_ids).issubset(claim.evidence_event_ids):
            raise ValueError("authority claim evidence is append-only")
        allowed = {
            AuthorityClaimStatus.ACTIVE: {
                AuthorityClaimStatus.ACTIVE,
                AuthorityClaimStatus.WITHDRAWN,
                AuthorityClaimStatus.DEFEATED,
                AuthorityClaimStatus.EXPIRED,
            },
            AuthorityClaimStatus.WITHDRAWN: {AuthorityClaimStatus.WITHDRAWN},
            AuthorityClaimStatus.DEFEATED: {AuthorityClaimStatus.DEFEATED},
            AuthorityClaimStatus.EXPIRED: {AuthorityClaimStatus.EXPIRED},
        }
        if claim.status not in allowed[current.status]:
            raise ValueError(
                f"invalid authority claim transition: {current.status.value} -> "
                f"{claim.status.value}"
            )
        self.claims[claim.id] = claim

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "institutions": {
                key: self.institutions[key].to_dict()
                for key in sorted(self.institutions)
            },
            "offices": {
                key: self.offices[key].to_dict() for key in sorted(self.offices)
            },
            "claims": {key: self.claims[key].to_dict() for key in sorted(self.claims)},
            "identity_anchors": {
                key: self.identity_anchors[key].to_dict()
                for key in sorted(self.identity_anchors)
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstitutionalAuthorityState":
        raw = _strict_state_payload(
            data,
            {"model_version", "institutions", "offices", "claims", "identity_anchors"},
            "authority state",
        )
        institutions = _registry(
            raw["institutions"], Institution.from_dict, "institutions"
        )
        offices = _registry(raw["offices"], InstitutionalOffice.from_dict, "offices")
        claims = _registry(raw["claims"], AuthorityClaim.from_dict, "claims")
        anchors = _registry(
            raw["identity_anchors"],
            InstitutionalIdentityAnchor.from_dict,
            "identity_anchors",
        )
        return cls(
            model_version=raw["model_version"],
            institutions=institutions,
            offices=offices,
            claims=claims,
            identity_anchors=anchors,
        )


__all__ = ["InstitutionalAuthorityState"]

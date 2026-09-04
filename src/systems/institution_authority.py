"""Deterministic authority checks over the canonical institutional state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.classes.environment.region import CityRegion
from src.classes.institution import (
    AuthorityScope,
    InstitutionalAuthorityState,
    Institution,
    InstitutionKind,
)
from src.classes.mechanical_language import EntityRef


class AuthorityDenial(StrEnum):
    INVALID_REQUEST = "invalid_request"
    INSTITUTION_NOT_FOUND = "institution_not_found"
    INSTITUTION_INACTIVE = "institution_inactive"
    OFFICE_NOT_FOUND = "office_not_found"
    HOLDER_MISSING = "holder_missing"
    HOLDER_DEAD = "holder_dead"
    HOLDER_NOT_YET_ACTIVE = "holder_not_yet_active"
    ACTOR_NOT_AUTHORIZED = "actor_not_authorized"
    MATERIAL_CONTROL_REQUIRED = "material_control_required"
    MATERIAL_CONTROL_MISSING = "material_control_missing"


@dataclass(frozen=True, slots=True)
class AuthorityVerdict:
    allowed: bool
    denial: AuthorityDenial | None = None
    institution_id: str | None = None
    office_id: str | None = None
    authorizing_institution_id: str | None = None
    contesting_claim_ids: tuple[str, ...] = field(default_factory=tuple)
    material_control_of: EntityRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise TypeError("allowed must be a bool")
        if self.allowed and self.denial is not None:
            raise ValueError("an allowed verdict cannot have a denial")
        if not self.allowed and self.denial is None:
            raise ValueError("a denied verdict requires a typed denial")
        if self.denial is not None and not isinstance(self.denial, AuthorityDenial):
            raise TypeError("denial must be an AuthorityDenial")
        object.__setattr__(
            self, "contesting_claim_ids", tuple(self.contesting_claim_ids)
        )


def material_control_of(world: Any, target_ref: EntityRef) -> EntityRef | None:
    """Return the current material controller of a city, from CityGovernance only."""

    if not isinstance(target_ref, EntityRef):
        return None
    if target_ref.kind != "region":
        return None
    for region in getattr(getattr(world, "map", None), "regions", {}).values():
        if isinstance(region, CityRegion) and str(region.id) == target_ref.id:
            governance = region.city_state.governance
            if governance.controller_kind and governance.controller_id:
                return EntityRef(
                    kind=governance.controller_kind,
                    id=governance.controller_id,
                )
            return None
    return None


def _denied(
    denial: AuthorityDenial,
    *,
    institution_id: str | None = None,
    office_id: str | None = None,
    authorizing_institution_id: str | None = None,
    claims: tuple[str, ...] = (),
    material: EntityRef | None = None,
) -> AuthorityVerdict:
    return AuthorityVerdict(
        allowed=False,
        denial=denial,
        institution_id=institution_id,
        office_id=office_id,
        authorizing_institution_id=authorizing_institution_id,
        contesting_claim_ids=claims,
        material_control_of=material,
    )


def _avatar_is_alive(world: Any, avatar_ref: EntityRef) -> bool:
    manager = getattr(world, "avatar_manager", None)
    getter = getattr(manager, "get_avatar", None)
    avatar = getter(avatar_ref.id) if callable(getter) else None
    return avatar is not None and not bool(getattr(avatar, "is_dead", False))


def _current_month(world: Any, current_month: int | None) -> int:
    if current_month is not None:
        return current_month
    return int(getattr(world, "month_stamp", 0))


def _authority_state(world: Any) -> InstitutionalAuthorityState | None:
    state = getattr(world, "institutional_authority", None)
    return state if isinstance(state, InstitutionalAuthorityState) else None


def _resolve_institution(
    state: InstitutionalAuthorityState, owner_ref: EntityRef
) -> Institution | None:
    return state.get_institution_for_owner(owner_ref)


def _controller_for_city(world: Any, region_ref: EntityRef) -> EntityRef | None:
    return material_control_of(world, region_ref)


def _office_authorizes(
    world: Any,
    state: InstitutionalAuthorityState,
    institution: Institution,
    actor_ref: EntityRef,
    scope: AuthorityScope,
    month: int,
) -> tuple[AuthorityVerdict | None, str | None]:
    office = state.office_for_scope(institution.id, scope)
    if office is None:
        return _denied(
            AuthorityDenial.OFFICE_NOT_FOUND,
            institution_id=institution.id,
            authorizing_institution_id=institution.id,
        ), None
    claims = tuple(claim.id for claim in state.active_claims(office.id))
    if office.holder_ref is None or office.holder_since_month is None:
        return _denied(
            AuthorityDenial.HOLDER_MISSING,
            institution_id=institution.id,
            office_id=office.id,
            authorizing_institution_id=institution.id,
            claims=claims,
        ), None
    if not _avatar_is_alive(world, office.holder_ref):
        return _denied(
            AuthorityDenial.HOLDER_DEAD,
            institution_id=institution.id,
            office_id=office.id,
            authorizing_institution_id=institution.id,
            claims=claims,
        ), None
    if office.holder_since_month > month:
        return _denied(
            AuthorityDenial.HOLDER_NOT_YET_ACTIVE,
            institution_id=institution.id,
            office_id=office.id,
            authorizing_institution_id=institution.id,
            claims=claims,
        ), None
    if actor_ref != institution.owner_ref and actor_ref != office.holder_ref:
        return _denied(
            AuthorityDenial.ACTOR_NOT_AUTHORIZED,
            institution_id=institution.id,
            office_id=office.id,
            authorizing_institution_id=institution.id,
            claims=claims,
        ), None
    return None, office.id


def can_actor_act_for(
    world: Any,
    actor_ref: EntityRef,
    institution_ref: EntityRef,
    scope: AuthorityScope,
    current_month: int | None = None,
    require_material_control: bool = False,
    material_target_ref: EntityRef | None = None,
) -> AuthorityVerdict:
    """Answer authority from current canonical state without mutating it."""

    if (
        not isinstance(actor_ref, EntityRef)
        or not isinstance(institution_ref, EntityRef)
        or not isinstance(scope, AuthorityScope)
        or not isinstance(require_material_control, bool)
        or (
            material_target_ref is not None
            and not isinstance(material_target_ref, EntityRef)
        )
    ):
        return _denied(AuthorityDenial.INVALID_REQUEST)
    try:
        month = _current_month(world, current_month)
        if isinstance(month, bool) or not isinstance(month, int) or month < 0:
            raise ValueError
    except (TypeError, ValueError):
        return _denied(AuthorityDenial.INVALID_REQUEST)
    state = _authority_state(world)
    if state is None:
        return _denied(AuthorityDenial.INSTITUTION_NOT_FOUND)
    institution = _resolve_institution(state, institution_ref)
    if institution is None:
        return _denied(AuthorityDenial.INSTITUTION_NOT_FOUND)
    if not institution.is_active(month):
        return _denied(
            AuthorityDenial.INSTITUTION_INACTIVE, institution_id=institution.id
        )

    effective_material_target = material_target_ref
    if (
        effective_material_target is None
        and require_material_control
        and institution_ref.kind == "region"
    ):
        effective_material_target = institution_ref
    material = (
        material_control_of(world, effective_material_target)
        if effective_material_target
        else None
    )
    if require_material_control and material is None:
        return _denied(
            AuthorityDenial.MATERIAL_CONTROL_MISSING,
            institution_id=institution.id,
            authorizing_institution_id=institution.id,
        )

    controlling_owner = institution.owner_ref
    if institution.kind is InstitutionKind.CITY:
        controlling_owner = _controller_for_city(world, institution.owner_ref)
        if controlling_owner is None:
            return _denied(
                AuthorityDenial.MATERIAL_CONTROL_MISSING,
                institution_id=institution.id,
            )
        controller = state.get_institution_for_owner(controlling_owner)
        if controller is None or not controller.is_active(month):
            return _denied(
                AuthorityDenial.MATERIAL_CONTROL_MISSING,
                institution_id=institution.id,
                authorizing_institution_id=controller.id
                if controller is not None
                else None,
                material=controlling_owner,
            )
        authorization_actor = (
            controller.owner_ref if actor_ref == institution.owner_ref else actor_ref
        )
        denied, office_id = _office_authorizes(
            world, state, controller, authorization_actor, scope, month
        )
        if denied is not None:
            return AuthorityVerdict(
                allowed=False,
                denial=denied.denial,
                institution_id=institution.id,
                office_id=denied.office_id,
                authorizing_institution_id=controller.id,
                contesting_claim_ids=denied.contesting_claim_ids,
                material_control_of=controlling_owner,
            )
        if effective_material_target is not None and material != controlling_owner:
            return _denied(
                AuthorityDenial.MATERIAL_CONTROL_MISSING,
                institution_id=institution.id,
                office_id=office_id,
                authorizing_institution_id=controller.id,
                material=material,
            )
        return AuthorityVerdict(
            allowed=True,
            institution_id=institution.id,
            office_id=office_id,
            authorizing_institution_id=controller.id,
            contesting_claim_ids=tuple(
                claim.id for claim in state.active_claims(office_id or "")
            ),
            material_control_of=controlling_owner,
        )

    denied, office_id = _office_authorizes(
        world, state, institution, actor_ref, scope, month
    )
    if denied is not None:
        return denied
    if effective_material_target is not None and material != institution.owner_ref:
        return _denied(
            AuthorityDenial.MATERIAL_CONTROL_MISSING,
            institution_id=institution.id,
            office_id=office_id,
            authorizing_institution_id=institution.id,
            material=material,
        )
    return AuthorityVerdict(
        allowed=True,
        institution_id=institution.id,
        office_id=office_id,
        authorizing_institution_id=institution.id,
        contesting_claim_ids=tuple(
            claim.id for claim in state.active_claims(office_id or "")
        ),
        material_control_of=material,
    )


__all__ = [
    "AuthorityDenial",
    "AuthorityVerdict",
    "can_actor_act_for",
    "material_control_of",
]

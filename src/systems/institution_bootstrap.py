"""Bootstrap durable institutional identities for a new world."""

from __future__ import annotations

from typing import Any

from src.classes.environment.region import CityRegion
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.institution import (
    AuthorityScope,
    InstitutionalAuthorityState,
    InstitutionalOffice,
    Institution,
    InstitutionKind,
)
from src.classes.mechanical_language import EntityRef
from src.classes.state_delta import StateDelta


# Listed explicitly rather than `tuple(AuthorityScope)`, so a scope added for
# one kind of institution cannot silently hand the same power to another: a
# sovereign administers cities, not somebody else's sect.
_DYNASTY_SCOPES = (
    AuthorityScope.URBAN_ADMINISTRATION,
    AuthorityScope.RESOURCE_DISPOSITION,
    AuthorityScope.TREASURY_DISPOSITION,
    AuthorityScope.COMMITMENT_NEGOTIATION,
    AuthorityScope.RECOGNITION,
    AuthorityScope.FORCE_EMPLOYMENT,
)
_SECT_SCOPES = (
    AuthorityScope.TREASURY_DISPOSITION,
    AuthorityScope.COMMITMENT_NEGOTIATION,
    AuthorityScope.RECOGNITION,
    AuthorityScope.FORCE_EMPLOYMENT,
    AuthorityScope.SECT_ADMINISTRATION,
)


def _living_avatar(world: Any, avatar_id: Any) -> Any | None:
    if avatar_id is None:
        return None
    getter = getattr(getattr(world, "avatar_manager", None), "get_avatar", None)
    if not callable(getter):
        return None
    avatar = getter(str(avatar_id))
    return (
        avatar
        if avatar is not None and not bool(getattr(avatar, "is_dead", False))
        else None
    )


def _ensure_institution(
    state: InstitutionalAuthorityState,
    kind: InstitutionKind,
    owner_ref: EntityRef,
    founded_month: int,
) -> Institution:
    institution = Institution(
        kind=kind, owner_ref=owner_ref, founded_month=founded_month
    )
    existing = state.institutions.get(institution.id)
    if existing is not None:
        return existing
    state.add_institution(institution)
    return institution


def _ensure_office(
    state: InstitutionalAuthorityState,
    institution: Institution,
    office_key: str,
    scopes: tuple[AuthorityScope, ...],
    holder: Any | None,
    founded_month: int,
) -> InstitutionalOffice:
    office_id = f"office:{institution.id}:{office_key}"
    existing = state.offices.get(office_id)
    if existing is not None:
        return existing
    office = InstitutionalOffice(
        institution_id=institution.id,
        office_key=office_key,
        scopes=scopes,
        holder_ref=EntityRef("avatar", str(holder.id)) if holder is not None else None,
        holder_since_month=founded_month if holder is not None else None,
    )
    state.add_office(office)
    return office


def _bootstrap_dynasty(
    world: Any, state: InstitutionalAuthorityState, month: int
) -> None:
    dynasty = getattr(world, "dynasty", None)
    if dynasty is None or not bool(getattr(dynasty, "is_active", True)):
        return
    institution = _ensure_institution(
        state, InstitutionKind.DYNASTY, EntityRef("dynasty", str(dynasty.id)), month
    )
    emperor = _living_avatar(world, getattr(dynasty, "current_emperor_id", None))
    _ensure_office(state, institution, "sovereign", _DYNASTY_SCOPES, emperor, month)


def _patriarch(world: Any, sect: Any) -> Any | None:
    members = getattr(sect, "members", {})
    patriarchs = [
        member
        for member in members.values()
        if str(
            getattr(
                getattr(member, "sect_rank", None),
                "value",
                getattr(member, "sect_rank", ""),
            )
        )
        == "patriarch"
        and not bool(getattr(member, "is_dead", False))
    ]
    return patriarchs[0] if len(patriarchs) == 1 else None


def _sect_scopes() -> tuple[AuthorityScope, ...]:
    return _SECT_SCOPES


def _bootstrap_sects(
    world: Any, state: InstitutionalAuthorityState, month: int
) -> None:
    context = getattr(world, "sect_context", None)
    get_active = getattr(context, "get_active_sects", None)
    sects = get_active() if callable(get_active) else ()
    for sect in sects:
        if not bool(getattr(sect, "is_active", True)):
            continue
        institution = _ensure_institution(
            state, InstitutionKind.SECT, EntityRef("sect", str(sect.id)), month
        )
        _ensure_office(
            state,
            institution,
            "patriarch",
            _SECT_SCOPES,
            _patriarch(world, sect),
            month,
        )


def _bootstrap_cities(
    world: Any, state: InstitutionalAuthorityState, month: int
) -> None:
    regions = getattr(getattr(world, "map", None), "regions", {})
    for region in regions.values():
        if isinstance(region, CityRegion):
            _ensure_institution(
                state, InstitutionKind.CITY, EntityRef("region", str(region.id)), month
            )


def bootstrap_institutional_authority(world: Any) -> InstitutionalAuthorityState:
    """Register active dynasty, sect, and city identities exactly once."""

    state = getattr(world, "institutional_authority", None)
    if not isinstance(state, InstitutionalAuthorityState):
        raise TypeError(
            "world institutional_authority must be an InstitutionalAuthorityState"
        )
    month = int(getattr(world, "month_stamp", 0))
    _bootstrap_dynasty(world, state, month)
    _bootstrap_sects(world, state, month)
    _bootstrap_cities(world, state, month)
    return state


def _active_sects(world: Any) -> dict[str, Any]:
    context = getattr(world, "sect_context", None)
    get_active = getattr(context, "get_active_sects", None)
    active = list(get_active()) if callable(get_active) else []
    return {str(getattr(sect, "id")): sect for sect in active}


def _all_sects(world: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for sect in getattr(world, "existed_sects", []) or []:
        result[str(getattr(sect, "id"))] = sect
    result.update(_active_sects(world))
    return result


def _owner_is_active(
    world: Any,
    institution: Institution,
    active_sects: dict[str, Any],
    all_sects: dict[str, Any],
) -> bool:
    if institution.kind is InstitutionKind.DYNASTY:
        dynasty = getattr(world, "dynasty", None)
        return (
            dynasty is not None
            and str(getattr(dynasty, "id", "")) == institution.owner_ref.id
            and bool(getattr(dynasty, "is_active", True))
        )
    if institution.kind is InstitutionKind.SECT:
        sect = all_sects.get(institution.owner_ref.id)
        return (
            sect is not None
            and institution.owner_ref.id in active_sects
            and bool(getattr(sect, "is_active", True))
        )
    return True


def _relevant_sources(
    current_events: tuple[Any, ...],
    *,
    institution: Institution,
    old_holder: EntityRef | None = None,
    new_holder: EntityRef | None = None,
) -> tuple[Any, ...]:
    del institution, new_holder
    old_holder_id = old_holder.id if old_holder is not None else None
    if old_holder_id is None:
        return ()
    matched: list[Any] = []
    for event in current_events:
        # Only a canonical death of the previous holder is precise enough to
        # motivate an office transition.  Mere co-occurrence with a sect or a
        # financial delta is context, not causality.
        related_avatars = {
            str(item) for item in (getattr(event, "related_avatars", None) or [])
        }
        if getattr(event, "event_type", "") == "death" and old_holder_id in related_avatars:
            matched.append(event)
    return tuple(
        sorted(
            {str(event.id): event for event in matched}.values(),
            key=lambda item: str(item.id),
        )
    )


def establish_genesis_identity_anchors(world: Any) -> list[Event]:
    """Declare, once, where each active sect's identity is already anchored.

    Invariants:

    * New-world initialization only. Neither `bootstrap_institutional_authority`
      nor `synchronize_institutional_authority` calls this, so a load or a
      monthly reconciliation can never add an anchor after the fact.
    * The only source is the map's own declaration: a `SectRegion` names its
      owner through `sect_id`. No dynasty or city anchor, and no city is ever
      created for a `SectRegion`.
    * `established_month` is the world clock as it stands -- the genesis
      month -- never backdated.
    * The premise fact is persisted before the anchor cites it, because
      `save_game._validate_institutional_evidence` refuses to save an
      authority state whose evidence is absent from the event store.
    * Deterministic ids make a re-run idempotent instead of duplicating.
    """
    from src.classes.environment.sect_region import SectRegion
    from src.classes.institution import (
        IdentityAnchorKind,
        InstitutionalIdentityAnchor,
    )
    from src.i18n import t

    state = getattr(world, "institutional_authority", None)
    if not isinstance(state, InstitutionalAuthorityState):
        raise TypeError(
            "world institutional_authority must be an InstitutionalAuthorityState"
        )
    month = int(getattr(world, "month_stamp", 0))
    sects = _active_sects(world)
    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    produced: list[Event] = []
    for region in sorted(regions.values(), key=lambda item: str(getattr(item, "id", ""))):
        if not isinstance(region, SectRegion):
            continue
        try:
            sect_id = int(getattr(region, "sect_id", -1))
        except (TypeError, ValueError):
            continue
        # `-1` is the field's own default for "no sect declared".
        if sect_id < 0:
            continue
        sect = sects.get(str(sect_id))
        if sect is None:
            continue
        institution = state.get_institution_for_owner(
            EntityRef("sect", str(sect_id))
        )
        if institution is None:
            continue
        # Deterministic, so re-running this on the same world produces the
        # same fact id and the same anchor id rather than a second founding.
        event_id = (
            f"institutional-identity-anchor:{institution.id}:"
            f"{IdentityAnchorKind.HEADQUARTERS.value}:region:{region.id}"
        )
        anchor = InstitutionalIdentityAnchor(
            institution_id=institution.id,
            kind=IdentityAnchorKind.HEADQUARTERS,
            subject=EntityRef("region", str(region.id)),
            established_month=month,
            evidence_event_ids=(event_id,),
        )
        if anchor.id in state.identity_anchors:
            continue
        institution_name = str(getattr(sect, "name", "") or institution.id)
        region_name = str(getattr(region, "name", "") or region.id)
        event = Event(
            month_stamp=world.month_stamp,
            # A declared pre-existing seat, not a founding: nothing here says
            # the institution came into being now.
            content=t(
                "The declared headquarters of {institution} is {region}.",
                institution=institution_name,
                region=region_name,
            ),
            related_sects=[sect_id],
            event_type="institution_identity_anchored",
            id=event_id,
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.DETERMINISTIC,
            render_params={
                "institution_id": institution.id,
                "anchor_id": anchor.id,
                "anchor_kind": IdentityAnchorKind.HEADQUARTERS.value,
                "region_id": str(region.id),
                "institution_name": institution_name,
                "region_name": region_name,
                # Says plainly what this fact is: a declared premise of the
                # world's genesis, not an act anyone decided.
                "premise": "world_genesis",
            },
        )
        delta = StateDelta(
            event_id=event.id,
            owner_kind="institutional_authority",
            owner_id=institution.id,
            aspect=f"identity_anchor:{anchor.id}",
            before="absent",
            after="established",
        )
        event.causal_payload = {"deltas": [delta.to_dict()]}
        # Persisted before the anchor cites it, so the evidence a save
        # validates always exists.
        world.event_manager.add_event(event)
        state.add_identity_anchor(anchor)
        produced.append(event)
    return produced


def _transition_event(
    world: Any,
    institution: Institution,
    *,
    aspect: str,
    before: str | None,
    after: str | None,
    registry_owner_id: str,
    current_events: tuple[Any, ...],
    old_holder: EntityRef | None = None,
    new_holder: EntityRef | None = None,
) -> Event:
    month = int(world.month_stamp)
    before_value = before or "none"
    after_value = after or "none"
    event_id = (
        f"institutional-authority:{institution.id}:{aspect}:{month}:"
        f"{before_value}:{after_value}"
    )
    event = Event(
        month_stamp=world.month_stamp,
        content=f"Institutional authority transition for {institution.id}: {aspect}.",
        related_avatars=[ref.id for ref in (old_holder, new_holder) if ref is not None]
        or None,
        related_sects=[int(institution.owner_ref.id)]
        if institution.owner_ref.kind == "sect" and institution.owner_ref.id.isdigit()
        else None,
        event_type="institutional_authority_transition",
        id=event_id,
        fact_kind=FactKind.STATE_TRANSITION,
    )
    delta = StateDelta(
        event_id=event.id,
        owner_kind="institutional_authority",
        owner_id=registry_owner_id,
        aspect=aspect,
        before=before,
        after=after,
    )
    event.causal_payload = {"deltas": [delta.to_dict()]}
    for source in _relevant_sources(
        current_events,
        institution=institution,
        old_holder=old_holder,
        new_holder=new_holder,
    ):
        event.causal_links.append(
            CausalLink(
                event_id=event.id,
                cause_event_id=str(source.id),
                relation=CausalRelation.RESPONSE_TO,
            )
        )
    return event


def _replace_institution_dissolved(
    state: InstitutionalAuthorityState, institution: Institution, month: int
) -> Institution | None:
    if institution.dissolved_month is not None or month < institution.founded_month:
        return None
    replacement = Institution(
        kind=institution.kind,
        owner_ref=institution.owner_ref,
        founded_month=institution.founded_month,
        dissolved_month=month,
        id=institution.id,
    )
    state.replace_institution(replacement)
    return replacement


def _synchronize_office(
    world: Any,
    state: InstitutionalAuthorityState,
    institution: Institution,
    *,
    office_key: str,
    scopes: tuple[AuthorityScope, ...],
    holder: Any | None,
    month: int,
    current_events: tuple[Any, ...],
) -> Event | None:
    office_id = f"office:{institution.id}:{office_key}"
    office = state.offices.get(office_id)
    if office is None:
        return None
    desired_ref = EntityRef("avatar", str(holder.id)) if holder is not None else None
    holder_changed = office.holder_ref != desired_ref
    normalized_scopes = tuple(sorted(scopes, key=lambda item: item.value))
    scopes_changed = office.scopes != normalized_scopes
    if not holder_changed and not scopes_changed:
        return None
    since = office.holder_since_month
    if holder_changed:
        since = month if desired_ref is not None else None
    replacement = InstitutionalOffice(
        institution_id=office.institution_id,
        office_key=office.office_key,
        scopes=normalized_scopes,
        holder_ref=desired_ref,
        holder_since_month=since,
        id=office.id,
    )
    state.replace_office(replacement)
    if holder_changed:
        return _transition_event(
            world,
            institution,
            aspect=f"{office_key}_holder",
            before=office.holder_ref.id if office.holder_ref else None,
            after=desired_ref.id if desired_ref else None,
            registry_owner_id=office.id,
            current_events=current_events,
            old_holder=office.holder_ref,
            new_holder=desired_ref,
        )
    return _transition_event(
        world,
        institution,
        aspect=f"{office_key}_scopes",
        before=",".join(scope.value for scope in office.scopes),
        after=",".join(scope.value for scope in normalized_scopes),
        registry_owner_id=office.id,
        current_events=current_events,
    )


def synchronize_institutional_authority(
    world: Any, *, current_events: Any = ()
) -> list[Event]:
    """Reconcile authority offices with current canonical owners.

    Bootstrap creates the initial world premise without events.  This runtime
    operation only records transitions caused by later canonical changes.
    """

    state = getattr(world, "institutional_authority", None)
    if not isinstance(state, InstitutionalAuthorityState):
        raise TypeError(
            "world institutional_authority must be an InstitutionalAuthorityState"
        )
    month = int(getattr(world, "month_stamp", 0))
    current = tuple(current_events or ())
    active_sects = _active_sects(world)
    all_sects = _all_sects(world)
    produced: list[Event] = []
    for institution in tuple(state.institutions.values()):
        if institution.kind not in {InstitutionKind.DYNASTY, InstitutionKind.SECT}:
            continue
        if not _owner_is_active(world, institution, active_sects, all_sects):
            replacement = _replace_institution_dissolved(state, institution, month)
            if replacement is not None:
                produced.append(
                    _transition_event(
                        world,
                        replacement,
                        aspect="institution_status",
                        before="active",
                        after="dissolved",
                        registry_owner_id=replacement.id,
                        current_events=current,
                    )
                )
            continue
        if institution.dissolved_month is not None:
            continue
        holder = None
        scopes = _DYNASTY_SCOPES
        office_key = "sovereign"
        if institution.kind is InstitutionKind.DYNASTY:
            dynasty = getattr(world, "dynasty", None)
            holder = _living_avatar(world, getattr(dynasty, "current_emperor_id", None))
        else:
            sect = all_sects.get(institution.owner_ref.id)
            holder = _patriarch(world, sect) if sect is not None else None
            scopes = _sect_scopes()
            office_key = "patriarch"
        event = _synchronize_office(
            world,
            state,
            institution,
            office_key=office_key,
            scopes=scopes,
            holder=holder,
            month=month,
            current_events=current,
        )
        if event is not None:
            produced.append(event)
    return produced


__all__ = [
    "bootstrap_institutional_authority",
    "establish_genesis_identity_anchors",
    "synchronize_institutional_authority",
]

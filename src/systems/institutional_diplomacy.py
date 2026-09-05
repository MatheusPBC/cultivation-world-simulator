"""Sect diplomacy projected from the shared institutional relation owner.

This module contains no state machine and no material combat effects.  It
translates the V1 sect-facing contract to and from InstitutionalRelation so
the existing battle and UI layers can remain projections of canonical state.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.classes.institution import (
    Institution,
    InstitutionalRelation,
    InstitutionalRelationKind,
    InstitutionKind,
)
from src.classes.mechanical_language import EntityRef
from src.systems.institution_authority import can_actor_act_for
from src.classes.institution import AuthorityScope


STATUS_PEACE = "peace"
STATUS_WAR = "war"

# The canonical event type of a formal war declaration between institutions.
# A war episode is anchored to one such event, never to ``since_month`` alone:
# peace followed by a new declaration in the same month is a different war.
WAR_DECLARED_EVENT_TYPE = "institutional_war_declared"


def sect_institution_ref(sect_id: int | str) -> EntityRef:
    return EntityRef("sect", str(int(sect_id)))


def sect_institution_id(sect_id: int | str) -> str:
    return Institution.id_for(InstitutionKind.SECT, sect_institution_ref(sect_id))


def active_sects(world: Any) -> list[Any]:
    """The sects the runtime currently considers active, in a stable order."""

    context = getattr(world, "sect_context", None)
    sects = (
        context.get_active_sects()
        if context is not None
        else (getattr(world, "existed_sects", []) or [])
    )
    return sorted(sects, key=lambda item: int(getattr(item, "id", 0)))


def sect_by_id(world: Any, sect_id: int | str) -> Any | None:
    return next(
        (
            sect
            for sect in active_sects(world)
            if str(getattr(sect, "id", "")) == str(sect_id)
        ),
        None,
    )


def has_active_sect_institution(
    world: Any, sect_id: int | str, *, current_month: int
) -> bool:
    institution = world.institutional_authority.get_institution(
        sect_institution_id(sect_id)
    )
    return institution is not None and institution.is_active(int(current_month))


def _relation(world: Any, sect_a_id: int | str, sect_b_id: int | str):
    return world.institutional_relations.get_relation(
        sect_institution_id(sect_a_id),
        sect_institution_id(sect_b_id),
    )


def _reason_from_evidence(world: Any, relation: InstitutionalRelation) -> str:
    getter = getattr(getattr(world, "event_manager", None), "get_event_by_id", None)
    if not callable(getter):
        return ""
    for event_id in reversed(relation.evidence_event_ids):
        event = getter(event_id)
        if event is None:
            continue
        params = event.render_params if isinstance(event.render_params, dict) else {}
        payload = event.causal_payload if isinstance(event.causal_payload, dict) else {}
        reason = params.get("reason", payload.get("reason", ""))
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
    return ""


def are_sects_at_war(world: Any, sect_a_id: int | str, sect_b_id: int | str) -> bool:
    relation = _relation(world, sect_a_id, sect_b_id)
    return relation is not None and relation.kind is InstitutionalRelationKind.AT_WAR


def sect_war_relation(
    world: Any, sect_a_id: int | str, sect_b_id: int | str
) -> InstitutionalRelation | None:
    """The canonical relation when, and only when, it is currently a war."""

    relation = _relation(world, sect_a_id, sect_b_id)
    return (
        relation
        if relation is not None
        and relation.kind is InstitutionalRelationKind.AT_WAR
        else None
    )


def negotiating_sect(world: Any, sect_id: int | str) -> bool:
    """A sect may only bind itself while active and authorized to negotiate.

    The scope is ``COMMITMENT_NEGOTIATION`` because ending a war is a
    negotiated cessation, not employment of force; it grants nothing military.
    """

    if not has_active_sect_institution(
        world, sect_id, current_month=int(world.month_stamp)
    ):
        return False
    sect_ref = sect_institution_ref(sect_id)
    return can_actor_act_for(
        world,
        sect_ref,
        sect_ref,
        AuthorityScope.COMMITMENT_NEGOTIATION,
        current_month=int(world.month_stamp),
    ).allowed


def get_sect_diplomacy_state(
    world: Any,
    sect_a_id: int | str,
    sect_b_id: int | str,
    *,
    current_month: int,
    start_year: int | None = None,
) -> dict[str, Any]:
    relation = _relation(world, sect_a_id, sect_b_id)
    if relation is None:
        peace_start = (
            int(
                (
                    start_year
                    if start_year is not None
                    else getattr(world, "start_year", 0)
                )
            )
            * 12
        )
        return {
            "status": STATUS_PEACE,
            "start_month": peace_start,
            "peace_start_month": peace_start,
            "peace_months": max(0, int(current_month) - peace_start),
            "war_months": 0,
            "reason": "",
        }
    if relation.kind is InstitutionalRelationKind.AT_WAR:
        return {
            "status": STATUS_WAR,
            "start_month": relation.since_month,
            "peace_start_month": None,
            "peace_months": 0,
            "war_months": max(0, int(current_month) - relation.since_month),
            "reason": _reason_from_evidence(world, relation),
        }
    return {
        "status": STATUS_PEACE,
        "start_month": relation.since_month,
        "peace_start_month": relation.since_month,
        "peace_months": max(0, int(current_month) - relation.since_month),
        "war_months": 0,
        "reason": _reason_from_evidence(world, relation),
    }


def get_sect_diplomacy_breakdown(
    world: Any,
    *,
    current_month: int,
    sect_ids: Iterable[int | str],
    start_year: int | None = None,
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    ids = sorted({int(sect_id) for sect_id in sect_ids if int(sect_id) > 0})
    result: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for index, first in enumerate(ids):
        for second in ids[index + 1 :]:
            pair = (first, second)
            state = get_sect_diplomacy_state(
                world,
                first,
                second,
                current_month=int(current_month),
                start_year=start_year,
            )
            if state["status"] == STATUS_WAR:
                relation = _relation(world, first, second)
                assert relation is not None
                months = int(state["war_months"])
                result[pair] = [
                    {
                        "reason": "WAR_STATE",
                        "delta": relation.friendliness - min(20, (months // 12) * 2),
                        "meta": {"status": STATUS_WAR, "war_months": months},
                    }
                ]
                continue
            months = int(state["peace_months"])
            entries = [
                {
                    "reason": "PEACE_STATE",
                    "delta": 0,
                    "meta": {"status": STATUS_PEACE, "peace_months": months},
                }
            ]
            bonus = min(20, months // 12)
            if bonus:
                entries.append(
                    {
                        "reason": "LONG_PEACE",
                        "delta": bonus,
                        "meta": {
                            "status": STATUS_PEACE,
                            "peace_months": months,
                            "capped": bonus >= 20,
                        },
                    }
                )
            result[pair] = entries
    return result


def _set_relation(
    world: Any,
    sect_a_id: int | str,
    sect_b_id: int | str,
    *,
    kind: InstitutionalRelationKind,
    current_month: int,
    evidence_event_ids: Iterable[str],
) -> InstitutionalRelation:
    institution_ids = sorted(
        (sect_institution_id(sect_a_id), sect_institution_id(sect_b_id))
    )
    existing = world.institutional_relations.get_relation(*institution_ids)
    evidence = tuple(
        dict.fromkeys(
            (
                *(existing.evidence_event_ids if existing is not None else ()),
                *(str(event_id) for event_id in evidence_event_ids if str(event_id)),
            )
        )
    )
    relation = InstitutionalRelation(
        institution_a_id=institution_ids[0],
        institution_b_id=institution_ids[1],
        kind=kind,
        # Friendliness is the shared bilateral climate owned by institutional
        # relationship impacts.  Changing the relation's kind is not itself an
        # opinion about the counterparty, so an existing climate is carried
        # over unchanged and a brand new relation simply starts neutral.
        friendliness=existing.friendliness if existing is not None else 0,
        since_month=int(current_month),
        evidence_event_ids=evidence,
    )
    if existing is None:
        world.institutional_relations.add_relation(
            relation, world.institutional_authority
        )
    else:
        world.institutional_relations.replace_relation(
            relation, world.institutional_authority
        )
    return relation


def set_formal_war(
    world: Any,
    sect_a_id: int | str,
    sect_b_id: int | str,
    *,
    current_month: int,
    evidence_event_ids: Iterable[str],
) -> InstitutionalRelation:
    return _set_relation(
        world,
        sect_a_id,
        sect_b_id,
        kind=InstitutionalRelationKind.AT_WAR,
        current_month=current_month,
        evidence_event_ids=evidence_event_ids,
    )


def conclude_formal_war(
    world: Any,
    sect_a_id: int | str,
    sect_b_id: int | str,
    *,
    current_month: int,
    evidence_event_ids: Iterable[str],
) -> InstitutionalRelation:
    """End a war episode without touching any separately owned value.

    Only ``kind`` (and the month the neutral relation begins) is this
    transition's business.  ``friendliness`` is the shared relationship
    climate owned by institutional relationship impacts, so it is carried
    over unchanged: concluding a war is not itself an opinion about the
    counterparty, and prior evidence stays in place as history.
    """

    institution_ids = sorted(
        (sect_institution_id(sect_a_id), sect_institution_id(sect_b_id))
    )
    existing = world.institutional_relations.get_relation(*institution_ids)
    if existing is None:
        raise ValueError("cannot conclude a war for a relation that does not exist")
    if existing.kind is not InstitutionalRelationKind.AT_WAR:
        raise ValueError("cannot conclude a war for a relation that is not a war")
    evidence = tuple(
        dict.fromkeys(
            (
                *existing.evidence_event_ids,
                *(str(event_id) for event_id in evidence_event_ids if str(event_id)),
            )
        )
    )
    relation = InstitutionalRelation(
        institution_a_id=institution_ids[0],
        institution_b_id=institution_ids[1],
        kind=InstitutionalRelationKind.NEUTRAL,
        friendliness=existing.friendliness,
        since_month=int(current_month),
        evidence_event_ids=evidence,
    )
    world.institutional_relations.replace_relation(
        relation, world.institutional_authority
    )
    return relation


__all__ = [
    "STATUS_PEACE",
    "STATUS_WAR",
    "WAR_DECLARED_EVENT_TYPE",
    "active_sects",
    "are_sects_at_war",
    "conclude_formal_war",
    "get_sect_diplomacy_breakdown",
    "get_sect_diplomacy_state",
    "has_active_sect_institution",
    "negotiating_sect",
    "sect_by_id",
    "sect_institution_id",
    "sect_institution_ref",
    "sect_war_relation",
    "set_formal_war",
]

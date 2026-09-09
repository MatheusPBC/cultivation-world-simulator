"""Canonical owner for sect-to-member spirit-stone support."""

from __future__ import annotations

from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.utils.config import CONFIG


def support_amount() -> int:
    return max(0, int(getattr(CONFIG.sect, "support_amount", 300)))


def _member_region_id(avatar: Any) -> str | None:
    region = getattr(getattr(avatar, "tile", None), "region", None)
    if region is None:
        return None
    return str(getattr(region, "id", "")) or None


def is_eligible_support_member(
    sect: Any,
    avatar: Any,
    *,
    region_id: str | None = None,
    amount: int | None = None,
) -> bool:
    """Check only grounded facts; this function never changes either owner."""
    amount = support_amount() if amount is None else max(0, int(amount))
    if amount <= 0:
        return False
    if not getattr(sect, "is_active", False) or getattr(avatar, "is_dead", True):
        return False
    if getattr(avatar, "sect", None) is not sect or str(
        getattr(avatar, "id", "")
    ) not in getattr(sect, "members", {}):
        return False
    if region_id is not None and _member_region_id(avatar) != str(region_id):
        return False
    if int(getattr(sect, "magic_stone", 0)) < amount:
        return False
    return int(getattr(getattr(avatar, "magic_stone", None), "value", 0)) < amount


def eligible_member_ids(
    sect: Any, *, region_id: str, amount: int | None = None
) -> tuple[str, ...]:
    members = getattr(sect, "members", {}) or {}
    eligible = [
        avatar
        for avatar in members.values()
        if is_eligible_support_member(sect, avatar, region_id=region_id, amount=amount)
    ]
    return tuple(sorted((str(avatar.id) for avatar in eligible)))


def transfer_sect_member_support(
    sect: Any,
    avatar: Any,
    *,
    amount: int | None = None,
) -> bool:
    """Apply the sole support mutation used by annual and reactive paths."""
    amount = support_amount() if amount is None else max(0, int(amount))
    if not is_eligible_support_member(sect, avatar, amount=amount):
        return False
    sect.magic_stone -= amount
    avatar.magic_stone += amount
    return True


def _event(
    world: Any,
    sect: Any,
    avatar: Any,
    *,
    region_id: str,
    decision_event_id: str,
    condition_event_id: str,
    outcome: str,
    reason: str = "",
    deltas: list[StateDelta] | None = None,
) -> Event:
    event_type = (
        "sect_member_support_completed"
        if outcome == "completed"
        else "sect_member_support_blocked"
    )
    event = Event(
        world.month_stamp,
        (
            t(
                "{sect_name} supported {avatar_name} with {amount} spirit stones.",
                sect_name=sect.name,
                avatar_name=avatar.name,
                amount=support_amount(),
            )
            if outcome == "completed"
            else t("Sect member support was blocked: {reason}", reason=reason)
        ),
        related_avatars=[str(avatar.id)],
        related_sects=[int(sect.id)],
        event_type=event_type,
        render_key=event_type,
        render_params={
            "sect_id": str(sect.id),
            "member_id": str(avatar.id),
            "region_id": str(region_id),
            "decision_event_id": str(decision_event_id),
            "condition_event_id": str(condition_event_id),
            "outcome": outcome,
        },
        fact_kind=FactKind.STATE_TRANSITION
        if outcome == "completed"
        else FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={
            "deltas": [delta.to_dict() for delta in (deltas or [])],
            "outcome": outcome,
            "reason": reason,
            "amount": support_amount(),
        },
    )
    for cause_id, relation in (
        (decision_event_id, CausalRelation.MOTIVATED_BY),
        (condition_event_id, CausalRelation.TRIGGERED_BY),
    ):
        if cause_id and cause_id not in {
            link.cause_event_id for link in event.causal_links
        }:
            event.causal_links.append(
                CausalLink(
                    event_id=event.id, cause_event_id=str(cause_id), relation=relation
                )
            )
    return event


def execute_sect_member_support(
    context: Any,
    option: Any,
    *,
    decision_event_id: str,
    decision_event: Any = None,
) -> Event:
    """Validate authorship and the live offer, then spend the treasury.

    The whole operation lives here, not in a registry wrapper: a direct call
    is exactly as guarded as the dispatched one. The actor's own canonical
    decision must select this option, the cited id must be that decision, and
    the option must still be one the provider composes from current state --
    matched by canonical id, which also covers a treasury office that lost its
    holder, because the provider asks `can_actor_act_for` for it. Nothing is
    spent before all of that holds.
    """
    from src.systems.collective_affordances import _active_sect
    from src.systems.domain_affordance_registry import (
        DOMAIN_AFFORDANCES,
        StaleAffordanceError,
        validate_actor_decision,
    )

    if (
        str(getattr(option, "action_kind", "")) != "support_member"
        or str(getattr(option, "domain", "")) != str(context.domain)
        or getattr(option, "actor_ref", None) != context.actor_ref
    ):
        raise StaleAffordanceError("member support option is not this actor's")
    validate_actor_decision(decision_event, context, option, label="member support")
    if str(getattr(decision_event, "id", "")) != str(decision_event_id):
        raise StaleAffordanceError("member support decision id does not match")
    live = next(
        (
            item
            for item in DOMAIN_AFFORDANCES.compose(context)
            if str(item.action_kind) == "support_member"
            and str(item.id) == str(option.id)
        ),
        None,
    )
    if live is None or dict(live.parameters) != dict(option.parameters):
        raise StaleAffordanceError("member support is not currently offered")

    world = context.world
    sect = _active_sect(world, context.actor_ref.id)
    if sect is None:
        raise StaleAffordanceError("member support actor disappeared")
    member_id = str(option.parameters["member_id"])
    region_id = str(option.parameters["region_id"])
    condition_event_id = str(context.trigger_event.id)
    avatar = (getattr(sect, "members", {}) or {}).get(str(member_id))
    if avatar is None:
        return _event(
            world,
            sect,
            type("MissingMember", (), {"id": member_id, "name": member_id})(),
            region_id=region_id,
            decision_event_id=decision_event_id,
            condition_event_id=condition_event_id,
            outcome="blocked",
            reason="member is not a current sect member",
        )
    amount = support_amount()
    before_sect = int(getattr(sect, "magic_stone", 0))
    before_avatar = int(getattr(getattr(avatar, "magic_stone", None), "value", 0))
    if not is_eligible_support_member(sect, avatar, region_id=region_id, amount=amount):
        return _event(
            world,
            sect,
            avatar,
            region_id=region_id,
            decision_event_id=decision_event_id,
            condition_event_id=condition_event_id,
            outcome="blocked",
            reason="member is not alive, present, in need, or affordable",
        )
    if not transfer_sect_member_support(sect, avatar, amount=amount):
        return _event(
            world,
            sect,
            avatar,
            region_id=region_id,
            decision_event_id=decision_event_id,
            condition_event_id=condition_event_id,
            outcome="blocked",
            reason="support affordance became unavailable",
        )
    deltas = [
        StateDelta(
            owner_kind="sect",
            owner_id=str(sect.id),
            aspect="magic_stone",
            before=str(before_sect),
            after=str(sect.magic_stone),
            magnitude=-amount,
        ),
        StateDelta(
            owner_kind="avatar",
            owner_id=str(avatar.id),
            aspect="magic_stone",
            before=str(before_avatar),
            after=str(avatar.magic_stone.value),
            magnitude=amount,
        ),
    ]
    event = _event(
        world,
        sect,
        avatar,
        region_id=region_id,
        decision_event_id=decision_event_id,
        condition_event_id=condition_event_id,
        outcome="completed",
        deltas=deltas,
    )
    for delta in deltas:
        delta.event_id = event.id
    event.causal_payload["deltas"] = [delta.to_dict() for delta in deltas]
    return event


__all__ = [
    "eligible_member_ids",
    "execute_sect_member_support",
    "is_eligible_support_member",
    "support_amount",
    "transfer_sect_member_support",
]

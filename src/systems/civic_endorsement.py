"""One named person publicly endorsing a petition their city already filed.

Individual **support**, not leadership and not a completed civic movement. It
creates no followers, no organization, no faction, no force, no authority claim
and no new durable state: an avatar's endorsement is a fact, and the addressed
government comes to know it by formal notice. The fact itself is what prevents
a repeat -- there is no avatar-side reaction receipt, because an acting
`DomainReactionReceipt` requires a real `DomainAffordance` id and an avatar
acts through the action registry instead.

Two things this module is careful not to claim:

* Standing in the city now is **not** evidence of having witnessed anything
  earlier. A recent local public petition is treated as *notice available now*
  -- the kind of public matter a person in that city could act on -- and the
  window, the source and the condition are all re-read from canonical stores.
  No avatar-level knowledge owner is invented to stand in for that.
* Recording institutional knowledge does **not** by itself put a fact in front
  of the government's decision context: `decision_context` projects only
  *memories* whose facts are known, and a fact recorded without memory factors
  has no memory. So the endorsement is wired as its own government trigger,
  with its own response receipt, rather than trusting knowledge to carry it.
"""

from __future__ import annotations

from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.institution import KnowledgeChannel
from src.classes.mechanical_language import DomainReactionReceipt, EntityRef

ENDORSEMENT_EVENT_TYPE = "civil_public_petition_endorsed"
ENDORSEMENT_RESPONSE_RECEIPT_DOMAIN = "civic_endorsement_response"
ENDORSE_ACTION_NAME = "EndorsePublicPetition"
# How long a filed petition stays public notice a resident could act on. The
# same window the government uses to recognise an unanswered petition.
ENDORSEMENT_WINDOW_MONTHS = 12


def _stored_event(world: Any, event_id: str) -> Event | None:
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_event_by_id", None)
    if not callable(getter) or not str(event_id):
        return None
    return getter(str(event_id))


def _authored_petition(world: Any, region: Any, condition: Any, event_id: str):
    """The petition this id names, only if the people really filed it.

    Authorship is not re-derived here: `prior_local_petition` already resolves
    the population's own audited decision for this grievance, and there is at
    most one petition per condition instance, so requiring the selected id to
    be exactly that petition is the whole check.
    """
    from src.systems.civil_petition import prior_local_petition

    petition = prior_local_petition(world, region, condition=condition)
    if petition is None or str(petition.id) != str(event_id):
        return None
    return petition


def _remember_endorsement_this_step(world: Any, event: Event) -> None:
    """Hold **this month's** own endorsement facts until the finalizer stores them.

    A `DomainReactionReceipt` is not available for this: an acting receipt
    requires a real `DomainAffordance` id, and an avatar acts through the
    action registry, so there is none. Inventing an id, or writing a
    `maintain` receipt for something that really acted, would both be lies in
    canonical state. The durable record is the Event itself; this buffer only
    covers the gap before the finalizer persists it.

    Scoped to the current month and nothing more. Persisted facts already
    cover the whole notice window, so keeping a year of duplicated events in
    `world.__dict__` -- which `SimulationMonthCheckpoint` captures whole --
    would be waste and a second truth. A rolled-back month drops it, and
    nothing here is ever written to a save.
    """
    transient = getattr(world, "_civic_endorsement_events_this_step", None)
    if not isinstance(transient, dict):
        transient = {}
        setattr(world, "_civic_endorsement_events_this_step", transient)
    month = int(world.month_stamp)
    for event_id in [
        key
        for key, item in transient.items()
        if int(getattr(item, "month_stamp", -1)) != month
    ]:
        del transient[event_id]
    transient[event.id] = event


def known_endorsement_events(world: Any) -> list[Event]:
    """Endorsement facts in the notice window: persisted, plus this month's.

    Read failures are **not** swallowed. "I could not read the store" is not
    "nobody ever endorsed", and answering the second when the first is true
    would let a replay through, so the error propagates to the caller.
    """
    month = int(world.month_stamp)
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_events_between_months", None)
    if not callable(getter):
        raise RuntimeError("endorsement history requires a readable event store")
    stored = list(getter(month - ENDORSEMENT_WINDOW_MONTHS + 1, month))
    transient = getattr(world, "_civic_endorsement_events_this_step", {}) or {}
    seen: set[str] = set()
    events: list[Event] = []
    for event in [
        *stored,
        # Only this month's, so a stale buffer entry can never stand in for
        # history the store owns.
        *(
            item
            for item in transient.values()
            if int(getattr(item, "month_stamp", -1)) == month
        ),
    ]:
        if event.id in seen:
            continue
        seen.add(event.id)
        events.append(event)
    return events


def already_endorsed(world: Any, avatar_id: str, petition_event_id: str) -> bool:
    """Whether this avatar's endorsement of this petition already happened.

    Answered from the canonical facts themselves -- the persisted ones plus
    this step's, before the finalizer runs -- not from a receipt this domain
    has no legitimate affordance to key.
    """
    for event in known_endorsement_events(world):
        payload = endorsement_payload(event)
        if (
            payload is not None
            and str(payload.get("avatar_id", "")) == str(avatar_id)
            and str(payload.get("petition_event_id", "")) == str(petition_event_id)
        ):
            return True
    return False


def get_endorse_petition_blocker(
    world: Any, avatar: Any, cause_event_id: str
) -> str | None:
    """Why this avatar cannot endorse this petition right now, or nothing.

    Every clause is read from canonical state at the moment it is asked, so the
    same function serves `can_start` and the execution boundary. Both resolve
    the petition **fresh by id**, so a caller cannot hand in a fabricated
    object. Returning `None` means the endorsement really is available.
    """
    return _blocker(world, avatar, cause_event_id)


def _blocker(
    world: Any, avatar: Any, cause_event_id: str, *, petition: Event | None = None
) -> str | None:
    """The rule itself.

    ``petition`` is an internal shortcut for the menu builder, which has just
    read the very same row out of a bounded window scan; supplying it avoids a
    second lookup per candidate for every avatar, every month. It is private
    precisely so no caller can substitute a forged object for the stored one.
    """
    from src.classes.environment.region import CityRegion
    from src.systems.civil_petition import governing_institution_ref, petition_payload

    # A living person the world actually holds. A detached object is nobody.
    if avatar is None or bool(getattr(avatar, "is_dead", False)):
        return "A departed voice cannot speak for anyone"
    getter = getattr(getattr(world, "avatar_manager", None), "get_avatar", None)
    if not callable(getter) or getter(str(getattr(avatar, "id", ""))) is not avatar:
        return "Only someone the world knows can speak for anyone"

    if petition is None:
        petition = _stored_event(world, cause_event_id)
    elif str(getattr(petition, "id", "")) != str(cause_event_id):
        return "That public petition does not exist"
    if petition is None:
        return "That public petition does not exist"
    payload = petition_payload(petition)
    if payload is None:
        return "That public petition does not exist"
    month = int(world.month_stamp)
    if not 0 <= month - int(getattr(petition, "month_stamp", 0)) < (
        ENDORSEMENT_WINDOW_MONTHS
    ):
        return "That petition is no longer public notice"
    region_id = str(payload.get("region_id", ""))
    region = (
        getattr(getattr(world, "map", None), "regions", {}) or {}
    ).get(int(region_id)) if region_id.isdigit() else None
    if not isinstance(region, CityRegion):
        return "That petition names no city"
    # Present where the petition was filed. This is a fact about now, not a
    # claim that the avatar saw the filing.
    here = getattr(getattr(avatar, "tile", None), "region", None)
    if here is None or str(getattr(here, "id", "")) != str(region.id):
        return "Only someone in that city can endorse its petition"
    # The grievance must still be live: endorsing a settled matter addresses
    # nothing.
    condition = next(
        (
            item
            for item in world.mechanical_language.get_active_conditions(
                EntityRef("region", str(region.id)), month
            )
            if str(item.id) == str(payload.get("condition_instance_id", ""))
        ),
        None,
    )
    if condition is None:
        return "That grievance is no longer active"
    # The people must really have filed it. A well-shaped payload is a claim.
    if _authored_petition(world, region, condition, str(petition.id)) is None:
        return "That petition was never filed by these people"
    # The addressed institution must still stand, and must still be the one
    # that administers this region. A new holder of the same office is fine --
    # the petition was addressed to the office -- but a region that changed
    # hands does not re-address a historical petition to its new controller.
    reference = payload.get("addressed_institution_ref")
    institution_id = str(payload.get("addressed_institution_id", ""))
    authority = getattr(world, "institutional_authority", None)
    if (
        not isinstance(reference, dict)
        or not institution_id
        or authority is None
    ):
        return "That petition addresses no standing institution"
    addressed = authority.get_institution(institution_id)
    current_ref = governing_institution_ref(world, region)
    if (
        addressed is None
        or not addressed.is_active(month)
        or current_ref is None
        or addressed.owner_ref != current_ref
        or str(reference.get("kind")) != current_ref.kind
        or str(reference.get("id")) != current_ref.id
    ):
        return "That petition addresses no standing institution"
    if already_endorsed(world, str(avatar.id), str(petition.id)):
        return "You have already endorsed that petition"
    return None


def can_endorse_public_petition(world: Any, avatar: Any) -> bool:
    """Whether any petition at all is endorsable by this avatar right now."""
    return bool(endorsable_petitions(world, avatar))


def endorsable_petitions(world: Any, avatar: Any) -> list[Event]:
    """The petitions this avatar could really endorse, oldest first.

    Called from `get_action_infos` for every avatar every month, so it is
    written to stay cheap: the avatar is rejected outright before any store is
    touched, and the bounded window scan is filtered down to petitions of this
    avatar's own city before the rule -- which is the expensive part -- is
    asked at all. No new cache and no persistent state.
    """
    from src.classes.environment.region import CityRegion
    from src.systems.civil_petition import PETITION_EVENT_TYPE

    # Cheapest rejections first, with no query at all.
    if avatar is None or bool(getattr(avatar, "is_dead", False)):
        return []
    getter = getattr(getattr(world, "avatar_manager", None), "get_avatar", None)
    if not callable(getter) or getter(str(getattr(avatar, "id", ""))) is not avatar:
        return []
    here = getattr(getattr(avatar, "tile", None), "region", None)
    if not isinstance(here, CityRegion):
        return []
    region_id = str(here.id)

    manager = getattr(world, "event_manager", None)
    window = getattr(manager, "get_events_between_months", None)
    if not callable(window):
        return []
    month = int(world.month_stamp)
    try:
        stored = window(month - ENDORSEMENT_WINDOW_MONTHS + 1, month)
    except Exception:
        return []

    candidates: list[Event] = []
    seen: set[str] = set()
    for event in stored:
        # Pre-filter on the row already in hand: type first, then this city.
        if str(getattr(event, "event_type", "")) != PETITION_EVENT_TYPE:
            continue
        if event.id in seen:
            continue
        seen.add(event.id)
        container = getattr(event, "causal_payload", None)
        payload = (
            container.get("civil_petition") if isinstance(container, dict) else None
        )
        if not isinstance(payload, dict):
            continue
        if str(payload.get("region_id", "")) != region_id:
            continue
        candidates.append(event)

    found = [
        event
        for event in sorted(
            candidates,
            key=lambda item: (int(getattr(item, "month_stamp", 0)), str(item.id)),
        )
        # The row is passed through, so the rule does not re-fetch what the
        # scan already returned.
        if _blocker(world, avatar, str(event.id), petition=event) is None
    ]
    return found


def record_public_endorsement(
    world: Any, avatar: Any, cause_event_id: str, *, action_origin: Any
) -> Event | None:
    """The endorsement fact, the notice given, and the dedup, as one act.

    Runs at the execution boundary, not at ``start``: the engine writes
    ``ActionOrigin.ACTOR_CHOICE`` onto the committed action only after
    ``start`` returns, so authorship can only be proved here. Two independent
    witnesses are required, neither forgeable by prose or a direct call -- the
    shared owner in `avatar_decision` must find this exact action with this
    exact parameter in the avatar's own audited decision, and the blocker must
    still pass now. The fact, the formal notice and this month's dedup buffer
    are written together, so no caller can produce the fact and skip what
    prevents a replay. There is no avatar-side reaction receipt: an acting
    `DomainReactionReceipt` requires a real `DomainAffordance` id, which an
    action-registry act does not have, so the Event is the record.
    """
    from src.classes.action_runtime import ActionOrigin
    from src.i18n import t
    from src.systems.avatar_decision import attach_validated_actor_decision
    from src.systems.civil_petition import petition_payload
    from src.systems.institutional_memory import record_known_fact

    # No permissive default: a missing, reactive or restored origin is not a
    # deliberate public act, and produces no fact, no notice and no buffer
    # entry rather than an unauthored one.
    if action_origin is not ActionOrigin.ACTOR_CHOICE:
        return None
    if get_endorse_petition_blocker(world, avatar, cause_event_id) is not None:
        return None
    petition = _stored_event(world, cause_event_id)
    assert petition is not None
    payload = petition_payload(petition)
    region_id = str(payload["region_id"])
    region = world.map.regions[int(region_id)]
    institution_id = str(payload["addressed_institution_id"])
    reference = dict(payload["addressed_institution_ref"])

    event = Event(
        world.month_stamp,
        t(
            "{avatar} publicly endorses the petition of {region}.",
            avatar=getattr(avatar, "name", str(avatar.id)),
            region=getattr(region, "name", region_id),
        ),
        related_avatars=[str(avatar.id)],
        event_type=ENDORSEMENT_EVENT_TYPE,
        # Endorsing moves no owner: it is a public act that happened, and the
        # only deltas it carries are the ones institutional knowledge appends
        # for itself.
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "region_id": region_id,
            "avatar_id": str(avatar.id),
            "avatar_name": str(getattr(avatar, "name", avatar.id)),
        },
        causal_payload={
            "deltas": [],
            "civic_endorsement": {
                "avatar_id": str(avatar.id),
                # A historical snapshot of the name as it stood, so a later
                # rename or death does not rewrite what was recorded.
                "avatar_name": str(getattr(avatar, "name", avatar.id)),
                "region_id": region_id,
                "condition_instance_id": str(payload["condition_instance_id"]),
                "petition_event_id": str(petition.id),
                "addressed_institution_id": institution_id,
                "addressed_institution_ref": reference,
            },
        },
    )
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=str(petition.id),
            relation=CausalRelation.RESPONSE_TO,
        )
    )
    # Authorship, or no fact at all. A consequence credited to a decision that
    # did not choose it would be worse than none.
    cited = attach_validated_actor_decision(
        event,
        avatar,
        action_name=ENDORSE_ACTION_NAME,
        params={"cause_event_id": str(cause_event_id)},
        action_origin=ActionOrigin.ACTOR_CHOICE,
    )
    if cited is None:
        return None
    # Addressed to the government, so formal notice is the honest channel: the
    # endorser is not necessarily a member of anything.
    record_known_fact(
        world, event, (institution_id,), channel=KnowledgeChannel.FORMAL_NOTICE
    )
    # Fact, notice and the no-repeat record are written together, so no caller
    # can produce the fact and skip what prevents a replay.
    _remember_endorsement_this_step(world, event)
    return event


# --------------------------------------------------------------------------
# The government's side: its own trigger, and one answer per endorsement
# --------------------------------------------------------------------------


def endorsement_payload(event: Event) -> dict | None:
    """The endorsement this event really is, or nothing.

    A matching event type is not authorship: the fact must be the kind of fact
    an endorsement is, and carry a complete record of who endorsed what.
    """
    if (
        str(getattr(event, "event_type", "")) != ENDORSEMENT_EVENT_TYPE
        or getattr(event, "fact_kind", None) is not FactKind.OCCURRENCE
        or getattr(event, "causal_origin", None) is not CausalOrigin.ACTOR_DECISION
        or bool(getattr(event, "is_story", False))
    ):
        return None
    container = getattr(event, "causal_payload", None)
    if not isinstance(container, dict):
        return None
    payload = container.get("civic_endorsement")
    if not isinstance(payload, dict):
        return None
    reference = payload.get("addressed_institution_ref")
    if (
        not str(payload.get("avatar_id", ""))
        or not str(payload.get("region_id", ""))
        or not str(payload.get("condition_instance_id", ""))
        or not str(payload.get("petition_event_id", ""))
        or not str(payload.get("addressed_institution_id", ""))
        or not isinstance(reference, dict)
    ):
        return None
    return payload


def canonical_endorsement_payload(world: Any, event: Event) -> dict | None:
    """The same reading, but of the fact the world actually stores.

    A loose object handed to the dispatcher or the registry authorizes nothing.
    The government answers on a later cycle than the endorsement, so the fact
    is genuinely in the store by then and no overlay is needed.
    """
    event_id = str(getattr(event, "id", ""))
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_event_by_id", None)
    if not event_id or not callable(getter):
        return None
    resolved = getter(event_id)
    return endorsement_payload(resolved) if resolved is not None else None


def endorsement_response_receipt_id(
    endorsement_event_id: str, institution_id: str
) -> str:
    """One government answer per institution per endorsement, ever.

    Separate from the original petition's response receipt, which is never
    reset: a new endorsement is a new thing addressed to the government, and
    answering the petition did not answer this.
    """
    return DomainReactionReceipt.create(
        f"civic-endorsement-response:{institution_id}:{endorsement_event_id}",
        ENDORSEMENT_RESPONSE_RECEIPT_DOMAIN,
        str(endorsement_event_id),
        decision="maintain",
        affordance_id=None,
    ).id


def endorsement_already_answered(
    world: Any, endorsement_event_id: str, institution_id: str
) -> bool:
    return (
        endorsement_response_receipt_id(endorsement_event_id, institution_id)
        in world.mechanical_language.reaction_receipts
    )


def mark_endorsement_answered(
    world: Any,
    endorsement_event_id: str,
    institution_id: str,
    *,
    decision_event_id: str,
    decision: str,
    affordance_id: str | None,
) -> None:
    """Close this endorsement for this institution, whatever it decided."""
    receipt = DomainReactionReceipt.create(
        f"civic-endorsement-response:{institution_id}:{endorsement_event_id}",
        ENDORSEMENT_RESPONSE_RECEIPT_DOMAIN,
        str(endorsement_event_id),
        decision=decision if affordance_id else "maintain",
        affordance_id=affordance_id,
        decision_event_ids=(decision_event_id,) if decision_event_id else (),
        completed=True,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt


def pending_endorsements(world: Any) -> list[tuple[Event, dict]]:
    """Endorsements this world's governments know about and have not answered."""
    month = int(world.month_stamp)
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_events_between_months", None)
    stored = (
        getter(month - ENDORSEMENT_WINDOW_MONTHS + 1, month)
        if callable(getter)
        else []
    )
    seen: set[str] = set()
    pending: list[tuple[Event, dict]] = []
    for event in stored:
        if event.id in seen:
            continue
        seen.add(event.id)
        payload = endorsement_payload(event)
        if payload is None:
            continue
        institution_id = str(payload.get("addressed_institution_id") or "")
        if not institution_id:
            continue
        if not world.institutional_knowledge.contains(institution_id, event.id):
            continue
        if endorsement_already_answered(world, event.id, institution_id):
            continue
        pending.append((event, payload))
    return pending


def active_condition_for(world: Any, region: Any, payload: dict):
    """The grievance's condition if it is still live, else nothing."""
    instance_id = str(payload.get("condition_instance_id", ""))
    if not instance_id:
        return None
    return next(
        (
            item
            for item in world.mechanical_language.get_active_conditions(
                EntityRef("region", str(region.id)), int(world.month_stamp)
            )
            if str(item.id) == instance_id
        ),
        None,
    )


def endorsement_fact_context(
    world: Any, trigger_event: Event, region: Any
) -> dict[str, Any]:
    """The endorsement as history, plus what the city reads right now.

    Who endorsed and what they endorsed come from the fact; the petition's own
    grievance and the current condition reading come from the owners as they
    stand. One person spoke; nothing here implies a following.
    """
    payload = endorsement_payload(trigger_event)
    if payload is None:
        return {}
    avatar_id = str(payload["avatar_id"])
    manager = getattr(world, "avatar_manager", None)
    getter = getattr(manager, "get_avatar", None)
    avatar = getter(avatar_id) if callable(getter) else None
    condition = active_condition_for(world, region, payload)
    petition = _stored_event(world, str(payload["petition_event_id"]))
    return {
        "civic_endorsement": {
            "endorsement_event_id": str(trigger_event.id),
            "endorsed_month": int(trigger_event.month_stamp),
            "current_month": int(world.month_stamp),
            "region_id": str(payload["region_id"]),
            "petition_event_id": str(payload["petition_event_id"]),
            "petition_month": (
                None if petition is None else int(petition.month_stamp)
            ),
            # The endorser as recorded, and whether that person is still here
            # to be answered. A single named voice, never a count.
            "endorser_avatar_id": avatar_id,
            "endorser_name": str(payload.get("avatar_name", avatar_id)),
            "endorser_alive": bool(
                avatar is not None and not getattr(avatar, "is_dead", False)
            ),
            # The grievance right now, so an answer is not built on a reading
            # that has since moved.
            "condition_instance_id": str(payload["condition_instance_id"]),
            "condition_still_active": condition is not None,
            "condition_intensity_now": (
                None if condition is None else float(condition.intensity)
            ),
        }
    }


__all__ = [
    "ENDORSEMENT_EVENT_TYPE",
    "ENDORSEMENT_WINDOW_MONTHS",
    "ENDORSE_ACTION_NAME",
    "active_condition_for",
    "already_endorsed",
    "can_endorse_public_petition",
    "canonical_endorsement_payload",
    "endorsable_petitions",
    "endorsement_already_answered",
    "endorsement_fact_context",
    "endorsement_payload",
    "known_endorsement_events",
    "endorsement_response_receipt_id",
    "get_endorse_petition_blocker",
    "mark_endorsement_answered",
    "pending_endorsements",
    "record_public_endorsement",
]

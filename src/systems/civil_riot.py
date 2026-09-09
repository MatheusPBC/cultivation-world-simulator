"""A riot: an aggrieved population damaging urban fabric it can reach.

Wave 10's third civil rung. A riot needs no leader, and this creates none: the
subject is the same aggregate population that petitions and stops working. No
organization, no faction, no troops, no repression, no population inventory,
and no escalation scripted from a petition or a stoppage -- the option stands
on its own material grounding and is offered in parallel with the others.

The law below is an explicit, calibratable **mechanical approximation**, not
proven physics. Every term is either declared in config or read from an
existing owner:

* how many people are aggrieved is an engine-owned *aggregate estimate* from
  declared demand and current service, never a census of named individuals;
* how damageable the fabric is comes only from the asset's declared
  `UrbanCrowdDamageProfile`; an absent profile blocks the action for lack of a
  basis, which is ignorance and not immunity;
* administrative capacity, service capacity and service quality play no part:
  serving people is not withstanding them.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.institution import KnowledgeChannel
from src.classes.mechanical_language import DomainReactionReceipt, EntityRef

RIOT_ACTION = "join_public_riot"
RIOT_EVENT_TYPE = "civil_riot_occurred"
RIOT_RECEIPT_DOMAIN = "civil_riot"
RIOT_RESPONSE_RECEIPT_DOMAIN = "civil_riot_response"

# The share of the aggrieved aggregate that a single riot can put in the
# street, reusing the ceiling the work stoppage already established rather
# than introducing a second figure for collective participation.
MAX_RIOT_PARTICIPATION = 0.20
# The ceiling on integrity lost to one riot, set equal to
# `MAX_MAINTENANCE_IMPROVEMENT` so damage and repair live on the same scale of
# the same owner. No new magnitude is invented.
MAX_RIOT_DAMAGE = 0.10


def _city_state(region: Any):
    return getattr(region, "city_state", None)


def service_shortfall(region: Any, capability_id: str) -> float | None:
    """The unmet share of declared demand for one capability, or nothing.

    An engine-owned aggregate estimate: `service_access` compares declared
    demand against current effective capacity. It is not a count of deprived
    people and is never presented as one.
    """
    state = _city_state(region)
    if state is None:
        return None
    try:
        access = state.service_access(str(capability_id), float(region.population))
    except (AttributeError, TypeError, ValueError):
        return None
    if access is None:
        return None
    return max(0.0, min(1.0, 1.0 - float(access)))


def aggrieved_crowd_wan(region: Any, asset: Any, capability_id: str) -> float:
    """The crowd this grievance could plausibly put in front of this asset.

    In 万, the same unit `region.population` uses. Estimated, not counted:
    the district's declared population weight times the unmet share of
    declared demand, capped by `MAX_RIOT_PARTICIPATION`.
    """
    state = _city_state(region)
    shortfall = service_shortfall(region, capability_id)
    if state is None or not shortfall:
        return 0.0
    try:
        district_wan = float(
            state.district_population(str(asset.district_id), float(region.population))
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return 0.0
    return max(0.0, district_wan * shortfall * MAX_RIOT_PARTICIPATION)


def riot_damage(region: Any, asset: Any, capability_id: str) -> float:
    """The bounded integrity loss this riot would really inflict.

    Zero whenever any material term is missing: no declared profile, nobody in
    the district, no unmet demand, or nothing left to break.
    """
    profile = getattr(asset, "crowd_damage_profile", None)
    if profile is None:
        return 0.0
    crowd_wan = aggrieved_crowd_wan(region, asset, capability_id)
    if crowd_wan <= 0.0:
        return 0.0
    effort = float(profile.breach_effort_wan)
    if effort <= 0.0:
        return 0.0
    return max(0.0, min(
        MAX_RIOT_DAMAGE,
        crowd_wan * float(profile.crowd_exposure) / effort,
        float(asset.integrity),
    ))


def projected_service_access(
    region: Any, asset: Any, capability_id: str, damage: float
) -> tuple[float | None, float | None]:
    """Service access now, and what it becomes if this damage lands.

    Computed from the owner's own formula on a hypothetical copy, so the menu
    can state the self-harm instead of only naming a damage figure. Nothing is
    mutated, and the forecast is an estimate like the crowd size is.
    """
    from dataclasses import replace

    state = _city_state(region)
    before = state.service_access(
        str(capability_id), float(region.population)
    ) if state is not None else None
    if state is None or before is None:
        return None, None
    weakened = replace(
        asset, integrity=max(0.0, float(asset.integrity) - float(damage))
    )
    hypothetical = replace(
        state,
        assets=tuple(
            weakened if item.id == asset.id else item for item in state.assets
        ),
    )
    after = hypothetical.service_access(
        str(capability_id), float(region.population)
    )
    return float(before), (None if after is None else float(after))


def riotable_targets(
    world: Any, region: Any, condition: Any, *, overlays: Any = None
) -> tuple[tuple[Any, str, float], ...]:
    """Every asset a grounded riot could really damage, with its damage.

    Each entry is `(asset, capability_id, damage)`. The capability is resolved
    from the condition's own metric evidence, never from a name; the asset must
    provide it, declare a crowd damage profile, and stand where people are.
    """
    from src.systems.city_interpreter import derive_eligible_capability_ids
    from src.systems.civil_petition import can_file_public_petition_basis

    if not can_file_public_petition_basis(
        world, region, condition, overlays=overlays
    ):
        return ()
    # One riot per grievance, checked here so a direct owner call cannot replay
    # a riot that already happened.
    if already_rioted(world, str(region.id), str(condition.id)):
        return ()
    state = _city_state(region)
    if state is None:
        return ()
    capabilities = set(
        derive_eligible_capability_ids(world, region, condition, state.assets)
    )
    if not capabilities:
        return ()
    targets: list[tuple[Any, str, float]] = []
    for asset in state.assets:
        if getattr(asset, "crowd_damage_profile", None) is None:
            continue
        for capability_id in sorted(capabilities & set(asset.capability_ids)):
            damage = riot_damage(region, asset, capability_id)
            if damage > 0.0:
                targets.append((asset, capability_id, damage))
                break
    return tuple(targets)


def riot_receipt_id(region_id: str, condition_instance_id: str) -> str:
    """One riot per region per condition instance."""
    return DomainReactionReceipt.create(
        f"civil-riot:{region_id}:{condition_instance_id}",
        RIOT_RECEIPT_DOMAIN,
        str(condition_instance_id),
        decision="maintain",
        affordance_id=None,
    ).id


def already_rioted(world: Any, region_id: str, condition_instance_id: str) -> bool:
    return (
        riot_receipt_id(region_id, condition_instance_id)
        in world.mechanical_language.reaction_receipts
    )


def can_join_public_riot(
    world: Any, region: Any, condition: Any, *, overlays: Any = None
) -> bool:
    """Whether a grounded riot is available at all for this grievance.

    The spent-receipt check lives in `riotable_targets`, so every caller --
    the menu, the owner, and any direct call -- gets it.
    """
    return bool(riotable_targets(world, region, condition, overlays=overlays))


def _damage_memory_factors(event: Event) -> dict[str, float]:
    """The memory factors this damage really supports, and nothing more.

    `relative_scale` is the **observed integrity loss itself**, read from the
    canonical `urban_asset_integrity` delta on the city's own 0..1 integrity
    scale. It is not divided by `MAX_RIOT_DAMAGE`: an execution cap is a limit
    on what one riot may do, not a scale for how large the loss was, and
    dividing by it would amplify a small loss into a large memory.

    The other three factors are frozen at zero because nothing supports them.
    No office, institution or control changed, so `institutional_change` is
    zero. No commitment exists, so `commitment_breach` is zero. And a generic
    urban asset is not an identity anchor, so `identity_anchor_impact` is zero
    -- claiming otherwise would make every broken roof a wound to what the
    city is.

    This only *reads* the transition the damage owner already applied. The
    integrity loss happened in `city_damage.execute_crowd_damage`; nothing
    here mutates anything, and a refusal below means no memory is written
    rather than any state being rolled back.

    Raises when the fact and its delta disagree, rather than remembering a
    magnitude no owner transition supports. The canonical path always
    satisfies these, so this stays a light coherence read and deliberately
    not a second validator of the damage owner.
    """
    import math

    payload = (event.causal_payload or {}).get("civil_riot")
    if not isinstance(payload, dict):
        raise ValueError("riot memory requires a riot fact")
    region_id = str(payload.get("region_id", ""))
    deltas = [
        item
        for item in ((event.causal_payload or {}).get("deltas") or [])
        if isinstance(item, Mapping)
        and str(item.get("aspect")) == "urban_asset_integrity"
        and str(item.get("event_id")) == str(event.id)
        and str(item.get("owner_kind")) == "region"
        and str(item.get("owner_id")) == region_id
    ]
    if len(deltas) != 1:
        raise ValueError("riot memory requires exactly one integrity delta")
    delta = deltas[0]
    before = float(delta["before"])
    after = float(delta["after"])
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0 for value in (before, after)
    ):
        raise ValueError("riot memory requires integrity endpoints in 0..1")
    observed = before - after
    if not 0.0 < observed <= 1.0:
        raise ValueError("riot memory requires a real, bounded integrity loss")
    # The three canonical statements of the same loss must agree: the delta's
    # endpoints, its recorded magnitude, and the payload's damage figure. A
    # non-finite claim fails the finiteness test first, because `abs(NaN) > t`
    # is False and would otherwise pass silently.
    for claimed in (float(delta["magnitude"]), float(payload["damage"])):
        if not math.isfinite(claimed) or abs(claimed - observed) > 1e-9:
            raise ValueError("riot memory found an incoherent integrity delta")
    return {
        "relative_scale": observed,
        "institutional_change": 0.0,
        "commitment_breach": 0.0,
        "identity_anchor_impact": 0.0,
    }


def record_riot_aftermath(
    world: Any,
    *,
    region: Any,
    condition: Any,
    event: Event,
    decision_event_id: str,
    affordance_id: str,
) -> Event:
    """What the riot fact leaves behind: knowledge, memory, and one receipt.

    The fact itself, its damage and its delta belong to
    `city_damage.execute_crowd_damage`, which already revalidated the decision
    and re-derived the amount. This adds only what the civil vertical owns.

    The memory exists because a riot is the one civil fact that really damaged
    something: without it, the damage vanished from every later institutional
    decision the moment the response receipt closed, since `decision_context`
    projects memories rather than raw known facts.
    """
    from src.systems.civil_petition import governing_institution_ref
    from src.systems.institutional_memory import record_known_fact

    payload = event.causal_payload.get("civil_riot")
    if not isinstance(payload, dict):
        raise ValueError("riot aftermath requires a riot fact")
    # A broken building is a public fact, and only the institution that really
    # administers this region learns it. No memory is fabricated.
    institution_ref = governing_institution_ref(world, region)
    institution = (
        world.institutional_authority.get_institution_for_owner(institution_ref)
        if institution_ref is not None
        else None
    )
    if institution is not None:
        payload["addressed_institution_id"] = institution.id
        payload["addressed_institution_ref"] = institution_ref.to_dict()
        record_known_fact(
            world,
            event,
            (institution.id,),
            factors=_damage_memory_factors(event),
            channel=KnowledgeChannel.PUBLIC_FACT,
        )
    receipt = DomainReactionReceipt.create(
        f"civil-riot:{region.id}:{condition.id}",
        RIOT_RECEIPT_DOMAIN,
        str(condition.id),
        decision="act",
        affordance_id=str(affordance_id),
        decision_event_ids=(str(decision_event_id),),
        completed=True,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt
    return event


# --------------------------------------------------------------------------
# The government's side: discovery and one answer per riot
# --------------------------------------------------------------------------


def riot_payload(event: Event) -> dict | None:
    """The riot this event really is, or nothing.

    A matching event type is not authorship: the fact must be the kind of fact
    a riot is, and carry a complete, coherent record of the damage.
    """
    if (
        str(getattr(event, "event_type", "")) != RIOT_EVENT_TYPE
        or getattr(event, "fact_kind", None) is not FactKind.STATE_TRANSITION
        or getattr(event, "causal_origin", None) is not CausalOrigin.ACTOR_DECISION
        or bool(getattr(event, "is_story", False))
    ):
        return None
    container = getattr(event, "causal_payload", None)
    if not isinstance(container, dict):
        return None
    payload = container.get("civil_riot")
    if not isinstance(payload, dict):
        return None
    reference = payload.get("addressed_institution_ref")
    try:
        damage = float(payload["damage"])
        exposure = float(payload["crowd_exposure"])
        effort = float(payload["breach_effort_wan"])
    except (KeyError, TypeError, ValueError):
        return None
    if (
        not str(payload.get("region_id", ""))
        or not str(payload.get("condition_instance_id", ""))
        or not str(payload.get("asset_id", ""))
        or not str(payload.get("capability_id", ""))
        or not str(payload.get("addressed_institution_id", ""))
        or not isinstance(reference, dict)
        or not 0.0 < damage <= MAX_RIOT_DAMAGE
        or not 0.0 <= exposure <= 1.0
        or effort <= 0.0
    ):
        return None
    return payload


def canonical_riot_payload(world: Any, event: Event) -> dict | None:
    """The same reading, but of the fact the world actually stores.

    A loose object handed to the dispatcher or the registry authorizes nothing.
    The government answers on a later cycle than the riot, so the fact is
    genuinely in the store by then and no overlay is needed.
    """
    event_id = str(getattr(event, "id", ""))
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_event_by_id", None)
    if not event_id or not callable(getter):
        return None
    resolved = getter(event_id)
    return riot_payload(resolved) if resolved is not None else None


def riot_response_receipt_id(riot_event_id: str, institution_id: str) -> str:
    """One government answer per institution per riot, ever."""
    return DomainReactionReceipt.create(
        f"civil-riot-response:{institution_id}:{riot_event_id}",
        RIOT_RESPONSE_RECEIPT_DOMAIN,
        str(riot_event_id),
        decision="maintain",
        affordance_id=None,
    ).id


def riot_already_answered(
    world: Any, riot_event_id: str, institution_id: str
) -> bool:
    return (
        riot_response_receipt_id(riot_event_id, institution_id)
        in world.mechanical_language.reaction_receipts
    )


def mark_riot_answered(
    world: Any,
    riot_event_id: str,
    institution_id: str,
    *,
    decision_event_id: str,
    decision: str,
    affordance_id: str | None,
) -> None:
    """Close this riot for this institution, whatever it decided."""
    receipt = DomainReactionReceipt.create(
        f"civil-riot-response:{institution_id}:{riot_event_id}",
        RIOT_RESPONSE_RECEIPT_DOMAIN,
        str(riot_event_id),
        decision=decision if affordance_id else "maintain",
        affordance_id=affordance_id,
        decision_event_ids=(decision_event_id,) if decision_event_id else (),
        completed=True,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt


def pending_riots(world: Any) -> list[tuple[Event, dict]]:
    """Riots this world's governments know about and have not answered."""
    from src.systems.civil_petition import PETITION_RESPONSE_WINDOW_MONTHS

    month = int(world.month_stamp)
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_events_between_months", None)
    stored = (
        getter(month - PETITION_RESPONSE_WINDOW_MONTHS + 1, month)
        if callable(getter)
        else []
    )
    seen: set[str] = set()
    pending: list[tuple[Event, dict]] = []
    for event in stored:
        if event.id in seen:
            continue
        seen.add(event.id)
        payload = riot_payload(event)
        if payload is None:
            continue
        institution_id = str(payload.get("addressed_institution_id") or "")
        if not institution_id:
            continue
        if not world.institutional_knowledge.contains(institution_id, event.id):
            continue
        if riot_already_answered(world, event.id, institution_id):
            continue
        pending.append((event, payload))
    return pending


def active_condition_for(world: Any, region: Any, payload: dict):
    """The grievance's condition if still live, else nothing."""
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


__all__ = [
    "MAX_RIOT_DAMAGE",
    "MAX_RIOT_PARTICIPATION",
    "RIOT_ACTION",
    "RIOT_EVENT_TYPE",
    "active_condition_for",
    "aggrieved_crowd_wan",
    "already_rioted",
    "can_join_public_riot",
    "canonical_riot_payload",
    "mark_riot_answered",
    "pending_riots",
    "record_riot_aftermath",
    "riot_already_answered",
    "riot_damage",
    "riot_payload",
    "riot_receipt_id",
    "riot_response_receipt_id",
    "riotable_targets",
    "service_shortfall",
]

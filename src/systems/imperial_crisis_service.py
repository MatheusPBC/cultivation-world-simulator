"""Political legitimacy crises; this service never changes territorial control."""
from __future__ import annotations

from src.classes.core.dynasty import ImperialCrisis
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import Event, FactKind
from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR, OFFICIAL_ORDER
from src.classes.official_rank import OFFICIAL_NONE
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.systems.celestial_dao_service import get_dao_context
from src.systems.cultivation import REALM_RANK


ASCENSION_THRESHOLD = 180
MINIMUM_WORLDLY_CASE = 120
MIN_CRISIS_DURATION_MONTHS = 12


def _official_rank_score(avatar) -> int:
    rank = str(getattr(avatar, "official_rank", "") or "")
    return OFFICIAL_ORDER.index(rank) * 60 if rank in OFFICIAL_ORDER else 0


def _cultivation_score(avatar) -> int:
    progress = getattr(avatar, "cultivation_progress", None)
    return int(REALM_RANK.get(getattr(progress, "realm", None), 0)) * 40


def _celestial_score(world, avatar) -> tuple[int, list[str]]:
    """A visible answer can sway opinion, but remains smaller than a worldly case."""
    region = getattr(getattr(getattr(avatar, "tile", None), "region", None), "id", None)
    context = get_dao_context(world, region_id=region, initiator_id=str(avatar.id))
    score = 0
    evidence_ids: list[str] = []
    for item in context:
        # A public omen is visible to everyone, but its limited legitimacy
        # weight belongs to the petitioner whose plea it answered.
        if str(item.get("initiator_id", "")) != str(avatar.id):
            continue
        if item["kind"] == "omen":
            score += 15
        elif item["kind"] == "limited_favor":
            score += 35
        source_event_id = item.get("source_event_id")
        if source_event_id:
            evidence_ids.append(str(source_event_id))
    return min(score, 50), list(dict.fromkeys(evidence_ids))


def build_legitimacy_factors(world, emperor, claimant, support_avatar_ids: list[str]) -> tuple[dict[str, int], list[str]]:
    """Return transparent claimant-minus-emperor factors for one political crisis."""
    claimant_celestial, claimant_evidence = _celestial_score(world, claimant)
    emperor_celestial, emperor_evidence = _celestial_score(world, emperor)
    support_delta = 75 * len(set(map(str, support_avatar_ids)))
    factors = {
        "office": _official_rank_score(claimant) - _official_rank_score(emperor),
        "reputation": int(getattr(claimant, "court_reputation", 0) or 0) - int(getattr(emperor, "court_reputation", 0) or 0),
        "cultivation": _cultivation_score(claimant) - _cultivation_score(emperor),
        "support": support_delta,
        "celestial": claimant_celestial - emperor_celestial,
    }
    factors["worldly_total"] = sum(value for key, value in factors.items() if key != "celestial")
    factors["total"] = factors["worldly_total"] + factors["celestial"]
    return factors, list(dict.fromkeys(claimant_evidence + emperor_evidence))


def get_imperial_claim_blocker(world, claimant_id: str) -> str | None:
    """Return the deterministic rule that makes a claim unavailable, if any."""
    dynasty = getattr(world, "dynasty", None)
    claimant = world.avatar_manager.get_avatar(str(claimant_id))
    emperor = world.avatar_manager.get_avatar(str(getattr(dynasty, "current_emperor_id", ""))) if dynasty else None
    if dynasty is None or emperor is None or claimant is None or claimant.is_dead:
        return "A living claimant and emperor are required"
    if str(claimant.id) == str(emperor.id):
        return "The reigning emperor cannot claim against themself"
    if dynasty.imperial_crisis is not None and dynasty.imperial_crisis.status == "active":
        return "An imperial crisis is already active"
    if getattr(claimant.race, "id", "") != "human" or claimant.official_rank != OFFICIAL_GRAND_COUNCILOR or int(claimant.court_reputation) < 700:
        return "Claimant is not eligible for an imperial claim"
    return None


def get_imperial_support_blocker(world, supporter_id: str) -> str | None:
    dynasty = getattr(world, "dynasty", None)
    crisis = getattr(dynasty, "imperial_crisis", None)
    supporter = world.avatar_manager.get_avatar(str(supporter_id))
    if crisis is None or crisis.status != "active":
        return "There is no active imperial crisis to support"
    if supporter is None or supporter.is_dead or getattr(supporter.race, "id", "") != "human":
        return "A living human court official is required to offer support"
    if str(getattr(supporter, "official_rank", OFFICIAL_NONE) or OFFICIAL_NONE) == OFFICIAL_NONE:
        return "Only court officials can offer imperial support"
    if str(supporter.id) in {str(crisis.emperor_avatar_id), str(crisis.claimant_avatar_id)}:
        return "A contender cannot offer support in their own crisis"
    if str(supporter.id) in {str(item) for item in crisis.support_avatar_ids}:
        return "This official has already declared support"
    return None


def open_imperial_claim(world, claimant_id: str) -> ImperialCrisis:
    dynasty = world.dynasty
    claimant = world.avatar_manager.get_avatar(str(claimant_id))
    emperor = world.avatar_manager.get_avatar(str(getattr(dynasty, "current_emperor_id", ""))) if dynasty else None
    blocker = get_imperial_claim_blocker(world, claimant_id)
    if blocker is not None:
        raise ValueError(t(blocker))
    assert dynasty is not None and claimant is not None and emperor is not None
    crisis = ImperialCrisis(str(emperor.id), str(claimant.id), int(world.month_stamp))
    dynasty.imperial_crisis = crisis
    event = Event(
        world.month_stamp,
        t("{claimant} openly claims the imperial mandate.", claimant=claimant.name),
        related_avatars=[str(emperor.id), str(claimant.id)],
        fact_kind=FactKind.DECISION,
        is_major=True,
        causal_payload={
            "deltas": [
                StateDelta(
                    owner_kind="dynasty",
                    owner_id=str(dynasty.id),
                    aspect="imperial_crisis",
                    before="none",
                    after="active",
                ).to_dict(),
            ],
        },
    )
    crisis.evidence_event_ids.append(event.id)
    world.event_manager.add_event(event)
    return crisis


def support_imperial_claim(world, supporter_id: str) -> Event:
    """An official's explicit support is a causal fact, not an inferred bonus."""
    blocker = get_imperial_support_blocker(world, supporter_id)
    if blocker is not None:
        raise ValueError(t(blocker))
    crisis = world.dynasty.imperial_crisis
    supporter = world.avatar_manager.get_avatar(str(supporter_id))
    assert crisis is not None and supporter is not None
    crisis.support_avatar_ids.append(str(supporter.id))
    event = Event(
        world.month_stamp,
        t("{official} publicly supports the imperial claimant.", official=supporter.name),
        related_avatars=[str(supporter.id), str(crisis.claimant_avatar_id)],
        fact_kind=FactKind.STATE_TRANSITION,
        is_major=True,
        causal_payload={"deltas": [
            StateDelta(
                owner_kind="imperial_crisis",
                owner_id=str(crisis.claimant_avatar_id),
                aspect="support_avatar_ids",
                before=len(crisis.support_avatar_ids) - 1,
                after=len(crisis.support_avatar_ids),
            ).to_dict(),
        ]},
    )
    if crisis.evidence_event_ids:
        event.causal_links = [
            CausalLink(event_id=event.id, cause_event_id=crisis.evidence_event_ids[0], relation=CausalRelation.MOTIVATED_BY),
        ]
    crisis.evidence_event_ids.append(event.id)
    world.event_manager.add_event(event)
    return event


def resolve_imperial_crisis(world) -> Event | None:
    dynasty = world.dynasty
    crisis = getattr(dynasty, "imperial_crisis", None)
    if crisis is None or crisis.status != "active":
        return None
    # A pretension must survive a full political year before the annual court
    # judgment. Opening a claim in January cannot resolve it in that same step.
    if int(world.month_stamp) - int(crisis.opened_month) < MIN_CRISIS_DURATION_MONTHS:
        return None
    previous_status = str(crisis.status)
    previous_emperor_id = str(getattr(dynasty, "current_emperor_id", "") or "")
    emperor = world.avatar_manager.get_avatar(crisis.emperor_avatar_id)
    claimant = world.avatar_manager.get_avatar(crisis.claimant_avatar_id)
    if emperor is None or claimant is None or claimant.is_dead:
        crisis.status = "withdrawn"
        outcome = t("The imperial pretension is withdrawn.")
    else:
        factors, celestial_evidence = build_legitimacy_factors(world, emperor, claimant, crisis.support_avatar_ids)
        crisis.legitimacy_factors = factors
        for evidence_id in celestial_evidence:
            if evidence_id not in crisis.evidence_event_ids:
                crisis.evidence_event_ids.append(evidence_id)
        score = factors["total"]
        worldly_score = factors["worldly_total"]
        if score >= ASCENSION_THRESHOLD and worldly_score >= MINIMUM_WORLDLY_CASE:
            dynasty.current_emperor_id = str(claimant.id); crisis.status = "ascended"; outcome = t("{claimant} ascends after a legitimacy crisis.", claimant=claimant.name)
        elif score <= -ASCENSION_THRESHOLD and worldly_score <= -MINIMUM_WORLDLY_CASE:
            crisis.status = "failed"; outcome = t("{claimant}'s imperial claim fails publicly.", claimant=claimant.name)
        else:
            crisis.status = "stalemate"; outcome = t("The legitimacy crisis remains unresolved.")
    deltas = [
        StateDelta(
            owner_kind="imperial_crisis",
            owner_id=str(crisis.claimant_avatar_id),
            aspect="status",
            before=previous_status,
            after=str(crisis.status),
        ).to_dict(),
    ]
    if str(crisis.status) == "ascended":
        deltas.append(
            StateDelta(
                owner_kind="dynasty",
                owner_id=str(dynasty.id),
                aspect="current_emperor_id",
                before=previous_emperor_id,
                after=str(dynasty.current_emperor_id),
            ).to_dict()
        )
    event = Event(
        world.month_stamp,
        outcome,
        related_avatars=[crisis.emperor_avatar_id, crisis.claimant_avatar_id],
        fact_kind=FactKind.STATE_TRANSITION,
        is_major=True,
        causal_payload={
            "deltas": deltas,
            "legitimacy_factors": dict(crisis.legitimacy_factors),
        },
    )
    event.causal_links = [
        CausalLink(event_id=event.id, cause_event_id=evidence_id, relation=CausalRelation.TRIGGERED_BY)
        for evidence_id in crisis.evidence_event_ids
    ]
    crisis.evidence_event_ids.append(event.id)
    return event

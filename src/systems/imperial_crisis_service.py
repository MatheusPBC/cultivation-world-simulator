"""Political legitimacy crises; this service never changes territorial control."""
from __future__ import annotations

from src.classes.core.dynasty import ImperialCrisis
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import Event, FactKind
from src.classes.causal_origin import CausalOrigin
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


def _celestial_score(world, avatar, crisis: ImperialCrisis) -> tuple[int, list[str]]:
    """A visible answer can sway opinion, but remains smaller than a worldly case."""
    region = getattr(getattr(getattr(avatar, "tile", None), "region", None), "id", None)
    context = get_dao_context(world, region_id=region)
    score = 0
    evidence_ids: list[str] = []
    for item in context:
        # Celestial evidence is political evidence only when the audience's
        # source fact named exactly this contender.  Regional interpretation
        # and an ambiguous fact remain context, never legitimacy.
        if str(item.get("target_avatar_id", "")) != str(avatar.id) or str(
            item.get("target_avatar_id", "")
        ) not in {
            str(crisis.emperor_avatar_id),
            str(crisis.claimant_avatar_id),
        }:
            continue
        item_evidence_ids = [str(item.get("source_event_id", ""))]
        item_evidence_ids.extend(
            str(event_id) for event_id in item.get("target_evidence_event_ids", [])
        )
        if item["kind"] == "omen":
            score += 15
        elif item["kind"] == "limited_favor":
            score += 35
        item_evidence_ids = [event_id for event_id in item_evidence_ids if event_id]
        item_evidence_ids.extend(
            str(event_id) for event_id in item.get("evidence_event_ids", [])
        )
        evidence_ids.extend(item_evidence_ids)
    return min(score, 50), list(dict.fromkeys(evidence_ids))


def build_legitimacy_factors(world, emperor, claimant) -> tuple[dict[str, int], list[str]]:
    """Return transparent claimant-minus-emperor factors for one political crisis."""
    crisis = getattr(getattr(world, "dynasty", None), "imperial_crisis", None)
    if crisis is None:
        raise ValueError("An active imperial crisis is required to evaluate legitimacy")
    claimant_celestial, claimant_evidence = _celestial_score(world, claimant, crisis)
    emperor_celestial, emperor_evidence = _celestial_score(world, emperor, crisis)
    positions = crisis.political_positions
    supporters = {str(key) for key, value in positions.items() if value == "support"}
    opposition = {str(key) for key, value in positions.items() if value == "oppose"}
    support_delta = 75 * (len(supporters) - len(opposition))
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
    if str(supporter.id) in crisis.political_positions:
        return "This official has already declared a position"
    return None


def open_imperial_claim(world, claimant_id: str) -> Event:
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
        causal_origin=CausalOrigin.ACTOR_DECISION,
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
    return event


def support_imperial_claim(world, supporter_id: str) -> Event:
    """An official's explicit support is a causal fact, not an inferred bonus."""
    blocker = get_imperial_support_blocker(world, supporter_id)
    if blocker is not None:
        raise ValueError(t(blocker))
    crisis = world.dynasty.imperial_crisis
    supporter = world.avatar_manager.get_avatar(str(supporter_id))
    assert crisis is not None and supporter is not None
    crisis.political_positions[str(supporter.id)] = "support"
    event = Event(
        world.month_stamp,
        t("{official} publicly supports the imperial claimant.", official=supporter.name),
        related_avatars=[str(supporter.id), str(crisis.claimant_avatar_id)],
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        is_major=True,
        causal_payload={"deltas": [
            StateDelta(
                owner_kind="imperial_crisis",
                owner_id=str(crisis.claimant_avatar_id),
                aspect="political_positions",
                before=None,
                after="support",
            ).to_dict(),
        ]},
    )
    if crisis.evidence_event_ids:
        event.causal_links = [
            CausalLink(event_id=event.id, cause_event_id=crisis.evidence_event_ids[0], relation=CausalRelation.MOTIVATED_BY),
        ]
    crisis.evidence_event_ids.append(event.id)
    return event


def get_imperial_opposition_blocker(world, avatar_id: str) -> str | None:
    crisis = getattr(getattr(world, "dynasty", None), "imperial_crisis", None)
    avatar = world.avatar_manager.get_avatar(str(avatar_id))
    if crisis is None or crisis.status != "active":
        return "There is no active imperial crisis"
    if avatar is None or avatar.is_dead or getattr(avatar.race, "id", "") != "human":
        return "A living human court official is required"
    if str(avatar.official_rank or OFFICIAL_NONE) == OFFICIAL_NONE:
        return "Only court officials can take a political position"
    if str(avatar.id) in {str(crisis.emperor_avatar_id), str(crisis.claimant_avatar_id)}:
        return "A contender cannot take a position in their own crisis"
    if str(avatar.id) in crisis.political_positions:
        return "This official has already declared a position"
    return None


def oppose_imperial_claim(world, avatar_id: str) -> Event:
    blocker = get_imperial_opposition_blocker(world, avatar_id)
    if blocker is not None:
        raise ValueError(t(blocker))
    crisis = world.dynasty.imperial_crisis
    avatar = world.avatar_manager.get_avatar(str(avatar_id))
    assert crisis is not None and avatar is not None
    crisis.political_positions[str(avatar.id)] = "oppose"
    event = Event(
        world.month_stamp,
        t("{official} publicly opposes the imperial claimant.", official=avatar.name),
        related_avatars=[str(avatar.id), str(crisis.claimant_avatar_id)],
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        is_major=True,
        causal_payload={"deltas": [StateDelta(owner_kind="imperial_crisis", owner_id=str(crisis.claimant_avatar_id), aspect="political_positions", before=None, after="oppose").to_dict()]},
    )
    if crisis.evidence_event_ids:
        event.causal_links = [CausalLink(event_id=event.id, cause_event_id=crisis.evidence_event_ids[0], relation=CausalRelation.MOTIVATED_BY)]
    crisis.evidence_event_ids.append(event.id)
    return event


def withdraw_imperial_claim(world, claimant_id: str) -> Event:
    crisis = getattr(world.dynasty, "imperial_crisis", None)
    if crisis is None or crisis.status != "active" or str(crisis.claimant_avatar_id) != str(claimant_id):
        raise ValueError(t("Only the active claimant can withdraw the imperial claim"))
    crisis.status = "withdrawn"
    event = Event(world.month_stamp, t("The imperial claimant withdraws the imperial pretension."), related_avatars=[crisis.emperor_avatar_id, crisis.claimant_avatar_id], fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION, is_major=True, causal_payload={"deltas": [StateDelta(owner_kind="imperial_crisis", owner_id=str(crisis.claimant_avatar_id), aspect="status", before="active", after="withdrawn").to_dict()]})
    event.causal_links = [CausalLink(event_id=event.id, cause_event_id=eid, relation=CausalRelation.TRIGGERED_BY) for eid in crisis.evidence_event_ids]
    crisis.evidence_event_ids.append(event.id)
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
    claimant_eligible = claimant is not None and not claimant.is_dead and getattr(claimant.race, "id", "") == "human" and claimant.official_rank == OFFICIAL_GRAND_COUNCILOR and int(claimant.court_reputation) >= 700
    if claimant is None or claimant.is_dead:
        crisis.status = "failed"
        outcome = t("The imperial claim fails because the claimant is no longer alive.")
    elif emperor is None:
        crisis.status = "active"
        outcome = t(
            "The annual legitimacy reading remains unresolved while the throne lacks its recorded emperor."
        )
        crisis.evaluations.append(
            {
                "month": int(world.month_stamp),
                "factors": {},
                "status": crisis.status,
                "reason": "emperor_unavailable",
            }
        )
    elif not claimant_eligible:
        crisis.status = "failed"
        outcome = t("The imperial claimant loses eligibility and the imperial claim fails.")
    else:
        factors, celestial_evidence = build_legitimacy_factors(world, emperor, claimant)
        crisis.legitimacy_factors = factors
        for evidence_id in celestial_evidence:
            if evidence_id not in crisis.evidence_event_ids:
                crisis.evidence_event_ids.append(evidence_id)
        score = factors["total"]
        worldly_score = factors["worldly_total"]
        if score >= ASCENSION_THRESHOLD and worldly_score >= MINIMUM_WORLDLY_CASE:
            dynasty.current_emperor_id = str(claimant.id)
            crisis.status = "ascended"
            outcome = t(
                "{claimant} ascends after a legitimacy crisis.",
                claimant=claimant.name,
            )
        else:
            # An annual evaluation is a public reading, not an automatic end
            # state.  The crisis remains politically active until a concrete
            # eligibility loss, withdrawal, death, or sufficient worldly case.
            crisis.status = "active"
            outcome = t(
                "The annual legitimacy reading leaves the imperial crisis unresolved."
            )
        crisis.evaluations.append({"month": int(world.month_stamp), "factors": dict(factors), "status": crisis.status})
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
        causal_origin=CausalOrigin.DETERMINISTIC,
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

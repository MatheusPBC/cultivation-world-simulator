"""Deterministic imperial challenges and successions."""
from __future__ import annotations

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.agent_decision import AgentDecision
from src.classes.core.dynasty import Dynasty, ImperialClaim, ImperialCrisis
from src.classes.event import Event, FactKind
from src.classes.official_rank import OFFICIAL_NONE, OFFICIAL_ORDER
from src.classes.relation.relation import Relation
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.systems.cultivation import REALM_RANK

LINEAGE_THRESHOLD = 60
MINIMUM_ASCENSION_SCORE = 60
MIN_CRISIS_DURATION_MONTHS = 12


def _get_avatar(world, avatar_id: str | None):
    if not avatar_id:
        return None
    return world.avatar_manager.get_avatar(str(avatar_id))


def _is_adult(avatar) -> bool:
    return avatar is not None and not avatar.is_dead and int(getattr(getattr(avatar, "age", None), "age", 0) or 0) >= 18


def _is_human(avatar) -> bool:
    return getattr(getattr(avatar, "race", None), "id", "human") == "human"


def _is_official(avatar) -> bool:
    return str(getattr(avatar, "official_rank", OFFICIAL_NONE) or OFFICIAL_NONE) != OFFICIAL_NONE


def _vacancy_candidate_ids(world, dynasty: Dynasty) -> list[str]:
    blood_ids = {str(value) for value in dynasty.royal_blood_member_ids}
    blood_candidates = [
        avatar for avatar in world.avatar_manager.get_living_avatars()
        if str(avatar.id) in blood_ids and _is_adult(avatar) and _is_human(avatar)
    ]
    if blood_candidates:
        return sorted(str(avatar.id) for avatar in blood_candidates)
    return sorted(
        str(avatar.id) for avatar in world.avatar_manager.get_living_avatars()
        if _is_adult(avatar) and _is_human(avatar) and _is_official(avatar)
    )


def sync_royal_membership(world) -> None:
    """Reconcile observable marriages and blood relations into Dynasty IDs."""
    dynasty = getattr(world, "dynasty", None)
    if dynasty is None:
        return
    if dynasty.current_emperor_id:
        # The reigning office is a house membership, not proof of descent.
        # Initial blood membership is seeded by the dynasty generator and new
        # blood membership is earned only through a birth from a blood parent.
        dynasty.add_royal_house_member(dynasty.current_emperor_id)
    for avatar in world.avatar_manager.get_living_avatars():
        for other, state in (getattr(avatar, "relations", {}) or {}).items():
            other_id = getattr(other, "id", other)
            if not other_id:
                continue
            if Relation.IS_LOVER_OF in getattr(state, "identity_relations", set()):
                dynasty.register_marriage([str(avatar.id), str(other_id)])
            if getattr(state, "blood_relation", None) is Relation.IS_PARENT_OF:
                # Relation names describe the *other* person from avatar's
                # perspective: IS_PARENT_OF means avatar is the child.
                dynasty.register_birth(str(avatar.id), [str(other_id)])


def ensure_succession_crisis(world) -> ImperialCrisis | None:
    dynasty = getattr(world, "dynasty", None)
    if dynasty is None:
        return None
    sync_royal_membership(world)
    incumbent = _get_avatar(world, dynasty.current_emperor_id)
    crisis = getattr(dynasty, "imperial_crisis", None)
    if incumbent is not None and not incumbent.is_dead:
        return crisis
    if crisis is not None and crisis.status == "active":
        crisis.kind = "succession"
        crisis.incumbent_id = None
        return crisis
    crisis = ImperialCrisis("succession", None, int(world.month_stamp))
    dynasty.imperial_crisis = crisis
    return crisis


def _claim_candidate_is_eligible(world, crisis: ImperialCrisis, claim: ImperialClaim) -> bool:
    candidate = _get_avatar(world, claim.candidate_id)
    if not _is_adult(candidate) or not _is_human(candidate):
        return False
    if crisis.kind == "succession":
        return str(candidate.id) in set(_vacancy_candidate_ids(world, world.dynasty))
    return str(candidate.id) != str(crisis.incumbent_id) and (_is_official(candidate) or str(candidate.id) in {str(value) for value in world.dynasty.royal_blood_member_ids})


def _official_rank_score(avatar) -> int:
    rank = str(getattr(avatar, "official_rank", "") or "")
    return OFFICIAL_ORDER.index(rank) * 20 if rank in OFFICIAL_ORDER else 0


def _cultivation_score(avatar) -> int:
    progress = getattr(avatar, "cultivation_progress", None)
    return int(REALM_RANK.get(getattr(progress, "realm", None), 0)) * 5


def _support_score(claim: ImperialClaim) -> int:
    return 25 * sum(1 if value == "support" else -1 for value in claim.political_positions.values())


def build_legitimacy_factors(world, incumbent, claimant, claim: ImperialClaim | None = None) -> tuple[dict[str, int], list[str]]:
    dynasty = world.dynasty
    lineage = LINEAGE_THRESHOLD if str(claimant.id) in {str(value) for value in dynasty.royal_blood_member_ids} else 0
    incumbent_score = 0
    if incumbent is not None:
        incumbent_score = _official_rank_score(incumbent) + int(getattr(incumbent, "court_reputation", 0) or 0) // 10 + _cultivation_score(incumbent)
    factors = {
        "lineage": lineage,
        "office": _official_rank_score(claimant),
        "reputation": int(getattr(claimant, "court_reputation", 0) or 0) // 10,
        "cultivation": _cultivation_score(claimant),
        "support": _support_score(claim) if claim is not None else 0,
        "incumbent_comparison": -incumbent_score if incumbent is not None else 0,
    }
    factors["total"] = sum(factors.values())
    return factors, list(claim.evidence_event_ids) if claim is not None else []


def _find_crisis(world) -> ImperialCrisis | None:
    return getattr(getattr(world, "dynasty", None), "imperial_crisis", None)


def _decision_event_id(
    world,
    actor_id: str,
    action_name: str,
    *,
    source: str = "actor",
) -> str:
    actor = _get_avatar(world, actor_id)
    existing = str(getattr(actor, "current_decision_event_id", "") or "")
    if existing:
        return existing
    decision = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="avatar",
        subject_id=str(actor_id),
        source=source,
        considered_count=1,
        chosen_chain=[{"action_name": action_name, "params": {}}],
    )
    event = Event(
        world.month_stamp,
        t("{actor} made an imperial decision.", actor=getattr(actor, "name", actor_id)),
        related_avatars=[str(actor_id)],
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"deltas": [], "decision": decision.to_dict()},
    )
    manager = getattr(world, "event_manager", None)
    if manager is not None:
        manager.add_event(event)
    return event.id


def get_imperial_claim_blocker(world, candidate_id: str) -> str | None:
    dynasty = getattr(world, "dynasty", None)
    candidate = _get_avatar(world, candidate_id)
    if dynasty is None or not _is_adult(candidate) or not _is_human(candidate):
        return "A living adult human candidate is required"
    crisis = _find_crisis(world)
    if crisis is not None and crisis.status == "active" and crisis.get_claim(candidate_id) is not None:
        return "This candidate already has a claim in the active crisis"
    incumbent = _get_avatar(world, dynasty.current_emperor_id)
    if incumbent is not None and str(candidate.id) == str(incumbent.id):
        return "The reigning emperor cannot claim against themself"
    if crisis is None and not (_is_official(candidate) or str(candidate.id) in {str(value) for value in dynasty.royal_blood_member_ids}):
        return "Candidate is not eligible for an imperial claim"
    if crisis is not None and crisis.kind == "succession" and not _claim_candidate_is_eligible(world, crisis, ImperialClaim(str(candidate.id), int(world.month_stamp))):
        return "Candidate is outside the succession eligibility pool"
    return None


def open_imperial_claim(
    world, candidate_id: str, *, decision_source: str = "actor"
) -> Event:
    blocker = get_imperial_claim_blocker(world, candidate_id)
    if blocker is not None:
        raise ValueError(t(blocker))
    dynasty = world.dynasty
    incumbent = _get_avatar(world, dynasty.current_emperor_id)
    crisis = _find_crisis(world)
    if crisis is None or crisis.status != "active":
        crisis = ImperialCrisis("challenge" if incumbent is not None else "succession", str(incumbent.id) if incumbent else None, int(world.month_stamp))
        dynasty.imperial_crisis = crisis
    elif crisis.kind == "challenge" and (incumbent is None or incumbent.is_dead):
        crisis.kind = "succession"
        crisis.incumbent_id = None
    before_claims = [item.candidate_id for item in crisis.claims]
    claim = ImperialClaim(str(candidate_id), int(world.month_stamp), position="claimant" if crisis.kind == "challenge" else "successor")
    crisis.claims.append(claim)
    decision_event_id = _decision_event_id(
        world,
        str(candidate_id),
        "ClaimImperialMandate",
        source=decision_source,
    )
    related = [str(candidate_id)] + ([str(crisis.incumbent_id)] if crisis.incumbent_id else [])
    event = Event(
        world.month_stamp,
        t("{claimant} openly claims the imperial mandate.", claimant=_get_avatar(world, candidate_id).name),
        related_avatars=related, fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        is_major=True,
    )
    event.causal_payload = {
        "deltas": [
            StateDelta(
                event_id=event.id,
                owner_kind="dynasty",
                owner_id=str(dynasty.id),
                aspect="imperial_claims",
                before=str(before_claims),
                after=str([item.candidate_id for item in crisis.claims]),
            ).to_dict()
        ]
    }
    event.causal_links = [
        CausalLink(
            event_id=event.id,
            cause_event_id=decision_event_id,
            relation=CausalRelation.MOTIVATED_BY,
        )
    ]
    claim.evidence_event_ids.append(event.id)
    return event


def _position_blocker(
    world, supporter_id: str, candidate_id: str | None, position: str
) -> str | None:
    crisis = _find_crisis(world)
    supporter = _get_avatar(world, supporter_id)
    if crisis is None or crisis.status != "active":
        return "There is no active imperial crisis"
    if candidate_id is None:
        return "A candidate_id is required for a political position"
    claim = crisis.get_claim(candidate_id)
    if claim is None or claim.status != "active":
        return "The candidate has no active imperial claim"
    if not _is_adult(supporter) or not _is_human(supporter) or not _is_official(supporter):
        return "A living human court official is required"
    if str(supporter.id) in {str(claim.candidate_id), str(crisis.incumbent_id or "")}:
        return "A contender cannot offer a position in their own crisis"
    if str(supporter.id) in claim.political_positions:
        return "This official has already declared a position"
    if position == "support" and any(
        other.political_positions.get(str(supporter.id)) == "support"
        for other in crisis.claims
    ):
        return "This official already supports another candidate"
    return None


def get_imperial_support_blocker(world, supporter_id: str, candidate_id: str | None = None) -> str | None:
    return _position_blocker(world, supporter_id, candidate_id, "support")


def get_imperial_opposition_blocker(world, avatar_id: str, candidate_id: str | None = None) -> str | None:
    return _position_blocker(world, avatar_id, candidate_id, "oppose")


def _record_position(world, supporter_id: str, candidate_id: str, position: str) -> Event:
    blocker = _position_blocker(world, supporter_id, candidate_id, position)
    if blocker is not None:
        raise ValueError(t(blocker))
    crisis = _find_crisis(world)
    claim = crisis.get_claim(candidate_id)
    supporter = _get_avatar(world, supporter_id)
    assert crisis is not None and claim is not None and supporter is not None
    claim.political_positions[str(supporter.id)] = position
    decision_event_id = _decision_event_id(
        world,
        str(supporter.id),
        "SupportImperialClaim" if position == "support" else "OpposeImperialClaim",
    )
    event = Event(
        world.month_stamp,
        t("{official} publicly takes a position on the imperial candidate.", official=supporter.name),
        related_avatars=[str(supporter.id), str(candidate_id)], fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION, is_major=True,
    )
    event.causal_payload = {
        "deltas": [
            StateDelta(
                event_id=event.id,
                owner_kind="imperial_claim",
                owner_id=str(candidate_id),
                aspect="political_positions",
                before=None,
                after=position,
            ).to_dict()
        ]
    }
    event.causal_links = [
        CausalLink(
            event_id=event.id,
            cause_event_id=decision_event_id,
            relation=CausalRelation.MOTIVATED_BY,
        )
    ]
    if claim.evidence_event_ids:
        event.causal_links.append(CausalLink(event_id=event.id, cause_event_id=claim.evidence_event_ids[0], relation=CausalRelation.RESPONSE_TO))
    claim.evidence_event_ids.append(event.id)
    return event


def support_imperial_claim(world, supporter_id: str, candidate_id: str) -> Event:
    return _record_position(world, supporter_id, candidate_id, "support")


def oppose_imperial_claim(world, avatar_id: str, candidate_id: str) -> Event:
    return _record_position(world, avatar_id, candidate_id, "oppose")


def withdraw_imperial_claim(world, candidate_id: str) -> Event:
    crisis = _find_crisis(world)
    claim = crisis.get_claim(candidate_id) if crisis else None
    if crisis is None or crisis.status != "active" or claim is None or claim.status != "active":
        raise ValueError(t("Only an active claimant can withdraw the imperial claim"))
    claim.status = "withdrawn"
    decision_event_id = _decision_event_id(
        world, str(candidate_id), "WithdrawImperialClaim"
    )
    event = Event(
        world.month_stamp,
        t("The imperial claimant withdraws the imperial pretension."),
        related_avatars=[str(candidate_id)],
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        is_major=True,
        causal_links=[
            CausalLink(
                cause_event_id=decision_event_id,
                relation=CausalRelation.MOTIVATED_BY,
            )
        ],
    )
    event.causal_payload = {
        "deltas": [
            StateDelta(
                event_id=event.id,
                owner_kind="imperial_claim",
                owner_id=str(candidate_id),
                aspect="status",
                before="active",
                after="withdrawn",
            ).to_dict()
        ]
    }
    event.causal_links[0].event_id = event.id
    claim.evidence_event_ids.append(event.id)
    return event


def resolve_imperial_crisis(world) -> Event | None:
    dynasty = getattr(world, "dynasty", None)
    crisis = _find_crisis(world)
    if dynasty is None or crisis is None or crisis.status != "active":
        return None
    incumbent = _get_avatar(world, crisis.incumbent_id)
    if crisis.kind == "challenge" and (incumbent is None or incumbent.is_dead):
        crisis.kind = "succession"
        crisis.incumbent_id = None
        return Event(world.month_stamp, t("The vacant throne turns the imperial challenge into a succession."), is_major=True)
    if int(world.month_stamp) - int(crisis.opened_month) < MIN_CRISIS_DURATION_MONTHS:
        return None
    qualifying: list[tuple[ImperialClaim, dict[str, int]]] = []
    for claim in crisis.claims:
        if claim.status != "active":
            continue
        candidate = _get_avatar(world, claim.candidate_id)
        if not _claim_candidate_is_eligible(world, crisis, claim):
            claim.status = "failed"
            claim.evaluations.append({"month": int(world.month_stamp), "status": "failed", "reason": "ineligible"})
            continue
        factors, _ = build_legitimacy_factors(world, incumbent, candidate, claim)
        claim.evaluations.append({"month": int(world.month_stamp), "factors": dict(factors), "status": "active"})
        if factors["total"] >= MINIMUM_ASCENSION_SCORE:
            qualifying.append((claim, factors))
    winner = None
    if qualifying:
        highest = max(factors["total"] for _claim, factors in qualifying)
        top = [(claim, factors) for claim, factors in qualifying if factors["total"] == highest]
        if len(top) == 1:
            winner, _factors = top[0]
            winner.winner = True
            winner.status = "ascended"
            dynasty.current_emperor_id = str(winner.candidate_id)
            crisis.status = "ascended"
            winner.evaluations[-1]["status"] = "ascended"
    related = [str(claim.candidate_id) for claim in crisis.claims]
    if crisis.incumbent_id:
        related.append(str(crisis.incumbent_id))
    event = Event(
        world.month_stamp,
        t("A yearly imperial evaluation leaves the succession unresolved.") if winner is None else t("{claimant} ascends after the imperial evaluation.", claimant=_get_avatar(world, winner.candidate_id).name),
        related_avatars=list(dict.fromkeys(related)), fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC, is_major=True,
        causal_payload={"claims": [claim.to_dict() for claim in crisis.claims]},
    )
    event.causal_links = [CausalLink(event_id=event.id, cause_event_id=evidence_id, relation=CausalRelation.TRIGGERED_BY) for claim in crisis.claims for evidence_id in claim.evidence_event_ids][:8]
    for claim in crisis.claims:
        claim.evidence_event_ids.append(event.id)
    return event

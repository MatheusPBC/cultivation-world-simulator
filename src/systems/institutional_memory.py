"""Read models and bounded updates for institutional memory.

Knowledge remains the sole owner of known facts and relations remains the
sole mutation owner for memories.  This module only derives relevance and
orchestrates validated owner calls around canonical events.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.institution import (
    AuthorityScope,
    InstitutionalFactKnowledge,
    InstitutionalMemory,
    KnowledgeChannel,
)
from src.classes.state_delta import StateDelta
from src.systems.institution_authority import can_actor_act_for


MEMORY_FACTOR_NAMES = (
    "relative_scale",
    "institutional_change",
    "commitment_breach",
    "identity_anchor_impact",
)
MEMORY_BASE_HALF_LIFE_MONTHS = 12
MAX_KNOWN_FACTS_IN_DECISION_CONTEXT = 4
MAX_EVENT_CONTENT_CHARS = 240
MAX_EVENT_RENDER_PARAMS = 8


def _canonical_event(event: Event) -> None:
    if (
        not isinstance(event, Event)
        or not event.id
        or event.is_story
        or event.fact_kind is FactKind.DECISION
        or event.causal_origin is CausalOrigin.LLM_INTERPRETATION
    ):
        raise ValueError("institutional memory requires a non-story canonical event")


def _factors(values: Mapping[str, Any]) -> tuple[tuple[str, float], ...]:
    return tuple(
        (name, max(0.0, min(1.0, float(values.get(name, 0.0)))))
        for name in MEMORY_FACTOR_NAMES
    )


def salience_for_factors(factors: Mapping[str, Any]) -> float:
    """The frozen four engine factors are the entire historical weighting rule."""

    normalized = _factors(factors)
    return sum(value for _, value in normalized) / len(normalized)


def effective_salience(memory: InstitutionalMemory, month: int) -> float:
    """Decay is derived at read time; historical facts and stored memory stay intact."""

    elapsed = max(0, int(month) - memory.last_reinforced_month)
    # Anchor impact is already one of the frozen factors: it only lengthens
    # the half-life, without adding a new historical-weight mechanism.
    anchor_impact = dict(memory.factors).get("identity_anchor_impact", 0.0)
    half_life = MEMORY_BASE_HALF_LIFE_MONTHS * (1.0 + 9.0 * anchor_impact)
    return memory.salience * (0.5 ** (elapsed / half_life))


def record_known_fact(
    world: Any,
    event: Event,
    institution_ids: tuple[str, ...],
    *,
    factors: Mapping[str, Any] | None = None,
    channel: KnowledgeChannel = KnowledgeChannel.FORMAL_NOTICE,
) -> None:
    """Record a canonical fact and, when relevant, its initial memory.

    A duplicate invocation is idempotent: the knowledge record and memory ID
    are both canonical and no second delta is appended.

    ``channel`` must describe how these institutions actually learned the
    fact.  It changes nothing else: without explicit ``factors`` no memory is
    created, whatever the channel.
    """

    _canonical_event(event)
    if not isinstance(channel, KnowledgeChannel):
        raise TypeError("channel must be a KnowledgeChannel")
    payload = event.causal_payload
    if not isinstance(payload, dict):
        raise TypeError("institutional fact event requires a causal payload")
    deltas = list(payload.get("deltas") or [])
    normalized_factors = _factors(factors or {}) if factors else ()
    for institution_id in tuple(dict.fromkeys(institution_ids)):
        was_known = world.institutional_knowledge.contains(institution_id, event.id)
        world.institutional_knowledge.record(
            InstitutionalFactKnowledge(
                institution_id=institution_id,
                event_id=event.id,
                learned_month=int(world.month_stamp),
                channel=channel,
                learned_from_event_id=event.id,
            ),
            world.institutional_authority,
        )
        if not was_known:
            deltas.append(
                StateDelta(
                    event_id=event.id,
                    owner_kind="institutional_knowledge",
                    owner_id=institution_id,
                    aspect=f"known_fact:{event.id}",
                    before="unknown",
                    after="known",
                ).to_dict()
            )
        if not normalized_factors:
            continue
        memory = InstitutionalMemory(
            institution_id=institution_id,
            event_id=event.id,
            salience=sum(value for _, value in normalized_factors) / len(normalized_factors),
            recorded_month=int(world.month_stamp),
            last_reinforced_month=int(world.month_stamp),
            factors=normalized_factors,
        )
        if memory.id not in world.institutional_relations.memories:
            world.institutional_relations.add_memory(
                memory, world.institutional_knowledge, world.institutional_authority
            )
            deltas.append(
                StateDelta(
                    event_id=event.id,
                    owner_kind="institutional_memory",
                    owner_id=memory.id,
                    aspect="salience",
                    before="none",
                    after=str(memory.salience),
                    magnitude=memory.salience,
                ).to_dict()
            )
    payload["deltas"] = deltas


def reinforce_from_evidence(
    world: Any,
    *,
    institution_id: str,
    remembered_event_id: str,
    evidence_event: Event,
) -> bool:
    """Reinforce once from a distinct new known canonical fact.

    The evidence event carries the append-only audit delta, which makes
    repeated calls idempotent without introducing a second memory owner.
    """

    _canonical_event(evidence_event)
    if evidence_event.id == remembered_event_id:
        return False
    knowledge = world.institutional_knowledge
    if not (
        knowledge.contains(institution_id, remembered_event_id)
        and knowledge.contains(institution_id, evidence_event.id)
    ):
        return False
    memory_id = InstitutionalMemory(
        institution_id=institution_id,
        event_id=remembered_event_id,
        salience=0.0,
        recorded_month=0,
        last_reinforced_month=0,
        factors=(),
    ).id
    current = world.institutional_relations.memories.get(memory_id)
    if current is None:
        return False
    payload = evidence_event.causal_payload
    if not isinstance(payload, dict):
        raise TypeError("institutional evidence event requires a causal payload")
    aspect = f"reinforced_by:{evidence_event.id}"
    if any(
        delta.get("owner_kind") == "institutional_memory"
        and delta.get("owner_id") == memory_id
        and delta.get("aspect") == aspect
        for delta in payload.get("deltas") or []
        if isinstance(delta, dict)
    ):
        return False
    effective_before = effective_salience(current, int(world.month_stamp))
    before = current.salience
    after = max(effective_before, salience_for_factors(dict(current.factors)))
    previous_reinforced_month = current.last_reinforced_month
    updated = replace(
        current,
        salience=after,
        last_reinforced_month=int(world.month_stamp),
        # Evidence refreshes relevance, not the historical interpretation of
        # the remembered fact: its frozen factors remain immutable.
        factors=current.factors,
    )
    world.institutional_relations.replace_memory(
        updated, knowledge, world.institutional_authority
    )
    payload.setdefault("deltas", []).extend((
        StateDelta(
            event_id=evidence_event.id,
            owner_kind="institutional_memory",
            owner_id=memory_id,
            aspect=aspect,
            before=str(before),
            after=str(after),
            magnitude=after - before,
        ).to_dict(),
        StateDelta(
            event_id=evidence_event.id,
            owner_kind="institutional_memory",
            owner_id=memory_id,
            aspect="last_reinforced_month",
            before=str(previous_reinforced_month),
            after=str(int(world.month_stamp)),
        ).to_dict(),
    ))
    return True


def decision_context(
    world: Any,
    institution_id: str,
    *,
    event_overlays: tuple[Event, ...] = (),
    authority_scope: AuthorityScope = AuthorityScope.COMMITMENT_NEGOTIATION,
) -> dict[str, Any]:
    """Bounded actor-known facts plus current authorized holder projection.

    ``authority_scope`` selects which office's current holder is projected.
    Different institutional choices are authorized by different offices, and
    projecting the wrong one would describe a leader who cannot actually take
    the choice at hand.  This selects a projection only; it grants nothing.
    """

    month = int(world.month_stamp)
    known = world.institutional_knowledge
    memories = world.institutional_relations.memories_for(institution_id)
    ranked = sorted(
        (
            (effective_salience(memory, month), memory)
            for memory in memories
            if known.contains(institution_id, memory.event_id)
        ),
        key=lambda item: (-item[0], item[1].event_id),
    )[:MAX_KNOWN_FACTS_IN_DECISION_CONTEXT]
    overlays = {event.id: event for event in event_overlays if isinstance(event, Event)}
    facts = []
    for salience, memory in ranked:
        fact = known.get_fact(institution_id, memory.event_id)
        if fact is not None:
            event = overlays.get(fact.event_id)
            if event is None:
                manager = getattr(world, "event_manager", None)
                getter = getattr(manager, "get_event_by_id", None)
                event = getter(fact.event_id) if callable(getter) else None
            if isinstance(event, Event) and not event.is_story:
                facts.append(
                    {
                        "event_id": fact.event_id,
                        "event_type": event.event_type,
                        "month_stamp": int(event.month_stamp),
                        "content": event.content[:MAX_EVENT_CONTENT_CHARS],
                        "participants": {
                            "avatars": list(event.related_avatars or []),
                            "sects": list(event.related_sects or []),
                        },
                        "render_params": _bounded_params(event.render_params),
                        "institutional_metadata": _institutional_metadata(world, event),
                        "learned_month": fact.learned_month,
                        "channel": fact.channel.value,
                        "salience": salience,
                    }
                )
    relations = []
    for relation in world.institutional_relations.relations.values():
        if institution_id not in (relation.institution_a_id, relation.institution_b_id):
            continue
        counterpart = relation.institution_b_id if relation.institution_a_id == institution_id else relation.institution_a_id
        relations.append({
            "relation_id": relation.id,
            "counterpart_institution_id": counterpart,
            "counterpart_name": _institution_name(world, counterpart),
            "kind": relation.kind.value,
            "friendliness": relation.friendliness,
            "evidence_event_ids": list(relation.evidence_event_ids[-4:]),
        })
    return {
        "known_facts": facts,
        "authorized_holder": _holder_projection(
            world, institution_id, authority_scope
        ),
        "current_relations": sorted(
            relations, key=lambda item: item["counterpart_institution_id"]
        )[:4],
    }


def _holder_projection(
    world: Any, institution_id: str, authority_scope: AuthorityScope
) -> dict[str, Any] | None:
    institution = world.institutional_authority.get_institution(institution_id)
    if institution is None:
        return None
    verdict = can_actor_act_for(
        world,
        institution.owner_ref,
        institution.owner_ref,
        authority_scope,
        current_month=int(world.month_stamp),
    )
    office = world.institutional_authority.offices.get(verdict.office_id or "")
    if not verdict.allowed or office is None or office.holder_ref is None:
        return None
    projection: dict[str, Any] = {
        "office_id": office.id,
        "authorizing_institution_id": verdict.authorizing_institution_id,
        "holder_ref": office.holder_ref.to_dict(),
        "active_claim_ids": [
            claim.id for claim in world.institutional_authority.active_claims(office.id)
        ],
    }
    manager = getattr(world, "avatar_manager", None)
    getter = getattr(manager, "get_avatar", None)
    avatar = getter(office.holder_ref.id) if callable(getter) else None
    if avatar is None:
        return projection
    projection["holder"] = {
        "id": str(getattr(avatar, "id", office.holder_ref.id)),
        "name": str(getattr(avatar, "name", "")),
        "alignment": str(getattr(avatar, "alignment", "") or ""),
        "persona_keys": sorted(
            str(getattr(persona, "key", ""))
            for persona in (getattr(avatar, "personas", None) or [])
            if getattr(persona, "key", "")
        ),
        "motivations": {
            "short_term_objective": str(getattr(avatar, "short_term_objective", ""))[:160],
            "long_term_objective": str(
                getattr(getattr(avatar, "long_term_objective", None), "content", "")
            )[:160],
        },
    }
    return projection


def _bounded_params(params: Any) -> dict[str, str | int | float | bool | None]:
    if not isinstance(params, Mapping):
        return {}
    result: dict[str, str | int | float | bool | None] = {}
    for key in sorted(params)[:MAX_EVENT_RENDER_PARAMS]:
        value = params[key]
        if isinstance(key, str) and (value is None or isinstance(value, (str, int, float, bool))):
            result[key] = value[:160] if isinstance(value, str) else value
    return result


def _institutional_metadata(world: Any, event: Event) -> dict[str, Any]:
    payload = event.causal_payload if isinstance(event.causal_payload, Mapping) else {}
    metadata = {
        key: payload[key]
        for key in ("commitment_id", "term_id", "outcome")
        if key in payload
        and (isinstance(payload.get(key), (str, int, float, bool)) or payload.get(key) is None)
    }
    request = payload.get("institutional_aid_request")
    offer = payload.get("institutional_trade_offer")
    if isinstance(offer, Mapping):
        legs = offer.get("legs")
        bounded_legs = list(legs)[:2] if isinstance(legs, (list, tuple)) else []
        # Both directions are canonical facts of the same exchange; showing one
        # of them would misrepresent what was agreed or declined.
        metadata["legs"] = [
            {
                key: leg[key]
                for key in (
                    "resource_id",
                    "amount",
                    "source_region_id",
                    "destination_region_id",
                )
                if isinstance(leg.get(key), (str, int, float))
            }
            for leg in bounded_legs
            if isinstance(leg, Mapping)
        ]
        parties = [
            str(offer[key])
            for key in ("proposer_institution_id", "counterparty_institution_id")
            if isinstance(offer.get(key), str)
        ]
        if parties:
            metadata["parties"] = [
                {"institution_id": party, "name": _institution_name(world, party)}
                for party in parties[:2]
            ]
    if isinstance(request, Mapping):
        for key in ("resource_id", "amount", "source_region_id", "destination_region_id"):
            if isinstance(request.get(key), (str, int, float)):
                metadata[key] = request[key]
        parties = [
            str(request[key])
            for key in ("requester_institution_id", "provider_institution_id")
            if isinstance(request.get(key), str)
        ]
        if parties:
            metadata["parties"] = [
                {"institution_id": party, "name": _institution_name(world, party)}
                for party in parties[:2]
            ]
    commitment_id = metadata.get("commitment_id")
    commitment = getattr(world, "institutional_relations", None)
    commitment = getattr(commitment, "commitments", {}).get(commitment_id)
    if commitment is not None:
        metadata["parties"] = [
            {"institution_id": party, "name": _institution_name(world, party)}
            for party in commitment.party_ids[:2]
        ]
        term_id = metadata.get("term_id")
        term = next((item for item in commitment.terms if item.id == term_id), None)
        if term is not None:
            metadata["term"] = {
                "kind": term.kind.value,
                "status": term.status.value,
                "amount": dict(term.parameters).get("amount"),
            }
    return metadata


def _institution_name(world: Any, institution_id: str) -> str:
    institution = world.institutional_authority.get_institution(institution_id)
    if institution is None:
        return "Unknown institution"
    owner = institution.owner_ref
    if owner.kind == "region":
        region = getattr(getattr(world, "map", None), "regions", {}).get(int(owner.id))
        return str(getattr(region, "name", institution_id))
    if owner.kind == "dynasty":
        return str(getattr(getattr(world, "dynasty", None), "title", institution_id))
    context = getattr(world, "sect_context", None)
    sect = next((item for item in (context.get_active_sects() if context else ()) if str(item.id) == owner.id), None)
    return str(getattr(sect, "name", institution_id))


__all__ = [
    "MAX_KNOWN_FACTS_IN_DECISION_CONTEXT",
    "MEMORY_BASE_HALF_LIFE_MONTHS",
    "decision_context",
    "effective_salience",
    "record_known_fact",
    "reinforce_from_evidence",
    "salience_for_factors",
]

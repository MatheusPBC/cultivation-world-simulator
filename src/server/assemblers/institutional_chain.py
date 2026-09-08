"""Read-only projection of canonical institutional state and factual history."""
from __future__ import annotations

import base64
import json
from typing import Any, Mapping

from src.classes.causal_link import CausalRelation
from src.classes.event_query import EventQuery
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.institution import AuthorityScope, InstitutionKind
from src.classes.mechanical_language import EntityRef
from src.systems.institution_authority import can_actor_act_for
from src.systems.institutional_memory import effective_salience

_OWNER_KINDS = {"region": InstitutionKind.CITY, "sect": InstitutionKind.SECT, "dynasty": InstitutionKind.DYNASTY}
_EVENT_TYPES = {"institutional_aid_requested", "institutional_aid_accepted", "institutional_aid_refused", "institutional_trade_proposed", "institutional_trade_accepted", "institutional_trade_refused", "regional_resource_transfer_completed", "institutional_commitment_term_fulfilled", "institutional_commitment_term_breached", "institutional_commitment_remediation_proposed", "institutional_commitment_term_remediated", "institutional_relationship_changed", "institutional_relationship_interpreted", "institutional_peace_proposed", "institutional_peace_accepted", "institutional_peace_rejected", "institutional_war_declared", "avatar_deliberate_attack", "dao_rite", "civil_public_petition", "city_maintenance_completed", "urban_capacity_project_started", "civil_work_stoppage_started", "civil_work_stoppage_ended", "regional_production_forgone"}
_PEACE_EVENT_TYPES = {"institutional_peace_proposed", "institutional_peace_accepted", "institutional_peace_rejected", "institutional_war_declared"}
_AGGRESSION_EVENT_TYPES = {"avatar_deliberate_attack"}
_EVENT_SCAN_PAGE_SIZE = 128
_EVENT_SCAN_PAGES = 3


def _civil_petition_party_ids(world: Any, payload: Mapping[str, Any]) -> set[str]:
    """Resolve only the petition's recorded institution and city identities."""
    region_id = payload.get("region_id")
    institution_id = payload.get("addressed_institution_id")
    addressed = payload.get("addressed_institution_ref")
    if not isinstance(region_id, str) or not region_id:
        return set()
    if not isinstance(institution_id, str) or not institution_id:
        return set()
    if not isinstance(addressed, Mapping):
        return set()
    kind, owner_id = addressed.get("kind"), addressed.get("id")
    if not isinstance(kind, str) or not isinstance(owner_id, str) or not owner_id:
        return set()
    try:
        region_institution = world.institutional_authority.get_institution_for_owner(
            EntityRef("region", region_id)
        )
        addressed_institution = world.institutional_authority.get_institution(
            institution_id
        )
    except (AttributeError, TypeError, ValueError):
        return set()
    if region_institution is None or addressed_institution is None:
        return set()
    if addressed_institution.owner_ref != EntityRef(kind, owner_id):
        return set()
    return {str(region_institution.id), str(addressed_institution.id)}


def _civil_stoppage_party_ids(world: Any, event: Any) -> set[str]:
    payload = event.causal_payload if isinstance(event.causal_payload, Mapping) else {}
    stoppage = payload.get("civil_work_stoppage")
    if (
        event.fact_kind is not FactKind.STATE_TRANSITION
        or event.causal_origin is not CausalOrigin.ACTOR_DECISION
        or not isinstance(stoppage, Mapping)
    ):
        return set()
    region_id = stoppage.get("region_id")
    condition_id = stoppage.get("condition_instance_id")
    petition_id = stoppage.get("petition_event_id")
    if not all(isinstance(value, str) and value for value in (region_id, condition_id, petition_id)):
        return set()
    try:
        city = world.institutional_authority.get_institution_for_owner(
            EntityRef("region", region_id)
        )
        petition = world.event_manager.get_event_by_id(petition_id)
    except (AttributeError, TypeError, ValueError):
        return set()
    if (
        city is None
        or petition is None
        or petition.event_type != "civil_public_petition"
        or petition.is_story
        or petition.fact_kind is not FactKind.OCCURRENCE
        or petition.causal_origin is not CausalOrigin.ACTOR_DECISION
        or _party_ids(world, petition) == set()
    ):
        return set()
    links = world.event_manager.get_causal_links_for_event(event.id)
    if not any(
        link.cause_event_id == petition_id
        and link.relation is CausalRelation.MOTIVATED_BY
        for link in links
    ):
        return set()
    condition_event = None
    decision_event = None
    for link in links:
        if link.cause_event_id == petition_id:
            continue
        cause = world.event_manager.get_event_by_id(link.cause_event_id)
        if cause is None or cause.is_story:
            continue
        if (
            link.relation is CausalRelation.ENABLED_BY
            and cause.event_type == "semantic_condition_activated"
            and str((cause.render_params or {}).get("region_id", "")) == region_id
        ):
            condition_event = cause
        if (
            link.relation is CausalRelation.TRIGGERED_BY
            and cause.fact_kind is FactKind.DECISION
            and cause.causal_origin is CausalOrigin.ACTOR_DECISION
            and isinstance(cause.causal_payload, Mapping)
            and isinstance(cause.causal_payload.get("decision"), Mapping)
        ):
            decision_event = cause
    if condition_event is None or decision_event is None:
        return set()
    return _party_ids(world, petition) | {str(city.id)}


def _civil_stoppage_transition_party_ids(world: Any, event: Any) -> set[str]:
    if event.fact_kind is not FactKind.STATE_TRANSITION or event.causal_origin is not CausalOrigin.DETERMINISTIC:
        return set()
    links = world.event_manager.get_causal_links_for_event(event.id)
    start = next(
        (world.event_manager.get_event_by_id(link.cause_event_id)
         for link in links
         if link.relation is CausalRelation.RESOLVES
         and link.cause_event_id
         and (world.event_manager.get_event_by_id(link.cause_event_id) is not None)
         and world.event_manager.get_event_by_id(link.cause_event_id).event_type
         == "civil_work_stoppage_started"),
        None,
    )
    if start is None or start.event_type != "civil_work_stoppage_started":
        return set()
    return _civil_stoppage_party_ids(world, start)


def _civil_forgone_party_ids(world: Any, event: Any) -> set[str]:
    if event.fact_kind is not FactKind.OCCURRENCE or event.causal_origin is not CausalOrigin.DETERMINISTIC:
        return set()
    links = world.event_manager.get_causal_links_for_event(event.id)
    start = next(
        (world.event_manager.get_event_by_id(link.cause_event_id)
         for link in links
         if link.relation is CausalRelation.TRIGGERED_BY
         and link.cause_event_id
         and (world.event_manager.get_event_by_id(link.cause_event_id) is not None)
         and world.event_manager.get_event_by_id(link.cause_event_id).event_type
         == "civil_work_stoppage_started"),
        None,
    )
    if start is None or start.event_type != "civil_work_stoppage_started":
        return set()
    return _civil_stoppage_party_ids(world, start)


def _encode_cursor(month: int, item_id: str) -> str:
    raw = json.dumps({"month": month, "id": item_id}, separators=(",", ":"), sort_keys=True)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(value: str | None) -> tuple[int, str] | None:
    if value is None:
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode()).decode())
        month, item_id = data["month"], data["id"]
        if isinstance(month, bool) or not isinstance(month, int) or month < 0 or not isinstance(item_id, str) or not item_id:
            raise ValueError
        return month, item_id
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid cursor") from exc


def _key(event: Any) -> tuple[int, str]:
    return int(event.month_stamp), str(event.id)


def _name(world: Any, institution: Any) -> str:
    ref = institution.owner_ref
    if ref.kind == "region":
        try:
            region = world.map.regions.get(int(ref.id))
        except (AttributeError, ValueError):
            region = None
        return str(getattr(region, "name", "") or ref.id)
    if ref.kind == "sect":
        context = getattr(world, "sect_context", None)
        sects = context.get_active_sects() if context else ()
        sect = next((item for item in sects if str(item.id) == ref.id), None)
        return str(getattr(sect, "name", "") or ref.id)
    dynasty = getattr(world, "dynasty", None)
    return str(getattr(dynasty, "title", "") or getattr(dynasty, "name", "") or ref.id)


def _controlled_cities(world: Any, kind: str, owner_id: str) -> list[Any]:
    if kind not in {"sect", "dynasty"}:
        return []
    result = []
    for institution in world.institutional_authority.institutions.values():
        if institution.kind is not InstitutionKind.CITY:
            continue
        try:
            governance = world.map.regions[int(institution.owner_ref.id)].city_state.governance
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        if governance.controller_kind == kind and str(governance.controller_id) == owner_id:
            result.append(institution)
    return sorted(result, key=lambda item: item.id)


def _sponsoring_institution_id(world: Any, event: Any) -> str | None:
    """Return the canonical sponsor for a valid institutional rite projection."""
    if str(getattr(event, "event_type", "")) != "dao_rite":
        return None
    if bool(getattr(event, "is_story", False)):
        return None
    if getattr(event, "fact_kind", None) is not FactKind.OCCURRENCE:
        return None
    if getattr(event, "causal_origin", None) is not CausalOrigin.ACTOR_DECISION:
        return None
    payload = event.causal_payload if isinstance(event.causal_payload, Mapping) else {}
    rite = payload.get("dao_rite")
    if (
        not isinstance(rite, Mapping)
        or rite.get("is_sponsorship") is not True
        or rite.get("is_popular") is True
    ):
        return None
    sponsor_id = rite.get("sponsor_institution_id")
    if not isinstance(sponsor_id, str) or not sponsor_id:
        return None
    try:
        institution = world.institutional_authority.get_institution(sponsor_id)
    except (AttributeError, TypeError, ValueError):
        return None
    if institution is None or str(getattr(institution, "id", "")) != sponsor_id:
        return None
    return sponsor_id


def _party_ids(
    world: Any,
    event: Any,
    *,
    visited: set[str] | None = None,
    depth: int = 0,
    memo: dict[str, set[str]] | None = None,
) -> set[str]:
    """Correlate events by canonical payload, EntityRef, and causal links only."""
    if bool(getattr(event, "is_story", False)):
        return set()
    event_id = str(event.id)
    if memo is not None and event_id in memo:
        return set(memo[event_id])
    visited = set() if visited is None else visited
    if event_id in visited or depth >= 3 or len(visited) >= 16:
        return set()
    visited.add(event_id)
    payload = event.causal_payload if isinstance(event.causal_payload, Mapping) else {}
    result: set[str] = set()
    if event.event_type == "civil_work_stoppage_started":
        return _civil_stoppage_party_ids(world, event)
    if event.event_type == "civil_work_stoppage_ended":
        return _civil_stoppage_transition_party_ids(world, event)
    if event.event_type == "regional_production_forgone":
        return _civil_forgone_party_ids(world, event)
    # Owner transitions for city maintenance/projects carry the factual region
    # in render_params; project history must not depend on today's controller.
    if event.event_type in {"city_maintenance_completed", "urban_capacity_project_started"}:
        region_id = (event.render_params or {}).get("region_id") if isinstance(event.render_params, Mapping) else None
        if region_id is not None:
            try:
                city = world.institutional_authority.get_institution_for_owner(
                    EntityRef("region", str(region_id))
                )
            except (AttributeError, TypeError, ValueError):
                city = None
            if city is not None:
                result.add(str(city.id))
    civil_petition = payload.get("civil_petition")
    if event.event_type == "civil_public_petition":
        # This is a closed projection shape: malformed petition facts must not
        # inherit institutions from otherwise-valid ancestor links.
        if (
            event.fact_kind is not FactKind.OCCURRENCE
            or event.causal_origin is not CausalOrigin.ACTOR_DECISION
            or not isinstance(civil_petition, Mapping)
        ):
            return set()
        return _civil_petition_party_ids(world, civil_petition)
    sponsor_id = _sponsoring_institution_id(world, event)
    if str(getattr(event, "event_type", "")) == "dao_rite":
        if sponsor_id is not None:
            result.add(sponsor_id)
        if memo is not None:
            memo[event_id] = set(result)
        return result
    # Sect participation is an explicit canonical fact on typed institutional
    # diplomacy events.  Resolve it through the authority state so the
    # projection emits the stable institution IDs used everywhere else.
    if event.event_type in _PEACE_EVENT_TYPES:
        for sect_id in event.related_sects or ():
            try:
                sect = world.institutional_authority.get_institution_for_owner(
                    EntityRef("sect", str(sect_id))
                )
            except (AttributeError, TypeError, ValueError):
                sect = None
            if sect is not None:
                result.add(str(sect.id))
    aggression = payload.get("avatar_aggression")
    if event.event_type in _AGGRESSION_EVENT_TYPES and isinstance(aggression, Mapping):
        result.update(
            str(aggression[key])
            for key in ("initiator_institution_id", "target_institution_id")
            if aggression.get(key)
        )
    relationship_impact = payload.get("relationship_impact")
    if isinstance(relationship_impact, Mapping):
        result.update(
            str(relationship_impact[key])
            for key in ("observer_institution_id", "counterparty_institution_id")
            if relationship_impact.get(key)
        )
    request = payload.get("institutional_aid_request")
    if isinstance(request, Mapping):
        result.update(str(request[key]) for key in ("requester_institution_id", "provider_institution_id") if request.get(key))
    offer = payload.get("institutional_trade_offer")
    if isinstance(offer, Mapping):
        result.update(
            str(offer[key])
            for key in ("proposer_institution_id", "counterparty_institution_id")
            if offer.get(key)
        )
    peace_proposal = payload.get("peace_proposal")
    if isinstance(peace_proposal, Mapping):
        result.update(
            str(peace_proposal[key])
            for key in ("proposer_institution_id", "counterparty_institution_id")
            if peace_proposal.get(key)
        )
    commitment_id = payload.get("commitment_id")
    if commitment_id:
        commitment = world.institutional_relations.commitments.get(str(commitment_id))
        if commitment:
            result.update(commitment.party_ids)
    execution = payload.get("execution")
    if isinstance(execution, Mapping):
        for field in ("source_region_id", "destination_region_id"):
            if execution.get(field) is not None:
                institution = world.institutional_authority.get_institution_for_owner(EntityRef("region", str(execution[field])))
                if institution:
                    result.add(institution.id)
    decision = payload.get("decision")
    if isinstance(decision, Mapping):
        try:
            institution = world.institutional_authority.get_institution_for_owner(EntityRef(str(decision["subject_kind"]), str(decision["subject_id"])))
        except (KeyError, TypeError, ValueError):
            institution = None
        if institution:
            result.add(institution.id)
    for link in world.event_manager.get_causal_links_for_event(event.id)[:3]:
        cause = world.event_manager.get_event_by_id(link.cause_event_id)
        if cause is not None:
            cause_payload = cause.causal_payload if isinstance(cause.causal_payload, Mapping) else {}
            if (
                isinstance(cause_payload.get("institutional_aid_request"), Mapping)
                or isinstance(cause_payload.get("institutional_trade_offer"), Mapping)
                or isinstance(cause_payload.get("decision"), Mapping)
                or isinstance(cause_payload.get("peace_proposal"), Mapping)
                or cause.event_type in _PEACE_EVENT_TYPES
                or isinstance(cause_payload.get("avatar_aggression"), Mapping)
                or cause.event_type in _AGGRESSION_EVENT_TYPES
                or cause.event_type in {"civil_public_petition", "city_maintenance_completed", "urban_capacity_project_started"}
            ):
                result.update(_party_ids(world, cause, visited=visited, depth=depth + 1, memo=memo))
    if memo is not None:
        memo[event_id] = set(result)
    return result


def _decision(payload: Mapping[str, Any]) -> dict[str, str] | None:
    audit = payload.get("decision")
    if not isinstance(audit, Mapping):
        return None
    interpretation = payload.get("interpretation")
    action = ""
    if isinstance(interpretation, Mapping):
        action = str(interpretation.get("decision") or interpretation.get("selected_affordance_id") or "")
    if not action and isinstance(audit.get("chosen_chain"), list) and audit["chosen_chain"]:
        chosen = audit["chosen_chain"][0]
        if isinstance(chosen, Mapping):
            action = str(chosen.get("selected_affordance_id") or chosen.get("action_name") or "")
    return {"actor_kind": str(audit.get("subject_kind") or ""), "actor_id": str(audit.get("subject_id") or ""), "action": action, "reason": str(audit.get("thinking") or "")}


def _event_row(world: Any, event: Any) -> dict[str, Any]:
    payload = event.causal_payload if isinstance(event.causal_payload, Mapping) else {}
    links = list(world.event_manager.get_causal_links_for_event(event.id))
    offer = payload.get("institutional_trade_offer")
    trade_offer = None
    if isinstance(offer, Mapping):
        legs = offer.get("legs")
        if isinstance(legs, list):
            projected_legs = []
            for leg in legs:
                if not isinstance(leg, Mapping):
                    continue
                amount = leg.get("amount")
                if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                    continue
                projected = {
                    "source_region_id": str(leg.get("source_region_id") or ""),
                    "destination_region_id": str(leg.get("destination_region_id") or ""),
                    "resource_id": str(leg.get("resource_id") or ""),
                    "route_id": str(leg.get("route_id") or ""),
                    "amount": amount,
                    "source_institution_id": None,
                    "destination_institution_id": None,
                }
                for field, output in (("source_region_id", "source_institution_id"), ("destination_region_id", "destination_institution_id")):
                    region_id = leg.get(field)
                    if region_id is not None:
                        owner = world.institutional_authority.get_institution_for_owner(EntityRef("region", str(region_id)))
                        if owner:
                            projected[output] = owner.id
                projected_legs.append(projected)
            trade_offer = {
                "proposer_institution_id": str(offer.get("proposer_institution_id") or ""),
                "counterparty_institution_id": str(offer.get("counterparty_institution_id") or ""),
                "urgency": offer.get("urgency"),
                "legs": projected_legs,
            }
    return {"event_id": str(event.id), "content": str(event.content or ""), "event_type": str(event.event_type or ""), "month_stamp": int(event.month_stamp), "fact_kind": getattr(event.fact_kind, "value", str(event.fact_kind)), "causal_origin": getattr(event.causal_origin, "value", str(event.causal_origin)), "commitment_id": str(payload["commitment_id"]) if payload.get("commitment_id") else None, "term_id": str(payload["term_id"]) if payload.get("term_id") else None, "relation": getattr(getattr(links[0], "relation", None), "value", None) if links else None, "source_event_ids": [str(link.cause_event_id) for link in links], "decision": _decision(payload), "trade_offer": trade_offer}


def _event_page(world: Any, institution_ids: set[str], cursor: str | None, limit: int) -> tuple[list[dict[str, Any]], str | None, bool, set[str]]:
    stable_cursor = _decode_cursor(cursor)
    rows: list[dict[str, Any]] = []
    participant_ids: set[str] = set()
    party_memo: dict[str, set[str]] = {}
    last_scan_cursor = stable_cursor
    last_page_has_more = False
    for _ in range(_EVENT_SCAN_PAGES):
        page = world.event_manager.query_page(EventQuery(
            stable_cursor=stable_cursor,
            stable_order=True,
            limit=_EVENT_SCAN_PAGE_SIZE,
            include_decisions=True,
        ))
        if not page.events:
            break
        last_page_has_more = page.next_cursor is not None
        for event in page.events:
            payload = event.causal_payload if isinstance(event.causal_payload, Mapping) else {}
            is_decision = isinstance(payload.get("decision"), Mapping)
            if event.event_type in _EVENT_TYPES or is_decision:
                parties = _party_ids(world, event, memo=party_memo)
                if parties.intersection(institution_ids):
                    participant_ids.update(parties)
                    rows.append(_event_row(world, event))
                    if len(rows) > limit:
                        consumed = rows[:limit]
                        return consumed, _encode_cursor(consumed[-1]["month_stamp"], consumed[-1]["event_id"]), True, participant_ids
        last_scan_cursor = _key(page.events[-1])
        stable_cursor = last_scan_cursor
        if not last_page_has_more:
            break
    if last_page_has_more and last_scan_cursor is not None:
        return rows, _encode_cursor(*last_scan_cursor), True, participant_ids
    return rows, None, False, participant_ids


def _term(term: Any) -> dict[str, Any]:
    return {"id": term.id, "index": term.index, "kind": term.kind.value, "obligor_institution_id": term.obligor_institution_id, "beneficiary_institution_id": term.beneficiary_institution_id, "subject": term.subject.to_dict(), "status": term.status.value, "proposed_month": term.proposed_month, "due_month": term.due_month, "breached_month": term.breached_month, "resolved_month": term.resolved_month, "parameters": dict(term.parameters), "evidence_event_ids": list(term.evidence_event_ids), "breach_event_ids": list(term.breach_event_ids), "remediation_of_term_id": term.remediation_of_term_id}


def _relation(relation: Any) -> dict[str, Any]:
    return {
        "id": relation.id,
        "institution_a_id": relation.institution_a_id,
        "institution_b_id": relation.institution_b_id,
        "kind": relation.kind.value,
        "friendliness": relation.friendliness,
        "since_month": relation.since_month,
        "evidence_event_ids": list(relation.evidence_event_ids),
    }


def build_institutional_chain(world: Any, *, owner_kind: str, owner_id: str, commitment_cursor: str | None = None, event_cursor: str | None = None, limit: int = 20) -> dict[str, Any]:
    if owner_kind not in _OWNER_KINDS:
        raise ValueError("owner_kind must be region, sect, or dynasty")
    if world is None:
        raise RuntimeError("world is unavailable")
    page_limit = max(1, min(int(limit), 50))
    authority = world.institutional_authority
    owner_ref = EntityRef(owner_kind, str(owner_id))
    institution = authority.get_institution_for_owner(owner_ref)
    if institution is None:
        raise KeyError("institution not found")
    controlled = _controlled_cities(world, owner_kind, str(owner_id))
    queried_ids = {institution.id, *(item.id for item in controlled)}
    after = _decode_cursor(commitment_cursor)
    commitments = sorted((item for item in world.institutional_relations.commitments.values() if queried_ids.intersection(item.party_ids)), key=lambda item: (item.opened_month, item.id), reverse=True)
    if after:
        commitments = [item for item in commitments if (item.opened_month, item.id) < after]
    has_more = len(commitments) > page_limit
    commitments = commitments[:page_limit]
    commitment_rows = []
    for commitment in commitments:
        direct = institution.id in commitment.party_ids
        actual_owner = institution.id if direct else next(city.id for city in controlled if city.id in commitment.party_ids)
        commitment_rows.append({"id": commitment.id, "party_ids": list(commitment.party_ids), "opened_month": commitment.opened_month, "closed_month": commitment.closed_month, "aggregate_status": commitment.aggregate_status.value, "owner_institution_id": actual_owner, "control_scope": "direct" if direct else "governed_city", "origin_event_id": commitment.origin_event_id, "terms": [_term(term) for term in commitment.terms]})
    events, event_next, event_more, timeline_participants = _event_page(world, queried_ids, event_cursor, page_limit)
    relations = sorted(
        (
            relation
            for relation in world.institutional_relations.relations.values()
            if queried_ids.intersection(
                (relation.institution_a_id, relation.institution_b_id)
            )
        ),
        key=lambda relation: (relation.since_month, relation.id),
        reverse=True,
    )[:page_limit]
    participants = {party for commitment in commitments for party in commitment.party_ids}
    participants.update(timeline_participants)
    participants.update(
        party
        for relation in relations
        for party in (relation.institution_a_id, relation.institution_b_id)
    )
    institutions = [{"id": institution.id, "kind": institution.kind.value, "name": _name(world, institution), "scope": "owner"}]
    institutions += [{"id": city.id, "kind": city.kind.value, "name": _name(world, city), "scope": "governed_city"} for city in controlled]
    for participant_id in sorted(participants - queried_ids):
        participant = authority.get_institution(participant_id)
        if participant:
            institutions.append({"id": participant.id, "kind": participant.kind.value, "name": _name(world, participant), "scope": "party"})
    offices = authority.offices_for(institution.id)
    memories = sorted((memory for memory in world.institutional_relations.memories.values() if memory.institution_id in queried_ids), key=lambda memory: (memory.recorded_month, memory.id), reverse=True)[:page_limit]
    scopes = (AuthorityScope.URBAN_ADMINISTRATION, AuthorityScope.RESOURCE_DISPOSITION, AuthorityScope.COMMITMENT_NEGOTIATION)
    return {"owner": {"kind": institution.kind.value, "id": str(owner_id), "institution_id": institution.id, "name": _name(world, institution), "region_id": str(owner_id) if owner_kind == "region" else None}, "current_month": int(world.month_stamp), "authority": {"institution_id": institution.id, "office_ids": [office.id for office in offices], "active_claim_ids": [claim.id for office in offices for claim in authority.active_claims(office.id)], "material_control": {scope.value: can_actor_act_for(world, owner_ref, owner_ref, scope, current_month=int(world.month_stamp)).allowed for scope in scopes}}, "institutions": institutions, "relations": [_relation(relation) for relation in relations], "commitments": commitment_rows, "events": events, "memories": [{"id": memory.id, "institution_id": memory.institution_id, "event_id": memory.event_id, "salience": memory.salience, "recorded_month": memory.recorded_month, "last_reinforced_month": memory.last_reinforced_month, "effective_salience": effective_salience(memory, int(world.month_stamp)), "factors": dict(memory.factors)} for memory in memories], "cursor": {"commitments": {"next": _encode_cursor(commitments[-1].opened_month, commitments[-1].id) if has_more and commitments else None, "has_more": has_more}, "events": {"next": event_next, "has_more": event_more}}}

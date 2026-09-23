"""Actor-specific negotiation inputs; foreign balances and techniques are absent."""
from dataclasses import dataclass
from src.classes.mechanical_language import EntityRef
from src.classes.governance.authority import can_actor_act_for
from .institutional_memory import institutional_views


@dataclass(frozen=True)
class DiplomaticContext:
    actor: EntityRef
    account_id: str | None
    balance: int
    budget: int
    techniques: frozenset[str]
    capabilities: frozenset[str]
    research_costs: tuple[tuple[str, int], ...]
    proposal_ids: tuple[str, ...]
    authority: frozenset[str]
    institutional_views: tuple[tuple[EntityRef, int, tuple[str, ...]], ...]
    strategic_capacity: dict[str, object]
    strategic_evidence: tuple[dict[str, object], ...]


def strategic_evidence(world, actor=None):
    """Private findings for one actor, or all findings for the Dao projection."""
    records = []
    for finding in world.knowledge.espionage_findings.values():
        if actor is not None and finding.recipient_ref != actor:
            continue
        records.append({
            "kind": "espionage",
            "finding_id": finding.id,
            "result": finding.result,
            "recipient_ref": finding.recipient_ref.to_dict(),
            "target_ref": finding.target_ref.to_dict(),
            "target_owner_ref": finding.target_owner_ref.to_dict(),
            "evidence_event_id": finding.evidence_event_id,
            "event_id": finding.event_id,
        })
    for finding in world.knowledge.investigation_findings.values():
        if actor is not None and finding.recipient_ref != actor:
            continue
        records.append({
            "kind": "investigation",
            "finding_id": finding.id,
            "result": finding.result,
            "recipient_ref": finding.recipient_ref.to_dict(),
            "subject_ref": finding.subject_ref.to_dict() if finding.subject_ref else None,
            "damage_event_id": finding.damage_event_id,
            "event_id": finding.event_id,
        })
    for notice in world.knowledge.investigation_accusation_notices.values():
        if actor is not None and notice.recipient_ref != actor:
            continue
        records.append({
            "kind": "investigation_accusation",
            "notice_id": notice.id,
            "result": "notified",
            "recipient_ref": notice.recipient_ref.to_dict(),
            "accuser_ref": notice.accuser_ref.to_dict(),
            "investigation_id": notice.investigation_id,
            "site_id": notice.site_id,
            "subject_ref": notice.subject_ref.to_dict(),
            "finding_event_id": notice.finding_event_id,
            "event_id": notice.event_id,
        })
    # Responses are factual occurrences, not a second knowledge registry.  A
    # direct response is visible to its author and to the accusing institution;
    # unrelated actors cannot infer it merely because they can see the ledger.
    notices = world.knowledge.investigation_accusation_notices
    for event in world.events:
        if event.event_type != "investigation_accusation_response" or not event.causal_payload:
            continue
        notice = notices.get(event.causal_payload.get("notice_id"))
        actor_payload = event.causal_payload.get("actor_ref")
        if notice is None or not isinstance(actor_payload, dict):
            continue
        response_actor = EntityRef.from_dict(actor_payload)
        if actor is not None and actor not in {response_actor, notice.accuser_ref}:
            continue
        records.append({
            "kind": "investigation_accusation_response",
            "event_id": event.id,
            "notice_id": notice.id,
            "actor_ref": response_actor.to_dict(),
            "recipient_ref": notice.accuser_ref.to_dict(),
            "response": event.causal_payload.get("response"),
            "accusation_event_id": notice.event_id,
        })
    for finding in world.knowledge.technology_theft_findings.values():
        if actor is not None and finding.recipient_ref != actor:
            continue
        records.append({
            "kind": "technology_theft",
            "finding_id": finding.id,
            "result": finding.result,
            "recipient_ref": finding.recipient_ref.to_dict(),
            "site_id": finding.site_id,
            "target_owner_ref": finding.target_owner_ref.to_dict(),
            "technology_id": finding.technology_id,
            "observation_event_id": finding.observation_event_id,
            "source_knowledge_event_id": finding.source_knowledge_event_id,
            "learned_knowledge_event_id": finding.learned_knowledge_event_id,
            "event_id": finding.event_id,
        })
    return tuple(sorted(records, key=lambda item: (
        str(item["kind"]), str(item.get("finding_id") or item.get("notice_id") or item["event_id"]))))


def diplomatic_context(world, actor):
    from .actor_dossier import provider_strategic_capacity
    last_identity = id(world.events[-1]) if world.events else 0
    knowledge_size = sum(len(getattr(world.knowledge, name)) for name in world.knowledge.registries)
    signature = (len(world.events), last_identity, knowledge_size)
    cached = world._diplomatic_context_cache
    if cached is None or cached[0] != signature:
        cached = (signature, {})
        world._diplomatic_context_cache = cached
    cache_key = (actor.kind, actor.id)
    if cache_key in cached[1]:
        return cached[1][cache_key]
    accounts = sorted((a for a in world.economy.accounts.values() if a.owner_ref == actor), key=lambda a:a.id)
    account = accounts[0] if accounts else None
    stocks = sorted((s for s in world.economy.stocks.values() if s.owner_ref == actor), key=lambda s:s.id)
    prices = world.economy.markets[stocks[0].location_id].prices if stocks else {
        r.id:r.base_price for r in world.economy.resources.values()}
    wages = sum(f.max_batches * world.economy.recipes[f.recipe_id].workers * f.wage_per_worker
                for f in world.economy.facilities.values() if account and f.payroll_account_id == account.id)
    # Keep one current payroll period protected while leaving the remaining
    # treasury available for a dated diplomatic choice.  Reserving two full
    # periods made a legitimate counteroffer disappear in otherwise solvent
    # fixtures as facility capacity grew; the owner still revalidates the
    # actual account before any payment executes.
    context = DiplomaticContext(actor=actor, account_id=account.id if account else None,
        balance=account.balance if account else 0, budget=max(0, account.balance - wages) if account else 0,
        techniques=frozenset(k.technology_id for k in world.knowledge.technologies.values() if k.owner_ref == actor),
        capabilities=frozenset(c for s in world.map.infrastructure_sites.values()
            if s.owner_ref == actor and s.enabled and s.integrity > 0 for c in s.capability_ids),
        research_costs=tuple((t.id,t.required_units*(sum(prices[r]*q for r,q in t.inputs.items())
            +(t.assistants_per_unit+1)*t.wage_per_worker)) for t in sorted(world.research.technologies.values(),key=lambda t:t.id)),
        proposal_ids=tuple(sorted({n.proposal_id for n in world.knowledge.notices.values() if n.recipient_ref == actor})),
        authority=frozenset(s for s in ('diplomacy','research','trade') if can_actor_act_for(world,actor,actor,s)),
        institutional_views=institutional_views(world, actor),
        strategic_capacity=provider_strategic_capacity(world, actor),
        strategic_evidence=strategic_evidence(world, actor))
    cached[1][cache_key] = context
    return context

"""Actor-specific negotiation inputs; foreign balances and techniques are absent."""
from dataclasses import dataclass
from src.classes.mechanical_language import EntityRef
from src.classes.governance.authority import can_actor_act_for


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


def diplomatic_context(world, actor):
    accounts = sorted((a for a in world.economy.accounts.values() if a.owner_ref == actor), key=lambda a:a.id)
    account = accounts[0] if accounts else None
    stocks = sorted((s for s in world.economy.stocks.values() if s.owner_ref == actor), key=lambda s:s.id)
    prices = world.economy.markets[stocks[0].location_id].prices if stocks else {
        r.id:r.base_price for r in world.economy.resources.values()}
    wages = sum(f.max_batches * world.economy.recipes[f.recipe_id].workers * f.wage_per_worker
                for f in world.economy.facilities.values() if account and f.payroll_account_id == account.id)
    return DiplomaticContext(actor=actor, account_id=account.id if account else None,
        balance=account.balance if account else 0, budget=max(0,account.balance - wages*2) if account else 0,
        techniques=frozenset(k.technology_id for k in world.knowledge.technologies.values() if k.owner_ref == actor),
        capabilities=frozenset(c for s in world.map.infrastructure_sites.values()
            if s.owner_ref == actor and s.enabled and s.integrity > 0 for c in s.capability_ids),
        research_costs=tuple((t.id,t.required_units*(sum(prices[r]*q for r,q in t.inputs.items())
            +(t.assistants_per_unit+1)*t.wage_per_worker)) for t in sorted(world.research.technologies.values(),key=lambda t:t.id)),
        proposal_ids=tuple(sorted({n.proposal_id for n in world.knowledge.notices.values() if n.recipient_ref == actor})),
        authority=frozenset(s for s in ('diplomacy','research','trade') if can_actor_act_for(world,actor,actor,s)))

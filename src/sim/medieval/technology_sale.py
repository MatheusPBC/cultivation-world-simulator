"""A bounded, paid transfer of one known technology between institutions.

The buyer only receives an offer for a technique it was factually shown, can
actually apply at one of its own usable sites, and can pay for from its own
account.  The holder independently consents after recomposing the same
affordance.  Economy moves the money; Knowledge records the new ownership.
There is no inventory of techniques and no transfer of the seller's knowledge.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .economy import _causes
from .events import record_event
from .economy import transfer_money
from .research import learn_technology


REQUEST_ACTION = "buy_technology"
ACCEPT_ACTION = "sell_technology"
SALE_RECEIPT = "technology_sale_completed"


@dataclass(frozen=True)
class TechnologySaleOption:
    """Transient buyer affordance; only its deterministic ID is selected."""

    id: Identity
    buyer_ref: EntityRef
    seller_ref: EntityRef
    technology_id: Identity
    sighting_event_id: Identity
    source_event_id: Identity
    buyer_site_id: Identity
    seller_site_id: Identity
    buyer_account_id: Identity
    seller_account_id: Identity
    amount: int
    quote_day: int

    def decision(self):
        return {"action": REQUEST_ACTION, "actor_ref": self.buyer_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class TechnologySaleAcceptance:
    """Transient seller consent, recomposed from a current buyer decision."""

    id: Identity
    request_event_id: Identity
    request_option_id: Identity
    buyer_ref: EntityRef
    seller_ref: EntityRef
    technology_id: Identity

    def decision(self):
        return {"action": ACCEPT_ACTION, "actor_ref": self.seller_ref.to_dict(),
                "selected_affordance_id": self.id}


def _usable_site(world, actor, technology):
    return next((site for _, site in sorted(world.map.infrastructure_sites.items())
                 if site.owner_ref == actor and site.enabled and site.integrity > 0
                 and technology.capability_id in site.capability_ids), None)


def _settlement_for_site(world, site):
    return next((settlement for _, settlement in sorted(world.society.settlements.items())
                 if settlement.region_id in site.region_ids), None)


def technology_sale_price(world, technology, seller_site):
    """Engine-owned price: one complete research cost at the holder's market."""
    settlement = _settlement_for_site(world, seller_site)
    if settlement is None:
        return None
    market = world.economy.markets.get(settlement.id)
    if market is None:
        return None
    materials = sum(market.prices[resource_id] * quantity
                    for resource_id, quantity in technology.inputs.items())
    wages = (technology.assistants_per_unit + 1) * technology.wage_per_worker
    return max(1, technology.required_units * (materials + wages))


def _account(world, owner):
    return next((account for _, account in sorted(world.economy.accounts.items())
                 if account.owner_ref == owner), None)


def technology_sale_options(world, buyer):
    """Current paid-sale options derived only from the buyer's own facts."""
    if (not isinstance(buyer, EntityRef)
            or any(not can_actor_act_for(world, buyer, buyer, scope) for scope in ("research", "trade"))):
        return ()
    buyer_account = _account(world, buyer)
    options = []
    day = world.clock.absolute_day
    for sighting in world.knowledge.technology_sightings_for_actor(buyer, current_day=day):
        technology = world.research.technologies.get(sighting.technology_id)
        if technology is None or sighting.holder_ref == buyer or world.knowledge.knows(buyer, technology.id):
            continue
        if any(not world.knowledge.knows(buyer, prerequisite) for prerequisite in technology.prerequisites):
            continue
        buyer_site = _usable_site(world, buyer, technology)
        seller_site = _usable_site(world, sighting.holder_ref, technology)
        seller_account = _account(world, sighting.holder_ref)
        amount = technology_sale_price(world, technology, seller_site) if seller_site else None
        if (buyer_site is None or seller_site is None or buyer_account is None or seller_account is None
                or amount is None or buyer_account.balance < amount):
            continue
        options.append(TechnologySaleOption(
            id=(f"technology-sale:{buyer.kind}:{buyer.id}:{sighting.holder_ref.kind}:"
                f"{sighting.holder_ref.id}:{technology.id}:{sighting.event_id}:"
                f"{buyer_site.id}:{seller_site.id}:{buyer_account.id}:{seller_account.id}:{amount}:{day}"),
            buyer_ref=buyer, seller_ref=sighting.holder_ref, technology_id=technology.id,
            sighting_event_id=sighting.event_id, source_event_id=sighting.source_event_id,
            buyer_site_id=buyer_site.id, seller_site_id=seller_site.id,
            buyer_account_id=buyer_account.id, seller_account_id=seller_account.id,
            amount=amount, quote_day=day))
    return tuple(options)


def _current_request(world, event):
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision is None or event.decision.get("action") != REQUEST_ACTION
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        return None
    try:
        buyer = EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError):
        return None
    return next((option for option in technology_sale_options(world, buyer)
                 if option.id == event.decision.get("selected_affordance_id")
                 and option.decision() == event.decision), None)


def technology_sale_acceptance_options(world, seller):
    """Current seller consents for buyer requests addressed to this holder."""
    if (not isinstance(seller, EntityRef)
            or any(not can_actor_act_for(world, seller, seller, scope) for scope in ("research", "trade"))):
        return ()
    options = []
    for event in world.events:
        if event.fact_kind != FactKind.DECISION or event.decision is None:
            continue
        request = _current_request(world, event)
        if request is None or request.seller_ref != seller:
            continue
        if any(item.event_type == SALE_RECEIPT and event.id in {
                link.cause_event_id for link in item.causal_links} for item in world.events):
            continue
        options.append(TechnologySaleAcceptance(
            id=f"technology-sale-accept:{event.id}:{request.id}", request_event_id=event.id,
            request_option_id=request.id,
            buyer_ref=request.buyer_ref, seller_ref=seller, technology_id=request.technology_id))
    return tuple(options)


def record_technology_sale_request(world, buyer, option_id):
    option = next((item for item in technology_sale_options(world, buyer) if item.id == option_id), None)
    if option is None:
        raise ValueError("technology sale option is stale or unknown")
    return record_event(world, "technology_sale_requested",
                        "Uma instituição pediu comprar uma técnica que pode aplicar.",
                        fact_kind=FactKind.DECISION, decision=option.decision(),
                        cause_ids=_causes(option.sighting_event_id, option.source_event_id))


def record_technology_sale_acceptance(world, seller, option_id):
    option = next((item for item in technology_sale_acceptance_options(world, seller) if item.id == option_id), None)
    if option is None:
        raise ValueError("technology sale acceptance is stale or unknown")
    return record_event(world, "technology_sale_accepted",
                        "O detentor consentiu vender a técnica pelo preço material calculado.",
                        fact_kind=FactKind.DECISION, decision=option.decision(),
                        cause_ids=(option.request_event_id,))


def execute_technology_sale(world, buyer, option_id, request_event_id, acceptance_event_id):
    """Revalidate both consents, pay, then grant only the purchased knowledge."""
    candidate = deepcopy(world)
    if any(item.event_type == SALE_RECEIPT and request_event_id in {
            link.cause_event_id for link in item.causal_links} for item in candidate.events):
        raise ValueError("technology sale decision already executed")
    request_event = next((item for item in candidate.events if item.id == request_event_id), None)
    option = _current_request(candidate, request_event)
    if option is None or option.buyer_ref != buyer or option.id != option_id:
        raise ValueError("technology sale request is stale or unknown")
    acceptance_event = next((item for item in candidate.events if item.id == acceptance_event_id), None)
    acceptance = next((item for item in technology_sale_acceptance_options(candidate, option.seller_ref)
                      if item.request_event_id == request_event_id), None)
    if (acceptance is None or acceptance_event is None or acceptance_event.decision is None
            or acceptance.id != acceptance_event.decision.get("selected_affordance_id")
            or acceptance_event.decision != acceptance.decision()):
        raise ValueError("technology sale acceptance is stale or unknown")
    require_authority(candidate, option.buyer_ref, "research")
    require_authority(candidate, option.buyer_ref, "trade")
    require_authority(candidate, option.seller_ref, "research")
    require_authority(candidate, option.seller_ref, "trade")
    source = next((item for item in candidate.knowledge.technologies.values()
                   if item.owner_ref == option.seller_ref and item.technology_id == option.technology_id), None)
    if source is None:
        raise ValueError("technology sale source knowledge is stale")
    transfer_money(candidate, option.buyer_account_id, option.seller_account_id, option.amount,
                   decision_event_id=request_event_id, decision_intent=request_event.decision)
    # transfer_money intentionally returns no event; recover its canonical receipt by the payment index.
    payment_event_id = candidate.economy.payments[request_event_id]
    learn_technology(candidate, option.buyer_ref, option.technology_id, "sale",
                     _causes(request_event_id, acceptance_event_id, option.sighting_event_id,
                             option.source_event_id, source.event_id, payment_event_id))
    knowledge = next((item for item in candidate.knowledge.technologies.values()
                      if item.owner_ref == option.buyer_ref and item.technology_id == option.technology_id), None)
    if knowledge is None:
        raise ValueError("technology sale did not record the learned technique")
    receipt = record_event(candidate, SALE_RECEIPT,
                           "Pagamento concluído e a técnica foi transferida ao comprador.",
                           fact_kind=FactKind.OCCURRENCE,
                           cause_ids=_causes(request_event_id, acceptance_event_id, payment_event_id,
                                             knowledge.event_id, option.sighting_event_id, source.event_id))
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return receipt


__all__ = ["REQUEST_ACTION", "ACCEPT_ACTION", "TechnologySaleOption", "TechnologySaleAcceptance",
           "technology_sale_price", "technology_sale_options", "technology_sale_acceptance_options",
           "record_technology_sale_request", "record_technology_sale_acceptance", "execute_technology_sale"]

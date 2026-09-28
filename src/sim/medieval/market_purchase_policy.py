"""Bilateral institutional consent for a known market purchase.

The buyer's civil menu records a dated request only.  A seller receives a
separate, transient acceptance affordance recomposed from that request.  Only
the seller's acceptance materializes the existing procurement executor; no
seller response is inferred by the buyer's choice.

Requests are valid only on their creation day.  Consequently, if the seller
has already taken its monthly turn, it cannot answer on the next boundary;
the buyer must request again after a fresh quote.  This makes actor ordering
observable rather than turning the request into a hidden persistent proposal.
"""

from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .events import record_event
from .institutional_decision_turn import DECISION_EVENT_TYPE, DiscretionaryAdapter
from .procurement import (MARKET_PURCHASE_ACTION, execute_market_purchase_option,
                          market_purchase_options, market_purchase_terms)
from .economy import _causes

MARKET_SALE_ACCEPT_ACTION = "accept_market_purchase"
_CONSULTATION_RECEIPT_TYPES = {"ai_decision_interpreted", "ai_decision_declined"}


@dataclass(frozen=True)
class MarketPurchaseAcceptance:
    """Seller affordance reconstructed from one current buyer request."""

    id: Identity
    request_event_id: Identity
    request_option_id: Identity
    buyer_ref: EntityRef
    seller_ref: EntityRef
    offer_id: Identity
    resource_id: Identity
    quantity: int
    total_price: int
    buyer_name: str
    origin_name: str
    destination_name: str

    def decision(self):
        return {"action": MARKET_SALE_ACCEPT_ACTION, "actor_ref": self.seller_ref.to_dict(),
                "selected_affordance_id": self.id}


def _current_request(world, event):
    if (event is None or event.fact_kind != FactKind.DECISION
            or event.causal_origin is not CausalOrigin.ACTOR_DECISION
            or event.day != world.clock.absolute_day or event.decision is None
            or event.decision.get("action") != MARKET_PURCHASE_ACTION
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        return None
    try:
        buyer = EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError):
        return None
    return next((option for option in market_purchase_options(world, buyer)
                 if option.id == event.decision.get("selected_affordance_id")
                 and option.decision() == event.decision), None)


def _request_was_presented_to_seller(world, seller, request_event_id):
    """Do not ask a seller twice about a request already in today's menu."""
    for event_type in _CONSULTATION_RECEIPT_TYPES:
        for receipt in world.events_of_type(event_type):
            if receipt.day != world.clock.absolute_day:
                continue
            selection = (receipt.causal_payload or {}).get("selection")
            if not isinstance(selection, dict) or selection.get("actor_ref") != seller.to_dict():
                continue
            if any(link.cause_event_id == request_event_id for link in receipt.causal_links):
                return True
    return False


def market_purchase_acceptance_options(world, seller):
    """Return only same-day requests whose quoted seller is this institution."""
    if not isinstance(seller, EntityRef):
        return ()
    # Seller authority is checked again by the material purchase owner.  Do
    # not expose an acceptance menu that could never be executed.
    from src.classes.governance.authority import can_actor_act_for
    if not can_actor_act_for(world, seller, seller, "trade"):
        return ()
    options = []
    sold_request_event_ids = {
        link.cause_event_id
        for event in world.events_of_type("sell_decided")
        for link in event.causal_links
    }
    # A request is the generic institutional decision receipt, but walking
    # every historical event once per seller makes this menu scale with the
    # whole world ledger. The transient event-type index keeps the canonical
    # receipt contract while skipping unrelated facts.
    for event in world.events_of_type(DECISION_EVENT_TYPE):
        if event.decision is None or event.decision.get("action") != MARKET_PURCHASE_ACTION:
            continue
        request = _current_request(world, event)
        if request is None:
            continue
        source = world.economy.stocks.get(request.source_id)
        if source is None or source.owner_ref != seller:
            continue
        # A request can only be executed once.  The payment index and order
        # ledger are both owner evidence; either one is enough to suppress a
        # duplicate transient acceptance.
        if (event.id in world.economy.payments
                or any(event.id in order.decision_ids for order in world.economy.freight_orders.values())
                or event.id in sold_request_event_ids):
            continue
        destination = world.economy.stocks[request.destination_id]
        buyer_state = (world.society.polities if request.actor_ref.kind == "polity"
                       else world.society.organizations)[request.actor_ref.id]
        options.append(MarketPurchaseAcceptance(
            id=f"market-purchase-accept:{event.id}:{request.id}",
            request_event_id=event.id, request_option_id=request.id,
            buyer_ref=request.actor_ref, seller_ref=seller, offer_id=request.offer_id,
            resource_id=request.resource_id, quantity=request.quantity,
            total_price=request.total_price, buyer_name=buyer_state.name,
            origin_name=world.society.settlements[source.location_id].name,
            destination_name=world.society.settlements[destination.location_id].name))
    return tuple(options)


def market_purchase_actors(world):
    """Discover account owners with a buyer request or seller response."""
    actors = set()
    for account in world.economy.accounts.values():
        actor = account.owner_ref
        if market_purchase_options(world, actor) or market_purchase_acceptance_options(world, actor):
            actors.add(actor)
    return tuple(sorted(actors, key=lambda ref: (ref.kind, ref.id)))


def market_purchase_response_actors(world):
    """Find sellers with a current request not already in today's menu."""
    account_owners = {account.owner_ref for account in world.economy.accounts.values()}
    response_actors = []
    for actor in sorted(account_owners, key=lambda ref: (ref.kind, ref.id)):
        pending = market_purchase_acceptance_options(world, actor)
        if any(not _request_was_presented_to_seller(world, actor, option.request_event_id)
               for option in pending):
            response_actors.append(actor)
    return tuple(response_actors)


def _options(world, actor):
    return (*market_purchase_options(world, actor), *market_purchase_acceptance_options(world, actor))


def _causes_for_option(world, option):
    if isinstance(option, MarketPurchaseAcceptance):
        return (option.request_event_id,)
    report = world.knowledge.reports.get(option.offer_id)
    causes = [report.event_id] if report is not None else []
    for route_id in option.route_ids:
        for item in (world.knowledge.route_report(option.actor_ref, route_id),
                     world.knowledge.fiscal_route_report(option.actor_ref, route_id)):
            if item is not None:
                causes.append(item.event_id)
    return tuple(sorted(set(causes)))


def _execute(world, actor, option_id, decision_event_id):
    option = next((item for item in _options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("market purchase option is stale or unknown")
    if not isinstance(option, MarketPurchaseAcceptance):
        # The generic institutional decision itself is the buyer's dated
        # request. It deliberately has no material executor.
        return None
    decision_event = next((event for event in world.events if event.id == decision_event_id), None)
    if (decision_event is None or decision_event.fact_kind != FactKind.DECISION
            or decision_event.causal_origin is not CausalOrigin.ACTOR_DECISION
            or decision_event.decision != option.decision()):
        raise ValueError("seller acceptance decision does not match its current affordance")
    request_event = next((event for event in world.events if event.id == option.request_event_id), None)
    request = _current_request(world, request_event)
    if request is None or request.seller_account_id != next(
            account.id for account in world.economy.accounts.values() if account.owner_ref == actor):
        raise ValueError("market purchase request disappeared")
    terms = market_purchase_terms(request)
    source = (decision_event.causal_payload or {}).get("decision_source")
    provenance = ({"decision_source": source} if source else {
        "decision_source": {"kind": "owner", "owner": "market_purchase",
                            "rule": "materialize_seller_selection"}
    })
    receipt_id = source.get("receipt_event_id") if source and source.get("kind") == "provider" else None
    # Markets still require a detailed seller consent.  The terms are
    # recomposed by the owner from the accepted affordance, never supplied by
    # the provider.  This event is caused by the seller's minimal decision.
    seller_decision = record_event(
        world, "sell_decided", "O vendedor aceitou o pedido de compra de mercado.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision={**terms, "action": "sell", "actor_ref": actor.to_dict(),
                  "selected_affordance_id": decision_event.decision["selected_affordance_id"]},
        causal_payload=provenance,
        cause_ids=_causes(decision_event_id, request_event.id,
                          *(_causes_for_option(world, request)), receipt_id))
    execute_market_purchase_option(world, request.actor_ref, request.id, request_event.id,
                                   seller_decision_id=seller_decision.id)


def market_purchase_adapters():
    return (
        DiscretionaryAdapter(
            name="market_purchase_request", family="supply",
            options_fn=market_purchase_options,
            label_fn=lambda option: f"Pedir compra de {option.resource_id} por rota conhecida.",
            causes_fn=_causes_for_option, execute_fn=_execute,
            claim_fn=lambda option: ("objective", option.objective_id)),
        DiscretionaryAdapter(
            name="market_purchase_acceptance", family="supply",
            options_fn=market_purchase_acceptance_options,
            label_fn=lambda option: (
                f"Vender {option.quantity} de {option.resource_id} para {option.buyer_name} "
                f"por {option.total_price} moedas, de {option.origin_name} "
                f"para {option.destination_name}."),
            causes_fn=_causes_for_option, execute_fn=_execute),
    )


__all__ = ["MARKET_SALE_ACCEPT_ACTION", "MarketPurchaseAcceptance",
           "market_purchase_acceptance_options", "market_purchase_actors",
           "market_purchase_response_actors",
           "market_purchase_adapters"]

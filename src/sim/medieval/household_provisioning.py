"""Local, prepaid household provisions for a possible migration; never consumption.

In provider mode the purchase is a two-turn bilateral decision: the household
selects a current public offer, then the offer owner independently accepts or
declines.  The old routine remains the offline safety net only.
"""

from dataclasses import dataclass

from src.classes.economy.models import Stock
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity
from .institutional_decision_turn import DiscretionaryAdapter
from .demand import reserve_quantity
from .economy import _causes, _delta
from .events import record_event


def household_stock_id(group_id):
    return f"household-stock:{group_id}"


def household_food_capacity(world, group_id):
    return 2 * world.society.population[group_id].count * world.economy.resources["food"].bulk


def _pressure(report):
    return report.missing_food > 0 or report.health < 700 or report.unrest >= 250


def _can_trade(world, owner):
    if owner.kind == "character":
        return owner.id in world.society.characters and world.society.characters[owner.id].death_day is None
    return can_actor_act_for(world, owner, owner, "trade")


def _known_destination(world, actor, source):
    from .migration_policy import _fresh, _route_path
    return any(destination.settlement_id != source.settlement_id and _fresh(world, destination)
               and destination.population < destination.housing_capacity
               and destination.health >= source.health and destination.missing_food <= source.missing_food
               and _route_path(world, actor, source.settlement_id, destination.settlement_id) is not None
               for destination in world.knowledge.settlements_for_actor(actor))


@dataclass(frozen=True)
class HouseholdProvisionPurchaseOption:
    """Transient household choice; terms are recomposed by the owner."""

    id: Identity
    actor_ref: EntityRef
    group_id: Identity
    offer_id: Identity
    quantity: int
    report_event_id: Identity

    def decision(self):
        return {"action": "buy_household_provisions", "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class HouseholdProvisionSaleOption:
    """Transient seller response to one known, still-open household intent."""

    id: Identity
    actor_ref: EntityRef
    buyer_group_id: Identity
    buyer_decision_id: Identity
    offer_id: Identity
    quantity: int
    response: str

    def decision(self):
        action = "sell_household_provisions" if self.response == "accept" else "decline_household_provisions"
        return {"action": action, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def household_provision_options(world, actor):
    """Enumerate current public offers a pressured, fully present household can buy."""
    if not isinstance(actor, EntityRef) or actor.kind != "population_group":
        return ()
    group = world.society.population.get(actor.id)
    if group is None or world.society.available_count(group.id) != group.count:
        return ()
    report = world.knowledge.settlement_report(actor, group.settlement_id)
    if (report is None or report.observed_day != world.clock.absolute_day
            or not _pressure(report) or not _known_destination(world, actor, report)):
        return ()
    pantry = world.economy.stocks.get(household_stock_id(group.id))
    stored = pantry.goods.get("food", 0) if pantry else 0
    desired = group.count
    buyer = world.economy.accounts.get(f"household:{group.id}")
    if buyer is None or stored >= desired:
        return ()
    capacity = household_food_capacity(world, group.id)
    effective_capacity = max(pantry.capacity, capacity) if pantry else capacity
    free_capacity = max(0, effective_capacity - stored * world.economy.resources["food"].bulk)
    options = []
    for offer in sorted(world.knowledge.for_actor(actor), key=lambda item: (item.unit_price, item.stock_id, item.id)):
        if (offer.kind != "offer" or offer.resource_id != "food"
                or offer.observed_day != world.clock.absolute_day or offer.quote_day != world.clock.absolute_day):
            continue
        stock = world.economy.stocks.get(offer.stock_id)
        seller = _seller_account(world, stock) if stock is not None else None
        if (stock is None or seller is None or stock.location_id != group.settlement_id
                or offer.publisher_ref != stock.owner_ref or not _can_trade(world, stock.owner_ref)):
            continue
        affordable = buyer.balance // offer.unit_price
        available = max(0, stock.goods.get("food", 0) - reserve_quantity(world, stock.id, "food"))
        maximum = min(desired - stored, offer.quantity, affordable, available, free_capacity)
        if maximum <= 0:
            continue
        quantities = tuple(dict.fromkeys((maximum, maximum // 2)))
        for quantity in quantities:
            if quantity <= 0:
                continue
            options.append(HouseholdProvisionPurchaseOption(
                id=f"household-provision:{group.id}:{offer.id}:{quantity}:{report.event_id}",
                actor_ref=actor, group_id=group.id, offer_id=offer.id, quantity=quantity,
                report_event_id=report.event_id))
    return tuple(sorted(options, key=lambda item: item.id))


def _open_purchase_decisions(world, *, ignore_response_event_id=None):
    """Current buyer intents not yet paired with a seller response/payment."""
    paid = set(world.economy.payments)
    response_ids = tuple(
        event.decision["selected_affordance_id"]
        for event in world.events
        if event.event_type == "institutional_decision_turn_decided"
        and event.id != ignore_response_event_id
        and isinstance(event.decision, dict)
        and event.decision.get("action") in {"sell_household_provisions", "decline_household_provisions"}
        and isinstance(event.decision.get("selected_affordance_id"), str)
        and event.decision["selected_affordance_id"].startswith("household-provision-sale:"))
    for event in world.events:
        decision = event.decision if event.fact_kind == FactKind.DECISION else None
        if (event.event_type != "household_provision_intent"
                or not isinstance(decision, dict) or decision.get("action") != "buy_household_provisions"
                or event.id in paid
                or any(response.startswith(f"household-provision-sale:{event.id}:") for response in response_ids)):
            continue
        try:
            buyer = EntityRef.from_dict(decision["actor_ref"])
        except (KeyError, TypeError, ValueError):
            continue
        if buyer.kind != "population_group":
            continue
        try:
            option = HouseholdProvisionPurchaseOption(
                id=decision["selected_affordance_id"], actor_ref=buyer,
                group_id=decision["group_id"], offer_id=decision["offer_id"],
                quantity=decision["quantity"], report_event_id=decision["report_event_id"])
        except (KeyError, TypeError, ValueError):
            continue
        yield event, option


def household_provision_sale_options(world, actor, *, ignore_response_event_id=None):
    """Enumerate accept/decline responses for open household purchase intents."""
    if not isinstance(actor, EntityRef):
        return ()
    options = []
    for buyer_decision, purchase in _open_purchase_decisions(
            world, ignore_response_event_id=ignore_response_event_id):
        offer = world.knowledge.reports.get(purchase.offer_id)
        stock = world.economy.stocks.get(offer.stock_id) if offer else None
        seller = _seller_account(world, stock) if stock else None
        if (offer is None or stock is None or seller is None or stock.owner_ref != actor
                or not _can_trade(world, actor)):
            continue
        base = f"household-provision-sale:{buyer_decision.id}:{offer.id}:{purchase.quantity}:{stock.last_event_ids.get('food')}"
        options.extend((HouseholdProvisionSaleOption(
            id=f"{base}:accept", actor_ref=actor, buyer_group_id=purchase.group_id,
            buyer_decision_id=buyer_decision.id, offer_id=offer.id, quantity=purchase.quantity, response="accept"),
            HouseholdProvisionSaleOption(
            id=f"{base}:decline", actor_ref=actor, buyer_group_id=purchase.group_id,
            buyer_decision_id=buyer_decision.id, offer_id=offer.id, quantity=purchase.quantity, response="decline")))
    return tuple(sorted(options, key=lambda item: item.id))


def _provision_causes(world, option):
    offer = world.knowledge.reports.get(option.offer_id)
    causes = [offer.event_id] if offer is not None else []
    if isinstance(option, HouseholdProvisionSaleOption):
        causes.append(option.buyer_decision_id)
    else:
        causes.append(option.report_event_id)
    return tuple(sorted(set(causes)))


def execute_household_provision_purchase(world, actor, option_id, decision_event_id):
    """Persist an owner receipt; no stock moves before seller consent."""
    option = next((item for item in household_provision_options(world, actor) if item.id == option_id), None)
    decision = next((item for item in world.events if item.id == decision_event_id), None)
    if (option is None or decision is None or decision.fact_kind != FactKind.DECISION
            or decision.decision != option.decision()):
        raise ValueError("household provision purchase option is stale or unknown")
    offer = world.knowledge.reports.get(option.offer_id)
    if offer is None:
        raise ValueError("household provision purchase offer is no longer known")
    terms = _terms(option.group_id, offer, option.quantity)
    terms["report_event_id"] = option.report_event_id
    return record_event(
        world, "household_provision_intent", "A coorte registrou uma intenção de reservar provisões.",
        fact_kind=FactKind.DECISION,
        decision={"action": "buy_household_provisions", "actor_ref": actor.to_dict(), **terms,
                  "selected_affordance_id": option.id},
        cause_ids=_causes(decision.id, option.report_event_id, offer.event_id))


def execute_household_provision_sale(world, actor, option_id, decision_event_id):
    """Accept or decline one buyer intent, executing material purchase only on acceptance."""
    option = next((item for item in household_provision_sale_options(
        world, actor, ignore_response_event_id=decision_event_id) if item.id == option_id), None)
    decision = next((item for item in world.events if item.id == decision_event_id), None)
    if (option is None or decision is None or decision.fact_kind != FactKind.DECISION
            or decision.decision != option.decision()):
        raise ValueError("household provision sale option is stale or unknown")
    if option.response == "decline":
        return decision
    buyer_decision = next((item for item in world.events if item.id == option.buyer_decision_id), None)
    if buyer_decision is None:
        raise ValueError("household provision buyer decision is missing")
    # Convert the transient IDs into the legacy bilateral executor's canonical
    # terms only at the owner boundary; no private terms enter the actor choice.
    payload = buyer_decision.decision
    if (payload.get("action") != "buy_household_provisions"
            or payload.get("group_id") != option.buyer_group_id):
        raise ValueError("household provision buyer option is stale")
    purchase = HouseholdProvisionPurchaseOption(
        id=payload["selected_affordance_id"], actor_ref=EntityRef.from_dict(payload["actor_ref"]),
        group_id=payload["group_id"], offer_id=payload["offer_id"], quantity=payload["quantity"],
        report_event_id=payload["report_event_id"])
    offer = world.knowledge.reports.get(purchase.offer_id)
    if offer is None or offer.id != option.offer_id:
        raise ValueError("household provision offer is no longer current")
    stock = world.economy.stocks[offer.stock_id]
    seller = _seller_account(world, stock)
    terms = _terms(purchase.group_id, offer, purchase.quantity)
    terms["seller_account_id"] = seller.id
    buyer_payload = {"action": "buy_household_provisions", "actor_ref": buyer_decision.decision["actor_ref"], **terms}
    seller_payload = {"action": "sell_household_provisions", "actor_ref": actor.to_dict(), **terms}
    from .events import record_event as _record_event
    buyer_material = _record_event(world, "household_provision_terms_authorized",
                                   "O owner recompôs os termos da intenção de provisão.",
                                   fact_kind=FactKind.DECISION, decision=buyer_payload,
                                   cause_ids=_causes(buyer_decision.id, purchase.report_event_id, offer.event_id))
    seller_material = _record_event(world, "household_provision_terms_accepted",
                                    "O fornecedor aceitou os termos atuais da provisão.",
                                    fact_kind=FactKind.DECISION, decision=seller_payload,
                                    cause_ids=_causes(decision.id, offer.event_id))
    return buy_household_provisions(world, group_id=purchase.group_id, offer_id=purchase.offer_id,
                                    quantity=purchase.quantity, buyer_decision_id=buyer_material.id,
                                    seller_decision_id=seller_material.id)


def household_provision_adapters():
    return (
        DiscretionaryAdapter(
            name="household_provision_purchase", family="household_provision",
            options_fn=household_provision_options,
            label_fn=lambda option: f"Reservar {option.quantity} rações da oferta pública conhecida.",
            causes_fn=_provision_causes, execute_fn=execute_household_provision_purchase),
        DiscretionaryAdapter(
            name="household_provision_sale", family="household_provision",
            options_fn=household_provision_sale_options,
            label_fn=lambda option: "Aceitar a venda pública de provisões." if option.response == "accept"
            else "Recusar a venda pública de provisões.",
            causes_fn=_provision_causes, execute_fn=execute_household_provision_sale),
    )


def _terms(group_id, offer, quantity):
    return {"group_id": group_id, "stock_id": offer.stock_id, "quantity": quantity,
            "unit_price": offer.unit_price, "seller_account_id": None, "offer_id": offer.id}


def _seller_account(world, stock):
    accounts = sorted((account for account in world.economy.accounts.values() if account.owner_ref == stock.owner_ref),
                      key=lambda account: account.id)
    return accounts[0] if accounts else None


def buy_household_provisions(world, *, group_id, offer_id, quantity, buyer_decision_id, seller_decision_id):
    """Execute two same-day decisions only after all public and material checks pass."""
    economy = world.economy
    group = world.society.population.get(group_id)
    buyer = economy.accounts.get(f"household:{group_id}")
    offer = world.knowledge.reports.get(offer_id)
    if (group is None or buyer is None or buyer.owner_ref != EntityRef("population_group", group_id)
            or offer is None or offer.recipient_ref != EntityRef("population_group", group_id)
            or offer.kind != "offer" or offer.resource_id != "food" or offer.channel != "market_bulletin"
            or offer.observed_day != world.clock.absolute_day or offer.quote_day != world.clock.absolute_day
            or world.society.available_count(group_id) != group.count):
        raise ValueError("household provisions require a current public local food offer")
    stock = economy.stocks.get(offer.stock_id)
    seller = _seller_account(world, stock) if stock is not None else None
    if (stock is None or seller is None or stock.location_id != group.settlement_id
            or seller.owner_ref != stock.owner_ref or offer.publisher_ref != stock.owner_ref):
        raise ValueError("household provisions require the local public seller")
    pantry_id = household_stock_id(group_id)
    pantry = economy.stocks.get(pantry_id)
    before_capacity = pantry.capacity if pantry is not None else 0
    if pantry is not None and (pantry.owner_ref != buyer.owner_ref or pantry.location_id != group.settlement_id):
        raise ValueError("household pantry is invalid")
    if type(quantity) is not int or quantity <= 0:
        raise ValueError("household provision quantity must be positive")
    market = economy.markets[group.settlement_id]
    capacity = household_food_capacity(world, group_id)
    stored = pantry.goods.get("food", 0) if pantry else 0
    effective_capacity = max(pantry.capacity, capacity) if pantry else capacity
    cost = quantity * offer.unit_price
    if (market.prices["food"] != offer.unit_price or market.updated_day != offer.quote_day
            or quantity > offer.quantity or stock.goods.get("food", 0) - reserve_quantity(world, stock.id, "food") < quantity
            or buyer.balance < cost or (stored + quantity) * economy.resources["food"].bulk > effective_capacity):
        raise ValueError("household provision price, reserve, funds or capacity changed")
    terms = _terms(group_id, offer, quantity)
    terms["seller_account_id"] = seller.id
    events = {event.id: event for event in world.events}
    for event_id, action, actor in ((buyer_decision_id, "buy_household_provisions", buyer.owner_ref),
                                    (seller_decision_id, "sell_household_provisions", seller.owner_ref)):
        event = events.get(event_id)
        if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
                or event_id in economy.payments
                or event.decision != {"action": action, "actor_ref": actor.to_dict(), **terms}):
            raise ValueError("household provisions require matching unused bilateral decisions")
    require_authority(world, seller.owner_ref, "trade")
    pantry = pantry or Stock(id=pantry_id, owner_ref=buyer.owner_ref, location_id=group.settlement_id,
                             capacity=capacity, goods={}, last_event_ids={})
    capacity_delta = (() if before_capacity == effective_capacity else
                      (_delta("stock", pantry.id, "capacity", before_capacity, effective_capacity),))
    event = record_event(world, "household_provisions_purchased",
                         f"{quantity} rações foram guardadas pela coorte para uma possível jornada.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("stock", stock.id, "food", stock.goods.get("food", 0), stock.goods.get("food", 0) - quantity),
                                 _delta("stock", pantry.id, "food", stored, stored + quantity),
                                 _delta("account", buyer.id, "balance", buyer.balance, buyer.balance - cost),
                                 _delta("account", seller.id, "balance", seller.balance, seller.balance + cost),
                                 *capacity_delta),
                         cause_ids=_causes(buyer_decision_id, seller_decision_id, offer.event_id,
                                           stock.last_event_ids.get("food"), buyer.last_event_id, seller.last_event_id))
    economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "food": stock.goods.get("food", 0) - quantity},
                                                          "last_event_ids": {**stock.last_event_ids, "food": event.id}})
    economy.stocks[pantry.id] = pantry.model_copy(update={"capacity": effective_capacity,
                                                            "goods": {**pantry.goods, "food": stored + quantity},
                                                            "last_event_ids": {**pantry.last_event_ids, "food": event.id}})
    economy.accounts[buyer.id] = buyer.model_copy(update={"balance": buyer.balance - cost, "last_event_id": event.id})
    economy.accounts[seller.id] = seller.model_copy(update={"balance": seller.balance + cost, "last_event_id": event.id})
    economy.payments[buyer_decision_id] = event.id
    economy.payments[seller_decision_id] = event.id
    return event


def review_household_provisions(world, *, excluded_actors=()):
    """Bounded preparation for actors without a completed provider turn."""
    excluded = set(excluded_actors)
    for group_id in sorted(world.society.population):
        group = world.society.population[group_id]
        actor = EntityRef("population_group", group_id)
        if actor in excluded:
            continue
        report = world.knowledge.settlement_report(actor, group.settlement_id)
        if (report is None or report.observed_day != world.clock.absolute_day or not _pressure(report)
                or world.society.available_count(group_id) != group.count
                or not _known_destination(world, actor, report)):
            continue
        pantry = world.economy.stocks.get(household_stock_id(group_id))
        stored = pantry.goods.get("food", 0) if pantry else 0
        desired = world.society.available_count(group_id)
        if stored >= desired:
            continue
        offers = sorted((offer for offer in world.knowledge.for_actor(actor)
                         if offer.kind == "offer" and offer.resource_id == "food"
                         and offer.observed_day == world.clock.absolute_day and offer.quote_day == world.clock.absolute_day),
                        key=lambda offer: (offer.unit_price, offer.stock_id, offer.id))
        buyer = world.economy.accounts.get(f"household:{group_id}")
        for offer in offers:
            stock = world.economy.stocks.get(offer.stock_id)
            seller = _seller_account(world, stock) if stock is not None else None
            if buyer is None or stock is None or seller is None or offer.publisher_ref != stock.owner_ref:
                continue
            quantity = min(desired - stored, offer.quantity, buyer.balance // (4 * offer.unit_price))
            if quantity <= 0:
                continue
            terms = _terms(group_id, offer, quantity)
            terms["seller_account_id"] = seller.id
            decision = record_event(world, "household_provisions_purchase_decided", "A coorte reserva alimento diante da pressão observada.",
                                    fact_kind=FactKind.DECISION,
                                    decision={"action": "buy_household_provisions", "actor_ref": actor.to_dict(), **terms},
                                    cause_ids=_causes(report.event_id, offer.event_id, buyer.last_event_id))
            pantry = world.economy.stocks.get(household_stock_id(group_id))
            pantry_capacity = max(pantry.capacity, household_food_capacity(world, group_id)) if pantry else household_food_capacity(world, group_id)
            pantry_food = pantry.goods.get("food", 0) if pantry else 0
            accepted = (_can_trade(world, seller.owner_ref)
                        and stock.goods.get("food", 0) - reserve_quantity(world, stock.id, "food") >= quantity
                        and buyer.balance >= quantity * offer.unit_price
                        and (pantry_food + quantity) * world.economy.resources["food"].bulk <= pantry_capacity
                        and world.economy.markets[group.settlement_id].prices["food"] == offer.unit_price
                        and world.economy.markets[group.settlement_id].updated_day == offer.quote_day)
            if not accepted:
                record_event(world, "household_provisions_sale_declined",
                             "O fornecedor recusa a venda pública nas condições atuais.",
                             fact_kind=FactKind.DECISION,
                             decision={"action": "decline_household_provisions", "actor_ref": seller.owner_ref.to_dict(), **terms},
                             cause_ids=_causes(decision.id, offer.event_id, stock.last_event_ids.get("food"),
                                               seller.last_event_id, buyer.last_event_id))
                break
            consent = record_event(world, "household_provisions_sale_decided", "O fornecedor aceita a venda pública local.",
                                   fact_kind=FactKind.DECISION,
                                   decision={"action": "sell_household_provisions", "actor_ref": seller.owner_ref.to_dict(), **terms},
                                   cause_ids=_causes(decision.id, offer.event_id, stock.last_event_ids.get("food")))
            buy_household_provisions(world, group_id=group_id, offer_id=offer.id, quantity=quantity,
                                     buyer_decision_id=decision.id, seller_decision_id=consent.id)
            break

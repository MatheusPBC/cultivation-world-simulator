"""Local, prepaid household provisions for a possible migration; never consumption."""

from src.classes.economy.models import Stock
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
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


def review_household_provisions(world):
    """Bounded preparation from dated own pressure; quiet worlds deliberately do nothing."""
    for group_id in sorted(world.society.population):
        group = world.society.population[group_id]
        actor = EntityRef("population_group", group_id)
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

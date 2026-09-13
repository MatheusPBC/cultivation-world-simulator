"""Local household purchases, separate from public relief and institutional tax."""

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from .economy import _apply_stock, _causes, _delta
from .events import record_event


def ration_shares(groups, quantity):
    """Integer proportional allocation: wealth does not change the public share."""
    total = sum(g.count for g in groups)
    if not total:
        return {}
    shares = {g.id: quantity * g.count // total for g in groups}
    remainder = quantity - sum(shares.values())
    ranked = sorted(groups, key=lambda g: (-(quantity * g.count % total), g.id))
    for group in ranked[:remainder]:
        shares[group.id] += 1
    return shares


def buy_rations(world, *, group_id, stock_id, quantity, unit_price,
                seller_account_id, buyer_decision_id, seller_decision_id):
    """Consume paid food and transfer cash together; caller owns the transaction."""
    economy = world.economy
    if type(quantity) is not int or quantity <= 0 or type(unit_price) is not int or unit_price <= 0:
        raise ValueError("rations require positive integer quantity and price")
    group = world.society.population.get(group_id)
    stock = economy.stocks.get(stock_id)
    buyer = economy.accounts.get(f"household:{group_id}")
    seller = economy.accounts.get(seller_account_id)
    if (group is None or stock is None or buyer is None or seller is None
            or group.settlement_id != stock.location_id or quantity > group.count
            or buyer.owner_ref != EntityRef("population_group", group_id)
            or seller.owner_ref != stock.owner_ref or buyer.id == seller.id):
        raise ValueError("rations require a local household and the supplier's account")
    market = economy.markets[stock.location_id]
    cost = quantity * unit_price
    if market.prices["food"] != unit_price or stock.goods.get("food", 0) < quantity or buyer.balance < cost:
        raise ValueError("ration price, stock or funds changed")
    terms = {"group_id": group_id, "stock_id": stock_id, "quantity": quantity,
             "unit_price": unit_price, "seller_account_id": seller_account_id}
    events = {e.id: e for e in world.events}
    for eid, action, actor in ((buyer_decision_id, "buy_rations", buyer.owner_ref),
                               (seller_decision_id, "sell_rations", seller.owner_ref)):
        event = events.get(eid)
        if (event is None or event.fact_kind != FactKind.DECISION
                or event.day != world.clock.absolute_day or eid in economy.payments
                or event.decision != {"action": action, "actor_ref": actor.to_dict(), **terms}):
            raise ValueError("rations require matching unused decisions from both parties")
    require_authority(world, seller.owner_ref, "trade")
    effect = _apply_stock(
        world, stock, {**stock.goods, "food": stock.goods.get("food", 0) - quantity},
        "household_purchase_completed",
        f"{world.society.settlements[group.settlement_id].name}: famílias consumiram {quantity} rações "
        f"por {cost} moedas ({unit_price} por ração).",
        extra_deltas=(_delta("account", buyer.id, "balance", buyer.balance, buyer.balance - cost),
                      _delta("account", seller.id, "balance", seller.balance, seller.balance + cost)),
        cause_ids=_causes(buyer_decision_id, seller_decision_id, market.last_event_id,
                          buyer.last_event_id, seller.last_event_id))
    economy.accounts[buyer.id] = buyer.model_copy(update={"balance": buyer.balance - cost, "last_event_id": effect.id})
    economy.accounts[seller.id] = seller.model_copy(update={"balance": seller.balance + cost, "last_event_id": effect.id})
    economy.payments[buyer_decision_id] = effect.id
    economy.payments[seller_decision_id] = effect.id
    return effect


def purchase_monthly_rations(world, need, consumed):
    """Budget routine chooses purchases; supplier accepts only its own local sale."""
    economy = world.economy
    stock = economy.stocks[need.stock_id]
    groups = [g for g in world.society.population.values() if g.settlement_id == need.id and g.count]
    shares = ration_shares(groups, consumed)
    accounts = sorted((a for a in economy.accounts.values() if a.owner_ref == stock.owner_ref), key=lambda a: a.id)
    if not accounts or not can_actor_act_for(world, stock.owner_ref, stock.owner_ref, "trade"):
        return 0, ()  # No authorized commercial supplier; existing public relief remains.
    seller_id = accounts[0].id
    market = economy.markets[need.id]
    price = market.prices["food"]
    paid, receipts = 0, []
    for group in sorted(groups, key=lambda g: g.id):
        buyer = economy.accounts.get(f"household:{group.id}")
        quantity = min(shares[group.id], buyer.balance // price) if buyer else 0
        if not quantity:
            continue
        terms = {"group_id": group.id, "stock_id": stock.id, "quantity": quantity,
                 "unit_price": price, "seller_account_id": seller_id}
        decision = record_event(world, "ration_purchase_decided", "O grupo destina parte de seu saldo à alimentação.",
                                fact_kind=FactKind.DECISION,
                                decision={"action": "buy_rations", "actor_ref": buyer.owner_ref.to_dict(), **terms},
                                cause_ids=_causes(buyer.last_event_id, market.last_event_id))
        # Supplier acts for itself, not on a household's authority. The executor
        # rechecks the stock, quote and mandate even after this routine accepts.
        consent = record_event(world, "ration_sale_decided", "O fornecedor aceita vender as rações à cotação local.",
                               fact_kind=FactKind.DECISION,
                               decision={"action": "sell_rations", "actor_ref": stock.owner_ref.to_dict(), **terms},
                               cause_ids=_causes(decision.id, market.last_event_id,
                                                 economy.stocks[stock.id].last_event_ids.get("food")))
        receipt = buy_rations(world, **terms, buyer_decision_id=decision.id, seller_decision_id=consent.id)
        paid += quantity
        receipts.append(receipt.id)
    return paid, tuple(receipts)

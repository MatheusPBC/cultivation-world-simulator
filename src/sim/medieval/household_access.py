"""Read-only projections of public food access for the omniscient observer."""

from collections import Counter

from .consumption import requirement_shares


def public_food_access_projection(world, settlement_id):
    """Estimate which public rations local households cannot afford today.

    This is an observer projection over current stock, price, available people,
    and household balances. It is not a canonical shortage, actual purchase,
    private-food reading, or actor knowledge. The returned event IDs identify
    the current inputs to the projection; they do not assert causal links.
    """
    need = world.economy.needs[settlement_id]
    stock = world.economy.stocks[need.stock_id]
    market = world.economy.markets[settlement_id]
    price = market.prices["food"]
    local_groups = [group for group in world.society.population.values()
                    if group.settlement_id == settlement_id]
    requirements = {
        group.id: available
        for group in local_groups
        if (available := world.society.available_count(group.id)) > 0
    }
    public_demand = sum(requirements.values())
    offered = min(public_demand, stock.goods.get("food", 0))
    shares = requirement_shares(requirements, offered)

    unaffordable_by_occupation = Counter()
    cash_by_occupation = Counter()
    household_cash = 0
    evidence_event_ids = {
        need.last_event_id,
        stock.last_event_ids.get("food"),
        market.last_event_id,
        *(group.last_event_id for group in local_groups),
    }
    local_group_ids = {group.id for group in local_groups}
    evidence_event_ids.update(
        journey.last_event_id for journey in world.society.migrations.values()
        if journey.source_group_id in local_group_ids
    )
    evidence_event_ids.update(
        transition.last_event_id for transition in world.society.workforce_transitions.values()
        if transition.source_group_id in local_group_ids
    )
    evidence_event_ids.update(
        detachment.last_event_id for detachment in world.society.detachments.values()
        if detachment.source_group_id in local_group_ids and detachment.stage != "disbanded"
    )
    evidence_event_ids.update(
        protest.last_event_id for protest in world.society.civic_protests.values()
        if protest.group_id in local_group_ids and protest.stage == "open"
    )
    evidence_event_ids.update(
        movement.last_event_id for movement in world.society.civic_movements.values()
        if movement.stage in {"active", "rebellion", "revolution", "negotiating"}
        and local_group_ids.intersection(movement.participants_by_group)
    )
    evidence_event_ids.update(
        strike.last_event_id for strike in world.society.civic_strikes.values()
        if strike.stage == "active" and local_group_ids.intersection(strike.participants_by_group)
    )
    for group_id, ration_share in shares.items():
        group = world.society.population[group_id]
        account = world.economy.accounts.get(f"household:{group_id}")
        balance = account.balance if account is not None else 0
        household_cash += balance
        cash_by_occupation[group.occupation] += balance
        affordable = balance // price if price else ration_share
        unaffordable_by_occupation[group.occupation] += max(0, ration_share - affordable)
        if account is not None:
            evidence_event_ids.add(account.last_event_id)

    return {
        "public_food_stock": stock.goods.get("food", 0),
        "food_price": price,
        "household_cash": household_cash,
        "household_cash_by_occupation": dict(sorted(cash_by_occupation.items())),
        "estimated_unaffordable_public_rations": sum(unaffordable_by_occupation.values()),
        "estimated_unaffordable_public_rations_by_occupation": dict(
            sorted(unaffordable_by_occupation.items())
        ),
        "food_access_evidence_event_ids": sorted(item for item in evidence_event_ids if item),
    }

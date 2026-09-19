"""Explicit, finite opening household income for an opted-in game premise."""

from src.classes.event import FactKind
from src.classes.state_delta import StateDelta
from .events import record_event


EVENT_TYPE = "initial_household_income_allocated"


def allocate_opening_household_income(world):
    """Fund one locally priced ration per household member from public treasuries.

    The caller opts into this authored world premise.  It is neither ongoing
    aid nor a substitute for payroll: every later household balance still
    comes from a material payment.  Repeating the bootstrap is a no-op only
    after the recorded premise has passed its structural validation.
    """
    existing = [event for event in world.events if event.event_type == EVENT_TYPE]
    if existing:
        if len(existing) != 1:
            raise ValueError("opening household income must have one receipt")
        _validate_receipt(world, existing[0])
        return existing[0]
    economy = world.economy
    credits, debits = _amounts(world)
    if any(economy.accounts[account_id].balance < amount for account_id, amount in debits.items()):
        raise ValueError("opening household income exceeds the administrator treasury")
    deltas = []
    for account_id, amount in sorted(debits.items()):
        account = economy.accounts[account_id]
        deltas.append(StateDelta(owner_kind="account", owner_id=account_id, aspect="balance",
                                 before=str(account.balance), after=str(account.balance - amount)))
    for account_id, amount in sorted(credits.items()):
        account = economy.accounts[account_id]
        deltas.append(StateDelta(owner_kind="account", owner_id=account_id, aspect="balance",
                                 before=str(account.balance), after=str(account.balance + amount)))
    event = record_event(world, EVENT_TYPE,
                         "A premissa inicial transferiu aos domicílios o saldo para uma ração local.",
                         fact_kind=FactKind.STATE_TRANSITION, deltas=tuple(deltas))
    for account_id, amount in debits.items():
        account = economy.accounts[account_id]
        economy.accounts[account_id] = account.model_copy(update={"balance": account.balance - amount,
                                                                    "last_event_id": event.id})
    for account_id, amount in credits.items():
        account = economy.accounts[account_id]
        economy.accounts[account_id] = account.model_copy(update={"balance": account.balance + amount,
                                                                    "last_event_id": event.id})
    return event


def _amounts(world):
    credits, debits = {}, {}
    for group in sorted(world.society.population.values(), key=lambda value: value.id):
        settlement = world.society.settlements[group.settlement_id]
        if settlement.administrator_id is None:
            raise ValueError("opening household income requires a settlement administrator")
        account_id = f"household:{group.id}"
        treasury_id = f"treasury:{settlement.administrator_id}"
        if account_id not in world.economy.accounts or treasury_id not in world.economy.accounts:
            raise ValueError("opening household income requires household and treasury accounts")
        amount = group.count * world.economy.markets[settlement.id].prices["food"]
        credits[account_id] = amount
        debits[treasury_id] = debits.get(treasury_id, 0) + amount
    return credits, debits


def _validate_receipt(world, event) -> None:
    if event.fact_kind is not FactKind.STATE_TRANSITION or event.decision is not None or event.causal_links:
        raise ValueError("opening household income receipt is invalid")
    credits, debits = _amounts(world)
    expected = {
        *( ("account", account_id, "balance", -amount) for account_id, amount in debits.items() ),
        *( ("account", account_id, "balance", amount) for account_id, amount in credits.items() ),
    }
    actual = {
        (delta.owner_kind, delta.owner_id, delta.aspect, int(delta.after) - int(delta.before))
        for delta in event.deltas
    }
    if actual != expected or len(event.deltas) != len(expected):
        raise ValueError("opening household income receipt is incomplete")

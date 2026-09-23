"""Monthly employment settlement over canonical population and money accounts."""

import hashlib

from src.classes.economy.models import MoneyAccount, Payroll
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from .events import record_event


def _income_withholding(amounts, rate_permille):
    """Allocate one aggregate income-tax rounding remainder deterministically.

    Tax is defined over the gross payroll, not independently over each cohort.
    Per-account floor division can otherwise erase a legitimate small tax
    (for example, two households earning 2 and 8 with a 10% rate).  The
    fractional remainders decide who receives the bounded final units; they do
    not change the aggregate amount or create money.
    """
    if not amounts or rate_permille <= 0:
        return {account_id: 0 for account_id in amounts}, 0
    denominator = 1000
    numerators = {account_id: amount * rate_permille for account_id, amount in amounts.items()}
    total = sum(numerators.values()) // denominator
    taxes = {account_id: numerator // denominator for account_id, numerator in numerators.items()}
    remainder = total - sum(taxes.values())
    if remainder:
        ranked = sorted(
            numerators,
            key=lambda account_id: (-(numerators[account_id] % denominator), account_id),
        )
        for account_id in ranked[:remainder]:
            taxes[account_id] += 1
    return taxes, total


def _rotated_groups(world, *, work_id, settlement_id, occupation, excluded=()):
    """Return a stable, month-rotated order for flexible labor allocation.

    Production is an Economy-owned material settlement, so it may choose a
    deterministic allocation when several equivalent cohorts can fill the
    same payroll.  Always sorting by cohort ID concentrated every wage in the
    first cohort forever; rotating the starting point by the authored month
    spreads the same real wage demand without creating labor, money, or food.
    Required specialists remain handled separately by ``settle_work``.
    """
    excluded = set(excluded)
    groups = sorted(
        (group for group in world.society.population.values()
         if group.id not in excluded
         and group.settlement_id == settlement_id
         and group.occupation == occupation),
        key=lambda group: group.id,
    )
    if len(groups) <= 1:
        return groups
    month = world.clock.absolute_day // 30
    digest = hashlib.sha256(f"{work_id}:{month}".encode("utf-8")).digest()
    offset = int.from_bytes(digest[:8], "big") % len(groups)
    return groups[offset:] + groups[:offset]


def set_income_tax(world, polity_id, income_rate, *, decision_event_id):
    """Change a policy, never transfer wealth merely because the rate changed."""
    from .economy import _causes, _delta

    world.authority.validate(world)
    if type(income_rate) is not int or not 0 <= income_rate <= 1000:
        raise ValueError("income tax must be an integer permille rate")
    policy = world.authority.tax_policies.get(polity_id)
    if policy is None:
        raise ValueError("unknown tax policy")
    actor = EntityRef("polity", polity_id)
    decision = next((e for e in world.events if e.id == decision_event_id), None)
    expected = {"action": "set_income_tax", "actor_ref": actor.to_dict(),
                "polity_id": polity_id, "income_rate": income_rate}
    if decision is None or decision.fact_kind != FactKind.DECISION or decision.decision != expected:
        raise ValueError("tax change requires a matching decision")
    if any(e.event_type == "income_tax_changed" and any(link.cause_event_id == decision_event_id
           for link in e.causal_links) for e in world.events):
        raise ValueError("tax decision already executed")
    require_authority(world, actor, "taxation")
    event = record_event(world, "income_tax_changed", f"Imposto de renda alterado para {income_rate}/1000.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("tax_policy", policy.id, "income_rate", policy.income_rate, income_rate),),
        cause_ids=_causes(decision_event_id, policy.last_event_id))
    world.authority.tax_policies[policy.id] = policy.model_copy(update={"income_rate": income_rate, "last_event_id": event.id})


def settle_labor(world, facility, batches, available, production_event_id):
    recipe = world.economy.recipes[facility.recipe_id]
    return settle_work(world, work_id=facility.id, account_id=facility.payroll_account_id,
        stock_id=facility.stock_id, occupation=recipe.occupation, worker_count=batches * recipe.workers,
        wage=facility.wage_per_worker, available=available, production_event_id=production_event_id)


def settle_work(world, *, work_id, account_id, stock_id, occupation, worker_count, wage, available, production_event_id, required_workers=None):
    from .economy import _causes, _delta

    economy = world.economy
    source = economy.accounts[account_id]
    stock = economy.stocks[stock_id]
    remaining = worker_count
    allocations = {}
    for group_id, count in (required_workers or {}).items():
        group = world.society.population.get(group_id)
        if (group is None or group.settlement_id != stock.location_id or type(count) is not int
                or count <= 0 or available.get(group_id, 0) < count or remaining < count):
            raise ValueError('required specialist is not available for payroll')
        allocations[group_id] = count
        remaining -= count
    for group in _rotated_groups(
            world, work_id=work_id, settlement_id=stock.location_id,
            occupation=occupation, excluded=allocations):
        count = min(remaining, available[group.id] - allocations.get(group.id, 0))
        if count:
            allocations[group.id] = allocations.get(group.id, 0) + count
            remaining -= count
    if remaining:
        raise ValueError("insufficient payroll workforce")
    gross = sum(allocations.values()) * wage
    if source.balance < gross:
        raise ValueError("insufficient payroll funds")
    last_event_id, tax_total = production_event_id, 0
    if gross:
        amounts = {}
        for group_id, count in allocations.items():
            account_id = f"household:{group_id}"
            # Population transfers can create a new cohort; an empty account does
            # not create wealth. Existing savings never get copied to it.
            if account_id not in economy.accounts:
                economy.accounts[account_id] = MoneyAccount(id=account_id,
                    owner_ref=EntityRef("population_group", group_id), balance=0)
            account = economy.accounts[account_id]
            if account.owner_ref != EntityRef("population_group", group_id):
                raise ValueError("payroll recipient must own its household account")
            amounts[account_id] = count * wage
        event = record_event(world, "wages_paid", f"Salários: {gross} unidades por trabalho realizado.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("account", source.id, "balance", source.balance, source.balance - gross),
                *(_delta("account", aid, "balance", economy.accounts[aid].balance,
                         economy.accounts[aid].balance + amount) for aid, amount in amounts.items())),
            cause_ids=_causes(production_event_id, source.last_event_id,
                             *(economy.accounts[aid].last_event_id for aid in amounts)))
        economy.accounts[source.id] = source.model_copy(update={"balance": source.balance - gross, "last_event_id": event.id})
        for aid, amount in amounts.items():
            account = economy.accounts[aid]
            economy.accounts[aid] = account.model_copy(update={"balance": account.balance + amount, "last_event_id": event.id})
        last_event_id = event.id
        government = world.society.settlements[stock.location_id].administrator_id
        policy = world.authority.tax_policies.get(government)
        ref = EntityRef("polity", government) if government else None
        if policy and can_actor_act_for(world, ref, ref, "taxation"):
            taxes, tax_total = _income_withholding(amounts, policy.income_rate)
            if tax_total:
                treasury = economy.accounts[policy.account_id]
                event = record_event(world, "income_tax_collected", f"Imposto sobre salários: {tax_total} unidades arrecadadas.",
                    fact_kind=FactKind.STATE_TRANSITION,
                    deltas=(_delta("account", treasury.id, "balance", treasury.balance, treasury.balance + tax_total),
                        *(_delta("account", aid, "balance", economy.accounts[aid].balance,
                                 economy.accounts[aid].balance - tax) for aid, tax in taxes.items() if tax)),
                    cause_ids=_causes(last_event_id, treasury.last_event_id, policy.last_event_id))
                economy.accounts[treasury.id] = treasury.model_copy(update={"balance": treasury.balance + tax_total, "last_event_id": event.id})
                for aid, tax in taxes.items():
                    if tax:
                        account = economy.accounts[aid]
                        economy.accounts[aid] = account.model_copy(update={"balance": account.balance - tax, "last_event_id": event.id})
                last_event_id = event.id
    for group_id, count in allocations.items():
        available[group_id] -= count
    economy.payrolls[work_id] = Payroll(id=work_id, day=world.clock.absolute_day,
        wage_per_worker=wage, workers_by_group=allocations,
        gross=gross, tax=tax_total, last_event_id=last_event_id)

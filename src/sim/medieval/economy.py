"""Material executors. Caller owns the world mutation transaction, not prose."""

from collections import defaultdict
import hashlib
import math

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.governance.authority import require_authority, can_actor_act_for
from src.classes.state_delta import StateDelta
from .events import record_event


def _delta(kind, owner_id, aspect, before, after):
    return StateDelta(owner_kind=kind, owner_id=owner_id, aspect=aspect,
                      before=str(before), after=str(after))


def _causes(*values):
    return tuple(sorted({value for value in values if value}))


def _apply_stock(world, stock, goods, event_type, content, *, extra_deltas=(), cause_ids=(),
                 causal_origin=CausalOrigin.DETERMINISTIC, causal_payload=None):
    changed = sorted(r for r in set(stock.goods) | set(goods) if stock.goods.get(r, 0) != goods.get(r, 0))
    deltas = tuple(_delta("stock", stock.id, r, stock.goods.get(r, 0), goods.get(r, 0)) for r in changed)
    causes = _causes(*cause_ids, *(stock.last_event_ids.get(r) for r in changed))
    updated = stock.model_copy(update={"goods": goods})
    # Do not append history if the candidate stock cannot be committed.
    type(stock).model_validate(updated.model_dump(mode="json"))
    if world.economy.used_capacity(updated) > updated.capacity:
        raise ValueError("storage capacity exceeded")
    event = record_event(world, event_type, content,
                         fact_kind=FactKind.STATE_TRANSITION if deltas or extra_deltas else FactKind.OCCURRENCE,
                         causal_origin=causal_origin, causal_payload=causal_payload,
                         deltas=(*deltas, *extra_deltas), cause_ids=causes)
    provenance = {**stock.last_event_ids, **{r: event.id for r in changed}}
    world.economy.stocks[stock.id] = updated.model_copy(update={"last_event_ids": provenance})
    return event


def monthly_workforce(world):
    available = {g.id: world.society.available_count(g.id) for g in world.society.population.values()}
    for payroll in world.economy.payrolls.values():
        if payroll.day == world.clock.absolute_day:
            for group_id, count in payroll.workers_by_group.items():
                available[group_id] = max(0, available[group_id] - count)
    return available


def _priority_competitors(world, facilities, priority):
    """Facilities in precisely the local workforce conflict an owner chose."""
    result = []
    for facility in facilities:
        stock = world.economy.stocks.get(facility.stock_id)
        recipe = world.economy.recipes.get(facility.recipe_id)
        if (stock is not None and recipe is not None
                and (stock.owner_ref, stock.location_id, recipe.occupation)
                == (priority.owner_ref, priority.settlement_id, priority.occupation)):
            result.append(facility)
    return result


def _rotated_facilities(world):
    """Return facilities in a stable, monthly-rotated payroll order.

    Production lines that share an employer account compete for the same
    material cash.  A permanent ID sort made the first line consume the
    treasury every month, starving later lines regardless of their local
    demand or stock.  Rotation is an engine-owned allocation rule: it creates
    no output, does not inspect private strategy, and leaves every line's own
    limits and owner revalidation unchanged.
    """
    grouped = defaultdict(list)
    for facility in world.economy.facilities.values():
        grouped[facility.payroll_account_id].append(facility)
    month = world.clock.absolute_day // 30
    ordered = []
    for account_id in sorted(grouped):
        facilities = sorted(grouped[account_id], key=lambda item: item.id)
        if len(facilities) > 1:
            digest = hashlib.sha256(f"{account_id}:{month}".encode("utf-8")).digest()
            offset = int.from_bytes(digest[:8], "big") % len(facilities)
            facilities = facilities[offset:] + facilities[:offset]
        # A chosen priority can affect only the exact local workforce conflict
        # it named, and only on the one future boundary it was selected for.
        # It is an owned instruction, not a deficit response: without a live
        # decision-backed record the monthly fair rotation above remains whole.
        active = []
        for priority in world.economy.production_priorities.values():
            if priority.payroll_account_id != account_id or priority.effective_day != world.clock.absolute_day:
                continue
            if not can_actor_act_for(world, priority.owner_ref, priority.owner_ref, "trade"):
                continue
            selected = next((item for item in facilities if item.id == priority.facility_id), None)
            if selected is None:
                continue
            stock = world.economy.stocks.get(selected.stock_id)
            recipe = world.economy.recipes.get(selected.recipe_id)
            if (stock is None or recipe is None
                    or (stock.owner_ref, stock.location_id, recipe.occupation)
                    != (priority.owner_ref, priority.settlement_id, priority.occupation)):
                continue
            competitors = _priority_competitors(world, facilities, priority)
            if len(competitors) > 1:
                active.append((priority, selected, competitors))
        # Registry identity is one conflict key, so ties cannot exist in
        # valid state.  Still keep a deterministic order for malformed direct
        # callers before validation rejects them.
        for _priority, selected, competitors in sorted(active, key=lambda item: item[0].id):
            facilities.remove(selected)
            first_competitor = min(facilities.index(item) for item in competitors if item in facilities)
            facilities.insert(first_competitor, selected)
        ordered.extend(facilities)
    return tuple(ordered)


def produce_monthly(world, available=None) -> None:
    from .labor import settle_labor
    economy = world.economy
    economy.validate(world)
    workers = defaultdict(int)
    if available is None:
        available = monthly_workforce(world)
    for group in world.society.population.values():
        workers[group.settlement_id, group.occupation] += available[group.id]
    active_priorities = {
        priority.facility_id: priority
        for priority in economy.production_priorities.values()
        if priority.effective_day == world.clock.absolute_day
        and can_actor_act_for(world, priority.owner_ref, priority.owner_ref, "trade")
    }
    for facility in _rotated_facilities(world):
        payroll = economy.payrolls.get(facility.id)
        if payroll is not None and payroll.day == world.clock.absolute_day:
            continue
        site = world.map.infrastructure_sites[facility.site_id]
        recipe = economy.recipes[facility.recipe_id]
        stock = economy.stocks[facility.stock_id]
        knowledge = next((item for item in world.knowledge.technologies.values()
                          if item.owner_ref == stock.owner_ref
                          and item.technology_id == recipe.required_technology_id), None)
        workforce = (stock.location_id, recipe.occupation)
        limits = {"capacity": facility.max_batches,
                  "site_integrity": math.floor(facility.max_batches * site.integrity),
                  "labor": workers[workforce] // recipe.workers,
                  "payroll_funds": economy.accounts[facility.payroll_account_id].balance // (recipe.workers * facility.wage_per_worker)}
        if not can_actor_act_for(world, stock.owner_ref, stock.owner_ref, "trade"):
            limits["employer_authority"] = 0
        if not site.enabled:
            limits["site_disabled"] = 0
        if recipe.required_technology_id and knowledge is None:
            limits['knowledge'] = 0
        for rid, amount in recipe.inputs.items():
            limits[f"input:{rid}"] = stock.goods.get(rid, 0) // amount
        net_bulk = (sum(economy.resources[r].bulk * q for r, q in recipe.outputs.items())
                    - sum(economy.resources[r].bulk * q for r, q in recipe.inputs.items()))
        if net_bulk > 0:
            limits["storage"] = (stock.capacity - economy.used_capacity(stock)) // net_bulk
        batches = min(limits.values())
        limitations = tuple(sorted(k for k, limit in limits.items() if limit == batches and limit < facility.max_batches))
        goods = dict(stock.goods)
        if batches:
            for rid, amount in recipe.inputs.items():
                goods[rid] -= amount * batches
            for rid, amount in recipe.outputs.items():
                goods[rid] = goods.get(rid, 0) + amount * batches
        updated = facility.model_copy(update={"last_batches": batches, "last_limitations": limitations})
        changes = tuple(_delta("production", facility.id, name, getattr(facility, name), getattr(updated, name))
                        for name in ("last_batches", "last_limitations") if getattr(facility, name) != getattr(updated, name))
        if "labor" in limitations:
            # Typed, repeatable signal of a material labour shortage: how many
            # workers this line still lacks to raise its output by one batch.
            changes += (_delta("production", facility.id, "labor_shortfall", 0,
                               recipe.workers * (batches + 1) - workers[workforce]),)
        labor_shortfall_value = (
            recipe.workers * (batches + 1) - workers[workforce]
            if "labor" in limitations else 0
        )
        priority = active_priorities.get(facility.id)
        event = _apply_stock(world, stock, goods, "production_completed" if batches else "production_limited",
                             f"{site.name}: {batches} lotes de produção concluídos.",
                             cause_ids=_causes(site.last_event_id, facility.last_event_id,
                                               knowledge.event_id if knowledge is not None else None,
                                               economy.accounts[facility.payroll_account_id].last_event_id,
                                               *(group.last_event_id for group in world.society.population.values()
                                                 if group.settlement_id == stock.location_id and group.occupation == recipe.occupation),
                                               *(stock.last_event_ids.get(r) for r in recipe.inputs),
                                               priority.last_event_id if priority is not None else None),
                             extra_deltas=changes)
        # Keep the engine's calculation alongside the scalar deltas.  Why views
        # and diagnostics can now explain the binding limit without reparsing
        # prose or guessing from a later state snapshot; the payload is not an
        # instruction and never changes the owner-side execution.
        event = event.model_copy(update={"causal_payload": {
            "production": {
                "facility_id": facility.id,
                "site_id": facility.site_id,
                "stock_id": facility.stock_id,
                "settlement_id": stock.location_id,
                "recipe_id": facility.recipe_id,
                "occupation": recipe.occupation,
                "batches": batches,
                "capacity": facility.max_batches,
                "limits": dict(sorted(limits.items())),
                "limitations": list(limitations),
                "labor_shortfall": max(0, labor_shortfall_value),
                "production_priority_event_id": priority.last_event_id if priority is not None else None,
                "observed_day": world.clock.absolute_day,
            }
        }})
        world.events[-1] = event
        economy.facilities[facility.id] = updated.model_copy(update={"last_event_id": event.id})
        settle_labor(world, facility, batches, available, event.id)
        workers[workforce] -= batches * recipe.workers


def consume_monthly(world) -> None:
    from .consumption import purchase_monthly_rations
    from .logistics import _route_causes
    from .migration import consume_travel_provisions
    economy = world.economy
    economy.validate(world)
    consume_travel_provisions(world)
    events = world.event_index()
    for need in sorted(economy.needs.values(), key=lambda item: item.id):
        previous = events.get(need.last_event_id)
        if previous is not None and previous.day == world.clock.absolute_day and previous.event_type == "subsistence_resolved":
            continue
        stock = economy.stocks[need.stock_id]
        groups = [group for group in world.society.population.values()
                  if group.settlement_id == need.id and world.society.available_count(group.id)]
        required_by_group = {group.id: world.society.available_count(group.id) for group in groups}
        domestic, domestic_receipts = _consume_household_food(world, need.id, required_by_group)
        required = sum(required_by_group.values()) + domestic
        public_required = sum(required_by_group.values())
        pool = min(public_required, stock.goods.get("food", 0))
        # Keep the affordability bottleneck explicit in the canonical reading.
        # Public stock can be abundant while a household cannot buy its share;
        # that is a real economic cause for missing food, not a reason to
        # manufacture a subsidy or to infer one from prose.
        from src.sim.medieval.consumption import requirement_shares
        public_shares = requirement_shares(required_by_group, pool)
        price = economy.markets[need.id].prices["food"]
        unaffordable = {
            group_id: max(0, quantity - min(quantity,
                                             (economy.accounts.get(f"household:{group_id}").balance // price
                                              if economy.accounts.get(f"household:{group_id}") is not None else 0)))
            for group_id, quantity in public_shares.items()
            if quantity > 0
        }
        paid, receipts, paid_by_group = purchase_monthly_rations(world, need, pool, required_by_group)
        unmet_by_group = {group_id: required - paid_by_group.get(group_id, 0)
                          for group_id, required in required_by_group.items()
                          if required > paid_by_group.get(group_id, 0)}
        stock = economy.stocks[need.stock_id]
        # Whatever public demand went unpaid is a real shortfall, not a
        # standing subsidy: only a later, explicit relief act can cover it.
        missing = public_required - paid
        pressure = math.ceil(100 * missing / required) if required else 0
        health = max(0, need.health - pressure) if missing else min(1000, need.health + 20)
        unrest = min(1000, need.unrest + pressure) if missing else max(0, need.unrest - 20)
        updated = need.model_copy(update={"health": health, "unrest": unrest, "missing_food": missing})
        deltas = tuple(_delta("subsistence", need.id, field, getattr(need, field), getattr(updated, field))
                       for field in ("health", "unrest", "missing_food") if getattr(need, field) != getattr(updated, field))
        settlement = world.society.settlements[need.id]
        # A blocked food order already carries the cargo-delay receipt, but the
        # settlement's dated scarcity fact should also name the current Map
        # interruption directly.  This keeps the causal chain navigable from
        # route -> missing food/health/unrest -> dated institutional reading
        # without making the route owner mutate Economy or creating aid.
        interrupted_route_causes = tuple(
            cause
            for order in economy.freight_orders.values()
            if (order.destination_id == stock.id and order.resource_id == "food"
                and order.delivered_quantity < order.quantity)
            for route_id in order.route_ids
            if world.map.get_route_operational_capacity(route_id) <= 0
            for cause in _route_causes(world, (route_id,)).get(route_id, ())
        )
        event = _apply_stock(world, stock, stock.goods, "subsistence_resolved",
                             f"{settlement.name}: {domestic + paid}/{required} rações atendidas; {domestic} domésticas, {paid} compradas; "
                             f"déficit de {missing}.",
                             extra_deltas=deltas, cause_ids=_causes(need.last_event_id, stock.last_event_ids.get("food"),
                                  *domestic_receipts, *receipts,
                                  *interrupted_route_causes,
                                  *(group.last_event_id for group in groups),
                                 *(f.last_event_id for f in economy.facilities.values() if f.stock_id == stock.id
                                   and "food" in economy.recipes[f.recipe_id].outputs),
                                 *(o.last_event_id for o in economy.freight_orders.values() if o.destination_id == stock.id
                                   and o.resource_id == "food" and o.delivered_quantity < o.quantity)))
        # The scalar deltas preserve the canonical state transition.  This
        # structured reading makes the affordability bottleneck explainable
        # without parsing prose or exposing household balances to decision
        # contexts that do not already know them.
        event = event.model_copy(update={"causal_payload": {
            "subsistence": {
                "settlement_id": need.id,
                "required": required,
                "public_required": public_required,
                "domestic_quantity": domestic,
                "purchased_quantity": paid,
                "missing_food": missing,
                "household_group_ids": sorted(required_by_group),
                "unaffordable_by_group": {group_id: amount for group_id, amount in sorted(unaffordable.items())
                                          if amount > 0},
                "unmet_by_group": dict(sorted(unmet_by_group.items())),
            }
        }})
        world.events[-1] = event
        economy.needs[need.id] = updated.model_copy(update={"last_event_id": event.id})


def apply_civic_refusal_pressure(world, settlement_id, *, refusal_event_id, pressure=50):
    """Apply a bounded unrest consequence to a materially refused demand.

    Economy remains the owner of subsistence condition.  A civic executor may
    name the refusal as a cause, but it cannot mutate ``SettlementNeeds``
    directly or manufacture a later protest/rebellion.
    """
    need = world.economy.needs.get(settlement_id)
    if need is None or type(pressure) is not int or pressure <= 0:
        raise ValueError("civic refusal pressure requires a settlement and positive pressure")
    updated = need.model_copy(update={"unrest": min(1000, need.unrest + pressure)})
    if updated.unrest == need.unrest:
        return None
    event = record_event(
        world, "civic_refusal_pressure",
        "A recusa administrativa agravou a tensão material registrada no assentamento.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("subsistence", settlement_id, "unrest", need.unrest, updated.unrest),),
        cause_ids=_causes(refusal_event_id, need.last_event_id))
    world.economy.needs[settlement_id] = updated.model_copy(update={"last_event_id": event.id})
    return event


def apply_civic_resolution_relief(world, settlement_id, *, resolution_event_id, relief=40):
    """Apply bounded unrest relief only after a material civic response.

    The protest owner supplies the factual closure and the material receipt;
    Economy owns the subsistence condition and records the derived transition.
    This never creates food or repairs and cannot erase more unrest than exists.
    """
    need = world.economy.needs.get(settlement_id)
    if need is None or type(relief) is not int or relief <= 0:
        raise ValueError("civic resolution relief requires a settlement and positive relief")
    updated = need.model_copy(update={"unrest": max(0, need.unrest - relief)})
    if updated.unrest == need.unrest:
        return None
    event = record_event(
        world, "civic_resolution_relief",
        "Uma resposta material reduziu a tensão registrada no assentamento.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("subsistence", settlement_id, "unrest", need.unrest, updated.unrest),),
        cause_ids=_causes(resolution_event_id, need.last_event_id))
    world.economy.needs[settlement_id] = updated.model_copy(update={"last_event_id": event.id})
    return event


def apply_rite_persecution_pressure(world, settlement_id, *, interruption_event_id, pressure=60):
    """Record bounded social pressure caused by a material rite interruption.

    Society owns the denial and Research owns the interrupted rite.  Economy
    remains the only owner allowed to change the settlement's subsistence
    condition.  This is deliberately pressure, not an automatic protest or
    persecution campaign: later civic affordances must still be recomposed
    from the resulting report and selected by an actor.
    """
    need = world.economy.needs.get(settlement_id)
    if need is None or type(pressure) is not int or pressure <= 0:
        raise ValueError("rite interruption pressure requires a settlement and positive pressure")
    updated = need.model_copy(update={"unrest": min(1000, need.unrest + pressure)})
    if updated.unrest == need.unrest:
        return None
    event = record_event(
        world, "rite_interruption_pressure",
        "A interrupção material de um rito agravou a tensão registrada no assentamento.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("subsistence", settlement_id, "unrest", need.unrest, updated.unrest),),
        cause_ids=_causes(interruption_event_id, need.last_event_id))
    world.economy.needs[need.id] = updated.model_copy(update={"last_event_id": event.id})
    return event


def apply_civic_rebellion_pressure(world, settlement_id, *, rebellion_event_id, pressure=100):
    """Record bounded subsistence pressure from an explicitly declared uprising.

    Society owns the declaration and its participants; Economy owns the
    settlement condition.  This does not transfer administration or create a
    military outcome.
    """
    need = world.economy.needs.get(settlement_id)
    if need is None or type(pressure) is not int or pressure <= 0:
        raise ValueError("civic rebellion pressure requires a settlement and positive pressure")
    updated = need.model_copy(update={"unrest": min(1000, need.unrest + pressure)})
    if updated.unrest == need.unrest:
        return None
    event = record_event(
        world, "civic_rebellion_pressure",
        "A declaração de rebelião agravou a pressão social registrada no assentamento.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("subsistence", settlement_id, "unrest", need.unrest, updated.unrest),),
        cause_ids=_causes(rebellion_event_id, need.last_event_id))
    world.economy.needs[settlement_id] = updated.model_copy(update={"last_event_id": event.id})
    return event


def apply_civic_suppression_pressure(world, settlement_id, *, suppression_event_id, pressure=120):
    """Record bounded social pressure caused by material repression.

    Society owns the suppression and participant release; Economy owns the
    settlement condition.  This never creates a successor movement or changes
    administration, so future civic action still requires a fresh decision.
    """
    need = world.economy.needs.get(settlement_id)
    if need is None or type(pressure) is not int or pressure <= 0:
        raise ValueError("civic suppression pressure requires a settlement and positive pressure")
    updated = need.model_copy(update={"unrest": min(1000, need.unrest + pressure)})
    if updated.unrest == need.unrest:
        return None
    event = record_event(
        world, "civic_suppression_pressure",
        "A repressão material agravou a pressão social registrada no assentamento.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("subsistence", settlement_id, "unrest", need.unrest, updated.unrest),),
        cause_ids=_causes(suppression_event_id, need.last_event_id))
    world.economy.needs[settlement_id] = updated.model_copy(update={"last_event_id": event.id})
    return event


def apply_civic_revolution_pressure(world, settlement_id, *, revolution_event_id, pressure=150):
    """Record the bounded additional pressure of an explicitly chosen revolution."""
    need = world.economy.needs.get(settlement_id)
    if need is None or type(pressure) is not int or pressure <= 0:
        raise ValueError("civic revolution pressure requires a settlement and positive pressure")
    updated = need.model_copy(update={"unrest": min(1000, need.unrest + pressure)})
    if updated.unrest == need.unrest:
        return None
    event = record_event(
        world, "civic_revolution_pressure",
        "A revolução declarada agravou a pressão social registrada no assentamento.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("subsistence", settlement_id, "unrest", need.unrest, updated.unrest),),
        cause_ids=_causes(revolution_event_id, need.last_event_id))
    world.economy.needs[settlement_id] = updated.model_copy(update={"last_event_id": event.id})
    return event


def _consume_household_food(world, settlement_id, requirements):
    """Private carried food is consumed once before any public allocation."""
    economy = world.economy
    total, receipts = 0, []
    for group_id in sorted(requirements):
        stock = economy.stocks.get(f"household-stock:{group_id}")
        if stock is None:
            continue
        if stock.owner_ref.kind != "population_group" or stock.owner_ref.id != group_id or stock.location_id != settlement_id:
            raise ValueError("invalid household food stock")
        eaten = min(requirements[group_id], stock.goods.get("food", 0))
        if not eaten:
            continue
        event = _apply_stock(world, stock, {**stock.goods, "food": stock.goods.get("food", 0) - eaten},
                             "household_rations_consumed", f"A família consumiu {eaten} rações próprias.",
                             cause_ids=_causes(stock.last_event_ids.get("food")))
        requirements[group_id] -= eaten
        total += eaten
        receipts.append(event.id)
    return total, tuple(receipts)


def transfer_money(world, source_id: str, target_id: str, amount: int, *, decision_event_id: str,
                   decision_intent=None) -> None:
    """Execute the account owner's payment once, with a current trading mandate."""
    economy = world.economy
    economy.validate(world)
    if type(amount) is not int or amount <= 0 or source_id == target_id:
        raise ValueError("payment requires distinct accounts and a positive integer")
    if source_id not in economy.accounts or target_id not in economy.accounts:
        raise ValueError("unknown payment account")
    source, target = economy.accounts[source_id], economy.accounts[target_id]
    if source.balance < amount:
        raise ValueError("insufficient money")
    event = next((e for e in world.events if e.id == decision_event_id), None)
    intent = event.decision if event is not None else None
    expected = decision_intent or {"action": "pay", "source_id": source_id,
                                   "target_id": target_id, "amount": amount,
                                   "actor_ref": source.owner_ref.to_dict()}
    if (event is None or event.fact_kind != FactKind.DECISION or intent is None
            or intent != expected
            or decision_event_id in economy.payments):
        raise ValueError("payment needs a matching unexecuted decision")
    if event.day != world.clock.absolute_day:
        raise ValueError("payment decision is stale; consent must be given today")
    require_authority(world, source.owner_ref, "trade")
    effect = record_event(world, "payment_completed", f"Pagamento de {amount} unidades monetárias concluído.",
                          fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(_delta("account", source.id, "balance", source.balance, source.balance - amount),
                                  _delta("account", target.id, "balance", target.balance, target.balance + amount)),
                          cause_ids=_causes(decision_event_id, source.last_event_id, target.last_event_id))
    economy.accounts[source.id] = source.model_copy(update={"balance": source.balance - amount, "last_event_id": effect.id})
    economy.accounts[target.id] = target.model_copy(update={"balance": target.balance + amount, "last_event_id": effect.id})
    economy.payments[decision_event_id] = effect.id

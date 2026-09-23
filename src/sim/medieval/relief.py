"""Public food relief is an act the stock owner chooses, never a standing rate.

A polity that owns a settlement's public granary may give some of it away for
free, but only by an explicit, dated decision: how much to move is bounded by
what that same polity's own current report says the settlement still lacks,
and by what physically sits in the granary today. Nothing here creates food,
and nothing here repeats itself: a stale, invented or already-executed option
never moves anything.
"""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import math

from src.classes.economy.models import Stock
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Count, Identity, SocietyValue
from .economy import _apply_stock, _causes, _delta
from .events import record_event
from .intelligence import reserve_quantity
from .logistics import open_order
from .routing import fiscal_route_options


def _household_stock_id(group_id):
    return f"household-stock:{group_id}"

# Fractions of the observed shortfall the owner may choose to cover. The
# actor picks *how much*, not only whether to act at all.
COVERAGE_FRACTIONS = (1, 2)


def _unmet_household_rations(world, settlement_id):
    """Latest unpaid rations minus relief allocated since that closing."""
    subsistence = next((event for event in reversed(world.events)
                        if event.event_type == "subsistence_resolved"
                        and event.causal_payload.get("subsistence", {}).get("settlement_id") == settlement_id), None)
    if subsistence is None:
        # A world premise may begin with a canonical shortage before its first
        # monthly closing. There are no earlier household purchases to skew.
        from .consumption import requirement_shares
        need = world.economy.needs[settlement_id]
        groups = {group.id: group.count for group in world.society.population.values()
                  if group.settlement_id == settlement_id and group.count}
        return {group_id: amount for group_id, amount in requirement_shares(
            groups, min(need.missing_food, sum(groups.values()))).items() if amount > 0}
    unpaid = subsistence.causal_payload["subsistence"].get("unmet_by_group")
    if not isinstance(unpaid, dict):
        return {}
    remaining = {group.id: unpaid.get(group.id, 0)
                 for group in world.society.population.values()
                 if group.settlement_id == settlement_id and group.count and unpaid.get(group.id, 0) > 0}
    for prior in reversed(world.events):
        if prior.id == subsistence.id:
            break
        if prior.event_type != "relief_distributed":
            continue
        reading = prior.causal_payload.get("relief_distribution", {})
        if reading.get("settlement_id") == settlement_id:
            for group_id, amount in reading.get("household_allocations", {}).items():
                if group_id in remaining:
                    remaining[group_id] = max(0, remaining[group_id] - amount)
    return {group_id: amount for group_id, amount in remaining.items() if amount > 0}


@dataclass(frozen=True)
class ReliefTransferOption:
    """A bounded internal freight from an owner's surplus granary."""
    id: Identity
    actor_ref: EntityRef
    source_stock_id: Identity
    destination_stock_id: Identity
    destination_settlement_id: Identity
    quantity: Count
    route_ids: tuple[Identity, ...]
    route_option_id: Identity
    source_inventory_event_id: Identity
    destination_report_id: Identity

    def decision(self):
        return {"action": "transfer_relief", "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


class ReliefDistributionOption(SocietyValue):
    """A current affordance to give away some of the granary's own owner's food.

    The actor is the stock's owner, never the settlement's administrator: it
    is whoever holds the food that gives up the revenue it could have sold
    it for. The quantity is bounded by that owner's own dated reading of the
    settlement and by what the granary physically holds right now.
    """

    id: Identity
    polity_id: Identity
    settlement_id: Identity
    stock_id: Identity
    quantity: Count
    report_id: Identity

    def decision(self):
        return {"action": "distribute_relief", "actor_ref": EntityRef("polity", self.polity_id).to_dict(),
                "selected_affordance_id": self.id}


def relief_settlement_options(world, polity_id, *, settlement_id=None):
    """Legal relief affordances backed by the owner's own current settlement report."""
    actor = EntityRef("polity", polity_id)
    if not can_actor_act_for(world, actor, actor, "supply"):
        return ()
    day = world.clock.absolute_day
    options = []
    for need_id in sorted(world.economy.needs):
        if settlement_id is not None and need_id != settlement_id:
            continue
        need = world.economy.needs[need_id]
        stock = world.economy.stocks[need.stock_id]
        if stock.owner_ref != actor:
            continue
        report = world.knowledge.settlement_report(actor, need_id)
        if (report is None or report.publisher_ref != actor or report.observed_day != day
                or report.missing_food <= 0):
            continue
        available = min(stock.goods.get("food", 0), sum(_unmet_household_rations(world, need_id).values()))
        if available <= 0:
            continue
        basis = f"{report.event_id}:{stock.last_event_ids.get('food')}"
        quantities = sorted({q for q in (min(report.missing_food // fraction, available)
                                         for fraction in COVERAGE_FRACTIONS) if q > 0}, reverse=True)
        for quantity in quantities:
            option_id = f"relief-distribute:{polity_id}:{need_id}:{quantity}:{basis}"
            options.append(ReliefDistributionOption(id=option_id, polity_id=polity_id, settlement_id=need_id,
                                                     stock_id=stock.id, quantity=quantity, report_id=report.id))
    return tuple(options)


def distribute_relief(world, option_id, *, decision_event_id):
    """Move real food out of the granary once, on an exact, current decision."""
    decision = next((event for event in world.events if event.id == decision_event_id), None)
    payload = decision.decision if decision is not None else None
    try:
        actor = EntityRef.from_dict(payload.get("actor_ref")) if isinstance(payload, dict) else None
    except (KeyError, TypeError, ValueError):
        actor = None
    polity_id = actor.id if actor is not None and actor.kind == "polity" else None
    option = next((item for item in relief_settlement_options(world, polity_id) if item.id == option_id), None)
    if (decision is None or decision.day != world.clock.absolute_day or decision.fact_kind != FactKind.DECISION
            or option is None or decision.decision != option.decision()):
        raise ValueError("relief distribution option is stale")
    if any(event.event_type == "relief_distributed" and any(link.cause_event_id == decision.id
           for link in event.causal_links) for event in world.events):
        raise ValueError("relief distribution decision already executed")
    actor = EntityRef("polity", option.polity_id)
    require_authority(world, actor, "supply")
    stock = world.economy.stocks[option.stock_id]
    need = world.economy.needs[option.settlement_id]
    report = world.knowledge.settlement_reports.get(option.report_id)
    if report is None:
        raise ValueError("relief material reading changed")
    quantity = option.quantity
    if quantity <= 0 or quantity > stock.goods.get("food", 0):
        raise ValueError("relief distribution exceeds the granary's real stock")
    # The public act must have a material destination.  Move the selected
    # rations into the existing household pantries (or create their canonical
    # stocks) in the same owner event; merely lowering ``missing_food`` would
    # make the relief disappear and cause the next monthly closure to charge
    # the same people again.
    from .consumption import requirement_shares
    groups = sorted((group for group in world.society.population.values()
                     if group.settlement_id == option.settlement_id and group.count), key=lambda item: item.id)
    if not groups:
        raise ValueError("relief distribution requires a living destination population")
    remaining = _unmet_household_rations(world, option.settlement_id)
    if sum(remaining.values()) < quantity:
        raise ValueError("relief distribution exceeds evidenced unmet household rations")
    allocations = requirement_shares(remaining, quantity)
    if sum(allocations.values()) != quantity:
        raise ValueError("relief distribution could not allocate the selected quantity")
    food_resource = world.economy.resources["food"]
    pantry_updates = []
    for group in groups:
        pantry = world.economy.stocks.get(_household_stock_id(group.id))
        default_capacity = 2 * group.count * food_resource.bulk
        capacity = max(default_capacity, pantry.capacity if pantry is not None else 0)
        before = pantry.goods.get("food", 0) if pantry is not None else 0
        after = before + allocations.get(group.id, 0)
        if after * food_resource.bulk > capacity:
            raise ValueError("relief distribution exceeds household pantry capacity")
        pantry_updates.append((group, pantry, capacity, before, after))
    missing_before = need.missing_food
    covered = min(quantity, missing_before)
    updated_missing = max(0, missing_before - quantity)
    # Relief is a material intervention after the dated subsistence reading,
    # not a free reset of social conditions.  Its immediate recovery is capped
    # at the same bounded amount as one fully fed cycle and scales only with
    # the fraction of the observed shortfall that the owner actually covers.
    recovery = (math.ceil(20 * covered / missing_before)
                if missing_before > 0 and covered > 0 else 0)
    updated_health = min(1000, need.health + recovery)
    updated_unrest = max(0, need.unrest - recovery)
    condition_deltas = tuple(
        _delta("subsistence", need.id, field, getattr(need, field), value)
        for field, value in (("missing_food", updated_missing),
                             ("health", updated_health),
                             ("unrest", updated_unrest))
        if getattr(need, field) != value
    )
    pantry_deltas = tuple(
        _delta("stock", _household_stock_id(group.id), "food", before, after)
        for group, _pantry, _capacity, before, after in pantry_updates
        if after != before
    )
    settlement = world.society.settlements[option.settlement_id]
    event = _apply_stock(
        world, stock, {**stock.goods, "food": stock.goods.get("food", 0) - quantity},
        "relief_distributed",
        f"{settlement.name}: {quantity} rações de ajuda distribuídas pela administração; déficit restante de {updated_missing}.",
        extra_deltas=(*condition_deltas, *pantry_deltas),
        cause_ids=_causes(decision.id, report.event_id, need.last_event_id),
    )
    event = event.model_copy(update={"causal_payload": {
        "relief_distribution": {
            "settlement_id": option.settlement_id,
            "quantity": quantity,
            "household_allocations": {group.id: allocations.get(group.id, 0) for group, *_ in pantry_updates
                                       if allocations.get(group.id, 0)},
        }
    }})
    world.events[-1] = event
    for group, pantry, capacity, _before, after in pantry_updates:
        if not allocations.get(group.id, 0):
            continue
        pantry = pantry or Stock(id=_household_stock_id(group.id),
                                 owner_ref=EntityRef("population_group", group.id),
                                 location_id=group.settlement_id, capacity=capacity)
        world.economy.stocks[pantry.id] = pantry.model_copy(
            update={"capacity": capacity, "goods": {**pantry.goods, "food": after},
                    "last_event_ids": {**pantry.last_event_ids, "food": event.id}})
    world.economy.needs[need.id] = need.model_copy(update={
        "missing_food": updated_missing, "health": updated_health,
        "unrest": updated_unrest, "last_event_id": event.id,
    })
    # The owner has changed a condition after the monthly observation was
    # published.  Existing local observers can see this public distribution,
    # so replace only their own local reading before another policy considers
    # a same-day request.  This deliberately does not publish a new bulletin
    # or grant a remote institution knowledge it did not already possess.
    from .settlement_intelligence import refresh_existing_local_settlement_reports
    refresh_existing_local_settlement_reports(world, option.settlement_id)
    return event


def relief_transfer_options(world, actor):
    """Enumerate current, routed transfers between the actor's own settlements."""
    if (not isinstance(actor, EntityRef) or actor.kind != "polity"
            or not can_actor_act_for(world, actor, actor, "supply")):
        return ()
    destinations = [report for report in world.knowledge.settlements_for_actor(actor)
                    if report.publisher_ref == actor and report.observed_day == world.clock.absolute_day
                    and report.missing_food > 0]
    inventory = [report for report in world.knowledge.for_actor(actor)
                 if report.kind == "inventory" and report.resource_id == "food"
                 and report.observed_day == world.clock.absolute_day]
    options = []
    for report in sorted(destinations, key=lambda item: item.id):
        destination = world.economy.needs.get(report.settlement_id)
        if destination is None:
            continue
        destination_stock = world.economy.stocks.get(destination.stock_id)
        # This vertical is an internal transfer between settlements of the
        # same institution. Knowing another polity's pressure can inform a
        # later aid request, but it must not create a freight affordance whose
        # destination owner would reject it during execution.
        if destination_stock is None or destination_stock.owner_ref != actor:
            continue
        for source_report in sorted(inventory, key=lambda item: item.id):
            source = world.economy.stocks.get(source_report.stock_id)
            if source is None or source.owner_ref != actor or source.id == destination.stock_id:
                continue
            source_need = world.economy.needs.get(source.location_id)
            local_shortfall = source_need.missing_food if source_need is not None else 0
            available = max(
                0,
                source.goods.get("food", 0)
                - reserve_quantity(world, source.id, "food")
                - local_shortfall,
            )
            if available <= 0:
                continue
            quantities = sorted({q for q in (min(available, report.missing_food // fraction)
                                             for fraction in COVERAGE_FRACTIONS) if q > 0}, reverse=True)
            for quantity in quantities:
                for route in fiscal_route_options(world, actor, source.id, destination.stock_id, "food", quantity):
                    opaque_terms = ":".join((actor.id, source.id, destination.stock_id, str(quantity), route.id,
                                              ":".join(route.route_ids), str(world.clock.absolute_day)))
                    opaque_id = sha256(opaque_terms.encode()).hexdigest()[:20]
                    options.append(ReliefTransferOption(
                        # The decision exposes only an opaque affordance handle;
                        # stock/account identifiers remain owner-private and are
                        # recomposed from the current option at execution time.
                        id=f"relief-transfer:{actor.id}:{opaque_id}",
                        actor_ref=actor, source_stock_id=source.id, destination_stock_id=destination.stock_id,
                        destination_settlement_id=report.settlement_id, quantity=quantity,
                        route_ids=route.route_ids, route_option_id=route.id,
                        source_inventory_event_id=source_report.event_id, destination_report_id=report.id))
    # Stable fallback order prefers the largest currently enumerated coverage;
    # actors with a provider still receive the complete menu and may choose
    # either coverage.  The opaque ID remains only a handle, never a source
    # of quantity or route terms.
    return tuple(sorted(options, key=lambda item: (-item.quantity, item.destination_settlement_id, item.id)))


def execute_relief_transfer(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in relief_transfer_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("relief transfer option is stale or unknown")
    decision = next((event for event in candidate.events if event.id == decision_event_id), None)
    if (decision is None or decision.fact_kind != FactKind.DECISION or decision.day != candidate.clock.absolute_day
            or decision.decision != option.decision()):
        raise ValueError("relief transfer requires the selected current decision")
    require_authority(candidate, actor, "supply")
    source_report = next((item for item in candidate.knowledge.for_actor(actor)
                          if item.kind == "inventory" and item.event_id == option.source_inventory_event_id), None)
    destination_report = candidate.knowledge.settlement_reports.get(option.destination_report_id)
    route = next((item for item in fiscal_route_options(candidate, actor, option.source_stock_id,
                                                        option.destination_stock_id, "food", option.quantity)
                   if item.id == option.route_option_id), None)
    source = candidate.economy.stocks.get(option.source_stock_id)
    destination = candidate.economy.stocks.get(option.destination_stock_id)
    if (source_report is None or destination_report is None or route is None or source is None or destination is None
            or source.owner_ref != actor or destination.owner_ref != actor):
        raise ValueError("relief transfer evidence is stale")
    order = open_order(candidate, source.id, destination.id, "food", option.quantity, route.route_ids,
                       decision_ids=(decision_event_id,),
                       cause_ids=_causes(source_report.event_id, destination_report.event_id,
                                         *route.route_report_ids, *route.fiscal_route_report_ids))
    world.__dict__.update(candidate.__dict__)
    return order

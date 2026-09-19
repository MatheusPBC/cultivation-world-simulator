"""Material migration journeys: people remain residents until a dated arrival."""

import math

from src.classes.economy.migration import MigrationProvision
from src.classes.economy.models import MoneyAccount, Stock
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.migration import MigrationJourney
from src.systems.calendar_agenda import ScheduledSituation
from .economy import _causes, _delta
from .events import record_event
from .logistics import _route_causes
from .migration_policy import PASSENGER_BULK, RATIONS_PER_PERSON, migration_options, recovery_options
from .travel import route_duration


def _event(world, event_id):
    return next((event for event in world.events if event.id == event_id), None)


def _used_decision(world, decision_event_id):
    return any(event.event_type == "migration_started" and any(link.cause_event_id == decision_event_id
               for link in event.causal_links) for event in world.events)


def _food_stock(world, group_id):
    group = world.society.population[group_id]
    owner = EntityRef("population_group", group_id)
    stock = world.economy.stocks.get(f"household-stock:{group_id}")
    return stock if stock is not None and stock.owner_ref == owner and stock.location_id == group.settlement_id else None


def _actor_id(decision):
    payload = decision.decision if decision is not None else None
    if not isinstance(payload, dict):
        return None
    actor_ref = payload.get("actor_ref")
    try:
        actor = EntityRef.from_dict(actor_ref) if actor_ref is not None else None
    except (KeyError, TypeError, ValueError):
        return None
    return actor.id if actor is not None and actor.kind == "population_group" else None


def _migration_detail(option, character_ids=(), cancel_activity_ids=()):
    return {
        "action": "migrate", "actor_ref": EntityRef("population_group", option.group_id).to_dict(),
        "option_id": option.id, "group_id": option.group_id,
        "destination_id": option.destination_id, "count": option.count, "food": option.food,
        "route_ids": list(option.route_ids), "source_report_id": option.source_report_id,
        "destination_report_id": option.destination_report_id,
        "route_report_ids": list(option.route_report_ids), "character_ids": list(character_ids),
        "cancel_activity_ids": list(cancel_activity_ids),
    }


def _recovery_detail(option, group_id):
    return {
        "action": option.action, "actor_ref": EntityRef("population_group", group_id).to_dict(),
        "option_id": option.id, "journey_id": option.journey_id, "route_ids": list(option.route_ids),
        "report_ids": list(option.report_ids),
        **({"destination_id": option.destination_id} if option.destination_id is not None else {}),
    }


def start_migration(world, option_id, *, decision_event_id, character_ids=(), cancel_activity_ids=()):
    """Commit one current option; all material state is checked before mutation."""
    decision = _event(world, decision_event_id)
    if decision is None or decision.fact_kind != FactKind.DECISION or _used_decision(world, decision_event_id):
        raise ValueError("migration requires an unused decision")
    group_id = (decision.decision or {}).get("group_id") or _actor_id(decision)
    option = next((item for item in migration_options(world, group_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("migration option is stale or not selected by this group")
    evidence = {world.knowledge.settlement_reports[option.source_report_id].event_id,
                world.knowledge.settlement_reports[option.destination_report_id].event_id,
                *(world.knowledge.route_reports[report_id].event_id for report_id in option.route_report_ids)}
    selected = option.decision()
    if decision.decision == selected:
        # Direct callers may submit the actor-facing ID-only decision.  The
        # owner recomposes material terms once, then executes that authorization.
        authorization = record_event(
            world, "migration_authorized", "O grupo autorizou a jornada escolhida.",
            fact_kind=FactKind.DECISION,
            decision=_migration_detail(option, character_ids, cancel_activity_ids),
            cause_ids=(decision.id, *sorted(evidence)))
        decision = authorization
    elif decision.decision != _migration_detail(option, character_ids, cancel_activity_ids):
        raise ValueError("migration option is stale or not selected by this group")
    source_evidence = {link.cause_event_id for link in decision.causal_links}
    if not evidence.issubset(source_evidence):
        raise ValueError("migration decision must cite every report used by its option")
    group, selected = world.society._select_people(group_id, option.count, tuple(character_ids))
    if any(character.location_id != group.settlement_id for character in selected):
        raise ValueError("selected traveler is not physically at the source settlement")
    if group.count != world.society.available_count(group_id):
        raise ValueError("a cohort already has an active migration")
    source_account = world.economy.accounts.get(f"household:{group_id}")
    stock = _food_stock(world, group_id)
    if source_account is None or source_account.owner_ref != EntityRef("population_group", group_id) or stock is None:
        raise ValueError("migration requires the household's own cash and rations")
    # A partial household leaves only its proportional pantry share; it cannot
    # carry the ration of residents who remain behind.
    food = min(option.food, stock.goods.get("food", 0) * option.count // group.count,
               RATIONS_PER_PERSON * option.count)
    if food < option.count:
        raise ValueError("migration requires one household ration per traveler")
    busy = [activity for activity in world.activities.values() if activity.character_id in {c.id for c in selected}]
    if set(cancel_activity_ids) != {activity.id for activity in busy} or any(activity.kind not in {"training", "study"} for activity in busy):
        raise ValueError("busy named travelers require their explicit cancellable practice IDs")
    journey_id = f"journey:{decision.id}"
    account_id = f"migration-account:{journey_id}"
    provision_id = f"migration-provision:{journey_id}"
    if journey_id in world.society.migrations or account_id in world.economy.accounts or provision_id in world.economy.migration_provisions:
        raise ValueError("migration identity collision")
    cash = source_account.balance * option.count // group.count
    event = record_event(world, "migration_started", f"{option.count} pessoas iniciaram jornada com {food} rações.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("stock", stock.id, "food", stock.goods.get("food", 0), stock.goods.get("food", 0) - food),
                                 _delta("account", source_account.id, "balance", source_account.balance, source_account.balance - cash),
                                 _delta("account", account_id, "balance", 0, cash),
                                 _delta("population_group", group_id, "present_count", group.count, group.count - option.count),
                                 _delta("migration", journey_id, "stage", "none", "waiting"),
                                 _delta("migration_provision", provision_id, "food", 0, food),
                                 *(_delta("activity", activity.id, "status", "active", "cancelled") for activity in busy)),
                         cause_ids=_causes(decision.id, stock.last_event_ids.get("food"), source_account.last_event_id))
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "food": stock.goods.get("food", 0) - food},
                                                                "last_event_ids": {**stock.last_event_ids, "food": event.id}})
    world.economy.accounts[source_account.id] = source_account.model_copy(update={"balance": source_account.balance - cash, "last_event_id": event.id})
    world.society.population[group_id] = group.model_copy(update={"last_event_id": event.id})
    world.economy.accounts[account_id] = MoneyAccount(id=account_id, owner_ref=EntityRef("population_group", group_id), balance=cash, last_event_id=event.id)
    world.economy.migration_provisions[provision_id] = MigrationProvision(id=provision_id, journey_id=journey_id,
        account_id=account_id, food=food, health=world.economy.needs[group.settlement_id].health, last_event_id=event.id)
    world.society.migrations[journey_id] = MigrationJourney(id=journey_id, source_group_id=group_id,
        destination_id=option.destination_id, initial_destination_id=option.destination_id, count=option.count,
        character_ids=tuple(character_ids), route_ids=option.route_ids, initial_route_ids=option.route_ids,
        due_day=world.clock.absolute_day + 1, decision_event_id=decision.id, provision_id=provision_id, last_event_id=event.id)
    for activity in busy:
        del world.activities[activity.id]
    world.agenda.schedule(ScheduledSituation(journey_id, "migration", world.clock.absolute_day + 1))
    return world.society.migrations[journey_id]


def recover_migration(world, option_id, *, decision_event_id):
    """Execute one explicit current recovery choice for a stranded household."""
    decision = _event(world, decision_event_id)
    journey_id = (decision.decision or {}).get("journey_id") if decision is not None else None
    if journey_id is None:
        journey_id = next((journey.id for journey in world.society.migrations.values()
                           if any(option.id == option_id for option in recovery_options(world, journey.id))), None)
    journey = world.society.migrations.get(journey_id)
    if (decision is None or decision.fact_kind != FactKind.DECISION or journey is None
            or journey.stage != "stranded"):
        raise ValueError("migration recovery requires a stranded journey and decision")
    option = next((item for item in recovery_options(world, journey.id) if item.id == option_id), None)
    if option is None:
        raise ValueError("migration recovery option is stale")
    evidence = {world.knowledge.settlement_reports[report_id].event_id
                if report_id in world.knowledge.settlement_reports else world.knowledge.route_reports[report_id].event_id
                for report_id in option.report_ids}
    if decision.decision == option.decision(journey.source_group_id):
        # Recovery has no hidden material terms: the owner can recompose the
        # current route/report set directly from the selected affordance.
        pass
    elif decision.decision != _recovery_detail(option, journey.source_group_id):
        raise ValueError("migration recovery option is stale")
    if any(event.event_type in {"migration_retry_started", "migration_reroute_started", "migration_return_started"}
           and any(link.cause_event_id == decision.id for link in event.causal_links) for event in world.events):
        raise ValueError("migration recovery decision already executed")
    if not evidence.issubset({link.cause_event_id for link in decision.causal_links}):
        raise ValueError("migration recovery decision must cite its current reports")
    if option.action == "retry_migration_arrival":
        event = record_event(world, "migration_retry_started", "O grupo tenta novamente a chegada conhecida.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(_delta("migration", journey.id, "stage", "stranded", "arrival_retry"),),
                             cause_ids=_causes(decision.id, journey.last_event_id, *evidence))
        refreshed = journey.model_copy(update={"last_event_id": event.id})
        world.society.migrations[journey.id] = refreshed
        provision = world.economy.migration_provisions[refreshed.provision_id]
        world.economy.migration_provisions[provision.id] = provision.model_copy(update={"last_event_id": event.id})
        return _arrive(world, refreshed, (decision.id, *evidence))
    if option.action == "reroute_migration":
        if option.destination_id is None or option.destination_id == journey.destination_id:
            raise ValueError("migration reroute requires another destination")
        source = world.society.population.get(journey.source_group_id)
        destination = world.society.settlements.get(option.destination_id)
        report = world.knowledge.settlement_report(EntityRef("population_group", journey.source_group_id),
                                                   option.destination_id)
        if (source is None or destination is None or report is None
                or report.population + journey.count > destination.housing_capacity):
            raise ValueError("migration reroute destination is stale")
        updated = journey.model_copy(update={"destination_id": option.destination_id,
                                              "route_ids": option.route_ids, "route_index": 0,
                                              "stage": "waiting", "returning": False,
                                              "due_day": world.clock.absolute_day + 1})
        return _record_journey(world, journey, updated, "migration_reroute_started",
                               "O grupo escolheu uma segunda cidade conhecida após a chegada bloqueada.",
                               deltas=(_delta("migration", journey.id, "stage", "stranded", "waiting"),
                                       _delta("migration", journey.id, "destination_id", journey.destination_id,
                                              option.destination_id),
                                       _delta("migration", journey.id, "route_ids", list(journey.route_ids),
                                              list(option.route_ids))),
                               causes=(decision.id, *evidence))
    if option.action != "return_migration":
        raise ValueError("unknown migration recovery action")
    group = world.society.population[journey.source_group_id]
    updated = journey.model_copy(update={"destination_id": group.settlement_id, "route_ids": option.route_ids,
                                          "route_index": 0, "stage": "waiting", "returning": True,
                                          "due_day": world.clock.absolute_day + 1})
    return _record_journey(world, journey, updated, "migration_return_started",
                           "O grupo escolheu retornar pela rota conhecida.",
                           deltas=(_delta("migration", journey.id, "stage", "stranded", "waiting"),
                                   _delta("migration", journey.id, "destination_id", journey.destination_id, group.settlement_id),
                                   _delta("migration", journey.id, "returning", False, True)),
                           causes=(decision.id, *evidence))


def _record_journey(world, journey, updated, event_type, content, *, deltas=(), causes=()):
    # Every dated journey transition is a material state change.  Waypoint and
    # delay receipts used to carry only prose, which the event contract now
    # correctly rejects as a state transition without a delta.
    explicit_aspects = {delta.aspect for delta in deltas if delta.owner_kind == "migration"}
    journey_deltas = list(deltas)
    for aspect in ("route_index", "stage", "due_day", "destination_id", "returning"):
        before = getattr(journey, aspect)
        after = getattr(updated, aspect)
        if before != after and aspect not in explicit_aspects:
            journey_deltas.append(_delta("migration", journey.id, aspect, before, after))
    event = record_event(world, event_type, content, fact_kind=FactKind.STATE_TRANSITION,
                         deltas=tuple(journey_deltas),
                         cause_ids=_causes(journey.last_event_id, *causes))
    world.society.migrations[journey.id] = updated.model_copy(update={"last_event_id": event.id})
    provision = world.economy.migration_provisions[journey.provision_id]
    world.economy.migration_provisions[provision.id] = provision.model_copy(update={"last_event_id": event.id})
    if updated.stage != "stranded":
        world.agenda.schedule(ScheduledSituation(updated.id, "migration", updated.due_day))
    return event


def _portable_capacity(world, count):
    return RATIONS_PER_PERSON * count * world.economy.resources["food"].bulk


def _return_arrive(world, journey, causes):
    """Return is a material arrival home, not cancellation or teleportation."""
    provision = world.economy.migration_provisions[journey.provision_id]
    group = world.society.population[journey.source_group_id]
    account = world.economy.accounts[provision.account_id]
    household = world.economy.accounts.get(f"household:{group.id}")
    stock_id = f"household-stock:{group.id}"
    domestic = world.economy.stocks.get(stock_id)
    if household is None or household.owner_ref != EntityRef("population_group", group.id):
        raise ValueError("return requires the source household account")
    if domestic is not None and (domestic.owner_ref != EntityRef("population_group", group.id) or domestic.location_id != group.settlement_id):
        raise ValueError("return household stock has an invalid owner")
    before_food = domestic.goods.get("food", 0) if domestic else 0
    before_capacity = domestic.capacity if domestic else 0
    capacity = max(before_capacity, _portable_capacity(world, group.count))
    need = world.economy.needs[group.settlement_id]
    prior_present = world.society.present_population_at(group.settlement_id)
    health = (need.health * prior_present + provision.health * journey.count) // (prior_present + journey.count)
    event = record_event(world, "migration_returned", f"{journey.count} pessoas retornaram a {world.society.settlements[group.settlement_id].name}.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("migration", journey.id, "stage", journey.stage, "returned"),
                                 _delta("migration_provision", provision.id, "food", provision.food, 0),
                                 _delta("account", account.id, "balance", account.balance, 0),
                                 _delta("account", household.id, "balance", household.balance, household.balance + account.balance),
                                 _delta("stock", stock_id, "capacity", before_capacity, capacity),
                                 _delta("stock", stock_id, "food", before_food, before_food + provision.food),
                                 _delta("population_group", group.id, "present_count", group.count - journey.count, group.count),
                                 _delta("subsistence", need.id, "health", need.health, health)),
                         cause_ids=_causes(journey.last_event_id, provision.last_event_id, account.last_event_id, *causes))
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0, "last_event_id": event.id})
    world.economy.accounts[household.id] = household.model_copy(update={"balance": household.balance + account.balance, "last_event_id": event.id})
    if domestic is None:
        world.economy.stocks[stock_id] = Stock(id=stock_id, owner_ref=EntityRef("population_group", group.id), location_id=group.settlement_id,
                                                capacity=capacity, goods={"food": provision.food}, last_event_ids={"food": event.id})
    else:
        world.economy.stocks[stock_id] = domestic.model_copy(update={"capacity": capacity,
            "goods": {**domestic.goods, "food": before_food + provision.food},
            "last_event_ids": {**domestic.last_event_ids, "food": event.id}})
    world.economy.needs[need.id] = need.model_copy(update={"health": health,
                                                          "last_event_id": event.id})
    world.society.population[group.id] = group.model_copy(update={"last_event_id": event.id})
    del world.society.migrations[journey.id]
    del world.economy.migration_provisions[provision.id]
    return event


def _arrive(world, journey, causes):
    if journey.returning:
        return _return_arrive(world, journey, causes)
    provision = world.economy.migration_provisions[journey.provision_id]
    destination = world.society.settlements[journey.destination_id]
    if world.society.population_at(destination.id) + journey.count > destination.housing_capacity:
        destination_need = world.economy.needs[destination.id]
        # A group turned away by real housing capacity adds bounded local
        # pressure.  The blocked journey remains the only cause: no protest,
        # reroute or relief is opened by this delta.
        pressure = min(40, max(1, 100 * journey.count // max(destination.housing_capacity, 1)))
        blocked_unrest = min(1000, destination_need.unrest + pressure)
        updated = journey.model_copy(update={"stage": "stranded", "due_day": world.clock.absolute_day})
        event = _record_journey(world, journey, updated, "migration_arrival_blocked",
                                "A chegada foi impedida pela capacidade residencial atual.",
                                deltas=(_delta("subsistence", destination_need.id, "unrest",
                                                destination_need.unrest, blocked_unrest),),
                                causes=causes)
        world.economy.needs[destination_need.id] = destination_need.model_copy(
            update={"unrest": blocked_unrest, "last_event_id": event.id})
        from .settlement_intelligence import observe_present_household
        report = observe_present_household(world, journey.source_group_id, destination.id, event.id)
        world.society.migrations[journey.id] = world.society.migrations[journey.id].model_copy(update={"last_event_id": report.event_id})
        provision = world.economy.migration_provisions[journey.provision_id]
        world.economy.migration_provisions[provision.id] = provision.model_copy(update={"last_event_id": report.event_id})
        return report
    source = world.society.population[journey.source_group_id]
    target = next((group for group in world.society.population.values() if
                   (group.settlement_id, group.people, group.occupation) == (destination.id, source.people, source.occupation)), None)
    target_id = target.id if target else f"pop:{destination.id}:{source.people}:{source.occupation}"
    account = world.economy.accounts[provision.account_id]
    household_id = f"household:{target_id}"
    household = world.economy.accounts.get(household_id)
    if household is not None and household.owner_ref != EntityRef("population_group", target_id):
        raise ValueError("destination household account has an invalid owner")
    stock_id = f"household-stock:{target_id}"
    domestic = world.economy.stocks.get(stock_id)
    food_bulk = world.economy.resources["food"].bulk
    before_capacity = domestic.capacity if domestic else 0
    resident_count = (target.count if target else 0) + journey.count
    capacity = max(before_capacity, _portable_capacity(world, resident_count))
    if domestic is not None and (domestic.owner_ref != EntityRef("population_group", target_id) or domestic.location_id != destination.id):
        raise ValueError("destination household stock has an invalid owner")
    before_food = domestic.goods.get("food", 0) if domestic else 0
    prior_present = world.society.present_population_at(destination.id)
    need = world.economy.needs[destination.id]
    source_need = world.economy.needs[source.settlement_id]
    # A successful departure has a material social consequence at the origin:
    # the people who actually leave no longer carry the same local pressure.
    # Keep it bounded and derive it from the moved fraction; migration does not
    # create a generic morale bonus or erase scarcity by narrative fiat.
    source_relief = min(80, max(1, 200 * journey.count // max(source.count, 1)))
    source_unrest = max(0, source_need.unrest - source_relief)
    total_present = max(prior_present + journey.count, 1)
    destination_unrest = ((need.unrest * prior_present) + (source_need.unrest * journey.count)
                          + total_present - 1) // total_present
    health = (need.health * prior_present + provision.health * journey.count) // (prior_present + journey.count)
    event = record_event(world, "migration_arrived", f"{journey.count} pessoas chegaram a {destination.name}.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("migration", journey.id, "stage", journey.stage, "arrived"),
                                 _delta("migration_provision", provision.id, "food", provision.food, 0),
                                 _delta("account", account.id, "balance", account.balance, 0),
                                 _delta("account", household_id, "balance", household.balance if household else 0,
                                        (household.balance if household else 0) + account.balance),
                                 _delta("stock", stock_id, "capacity", before_capacity, capacity),
                                 _delta("stock", stock_id, "food", before_food, before_food + provision.food),
                                 _delta("population_group", journey.source_group_id, "resident_count", source.count, source.count - journey.count),
                                 _delta("population_group", target_id, "resident_count", target.count if target else 0,
                                        (target.count if target else 0) + journey.count),
                                 *(_delta("character", character.id, "location_id", character.location_id, destination.id)
                                   for character in (world.society.characters[character_id] for character_id in journey.character_ids)),
                                 *(_delta("character", character.id, "population_group_id", character.population_group_id, target_id)
                                   for character in (world.society.characters[character_id] for character_id in journey.character_ids)),
                                 _delta("subsistence", need.id, "health", need.health, health),
                                 _delta("subsistence", need.id, "unrest", need.unrest, destination_unrest),
                                 _delta("subsistence", source_need.id, "unrest", source_need.unrest, source_unrest)),
                         cause_ids=_causes(journey.last_event_id, provision.last_event_id, account.last_event_id, *causes))
    target_id = world.society.transfer_people(journey.source_group_id, destination.id, source.occupation,
                                               journey.count, journey.character_ids)
    world.society.population[journey.source_group_id] = world.society.population[journey.source_group_id].model_copy(update={"last_event_id": event.id})
    world.society.population[target_id] = world.society.population[target_id].model_copy(update={"last_event_id": event.id})
    if household is None:
        world.economy.accounts[household_id] = MoneyAccount(id=household_id, owner_ref=EntityRef("population_group", target_id), balance=account.balance, last_event_id=event.id)
    else:
        world.economy.accounts[household_id] = household.model_copy(update={"balance": household.balance + account.balance, "last_event_id": event.id})
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0, "last_event_id": event.id})
    if domestic is None:
        world.economy.stocks[stock_id] = Stock(id=stock_id, owner_ref=EntityRef("population_group", target_id), location_id=destination.id,
                                                capacity=capacity, goods={"food": provision.food}, last_event_ids={"food": event.id})
    else:
        world.economy.stocks[stock_id] = domestic.model_copy(update={"capacity": capacity,
            "goods": {**domestic.goods, "food": before_food + provision.food},
                                                                       "last_event_ids": {**domestic.last_event_ids, "food": event.id}})
    world.economy.needs[need.id] = need.model_copy(update={"health": health, "unrest": destination_unrest,
                                                          "last_event_id": event.id})
    world.economy.needs[source_need.id] = source_need.model_copy(update={"unrest": source_unrest,
                                                                           "last_event_id": event.id})
    del world.society.migrations[journey.id]
    del world.economy.migration_provisions[provision.id]
    return event


def _resolve(world, journey):
    provision = world.economy.migration_provisions[journey.provision_id]
    route_id = journey.route_ids[journey.route_index]
    route = world.map.routes[route_id]
    day = world.clock.absolute_day
    causes = _route_causes(world, (route_id,))[route_id]
    if journey.stage == "traveling":
        if journey.route_index == len(journey.route_ids) - 1:
            _arrive(world, journey, causes)
        else:
            updated = journey.model_copy(update={"route_index": journey.route_index + 1, "stage": "waiting", "due_day": day + 1})
            _record_journey(world, journey, updated, "migration_waypoint_reached", "A jornada alcançou o próximo trecho.", causes=causes)
        return
    capacity = math.floor(world.map.get_route_operational_capacity(route_id))
    bulk = journey.count * PASSENGER_BULK + provision.food * world.economy.resources["food"].bulk
    flow = world.economy.route_flows.get(route_id)
    used = flow.bulk if flow is not None and flow.day == day else 0
    if route.mode not in {"road", "river"} or route.quality <= 0 or capacity - used < bulk:
        updated = journey.model_copy(update={"due_day": day + 1})
        delay_count = sum(
            1 for event in world.events
            if event.event_type == "migration_delayed"
            and any(delta.owner_kind == "migration" and delta.owner_id == journey.id for delta in event.deltas)
        )
        pressure_deltas = ()
        source_need = world.economy.needs.get(world.society.population[journey.source_group_id].settlement_id)
        # A week of materially blocked travel raises local uncertainty once,
        # bounded by the same subsistence scale used elsewhere. The delay is
        # the cause; no actor or prose chooses the amount and no revolt is
        # opened by this condition alone.
        if source_need is not None and (delay_count + 1) % 7 == 0:
            pressure_deltas = (_delta("subsistence", source_need.id, "unrest",
                                      source_need.unrest, min(1000, source_need.unrest + 5)),)
        event = _record_journey(world, journey, updated, "migration_delayed",
                                "A passagem não comporta a jornada hoje.",
                                deltas=pressure_deltas, causes=causes)
        if pressure_deltas and source_need is not None:
            world.economy.needs[source_need.id] = source_need.model_copy(
                update={"unrest": min(1000, source_need.unrest + 5), "last_event_id": event.id})
        return
    updated = journey.model_copy(update={"stage": "traveling", "due_day": day + route_duration(world, route_id)})
    event = _record_journey(world, journey, updated, "migration_departed", "O grupo partiu pela rota conhecida.",
                            deltas=(_delta("route_flow", route_id, "bulk", used, used + bulk),), causes=causes)
    from src.classes.economy.logistics import RouteFlow
    world.economy.route_flows[route_id] = RouteFlow(id=route_id, day=day, bulk=used + bulk)
    return event


def resolve_migrations(world, situations):
    journeys = []
    for situation in situations:
        journey = world.society.migrations.get(situation.id)
        if situation.kind != "migration" or journey is None or journey.stage == "stranded" or journey.due_day != world.clock.absolute_day:
            raise ValueError("unknown or inconsistent dated migration")
        journeys.append(journey)
    for journey in sorted(journeys, key=lambda item: item.id):
        _resolve(world, journey)


def consume_travel_provisions(world):
    """One existing monthly ration per traveler; delays never create food."""
    for provision in sorted(world.economy.migration_provisions.values(), key=lambda item: item.id):
        if provision.consumed_day == world.clock.absolute_day:
            continue
        journey = world.society.migrations.get(provision.journey_id)
        if journey is None:
            raise ValueError("migration provision has no active journey")
        eaten = min(journey.count, provision.food)
        missing = journey.count - eaten
        health = max(0, provision.health - math.ceil(100 * missing / journey.count)) if missing else provision.health
        event = record_event(world, "migration_rations_consumed",
                             f"A jornada consumiu {eaten}/{journey.count} rações; déficit de {missing}.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(_delta("migration_provision", provision.id, "food", provision.food, provision.food - eaten),
                                     _delta("migration_provision", provision.id, "missing_food", provision.missing_food, missing),
                                     _delta("migration_provision", provision.id, "health", provision.health, health),
                                     _delta("migration_provision", provision.id, "consumed_day", provision.consumed_day,
                                            world.clock.absolute_day)),
                             cause_ids=_causes(provision.last_event_id, journey.last_event_id))
        world.economy.migration_provisions[provision.id] = provision.model_copy(update={"food": provision.food - eaten,
            "missing_food": missing, "health": health, "consumed_day": world.clock.absolute_day,
            "consumed_event_id": event.id, "last_event_id": event.id})

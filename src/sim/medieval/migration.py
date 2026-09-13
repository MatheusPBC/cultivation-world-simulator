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


def start_migration(world, option_id, *, decision_event_id, character_ids=(), cancel_activity_ids=()):
    """Commit one current option; all material state is checked before mutation."""
    decision = _event(world, decision_event_id)
    if decision is None or decision.fact_kind != FactKind.DECISION or _used_decision(world, decision_event_id):
        raise ValueError("migration requires an unused decision")
    group_id = (decision.decision or {}).get("group_id")
    option = next((item for item in migration_options(world, group_id) if item.id == option_id), None)
    if option is None or decision.decision != option.decision(character_ids=tuple(character_ids),
                                                               cancel_activity_ids=tuple(cancel_activity_ids)):
        raise ValueError("migration option is stale or not selected by this group")
    evidence = {world.knowledge.settlement_reports[option.source_report_id].event_id,
                world.knowledge.settlement_reports[option.destination_report_id].event_id,
                *(world.knowledge.route_reports[report_id].event_id for report_id in option.route_report_ids)}
    if {link.cause_event_id for link in decision.causal_links} != evidence:
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
    journey_id = f"journey:{decision_event_id}"
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
                         cause_ids=_causes(decision_event_id, stock.last_event_ids.get("food"), source_account.last_event_id))
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
        due_day=world.clock.absolute_day + 1, decision_event_id=decision_event_id, provision_id=provision_id, last_event_id=event.id)
    for activity in busy:
        del world.activities[activity.id]
    world.agenda.schedule(ScheduledSituation(journey_id, "migration", world.clock.absolute_day + 1))
    return world.society.migrations[journey_id]


def recover_migration(world, option_id, *, decision_event_id):
    """Execute one explicit current recovery choice for a stranded household."""
    decision = _event(world, decision_event_id)
    journey_id = (decision.decision or {}).get("journey_id") if decision is not None else None
    journey = world.society.migrations.get(journey_id)
    if (decision is None or decision.fact_kind != FactKind.DECISION or journey is None
            or journey.stage != "stranded"):
        raise ValueError("migration recovery requires a stranded journey and decision")
    option = next((item for item in recovery_options(world, journey.id) if item.id == option_id), None)
    if option is None or decision.decision != option.decision(journey.source_group_id):
        raise ValueError("migration recovery option is stale")
    if any(event.event_type in {"migration_retry_started", "migration_return_started"}
           and any(link.cause_event_id == decision.id for link in event.causal_links) for event in world.events):
        raise ValueError("migration recovery decision already executed")
    evidence = {world.knowledge.settlement_reports[report_id].event_id
                if report_id in world.knowledge.settlement_reports else world.knowledge.route_reports[report_id].event_id
                for report_id in option.report_ids}
    if {link.cause_event_id for link in decision.causal_links} != evidence:
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
    event = record_event(world, event_type, content, fact_kind=FactKind.STATE_TRANSITION, deltas=deltas,
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
    world.economy.needs[need.id] = need.model_copy(update={"health": health, "last_event_id": event.id})
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
        updated = journey.model_copy(update={"stage": "stranded", "due_day": world.clock.absolute_day})
        event = _record_journey(world, journey, updated, "migration_arrival_blocked",
                                "A chegada foi impedida pela capacidade residencial atual.", causes=causes)
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
                                 _delta("subsistence", need.id, "health", need.health, health)),
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
    world.economy.needs[need.id] = need.model_copy(update={"health": health, "last_event_id": event.id})
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
        _record_journey(world, journey, updated, "migration_delayed", "A passagem não comporta a jornada hoje.", causes=causes)
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

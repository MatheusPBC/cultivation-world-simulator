"""Dated, household-owned choices to leave a pressured settlement."""

from collections import deque

from pydantic import Field

from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Count, Identity, SocietyValue


REPORT_MAX_AGE = 30
PASSENGER_BULK = 1
RATIONS_PER_PERSON = 2


class MigrationOption(SocietyValue):
    """A transient, fully derivable option; it is deliberately not saved."""
    id: Identity
    group_id: Identity
    destination_id: Identity
    count: Count
    food: Count
    route_ids: tuple[Identity, ...]
    source_report_id: Identity
    destination_report_id: Identity
    route_report_ids: tuple[Identity, ...]

    def decision(self, *, character_ids=(), cancel_activity_ids=()):
        return {"action": "migrate", "actor_ref": EntityRef("population_group", self.group_id).to_dict(),
                "option_id": self.id, "group_id": self.group_id, "destination_id": self.destination_id,
                "count": self.count, "food": self.food, "route_ids": list(self.route_ids),
                "source_report_id": self.source_report_id, "destination_report_id": self.destination_report_id,
                "route_report_ids": list(self.route_report_ids), "character_ids": list(character_ids),
                "cancel_activity_ids": list(cancel_activity_ids)}


class MigrationRecoveryOption(SocietyValue):
    id: Identity
    journey_id: Identity
    action: str
    route_ids: tuple[Identity, ...] = ()
    report_ids: tuple[Identity, ...]

    def decision(self, group_id):
        return {"action": self.action, "actor_ref": EntityRef("population_group", group_id).to_dict(),
                "option_id": self.id, "journey_id": self.journey_id, "route_ids": list(self.route_ids),
                "report_ids": list(self.report_ids)}


def _fresh(world, report):
    return report is not None and world.clock.absolute_day - report.observed_day < REPORT_MAX_AGE


def _route_path(world, actor, origin_id, destination_id):
    """Use public topology only to connect the actor's own dated route reports."""
    origin = world.society.settlements[origin_id].region_id
    target = world.society.settlements[destination_id].region_id
    edges = {}
    for report in world.knowledge.routes_for_actor(actor):
        route = world.map.routes.get(report.route_id)
        if (not _fresh(world, report) or route is None or report.travel_days is None
                or report.operational_capacity <= 0 or route.mode not in {"road", "river"}):
            continue
        left, right = route.endpoint_region_ids
        edges.setdefault(left, []).append((right, report))
        edges.setdefault(right, []).append((left, report))
    pending = deque([(origin, (), ())])
    visited = {origin}
    while pending:
        region, routes, reports = pending.popleft()
        if region == target:
            return routes, reports
        for next_region, report in sorted(edges.get(region, ()), key=lambda item: item[1].route_id):
            if next_region not in visited:
                visited.add(next_region)
                pending.append((next_region, (*routes, report.route_id), (*reports, report)))
    return None


def _own_food(world, group_id):
    group = world.society.population[group_id]
    stock = world.economy.stocks.get(f"household-stock:{group_id}")
    return (stock.goods.get("food", 0) if stock is not None and stock.owner_ref == EntityRef("population_group", group_id)
            and stock.location_id == group.settlement_id else 0)


def migration_options(world, group_id):
    """Return only destinations this household was actually told about."""
    group = world.society.population.get(group_id)
    actor = EntityRef("population_group", group_id)
    source = world.knowledge.settlement_report(actor, group.settlement_id) if group else None
    if (group is None or world.society.available_count(group_id) != group.count or not _fresh(world, source)
            or not (source.missing_food > 0 or source.health < 700 or source.unrest >= 250)):
        return ()
    food_available = _own_food(world, group_id)
    choices = []
    for destination in world.knowledge.settlements_for_actor(actor):
        if (destination.settlement_id == group.settlement_id or not _fresh(world, destination)
                or destination.population >= destination.housing_capacity
                or destination.health < source.health or destination.missing_food > source.missing_food):
            continue
        path = _route_path(world, actor, group.settlement_id, destination.settlement_id)
        if path is None:
            continue
        route_ids, route_reports = path
        headroom = destination.housing_capacity - destination.population
        per_person_bulk = PASSENGER_BULK + RATIONS_PER_PERSON * world.economy.resources["food"].bulk
        route_limit = min(int(report.operational_capacity) // per_person_bulk for report in route_reports)
        population = max(1, source.present_population)
        severity = max(1000 - source.health, source.unrest, 1000 * source.missing_food // population)
        if severity < 250:  # Maintain locally when the dated pressure is not yet urgent.
            continue
        rate = min(200, max(50, severity // 5))
        policy_cap = group.count // 5
        if policy_cap <= 0:
            continue
        count = min(max(1, group.count * rate // 1000), policy_cap, headroom, food_available, route_limit)
        if count <= 0:
            continue
        food = min(food_available * count // group.count, RATIONS_PER_PERSON * count)
        if food < count:
            continue
        evidence = (source.event_id, destination.event_id, *(report.event_id for report in route_reports))
        option_id = "migration:" + group_id + ":" + destination.settlement_id + ":" + ":".join(evidence)
        choices.append(MigrationOption(id=option_id, group_id=group_id, destination_id=destination.settlement_id,
                       count=count, food=food, route_ids=route_ids, source_report_id=source.id,
                       destination_report_id=destination.id, route_report_ids=tuple(report.id for report in route_reports)))
    return tuple(sorted(choices, key=lambda choice: choice.id))


def recovery_options(world, journey_id):
    """A stranded household may choose a current retry or physically return."""
    journey = world.society.migrations.get(journey_id)
    if journey is None or journey.stage != "stranded":
        return ()
    actor = EntityRef("population_group", journey.source_group_id)
    options = []
    if not journey.returning:
        report = world.knowledge.settlement_report(actor, journey.destination_id)
        if _fresh(world, report) and report.population + journey.count <= report.housing_capacity:
            options.append(MigrationRecoveryOption(id=f"migration-retry:{journey.id}:{journey.last_event_id}:{report.event_id}",
                journey_id=journey.id, action="retry_migration_arrival", report_ids=(report.id,)))
    reports = [world.knowledge.route_report(actor, route_id) for route_id in reversed(journey.route_ids)]
    source = world.knowledge.settlement_report(actor, world.society.population[journey.source_group_id].settlement_id)
    destination = world.knowledge.settlement_report(actor, journey.destination_id)
    if (all(_fresh(world, report) and report.travel_days is not None and report.operational_capacity > 0 for report in reports)
            and _fresh(world, source) and _fresh(world, destination)):
        options.append(MigrationRecoveryOption(id="migration-return:" + journey.id + ":" + journey.last_event_id + ":" +
            ":".join(report.event_id for report in reports), journey_id=journey.id, action="return_migration",
            route_ids=tuple(reversed(journey.route_ids)), report_ids=tuple((*[report.id for report in reports], source.id, destination.id))))
    return tuple(sorted(options, key=lambda option: option.id))


def review_migration(world):
    """Groups select conservative options from their own dated observations."""
    from src.classes.event import FactKind
    from .events import record_event
    from .migration import recover_migration, start_migration
    from .settlement_intelligence import observe_present_household

    # A stranded group is physically at its endpoint and can make a fresh local
    # observation there. This is presence, not a map-derived private fact.
    recovered_groups = set()
    recovered_groups.update(delta.owner_id for event in world.events
                            if event.day == world.clock.absolute_day and event.event_type == "migration_returned"
                            for delta in event.deltas if delta.owner_kind == "population_group")
    for journey in sorted(world.society.migrations.values(), key=lambda item: item.id):
        if journey.stage != "stranded":
            continue
        actor = EntityRef("population_group", journey.source_group_id)
        observe_present_household(world, journey.source_group_id, journey.destination_id, journey.last_event_id)
        options = recovery_options(world, journey.id)
        retry = next((item for item in options if item.action == "retry_migration_arrival"), None)
        source = world.knowledge.settlement_report(actor, world.society.population[journey.source_group_id].settlement_id)
        destination = world.knowledge.settlement_report(actor, journey.destination_id)
        returning = next((item for item in options if item.action == "return_migration"), None)
        # Waiting remains valid when the known destination is healthier despite
        # lacking housing; return only when its observed conditions are worse.
        option = retry or (returning if destination is not None and source is not None
                           and (destination.health <= source.health or destination.missing_food >= source.missing_food
                                or destination.unrest > source.unrest) else None)
        if option is None:
            continue
        evidence = {world.knowledge.settlement_reports[report_id].event_id
                    if report_id in world.knowledge.settlement_reports else world.knowledge.route_reports[report_id].event_id
                    for report_id in option.report_ids}
        decision = record_event(world, "migration_recovery_decided", "O grupo reavalia a jornada a partir de sua posição atual.",
                                fact_kind=FactKind.DECISION, decision=option.decision(journey.source_group_id),
                                cause_ids=tuple(sorted(evidence)))
        recover_migration(world, option.id, decision_event_id=decision.id)
        recovered_groups.add(journey.source_group_id)

    for group_id in sorted(world.society.population):
        if group_id in recovered_groups:
            continue
        options = migration_options(world, group_id)
        if not options:
            continue
        # Conservative household choice: the best observed health/food/headroom,
        # then the shorter known route. It is not an arbitrary registry first.
        option = max(options, key=lambda item: (
            world.knowledge.settlement_reports[item.destination_report_id].health,
            -world.knowledge.settlement_reports[item.destination_report_id].missing_food,
            world.knowledge.settlement_reports[item.destination_report_id].housing_capacity
            - world.knowledge.settlement_reports[item.destination_report_id].population,
            -len(item.route_ids), item.id))
        report_events = {world.knowledge.settlement_reports[option.source_report_id].event_id,
                         world.knowledge.settlement_reports[option.destination_report_id].event_id,
                         *(world.knowledge.route_reports[rid].event_id for rid in option.route_report_ids)}
        decision = record_event(world, "migration_decided", "O grupo escolhe uma rota conhecida para deixar a pressão local.",
                                fact_kind=FactKind.DECISION, decision=option.decision(),
                                cause_ids=tuple(sorted(report_events)))
        start_migration(world, option.id, decision_event_id=decision.id)

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
                "selected_affordance_id": self.id}


class MigrationRecoveryOption(SocietyValue):
    id: Identity
    journey_id: Identity
    action: str
    route_ids: tuple[Identity, ...] = ()
    report_ids: tuple[Identity, ...]
    destination_id: Identity | None = None

    def decision(self, group_id):
        return {"action": self.action, "actor_ref": EntityRef("population_group", group_id).to_dict(),
                "selected_affordance_id": self.id}


def _fresh(world, report):
    return report is not None and world.clock.absolute_day - report.observed_day < REPORT_MAX_AGE


def _route_path(world, actor, origin_id, destination_id, *, route_reports=None):
    """Use public topology only to connect the actor's own dated route reports."""
    origin = world.society.settlements[origin_id].region_id
    target = world.society.settlements[destination_id].region_id
    edges = {}
    # Reports are immutable during one migration review.  Callers may pass a
    # transient per-actor index so repeated destination checks do not rebuild
    # the same public graph; the index is never persisted.
    for report in (world.knowledge.routes_for_actor(actor) if route_reports is None else route_reports):
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


def migration_options(world, group_id, *, route_reports=None):
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
        path = _route_path(world, actor, group.settlement_id, destination.settlement_id,
                           route_reports=route_reports)
        if path is None:
            continue
        route_ids, path_reports = path
        headroom = destination.housing_capacity - destination.population
        per_person_bulk = PASSENGER_BULK + RATIONS_PER_PERSON * world.economy.resources["food"].bulk
        route_limit = min(int(report.operational_capacity) // per_person_bulk for report in path_reports)
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
        evidence = (source.event_id, destination.event_id, *(report.event_id for report in path_reports))
        option_id = "migration:" + group_id + ":" + destination.settlement_id + ":" + ":".join(evidence)
        choices.append(MigrationOption(id=option_id, group_id=group_id, destination_id=destination.settlement_id,
                       count=count, food=food, route_ids=route_ids, source_report_id=source.id,
                       destination_report_id=destination.id, route_report_ids=tuple(report.id for report in path_reports)))
    return tuple(sorted(choices, key=lambda choice: choice.id))


def recovery_options(world, journey_id, *, route_reports=None):
    """A stranded household may retry, reroute, or physically return.

    Rerouting is limited to another settlement known through current reports
    and reachable through the household's own dated route observations. It
    changes no population or stock until a later physical arrival.
    """
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
        source = world.society.population.get(journey.source_group_id)
        source_report = (world.knowledge.settlement_report(actor, source.settlement_id)
                         if source is not None else None)
        if source is not None and _fresh(world, source_report):
            for destination in world.knowledge.settlements_for_actor(actor):
                if (destination.settlement_id in {source.settlement_id, journey.destination_id}
                        or not _fresh(world, destination)
                        or destination.population + journey.count > destination.housing_capacity):
                    continue
                path = _route_path(world, actor, source.settlement_id, destination.settlement_id,
                                   route_reports=route_reports)
                if path is None:
                    continue
                route_ids, route_reports = path
                if not route_ids or any(not _fresh(world, item) or item.operational_capacity <= 0
                                        for item in route_reports):
                    continue
                report_ids = (source_report.id, destination.id, *(item.id for item in route_reports))
                options.append(MigrationRecoveryOption(
                    id=(f"migration-reroute:{journey.id}:{journey.last_event_id}:{destination.settlement_id}:"
                        f"{':'.join(item.event_id for item in route_reports)}"),
                    journey_id=journey.id, action="reroute_migration", route_ids=tuple(route_ids),
                    report_ids=tuple(report_ids), destination_id=destination.settlement_id))
    reports = [world.knowledge.route_report(actor, route_id) for route_id in reversed(journey.route_ids)]
    source = world.knowledge.settlement_report(actor, world.society.population[journey.source_group_id].settlement_id)
    destination = world.knowledge.settlement_report(actor, journey.destination_id)
    if (all(_fresh(world, report) and report.travel_days is not None and report.operational_capacity > 0 for report in reports)
            and _fresh(world, source) and _fresh(world, destination)):
        options.append(MigrationRecoveryOption(id="migration-return:" + journey.id + ":" + journey.last_event_id + ":" +
            ":".join(report.event_id for report in reports), journey_id=journey.id, action="return_migration",
            route_ids=tuple(reversed(journey.route_ids)), report_ids=tuple((*[report.id for report in reports], source.id, destination.id))))
    return tuple(sorted(options, key=lambda option: option.id))


def review_migration(world, *, excluded_actors=()):
    """Groups select conservative options without a completed provider turn."""
    excluded = set(excluded_actors)
    from src.classes.event import FactKind
    from .events import record_event
    from .migration import recover_migration, start_migration
    from .settlement_intelligence import observe_present_household

    # A stranded group is physically at its endpoint and can make a fresh local
    # observation there. This is presence, not a map-derived private fact.
    recovered_groups = set()
    # Reuse each population group's dated public route reports for the whole
    # review.  This is a transient read index, not persisted world state.
    route_reports_by_actor = {
        EntityRef("population_group", group_id): world.knowledge.routes_for_actor(
            EntityRef("population_group", group_id))
        for group_id in sorted(world.society.population)
    }
    recovered_groups.update(delta.owner_id for event in world.events
                            if event.day == world.clock.absolute_day and event.event_type == "migration_returned"
                            for delta in event.deltas if delta.owner_kind == "population_group")
    for journey in sorted(world.society.migrations.values(), key=lambda item: item.id):
        if journey.stage != "stranded":
            continue
        actor = EntityRef("population_group", journey.source_group_id)
        if actor in excluded:
            continue
        observe_present_household(world, journey.source_group_id, journey.destination_id, journey.last_event_id)
        options = recovery_options(world, journey.id,
                                   route_reports=route_reports_by_actor.get(actor, ()))
        retry = next((item for item in options if item.action == "retry_migration_arrival"), None)
        source = world.knowledge.settlement_report(actor, world.society.population[journey.source_group_id].settlement_id)
        destination = world.knowledge.settlement_report(actor, journey.destination_id)
        returning = next((item for item in options if item.action == "return_migration"), None)
        # Waiting remains valid when the known destination is healthier despite
        # lacking housing; return only when its observed conditions are worse.
        destination_need = (world.economy.needs.get(destination.settlement_id)
                            if destination is not None else None)
        blocked_pressure = False
        if destination_need is not None and destination_need.last_event_id:
            blocked_event = next((event for event in reversed(world.events)
                                  if event.id == destination_need.last_event_id), None)
            blocked_pressure = blocked_event is not None and blocked_event.event_type == "migration_arrival_blocked"
        option = retry or (returning if destination is not None and source is not None
                           and (destination.health <= source.health or destination.missing_food >= source.missing_food
                                or (destination.unrest > source.unrest and not blocked_pressure)) else None)
        if option is None:
            continue
        evidence = {world.knowledge.settlement_reports[report_id].event_id
                    if report_id in world.knowledge.settlement_reports else world.knowledge.route_reports[report_id].event_id
                    for report_id in option.report_ids}
        recovery_decision = {"action": option.action,
                             "actor_ref": actor.to_dict(), "option_id": option.id,
                             "journey_id": option.journey_id, "route_ids": list(option.route_ids),
                             "report_ids": list(option.report_ids),
                             **({"destination_id": option.destination_id} if option.destination_id is not None else {})}
        decision = record_event(world, "migration_recovery_decided", "O grupo reavalia a jornada a partir de sua posição atual.",
                                fact_kind=FactKind.DECISION, decision=recovery_decision,
                                cause_ids=tuple(sorted(evidence)))
        recover_migration(world, option.id, decision_event_id=decision.id)
        recovered_groups.add(journey.source_group_id)

    for group_id in sorted(world.society.population):
        if group_id in recovered_groups:
            continue
        actor = EntityRef("population_group", group_id)
        if actor in excluded:
            continue
        options = migration_options(world, group_id,
                                    route_reports=route_reports_by_actor.get(actor, ()))
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
        migration_decision = {"action": "migrate", "actor_ref": EntityRef("population_group", group_id).to_dict(),
                              "option_id": option.id, "group_id": option.group_id,
                              "destination_id": option.destination_id, "count": option.count, "food": option.food,
                              "route_ids": list(option.route_ids), "source_report_id": option.source_report_id,
                              "destination_report_id": option.destination_report_id,
                              "route_report_ids": list(option.route_report_ids), "character_ids": [],
                              "cancel_activity_ids": []}
        decision = record_event(world, "migration_decided", "O grupo escolhe uma rota conhecida para deixar a pressão local.",
                                fact_kind=FactKind.DECISION, decision=migration_decision,
                                cause_ids=tuple(sorted(report_events)))
        start_migration(world, option.id, decision_event_id=decision.id)


def migration_adapters():
    from .institutional_decision_turn import DiscretionaryAdapter
    from .migration import recover_migration, start_migration
    from .events import record_event
    from src.classes.event import FactKind

    def migration_options_for(world, actor):
        return migration_options(world, actor.id) if isinstance(actor, EntityRef) and actor.kind == "population_group" else ()

    def recovery_options_for(world, actor):
        if not isinstance(actor, EntityRef) or actor.kind != "population_group":
            return ()
        return tuple(option for journey in world.society.migrations.values()
                     if journey.source_group_id == actor.id
                     for option in recovery_options(world, journey.id))

    def causes_for(world, option):
        ids = []
        if isinstance(option, MigrationOption):
            ids.extend((world.knowledge.settlement_reports[option.source_report_id].event_id,
                        world.knowledge.settlement_reports[option.destination_report_id].event_id))
            ids.extend(world.knowledge.route_reports[item].event_id for item in option.route_report_ids)
        else:
            ids.extend((world.knowledge.settlement_reports[item].event_id
                        if item in world.knowledge.settlement_reports
                        else world.knowledge.route_reports[item].event_id)
                       for item in option.report_ids)
        return tuple(dict.fromkeys(ids))

    def execute_migration(world, actor, option_id, decision_event_id):
        option = next((item for item in migration_options(world, actor.id) if item.id == option_id), None)
        if option is None:
            raise ValueError("migration option is stale or unknown")
        authorization = record_event(
            world, "migration_authorized", "O grupo autorizou a jornada escolhida.",
            fact_kind=FactKind.DECISION,
            decision={"action": "migrate", "actor_ref": actor.to_dict(), "group_id": option.group_id,
                      "destination_id": option.destination_id, "count": option.count, "food": option.food,
                      "route_ids": list(option.route_ids), "source_report_id": option.source_report_id,
                      "destination_report_id": option.destination_report_id,
                      "route_report_ids": list(option.route_report_ids), "character_ids": [],
                      "cancel_activity_ids": []},
            cause_ids=(decision_event_id,))
        return start_migration(world, option.id, decision_event_id=authorization.id)

    def execute_recovery(world, actor, option_id, decision_event_id):
        option = next((item for journey in world.society.migrations.values()
                       if journey.source_group_id == actor.id
                       for item in recovery_options(world, journey.id) if item.id == option_id), None)
        if option is None:
            raise ValueError("migration recovery option is stale or unknown")
        authorization = record_event(
            world, "migration_recovery_authorized", "O grupo autorizou a recuperação escolhida.",
            fact_kind=FactKind.DECISION,
            decision={"action": option.action, "actor_ref": actor.to_dict(), "option_id": option.id,
                      "journey_id": option.journey_id, "route_ids": list(option.route_ids),
                      "report_ids": list(option.report_ids),
                      **({"destination_id": option.destination_id} if option.destination_id is not None else {})},
            cause_ids=(decision_event_id,))
        return recover_migration(world, option.id, decision_event_id=authorization.id)

    return (
        DiscretionaryAdapter(name="migration", family="mobility", options_fn=migration_options_for,
                             label_fn=lambda option: f"Migrar {option.count} pessoas para {option.destination_id}.",
                             causes_fn=causes_for, execute_fn=execute_migration),
        DiscretionaryAdapter(name="migration_recovery", family="mobility", options_fn=recovery_options_for,
                             label_fn=lambda option: f"Escolher recuperação da jornada ({option.action}).",
                             causes_fn=causes_for, execute_fn=execute_recovery),
    )


def migration_actors(world):
    return tuple(EntityRef("population_group", group_id) for group_id in sorted(world.society.population)
                 if migration_options(world, group_id) or any(
                     recovery_options(world, journey.id) for journey in world.society.migrations.values()
                     if journey.source_group_id == group_id))

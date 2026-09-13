"""Pure projections of canonical state, called while the runtime owns its lock."""

from .contracts import (CalendarView, CausalView, CharacterView, EconomyView, EventsView,
                        MapView, RouteView, SettlementView, SocietyView, WorldView)
from .errors import RuntimeProblem


def observatory_view(runtime):
    from .contracts import ObservatoryView
    world = runtime.require_world()
    return ObservatoryView(status=runtime.status(), world=world_view(world),
                           society=society_view(world), economy=economy_view(world),
                           map=map_view(world), governance=governance_view(world), research=research_view(world))


def research_view(world):
    from .contracts import ResearchView
    return ResearchView(technologies=ordered(world.research.technologies),
                        projects=ordered(world.research.projects), knowledge=ordered(world.knowledge.technologies))


def governance_view(world):
    from .contracts import GovernanceView, ObjectiveView
    from src.sim.medieval.demand import objective_target
    return GovernanceView(offices=ordered(world.authority.offices), tax_policies=ordered(world.authority.tax_policies), reports=ordered(world.knowledge.reports),
                          objectives=[ObjectiveView(**o.model_dump(), target_quantity=objective_target(world, o))
                                      for o in ordered(world.strategy.objectives)], plans=ordered(world.strategy.plans))


def ordered(registry):
    return [value for _, value in sorted(registry.items())]


def world_view(world):
    year, month, day = world.clock.calendar_date
    return WorldView(day=world.clock.absolute_day, calendar=CalendarView(year=year + 1, month=month, day=day),
                     config=world.config, population=world.society.total_population,
                     living_characters=sum(c.death_day is None for c in world.society.characters.values()),
                     settlements=len(world.society.settlements), polities=len(world.society.polities),
                     organizations=len(world.society.organizations), events=len(world.events),
                     next_scheduled_day=min(world.agenda.due_days, default=None))


def settlements(world):
    result = []
    for item in ordered(world.society.settlements):
        needs = world.economy.needs[item.id]
        result.append(SettlementView(**item.model_dump(), population=world.society.population_at(item.id),
                                      center=world.map.regions[item.region_id].center_loc,
                                      health=needs.health, unrest=needs.unrest, missing_food=needs.missing_food))
    return result


def society_view(world):
    characters = [CharacterView(**c.model_dump(), age_years=((c.death_day if c.death_day is not None else world.clock.absolute_day)
                                                           - c.birth_day) // 360) for c in ordered(world.society.characters)]
    return SocietyView(characters=characters, settlements=settlements(world), polities=ordered(world.society.polities),
                       organizations=ordered(world.society.organizations), population_groups=ordered(world.society.population),
                       activities=ordered(world.activities))


def economy_view(world):
    economy = world.economy
    registries = {name: ordered(getattr(economy, name)) for name in
                  ("resources", "recipes", "stocks", "accounts", "facilities", "payrolls", "needs", "markets", "parcels", "route_flows", "expansion_blueprints", "expansions")}
    pending = [o for o in ordered(economy.freight_orders) if o.delivered_quantity < o.quantity]
    return EconomyView(**registries, pending_orders=pending, completed_order_count=len(economy.freight_orders) - len(pending))


def map_view(world):
    game_map = world.map
    region_rows = [[game_map.get_tile(x, y).region.id for x in range(game_map.width)] for y in range(game_map.height)]
    return MapView(map_id=game_map.map_id, name=game_map.map_name, width=game_map.width, height=game_map.height,
                   region_rows=region_rows, geography=game_map.geography, settlements=settlements(world),
                   routes=[RouteView(route=r, operational_capacity=game_map.get_route_operational_capacity(r.id))
                           for r in ordered(game_map.routes)], sites=ordered(game_map.infrastructure_sites))


def events_view(world, after=0, limit=50):
    # Sequence numbers are contiguous and one-based; slicing avoids scanning old history.
    page = world.events[after:after + limit]
    next_after = page[-1].sequence if page else after
    return EventsView(items=page, next_after=next_after, has_more=next_after < len(world.events))


def causal_view(world, event_id, after=0, limit=50):
    lookup = {e.id: e for e in world.events}
    event = lookup.get(event_id)
    if event is None:
        raise RuntimeProblem("EVENT_NOT_FOUND", "Acontecimento não encontrado.", 404)
    effects = [e for e in world.events[after:] if any(link.cause_event_id == event_id for link in e.causal_links)]
    page = effects[:limit]
    return CausalView(event=event, causes=[lookup[link.cause_event_id] for link in event.causal_links], effects=page,
                      next_after=page[-1].sequence if page else after, has_more=len(effects) > limit)

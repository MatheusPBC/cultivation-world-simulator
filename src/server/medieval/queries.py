"""Pure projections of canonical state, called while the runtime owns its lock."""

from .contracts import (CalendarView, CausalView, CharacterView, EconomyView, EventsView,
                        MapView, RouteView, SettlementView, SocietyView, WorldView)
from .errors import RuntimeProblem
from src.classes.mechanical_language import EntityRef


def observatory_view(runtime):
    from .contracts import ObservatoryView
    world = runtime.require_world()
    return ObservatoryView(status=runtime.status(), world=world_view(world),
                           society=society_view(world), economy=economy_view(world),
                           map=map_view(world), governance=governance_view(world), research=research_view(world),
                           diplomacy=diplomacy_view(world), creatures=creature_view(world),
                           campaigns=campaign_view(world))


def creature_view(world):
    """Omniscient Dao read: creatures, their demands and the private notices."""
    from .contracts import CreatureDamageView, CreatureView
    damages = []
    for creature in ordered(world.creatures.creatures):
        if creature.damaged_site_id is None:
            continue
        site = world.map.infrastructure_sites.get(creature.damaged_site_id)
        if site is None or creature.damage_event_id is None:
            raise RuntimeError("validated creature damage is missing its canonical site")
        damages.append(CreatureDamageView(creature_id=creature.id, site_id=site.id,
                                          damage_event_id=creature.damage_event_id,
                                          integrity=site.integrity))
    return CreatureView(creatures=ordered(world.creatures.creatures),
                        demands=ordered(world.creatures.demands),
                        tribute_notices=ordered(world.knowledge.creature_tribute_notices),
                        damaged_sites=damages)


def campaign_view(world):
    """Dao-only campaign state assembled from Society's canonical registries.

    This deliberately reads no KnowledgeState registry.  The viewer may see a
    force, claim or threat even when the actors involved have received no
    corresponding notice.
    """
    from .contracts import CampaignView, OccupationView
    occupations = [OccupationView(settlement_id=settlement.id,
                                  occupier_ref=EntityRef("polity", settlement.occupier_id))
                   for settlement in ordered(world.society.settlements)
                   if settlement.occupier_id is not None]
    return CampaignView(detachments=ordered(world.society.detachments),
                        commands=ordered(world.society.detachment_commands),
                        positions=ordered(world.society.force_positions),
                        standoffs=ordered(world.society.force_standoffs),
                        field_engagements=ordered(world.society.field_engagements),
                        route_interdictions=ordered(world.society.route_interdictions),
                        settlement_investments=ordered(world.society.settlement_investments),
                        assembly_denials=ordered(world.society.assembly_denials),
                        occupations=occupations)


def diplomacy_view(world):
    from .contracts import AidRelationshipView, DiplomacyView, InstitutionalMemoryView
    from src.sim.medieval.institutional_memory import aid_evidence, effective_salience, institutional_view
    memories = [InstitutionalMemoryView(**memory.model_dump(),
                                        effective_salience=effective_salience(world, memory))
                for memory in ordered(world.relations.memories)]
    observers = sorted({memory.institution_ref for memory in world.relations.memories.values()},
                       key=lambda ref: (ref.kind, ref.id))
    readings = [AidRelationshipView(observer_ref=observer, subject_ref=subject,
                                    value=institutional_view(world, observer, subject),
                                    evidence_event_ids=list(event_ids))
                for observer in observers for subject, event_ids in aid_evidence(world, observer)]
    return DiplomacyView(proposals=ordered(world.relations.proposals),
                         obligations=ordered(world.relations.obligations),
                         notices=ordered(world.knowledge.notices),
                         aid_notices=ordered(world.knowledge.institutional_aid_notices),
                         memories=memories, aid_readings=readings)


def research_view(world):
    from .contracts import ResearchView
    return ResearchView(technologies=ordered(world.research.technologies),
                        projects=ordered(world.research.projects), knowledge=ordered(world.knowledge.technologies))


def governance_view(world):
    from .contracts import GovernanceView, ObjectiveView
    from src.sim.medieval.demand import objective_target
    return GovernanceView(offices=ordered(world.authority.offices), tax_policies=ordered(world.authority.tax_policies), reports=ordered(world.knowledge.reports),
                          objectives=[ObjectiveView(**o.model_dump(), target_quantity=objective_target(world, o))
                                      for o in ordered(world.strategy.objectives)], plans=ordered(world.strategy.plans),
                          route_reports=ordered(world.knowledge.route_reports),
                          fiscal_route_reports=ordered(world.knowledge.fiscal_route_reports),
                          site_reports=ordered(world.knowledge.site_reports),
                          settlement_reports=ordered(world.knowledge.settlement_reports),
                          customs_notices=ordered(world.knowledge.customs_notices),
                          workforce_demand_reports=ordered(world.knowledge.workforce_demand_reports),
                          workforce_offer_notices=ordered(world.knowledge.workforce_offer_notices),
                          claims=ordered(world.authority.claims),
                          authority_recognitions=ordered(world.relations.authority_recognitions))


def ordered(registry):
    return [value for _, value in sorted(registry.items())]


def world_view(world):
    from .contracts import DecisionSourceView
    from src.sim.medieval.ai_decider import FAILED_EVENT, INTERPRETED_EVENT
    year, month, day = world.clock.calendar_date
    sources = DecisionSourceView(
        provider_consultations=sum(1 for item in world.events if item.event_type == INTERPRETED_EVENT),
        provider_failures=sum(1 for item in world.events if item.event_type == FAILED_EVENT),
        ai_enabled=world.config.ai_enabled)
    return WorldView(day=world.clock.absolute_day, calendar=CalendarView(year=year + 1, month=month, day=day),
                     config=world.config, decision_sources=sources, population=world.society.total_population,
                     living_characters=sum(c.death_day is None for c in world.society.characters.values()),
                     settlements=len(world.society.settlements), polities=len(world.society.polities),
                     organizations=len(world.society.organizations), events=len(world.events),
                     next_scheduled_day=min(world.agenda.due_days, default=None),
                     regional_overflows=ordered(world.regional_overflow.active_occurrences))


def settlements(world):
    result = []
    for item in ordered(world.society.settlements):
        needs = world.economy.needs[item.id]
        result.append(SettlementView(**item.model_dump(), population=world.society.population_at(item.id),
                                      present_population=world.society.present_population_at(item.id),
                                      center=world.map.regions[item.region_id].center_loc,
                                      health=needs.health, unrest=needs.unrest, missing_food=needs.missing_food))
    return result


def society_view(world):
    characters = [CharacterView(**c.model_dump(), age_years=((c.death_day if c.death_day is not None else world.clock.absolute_day)
                                                           - c.birth_day) // 360) for c in ordered(world.society.characters)]
    return SocietyView(characters=characters, settlements=settlements(world), polities=ordered(world.society.polities),
                       organizations=ordered(world.society.organizations), population_groups=ordered(world.society.population),
                       activities=ordered(world.activities), migrations=ordered(world.society.migrations),
                       workforce_transitions=ordered(world.society.workforce_transitions))


def economy_view(world):
    economy = world.economy
    registries = {name: ordered(getattr(economy, name)) for name in
                  ("resources", "recipes", "stocks", "accounts", "facilities", "payrolls", "needs", "markets", "parcels", "route_flows",
                  "expansion_blueprints", "expansions", "repair_blueprints", "repairs", "migration_provisions", "customs_checkpoints", "cargo_manifests")}
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

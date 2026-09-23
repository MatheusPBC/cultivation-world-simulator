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
    from .contracts import CreatureDamageView, CreatureView, HazardImpactView
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
    impacts = []
    for event in world.events:
        payload = getattr(event, "causal_payload", {})
        impact = payload.get("hazard_impact") if isinstance(payload, dict) else None
        if impact is None:
            continue
        resistance = payload.get("hazard_resistance", {})
        impacts.append(HazardImpactView(
            event_id=event.id,
            source_event_id=impact["source_event_id"],
            hazard_kind=impact["hazard_kind"],
            target_ref=EntityRef.from_dict(impact["target_ref"]),
            effect=impact["effect"], magnitude=impact["magnitude"], exposure=impact["exposure"],
            resistance=resistance,
        ))
    return CreatureView(creatures=ordered(world.creatures.creatures),
                        demands=ordered(world.creatures.demands),
                        tribute_notices=ordered(world.knowledge.creature_tribute_notices),
                        damaged_sites=damages, hazard_impacts=impacts)


def campaign_view(world):
    """Dao-only campaign state assembled from Society's canonical registries.

    This deliberately reads no KnowledgeState registry.  The viewer may see a
    force, claim or threat even when the actors involved have received no
    corresponding notice.
    """
    from .contracts import CampaignView, OccupationView, PoliticalSettlementView, ThreatView
    occupations = [OccupationView(settlement_id=settlement.id,
                                  occupier_ref=EntityRef("polity", settlement.occupier_id))
                   for settlement in ordered(world.society.settlements)
                   if settlement.occupier_id is not None]
    political_settlements = [
        PoliticalSettlementView(
            id=proposal.id,
            proposal_kind=proposal.proposal_kind,
            settlement_id=next((getattr(clause, "settlement_id", None) for clause in proposal.clauses
                                if getattr(clause, "settlement_id", None) is not None),
                               next((standoff.settlement_id for clause in proposal.clauses
                                     for standoff in world.society.force_standoffs.values()
                                     if getattr(clause, "standoff_id", None) == standoff.id),
                                    next((world.society.siege_campaigns[clause.campaign_id].settlement_id
                                          for clause in proposal.clauses
                                          if getattr(clause, "campaign_id", None) in world.society.siege_campaigns),
                                         None))),
            proposer_ref=proposal.proposer_ref,
            counterparty_ref=proposal.counterparty_ref,
            status=proposal.status,
            offered_day=proposal.offered_day,
            expires_day=proposal.expires_day,
            clause_kinds=[clause.kind for clause in proposal.clauses],
            decision_event_id=proposal.decision_event_id,
            last_event_id=proposal.last_event_id,
        )
        for proposal in ordered(world.relations.proposals)
        if proposal.proposal_kind in {"force_deescalation", "administration_concession", "campaign_ceasefire"}
        and proposal.status in {"offered", "accepted"}
        and (proposal.status == "accepted" or proposal.expires_day >= world.clock.absolute_day)
    ]
    threats = []
    for demand in ordered(world.creatures.demands):
        if demand.stage == "open":
            threats.append(ThreatView(
                id=f"creature-demand:{demand.id}", kind="creature_demand",
                route_id=demand.route_id,
                severity="high" if demand.due_day <= world.clock.absolute_day else "medium",
                status=demand.stage, source_event_id=demand.perception_event_id))
    for siege in ordered(world.society.siege_campaigns):
        if siege.phase in {"sieging", "breached"}:
            threats.append(ThreatView(
                id=f"siege:{siege.id}", kind="siege", settlement_id=siege.settlement_id,
                severity="high" if siege.phase == "breached" else "medium",
                status=siege.phase, source_event_id=siege.last_event_id))
    for movement in ordered(world.society.civic_movements):
        if movement.stage in {"rebellion", "revolution"}:
            threats.append(ThreatView(
                id=f"civic:{movement.id}", kind="civic_rebellion", settlement_id=movement.settlement_id,
                severity="high" if movement.stage == "revolution" else "medium",
                status=movement.stage, source_event_id=movement.last_event_id))
    for interdiction in ordered(world.society.route_interdictions):
        if interdiction.stage == "active":
            threats.append(ThreatView(
                id=f"route-interdiction:{interdiction.id}", kind="route_interdiction",
                route_id=interdiction.route_id, severity="high", status=interdiction.stage,
                source_event_id=interdiction.last_event_id))
    for creature in ordered(world.creatures.creatures):
        ecology_event = next((event for event in reversed(world.events)
                              if event.event_type == "creature_ecology_tick"
                              and any(delta.owner_kind == "creature"
                                      and delta.owner_id == creature.id
                                      for delta in event.deltas)), None)
        payload = getattr(ecology_event, "causal_payload", None) if ecology_event is not None else None
        ecology = payload.get("ecology") if isinstance(payload, dict) else None
        if isinstance(ecology, dict):
            for route_id in ecology.get("impaired_route_ids", ()):
                stress = int(ecology.get("habitat_stress", 0) or 0)
                threats.append(ThreatView(
                    id=f"creature-habitat:{creature.id}:{route_id}:{ecology_event.id}",
                    kind="creature_habitat_stress", route_id=route_id,
                    severity="high" if stress >= 5 else "medium", status="active",
                    source_event_id=ecology_event.id))
        if creature.damaged_site_id is not None and creature.damage_event_id is not None:
            threats.append(ThreatView(
                id=f"hazard-site:{creature.id}:{creature.damaged_site_id}", kind="hazard_damage",
                site_id=creature.damaged_site_id, severity="medium", status="active",
                source_event_id=creature.damage_event_id))
    for journey in ordered(world.society.migrations):
        if journey.stage == "stranded":
            route_id = journey.route_ids[journey.route_index] if journey.route_ids and journey.route_index < len(journey.route_ids) else None
            threats.append(ThreatView(
                id=f"migration-blocked:{journey.id}", kind="migration_blocked",
                settlement_id=journey.destination_id, route_id=route_id,
                severity="high" if journey.due_day < world.clock.absolute_day else "medium",
                status="blocked", source_event_id=journey.last_event_id))
    for denial in ordered(world.society.assembly_denials):
        event = next((item for item in reversed(world.events) if item.id == denial.last_event_id), None)
        payload = event.causal_payload if event is not None else None
        conflict = payload.get("social_conflict") if isinstance(payload, dict) else None
        if isinstance(conflict, dict) and conflict.get("kind") == "religious_persecution":
            threats.append(ThreatView(
                id=f"religious-persecution:{denial.id}", kind="religious_persecution",
                settlement_id=denial.settlement_id, severity="medium", status="active",
                source_event_id=denial.last_event_id))
    return CampaignView(detachments=ordered(world.society.detachments),
                        commands=ordered(world.society.detachment_commands),
                        positions=ordered(world.society.force_positions),
                        standoffs=ordered(world.society.force_standoffs),
                        field_engagements=ordered(world.society.field_engagements),
                        route_interdictions=ordered(world.society.route_interdictions),
                        settlement_investments=ordered(world.society.settlement_investments),
                        garrisons=ordered(world.society.garrisons),
                        siege_campaigns=ordered(world.society.siege_campaigns),
                        assembly_denials=ordered(world.society.assembly_denials),
                        occupations=occupations,
                        territorial_controls=ordered(world.society.territorial_controls),
                        political_settlements=political_settlements,
                        threats=sorted(threats, key=lambda item: item.id))


def diplomacy_view(world):
    from .contracts import AidRelationshipView, DiplomacyView, InstitutionalMemoryView
    from src.sim.medieval.diplomacy_context import strategic_evidence
    from src.sim.medieval.institutional_memory import aid_evidence, effective_salience, institutional_view
    events = {event.id: event for event in world.events}
    memories = []
    for memory in ordered(world.relations.memories):
        event = events.get(memory.event_id)
        kind = event.event_type if event is not None else "unknown"
        if kind == "commitment_breached" and event is not None:
            deliberate = any(
                (cause := events.get(link.cause_event_id)) is not None
                and cause.decision is not None
                and cause.decision.get("action") == "repudiate_obligation"
                for link in event.causal_links
            )
            kind = "commitment_repudiated" if deliberate else "commitment_breached"
        memories.append(InstitutionalMemoryView(
            **memory.model_dump(), effective_salience=effective_salience(world, memory), kind=kind))
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
                         memories=memories, aid_readings=readings,
                         strategic_evidence=list(strategic_evidence(world)))


def research_view(world):
    from .contracts import ResearchView, TechnologySaleEvidenceView
    events = {event.id: event for event in world.events}
    sales = []
    for receipt in world.events:
        if receipt.event_type != "technology_sale_completed":
            continue
        causes = {link.cause_event_id for link in receipt.causal_links}
        request = next((events[event_id] for event_id in causes
                        if events[event_id].event_type == "technology_sale_requested"), None)
        acceptance = next((events[event_id] for event_id in causes
                           if events[event_id].event_type == "technology_sale_accepted"), None)
        learned = next((knowledge for knowledge in world.knowledge.technologies.values()
                        if knowledge.channel == "sale" and knowledge.event_id in causes), None)
        if request is None or acceptance is None or learned is None:
            raise RuntimeError("technology sale receipt is missing its canonical evidence")
        payment_event_id = world.economy.payments.get(request.id)
        if payment_event_id not in causes or request.decision is None or acceptance.decision is None:
            raise RuntimeError("technology sale receipt is missing its current consent or payment")
        sales.append(TechnologySaleEvidenceView(
            receipt_event_id=receipt.id,
            buyer_ref=EntityRef.from_dict(request.decision["actor_ref"]),
            seller_ref=EntityRef.from_dict(acceptance.decision["actor_ref"]),
            technology_id=learned.technology_id,
            request_event_id=request.id,
            acceptance_event_id=acceptance.id,
            payment_event_id=payment_event_id,
            knowledge_event_id=learned.event_id,
        ))
    rite_blueprints = [
        {
            "id": blueprint.id,
            "school": blueprint.school,
            "cost": blueprint.cost,
            "range": blueprint.range,
            "duration_days": blueprint.duration_days,
        }
        for blueprint in ordered(world.research.rite_blueprints)
    ]
    return ResearchView(technologies=ordered(world.research.technologies),
                        projects=ordered(world.research.projects), knowledge=ordered(world.knowledge.technologies),
                        technology_sales=sales, rite_blueprints=rite_blueprints)


def governance_view(world):
    from .contracts import GovernanceView, ObjectiveView, StrategicCapacityView, StrategicCapacityDimensionView
    from src.sim.medieval.demand import objective_target
    actors = [*(EntityRef("polity", identity) for identity in sorted(world.society.polities)),
              *(EntityRef("organization", identity) for identity in sorted(world.society.organizations))]
    strategic_capacity = []
    for actor in actors:
        raw = world.strategy.capacity_for(actor, world).to_dict()
        strategic_capacity.append(StrategicCapacityView(
            actor_ref=actor,
            dimensions={key: StrategicCapacityDimensionView(**value) for key, value in raw.items()},
        ))
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
                          authority_recognitions=ordered(world.relations.authority_recognitions),
                          strategic_capacity=strategic_capacity)


def ordered(registry):
    return [value for _, value in sorted(registry.items())]


def world_view(world):
    from .contracts import DecisionSourceView
    from src.sim.medieval.ai_decider import DECLINED_EVENT, FAILED_EVENT, INTERPRETED_EVENT
    from src.sim.medieval.institutional_decision_turn import NO_AFFORDANCE_EVENT_TYPE, STALE_AFFORDANCE_EVENT_TYPE
    year, month, day = world.clock.calendar_date
    sources = DecisionSourceView(
        provider_consultations=sum(1 for item in world.events if item.event_type == INTERPRETED_EVENT),
        provider_declines=sum(1 for item in world.events if item.event_type == DECLINED_EVENT),
        provider_failures=sum(1 for item in world.events if item.event_type == FAILED_EVENT),
        no_affordance_receipts=sum(1 for item in world.events if item.event_type == NO_AFFORDANCE_EVENT_TYPE),
        stale_affordance_receipts=sum(1 for item in world.events if item.event_type == STALE_AFFORDANCE_EVENT_TYPE),
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
                       workforce_transitions=ordered(world.society.workforce_transitions),
                       civic_protests=ordered(world.society.civic_protests),
                       civic_movements=ordered(world.society.civic_movements),
                       civic_strikes=ordered(world.society.civic_strikes),
                       civic_amnesties=ordered(world.society.civic_amnesties))


def actor_dossier(world, actor_kind, actor_id):
    """Project one actor's current private perspective without inventing facts.

    KnowledgeState remains the only owner of notices and findings.  This query
    merely filters those registries by their explicit recipient, then adds the
    actor's own technical knowledge, institutional memories and strategy
    records.  Foreign inventories, plans and canonical events are excluded.
    """
    from .contracts import DossierEntry, DossierView
    from src.classes.governance.serialization import validate_actor
    from src.sim.medieval.institutional_memory import effective_salience

    actor = EntityRef(actor_kind, actor_id)
    try:
        validate_actor(world, actor)
    except ValueError as exc:
        raise RuntimeProblem("ACTOR_NOT_FOUND", "Ator não encontrado.", 404) from exc

    entries = []
    events = {event.id: event for event in world.events}

    def add(category, item):
        payload = item.model_dump(mode="json")
        event_id = payload.get("event_id") or payload.get("source_event_id") or payload.get("last_event_id")
        learned_day = payload.get("learned_day")
        entries.append(DossierEntry(category=category, id=item.id, event_id=event_id,
                                    learned_day=learned_day, payload=payload))

    for registry_name in world.knowledge.registries:
        for item in getattr(world.knowledge, registry_name).values():
            if getattr(item, "recipient_ref", None) == actor:
                add(registry_name, item)
    for item in world.knowledge.technologies.values():
        if item.owner_ref == actor:
            add("technical_knowledge", item)
    for item in world.relations.memories.values():
        if item.institution_ref == actor:
            payload = item.model_dump(mode="json")
            payload["effective_salience"] = effective_salience(world, item)
            entries.append(DossierEntry(category="institutional_memory", id=item.id,
                                        event_id=item.event_id, payload=payload))
    for item in world.strategy.objectives.values():
        if item.actor_ref == actor:
            add("strategic_objective", item)
    objective_ids = {item.id for item in world.strategy.objectives.values() if item.actor_ref == actor}
    for item in world.strategy.plans.values():
        if item.objective_id in objective_ids:
            add("strategic_plan", item)
    # An actor necessarily knows its own decisions.  This makes an investigation
    # useful without granting it foreign private state.
    own_decision_ids = {
        event.id for event in world.events
        if event.decision is not None
        and event.decision.get("actor_ref") == actor.to_dict()
    }
    known_event_ids = sorted({item.event_id for item in entries if item.event_id} | own_decision_ids)
    known_event_set = set(known_event_ids)
    # Roots are facts delivered directly by a notice/read-model or decisions
    # made by the actor.  Follow only already-known causal links; this keeps a
    # multi-hop dossier useful for navigation without turning it into an
    # investigation oracle that leaks hidden causes.
    # Actor decisions are the only stable causal roots here.  A delivered
    # notice is an observed result, so when its own known ancestors exist the
    # depth remains useful instead of flattening every notice to zero.
    roots = set(own_decision_ids)
    causal_depth = {event_id: 0 for event_id in roots if event_id in known_event_set}
    changed = True
    while changed:
        changed = False
        for event_id in known_event_ids:
            event = events.get(event_id)
            if event is None:
                continue
            parent_depths = [causal_depth[link.cause_event_id] for link in event.causal_links
                             if link.cause_event_id in causal_depth]
            if not parent_depths:
                continue
            depth = min(parent_depths) + 1
            if event_id not in causal_depth or depth < causal_depth[event_id]:
                causal_depth[event_id] = min(depth, 64)
                changed = True
    for event_id in known_event_ids:
        event = events.get(event_id)
        if event is None:
            continue
        # The actor receives the factual receipt itself, not a hidden causal
        # expansion.  Causes remain available only through the normal Why
        # endpoint when the Dao chooses to inspect them.
        payload = {
            "id": event.id, "day": event.day, "event_type": event.event_type,
            "content": event.content, "fact_kind": event.fact_kind,
            # StateDelta is a domain dataclass, not a Pydantic model.  Use its
            # canonical wire representation so the actor-facing read model
            # remains JSON-safe after a material event reaches the dossier.
            "deltas": [delta.to_dict() for delta in event.deltas],
        }
        known_causes = [link.cause_event_id for link in event.causal_links
                        if link.cause_event_id in known_event_ids]
        entries.append(DossierEntry(category="known_fact", id=f"fact:{event.id}",
                                    event_id=event.id, learned_day=event.day,
                                    cause_event_ids=known_causes,
                                    causal_depth=causal_depth.get(event.id, 0), payload=payload))
    entries.sort(key=lambda item: (item.category, item.id))
    return DossierView(actor_ref=actor, entries=entries)


def economy_view(world):
    economy = world.economy
    registries = {name: ordered(getattr(economy, name)) for name in
                  ("resources", "recipes", "stocks", "accounts", "facilities", "payrolls", "needs", "markets", "parcels", "route_flows",
                  "expansion_blueprints", "expansions", "repair_blueprints", "repairs", "migration_provisions", "customs_checkpoints", "cargo_manifests", "employment_contracts")}
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

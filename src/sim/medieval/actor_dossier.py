"""What one actor actually knows, read straight from its own canonical records.

The Dao/observatory keep full omniscient access elsewhere; this module exists
only to bound what a *decider* sees before a provider chooses among an
engine-enumerated menu. It reads existing knowledge, relations, strategy and
authority registries and copies nothing into new state: every field here is a
dated report, an active memory, an objective or an authority scope the actor
already holds. A decision-context builder composes its own ``situation`` from
this dossier instead of hand-rolling which omniscient fields are safe to show.
"""

from collections import defaultdict

from src.classes.mechanical_language import EntityRef

from .diplomacy_context import strategic_evidence
from .infrastructure import current_observation
from .institutional_memory import effective_salience, institutional_views
from .regional_overflow import site_overflow_reading


def _latest_food_affordability(world, report):
    """Project only affordability known at the report's actual observation.

    ``consume_monthly`` records household purchasing limits in the structured
    subsistence payload.  The provider gets only aggregate quantities and the
    source event; balances, cohort IDs and prose never become actor context.
    """
    unknown = {"unaffordable_food": 0, "unaffordable_group_count": 0,
               "affordability_event_id": None}
    if report is None:
        return unknown
    events = world.event_index()
    observed = events.get(report.event_id)
    if observed is None:
        return unknown
    if observed.event_type == "settlement_report_received":
        observed = next((events.get(link.cause_event_id) for link in observed.causal_links
                         if events.get(link.cause_event_id) is not None
                         and events[link.cause_event_id].event_type == "settlement_observed"), None)
    if observed is None or observed.event_type != "settlement_observed":
        return unknown
    for event in reversed(world.events_of_type("subsistence_resolved")):
        if event.sequence > observed.sequence:
            continue
        payload = event.causal_payload if isinstance(event.causal_payload, dict) else None
        reading = payload.get("subsistence") if payload else None
        if not isinstance(reading, dict) or reading.get("settlement_id") != report.settlement_id:
            continue
        unaffordable = reading.get("unaffordable_by_group", {})
        if not isinstance(unaffordable, dict):
            return {"unaffordable_food": 0, "unaffordable_group_count": 0,
                    "affordability_event_id": event.id}
        amounts = tuple(max(0, int(value)) for value in unaffordable.values()
                        if isinstance(value, int) and not isinstance(value, bool))
        return {"unaffordable_food": sum(amounts),
                "unaffordable_group_count": len(amounts),
                "affordability_event_id": event.id}
    return unknown


def _known_settlement_reports(world, actor):
    reports = []
    for report in world.knowledge.settlements_for_actor(actor):
        reports.append({"settlement_id": report.settlement_id, "missing_food": report.missing_food,
                        "observed_day": report.observed_day, "event_id": report.event_id,
                        **_latest_food_affordability(world, report)})
    return tuple(reports)


def _known_site_overflow_reports(world, actor):
    """Project regional overflow exposure only for the actor's current, valid sites.

    ``current_observation`` is the same canonical infrastructure/knowledge
    check the maintenance vertical revalidates a report against (provenance
    plus the 30-day freshness window); it is reused here rather than
    duplicated, so a stale or forged report is silently omitted instead of
    projected.  ``site_overflow_reading`` derives geography-only exposure and
    replays the engine's own already-recorded monthly assessment/occurrence;
    nothing here computes or predicts a future month, and no stock, account
    or route ever joins this projection.
    """
    reports = []
    for candidate in world.knowledge.site_reports.values():
        if candidate.recipient_ref != actor:
            continue
        report = current_observation(world, actor, candidate.site_id)
        if report is None:
            continue
        reading = site_overflow_reading(world, report.site_id)
        if reading is not None:
            reports.append({"observed_day": report.observed_day, "event_id": report.event_id, **reading})
    return tuple(sorted(reports, key=lambda item: item["site_id"]))


def _own_production_readings(world, actor):
    """Expose dated production limits for facilities owned by ``actor``.

    This is a read projection, not a second economy ledger.  The owner keeps
    the authoritative facility/stock state; the dossier only repeats the
    latest production receipt and the engine-owned limitation it recorded.
    Foreign facilities are never projected, and no estimate is made when a
    facility has not produced yet.  In particular, a missing labour reading is
    not turned into an invented worker demand here: the workforce owner must
    enumerate that affordance separately.
    """
    readings = []
    events = world.event_index()
    for facility in sorted(world.economy.facilities.values(), key=lambda item: item.id):
        stock = world.economy.stocks.get(facility.stock_id)
        if stock is None or stock.owner_ref != actor or facility.last_event_id is None:
            continue
        event = events.get(facility.last_event_id)
        if event is None or event.event_type not in {"production_completed", "production_limited"}:
            continue
        recipe = world.economy.recipes[facility.recipe_id]
        shortfall = next(
            (int(delta.after) for delta in event.deltas
             if delta.owner_kind == "production"
             and delta.owner_id == facility.id
             and delta.aspect == "labor_shortfall"),
            0,
        )
        readings.append({
            "settlement_id": stock.location_id,
            "occupation": recipe.occupation,
            "batches": facility.last_batches,
            "capacity": facility.max_batches,
            "limitations": list(facility.last_limitations),
            "labor_shortfall": max(0, shortfall),
            "observed_day": event.day,
            "event_id": event.id,
        })
    return tuple(readings)


def _own_local_livelihood_readings(world, actor):
    """Show an administrator its current census beside its own paid production.

    A local settlement observation grounds the resident counts.  Only payrolls
    from the actor's own facilities are included; other employers' accounts,
    wages and group identities are neither read nor guessed.  If the census
    predates a population change, the reading waits for another observation.
    """
    if actor.kind != "polity":
        return ()
    events = world.event_index()
    day = world.clock.absolute_day
    readings = []
    for settlement in sorted(world.society.settlements.values(), key=lambda item: item.id):
        if settlement.administrator_id != actor.id:
            continue
        report = world.knowledge.settlement_report(actor, settlement.id)
        if (report is None or report.publisher_ref != actor
                or report.channel != "local_settlement_report" or report.observed_day != day):
            continue
        try:
            world.knowledge._validate_settlement_report(world, events, report)
        except ValueError:
            continue
        observed = events.get(report.event_id)
        if observed is None or observed.event_type != "settlement_observed":
            continue
        groups = {group.id: group for group in world.society.population.values()
                  if group.settlement_id == settlement.id}
        if (sum(group.count for group in groups.values()) != report.population
                or any(group.last_event_id in events
                       and events[group.last_event_id].sequence > observed.sequence
                       for group in groups.values())):
            continue
        residents = defaultdict(int)
        for group in groups.values():
            residents[group.occupation] += group.count
        paid = defaultdict(int)
        payroll_sources = []
        for facility in world.economy.facilities.values():
            stock = world.economy.stocks.get(facility.stock_id)
            payroll = world.economy.payrolls.get(facility.id)
            if (stock is None or stock.owner_ref != actor or stock.location_id != settlement.id
                    or payroll is None or payroll.day != day):
                continue
            source = events.get(payroll.last_event_id)
            if source is None or source.sequence > observed.sequence:
                continue
            for group_id, count in payroll.workers_by_group.items():
                group = groups.get(group_id)
                if group is not None:
                    paid[group.occupation] += count
            payroll_sources.append(source.id)
        readings.append({
            "settlement_id": settlement.id,
            "observed_day": report.observed_day,
            "residents_by_occupation": dict(sorted(residents.items())),
            "own_production_paid_workers_by_occupation": dict(sorted(paid.items())),
            "source_event_ids": tuple(sorted({report.event_id, *payroll_sources})),
        })
    return tuple(readings)


def _authority_scopes(world, actor):
    day = world.clock.absolute_day
    return tuple(sorted({scope for office in world.authority.offices.values()
                         for scope in office.scopes
                         if office.institution_ref == actor and office.holder_ref == actor
                         and office.starts_day <= day and (office.ends_day is None or day < office.ends_day)}))


def _own_objectives(world, actor):
    """Kind, place and resource only -- never the objective's own raw id,
    which is only an internal basis (e.g. built from a stock's address) and
    is not itself a dated report the actor is owed."""
    return tuple({"resource_id": objective.resource_id,
                  "settlement_id": objective.settlement_id, "kind": objective.kind}
                 for objective in sorted(world.strategy.objectives.values(), key=lambda o: o.id)
                 if objective.actor_ref == actor)


def _own_plans(world, actor):
    """Expose lifecycle of the actor's plans without foreign handles.

    Orders, stock IDs and freight identities remain owner-private.  The actor
    still needs to know whether its own intention is active, blocked or done
    so the provider can choose among current affordances coherently.
    """
    objectives = {objective.id: objective for objective in world.strategy.objectives.values()
                  if objective.actor_ref == actor}
    return tuple({"settlement_id": objective.settlement_id,
                  "resource_id": objective.resource_id,
                  "kind": objective.kind,
                  "stage": plan.stage,
                  "blocker": plan.blocker,
                  "last_review_day": plan.last_review_day}
                 for plan in sorted(world.strategy.plans.values(), key=lambda item: item.id)
                 if (objective := objectives.get(plan.objective_id)) is not None)


def _active_memory(world, actor):
    return tuple({"institution_ref": memory.institution_ref.to_dict(), "event_id": memory.event_id,
                  "recorded_day": memory.recorded_day}
                 for memory in world.relations.memories_for(actor)
                 if effective_salience(world, memory) > 0)


def _known_institutional_views(world, actor):
    """Expose only directional readings backed by the actor's own knowledge.

    The memory module already applies the knowledge boundary and derives the
    reading from canonical facts.  Keeping this projection in the shared
    dossier means every composed institutional turn receives the same social
    context instead of only the diplomacy-specific provider path.
    """
    return tuple({"subject_ref": subject.to_dict(), "reading": reading,
                  "evidence_event_ids": list(event_ids)}
                 for subject, reading, event_ids in institutional_views(world, actor))


def provider_strategic_capacity(world, actor):
    """Project capacity without exposing internal registry identifiers.

    The Dao/API may expose source IDs for navigation. An actor-facing provider
    context receives only lifecycle status and bounded counts; raw objective,
    stock, treasury, payroll or order handles remain owner-private.
    """
    last_identity = id(world.events[-1]) if world.events else 0
    signature = (len(world.events), last_identity)
    cached = world._strategic_capacity_cache
    if cached is None or cached[0] != signature:
        cached = (signature, {})
        world._strategic_capacity_cache = cached
    key = (actor.kind, actor.id)
    projected = cached[1].get(key)
    if projected is not None:
        return projected
    raw = world.strategy.capacity_for(actor, world).to_dict()
    projected = {
        key: {
            "status": value["status"],
            "objective_count": len(value.get("objective_ids", ())),
            "plan_count": len(value.get("plan_ids", ())),
            "source_count": len(value.get("source_ids", ())),
        }
        for key, value in raw.items()
    }
    cached[1][key] = projected
    return projected


def build_actor_dossier(world, actor):
    """Only current, actor-owned knowledge; never a live or foreign record."""
    if not isinstance(actor, EntityRef):
        raise TypeError("dossier requires an EntityRef actor")
    return {
        "actor": actor.to_dict(),
        "today": world.clock.absolute_day,
        "known_settlement_reports": _known_settlement_reports(world, actor),
        "own_production_readings": _own_production_readings(world, actor),
        "own_local_livelihood_readings": _own_local_livelihood_readings(world, actor),
        "known_site_overflow_reports": _known_site_overflow_reports(world, actor),
        "authority_scopes": _authority_scopes(world, actor),
        "own_objectives": _own_objectives(world, actor),
        "own_plans": _own_plans(world, actor),
        "active_memory": _active_memory(world, actor),
        "known_institutional_views": _known_institutional_views(world, actor),
        # Findings are already private KnowledgeState projections.  Keep the
        # same recipient boundary in the generic dossier so every institutional
        # family receives the evidence the actor actually knows, without
        # exposing foreign inventory, plans or hidden causes.
        "known_strategic_evidence": strategic_evidence(world, actor),
        "strategic_capacity": provider_strategic_capacity(world, actor),
    }

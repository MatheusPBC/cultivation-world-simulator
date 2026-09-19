"""What one actor actually knows, read straight from its own canonical records.

The Dao/observatory keep full omniscient access elsewhere; this module exists
only to bound what a *decider* sees before a provider chooses among an
engine-enumerated menu. It reads existing knowledge, relations, strategy and
authority registries and copies nothing into new state: every field here is a
dated report, an active memory, an objective or an authority scope the actor
already holds. A decision-context builder composes its own ``situation`` from
this dossier instead of hand-rolling which omniscient fields are safe to show.
"""

from src.classes.mechanical_language import EntityRef

from .diplomacy_context import strategic_evidence
from .institutional_memory import effective_salience, institutional_views


def _known_settlement_reports(world, actor):
    return tuple({"settlement_id": report.settlement_id, "missing_food": report.missing_food,
                  "observed_day": report.observed_day, "event_id": report.event_id}
                 for report in world.knowledge.settlements_for_actor(actor))


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
    raw = world.strategy.capacity_for(actor, world).to_dict()
    return {
        key: {
            "status": value["status"],
            "objective_count": len(value.get("objective_ids", ())),
            "plan_count": len(value.get("plan_ids", ())),
            "source_count": len(value.get("source_ids", ())),
        }
        for key, value in raw.items()
    }


def build_actor_dossier(world, actor):
    """Only current, actor-owned knowledge; never a live or foreign record."""
    if not isinstance(actor, EntityRef):
        raise TypeError("dossier requires an EntityRef actor")
    return {
        "actor": actor.to_dict(),
        "today": world.clock.absolute_day,
        "known_settlement_reports": _known_settlement_reports(world, actor),
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

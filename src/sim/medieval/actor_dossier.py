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

from .institutional_memory import effective_salience


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


def _active_memory(world, actor):
    return tuple({"institution_ref": memory.institution_ref.to_dict(), "event_id": memory.event_id,
                  "recorded_day": memory.recorded_day}
                 for memory in world.relations.memories_for(actor)
                 if effective_salience(world, memory) > 0)


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
        "active_memory": _active_memory(world, actor),
    }

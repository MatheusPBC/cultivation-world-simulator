"""Provider turn for the bounded civic-demand vertical.

This module only gives a real actor a turn over already materialized civic
affordances.  The protest owner remains :mod:`civic_protest`; this policy
records the actor decision and delegates execution back to that owner.
"""

from src.classes.mechanical_language import EntityRef

from .civic_protest import (DISSOLVE_ACTION, OPEN_ACTION, REFUSE_ACTION,
                             civic_dissolve_options, civic_protest_options,
                             civic_refusal_options, dissolve_civic_protest,
                             open_civic_protest, refuse_civic_demand)
from .institutional_decision_turn import (DiscretionaryAdapter, _rotated,
                                          review_institutional_decision_turn_with_provider)

_LABELS = {
    OPEN_ACTION: "Abrir uma demanda cívica local usando o relatório observado.",
    DISSOLVE_ACTION: "Dissolver a própria demanda cívica.",
    REFUSE_ACTION: "Recusar a demanda cívica recebida.",
}


def _group_situation(world, actor, options):
    group = world.society.population[actor.id]
    report = world.knowledge.settlement_report(actor, group.settlement_id)
    return {
        "you_are": actor.to_dict(),
        "settlement_id": group.settlement_id,
        "observed_day": report.observed_day if report is not None else None,
        "missing_food": report.missing_food if report is not None else None,
        "health": report.health if report is not None else None,
        "unrest": report.unrest if report is not None else None,
        "open_protests": [item.id for item in options if item.id.startswith("civic-protest-dissolve:")],
        "today": world.clock.absolute_day,
    }


def _admin_situation(world, actor, options):
    notices = {item.protest_id: item for item in world.knowledge.civic_demands_for_actor(actor)}
    return {
        "you_are": actor.to_dict(),
        "demands_received": [
            {"protest_id": notice.protest_id, "settlement_id": notice.settlement_id,
             "demand_kind": notice.demand_kind, "due_day": notice.due_day}
            for item in options if (notice := notices.get(item.protest_id)) is not None
        ],
        "today": world.clock.absolute_day,
    }


def _situation(world, actor, options):
    return (_group_situation if actor.kind == "population_group" else _admin_situation)(world, actor, options)


def _open_options(world, actor):
    return civic_protest_options(world, actor.id) if actor.kind == "population_group" else ()


def _dissolve_options(world, actor):
    return civic_dissolve_options(world, actor.id) if actor.kind == "population_group" else ()


def _refusal_options(world, actor):
    return civic_refusal_options(world, actor) if actor.kind != "population_group" else ()


def _open_causes(world, option):
    return (option.report_event_id,)


def _terminal_causes(world, option):
    """Dissolve cites the protest's own last event; refuse cites the notice
    that told this administrator about it -- the same option class serves
    both, distinguished only by ``kind``."""
    if option.kind == "dissolve":
        protest = world.society.civic_protests.get(option.protest_id)
        return (protest.last_event_id,) if protest is not None else ()
    notice = next((item for item in world.knowledge.civic_demands_for_actor(option.actor_ref)
                  if item.protest_id == option.protest_id), None)
    return (notice.event_id,) if notice is not None else ()


def civic_actors(world):
    """Groups that could raise or end their own demand, plus administrators
    that actually received one; both only when an option currently exists."""
    groups = (EntityRef("population_group", group_id) for group_id in sorted(world.society.population)
             if civic_protest_options(world, group_id) or civic_dissolve_options(world, group_id))
    admins = (actor for actor in sorted({item.recipient_ref for item in world.knowledge.civic_demand_notices.values()},
                                        key=lambda ref: (ref.kind, ref.id))
             if civic_refusal_options(world, actor))
    return sorted({*groups, *admins}, key=lambda ref: (ref.kind, ref.id))


def civic_adapters(on_executed=None):
    """The family's adapters; ``on_executed`` only reports that a material
    civic action actually ran, for the standalone caller's boolean contract."""
    def _executed():
        if on_executed is not None:
            on_executed()

    def _execute_open(world, actor, option_id, decision_event_id):
        open_civic_protest(world, actor.id, option_id, decision_event_id)
        _executed()

    def _execute_dissolve(world, actor, option_id, decision_event_id):
        dissolve_civic_protest(world, actor.id, option_id, decision_event_id)
        _executed()

    def _execute_refuse(world, actor, option_id, decision_event_id):
        refuse_civic_demand(world, actor, option_id, decision_event_id)
        _executed()

    def _adapter(name, options_fn, causes_fn, execute_fn):
        return DiscretionaryAdapter(name=name, family="civic", options_fn=options_fn,
                                    label_fn=lambda option: _LABELS[option.decision()["action"]],
                                    causes_fn=causes_fn, execute_fn=execute_fn, situation_fn=_situation)

    return (_adapter("civic_open", _open_options, _open_causes, _execute_open),
            _adapter("civic_dissolve", _dissolve_options, _terminal_causes, _execute_dissolve),
            _adapter("civic_refuse", _refusal_options, _terminal_causes, _execute_refuse))


async def review_civic_protests_with_provider(world):
    """Give each actor at most one current civic turn in this review.

    Options are built from current local readings and delivered notices only.
    Provider mode deliberately has no deterministic fallback.
    """
    changed = {"value": False}
    adapters = civic_adapters(on_executed=lambda: changed.__setitem__("value", True))
    await review_institutional_decision_turn_with_provider(
        world, adapters, actors=_rotated(world, civic_actors(world)), situation_fn=_situation)
    return changed["value"]


__all__ = ["review_civic_protests_with_provider", "civic_adapters", "civic_actors"]

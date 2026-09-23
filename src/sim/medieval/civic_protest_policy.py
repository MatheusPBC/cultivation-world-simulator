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
from .institutional_memory import institutional_views
from .civic_tumult import TUMULT_ACTION, civic_tumult_options, execute_civic_tumult
from .civic_movement import (MOVEMENT_ACTION, JOIN_MOVEMENT_ACTION, civic_movement_dissolve_options,
                             civic_movement_options, dissolve_civic_movement,
                             civic_movement_join_options, join_civic_movement,
                             form_civic_movement, REBELLION_ACTION,
                             civic_rebellion_options, declare_civic_rebellion,
                             SUPPRESS_REBELLION_ACTION, civic_rebellion_response_options,
                             respond_civic_rebellion,
                             OFFER_NEGOTIATION_ACTION, REVOLUTION_ACTION,
                             civic_revolution_options, declare_civic_revolution)
from .civic_strike import (STRIKE_ACTION, civic_general_strike_options,
                           start_general_strike)
from .civic_amnesty import (AMNESTY_ACTION, civic_amnesty_options,
                            grant_civic_amnesty)

_LABELS = {
    OPEN_ACTION: "Abrir uma demanda cívica local usando o relatório observado.",
    DISSOLVE_ACTION: "Dissolver a própria demanda cívica.",
    REFUSE_ACTION: "Recusar a demanda cívica recebida.",
    TUMULT_ACTION: "Participar de um tumulto local contra uma instalação observada.",
    MOVEMENT_ACTION: "Formar um movimento cívico com outros grupos locais observados.",
    JOIN_MOVEMENT_ACTION: "Entrar voluntariamente em um movimento cívico observado.",
    "dissolve_civic_movement": "Encerrar o movimento cívico e liberar os participantes.",
    STRIKE_ACTION: "Iniciar uma greve geral limitada com os grupos do movimento.",
    REBELLION_ACTION: "Declarar uma rebelião organizada contra a administração local.",
    SUPPRESS_REBELLION_ACTION: "Suprimir uma rebelião sob autoridade militar local.",
    OFFER_NEGOTIATION_ACTION: "Oferecer negociação ao movimento organizado.",
    "accept_civic_negotiation": "Aceitar a negociação e encerrar o movimento.",
    REVOLUTION_ACTION: "Declarar uma revolução após uma rebelião persistente.",
    AMNESTY_ACTION: "Conceder anistia formal após uma negociação cívica aceita.",
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
        "strike_targets": [item.id for item in options if ":organized_strike:" in item.id],
        "tumult_targets": [item.id for item in options if item.id.startswith("civic-tumult:")],
        "movement_targets": [item.id for item in options if item.id.startswith("civic-movement:")],
        "movement_join_targets": [item.id for item in options if item.id.startswith("civic-movement-join:")],
        "general_strike_targets": [item.id for item in options if item.id.startswith("civic-strike:")],
        "rebellion_targets": [item.id for item in options if item.id.startswith("civic-rebellion:")],
        "revolution_targets": [item.id for item in options if item.id.startswith("civic-revolution:")],
        "today": world.clock.absolute_day,
    }


def _admin_situation(world, actor, options):
    notices = {item.protest_id: item for item in world.knowledge.civic_demands_for_actor(actor)}
    return {
        "you_are": actor.to_dict(),
        "demands_received": [
            {"protest_id": notice.protest_id, "settlement_id": notice.settlement_id,
             "demand_kind": notice.demand_kind, "due_day": notice.due_day}
            for item in options if (notice := notices.get(getattr(item, "protest_id", None))) is not None
        ],
        "rebellion_targets": [item.id for item in options if item.id.startswith("civic-rebellion-suppress:")],
        "negotiation_targets": [item.id for item in options if item.id.startswith("civic-rebellion-negotiate:")],
        "amnesty_targets": [item.id for item in options if item.id.startswith("civic-amnesty:")],
        # This is a read-only, privacy-filtered view.  It gives the
        # administrator the institutional history it already knows without
        # turning memory into a hidden planner or a material score.
        "institutional_memory": [
            {"institution_ref": subject.to_dict(), "reading": reading,
             "event_ids": list(event_ids)}
            for subject, reading, event_ids in institutional_views(world, actor)
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


def _tumult_options(world, actor):
    return civic_tumult_options(world, actor.id) if actor.kind == "population_group" else ()


def _movement_options(world, actor):
    return civic_movement_options(world, actor.id) if actor.kind == "population_group" else ()


def _movement_dissolve_options(world, actor):
    return civic_movement_dissolve_options(world, actor.id) if actor.kind == "population_group" else ()


def _movement_join_options(world, actor):
    return civic_movement_join_options(world, actor.id) if actor.kind == "population_group" else ()


def _strike_options(world, actor):
    return civic_general_strike_options(world, actor.id) if actor.kind == "population_group" else ()


def _rebellion_options(world, actor):
    return civic_rebellion_options(world, actor.id) if actor.kind == "population_group" else ()


def _revolution_options(world, actor):
    return civic_revolution_options(world, actor.id) if actor.kind == "population_group" else ()


def _rebellion_response_options(world, actor):
    return civic_rebellion_response_options(world, actor) if actor.kind == "polity" else ()


def _amnesty_options(world, actor):
    return civic_amnesty_options(world, actor) if actor.kind == "polity" else ()


def _open_causes(world, option):
    return (option.report_event_id,)


def _tumult_causes(world, option):
    return (option.report_event_id, option.site_report_event_id, option.refusal_event_id)


def _movement_causes(world, option):
    return (option.catalyst_event_id, *option.report_event_ids)


def _movement_dissolve_causes(world, option):
    movement = world.society.civic_movements.get(option.movement_id)
    return (movement.last_event_id,) if movement is not None else ()


def _movement_join_causes(world, option):
    movement = world.society.civic_movements.get(option.movement_id)
    return (movement.last_event_id, option.report_event_id) if movement is not None else (option.report_event_id,)


def _strike_causes(world, option):
    movement = world.society.civic_movements.get(option.movement_id)
    return (movement.last_event_id, *option.report_event_ids) if movement is not None else option.report_event_ids


def _rebellion_causes(world, option):
    return (option.mobilization_event_id, option.report_event_id)


def _revolution_causes(world, option):
    return (option.rebellion_event_id, option.mobilization_event_id, option.report_event_id)


def _rebellion_response_causes(world, option):
    movement = world.society.civic_movements.get(option.movement_id)
    return (movement.last_event_id, option.report_event_id) if movement is not None else (option.report_event_id,)


def _amnesty_causes(world, option):
    return (option.negotiation_event_id, option.report_event_id)


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
             if civic_protest_options(world, group_id) or civic_dissolve_options(world, group_id)
             or civic_tumult_options(world, group_id) or civic_movement_options(world, group_id)
             or civic_movement_join_options(world, group_id)
             or civic_movement_dissolve_options(world, group_id)
             or civic_general_strike_options(world, group_id)
             or civic_rebellion_options(world, group_id)
             or civic_revolution_options(world, group_id))
    admin_ids = {item.recipient_ref for item in world.knowledge.civic_demand_notices.values()}
    admin_ids.update(EntityRef("polity", settlement.administrator_id)
                     for settlement in world.society.settlements.values()
                     if settlement.administrator_id is not None)
    admins = (actor for actor in sorted(admin_ids, key=lambda ref: (ref.kind, ref.id))
             if civic_refusal_options(world, actor) or civic_rebellion_response_options(world, actor)
             or civic_amnesty_options(world, actor))
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

    def _execute_tumult(world, actor, option_id, decision_event_id):
        execute_civic_tumult(world, actor.id, option_id, decision_event_id)
        _executed()

    def _execute_movement(world, actor, option_id, decision_event_id):
        form_civic_movement(world, actor.id, option_id, decision_event_id)
        _executed()

    def _execute_movement_dissolve(world, actor, option_id, decision_event_id):
        dissolve_civic_movement(world, actor.id, option_id, decision_event_id)
        _executed()

    def _execute_movement_join(world, actor, option_id, decision_event_id):
        join_civic_movement(world, actor.id, option_id, decision_event_id)
        _executed()

    def _execute_strike(world, actor, option_id, decision_event_id):
        start_general_strike(world, actor.id, option_id, decision_event_id)
        _executed()

    def _execute_rebellion(world, actor, option_id, decision_event_id):
        declare_civic_rebellion(world, actor.id, option_id, decision_event_id)
        _executed()

    def _execute_revolution(world, actor, option_id, decision_event_id):
        declare_civic_revolution(world, actor.id, option_id, decision_event_id)
        _executed()

    def _execute_rebellion_response(world, actor, option_id, decision_event_id):
        respond_civic_rebellion(world, actor, option_id, decision_event_id)
        _executed()

    def _execute_amnesty(world, actor, option_id, decision_event_id):
        grant_civic_amnesty(world, actor, option_id, decision_event_id)
        _executed()

    def _adapter(name, options_fn, causes_fn, execute_fn):
        return DiscretionaryAdapter(name=name, family="civic", options_fn=options_fn,
                                    label_fn=lambda option: _LABELS[option.decision()["action"]],
                                    causes_fn=causes_fn, execute_fn=execute_fn, situation_fn=_situation)

    return (_adapter("civic_open", _open_options, _open_causes, _execute_open),
            _adapter("civic_dissolve", _dissolve_options, _terminal_causes, _execute_dissolve),
            _adapter("civic_refuse", _refusal_options, _terminal_causes, _execute_refuse),
            _adapter("civic_tumult", _tumult_options, _tumult_causes, _execute_tumult),
            _adapter("civic_movement", _movement_options, _movement_causes, _execute_movement),
            _adapter("civic_movement_dissolve", _movement_dissolve_options,
                     _movement_dissolve_causes, _execute_movement_dissolve),
            _adapter("civic_movement_join", _movement_join_options,
                     _movement_join_causes, _execute_movement_join),
            _adapter("civic_general_strike", _strike_options, _strike_causes, _execute_strike),
            _adapter("civic_rebellion", _rebellion_options, _rebellion_causes, _execute_rebellion),
            _adapter("civic_revolution", _revolution_options, _revolution_causes, _execute_revolution),
            _adapter("civic_rebellion_response", _rebellion_response_options,
                     _rebellion_response_causes, _execute_rebellion_response),
            _adapter("civic_amnesty", _amnesty_options, _amnesty_causes, _execute_amnesty))


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

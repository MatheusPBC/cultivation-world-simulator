"""Provider turn for the bounded civic-demand vertical.

This module only gives a real actor a turn over already materialized civic
affordances.  The protest owner remains :mod:`civic_protest`; this policy
records the actor decision and delegates execution back to that owner.
"""

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef

from . import ai_decider
from .civic_protest import (DISSOLVE_ACTION, OPEN_ACTION, REFUSE_ACTION,
                             civic_dissolve_options, civic_protest_options,
                             civic_refusal_options, dissolve_civic_protest,
                             open_civic_protest, refuse_civic_demand)
from .events import record_event


def _decide(world, option, *, causes):
    return record_event(
        world,
        "civic_protest_decided",
        "Um ator escolheu uma affordance cívica válida.",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(),
        cause_ids=tuple(causes),
    )


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


def _labels(options):
    labels = {
        OPEN_ACTION: "Abrir uma demanda cívica local usando o relatório observado.",
        DISSOLVE_ACTION: "Dissolver a própria demanda cívica.",
        REFUSE_ACTION: "Recusar a demanda cívica recebida.",
    }
    return [{"id": item.id, "label": labels[item.decision()["action"]]} for item in options]


async def _turn(world, actor, options, *, causes, situation):
    selected = await ai_decider.select_option(world, actor, situation, _labels(options), causes=causes)
    if selected in (None, ai_decider.NO_ACTION):
        return False
    current = next((item for item in options if item.id == selected), None)
    if current is None:
        return False
    decision = _decide(world, current, causes=causes)
    action = current.decision()["action"]
    try:
        if action == OPEN_ACTION:
            open_civic_protest(world, actor.id, current.id, decision.id)
        elif action == DISSOLVE_ACTION:
            dissolve_civic_protest(world, actor.id, current.id, decision.id)
        elif action == REFUSE_ACTION:
            refuse_civic_demand(world, actor, current.id, decision.id)
        else:
            return False
    except ValueError:
        # The option is re-composed in the owner immediately before execution;
        # an obsolete selection can therefore never mutate canonical state.
        return False
    return True


async def review_civic_protests_with_provider(world):
    """Give each actor at most one current civic turn in this review.

    Options are built from current local readings and delivered notices only.
    Provider mode deliberately has no deterministic fallback.
    """
    if not world.config.ai_enabled:
        return False
    consulted = set()
    changed = False
    groups = []
    for group_id in sorted(world.society.population):
        actor = EntityRef("population_group", group_id)
        options = (*civic_protest_options(world, group_id), *civic_dissolve_options(world, group_id))
        if options:
            groups.append((actor, options))
    for actor, options in groups:
        if actor in consulted:
            continue
        consulted.add(actor)
        causes = tuple(sorted({*(item.report_event_id for item in options if hasattr(item, "report_event_id")),
                               *(world.society.civic_protests[item.protest_id].last_event_id
                                 for item in options if hasattr(item, "protest_id")
                                 and item.protest_id in world.society.civic_protests)}))
        changed |= await _turn(world, actor, options, causes=causes,
                               situation=_group_situation(world, actor, options))

    admins = sorted({item.recipient_ref for item in world.knowledge.civic_demand_notices.values()},
                    key=lambda ref: (ref.kind, ref.id))
    for actor in admins:
        if actor in consulted:
            continue
        options = civic_refusal_options(world, actor)
        if not options:
            continue
        consulted.add(actor)
        causes = tuple(sorted({item.event_id for item in world.knowledge.civic_demands_for_actor(actor)
                               if item.protest_id in {option.protest_id for option in options}}))
        changed |= await _turn(world, actor, options, causes=causes,
                               situation=_admin_situation(world, actor, options))
    return changed


__all__ = ["review_civic_protests_with_provider"]

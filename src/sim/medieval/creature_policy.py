"""Turn-taking for the drake and the institutions it addresses.

This is orchestration, not drama: it only decides *when* someone may choose,
never what they choose. Every choice comes from options the engine already
composed, and a provider that is disabled, unavailable, over budget, failing or
wrong simply produces no action — the drake is never moved by a routine.
"""

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.systems.calendar_agenda import ScheduledSituation

from .ai_decider import NO_ACTION, ProviderDecisionRequired, select_option
from .creatures import (creature_options, execute_creature_option, offer_creature_tribute,
                        tribute_options)
from .events import record_event

REVIEW_KIND = "creature_review"


def review_id(creature_id, day):
    return f"creature-review:{creature_id}:{day}"


def schedule_review(world, creature_id, day):
    """One concrete dated review for one creature; deadlines decide nothing."""
    identity = review_id(creature_id, day)
    if day > world.clock.absolute_day and world.agenda.get(identity) is None:
        world.agenda.schedule(ScheduledSituation(identity, REVIEW_KIND, day))


def _decide(world, option, event_type, content, *, cause_ids):
    """A material decision cites the factual notice/perception, never its LLM receipt."""
    return record_event(world, event_type, content, fact_kind=FactKind.DECISION,
                        causal_origin=CausalOrigin.ACTOR_DECISION, decision=option.decision(),
                        cause_ids=tuple(cause_ids))


def _stale(actor):
    return ProviderDecisionRequired(
        f"provider decision required for {actor.kind}:{actor.id}: creature affordance became stale"
    )


_CREATURE_LABELS = {
    "maintain": "Permanecer como está.",
    "request": "Exigir tributo em alimento para manter a passagem.",
    "restrict": "Fechar a passagem até ser atendido.",
    "withdraw": "Recuar e reabrir a passagem.",
    "damage": "Danificar a instalação aquática ligada à passagem.",
    "attack_population": "Atacar uma coorte anônima ligada à passagem.",
}


async def _creature_turn(world, creature_id):
    creature = world.creatures.creatures.get(creature_id)
    options = creature_options(world, creature_id)
    if creature is None or len(options) <= 1:
        return False
    # The drake knows its own body and what crossed its river; nothing else.
    events = world.event_index()
    remembered = [{"event_id": event.id, "event_type": event.event_type, "day": event.day}
                  for event_id in creature.memory_event_ids
                  if (event := events.get(event_id)) is not None]
    situation = {"you_are": creature.name, "condition": creature.condition,
                 "crossings_you_saw": creature.perceived_crossings,
                 "recent_memory": remembered,
                 "your_open_demands": [{"route_id": item.route_id,
                                        "food_remaining": item.food - item.food_received,
                                        "due_day": item.due_day}
                                       for item in world.creatures.open_demands(creature_id)],
                 "expired_demands": [{"route_id": item.route_id, "due_day": item.due_day}
                                     for item in world.creatures.demands.values()
                                     if item.creature_id == creature_id and item.stage == "open"
                                     and item.due_day < world.clock.absolute_day],
                 "population_targets": [{"group_id": item.population_group_id,
                                         "affected_count": item.population_count}
                                        for item in options if item.kind == "attack_population"],
                 "today": world.clock.absolute_day}
    choices = [{"id": item.id, "label": _CREATURE_LABELS[item.kind]} for item in options]
    selected = await select_option(world, EntityRef("creature", creature_id), situation, choices,
                                   causes=(creature.last_event_id,) if creature.last_event_id else ())
    if selected in (None, NO_ACTION):
        # Silence, provider failure and NO_ACTION leave no autonomous loop.
        # Only a later physical crossing, a newly opened demand's response
        # day, or that demand's deadline may grant another turn.
        return False
    chosen = next((item for item in creature_options(world, creature_id) if item.id == selected), None)
    if chosen is None:
        raise _stale(EntityRef("creature", creature_id))
    factual_cause = (creature.last_event_id,) if creature.last_event_id else ()
    decision = _decide(world, chosen, "creature_decided", "O habitante do rio escolheu entre suas opções.",
                       cause_ids=factual_cause)
    try:
        execute_creature_option(world, creature_id, chosen.id, decision.id)
    except ValueError as exc:
        raise _stale(EntityRef("creature", creature_id)) from exc
    updated = world.creatures.creatures[creature_id]
    if chosen.kind == "request":
        demand = next(item for item in world.creatures.open_demands(creature_id)
                      if item.route_id == chosen.route_id)
        schedule_review(world, creature_id, world.clock.absolute_day + 1)
        schedule_review(world, creature_id, demand.due_day)
    if chosen.kind in {"restrict", "withdraw"}:
        # Administrations learn the passage changed, as a route fact only.
        from .route_intelligence import refresh_route_reports
        refresh_route_reports(world, route_ids=(chosen.route_id,))
    return bool(updated)


async def _tribute_turn(world, actor):
    options = tribute_options(world, actor)
    if not options:
        return False
    notices = {item.demand_id: item for item in world.knowledge.creature_tributes_for_actor(actor)}
    # Its own notice and its own stock; never the creature's hunger or another
    # institution's answer.
    situation = {"you_are": actor.to_dict(), "today": world.clock.absolute_day,
                 "demands_delivered_to_you": [{"route_id": notices[item.demand_id].route_id,
                                               "food_remaining": world.creatures.demands[item.demand_id].food
                                               - world.creatures.demands[item.demand_id].food_received,
                                               "due_day": notices[item.demand_id].due_day}
                                              for item in options if item.demand_id in notices]}
    choices = [{"id": item.id, "label": f"Entregar {item.food} de alimento do próprio estoque."}
               for item in options]
    selected = await select_option(world, actor, situation, choices,
                                   causes=tuple(sorted({notices[item.demand_id].event_id for item in options
                                                        if item.demand_id in notices})))
    if selected in (None, NO_ACTION):
        return False
    chosen = next((item for item in tribute_options(world, actor) if item.id == selected), None)
    if chosen is None:
        raise _stale(actor)
    decision = _decide(world, chosen, "creature_tribute_decided", "A instituição respondeu à exigência do rio.",
                       cause_ids=(notices[chosen.demand_id].event_id,))
    try:
        offer_creature_tribute(world, actor, chosen.id, decision.id)
    except ValueError as exc:
        raise _stale(actor) from exc
    return True


async def review_creatures(world, situations):
    """Run only on a concrete dated review; institutions answer before the drake."""
    creature_ids = tuple(sorted({
        item.id.removeprefix("creature-review:").rsplit(":", 1)[0]
        for item in situations if item.kind == REVIEW_KIND
    }))
    if not creature_ids:
        return
    for identity in sorted(world.society.polities):
        await _tribute_turn(world, EntityRef("polity", identity))
    for creature_id in creature_ids:
        await _creature_turn(world, creature_id)


def note_perception(world, creature):
    """A hungry creature earns one turn from a real new crossing, never hunger alone."""
    # A voiced demand already owns its bounded response/deadline turns.  New
    # crossings remain factual perceptions, but cannot fan out another daily
    # provider agenda while that demand is still open.  Its deadline review is
    # the final post-deadline opportunity; ignored demands stay historical but
    # never reopen a review loop from later cargo.
    if creature.condition < creature.hunger_threshold and not world.creatures.open_demands(creature.id):
        schedule_review(world, creature.id, world.clock.absolute_day + 1)

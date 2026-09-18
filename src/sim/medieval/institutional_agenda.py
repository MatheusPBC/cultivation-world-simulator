"""The single monthly institutional turn, composed from every family.

Civil supply/aid/repair, diplomacy, technique copying, civic demands and
strategic adoption each already expose their own adapters over their own
unchanged executors. This module only unions those adapters and their actor
sets, so one institution answers **one** provider consultation per boundary
across every discretionary domain it currently has, instead of one per
vertical. It adds no executor, no option and no persisted state.

Deliberately outside the monthly turn: anything already in course (an
accepted aid obligation being fulfilled or remediated, a promised teaching
being taught or accepted, an adopted defence plan being executed).

On the DAILY cadence only the recourse turn is composed here
(``review_daily_institutional_turn``): it is genuinely discretionary, keyed
by the acting polity itself, has no cross-actor dependency inside one day,
and keeps its own family context fragment. The other daily verticals keep
their own owners and ordering, each for its own reason: force contact and
campaign supply answer material processes already in course; field aftermath
and strategy-response reviews are keyed per notice/plan, not per actor;
creatures run two dependent phases (institutions answer, then the drake
re-evaluates) inside one day; and the scheduled diplomacy day mixes
discretionary claims with in-course payment and the teacher-before-learner
ordering. Those keep their own owners and their own ordering.
"""

from .civic_protest_policy import civic_actors, civic_adapters
from .concurrent_civil_decision import CIVIL_ADAPTERS
from .diplomacy_policy import diplomacy_actors, diplomacy_adapters
from .institutional_decision_turn import (_rotated, review_institutional_decision_turn,
                                          review_institutional_decision_turn_with_provider)
from .recourse_policy import (REVIEW_KIND as RECOURSE_REVIEW_KIND, recourse_actors,
                              recourse_adapters, schedule_pending_recourse)
from .relief_policy import relief_actors, relief_adapters
from .strategy_response import strategy_adoption_actors, strategy_adoption_adapters
from .technique_copy_policy import technique_copy_actors, technique_copy_adapters

from src.classes.mechanical_language import EntityRef


def monthly_adapters(*, allow_offers=True):
    return (*CIVIL_ADAPTERS, *diplomacy_adapters(allow_offers=allow_offers), *technique_copy_adapters(),
            *relief_adapters(), *civic_adapters(), *strategy_adoption_adapters())


def monthly_actors(world):
    """Every institution any family could offer something to this boundary."""
    actors = {EntityRef("polity", identity) for identity in world.society.polities}
    actors.update(diplomacy_actors(world))
    actors.update(technique_copy_actors(world))
    actors.update(civic_actors(world))
    actors.update(relief_actors(world))
    actors.update(strategy_adoption_actors(world))
    return _rotated(world, sorted(actors, key=lambda ref: (ref.kind, ref.id)))


async def review_monthly_institutional_turn(world, *, allow_offers=True):
    """One consultation per institution across every discretionary family.

    Returns the same ``(claims, covered)`` every turn returns: ``claims`` for
    the deterministic passes that must skip a target already offered, and
    ``covered`` for the policies that must not ask the same institution again
    this boundary.
    """
    return await review_institutional_decision_turn_with_provider(
        world, monthly_adapters(allow_offers=allow_offers), actors=monthly_actors(world))


def daily_adapters(situations):
    return recourse_adapters() if any(item.kind == RECOURSE_REVIEW_KIND for item in situations) else ()


def daily_actors(world, situations):
    if not any(item.kind == RECOURSE_REVIEW_KIND for item in situations):
        return ()
    actors = tuple(sorted(set(recourse_actors(world)), key=lambda actor: (actor.kind, actor.id)))
    if not actors:
        return actors
    offset = world.clock.absolute_day % len(actors)
    return actors[offset:] + actors[:offset]


async def review_daily_institutional_turn(world, situations):
    situations = tuple(situations)
    adapters = daily_adapters(situations)
    if not adapters:
        return {}, set()
    claims, covered = {}, set()
    for actor in daily_actors(world, situations):
        actor_claims, consulted = await review_institutional_decision_turn(world, actor, adapters)
        for kind, identities in actor_claims.items():
            claims.setdefault(kind, set()).update(identities)
        if consulted:
            covered.add(actor)
    schedule_pending_recourse(world)
    return claims, covered


__all__ = ["monthly_actors", "monthly_adapters", "review_monthly_institutional_turn",
           "daily_actors", "daily_adapters", "review_daily_institutional_turn"]

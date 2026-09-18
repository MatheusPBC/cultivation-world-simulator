"""One bounded provider consultation per institution per boundary.

This is not a new executor and not a persisted planner. A caller registers a
tuple of ``DiscretionaryAdapter``s, each wrapping one existing vertical's own
option builder and executor verbatim; this module only recomposes their
options into a single menu, asks the actor once, and dispatches the chosen ID
back to its own adapter's unmodified executor. Nothing about a "supply
objective" or "aid request" is understood here -- only IDs, labels and
causes the adapter already computed.

A technical failure (no budget, no provider, no monthly slots left) means the
actor was never actually consulted, not that it chose to defer: nothing is
claimed, so whatever deterministic safety net a caller still runs for that
target proceeds exactly as if this turn had not existed this boundary. A
provider that was genuinely asked -- and answered, declined explicitly, or
answered badly -- did use its turn, so its options are claimed regardless of
whether an action actually executed.
"""

from dataclasses import dataclass
from typing import Callable

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef

from . import ai_decider
from .actor_dossier import build_actor_dossier
from .events import record_event

DECISION_EVENT_TYPE = "institutional_decision_turn_decided"
# A deliberate refusal is a decision like any other -- no deltas, same
# causes as the menu it answered -- so downstream causal chains (e.g. a
# revolt) can point at "the actor chose not to act" instead of only seeing
# the consultation receipt. A technical failure (never actually asked) must
# never reach this: see ``was_askable`` below.
DECLINED_DECISION_EVENT_TYPE = "institutional_decision_turn_declined"


@dataclass(frozen=True)
class DiscretionaryAdapter:
    """Wraps one existing vertical's own option builder and executor.

    ``claim_fn`` extracts, from one of this adapter's own options, the
    ``(kind, target_id)`` pair a caller uses to skip its own separate
    automatic pass for that same target this boundary. Return ``None`` from
    it when there is no automatic counterpart to skip (e.g. a fresh request
    that has no deterministic fallback of its own).

    ``family`` and ``situation_fn`` only matter when several families share
    one composed turn: each family then contributes its own context fragment
    under its own key, so a merged menu still shows every domain the context
    it always had, and no family's keys can collide with another's. Adapters
    of the same family share one fragment, computed once over their combined
    options.
    """
    name: str
    options_fn: Callable
    label_fn: Callable
    causes_fn: Callable
    execute_fn: Callable
    claim_fn: Callable = lambda option: None
    family: str = ""
    situation_fn: Callable | None = None

    def family_key(self):
        return self.family or self.name


def _rotated(world, items):
    """A fixed order always lets the same item spend the shared daily
    provider budget first; rotating the start each month gives every item a
    turn at the front over time instead. ``items`` must already be sorted."""
    items = tuple(items)
    if not items:
        return items
    offset = (world.clock.absolute_day // 30) % len(items)
    return items[offset:] + items[:offset]


def _rotated_polities(world):
    return _rotated(world, sorted(world.society.polities))


def _by_id(world, actor, adapters):
    options = {}
    for adapter in adapters:
        for option in adapter.options_fn(world, actor):
            options[option.id] = (adapter, option)
    return options


def _claims_of(by_id):
    claims = {}
    for adapter, option in by_id.values():
        claim = adapter.claim_fn(option)
        if claim is not None:
            kind, target_id = claim
            claims.setdefault(kind, set()).add(target_id)
    return claims


def _composed_situation(world, actor, by_id):
    """The generic dossier plus one fragment per family that declared one."""
    situation = build_actor_dossier(world, actor)
    families = {}
    for adapter, option in by_id.values():
        if adapter.situation_fn is not None:
            families.setdefault(adapter.family_key(), (adapter, []))[1].append(option)
    for key, (adapter, options) in sorted(families.items()):
        situation[key] = adapter.situation_fn(world, actor, options)
    return situation


async def review_institutional_decision_turn(world, actor, adapters, *, situation_fn=None):
    """One turn across every registered discretionary family for one actor.

    ``situation_fn(world, actor, options)`` fully replaces what the provider
    sees, for a single-family caller whose options need their own narrower or
    differently-shaped context (e.g. diplomacy's own proposal and obligation
    IDs, never a settlement report or objective). Without it, the composed
    situation is used: the generic actor dossier plus one namespaced fragment
    per family that declared a ``situation_fn`` on its adapters.

    Returns ``(claims, covered)``: ``claims`` maps a claim kind to the target
    IDs this boundary's menu named for it (empty when the actor was never
    actually asked), and ``covered`` is whether it received a menu at all.
    """
    by_id = _by_id(world, actor, adapters)
    if not by_id:
        return {}, False
    was_askable = ai_decider.consultable(world, actor)
    situation = (situation_fn(world, actor, [option for _, option in by_id.values()])
                 if situation_fn is not None else _composed_situation(world, actor, by_id))
    choices = [{"id": option_id, "label": adapter.label_fn(option)}
               for option_id, (adapter, option) in sorted(by_id.items())]
    causes = tuple(sorted({cause for adapter, option in by_id.values() for cause in adapter.causes_fn(world, option)}))
    selected = await ai_decider.select_option(world, actor, situation, choices, causes=causes)
    if selected is None and not was_askable:
        return {}, False
    claims = _claims_of(by_id)
    if selected == ai_decider.NO_ACTION:
        # The actor was genuinely consultable (``was_askable``) and answered
        # NO_ACTION: a deliberate refusal, not a missed turn. Record it as its
        # own zero-delta decision fact, carrying the same dated causes that
        # composed the menu and the affordances it turned down, so a reader
        # (or a downstream causal chain) can see the omission itself, not just
        # ``ai_decision_declined``'s receipt that the consultation happened.
        record_event(
            world, DECLINED_DECISION_EVENT_TYPE,
            "O ator foi consultado e optou por não agir entre as opções institucionais concorrentes.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            decision={"action": "no_action", "actor_ref": actor.to_dict(),
                      "declined_option_ids": tuple(sorted(by_id))},
            cause_ids=causes,
        )
        return claims, True
    if selected is None:
        return claims, True
    # Re-fetch fresh: nothing about the chosen option survives past this
    # point unless it is still present in a freshly recomposed menu.
    fresh = _by_id(world, actor, adapters)
    if selected not in fresh:
        return claims, True
    adapter, option = fresh[selected]
    decision = record_event(
        world, DECISION_EVENT_TYPE, "O ator escolheu entre opções institucionais concorrentes.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(), cause_ids=adapter.causes_fn(world, option),
    )
    try:
        adapter.execute_fn(world, actor, option.id, decision.id)
    except ValueError:
        # The decision remains factual history; a stale affordance never
        # becomes a material mutation.
        pass
    return claims, True


async def review_institutional_decision_turn_with_provider(world, adapters, *, actors=None, situation_fn=None):
    """One review per actor per boundary; no persisted planner or menu state.

    ``actors`` lets a caller whose institutions are not only polities (e.g.
    diplomacy's organizations) supply its own, already-ordered actor list;
    it defaults to every current polity, rotated. ``situation_fn`` is passed
    through to :func:`review_institutional_decision_turn` unchanged.
    """
    claims_totals, covered_actors = {}, set()
    if not world.config.ai_enabled:
        return claims_totals, covered_actors
    if actors is None:
        actors = (EntityRef("polity", identity) for identity in _rotated_polities(world))
    for actor in actors:
        claims, covered = await review_institutional_decision_turn(world, actor, adapters, situation_fn=situation_fn)
        for kind, ids in claims.items():
            claims_totals.setdefault(kind, set()).update(ids)
        if covered:
            covered_actors.add(actor)
    return claims_totals, covered_actors

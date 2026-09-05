"""The one owner of an Avatar's canonical decision audit record.

Two callers commit an action chain for an Avatar: the AI decision boundary
(``phase_decide_actions``) and an accepted player roleplay command
(``roleplay_service``).  Both must produce the *same* kind of fact -- a
``fact_kind=DECISION`` event carrying one ``AgentDecision`` -- differing only
in ``source``, so that everything reading a decision downstream
(``avatar_aggression``, the ``why`` query, the Chronicle) sees one shape and
not two dialects.  This module is that single owner.

It is an audit trail, not a parallel planner: nothing here is ever read back
to decide anything.  ``chosen_chain`` only mirrors the plans that
``load_decide_result_chain`` already queued, and the decision event is
filtered out of timelines and memory by default
(``EventQuery.include_decisions``).  See docs/specs/causal-world-kernel.md
section 5.4.

Building and adopting are deliberately separate.  Building is pure: it
touches no Avatar field, so a caller whose durable write can fail may build
the fact, persist it, and only then adopt it -- no queued plan, emotion or
audit pointer can outlive a failed persistence.  Adoption is the infallible
in-memory step that makes the fact the Avatar's current decision.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from typing import Any

from src.classes.agent_decision import AgentDecision
from src.classes.action_runtime import ActionOrigin
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.i18n import t
from src.utils.params import filter_kwargs_for_callable

# ``AgentDecision.source`` values this module may write.  They mirror
# ``single_choice.ChoiceSource``: an autonomous LLM decision, and a decision
# the player authored by direct command while roleplaying an Avatar.
DECISION_SOURCE_LLM = "llm"
DECISION_SOURCE_PLAYER = "player"


class ActionChainRejected(Exception):
    """An offered action chain is not acceptable as a decision.

    ``reason`` is a translated, user-facing sentence: the player is the one
    who has to correct the command, so the rejection has to say what is
    wrong with it.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _parse_step(item: Any) -> tuple[str, dict[str, Any]] | None:
    """One well-formed step, or None if the entry is malformed.

    The two shapes a model actually returns are accepted -- ``[name, params]``
    and ``{"action_name": ..., "action_params": ...}``.  ``null`` params mean
    "no arguments" and become an empty dict, because that is the one thing a
    model omitting arguments genuinely means.  Any other non-mapping params
    value (a number, a string, a list) is malformed and is *not* silently
    turned into an empty dict: doing so would quietly convert nonsense into a
    different, executable command.
    """

    if isinstance(item, Mapping):
        if "action_name" not in item or "action_params" not in item:
            return None
        name, params = item["action_name"], item["action_params"]
    elif isinstance(item, (list, tuple)) and len(item) == 2:
        name, params = item[0], item[1]
    else:
        return None
    if not isinstance(name, str) or not name:
        return None
    if params is None:
        return name, {}
    if isinstance(params, Mapping):
        return name, dict(params)
    return None


def parse_action_chain(payload: Any) -> list[tuple[str, dict[str, Any]]]:
    """Normalise a raw ``action_name_params_pairs`` payload, dropping junk.

    Shape normalisation only: whether the named actions exist, are available
    or carry the right arguments is decided elsewhere, against the action
    registry and the offered catalogue.  Malformed entries are skipped, which
    is what the autonomous decision path has always done -- an empty result
    simply means this Avatar produced no decision this month.
    """

    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        return []
    steps = (_parse_step(item) for item in payload)
    return [step for step in steps if step is not None]


def parse_player_action_chain(payload: Any) -> list[tuple[str, dict[str, Any]]]:
    """The same normalisation, but a malformed entry is a refusal.

    A player command is accepted or refused as a whole.  Dropping one
    unreadable step would accept a *different* command than the one that was
    interpreted, so anything unreadable refuses the submission instead.
    """

    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ActionChainRejected(
            t("Failed to generate a valid action plan from this command")
        )
    pairs: list[tuple[str, dict[str, Any]]] = []
    for item in payload:
        step = _parse_step(item)
        if step is None:
            raise ActionChainRejected(
                t("Failed to generate a valid action plan from this command")
            )
        pairs.append(step)
    return pairs


def offered_actions(avatar: Any) -> dict[str, Any]:
    """The action catalogue this Avatar was actually offered.

    The same catalogue that goes into the decision prompt and that
    ``considered_count`` counts, so "was this action on the menu" is answered
    by the menu itself instead of by a second availability engine.
    """

    from src.classes.actions import get_action_infos

    return get_action_infos(avatar)


def _required_declared_arguments(action: Any, declared: set[str]) -> set[str]:
    """Declared parameters this action cannot even be asked about without.

    Read off ``can_start``'s own signature, intersected with the action's
    declared ``PARAMS``: a required signature parameter that the action never
    declares is an inconsistency in the action itself, not something a
    command could have supplied, so it must not refuse the command.
    """

    try:
        signature = inspect.signature(action.can_start)
    except (TypeError, ValueError):
        return set()
    return {
        name
        for name, parameter in signature.parameters.items()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        and name in declared
    }


def validate_player_action_chain(
    avatar: Any,
    action_name_params_pairs: Sequence[tuple[str, Mapping[str, Any]]],
    *,
    offered: Mapping[str, Any],
) -> None:
    """Accept a player-authored chain, or say precisely why it is refused.

    Every check is delegated to the component that owns the answer, and none
    of them executes the action:

    * the action must be in the catalogue the Avatar was offered, so an
      invented name and an action this Avatar could never perform are both
      out;
    * every parameter key must be one the action class itself declares in
      ``PARAMS``, so a plausible-looking but unparseable parameter cannot be
      queued;
    * every declared parameter that ``can_start`` requires must be present,
      read off that callable's own signature.  This is argument binding, not
      a precondition: it refuses ``Attack`` with no target, and says nothing
      about whether a target is reachable;
    * the *first* step must pass its own ``can_start`` right now.  That step
      is the immediate boundary: the world is paused exactly as the player
      saw it, so refusing it here is honest.  Later steps are deliberately
      never checked for material preconditions -- a ``Move`` followed by an
      ``Attack`` on a target currently out of range is a legitimate plan --
      and each is revalidated by ``commit_next_plan`` when it is actually
      committed.

    A shape rejection reuses the existing "no valid plan" sentence rather
    than minting new user-facing strings; a first-step rejection carries the
    action's own already-translated reason, which is more specific than
    anything this module could invent.
    """

    if not action_name_params_pairs:
        raise ActionChainRejected(
            t("Failed to generate a valid action plan from this command")
        )
    for action_name, params in action_name_params_pairs:
        if action_name not in offered:
            raise ActionChainRejected(
                t("Failed to generate a valid action plan from this command")
            )
        action = avatar.create_action(action_name)
        declared = set(getattr(type(action), "PARAMS", {}) or {})
        if set(params) - declared:
            raise ActionChainRejected(
                t("Failed to generate a valid action plan from this command")
            )
        if _required_declared_arguments(action, declared) - set(params):
            raise ActionChainRejected(
                t("Failed to generate a valid action plan from this command")
            )

    first_name, first_params = action_name_params_pairs[0]
    action = avatar.create_action(first_name)
    can_start, reason = action.can_start(
        **filter_kwargs_for_callable(action.can_start, dict(first_params))
    )
    if not can_start:
        raise ActionChainRejected(
            str(reason) or t("Failed to generate a valid action plan from this command")
        )


def build_avatar_decision_event(
    world: Any,
    avatar: Any,
    action_name_params_pairs: Sequence[tuple[str, Mapping[str, Any]]],
    avatar_thinking: str,
    short_term_objective: str,
    *,
    source: str,
    offered: Mapping[str, Any],
) -> Event:
    """The audit fact for one committed decision.  Pure: mutates nothing.

    ``causal_origin`` stays ``LLM_INTERPRETATION`` for a player command too:
    a human authored the intent, but the concrete engine steps recorded here
    were still written by a model reading free text.  Who decided is stated
    by ``AgentDecision.source``, which is the field every reader checks.
    """

    decision = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="avatar",
        subject_id=str(avatar.id),
        source=source,
        considered_count=len(offered),
        chosen_chain=[
            {"action_name": name, "params": dict(params)}
            for name, params in action_name_params_pairs
        ],
        thinking=avatar_thinking,
        short_term_objective=short_term_objective,
    )
    return Event(
        world.month_stamp,
        t("{avatar} committed to an action chain", avatar=avatar.name),
        related_avatars=[avatar.id],
        is_major=False,
        is_story=False,
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        causal_payload={"deltas": [], "decision": decision.to_dict()},
    )


def adopt_avatar_decision(avatar: Any, event: Event) -> None:
    """Make a built decision fact this Avatar's current decision.

    Runtime identity only: one decision may span several months of queued
    plans (see ``commit_next_plan``), and these two fields are never saved,
    so a restored save carries no decision and therefore fails closed.
    """

    avatar.current_decision_event_id = event.id
    avatar._current_decision_payload = event.causal_payload


def committed_decision_event_id(
    avatar: Any,
    *,
    action_name: str,
    params: Mapping[str, Any],
    action_origin: ActionOrigin | str,
) -> str | None:
    """The actor's own audited decision, only if it really chose *this* action.

    Two independent witnesses, neither of which prose or an LLM parameter can
    forge, and both required:

    * the engine wrote ``ACTOR_CHOICE`` onto the committed action.  A
      pre-empted fallback, a mutual-action response and a restored save all
      carry the fail-closed ``REACTIVE_RESPONSE`` value;
    * the live decision payload -- the audit record adopted at the decision
      boundary -- actually contains this exact step for this exact subject.
      A decision that chose something else cannot be relabelled, and an
      Avatar carrying no audit at all attributes nothing.

    The live payload is read rather than the event store because a decision
    made in this same step is not queryable yet.  Returning ``None`` is the
    normal, safe outcome: the consequence simply stays unattributed.
    """

    if ActionOrigin(action_origin) is not ActionOrigin.ACTOR_CHOICE:
        return None
    event_id = str(getattr(avatar, "current_decision_event_id", "") or "")
    payload = getattr(avatar, "_current_decision_payload", None)
    if not event_id.strip() or not isinstance(payload, Mapping):
        return None
    decision = payload.get("decision")
    if not isinstance(decision, Mapping):
        return None
    if str(decision.get("subject_kind", "")) != "avatar" or str(
        decision.get("subject_id", "")
    ) != str(getattr(avatar, "id", "")):
        return None
    expected = dict(params)
    for step in decision.get("chosen_chain") or []:
        if not isinstance(step, Mapping) or str(step.get("action_name", "")) != str(action_name):
            continue
        step_params = step.get("params")
        if isinstance(step_params, Mapping) and dict(step_params) == expected:
            return event_id
    return None


def attach_validated_actor_decision(
    event: Event,
    avatar: Any,
    *,
    action_name: str,
    params: Mapping[str, Any],
    action_origin: ActionOrigin | str,
) -> str | None:
    """Attribute a material consequence to the decision that actually chose it.

    Deliberately stricter than attaching whatever ``current_decision_event_id``
    happens to hold: an unproved consequence is left exactly as it was, still
    a true fact but with no author, rather than credited to a decision that
    did not choose it.  Returns the cited decision id, or ``None`` when the
    consequence stays unattributed.
    """

    decision_event_id = committed_decision_event_id(
        avatar, action_name=action_name, params=params, action_origin=action_origin
    )
    if decision_event_id is None:
        return None
    event.causal_origin = CausalOrigin.ACTOR_DECISION
    if not any(
        link.cause_event_id == decision_event_id
        and link.relation is CausalRelation.MOTIVATED_BY
        for link in event.causal_links
    ):
        event.causal_links.append(
            CausalLink(
                event_id=event.id,
                cause_event_id=decision_event_id,
                relation=CausalRelation.MOTIVATED_BY,
            )
        )
    payload = dict(event.causal_payload or {})
    payload.setdefault("deltas", [])
    payload["decision_source"] = {
        "kind": "avatar_action",
        "action_name": str(action_name),
        "avatar_id": str(getattr(avatar, "id", "")),
        "decision_event_id": decision_event_id,
    }
    event.causal_payload = payload
    return decision_event_id


__all__ = [
    "ActionChainRejected",
    "DECISION_SOURCE_LLM",
    "DECISION_SOURCE_PLAYER",
    "adopt_avatar_decision",
    "attach_validated_actor_decision",
    "build_avatar_decision_event",
    "committed_decision_event_id",
    "offered_actions",
    "parse_action_chain",
    "parse_player_action_chain",
    "validate_player_action_chain",
]

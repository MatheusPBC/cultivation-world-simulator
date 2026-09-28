"""Dated medieval facts using the fork's existing causal links and state deltas."""

from dataclasses import replace
import json
from typing import Any

from pydantic import Field, model_validator

from src.classes.causal_link import CausalLink
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.society.models import Count, Identity, SocietyValue
from src.classes.state_delta import StateDelta


class WorldEvent(SocietyValue):
    id: Identity
    day: Count
    sequence: int = Field(strict=True, ge=1)
    event_type: Identity
    content: str
    fact_kind: FactKind = FactKind.OCCURRENCE
    causal_origin: CausalOrigin = CausalOrigin.DETERMINISTIC
    decision: dict[str, Any] | None = None
    # Structured engine evidence used by read models and Why navigation.  It
    # is part of the canonical event contract, not a transient runtime
    # attribute: otherwise model_dump/save-load silently discarded ecology,
    # hazard and owner evidence attached after the event was created.
    causal_payload: dict[str, Any] | None = None
    deltas: tuple[StateDelta, ...] = ()
    causal_links: tuple[CausalLink, ...] = ()

    def __eq__(self, other):
        """Compare event payloads by their JSON-shaped canonical values.

        Decisions are deliberately open structured data.  An event created in
        memory may contain tuples while the same event loaded from JSON must
        contain lists; those are the same causal payload and must not make
        save/load continuation look different.  Keep the original payload
        shapes untouched for executors and normalize only at the equality
        boundary used by history verification.
        """
        if not isinstance(other, WorldEvent):
            return NotImplemented
        return _canonical_value(self.model_dump(mode="python")) == _canonical_value(
            other.model_dump(mode="python")
        )

    def __deepcopy__(self, memo=None):
        # Frozen outer models still contain mutable dicts and dataclasses. Rebuild
        # independent values through the canonical wire shape instead of sharing
        # them, or recursing through Pydantic/dataclass internals in Python.
        # Python mode preserves nonfinite floats so strict JSON can reject them;
        # JSON mode would normalize them to null before this check.
        payload = json.dumps(self.model_dump(mode="python", warnings="error"), allow_nan=False)
        cloned = type(self).model_validate_json(payload)
        if memo is not None:
            memo[id(self)] = cloned
        return cloned

    @model_validator(mode="after")
    def validate_causal_shape(self):
        if self.id != f"event:{self.sequence}":
            raise ValueError("event ID must match its sequence")
        if self.fact_kind == FactKind.DECISION:
            if self.deltas or self.decision is None:
                raise ValueError("decision requires an intent and cannot apply deltas")
        elif self.decision is not None:
            raise ValueError("only a decision may carry intent")
        if self.deltas and self.fact_kind != FactKind.STATE_TRANSITION:
            raise ValueError("only state transitions can carry material deltas")
        if self.fact_kind == FactKind.STATE_TRANSITION and not self.deltas:
            raise ValueError("a state transition requires at least one material delta")
        if self.deltas and self.causal_origin == CausalOrigin.LLM_INTERPRETATION:
            raise ValueError("an interpretation cannot carry a state change")
        if self.causal_origin == CausalOrigin.ACTOR_DECISION and self.deltas:
            payload = self.causal_payload
            if (not isinstance(payload, dict)
                    or not isinstance(payload.get("decision_event_id"), str)
                    or not isinstance(payload.get("actor_ref"), dict)
                    or not isinstance(payload.get("selected_affordance_id"), str)):
                raise ValueError("actor state transition requires causal authorship payload")
        if self.causal_origin == CausalOrigin.LLM_INTERPRETATION:
            payload_deltas = self.causal_payload.get("deltas") if self.causal_payload else None
            if payload_deltas:
                raise ValueError("an interpretation cannot carry state deltas in its causal payload")
        for index, delta in enumerate(self.deltas):
            if (delta.event_id != self.id or delta.id != f"{self.id}:delta:{index}"
                    or not delta.owner_kind or not delta.owner_id or not delta.aspect):
                raise ValueError("invalid delta owner or event reference")
        for index, link in enumerate(self.causal_links):
            if link.event_id != self.id or link.id != f"{self.id}:cause:{index}":
                raise ValueError("invalid causal link event reference")
        return self


def _canonical_value(value):
    if isinstance(value, dict):
        return tuple(sorted((key, _canonical_value(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_canonical_value(item) for item in value)
    if isinstance(value, FactKind):
        return value.value
    if isinstance(value, CausalOrigin):
        return value.value
    if isinstance(value, float) and value == 0.0:
        return 0.0
    return value


def _interprets(event) -> bool:
    return event.causal_origin == CausalOrigin.LLM_INTERPRETATION


def validate_history(events, day: int, *, from_sequence: int = 1) -> None:
    """Validate the ledger, optionally checking only an appended suffix.

    Persistence and audit callers use the default full scan.  The transactional
    engine may validate only events appended to its isolated candidate because
    the prior prefix was validated at the previous commit.  Cause IDs still
    resolve against the complete ledger, so causal and interpretation-origin
    rules remain enforced for every new event.
    """
    if type(from_sequence) is not int or not 1 <= from_sequence <= len(events) + 1:
        raise ValueError("event history suffix must start inside the ledger")
    previous_day = events[from_sequence - 2].day if from_sequence > 1 else 0
    for index, event in enumerate(events[from_sequence - 1:], start=from_sequence):
        event = WorldEvent.model_validate(event.model_dump(mode="json"))
        if event.sequence != index or not previous_day <= event.day <= day:
            raise ValueError("event sequence or date is inconsistent with world clock")
        causes = [link.cause_event_id for link in event.causal_links]
        if len(set(causes)) != len(causes) or any(not _is_recorded(events, cause) for cause in causes):
            raise ValueError("unknown or repeated event cause")
        if any((source := _recorded_event(events, cause)) is not None
               and (source.sequence >= event.sequence or source.day > event.day)
               for cause in causes):
            raise ValueError("causal links must point to an earlier event no later than their effect")
        if (event.fact_kind is FactKind.DECISION
                and event.causal_origin is CausalOrigin.ACTOR_DECISION):
            _validate_actor_decision_source(
                events, decision=event.decision, causal_payload=event.causal_payload,
                cause_ids=causes, decision_sequence=index, decision_day=event.day)
        if (event.causal_origin is CausalOrigin.ACTOR_DECISION
                and event.fact_kind is not FactKind.DECISION):
            if not any((_cause := _recorded_event(events, cause)) is not None
                       and _cause.fact_kind is FactKind.DECISION
                       and _cause.causal_origin is CausalOrigin.ACTOR_DECISION
                       and _cause.decision is not None
                       and _cause.sequence < event.sequence and _cause.day == event.day
                       for cause in causes):
                raise ValueError("actor-authored event requires a same-day real decision cause")
            if event.deltas:
                _validate_actor_authorship_payload(
                    events, causal_payload=event.causal_payload, cause_ids=causes,
                    event_day=event.day, event_sequence=event.sequence)
        if event.deltas and any((_cause := _recorded_event(events, cause)) is not None
                                and _interprets(_cause) for cause in causes):
            raise ValueError("a state change cannot be caused directly by an interpretation")
        previous_day = event.day


def _is_recorded(events, cause_id) -> bool:
    # Canonical IDs name their own position, so a cause is checked against the
    # single event it could be instead of rescanning the whole history.
    if not isinstance(cause_id, str):
        return False
    prefix, separator, sequence = cause_id.partition(":")
    if prefix != "event" or not separator or not sequence.isdecimal():
        return False
    position = int(sequence)
    return 1 <= position <= len(events) and events[position - 1].id == cause_id


def _recorded_event(events, event_id):
    if not _is_recorded(events, event_id):
        return None
    return events[int(event_id.partition(":")[2]) - 1]


def _validate_actor_authorship_payload(events, *, causal_payload, cause_ids,
                                       event_day, event_sequence):
    """Require an actor transition to carry the decision that authored it.

    ``validate_history`` remains the complete-ledger guard, but callers also
    need the invariant before the event is appended.  Otherwise a direct owner
    invocation could briefly publish a material transition whose decision,
    actor, or affordance was never recorded, bypassing the transactional
    rollback boundary used by the monthly engine.
    """
    if not isinstance(causal_payload, dict):
        raise ValueError("actor state transition requires causal authorship payload")
    decision_event_id = causal_payload.get("decision_event_id")
    actor_ref = causal_payload.get("actor_ref")
    selected_affordance_id = causal_payload.get("selected_affordance_id")
    if (not isinstance(decision_event_id, str)
            or not isinstance(actor_ref, dict)
            or not isinstance(selected_affordance_id, str)
            or decision_event_id not in cause_ids):
        raise ValueError("actor state transition has incomplete causal authorship payload")
    decision_source = _recorded_event(events, decision_event_id)
    if (decision_source is None or decision_source.fact_kind is not FactKind.DECISION
            or decision_source.causal_origin is not CausalOrigin.ACTOR_DECISION
            or decision_source.decision is None or decision_source.day != event_day
            or decision_source.sequence >= event_sequence):
        raise ValueError("actor state transition has invalid decision authorship payload")
    if (decision_source.decision.get("actor_ref") != actor_ref
            or decision_source.decision.get("selected_affordance_id") != selected_affordance_id):
        raise ValueError("actor state transition authorship does not match its decision")


def _provider_selection_source(events, decision, *, decision_day):
    """Match the immediately preceding provider receipt to its actor decision."""
    if not events or not isinstance(decision, dict):
        return None
    receipt = events[-1]
    if (receipt.day != decision_day
            or receipt.event_type not in {"ai_decision_interpreted", "ai_decision_declined"}):
        return None
    selection = (receipt.causal_payload or {}).get("selection")
    if not isinstance(selection, dict) or selection.get("actor_ref") != decision.get("actor_ref"):
        return None
    selected_id = selection.get("selected_affordance_id")
    matches = (selected_id == decision.get("selected_affordance_id")
               or selected_id == "NO_ACTION"
               and decision.get("action") in {"no_action", "maintain"})
    if not matches:
        return None
    return receipt


def _validate_actor_decision_source(events, *, decision, causal_payload, cause_ids,
                                    decision_sequence, decision_day):
    """Require an auditable origin for every actor-authored decision fact."""
    source = causal_payload.get("decision_source") if isinstance(causal_payload, dict) else None
    if not isinstance(source, dict) or not isinstance(source.get("kind"), str):
        raise ValueError("actor decision requires a decision source")

    kind = source["kind"]
    if kind == "fallback":
        if any(not isinstance(source.get(field), str) or not source[field].strip()
               for field in ("policy", "rule")):
            raise ValueError("fallback decision source requires policy and rule")
        return
    if kind in {"player", "api"}:
        return
    if kind != "provider":
        raise ValueError("actor decision has an unsupported decision source")

    receipt_id = source.get("receipt_event_id")
    receipt = _recorded_event(events, receipt_id)
    if (not isinstance(receipt_id, str) or receipt_id not in cause_ids or receipt is None
            or receipt.sequence >= decision_sequence
            or receipt.day != decision_day
            or receipt.event_type not in {"ai_decision_interpreted", "ai_decision_declined"}
            or receipt.causal_origin is not CausalOrigin.LLM_INTERPRETATION or receipt.deltas):
        raise ValueError("provider decision source requires a prior causal receipt")
    selection = (receipt.causal_payload or {}).get("selection")
    if not isinstance(decision, dict) or not isinstance(selection, dict):
        raise ValueError("provider decision source does not match an actor selection")
    selected_id = selection.get("selected_affordance_id")
    matches = (selected_id == decision.get("selected_affordance_id")
               or selected_id == "NO_ACTION"
               and decision.get("action") in {"no_action", "maintain"})
    if not matches or selection.get("actor_ref") != decision.get("actor_ref"):
        raise ValueError("provider decision source does not match actor and affordance")


def record_event(world, event_type: str, content: str, *, fact_kind=FactKind.OCCURRENCE,
                 causal_origin=CausalOrigin.DETERMINISTIC, decision=None, causal_payload=None,
                 deltas=(), cause_ids=()) -> WorldEvent:
    if (fact_kind is FactKind.DECISION and causal_origin is CausalOrigin.ACTOR_DECISION
            and isinstance(decision, dict)
            and not (isinstance(causal_payload, dict) and causal_payload.get("decision_source"))):
        receipt = _provider_selection_source(world.events, decision,
                                             decision_day=world.clock.absolute_day)
        if receipt is not None:
            cause_ids = tuple(cause_ids)
            causal_payload = {**(causal_payload or {}),
                              "decision_source": {"kind": "provider", "receipt_event_id": receipt.id}}
            if receipt.id not in cause_ids:
                cause_ids = (*cause_ids, receipt.id)
    sequence = len(world.events) + 1
    event_id = f"event:{sequence}"
    if len(set(cause_ids)) != len(cause_ids) or any(not _is_recorded(world.events, cause) for cause in cause_ids):
        raise ValueError("unknown or repeated event cause")
    if deltas and any(_interprets(world.events[int(cause.partition(":")[2]) - 1]) for cause in cause_ids):
        raise ValueError("a state change cannot be caused directly by an interpretation")
    if fact_kind is FactKind.DECISION and causal_origin is CausalOrigin.ACTOR_DECISION:
        _validate_actor_decision_source(
            world.events, decision=decision, causal_payload=causal_payload,
            cause_ids=cause_ids, decision_sequence=sequence,
            decision_day=world.clock.absolute_day)
    if causal_origin == CausalOrigin.ACTOR_DECISION and deltas:
        if not any((cause_event := _recorded_event(world.events, cause)) is not None
                   and cause_event.fact_kind is FactKind.DECISION
                   and cause_event.causal_origin is CausalOrigin.ACTOR_DECISION
                   and cause_event.decision is not None
                   and cause_event.sequence < sequence
                   and cause_event.day == world.clock.absolute_day
                   for cause in cause_ids):
            raise ValueError("actor state transition requires a same-day real decision cause")
        _validate_actor_authorship_payload(
            world.events, causal_payload=causal_payload, cause_ids=cause_ids,
            event_day=world.clock.absolute_day, event_sequence=sequence)
    elif (causal_origin is CausalOrigin.ACTOR_DECISION
          and fact_kind is not FactKind.DECISION):
        if not any((cause_event := _recorded_event(world.events, cause)) is not None
                   and cause_event.fact_kind is FactKind.DECISION
                   and cause_event.causal_origin is CausalOrigin.ACTOR_DECISION
                   and cause_event.decision is not None
                   and cause_event.sequence < sequence
                   and cause_event.day == world.clock.absolute_day
                   for cause in cause_ids):
            raise ValueError("actor-authored event requires a same-day real decision cause")
    event = WorldEvent(
        id=event_id, day=world.clock.absolute_day, sequence=sequence,
        event_type=event_type, content=content, fact_kind=fact_kind,
        causal_origin=causal_origin, decision=decision, causal_payload=causal_payload,
        deltas=tuple(replace(d, event_id=event_id, id=f"{event_id}:delta:{i}") for i, d in enumerate(deltas)),
        causal_links=tuple(CausalLink(id=f"{event_id}:cause:{i}", event_id=event_id,
                                    cause_event_id=cause, created_at=0.0)
                           for i, cause in enumerate(cause_ids)),
    )
    prior_count = len(world.events)
    prior_identity = id(world.events[-1]) if world.events else 0
    cached_index = world._event_index_cache
    cached_types = world._event_type_cache
    world.events.append(event)
    if (cached_index is not None and cached_index[0] == prior_count
            and cached_index[1] == prior_identity):
        cached_index[2][event.id] = event
        world._event_index_cache = (len(world.events), id(event), cached_index[2])
    else:
        world._event_index_cache = None
    if (cached_types is not None and cached_types[0] == prior_count
            and cached_types[1] == prior_identity):
        grouped = cached_types[2]
        grouped[event.event_type] = (*grouped.get(event.event_type, ()), event)
        world._event_type_cache = (len(world.events), id(event), grouped)
    else:
        world._event_type_cache = None
    world._actor_decision_cache = None
    if hasattr(world.knowledge, "_query_cache"):
        world.knowledge._query_cache = None
    return event


def record_no_action_decision(world, event_type: str, content: str, actor_ref, *,
                              affordance_ids=(), cause_ids=()):
    """Persist an explicit provider refusal without implying a world effect."""
    actor = actor_ref.to_dict() if hasattr(actor_ref, "to_dict") else actor_ref
    if not isinstance(actor, dict):
        raise ValueError("no-action decision requires an actor reference")
    cause_ids = tuple(cause_ids)
    receipt = world.events[-1] if world.events else None
    selection = (receipt.causal_payload or {}).get("selection") if receipt is not None else None
    if (receipt is None or receipt.event_type != "ai_decision_declined"
            or receipt.fact_kind is not FactKind.OCCURRENCE
            or receipt.causal_origin is not CausalOrigin.LLM_INTERPRETATION
            or receipt.deltas
            or receipt.day != world.clock.absolute_day
            or not isinstance(selection, dict)
            or selection.get("actor_ref") != actor
            or selection.get("selected_affordance_id") != "NO_ACTION"
            or {link.cause_event_id for link in receipt.causal_links} != set(cause_ids)):
        raise ValueError("no-action decision requires its current provider refusal receipt")
    causal_ids = tuple(dict.fromkeys((*cause_ids, receipt.id)))
    return record_event(
        world, event_type, content, fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        decision={"action": "no_action", "actor_ref": actor,
                  "selected_affordance_id": "NO_ACTION",
                  "declined_option_ids": tuple(sorted(affordance_ids))},
        causal_payload={"decision_source": {"kind": "provider", "receipt_event_id": receipt.id}},
        cause_ids=causal_ids,
    )

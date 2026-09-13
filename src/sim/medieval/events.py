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
    deltas: tuple[StateDelta, ...] = ()
    causal_links: tuple[CausalLink, ...] = ()

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
        if self.deltas and self.causal_origin == CausalOrigin.LLM_INTERPRETATION:
            raise ValueError("an interpretation cannot carry a state change")
        for index, delta in enumerate(self.deltas):
            if (delta.event_id != self.id or delta.id != f"{self.id}:delta:{index}"
                    or not delta.owner_kind or not delta.owner_id or not delta.aspect):
                raise ValueError("invalid delta owner or event reference")
        for index, link in enumerate(self.causal_links):
            if link.event_id != self.id or link.id != f"{self.id}:cause:{index}":
                raise ValueError("invalid causal link event reference")
        return self


def _interprets(event) -> bool:
    return event.causal_origin == CausalOrigin.LLM_INTERPRETATION


def validate_history(events, day: int) -> None:
    known = {}
    previous_day = 0
    for index, event in enumerate(events, start=1):
        event = WorldEvent.model_validate(event.model_dump(mode="json"))
        if event.sequence != index or not previous_day <= event.day <= day:
            raise ValueError("event sequence or date is inconsistent with world clock")
        causes = [link.cause_event_id for link in event.causal_links]
        if len(set(causes)) != len(causes) or any(cause not in known for cause in causes):
            raise ValueError("unknown or repeated event cause")
        if event.deltas and any(_interprets(known[cause]) for cause in causes):
            raise ValueError("a state change cannot be caused directly by an interpretation")
        known[event.id] = event
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


def record_event(world, event_type: str, content: str, *, fact_kind=FactKind.OCCURRENCE,
                 causal_origin=CausalOrigin.DETERMINISTIC, decision=None, deltas=(), cause_ids=()) -> WorldEvent:
    sequence = len(world.events) + 1
    event_id = f"event:{sequence}"
    if len(set(cause_ids)) != len(cause_ids) or any(not _is_recorded(world.events, cause) for cause in cause_ids):
        raise ValueError("unknown or repeated event cause")
    if deltas and any(_interprets(world.events[int(cause.partition(":")[2]) - 1]) for cause in cause_ids):
        raise ValueError("a state change cannot be caused directly by an interpretation")
    event = WorldEvent(
        id=event_id, day=world.clock.absolute_day, sequence=sequence,
        event_type=event_type, content=content, fact_kind=fact_kind,
        causal_origin=causal_origin, decision=decision,
        deltas=tuple(replace(d, event_id=event_id, id=f"{event_id}:delta:{i}") for i, d in enumerate(deltas)),
        causal_links=tuple(CausalLink(id=f"{event_id}:cause:{i}", event_id=event_id,
                                    cause_event_id=cause, created_at=0.0)
                           for i, cause in enumerate(cause_ids)),
    )
    world.events.append(event)
    return event

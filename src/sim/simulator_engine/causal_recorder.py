"""
Passive per-step causal recorder.

Domain owners (an `Action`, a phase function, ...) write to this object
*after* they have already applied a change to the authoritative state; the
recorder never calls a domain method and never orchestrates anything. It is
drained once, by `finalize_step`, onto the final events of the step.

Removing this object, or never writing to it, must reproduce today's event
set and domain state byte for byte -- see
docs/specs/causal-world-kernel.md section 4.2.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from src.classes.causal_link import CausalLink, MAX_CAUSAL_LINKS_PER_EVENT
from src.classes.event import Event
from src.classes.state_delta import StateDelta


@dataclass(slots=True)
class CausalRecorder:
    _links: dict[str, list[tuple[int, CausalLink]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _deltas: dict[str, list[StateDelta]] = field(default_factory=lambda: defaultdict(list))

    def record_link(self, event_id: str, link: CausalLink, *, priority: int = 0) -> None:
        """Attach a causal edge to the effect event `event_id`.

        `priority` only decides which links survive the recorder's own
        at-most-`MAX_CAUSAL_LINKS_PER_EVENT` selection in `attach_to`; it is
        not persisted. `EventStorage`'s own first-N slice stays a backstop
        for anything that reaches it uncapped.
        """
        link.event_id = event_id
        self._links[event_id].append((priority, link))

    def record_delta(self, event_id: str, delta: StateDelta) -> None:
        delta.event_id = event_id
        self._deltas[event_id].append(delta)

    def attach_to(self, events: list[Event]) -> None:
        """Drain recorded links/deltas onto the matching final events.

        Events with nothing recorded against their id are left completely
        untouched -- this is what makes an empty recorder a no-op.
        """
        for event in events:
            links = self._links.get(event.id)
            if links:
                ranked = sorted(links, key=lambda pair: pair[0], reverse=True)
                event.causal_links = [link for _, link in ranked[:MAX_CAUSAL_LINKS_PER_EVENT]]

            deltas = self._deltas.get(event.id)
            if deltas:
                payload: dict[str, Any] = dict(event.causal_payload or {})
                payload["deltas"] = [delta.to_dict() for delta in deltas]
                event.causal_payload = payload


def get_causal_recorder(world: Any) -> CausalRecorder | None:
    """Bridge for domain owners that only have access to `world`, not the
    step's `SimulationStepContext` -- same shape as
    `runtime_capabilities.get_decision_boundary_gateway`."""
    return getattr(world, "step_causal_recorder", None)

"""Code-owned registry for transient collective-domain affordances."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from src.classes.domain_affordance import DomainAffordance
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event
from src.classes.event import FactKind
from src.classes.mechanical_language import ConditionInstance, EntityRef


@dataclass(frozen=True, slots=True)
class AffordanceContext:
    world: Any
    domain: str
    actor_ref: EntityRef
    trigger_event: Event
    condition: ConditionInstance | None = None


AffordanceProvider = Callable[[AffordanceContext], Iterable[DomainAffordance]]
AffordanceExecutor = Callable[..., Event]


class StaleAffordanceError(ValueError):
    pass


class DomainAffordanceRegistry:
    """Composes options from current state and revalidates before execution."""

    def __init__(self) -> None:
        self._providers: dict[str, list[AffordanceProvider]] = defaultdict(list)
        self._executors: dict[str, AffordanceExecutor] = {}

    def register_provider(
        self, domain: str, provider: AffordanceProvider
    ) -> AffordanceProvider:
        if provider not in self._providers[domain]:
            self._providers[domain].append(provider)
        return provider

    def register_executor(
        self, action_kind: str, executor: AffordanceExecutor
    ) -> AffordanceExecutor:
        existing = self._executors.get(action_kind)
        if existing is not None and existing is not executor:
            raise ValueError(f"executor already registered for {action_kind}")
        self._executors[action_kind] = executor
        return executor

    def compose(self, context: AffordanceContext) -> tuple[DomainAffordance, ...]:
        options: dict[str, DomainAffordance] = {}
        for provider in self._providers.get(context.domain, ()):
            for option in provider(context):
                if option.domain != context.domain or option.actor_ref != context.actor_ref:
                    raise ValueError("provider returned an affordance for another actor")
                if option.id in options and options[option.id] != option:
                    raise ValueError("affordance id collision")
                options[option.id] = option
        return tuple(
            sorted(
                options.values(),
                key=lambda item: (-item.urgency, item.action_kind, item.id),
            )
        )

    def revalidate(
        self, context: AffordanceContext, selected_affordance_id: str
    ) -> DomainAffordance:
        match = next(
            (
                option
                for option in self.compose(context)
                if option.id == selected_affordance_id
            ),
            None,
        )
        if match is None:
            raise StaleAffordanceError(
                "selected affordance is absent or stale in canonical state"
            )
        if match.action_kind not in self._executors:
            raise ValueError(f"no executor registered for {match.action_kind}")
        return match

    def execute(
        self,
        context: AffordanceContext,
        selected_affordance_id: str,
        **kwargs: Any,
    ) -> Event:
        option = self.revalidate(context, selected_affordance_id)
        return self._executors[option.action_kind](context, option, **kwargs)

    def clear(self) -> None:
        self._providers.clear()
        self._executors.clear()


DOMAIN_AFFORDANCES = DomainAffordanceRegistry()


def stale_affordance_blocked_event(
    context: AffordanceContext,
    *,
    decision_event_id: str,
    selected_affordance_id: str,
) -> Event:
    event = Event(
        context.world.month_stamp,
        "The selected domain affordance was no longer available.",
        event_type="domain_affordance_blocked",
        render_key="domain_affordance_blocked",
        render_params={
            "domain": context.domain,
            "actor_kind": context.actor_ref.kind,
            "actor_id": context.actor_ref.id,
            "affordance_id": selected_affordance_id,
            "reason": "absent_or_stale",
        },
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={
            "deltas": [],
            "outcome": "blocked",
            "reason": "absent_or_stale",
            "affordance_id": selected_affordance_id,
        },
    )
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=decision_event_id,
            relation=CausalRelation.MOTIVATED_BY,
        )
    )
    return event


__all__ = [
    "AffordanceContext",
    "DOMAIN_AFFORDANCES",
    "DomainAffordanceRegistry",
    "StaleAffordanceError",
    "stale_affordance_blocked_event",
]

"""Code-owned registry for transient collective-domain affordances."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from src.classes.agent_decision import AgentDecision
from src.classes.domain_affordance import DomainAffordance
from src.classes.domain_affordance import DomainDecisionKind
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


def event_lookup(
    world: Any, overlays: Iterable[Event] = ()
) -> Callable[[str], Event | None]:
    """Resolve an event id from explicit step-local evidence, then the store.

    Overlays are the canonical events this very step produced, which are not
    queryable until the finalizer persists them.  Nothing else may be injected
    here: an arbitrary object carrying a familiar id is not canonical
    evidence, and in particular a caller's own trigger object is never trusted
    as its own source.
    """

    by_id = {
        event.id: event
        for event in overlays
        if isinstance(event, Event) and event.id
    }
    resolved: dict[str, Event | None] = {}

    def lookup(event_id: str) -> Event | None:
        key = str(event_id)
        if key in resolved:
            return resolved[key]
        found = by_id.get(key)
        if not isinstance(found, Event):
            manager = getattr(world, "event_manager", None)
            getter = getattr(manager, "get_event_by_id", None)
            stored = getter(key) if callable(getter) else None
            found = stored if isinstance(stored, Event) else None
        resolved[key] = found
        return found

    return lookup


def validate_actor_decision(
    decision_event: Any,
    context: "AffordanceContext",
    option: DomainAffordance,
    *,
    label: str,
) -> None:
    """Only this actor's real, current decision may move canonical state.

    Shared by every collective domain: the decision must be a canonical
    `DECISION` fact carrying no delta, authored this month by this very actor,
    selecting exactly this option, and answering this trigger.
    """

    if not isinstance(decision_event, Event):
        raise StaleAffordanceError(f"{label} decision is absent")
    payload = (
        decision_event.causal_payload
        if isinstance(decision_event.causal_payload, dict)
        else {}
    )
    decision = payload.get("decision")
    interpretation = payload.get("interpretation")
    try:
        audit = AgentDecision.from_dict(decision)
    except (AttributeError, TypeError, ValueError):
        raise StaleAffordanceError(f"{label} decision is not canonical") from None
    render_params = decision_event.render_params or {}
    if (
        decision_event.fact_kind is not FactKind.DECISION
        or decision_event.is_story
        or payload.get("deltas") != []
        or not isinstance(decision, dict)
        or not isinstance(interpretation, dict)
        or set(decision) != set(audit.to_dict())
        or audit.month_stamp != int(context.world.month_stamp)
        or not audit.id
        or audit.subject_kind != context.actor_ref.kind
        or str(audit.subject_id) != context.actor_ref.id
        or audit.source not in {"llm", "rule", "injected"}
        or audit.chosen_chain != [{"selected_affordance_id": option.id}]
        or render_params.get("domain") != context.domain
        or render_params.get("actor_kind") != context.actor_ref.kind
        or str(render_params.get("actor_id")) != context.actor_ref.id
        or interpretation.get("decision") != DomainDecisionKind.ACT.value
        or str(interpretation.get("selected_affordance_id", "")) != option.id
        or not any(
            link.relation is CausalRelation.RESPONSE_TO
            and link.cause_event_id == context.trigger_event.id
            for link in decision_event.causal_links
        )
    ):
        raise StaleAffordanceError(f"{label} decision is not canonical")


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
    "event_lookup",
    "stale_affordance_blocked_event",
    "validate_actor_decision",
]

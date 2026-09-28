"""Atomic boundary for direct material owner commands.

The monthly simulator has its own candidate transaction. Direct owner commands
must not publish a receipt (or mutate a registry) before all later checks pass.
"""

from collections.abc import Callable
from typing import TypeVar

from src.classes.core.infrastructure import validate_infrastructure

from .activities import validate_activities
from .events import validate_history


Result = TypeVar("Result")


def execute_material(world, operation: Callable[..., Result], /, *args, **kwargs) -> Result:
    """Execute on an isolated candidate; publish only a valid complete result.

    The owner supplies its own current-affordance, authority, resource and
    physical checks. This boundary owns rollback and cross-owner/ledger checks.
    """
    candidate = world.transaction_copy()
    history_start = len(world.events) + 1
    result = operation(candidate, *args, **kwargs)
    material_events = [event for event in candidate.events[history_start - 1:]
                       if event.deltas]
    if not material_events:
        raise ValueError("material execution requires a state-transition receipt")
    if any(not event.causal_links for event in material_events):
        raise ValueError("direct material execution requires a recorded cause")
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.authority.validate(candidate)
    candidate.strategy.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.research.validate(candidate)
    candidate.relations.validate(candidate)
    candidate.regional_overflow.validate(candidate)
    candidate.creatures.validate(candidate)
    validate_infrastructure(candidate)
    validate_activities(candidate)
    validate_history(candidate.events, candidate.clock.absolute_day,
                     from_sequence=history_start)
    world.__dict__.update(candidate.__dict__)
    return result

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CausalBudget:
    """One shared guardrail for every nested reaction in a simulation step."""

    semantic_evaluations: int
    interpreter_calls: int
    propagation_steps: int
    domain_mutations: int

    @classmethod
    def from_world(cls, world: Any) -> "CausalBudget":
        config = getattr(world, "run_config_snapshot", {}) or {}
        return cls(
            semantic_evaluations=_value(
                config,
                "semantic_evaluation_budget_per_month",
                256,
            ),
            interpreter_calls=_value(
                config,
                "domain_interpreter_budget_per_month",
                8,
            ),
            propagation_steps=_value(
                config,
                "causal_propagation_budget_per_month",
                32,
            ),
            domain_mutations=_value(
                config,
                "domain_mutation_budget_per_month",
                32,
            ),
        )

    def consume_semantic_evaluation(self) -> bool:
        return self._consume("semantic_evaluations")

    def consume_interpreter_call(self) -> bool:
        return self._consume("interpreter_calls")

    def consume_propagation_step(self) -> bool:
        return self._consume("propagation_steps")

    def consume_domain_mutation(self) -> bool:
        return self._consume("domain_mutations")

    def _consume(self, field_name: str) -> bool:
        remaining = int(getattr(self, field_name))
        if remaining <= 0:
            return False
        setattr(self, field_name, remaining - 1)
        return True


def _value(config: dict[str, Any], key: str, default: int) -> int:
    try:
        return max(0, int(config.get(key, default)))
    except (TypeError, ValueError):
        return default

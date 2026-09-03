from __future__ import annotations

from typing import Any

from src.classes.mechanical_language import PrimitiveDimension


def metric_leaves(
    expression: Any,
    definitions: dict[str, Any] | None = None,
    *,
    _seen: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """Expand metric leaves through registered derived definitions safely."""
    if isinstance(expression, dict):
        leaves = [expression] if expression.get("op") == "metric" else []
        if expression.get("op") == "derived":
            definition_id = str(expression.get("definition_id", ""))
            if definition_id and definition_id not in _seen:
                definition = (definitions or {}).get(definition_id)
                if definition is not None:
                    leaves.extend(
                        metric_leaves(
                            definition.expression,
                            definitions,
                            _seen=_seen | {definition_id},
                        )
                    )
        for value in expression.values():
            leaves.extend(metric_leaves(value, definitions, _seen=_seen))
        return leaves
    if isinstance(expression, list):
        return [
            leaf
            for value in expression
            for leaf in metric_leaves(value, definitions, _seen=_seen)
        ]
    return []


def is_settlement_pressure(world: Any, definition_id: str) -> bool:
    """Return whether a condition depends on settlement load and capacity."""
    state = world.mechanical_language
    condition = state.condition_definitions.get(definition_id)
    if condition is None:
        return False
    metric = state.derived_definitions.get(condition.metric_definition_id)
    if metric is None or metric.target_kind != "region":
        return False

    leaves = {
        (str(node.get("dimension")), str(node.get("concept_id")))
        for node in metric_leaves(metric.expression, state.derived_definitions)
    }

    return {
        ("load", "settlement"),
        ("capacity", "settlement"),
    }.issubset(leaves)


def is_regional_adversity(world: Any, definition_id: str) -> bool:
    """Return whether a grounded regional condition represents elevated risk.

    Institutional emergency support is a material response, so a mere label or
    arbitrary regional condition is insufficient.  V1 accepts only a
    registered region-scoped derived risk metric; the phenomenon vocabulary
    remains dynamic while the mechanical grammar stays closed.
    """
    state = world.mechanical_language
    condition = state.condition_definitions.get(definition_id)
    if condition is None or condition.target_kind != "region":
        return False
    metric = state.derived_definitions.get(condition.metric_definition_id)
    if (
        metric is None
        or metric.target_kind != "region"
        or metric.dimension is not PrimitiveDimension.RISK
    ):
        return False
    return not any(
        leaf.get("group_id") is not None
        and dict(leaf.get("qualifiers", {}) or {}).get("kind") == "urban_service"
        for leaf in metric_leaves(metric.expression, state.derived_definitions)
    )


__all__ = ["is_regional_adversity", "is_settlement_pressure", "metric_leaves"]

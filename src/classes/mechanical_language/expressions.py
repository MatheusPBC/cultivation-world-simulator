from __future__ import annotations

import math
from typing import Any

from .models import (
    MeasurementAvailability,
    MetricKey,
    MetricReading,
    PrimitiveDimension,
    ReadingKind,
)


class ExpressionValidationError(ValueError):
    pass


_OPS = {"metric", "derived", "constant", "add", "subtract", "multiply", "divide", "min", "max", "clamp", "weighted_sum"}
_SCALAR_UNITS = {"scalar", "ratio"}
def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _children(node: dict[str, Any]) -> list[dict[str, Any]]:
    op = node.get("op")
    if op in {"add", "subtract", "multiply", "divide", "min", "max"}:
        return [node.get("left"), node.get("right")]
    if op == "clamp":
        return [node.get("value")]
    if op == "weighted_sum":
        return [item.get("expression") for item in node.get("items", [])]
    return []


def validate_expression(
    expression: dict[str, Any],
    *,
    max_nodes: int,
    max_depth: int,
    definitions: dict[str, Any] | None = None,
    require_grounded: bool = False,
    target_kind: str = "region",
) -> None:
    count = 0

    def visit(node: Any, depth: int) -> None:
        nonlocal count
        if not isinstance(node, dict):
            raise ExpressionValidationError("every expression node must be an object")
        count += 1
        if count > max_nodes or depth > max_depth:
            raise ExpressionValidationError("expression exceeds configured complexity")
        op = node.get("op")
        if op not in _OPS:
            raise ExpressionValidationError(f"unsupported expression operator: {op}")
        if op == "metric":
            try:
                PrimitiveDimension(str(node["dimension"]))
                str(node["concept_id"])
                _parse_group_id(node.get("group_id"))
                _parse_qualifiers(node.get("qualifiers", {}))
            except (KeyError, ValueError) as exc:
                raise ExpressionValidationError("invalid metric reference") from exc
        elif op == "derived" and not str(node.get("definition_id", "")).strip():
            raise ExpressionValidationError("derived reference requires definition_id")
        elif op == "constant":
            if not _is_finite_number(node.get("value")):
                raise ExpressionValidationError("constant requires a number")
            if str(node.get("unit", "scalar")) not in _SCALAR_UNITS:
                raise ExpressionValidationError(
                    "constants may only declare scalar or ratio units"
                )
        elif op == "clamp":
            if not _is_finite_number(node.get("min")) or not _is_finite_number(node.get("max")):
                raise ExpressionValidationError("clamp requires numeric bounds")
            if float(node["min"]) > float(node["max"]):
                raise ExpressionValidationError("clamp min cannot exceed max")
        elif op == "weighted_sum":
            items = node.get("items")
            if not isinstance(items, list) or not items:
                raise ExpressionValidationError("weighted_sum requires items")
            if any(not isinstance(item, dict) or not _is_finite_number(item.get("weight")) for item in items):
                raise ExpressionValidationError("weighted_sum items require numeric weights")
        for child in _children(node):
            visit(child, depth + 1)

    visit(expression, 1)
    infer_expression_unit(
        expression,
        definitions=definitions,
        require_grounded=require_grounded,
        target_kind=target_kind,
    )


def infer_expression_unit(
    expression: dict[str, Any],
    *,
    definitions: dict[str, Any] | None = None,
    require_grounded: bool = False,
    target_kind: str = "region",
) -> str | None:
    """Infer the unit of a safe expression without reading canonical state.

    ``None`` means that a referenced derived definition is not available yet,
    or that a non-grounded expression cannot be measured. Known incompatible
    units are errors rather than an implicit conversion.
    """

    def unit(node: dict[str, Any]) -> str | None:
        op = node["op"]
        if op == "constant":
            return str(node.get("unit", "scalar"))
        if op == "metric":
            from src.systems.semantic_world.resolvers import metric_unit as resolve_metric_unit

            dimension = PrimitiveDimension(str(node["dimension"]))
            concept_id = str(node["concept_id"])
            group_id = _parse_group_id(node.get("group_id"))
            qualifiers = _parse_qualifiers(node.get("qualifiers", {}))
            metric_unit = resolve_metric_unit(
                MetricKey(
                    dimension,
                    target_kind,
                    "*",
                    concept_id,
                    group_id=group_id,
                    qualifiers=qualifiers,
                )
            )
            if metric_unit is None and require_grounded:
                raise ExpressionValidationError("unknown or unmeasurable metric leaf")
            return metric_unit
        if op == "derived":
            definition = (definitions or {}).get(str(node["definition_id"]))
            if definition is None:
                if require_grounded:
                    raise ExpressionValidationError("unknown derived metric reference")
                return None
            return str(definition.unit) if str(definition.unit).strip() else None
        if op == "clamp":
            return unit(node["value"])
        if op == "weighted_sum":
            item_units = [unit(item["expression"]) for item in node["items"]]
            return _same_units(item_units)

        left = unit(node["left"])
        right = unit(node["right"])
        if left is None or right is None:
            return None
        if op in {"add", "subtract", "min", "max"}:
            return _require_same_units(left, right)
        if op == "multiply":
            if left in _SCALAR_UNITS:
                return right
            if right in _SCALAR_UNITS:
                return left
            raise ExpressionValidationError("incompatible expression units for multiply")
        if op == "divide":
            if right in _SCALAR_UNITS:
                return left
            if left == right:
                return "ratio"
            raise ExpressionValidationError("incompatible expression units for divide")
        raise ExpressionValidationError(f"unsupported expression operator: {op}")

    return unit(expression)


def _same_units(units: list[str | None]) -> str | None:
    if any(item is None for item in units):
        return None
    known = [item for item in units if item is not None]
    if not known:
        return None
    if len(set(known)) != 1:
        raise ExpressionValidationError("incompatible expression units")
    return known[0]


def _require_same_units(left: str, right: str) -> str:
    if left != right:
        raise ExpressionValidationError("incompatible expression units")
    return left


def evaluate_expression(
    expression: dict[str, Any],
    *,
    world: Any,
    target: Any,
    target_kind: str,
    definitions: dict[str, Any] | None = None,
    calculated_month: int = 0,
) -> MetricReading:
    from src.systems.semantic_world.resolvers import resolve_metric

    subject_id = str(getattr(target, "id", ""))
    leaves: list[MetricReading] = []

    def unknown(concept_id: str = "expression") -> MetricReading:
        availability = (
            MeasurementAvailability.PARTIALLY_MEASURABLE
            if any(item.availability is not MeasurementAvailability.UNMEASURABLE for item in leaves)
            else MeasurementAvailability.UNMEASURABLE
        )
        return MetricReading(
            key=MetricKey(PrimitiveDimension.QUALITY, target_kind, subject_id, concept_id),
            value=None,
            unit="unknown",
            availability=availability,
            reading_kind=ReadingKind.UNKNOWN,
            calculated_month=calculated_month,
            derived_from=[item.key.to_dict() for item in leaves],
            state_refs=_unique(ref for item in leaves for ref in item.state_refs),
            source_event_ids=_unique(event_id for item in leaves for event_id in item.source_event_ids),
        )

    def calculate(node: dict[str, Any]) -> float | None:
        op = node["op"]
        if op == "constant":
            return float(node["value"])
        if op == "metric":
            group_id = _parse_group_id(node.get("group_id"))
            qualifiers = _parse_qualifiers(node.get("qualifiers", {}))
            reading = resolve_metric(
                world,
                MetricKey(
                    PrimitiveDimension(node["dimension"]),
                    target_kind,
                    subject_id,
                    str(node["concept_id"]),
                    group_id=group_id,
                    qualifiers=qualifiers,
                ),
                target=target,
                calculated_month=calculated_month,
            )
            leaves.append(reading)
            return reading.value
        if op == "derived":
            definition = (definitions or {}).get(str(node["definition_id"]))
            if definition is None:
                return None
            nested = evaluate_expression(
                definition.expression,
                world=world,
                target=target,
                target_kind=target_kind,
                definitions=definitions,
                calculated_month=calculated_month,
            )
            leaves.append(nested)
            return nested.value
        if op == "weighted_sum":
            values = [(calculate(item["expression"]), float(item["weight"])) for item in node["items"]]
            return None if any(value is None for value, _ in values) else sum(float(value) * weight for value, weight in values)
        if op == "clamp":
            value = calculate(node["value"])
            return None if value is None else max(float(node["min"]), min(float(node["max"]), value))
        left = calculate(node["left"])
        right = calculate(node["right"])
        if left is None or right is None:
            return None
        if op == "add":
            return left + right
        if op == "subtract":
            return left - right
        if op == "multiply":
            return left * right
        if op == "divide":
            return None if right == 0 else left / right
        if op == "min":
            return min(left, right)
        if op == "max":
            return max(left, right)
        raise ExpressionValidationError(f"unsupported expression operator: {op}")

    value = calculate(expression)
    unit = infer_expression_unit(
        expression,
        definitions=definitions,
        target_kind=target_kind,
    )
    if value is None or unit is None or not math.isfinite(value):
        return unknown()
    return MetricReading(
        key=MetricKey(PrimitiveDimension.QUALITY, target_kind, subject_id, "expression"),
        value=value,
        unit=unit,
        availability=MeasurementAvailability.MEASURABLE,
        reading_kind=ReadingKind.DERIVED,
        calculated_month=calculated_month,
        derived_from=[item.key.to_dict() for item in leaves],
        state_refs=_unique(ref for item in leaves for ref in item.state_refs),
        source_event_ids=_unique(event_id for item in leaves for event_id in item.source_event_ids),
    )


def _unique(values) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _parse_qualifiers(raw: Any) -> tuple[tuple[str, str], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise ExpressionValidationError("metric qualifiers must be an object")
    return tuple((str(name), str(value)) for name, value in raw.items())


def _parse_group_id(raw: Any) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ExpressionValidationError("metric group_id must be a non-empty string")
    return raw.strip()

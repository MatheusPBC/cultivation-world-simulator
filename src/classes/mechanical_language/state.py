from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any, TypeVar

from .expressions import ExpressionValidationError, infer_expression_unit, validate_expression
from .models import (
    Concept,
    ConditionDefinition,
    DerivedMetricDefinition,
    DomainReactionReceipt,
    EntityRef,
    Grounding,
    MechanicProposal,
    ConditionInstance,
)

MECHANICAL_LANGUAGE_VERSION = 1
RegistryItem = TypeVar("RegistryItem")


@dataclass
class MechanicalLanguageState:
    language_version: int = MECHANICAL_LANGUAGE_VERSION
    concepts: dict[str, Concept] = field(default_factory=dict)
    groundings: dict[str, Grounding] = field(default_factory=dict)
    derived_definitions: dict[str, DerivedMetricDefinition] = field(default_factory=dict)
    condition_definitions: dict[str, ConditionDefinition] = field(default_factory=dict)
    condition_instances: dict[str, ConditionInstance] = field(default_factory=dict)
    mechanic_proposals: dict[str, MechanicProposal] = field(default_factory=dict)
    reaction_receipts: dict[str, DomainReactionReceipt] = field(default_factory=dict)
    fingerprints: dict[str, str] = field(default_factory=dict)
    discovery_attempt_months: dict[str, int] = field(default_factory=dict)
    pending_streaks: dict[str, dict[str, int]] = field(default_factory=dict)
    dirty_targets: list[str] = field(default_factory=list)
    pending_source_event_ids: dict[str, list[str]] = field(default_factory=dict)
    pending_target_source_event_ids: dict[str, list[str]] = field(default_factory=dict)
    pending_affinity_source_event_ids: dict[str, dict[str, list[str]]] = field(
        default_factory=dict
    )
    _world: Any = field(default=None, init=False, repr=False, compare=False)

    def bind_world(self, world: Any) -> None:
        self._world = world

    def add_derived_definition(
        self,
        definition: DerivedMetricDefinition,
        *,
        max_nodes: int = 32,
        max_depth: int = 8,
        allow_unresolved_leaves: bool = False,
    ) -> None:
        if definition.id in self.derived_definitions:
            raise ExpressionValidationError(f"duplicate derived metric id: {definition.id}")
        validate_expression(
            definition.expression,
            max_nodes=max_nodes,
            max_depth=max_depth,
            definitions=self.derived_definitions,
            require_grounded=not allow_unresolved_leaves,
            target_kind=definition.target_kind,
        )
        inferred_unit = infer_expression_unit(
            definition.expression,
            definitions=self.derived_definitions,
            require_grounded=not allow_unresolved_leaves,
            target_kind=definition.target_kind,
        )
        if inferred_unit is not None and definition.unit != inferred_unit:
            raise ExpressionValidationError(
                f"definition unit {definition.unit!r} does not match inferred unit {inferred_unit!r}"
            )
        candidate = dict(self.derived_definitions)
        candidate[definition.id] = definition
        graph = {
            definition_id: _derived_refs(item.expression)
            for definition_id, item in candidate.items()
        }
        _reject_cycles(graph)
        self.derived_definitions[definition.id] = definition

    def add_condition_definition(self, definition: ConditionDefinition) -> None:
        if definition.id in self.condition_definitions:
            raise ValueError(f"duplicate condition definition id: {definition.id}")
        metric = self.derived_definitions.get(definition.metric_definition_id)
        if metric is None:
            raise ValueError(f"unknown metric definition: {definition.metric_definition_id}")
        if metric.target_kind != definition.target_kind:
            raise ValueError("condition and metric target kinds must match")
        self.condition_definitions[definition.id] = definition

    def add_condition_instance(self, instance: ConditionInstance) -> None:
        if not isinstance(instance, ConditionInstance):
            raise TypeError("condition instance must be a ConditionInstance")
        if instance.id in self.condition_instances:
            raise ValueError(f"duplicate condition instance id: {instance.id}")
        self.condition_instances[instance.id] = instance

    def replace_condition_instance(self, instance: ConditionInstance) -> None:
        if instance.id not in self.condition_instances:
            raise KeyError(f"unknown condition instance: {instance.id}")
        self.condition_instances[instance.id] = instance

    def get_conditions_for_target(self, target: EntityRef) -> list[ConditionInstance]:
        return [
            instance
            for instance in self.condition_instances.values()
            if instance.target_kind == target.kind and instance.target_id == target.id
        ]

    def get_active_conditions(
        self,
        target: EntityRef,
        current_month: int,
    ) -> list[ConditionInstance]:
        return [
            instance
            for instance in self.get_conditions_for_target(target)
            if instance.is_active(current_month)
        ]

    def to_public_dict(self, target: EntityRef | None = None) -> dict[str, Any]:
        active_lifecycles = {"candidate", "active"}
        active_concepts = [
            concept.to_dict()
            for concept in self.concepts.values()
            if concept.lifecycle.value in active_lifecycles
        ]
        historical_concepts = [
            concept.to_dict()
            for concept in self.concepts.values()
            if concept.lifecycle.value not in active_lifecycles
        ]
        return {
            "active_concepts": active_concepts,
            "historical_concepts": historical_concepts,
            "language_version": self.language_version,
            "groundings": [item.to_dict() for item in self.groundings.values()],
            "derived_metric_definitions": [item.to_dict() for item in self.derived_definitions.values()],
            "condition_definitions": [item.to_dict() for item in self.condition_definitions.values()],
            "condition_instances": [
                item.to_dict()
                for item in (
                    self.get_conditions_for_target(target)
                    if target is not None
                    else self.condition_instances.values()
                )
            ],
            "mechanic_proposals": [item.to_dict() for item in self.mechanic_proposals.values()],
            "reaction_receipts": [
                item.to_dict() for item in self.reaction_receipts.values()
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "language_version": self.language_version,
            "concepts": {key: value.to_dict() for key, value in self.concepts.items()},
            "groundings": {key: value.to_dict() for key, value in self.groundings.items()},
            "derived_definitions": {key: value.to_dict() for key, value in self.derived_definitions.items()},
            "condition_definitions": {key: value.to_dict() for key, value in self.condition_definitions.items()},
            "condition_instances": {
                key: value.to_dict()
                for key, value in self.condition_instances.items()
            },
            "mechanic_proposals": {key: value.to_dict() for key, value in self.mechanic_proposals.items()},
            "reaction_receipts": {
                key: value.to_dict()
                for key, value in self.reaction_receipts.items()
            },
            "fingerprints": dict(self.fingerprints),
            "discovery_attempt_months": dict(self.discovery_attempt_months),
            "pending_streaks": {key: dict(value) for key, value in self.pending_streaks.items()},
            "dirty_targets": list(self.dirty_targets),
            "pending_source_event_ids": {
                key: list(value)
                for key, value in self.pending_source_event_ids.items()
            },
            "pending_target_source_event_ids": {
                key: list(value)
                for key, value in self.pending_target_source_event_ids.items()
            },
            "pending_affinity_source_event_ids": {
                target_ref: {
                    affinity: list(source_ids)
                    for affinity, source_ids in affinities.items()
                }
                for target_ref, affinities in self.pending_affinity_source_event_ids.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MechanicalLanguageState":
        if not isinstance(data, dict):
            raise TypeError("mechanical language state must be a mapping")
        raw = data
        language_version = int(raw["language_version"])
        if language_version != MECHANICAL_LANGUAGE_VERSION:
            raise ValueError(f"unsupported mechanical language version: {language_version}")
        state = cls(
            language_version=language_version,
            concepts=_load_registry(raw["concepts"], Concept.from_dict, "concepts"),
            groundings=_load_registry(raw["groundings"], Grounding.from_dict, "groundings"),
            derived_definitions=_load_registry(
                raw["derived_definitions"],
                DerivedMetricDefinition.from_dict,
                "derived_definitions",
            ),
            condition_definitions=_load_registry(
                raw["condition_definitions"],
                ConditionDefinition.from_dict,
                "condition_definitions",
            ),
            condition_instances=_load_registry(
                raw["condition_instances"],
                ConditionInstance.from_dict,
                "condition_instances",
            ),
            mechanic_proposals=_load_registry(
                raw["mechanic_proposals"],
                MechanicProposal.from_dict,
                "mechanic_proposals",
            ),
            reaction_receipts=_load_registry(
                raw["reaction_receipts"],
                DomainReactionReceipt.from_dict,
                "reaction_receipts",
            ),
            fingerprints={str(key): str(value) for key, value in raw["fingerprints"].items()},
            discovery_attempt_months={
                str(key): int(value)
                for key, value in raw["discovery_attempt_months"].items()
            },
            pending_streaks={
                str(key): {str(k): int(v) for k, v in value.items()}
                for key, value in raw["pending_streaks"].items()
            },
            dirty_targets=[str(item) for item in raw["dirty_targets"]],
            pending_source_event_ids={
                str(key): [str(item) for item in value]
                for key, value in raw["pending_source_event_ids"].items()
            },
            pending_target_source_event_ids={
                str(key): [str(item) for item in value]
                for key, value in raw["pending_target_source_event_ids"].items()
            },
            pending_affinity_source_event_ids={
                str(target_ref): {
                    str(affinity): [str(item) for item in source_ids]
                    for affinity, source_ids in affinities.items()
                }
                for target_ref, affinities in raw[
                    "pending_affinity_source_event_ids"
                ].items()
            },
        )
        _reject_cycles({key: _derived_refs(value.expression) for key, value in state.derived_definitions.items()})
        for definition in state.derived_definitions.values():
            validate_expression(
                definition.expression,
                max_nodes=256,
                max_depth=32,
                definitions=state.derived_definitions,
                require_grounded=True,
                target_kind=definition.target_kind,
            )
            inferred_unit = infer_expression_unit(
                definition.expression,
                definitions=state.derived_definitions,
                require_grounded=True,
                target_kind=definition.target_kind,
            )
            if definition.unit != inferred_unit:
                raise ExpressionValidationError(
                    f"definition unit {definition.unit!r} does not match inferred unit {inferred_unit!r}"
                )
        for definition in state.condition_definitions.values():
            metric = state.derived_definitions.get(definition.metric_definition_id)
            if metric is None:
                raise ValueError(f"unknown metric definition: {definition.metric_definition_id}")
            if metric.target_kind != definition.target_kind:
                raise ValueError("condition and metric target kinds must match")
        return state


def _load_registry(
    raw_registry: Any,
    parser: Callable[[dict[str, Any]], RegistryItem],
    registry_name: str,
) -> dict[str, RegistryItem]:
    if not isinstance(raw_registry, dict):
        raise TypeError(f"persisted {registry_name} must be a mapping")
    loaded: dict[str, RegistryItem] = {}
    seen_ids: set[str] = set()
    for raw_key, raw_item in raw_registry.items():
        if not isinstance(raw_item, dict):
            raise TypeError(f"persisted {registry_name} entries must be mappings")
        item = parser(raw_item)
        item_id = str(getattr(item, "id"))
        if item_id in seen_ids:
            raise ValueError(f"duplicate persisted {registry_name} id: {item_id}")
        key = str(raw_key)
        if key != item_id:
            raise ValueError(
                f"persisted {registry_name} key {key!r} does not match object id {item_id!r}"
            )
        seen_ids.add(item_id)
        loaded[item_id] = item
    return loaded


def _derived_refs(expression: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    stack = [expression]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if node.get("op") == "derived":
            refs.add(str(node.get("definition_id", "")))
        for value in node.values():
            if isinstance(value, dict):
                stack.append(value)
            elif isinstance(value, list):
                stack.extend(item for item in value if isinstance(item, dict))
    return refs


def _reject_cycles(graph: dict[str, set[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ExpressionValidationError("derived metric dependency cycle")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, set()):
            if dependency in graph:
                visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)

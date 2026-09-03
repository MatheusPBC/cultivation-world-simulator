from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import re
from typing import Any, Awaitable, Callable
import uuid

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import (
    Concept,
    ConceptLifecycle,
    ConditionDefinition,
    ConditionInstance,
    DerivedMetricDefinition,
    EntityRef,
    Grounding,
    GroundingStatus,
    MechanicProposal,
    MechanicalLanguageState,
    MeasurementAvailability,
    PrimitiveDimension,
    validate_expression,
)
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.systems.semantic_world.resolvers import (
    available_metric_keys,
    metric_unit,
    resolve_derived_metric,
)
from src.systems.collective_health import project_collective_health
from src.systems.spiritual_ecology import (
    SPIRITUAL_ANCHOR_RATIO_CONCEPT,
    project_spiritual_ecology,
    spiritual_metric_keys,
)
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ParseError, ProviderCallError
from src.utils.llm.runtime_mode import is_test_mode_enabled, is_world_test_mode
from src.utils.llm.test_mode_fallbacks import resolve_test_mode_task


SEMANTIC_DISCOVERY_TASK = "semantic_discovery"
SEMANTIC_DISCOVERY_TEMPLATE = "semantic_discovery.txt"
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


async def evaluate_semantic_world(
    world: Any,
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    source_event_ids_by_target: dict[str, list[str]] | None = None,
    health_source_event_ids_by_target: dict[str, list[str]] | None = None,
    spiritual_source_event_ids_by_target: dict[str, list[str]] | None = None,
    budget: Any | None = None,
) -> list[Event]:
    """Discover reusable observations, then evaluate them deterministically.

    This service may register vocabulary and observation rules. It never writes
    population, resources, relationships, or any other canonical domain value.
    """
    state = world.mechanical_language
    month = int(world.month_stamp)
    cities = sorted(
        (region for region in world.map.regions.values() if isinstance(region, CityRegion)),
        key=lambda region: (-_settlement_ratio(region), int(region.id)),
    )
    changed = [
        city
        for city in cities
        if state.fingerprints.get(_target_ref(city)) != _fingerprint(world, city)
    ]

    discovery_candidates = [
        (city, _uncovered_metric_keys(world, state, city))
        for city in cities
    ]
    discovery_candidates = [
        item for item in discovery_candidates if item[1]
    ]
    discovery_key = (
        _discovery_surface_key(discovery_candidates[0][1])
        if discovery_candidates
        else ""
    )
    last_attempt = state.discovery_attempt_months.get(discovery_key)
    retry_after = _guardrail(world, "semantic_discovery_retry_after_months", 12)
    can_attempt_discovery = last_attempt is None or month - last_attempt >= retry_after
    new_definition_ids: set[str] = set()
    if (
        discovery_candidates
        and _guardrail(world, "semantic_discovery_budget_per_month", 2) > 0
        and can_attempt_discovery
        and (budget is None or budget.consume_interpreter_call())
    ):
        source, available_metrics = discovery_candidates[0]
        state.discovery_attempt_months[discovery_key] = month
        try:
            definitions_before = set(state.derived_definitions)
            proposal = await _discover(
                world,
                source,
                available_metrics=available_metrics,
                llm_call=llm_call,
            )
            _accept_proposal(world, source, proposal)
            new_definition_ids = set(state.derived_definitions) - definitions_before
        except (LLMError, ParseError, ProviderCallError, ValueError, KeyError, TypeError):
            # Discovery is observational. Provider or validation failure cannot
            # abort a month or mutate canonical state.
            pass
        finally:
            for city in changed:
                state.fingerprints[_target_ref(city)] = _fingerprint(world, city)

    evaluation_budget = _guardrail(world, "semantic_evaluation_budget_per_month", 256)
    events: list[Event] = []
    task_by_key: dict[str, tuple[str, CityRegion]] = {}
    for definition in state.derived_definitions.values():
        if definition.lifecycle in {ConceptLifecycle.DEPRECATED, ConceptLifecycle.MERGED, ConceptLifecycle.DORMANT}:
            continue
        for city in cities:
            task_by_key[_evaluation_key(definition.id, city)] = (definition.id, city)
    sources_by_target = {
        target_ref: list(source_ids)
        for target_ref, source_ids in state.pending_target_source_event_ids.items()
    }
    for target_ref, source_ids in (source_event_ids_by_target or {}).items():
        pending = sources_by_target.setdefault(target_ref, [])
        pending.extend(source_id for source_id in source_ids if source_id not in pending)
    distributed_targets: set[str] = set()
    for target_ref, source_ids in sources_by_target.items():
        for key, (definition_id, city) in task_by_key.items():
            if (
                _target_ref(city) != target_ref
                or _definition_source_affinities(state, definition_id, city)
            ):
                continue
            distributed_targets.add(target_ref)
            pending_sources = state.pending_source_event_ids.setdefault(key, [])
            pending_sources.extend(
                source_id
                for source_id in source_ids
                if source_id not in pending_sources
            )
            if key not in state.dirty_targets:
                state.dirty_targets.append(key)
    for target_ref in distributed_targets:
        state.pending_target_source_event_ids.pop(target_ref, None)
    affinity_sources_by_target = {
        target_ref: {
            affinity: list(source_ids)
            for affinity, source_ids in affinities.items()
        }
        for target_ref, affinities in state.pending_affinity_source_event_ids.items()
    }
    for target_ref, source_ids in (health_source_event_ids_by_target or {}).items():
        pending = affinity_sources_by_target.setdefault(target_ref, {}).setdefault(
            "collective_health",
            [],
        )
        pending.extend(source_id for source_id in source_ids if source_id not in pending)
    for target_ref, source_ids in (spiritual_source_event_ids_by_target or {}).items():
        pending = affinity_sources_by_target.setdefault(target_ref, {}).setdefault(
            "spiritual_ecology",
            [],
        )
        pending.extend(source_id for source_id in source_ids if source_id not in pending)
    distributed_affinities: dict[str, set[str]] = {}
    for target_ref, affinities in affinity_sources_by_target.items():
        for affinity, source_ids in affinities.items():
            for key, (definition_id, city) in task_by_key.items():
                if (
                    _target_ref(city) != target_ref
                    or affinity
                    not in _definition_source_affinities(state, definition_id, city)
                ):
                    continue
                distributed_affinities.setdefault(target_ref, set()).add(affinity)
                pending_sources = state.pending_source_event_ids.setdefault(key, [])
                pending_sources.extend(
                    source_id
                    for source_id in source_ids
                    if source_id not in pending_sources
                )
                if key not in state.dirty_targets:
                    state.dirty_targets.append(key)
    for target_ref, affinities in distributed_affinities.items():
        pending = state.pending_affinity_source_event_ids.get(target_ref, {})
        for affinity in affinities:
            pending.pop(affinity, None)
        if not pending:
            state.pending_affinity_source_event_ids.pop(target_ref, None)
    for city in changed:
        for definition in state.derived_definitions.values():
            key = _evaluation_key(definition.id, city)
            if key in task_by_key and key not in state.dirty_targets:
                state.dirty_targets.append(key)
    for definition_id in sorted(new_definition_ids):
        for city in cities:
            key = _evaluation_key(definition_id, city)
            if key in task_by_key and key not in state.dirty_targets:
                state.dirty_targets.append(key)
    for key, (definition_id, city) in task_by_key.items():
        if _definition_has_pending_streak(state, definition_id, city):
            if key not in state.dirty_targets:
                state.dirty_targets.append(key)
    ordered_keys = [key for key in state.dirty_targets if key in task_by_key]
    selected_keys: list[str] = []
    for key in ordered_keys[:evaluation_budget]:
        if budget is not None and not budget.consume_semantic_evaluation():
            break
        selected_keys.append(key)
    state.dirty_targets = ordered_keys[len(selected_keys):]

    for key in selected_keys:
        definition_id, city = task_by_key[key]
        definition = state.derived_definitions[definition_id]
        condition_defs = [
            item
            for item in state.condition_definitions.values()
            if item.metric_definition_id == definition.id
            and item.lifecycle not in {
                ConceptLifecycle.DEPRECATED,
                ConceptLifecycle.MERGED,
                ConceptLifecycle.DORMANT,
            }
        ]
        reading = resolve_derived_metric(
            world,
            definition,
            target=city,
            calculated_month=month,
            definitions=state.derived_definitions,
        )
        source_ids = state.pending_source_event_ids.get(key, [])
        if source_ids:
            reading = replace(
                reading,
                source_event_ids=list(dict.fromkeys((*reading.source_event_ids, *source_ids))),
            )
        state.derived_definitions[definition.id] = _record_reuse(definition, city, month)
        state.fingerprints[_target_ref(city)] = _fingerprint(world, city)
        emitted_transition = False
        for condition_def in condition_defs:
            event = _evaluate_condition(world, city, condition_def, reading)
            if event is not None:
                emitted_transition = True
                events.append(event)
                _promote_for_consequence(state, definition.id, condition_def.id, month)
        has_pending_transition = any(
            _condition_has_pending_streak(state, condition_def, city)
            for condition_def in condition_defs
        )
        if has_pending_transition and key not in state.dirty_targets:
            state.dirty_targets.append(key)
        if emitted_transition or not has_pending_transition:
            state.pending_source_event_ids.pop(key, None)
    _apply_dormancy(world, month)
    return events


async def _discover(
    world: Any,
    source: CityRegion,
    *,
    available_metrics: list[Any],
    llm_call=None,
) -> dict[str, Any]:
    template_path = resolve_locale_template_path(
        SEMANTIC_DISCOVERY_TEMPLATE,
        current_locale=str((getattr(world, "run_config_snapshot", {}) or {}).get("content_locale", "")) or None,
    )
    infos = {
        "target": {
            "kind": "region",
            "id": str(source.id),
            "name": source.name,
            "population": source.population,
            "population_capacity": source.population_capacity,
        },
        "primitive_dimensions": [item.value for item in PrimitiveDimension],
        "available_metrics": _available_city_metrics(
            source,
            keys=available_metrics,
        ),
    }
    if is_world_test_mode(world) or is_test_mode_enabled():
        return resolve_test_mode_task(SEMANTIC_DISCOVERY_TASK, infos)
    caller = llm_call or call_llm_with_task_name
    return await caller(
        SEMANTIC_DISCOVERY_TASK,
        template_path,
        infos,
        output_schema=_discovery_schema(),
    )


def _available_city_metrics(
    source: CityRegion,
    *,
    keys: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Describe only measurements grounded by this city's canonical state."""
    metrics: list[dict[str, Any]] = []
    for key in keys if keys is not None else available_metric_keys(source):
        schema: dict[str, Any] = {
            "dimension": key.dimension.value,
            "concept_id": key.concept_id,
            "unit": metric_unit(key),
        }
        if key.group_id is not None:
            schema["group_id"] = key.group_id
        if key.qualifiers:
            schema["qualifiers"] = dict(key.qualifiers)
        metrics.append(schema)
    return metrics


def _accept_proposal(world: Any, source: CityRegion, proposal: dict[str, Any]) -> None:
    canonical_state = world.mechanical_language
    state = MechanicalLanguageState.from_dict(canonical_state.to_dict())
    state.bind_world(world)
    month = int(world.month_stamp)
    max_nodes = _guardrail(world, "semantic_max_ast_nodes", 32)
    max_depth = _guardrail(world, "semantic_max_ast_depth", 8)

    proposed_concepts = {
        _validate_id(raw["id"]): raw
        for raw in proposal.get("concepts", [])
        if isinstance(raw, dict)
    }
    accepted_metric_ids: set[str] = set()
    for raw in proposal.get("derived_metrics", []):
        definition_id = _validate_id(raw["id"])
        concept_id = _validate_id(raw["concept_id"])
        if concept_id not in proposed_concepts:
            raise ValueError("derived metric must reference a proposed concept")
        if str(raw["target_kind"]) != "region":
            raise ValueError("V1 discovery supports region targets only")
        expression = dict(raw["expression"])
        validate_expression(
            expression,
            max_nodes=max_nodes,
            max_depth=max_depth,
            target_kind="region",
        )
        candidate_definition = DerivedMetricDefinition(
            id=definition_id,
            concept_id=concept_id,
            dimension=PrimitiveDimension(str(raw["dimension"])),
            target_kind="region",
            expression=expression,
            unit=str(raw["unit"]),
            created_month=month,
            last_used_month=month,
        )
        reading = resolve_derived_metric(
            world,
            candidate_definition,
            target=source,
            calculated_month=month,
            definitions=state.derived_definitions,
        )
        if reading.availability is not MeasurementAvailability.MEASURABLE or reading.value is None:
            raise ValueError("a derived metric must be grounded by measurable inputs")
        structural_id = _find_structural_metric(state, expression, "region")
        if structural_id is not None:
            accepted_metric_ids.add(structural_id)
            continue
        definition = candidate_definition
        state.add_derived_definition(
            definition,
            max_nodes=max_nodes,
            max_depth=max_depth,
            # The proposal was already resolved against this concrete city
            # above.  Generic vocabulary is intentionally world-grounded at
            # acceptance time rather than hard-coded in the AST validator.
            allow_unresolved_leaves=True,
        )
        grounding_id = f"grounding:{definition_id}:region:{source.id}"
        state.groundings[grounding_id] = Grounding(
            id=grounding_id,
            concept_id=concept_id,
            subject_kind="region",
            subject_id=str(source.id),
            dimension=definition.dimension,
            metric_definition_id=definition.id,
            evidence_refs=tuple(reading.state_refs),
            status=GroundingStatus.GROUNDED,
            created_month=month,
        )
        concept_raw = proposed_concepts[concept_id]
        state.concepts[concept_id] = Concept(
            id=concept_id,
            label=str(concept_raw["label"]).strip(),
            concept_kind=str(concept_raw["concept_kind"]).strip(),
            grounding_status=GroundingStatus.GROUNDED,
            lifecycle=ConceptLifecycle.CANDIDATE,
            grounded_by=(grounding_id,),
            created_month=month,
            last_used_month=month,
        )
        accepted_metric_ids.add(definition_id)

    for raw in proposal.get("conditions", []):
        definition_id = _validate_id(raw["id"])
        concept_id = _validate_id(raw["concept_id"])
        metric_definition_id = _validate_id(raw["metric_definition_id"])
        if metric_definition_id not in accepted_metric_ids and metric_definition_id not in state.derived_definitions:
            raise ValueError("condition must reference an accepted metric definition")
        activate = float(raw["activate_above"])
        resolve = float(raw["resolve_below"])
        if not 0.0 <= resolve < activate <= 1.0 or activate - resolve < 0.05:
            raise ValueError("normalized condition thresholds require at least 0.05 hysteresis")
        state.add_condition_definition(ConditionDefinition(
            id=definition_id,
            concept_id=concept_id,
            target_kind="region",
            metric_definition_id=metric_definition_id,
            activate_above=activate,
            resolve_below=resolve,
            activate_after_months=int(raw["activate_after_months"]),
            resolve_after_months=int(raw["resolve_after_months"]),
            created_month=month,
        ))
        metric_definition = state.derived_definitions[metric_definition_id]
        grounding_id = f"grounding:{definition_id}:region:{source.id}"
        state.groundings[grounding_id] = Grounding(
            id=grounding_id,
            concept_id=concept_id,
            subject_kind="region",
            subject_id=str(source.id),
            dimension=metric_definition.dimension,
            metric_definition_id=metric_definition_id,
            evidence_refs=(f"derived_metric:{metric_definition_id}",),
            status=GroundingStatus.GROUNDED,
            created_month=month,
        )
        concept_raw = proposed_concepts[concept_id]
        state.concepts[concept_id] = Concept(
            id=concept_id,
            label=str(concept_raw["label"]).strip(),
            concept_kind=str(concept_raw["concept_kind"]).strip(),
            grounding_status=GroundingStatus.GROUNDED,
            lifecycle=ConceptLifecycle.CANDIDATE,
            grounded_by=(grounding_id,),
            created_month=month,
            last_used_month=month,
        )

    for raw in proposal.get("mechanic_proposals", []):
        mechanic = MechanicProposal(
            concept=str(raw.get("concept", "")).strip(),
            reason=str(raw.get("reason", "")).strip(),
            unmeasurable_keys=tuple(dict(item) for item in raw.get("unmeasurable_keys", [])),
            created_month=month,
        )
        state.mechanic_proposals[mechanic.id] = mechanic

    canonical_state.concepts = state.concepts
    canonical_state.groundings = state.groundings
    canonical_state.derived_definitions = state.derived_definitions
    canonical_state.condition_definitions = state.condition_definitions
    canonical_state.mechanic_proposals = state.mechanic_proposals


def _evaluate_condition(world: Any, region: CityRegion, definition: ConditionDefinition, reading) -> Event | None:
    state = world.mechanical_language
    month = int(world.month_stamp)
    streak_key = f"{definition.id}:region:{region.id}"
    streak = state.pending_streaks.setdefault(streak_key, {"activate": 0, "resolve": 0})
    previous_evaluated_month = streak.get("evaluated_month")
    if previous_evaluated_month != month:
        if (
            previous_evaluated_month is not None
            and month - int(previous_evaluated_month) != 1
        ):
            streak.update(activate=0, resolve=0)
        streak["activate_base"] = streak["activate"]
        streak["resolve_base"] = streak["resolve"]
        streak["evaluated_month"] = month
    active = next(
        (
            item
            for item in state.get_active_conditions(
                EntityRef("region", str(region.id)),
                month,
            )
            if item.definition_id == definition.id
        ),
        None,
    )
    if reading.value is None or reading.availability is not MeasurementAvailability.MEASURABLE:
        streak.update(activate=0, resolve=0)
        return None

    if active is None:
        streak["resolve"] = 0
        streak["activate"] = (
            streak["activate_base"] + 1
            if reading.value > definition.activate_above
            else 0
        )
        if streak["activate"] < definition.activate_after_months:
            return None
        streak["activate"] = 0
        event = Event(
            world.month_stamp,
            t("{region} entered the condition {condition}.", region=region.name, condition=_condition_label(state, definition)),
            related_avatars=None,
            is_major=False,
            event_type="semantic_condition_activated",
            render_params={"region_id": str(region.id), "condition_definition_id": definition.id},
            fact_kind=FactKind.DERIVED_CONDITION,
            causal_origin=CausalOrigin.DERIVED_CONDITION,
        )
        intensity = _condition_intensity(reading.value, definition.resolve_below)
        instance = ConditionInstance(
            id=str(uuid.uuid4()),
            definition_id=definition.id,
            target_kind="region",
            target_id=str(region.id),
            label=_condition_label(state, definition),
            intensity=intensity,
            started_month=month,
            cause_event_id=event.id,
            source_readings=(reading.to_dict(),),
        )
        state.add_condition_instance(instance)
        event.causal_payload = {
            "deltas": [StateDelta(
                event_id=event.id,
                owner_kind="region",
                owner_id=str(region.id),
                aspect=f"condition:{definition.id}",
                before=None,
                after=json.dumps(instance.to_dict(), ensure_ascii=False, sort_keys=True),
            ).to_dict()],
            "measurements": [reading.to_dict()],
        }
        event.causal_links.extend(_reading_links(event.id, reading.source_event_ids))
        return event

    streak["activate"] = 0
    streak["resolve"] = (
        streak["resolve_base"] + 1
        if month > active.started_month and reading.value < definition.resolve_below
        else 0
    )
    if streak["resolve"] < definition.resolve_after_months:
        return None
    streak["resolve"] = 0
    event = Event(
        world.month_stamp,
        t("{region} left the condition {condition}.", region=region.name, condition=active.label),
        related_avatars=None,
        is_major=False,
        event_type="semantic_condition_resolved",
        render_params={"region_id": str(region.id), "condition_definition_id": definition.id},
        fact_kind=FactKind.DERIVED_CONDITION,
        causal_origin=CausalOrigin.DERIVED_CONDITION,
    )
    resolved = replace(active, resolved_month=month, resolution_event_id=event.id)
    state.replace_condition_instance(resolved)
    event.causal_payload = {
        "deltas": [StateDelta(
            event_id=event.id,
            owner_kind="region",
            owner_id=str(region.id),
            aspect=f"condition:{definition.id}",
            before=json.dumps(active.to_dict(), ensure_ascii=False, sort_keys=True),
            after=json.dumps(resolved.to_dict(), ensure_ascii=False, sort_keys=True),
        ).to_dict()],
        "measurements": [reading.to_dict()],
    }
    event.causal_links.append(CausalLink(event_id=event.id, cause_event_id=active.cause_event_id, relation=CausalRelation.RESOLVES))
    event.causal_links.extend(_reading_links(event.id, reading.source_event_ids))
    return event


def _record_reuse(definition: DerivedMetricDefinition, target: CityRegion, month: int) -> DerivedMetricDefinition:
    contexts = tuple(dict.fromkeys((*definition.reuse_contexts, f"region:{target.id}")))
    lifecycle = ConceptLifecycle.ACTIVE if len(contexts) >= 2 else definition.lifecycle
    return replace(definition, reuse_contexts=contexts, lifecycle=lifecycle, last_used_month=month)


def _promote_for_consequence(state, metric_id: str, condition_id: str, month: int) -> None:
    metric = state.derived_definitions[metric_id]
    state.derived_definitions[metric_id] = replace(metric, lifecycle=ConceptLifecycle.ACTIVE, last_used_month=month)
    condition = state.condition_definitions[condition_id]
    state.condition_definitions[condition_id] = replace(condition, lifecycle=ConceptLifecycle.ACTIVE)
    for concept_id in {metric.concept_id, condition.concept_id}:
        concept = state.concepts.get(concept_id)
        if concept is not None:
            state.concepts[concept_id] = replace(concept, lifecycle=ConceptLifecycle.ACTIVE, last_used_month=month)


def _apply_dormancy(world: Any, month: int) -> None:
    after = _guardrail(world, "semantic_dormant_after_months", 24)
    state = world.mechanical_language
    for definition_id, definition in list(state.derived_definitions.items()):
        if definition.lifecycle is ConceptLifecycle.CANDIDATE and month - definition.last_used_month >= after:
            state.derived_definitions[definition_id] = replace(definition, lifecycle=ConceptLifecycle.DORMANT)


def _reading_links(event_id: str, source_event_ids: list[str]) -> list[CausalLink]:
    return [CausalLink(event_id=event_id, cause_event_id=source_id, relation=CausalRelation.ENABLED_BY) for source_id in dict.fromkeys(source_event_ids)]


def _condition_has_pending_streak(
    state: MechanicalLanguageState,
    definition: ConditionDefinition,
    region: CityRegion,
) -> bool:
    streak = state.pending_streaks.get(
        f"{definition.id}:region:{region.id}",
        {},
    )
    return int(streak.get("activate", 0)) > 0 or int(streak.get("resolve", 0)) > 0


def _definition_has_pending_streak(
    state: MechanicalLanguageState,
    definition_id: str,
    region: CityRegion,
) -> bool:
    return any(
        condition.metric_definition_id == definition_id
        and _condition_has_pending_streak(state, condition, region)
        for condition in state.condition_definitions.values()
    )


def _definition_source_affinities(
    state: MechanicalLanguageState,
    definition_id: str,
    city: CityRegion,
) -> set[str]:
    from src.systems.semantic_world.condition_semantics import metric_leaves

    definition = state.derived_definitions[definition_id]
    affinities: set[str] = set()
    for leaf in metric_leaves(definition.expression, state.derived_definitions):
        kind = dict(leaf.get("qualifiers", {})).get("kind")
        if kind == "collective_health":
            affinities.add("collective_health")
        elif kind in {
            "spiritual_anchor_ratio",
            "spiritual_anchors",
            "spiritual_grave_presence",
            "spiritual_formation_presence",
            "spiritual_treasure_presence",
        }:
            affinities.add("spiritual_ecology")
        elif kind == "urban_service":
            concept_id = str(leaf.get("concept_id", "")).strip()
            if concept_id:
                affinities.add(f"urban_service:{concept_id}")
        elif (
            not kind
            and leaf.get("dimension") == PrimitiveDimension.QUALITY.value
        ):
            concept_id = str(leaf.get("concept_id", "")).strip()
            if concept_id and any(
                concept_id in asset.capability_ids
                for asset in city.city_state.assets
            ):
                affinities.add(f"urban_service:{concept_id}")
    return affinities


def _condition_label(state, definition: ConditionDefinition) -> str:
    concept = state.concepts.get(definition.concept_id)
    return concept.label if concept is not None else definition.concept_id


def _condition_intensity(value: float, baseline: float) -> float:
    return max(0.0, min(1.0, (value - baseline) / max(0.000001, 1.0 - baseline)))


def _find_structural_metric(state, expression: dict[str, Any], target_kind: str) -> str | None:
    target_hash = _structural_hash(expression, target_kind)
    for definition in state.derived_definitions.values():
        if _structural_hash(definition.expression, definition.target_kind) == target_hash:
            return definition.id
    return None


def _metric_leaf_signature(node: dict[str, Any]) -> tuple[Any, ...]:
    qualifiers = tuple(
        sorted(
            (str(name), str(value))
            for name, value in dict(node.get("qualifiers", {})).items()
        )
    )
    return (
        PrimitiveDimension(str(node["dimension"])),
        str(node["concept_id"]),
        str(node["group_id"]) if node.get("group_id") is not None else None,
        qualifiers,
    )


def _covered_metric_signatures(
    state: MechanicalLanguageState,
) -> set[tuple[Any, ...]]:
    covered: set[tuple[Any, ...]] = set()
    for definition in state.derived_definitions.values():
        stack = [definition.expression]
        while stack:
            node = stack.pop()
            if node.get("op") == "metric":
                covered.add(_metric_leaf_signature(node))
            stack.extend(_expression_children(node))
    return covered


def _uncovered_metric_keys(
    world: Any,
    state: MechanicalLanguageState,
    city: CityRegion,
) -> list[Any]:
    covered = _covered_metric_signatures(state)
    health_view = project_collective_health(world, city.id)
    has_active_health_signal = bool(
        health_view.active_wounded_count.value is not None
        and health_view.active_wounded_count.value > 0
    )
    keys = [*available_metric_keys(city)]
    keys.extend(
        key
        for key in spiritual_metric_keys(world, city.id)
        if key.concept_id == SPIRITUAL_ANCHOR_RATIO_CONCEPT
    )
    return [
        key
        for key in keys
        if (
            key.dimension,
            key.concept_id,
            key.group_id,
            key.qualifiers,
        ) not in covered
        and (
            dict(key.qualifiers).get("kind") != "collective_health"
            or has_active_health_signal
        )
    ]


def _discovery_surface_key(keys: list[Any]) -> str:
    payload = [
        {
            "dimension": key.dimension.value,
            "concept_id": key.concept_id,
            "group_id": key.group_id,
            "qualifiers": dict(key.qualifiers),
            "unit": metric_unit(key),
        }
        for key in keys
    ]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return f"metric_surface:{digest}"


def _expression_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    op = node.get("op")
    if op in {"add", "subtract", "multiply", "divide", "min", "max"}:
        return [child for child in (node.get("left"), node.get("right")) if isinstance(child, dict)]
    if op == "clamp":
        return [node["value"]] if isinstance(node.get("value"), dict) else []
    if op == "weighted_sum":
        return [item["expression"] for item in node.get("items", []) if isinstance(item, dict) and isinstance(item.get("expression"), dict)]
    return []


def _structural_hash(expression: dict[str, Any], target_kind: str) -> str:
    payload = json.dumps({"target_kind": target_kind, "expression": expression}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_id(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if not _ID_PATTERN.fullmatch(normalized):
        raise ValueError(f"invalid semantic id: {value}")
    return normalized


def _target_ref(region: CityRegion) -> str:
    return f"region:{region.id}"


def _evaluation_key(definition_id: str, region: CityRegion) -> str:
    return f"{definition_id}|{_target_ref(region)}"


def _fingerprint(world: Any, region: CityRegion) -> str:
    spiritual = project_spiritual_ecology(world, region.id)
    payload = {
        "population": region.population,
        "population_capacity": region.population_capacity,
        "economy": region.economy.to_dict(),
        "infrastructure": region.infrastructure.to_dict(),
        "city_state": region.city_state.to_dict(),
        "collective_health": project_collective_health(world, region.id).to_dict(),
        "spiritual_anchors": {
            "formations": [item.to_dict() for item in spiritual.formations],
            "graves": [item.to_dict() for item in spiritual.graves],
            "treasures": [item.to_dict() for item in spiritual.treasures],
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _settlement_ratio(region: CityRegion) -> float:
    return region.population / region.population_capacity if region.population_capacity > 0 else 0.0


def _guardrail(world: Any, name: str, default: int) -> int:
    snapshot = getattr(world, "run_config_snapshot", {}) or {}
    try:
        return max(0, int(snapshot.get(name, default)))
    except (TypeError, ValueError):
        return default


def _discovery_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["concepts", "derived_metrics", "conditions", "mechanic_proposals"],
        "properties": {
            "concepts": {"type": "array", "items": {"type": "object"}},
            "derived_metrics": {"type": "array", "items": {"type": "object"}},
            "conditions": {"type": "array", "items": {"type": "object"}},
            "mechanic_proposals": {"type": "array", "items": {"type": "object"}},
        },
    }

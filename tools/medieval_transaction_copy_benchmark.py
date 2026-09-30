"""Reproducible RelationsState transaction-copy diagnostic (E347).

This is deliberately a benchmark, not a production optimization.  The
fixture is synthetic: it creates independent, model-valid registry values and
does not represent a natural world, provider behavior, or cross-owner
validation.
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import sys
import time
from dataclasses import fields, is_dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel, ConfigDict, PrivateAttr

from src.classes.governance.diplomacy import (
    DiplomaticProposal,
    InstitutionalMemory,
    Obligation,
    RelationsState,
    TeachingClause,
)
from src.classes.mechanical_language import EntityRef
from src.classes.core.medieval_world import _copy_transaction_container


CARDINALITIES = {"proposals": 1279, "obligations": 181, "memories": 381}
REPEATS = 5


def _synthetic_relations() -> RelationsState:
    """Build independently-created, model-valid synthetic registry values."""
    proposals = {}
    for index in range(CARDINALITIES["proposals"]):
        proposer = EntityRef("polity", f"synthetic-proposer-{index}")
        counterparty = EntityRef("polity", f"synthetic-counterparty-{index}")
        clause = TeachingClause(
            debtor_ref=proposer,
            creditor_ref=counterparty,
            due_day=12,
            technology_id=f"technology-{index}",
        )
        proposal = DiplomaticProposal(
            id=f"proposal:synthetic:{index}",
            proposer_ref=proposer,
            counterparty_ref=counterparty,
            clauses=(clause,),
            offered_day=0,
            expires_day=7,
            decision_event_id=f"event:proposal:{index}",
            last_event_id=f"event:proposal:{index}:last",
        )
        proposals[proposal.id] = proposal

    obligations = {}
    for index in range(CARDINALITIES["obligations"]):
        obligation = Obligation(
            id=f"obligation:synthetic:{index}",
            proposal_id=f"proposal:synthetic:{index}",
            clause_index=0,
            last_event_id=f"event:obligation:{index}",
        )
        obligations[obligation.id] = obligation

    memories = {}
    for index in range(CARDINALITIES["memories"]):
        memory = InstitutionalMemory(
            id=f"memory:synthetic:{index}",
            institution_ref=EntityRef("polity", f"synthetic-institution-{index}"),
            event_id=f"event:memory:{index}",
            recorded_day=1,
            last_reinforced_day=1,
        )
        memories[memory.id] = memory
    return RelationsState(proposals=proposals, obligations=obligations, memories=memories)


def _baseline_copy_value(value, *, share_values=False):
    """In-tool copy of the pre-change helper, retained for a real comparison."""
    if isinstance(value, dict):
        return {key: _baseline_copy_value(item, share_values=share_values)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_baseline_copy_value(item, share_values=share_values) for item in value]
    if isinstance(value, set):
        return {_baseline_copy_value(item, share_values=share_values) for item in value}
    if isinstance(value, tuple):
        if all(isinstance(item, (str, int, float, bool, type(None), bytes)) for item in value):
            return value
        return tuple(_baseline_copy_value(item, share_values=share_values) for item in value)
    if isinstance(value, frozenset):
        if all(isinstance(item, (str, int, float, bool, type(None), bytes)) for item in value):
            return value
        return frozenset(_baseline_copy_value(item, share_values=share_values) for item in value)
    if hasattr(value, "__pydantic_fields__") and hasattr(value, "__dict__"):
        if share_values:
            return value
        result = copy.copy(value)
        for key, item in value.__dict__.items():
            object.__setattr__(result, key, _baseline_copy_value(item, share_values=share_values))
        for attribute in ("__pydantic_extra__", "__pydantic_private__"):
            payload = getattr(value, attribute, None)
            if payload is not None:
                object.__setattr__(result, attribute, _baseline_copy_value(
                    payload, share_values=share_values))
        return result
    return value


def _baseline_copy_container(value, *, share_values=False):
    if not is_dataclass(value):
        return copy.deepcopy(value)
    result = copy.copy(value)
    for item in fields(value):
        setattr(result, item.name, _baseline_copy_value(
            getattr(value, item.name), share_values=share_values))
    bind = getattr(result, "_bind_registry_epoch", None)
    if bind is not None:
        bind(preserve_query=True)
    return result


def _prototype_copy_value(value):
    """Prototype: recurse only where a mutable/model payload needs cloning."""
    if isinstance(value, dict):
        return {key: _prototype_copy_value(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_prototype_copy_value(item) for item in value]
    if isinstance(value, set):
        return {_prototype_copy_value(item) for item in value}
    if isinstance(value, tuple):
        if all(isinstance(item, (str, int, float, bool, type(None), bytes)) for item in value):
            return value
        return tuple(_prototype_copy_value(item) for item in value)
    if isinstance(value, frozenset):
        if all(isinstance(item, (str, int, float, bool, type(None), bytes)) for item in value):
            return value
        return frozenset(_prototype_copy_value(item) for item in value)
    if hasattr(value, "__pydantic_fields__") and hasattr(value, "__dict__"):
        result = copy.copy(value)
        for key, item in value.__dict__.items():
            if (isinstance(item, (dict, list, set, tuple, frozenset))
                    or (hasattr(item, "__pydantic_fields__") and hasattr(item, "__dict__"))):
                object.__setattr__(result, key, _prototype_copy_value(item))
        for attribute in ("__pydantic_extra__", "__pydantic_private__"):
            payload = getattr(value, attribute, None)
            if payload is not None:
                object.__setattr__(result, attribute, _prototype_copy_value(payload))
        return result
    return value


def _prototype_copy_container(value):
    if not is_dataclass(value):
        return _prototype_copy_value(value)
    result = copy.copy(value)
    for item in fields(value):
        current = getattr(value, item.name)
        setattr(result, item.name, _prototype_copy_value(current))
    bind = getattr(result, "_bind_registry_epoch", None)
    if bind is not None:
        bind(preserve_query=True)
    return result


def _serialized(state: RelationsState) -> dict:
    return state.to_dict()


class _EdgeModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")
    scalar: int
    nested: list[int]
    _private: dict[str, object] = PrivateAttr(default_factory=dict)


def _check_isolation(source: RelationsState, copier) -> None:
    copied = copier(source)
    assert copied is not source
    for name in ("proposals", "obligations", "memories"):
        source_registry = getattr(source, name)
        copied_registry = getattr(copied, name)
        assert copied_registry is not source_registry
        assert all(copied_registry[key] is not value
                   for key, value in source_registry.items())

    proposal = next(iter(source.proposals.values()))
    invalid = proposal.model_copy(update={"parent_id": []})
    invalid_source = RelationsState(proposals={invalid.id: invalid})
    invalid_copy = copier(invalid_source).proposals[proposal.id]
    assert invalid_copy.parent_id == []
    assert invalid_copy.parent_id is not invalid.parent_id

    edge = _EdgeModel(scalar=3, nested=[3], payload={})
    edge._private["empty"] = {}
    edge_copy = copier({"edge": edge})["edge"]
    edge_copy.nested.append(4)
    edge_copy.payload["candidate"] = 4
    edge_copy._private["empty"]["candidate"] = 4
    assert edge.nested == [3]
    assert edge.payload == {}
    assert edge._private == {"empty": {}}


def _measure_once(source: RelationsState, copier) -> dict[str, float]:
    cpu_start = time.process_time_ns()
    wall_start = time.perf_counter_ns()
    copied = copier(source)
    sample = {
        "cpu_seconds": (time.process_time_ns() - cpu_start) / 1e9,
        "wall_seconds": (time.perf_counter_ns() - wall_start) / 1e9,
    }
    assert _serialized(copied) == _serialized(source)
    return sample


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = _synthetic_relations()
    source_serialized = _serialized(source)
    production_serialized = _serialized(_copy_transaction_container(source))
    _check_isolation(source, _copy_transaction_container)
    _check_isolation(source, _baseline_copy_container)
    _check_isolation(source, _prototype_copy_container)

    # Alternate variants to reduce drift from one-sided process warmup/load.
    measurements = {"baseline": [], "prototype": []}
    baseline_serialized = None
    prototype_serialized = None
    for index in range(REPEATS):
        variant_order = ("baseline", "prototype") if index % 2 == 0 else ("prototype", "baseline")
        for variant in variant_order:
            copier = (_baseline_copy_container if variant == "baseline"
                      else _prototype_copy_container)
            copied = copier(source)
            if variant == "baseline":
                baseline_serialized = _serialized(copied)
            else:
                prototype_serialized = _serialized(copied)
            measurements[variant].append(_measure_once(source, copier))

    summary = {}
    for variant, samples in measurements.items():
        summary[variant] = {
            "raw": samples,
            "median_cpu_seconds": statistics.median(item["cpu_seconds"] for item in samples),
            "median_wall_seconds": statistics.median(item["wall_seconds"] for item in samples),
        }

    result = {
        "benchmark": "medieval_transaction_copy_relations_e347",
        "fixture": "synthetic model-valid independently-created RelationsState; not natural/provider/cross-owner validation",
        "cardinalities": CARDINALITIES,
        "repeats_per_variant": REPEATS,
        "data_equal": (production_serialized == baseline_serialized
                        == prototype_serialized == source_serialized),
        "checks": {
            "top_models_independent": True,
            "nested_extra_private_empty_dict_isolated": True,
            "invalid_scalar_list_injected_by_model_copy_isolated": True,
        },
        "measurements": summary,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

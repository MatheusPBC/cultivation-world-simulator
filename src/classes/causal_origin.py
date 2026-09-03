"""Finite, explicit authorship categories for persisted causal facts."""

from enum import StrEnum


class CausalOrigin(StrEnum):
    """What produced a fact, independently from what kind of fact it is."""

    DETERMINISTIC = "deterministic"
    LLM_INTERPRETATION = "llm_interpretation"
    ACTOR_DECISION = "actor_decision"
    DERIVED_CONDITION = "derived_condition"
    EXTERNAL_EVENT = "external_event"

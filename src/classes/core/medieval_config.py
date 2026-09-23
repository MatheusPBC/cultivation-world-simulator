"""Persistent configuration of a medieval run, independent of provider secrets."""

from typing import Literal
from pydantic import Field
from src.classes.society.models import SocietyValue


class MedievalRunConfig(SocietyValue):
    """Rules of one run. Provider keys, models and URLs never live here."""
    seed: int = Field(default=73, strict=True, ge=0, le=2**32 - 1)
    character_count: int = Field(default=12, strict=True, ge=1, le=60)
    locale: Literal["pt-BR"] = "pt-BR"
    decision_policy: Literal["routine-rules"] = "routine-rules"
    ai_enabled: bool = False
    # The budget is per simulation step, not per actor.  The composed
    # institutional boundary can legitimately contain polities, organizations
    # and population groups, so the schema must allow a fixture/provider to
    # fund all current actors while still permitting small explicit budgets for
    # fail-closed tests and constrained runs.
    ai_calls_per_step: int = Field(default=1, strict=True, ge=0, le=256)
    ai_max_calls: int = Field(default=0, strict=True, ge=0, le=10000)
    # An explicit, per-institution monthly ceiling on top of the shared daily
    # budget above: 0 means no ceiling (unchanged behaviour). It bounds how
    # many times one actor may consult a provider in one calendar month,
    # counting every attempt -- success, explicit NO_ACTION or technical
    # failure alike -- because the ceiling is about a sustainable pace of
    # asking, not about how often the answer happened to be useful.
    institutional_actions_per_month: int = Field(default=0, strict=True, ge=0, le=1000)
    # Consumption ledger keyed by ``f"{actor.kind}:{actor.id}:{month_index}"``.
    # Old months are never pruned; the map only ever grows, which is
    # acceptable for a V1 policy counter and avoids guessing which months are
    # safe to forget.
    institutional_actions_consumed: dict[str, int] = Field(default_factory=dict)

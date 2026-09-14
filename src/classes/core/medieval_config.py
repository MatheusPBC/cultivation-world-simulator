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
    ai_calls_per_step: int = Field(default=1, strict=True, ge=0, le=8)
    ai_max_calls: int = Field(default=0, strict=True, ge=0, le=10000)

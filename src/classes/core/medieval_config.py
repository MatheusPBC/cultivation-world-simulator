"""Persistent configuration of a medieval run, independent of provider secrets."""

from typing import Literal
from pydantic import Field
from src.classes.society.models import SocietyValue


class MedievalRunConfig(SocietyValue):
    seed: int = Field(default=73, strict=True, ge=0, le=2**32 - 1)
    character_count: int = Field(default=12, strict=True, ge=1, le=60)
    locale: Literal["pt-BR"] = "pt-BR"
    decision_policy: Literal["routine-rules"] = "routine-rules"

"""
A direct participant's personal, immutable interpretation of an `Event`.

`EventAppraisal` is historical residue, not a second execution path: it
never rewrites the source `Event`, and later reconciliation, betrayal,
rescue, or loss creates another appraisal rather than mutating this one.
Positive and negative appraisals of different events may coexist for the
same appraiser/focus pair.

See docs/specs/personal-appraisal-politics.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time
import uuid

from src.classes.emotions import EmotionType

# Half-life of an appraisal's age decay, in months (10 years).
_AGE_DECAY_HALF_LIFE_MONTHS = 120
MAX_APPRAISAL_SUMMARY_LENGTH = 240


class AppraisalSource(Enum):
    LLM = "llm"
    RULE = "rule"


@dataclass(frozen=True)
class ScoredEventAppraisal:
    """An appraisal together with the read-time facts needed to display it.

    `effective_weight` and the source event's date are *derived* at query
    time from the source `Event`'s `month_stamp`; neither is stored on the
    appraisal row, so this view exists to avoid every caller re-deriving
    (and re-deciding) them. `EventStorage` stays the sole owner.
    """

    appraisal: "EventAppraisal"
    source_event_month_stamp: int
    effective_weight: float


@dataclass(frozen=True)
class EventAppraisal:
    event_id: str
    appraiser_avatar_id: str
    focus_avatar_id: str
    personal_importance: float
    valence: float
    persistence: float
    primary_emotion: EmotionType
    summary: str
    source: AppraisalSource = AppraisalSource.RULE
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not 0.0 <= self.personal_importance <= 1.0:
            raise ValueError(
                f"personal_importance must be within [0, 1], got {self.personal_importance!r}"
            )
        if not -1.0 <= self.valence <= 1.0:
            raise ValueError(f"valence must be within [-1, 1], got {self.valence!r}")
        if not 0.0 <= self.persistence <= 1.0:
            raise ValueError(f"persistence must be within [0, 1], got {self.persistence!r}")
        if len(self.summary) > MAX_APPRAISAL_SUMMARY_LENGTH:
            raise ValueError(
                f"summary must be at most {MAX_APPRAISAL_SUMMARY_LENGTH} characters, "
                f"got {len(self.summary)}"
            )
        if not isinstance(self.primary_emotion, EmotionType):
            raise TypeError(f"primary_emotion must be an EmotionType, got {self.primary_emotion!r}")
        if not isinstance(self.source, AppraisalSource):
            raise TypeError(f"source must be an AppraisalSource, got {self.source!r}")

    def effective_weight(self, age_months: int) -> float:
        """Current influence of this appraisal, decaying with age.

        `age_months` is the number of months between the source event and
        the date being evaluated at; callers derive it from the event's
        `month_stamp`, since the appraisal itself does not track the
        source event's date. Evaluating at a date before the source event
        is a caller error, not a valid state, so it is rejected rather
        than silently clamped to zero.
        """
        if age_months < 0:
            raise ValueError(f"age_months must be non-negative, got {age_months!r}")
        age_decay = 0.5 ** (age_months / _AGE_DECAY_HALF_LIFE_MONTHS)
        return self.personal_importance * (
            self.persistence + (1 - self.persistence) * age_decay
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "appraiser_avatar_id": self.appraiser_avatar_id,
            "focus_avatar_id": self.focus_avatar_id,
            "personal_importance": self.personal_importance,
            "valence": self.valence,
            "persistence": self.persistence,
            "primary_emotion": self.primary_emotion.value,
            "summary": self.summary,
            "source": self.source.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventAppraisal":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            event_id=data["event_id"],
            appraiser_avatar_id=data["appraiser_avatar_id"],
            focus_avatar_id=data["focus_avatar_id"],
            personal_importance=data["personal_importance"],
            valence=data["valence"],
            persistence=data["persistence"],
            primary_emotion=EmotionType(data["primary_emotion"]),
            summary=data["summary"],
            source=AppraisalSource(data.get("source", AppraisalSource.RULE.value)),
            created_at=data.get("created_at", time.time()),
        )

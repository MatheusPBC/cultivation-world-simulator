"""
Audit record for one agent decision.

Carried inside a `fact_kind=DECISION` `Event`'s `causal_payload["decision"]`
(see `src/classes/event.py`). This is an audit trail only -- nothing in the
simulator may read it back to make a decision; `thinking` and
`short_term_objective` stay owned by `Avatar` and are only copied here.

See docs/specs/causal-world-kernel.md section 5.4.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass
class AgentDecision:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    month_stamp: int = 0
    subject_kind: str = "avatar"      # "avatar" | "sect"
    subject_id: str = ""
    source: str = "llm"               # mirrors single_choice.ChoiceSource
    considered_count: int = 0         # how many actions were offered
    # [{"action_name": ..., "params": {...}}, ...] -- mirrors ActionPlan.to_dict()
    chosen_chain: list[dict[str, Any]] = field(default_factory=list)
    thinking: str = ""
    short_term_objective: str = ""
    # [{"action_name": ..., "params": {...}, "reason": ...}] captured at
    # Avatar.commit_next_plan, the only place can_start(**params) runs.
    rejected: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "month_stamp": self.month_stamp,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "source": self.source,
            "considered_count": self.considered_count,
            "chosen_chain": self.chosen_chain,
            "thinking": self.thinking,
            "short_term_objective": self.short_term_objective,
            "rejected": self.rejected,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentDecision":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            month_stamp=data.get("month_stamp", 0),
            subject_kind=data.get("subject_kind", "avatar"),
            subject_id=data.get("subject_id", ""),
            source=data.get("source", "llm"),
            considered_count=data.get("considered_count", 0),
            chosen_chain=list(data.get("chosen_chain") or []),
            thinking=data.get("thinking", ""),
            short_term_objective=data.get("short_term_objective", ""),
            rejected=list(data.get("rejected") or []),
        )

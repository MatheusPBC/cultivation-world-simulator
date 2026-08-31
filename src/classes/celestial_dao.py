"""Persistent domain state for the player's Celestial Dao."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
import uuid


class DaoTradition(StrEnum):
    MANDATE_AND_ORDER = "mandate_and_order"
    BALANCE = "balance"
    MERCY = "mercy"
    TRANSCENDENCE = "transcendence"


class DaoPetitionStatus(StrEnum):
    PENDING = "pending"
    SILENCED = "silenced"
    SIGNED = "signed"
    FAVORED = "favored"


@dataclass
class DaoPetition:
    initiator_kind: str
    initiator_id: str
    region_id: int
    tradition: DaoTradition
    motivated_event_ids: list[str] = field(default_factory=list)
    content: str = ""
    created_month: int = 0
    status: DaoPetitionStatus = DaoPetitionStatus.PENDING
    response_event_id: str = ""
    favor_expires_month: int | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "initiator_kind": self.initiator_kind, "initiator_id": self.initiator_id, "region_id": self.region_id, "tradition": self.tradition.value, "motivated_event_ids": list(self.motivated_event_ids), "content": self.content, "created_month": self.created_month, "status": self.status.value, "response_event_id": self.response_event_id, "favor_expires_month": self.favor_expires_month}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DaoPetition":
        return cls(id=str(data["id"]), initiator_kind=str(data["initiator_kind"]), initiator_id=str(data["initiator_id"]), region_id=int(data["region_id"]), tradition=DaoTradition(data["tradition"]), motivated_event_ids=[str(x) for x in data.get("motivated_event_ids", [])], content=str(data.get("content", "")), created_month=int(data.get("created_month", 0)), status=DaoPetitionStatus(data.get("status", DaoPetitionStatus.PENDING)), response_event_id=str(data.get("response_event_id", "")), favor_expires_month=data.get("favor_expires_month"))

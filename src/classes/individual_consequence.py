"""Persistent semantic consequences owned by an individual avatar."""
from __future__ import annotations

from dataclasses import dataclass, field


MAX_RECENT_RESOLVED = 8


@dataclass
class IndividualInjury:
    severity: str
    started_month: int
    hp_lost: int
    cause_event_ids: list[str] = field(default_factory=list)
    salience: float = 0.0

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "started_month": self.started_month,
            "hp_lost": self.hp_lost,
            "cause_event_ids": list(self.cause_event_ids),
            "salience": self.salience,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IndividualInjury":
        return cls(
            severity=str(data.get("severity", "moderate")),
            started_month=int(data.get("started_month", 0)),
            hp_lost=int(data.get("hp_lost", 0)),
            cause_event_ids=[str(value) for value in data.get("cause_event_ids", [])],
            salience=float(data.get("salience", 0.0)),
        )


@dataclass
class IndividualConsequenceState:
    active_injury: IndividualInjury | None = None
    recent_resolved: list[dict] = field(default_factory=list)

    @property
    def derived_priority(self) -> str:
        return "recover" if self.active_injury is not None else ""

    def record_injury(self, *, month: int, max_hp: int, damage: int, cause_event_id: str) -> bool:
        if max_hp <= 0 or damage / max_hp < 0.25:
            return False
        severity = "severe" if damage / max_hp >= 0.50 else "moderate"
        if self.active_injury is None:
            self.active_injury = IndividualInjury(
                severity=severity,
                started_month=month,
                hp_lost=damage,
                cause_event_ids=[cause_event_id],
                salience=damage / max_hp,
            )
            return True
        injury = self.active_injury
        injury.hp_lost += damage
        injury.salience = min(1.0, injury.salience + damage / max_hp)
        if severity == "severe":
            injury.severity = "severe"
        if cause_event_id and cause_event_id not in injury.cause_event_ids:
            injury.cause_event_ids.append(cause_event_id)
        return True

    def resolve_if_recovered(self, *, month: int, current_hp: int, max_hp: int) -> dict | None:
        if self.active_injury is None or current_hp < max_hp:
            return None
        summary = self.active_injury.to_dict() | {"resolved_month": month}
        self.recent_resolved.insert(0, summary)
        del self.recent_resolved[MAX_RECENT_RESOLVED:]
        self.active_injury = None
        return summary

    def to_dict(self) -> dict:
        return {
            "active_injury": self.active_injury.to_dict() if self.active_injury else None,
            "recent_resolved": list(self.recent_resolved),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "IndividualConsequenceState":
        data = data or {}
        injury = data.get("active_injury")
        return cls(
            active_injury=IndividualInjury.from_dict(injury) if isinstance(injury, dict) else None,
            recent_resolved=list(data.get("recent_resolved", []))[:MAX_RECENT_RESOLVED],
        )


def record_injury_from_event(avatar, event, damage: int) -> bool:
    """Record a material non-fatal injury and append evidence to its source event."""
    if damage <= 0 or getattr(avatar, "is_dead", False) or getattr(avatar.hp, "cur", 0) <= 0:
        return False
    state = avatar.individual_consequences
    before = state.active_injury.to_dict() if state.active_injury else None
    recorded = state.record_injury(
        month=int(avatar.world.month_stamp),
        max_hp=int(avatar.hp.max),
        damage=int(damage),
        cause_event_id=event.id,
    )
    if not recorded:
        return False

    from src.classes.state_delta import StateDelta
    _append_event_delta(event, StateDelta(
        event_id=event.id,
        owner_kind="avatar",
        owner_id=str(avatar.id),
        aspect="active_injury",
        before=str(before) if before else None,
        after=str(state.active_injury.to_dict()),
        magnitude=float(damage),
    ))
    return True


def record_hp_change_from_event(avatar, event, before_hp: int) -> bool:
    """Attach the real HP transition and, when applicable, its V1 injury evidence."""
    hp = getattr(avatar, "hp", None)
    after_hp = getattr(hp, "cur", None)
    if after_hp is None:
        return False

    before_hp = int(before_hp)
    after_hp = int(after_hp)
    if before_hp == after_hp:
        return False
    if _event_has_delta(event, str(avatar.id), "hp"):
        return False

    from src.classes.state_delta import StateDelta
    _append_event_delta(event, StateDelta(
        event_id=event.id,
        owner_kind="avatar",
        owner_id=str(avatar.id),
        aspect="hp",
        before=str(before_hp),
        after=str(after_hp),
        magnitude=float(after_hp - before_hp),
    ))

    damage = before_hp - after_hp
    if damage > 0 and after_hp > 0:
        record_injury_from_event(avatar, event, damage)
    return True


def _append_event_delta(event, delta) -> None:
    payload = dict(event.causal_payload or {})
    deltas = payload.setdefault("deltas", [])
    if not isinstance(deltas, list):
        deltas = []
        payload["deltas"] = deltas
    delta_data = delta.to_dict()
    duplicate = any(
        item.get("owner_kind") == delta_data["owner_kind"]
        and item.get("owner_id") == delta_data["owner_id"]
        and item.get("aspect") == delta_data["aspect"]
        for item in deltas
        if isinstance(item, dict)
    )
    if not duplicate:
        deltas.append(delta_data)
    event.causal_payload = payload


def _event_has_delta(event, owner_id: str, aspect: str) -> bool:
    payload = event.causal_payload or {}
    return any(
        item.get("owner_id") == owner_id and item.get("aspect") == aspect
        for item in payload.get("deltas", [])
        if isinstance(item, dict)
    )

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ScheduledSituation:
    """A named world situation that needs resolution on one absolute day."""

    id: str
    kind: str
    due_day: int

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("situation id must be a non-empty string")
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("situation kind must be a non-empty string")
        if isinstance(self.due_day, bool) or not isinstance(self.due_day, int):
            raise TypeError("situation due_day must be an integer")
        if self.due_day < 0:
            raise ValueError("situation due_day must not be negative")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "due_day": self.due_day}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduledSituation":
        if not isinstance(data, dict):
            raise TypeError("scheduled situation must be an object")
        return cls(
            id=data.get("id"),
            kind=data.get("kind"),
            due_day=data.get("due_day"),
        )


@dataclass(slots=True)
class WorldAgenda:
    """Canonical pending work that can interrupt otherwise monthly simulation."""

    _situations: dict[str, ScheduledSituation] = field(default_factory=dict)

    @property
    def due_days(self) -> tuple[int, ...]:
        return tuple(sorted(situation.due_day for situation in self._situations.values()))

    def get(self, situation_id: str) -> ScheduledSituation | None:
        return self._situations.get(situation_id)

    def schedule(self, situation: ScheduledSituation) -> None:
        if not isinstance(situation, ScheduledSituation):
            raise TypeError("agenda accepts ScheduledSituation instances")
        if situation.id in self._situations:
            raise ValueError(f"situation {situation.id!r} is already scheduled")
        self._situations[situation.id] = situation

    def pop_due(self, day: int) -> tuple[ScheduledSituation, ...]:
        if isinstance(day, bool) or not isinstance(day, int):
            raise TypeError("day must be an integer")
        due = tuple(
            sorted(
                (situation for situation in self._situations.values() if situation.due_day == day),
                key=lambda situation: situation.id,
            )
        )
        for situation in due:
            del self._situations[situation.id]
        return due

    def to_dict(self) -> list[dict[str, Any]]:
        return [
            situation.to_dict()
            for situation in sorted(self._situations.values(), key=lambda item: item.id)
        ]

    @classmethod
    def from_dict(cls, data: object) -> "WorldAgenda":
        if data is None:
            return cls()
        if not isinstance(data, list):
            raise TypeError("agenda must be a list")
        agenda = cls()
        for item in data:
            agenda.schedule(ScheduledSituation.from_dict(item))
        return agenda

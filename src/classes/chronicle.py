"""Immutable, JSON-pure values used by the World Chronicle projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping


ChronicleTrigger = Literal["major_event", "max_interval"]
ChronicleClaimKind = Literal["fact", "inference"]
ChronicleReferenceKind = Literal["avatar", "sect", "region", "event"]

_TRIGGERS = {"major_event", "max_interval"}
_CLAIM_KINDS = {"fact", "inference"}
_REFERENCE_KINDS = {"avatar", "sect", "region", "event"}


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _ids(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} must be a list of strings")
    result = tuple(_text(item, field) for item in value)
    if not allow_empty and not result:
        raise ValueError(f"{field} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{field} must not contain duplicate IDs")
    return result


@dataclass(frozen=True, slots=True)
class ChronicleReference:
    id: str
    kind: ChronicleReferenceKind
    label: str
    target_id: str | None
    claim_kind: ChronicleClaimKind | None
    source_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.id, "id")
        _text(self.label, "label")
        if not isinstance(self.kind, str) or self.kind not in _REFERENCE_KINDS:
            raise ValueError(f"Invalid Chronicle reference kind: {self.kind}")
        if self.claim_kind is not None and (not isinstance(self.claim_kind, str) or self.claim_kind not in _CLAIM_KINDS):
            raise ValueError(f"Invalid Chronicle claim kind: {self.claim_kind}")
        if self.target_id is not None:
            _text(self.target_id, "target_id")
        object.__setattr__(self, "source_event_ids", _ids(self.source_event_ids, "source_event_ids"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "target_id": self.target_id,
            "claim_kind": self.claim_kind,
            "source_event_ids": list(self.source_event_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ChronicleReference":
        if not isinstance(data, Mapping):
            raise ValueError("Chronicle reference must be an object")
        return cls(
            id=data.get("id", ""),
            kind=data.get("kind", ""),  # type: ignore[arg-type]
            label=data.get("label", ""),
            target_id=data.get("target_id"),
            claim_kind=data.get("claim_kind"),  # type: ignore[arg-type]
            source_event_ids=data.get("source_event_ids", ()),  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class ChronicleSegment:
    text: str
    reference: ChronicleReference | None = None

    def __post_init__(self) -> None:
        _text(self.text, "text")

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "reference": self.reference.to_dict() if self.reference else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ChronicleSegment":
        if not isinstance(data, Mapping):
            raise ValueError("Chronicle segment must be an object")
        reference = data.get("reference")
        return cls(
            text=data.get("text", ""),
            reference=ChronicleReference.from_dict(reference) if reference is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ChronicleParagraph:
    segments: tuple[ChronicleSegment, ...]
    source_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.segments, (list, tuple)) or not self.segments:
            raise ValueError("Chronicle paragraph must have segments")
        if any(not isinstance(segment, ChronicleSegment) for segment in self.segments):
            raise ValueError("Chronicle paragraph segments are malformed")
        object.__setattr__(self, "segments", tuple(self.segments))
        object.__setattr__(self, "source_event_ids", _ids(self.source_event_ids, "source_event_ids"))

    def to_dict(self) -> dict:
        return {
            "segments": [segment.to_dict() for segment in self.segments],
            "source_event_ids": list(self.source_event_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ChronicleParagraph":
        if not isinstance(data, Mapping):
            raise ValueError("Chronicle paragraph must be an object")
        segments = data.get("segments", ())
        if not isinstance(segments, (list, tuple)):
            raise ValueError("Chronicle paragraph segments must be a list")
        return cls(
            segments=tuple(ChronicleSegment.from_dict(item) for item in segments),  # type: ignore[arg-type]
            source_event_ids=data.get("source_event_ids", ()),  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class ChronicleChapter:
    id: str
    start_month_stamp: int
    end_month_stamp: int
    trigger: ChronicleTrigger
    title: str
    paragraphs: tuple[ChronicleParagraph, ...]
    source_event_ids: tuple[str, ...]
    created_at: float

    def __post_init__(self) -> None:
        _text(self.id, "id")
        if not isinstance(self.start_month_stamp, int) or not isinstance(self.end_month_stamp, int):
            raise ValueError("Chapter month stamps must be integers")
        if self.start_month_stamp > self.end_month_stamp:
            raise ValueError("Chapter start month must not exceed end month")
        if not isinstance(self.trigger, str) or self.trigger not in _TRIGGERS:
            raise ValueError(f"Invalid Chronicle trigger: {self.trigger}")
        _text(self.title, "title")
        if not isinstance(self.paragraphs, (list, tuple)) or not self.paragraphs:
            raise ValueError("Chronicle chapter must have paragraphs")
        if any(not isinstance(paragraph, ChronicleParagraph) for paragraph in self.paragraphs):
            raise ValueError("Chronicle chapter paragraphs are malformed")
        object.__setattr__(self, "paragraphs", tuple(self.paragraphs))
        object.__setattr__(self, "source_event_ids", _ids(self.source_event_ids, "source_event_ids"))
        if not isinstance(self.created_at, (int, float)):
            raise ValueError("created_at must be numeric")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start_month_stamp": self.start_month_stamp,
            "end_month_stamp": self.end_month_stamp,
            "trigger": self.trigger,
            "title": self.title,
            "paragraphs": [paragraph.to_dict() for paragraph in self.paragraphs],
            "source_event_ids": list(self.source_event_ids),
            "created_at": float(self.created_at),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ChronicleChapter":
        if not isinstance(data, Mapping):
            raise ValueError("Chronicle chapter must be an object")
        paragraphs = data.get("paragraphs", ())
        if not isinstance(paragraphs, (list, tuple)):
            raise ValueError("Chronicle chapter paragraphs must be a list")
        return cls(
            id=data.get("id", ""),
            start_month_stamp=data.get("start_month_stamp", -1),
            end_month_stamp=data.get("end_month_stamp", -1),
            trigger=data.get("trigger", ""),  # type: ignore[arg-type]
            title=data.get("title", ""),
            paragraphs=tuple(ChronicleParagraph.from_dict(item) for item in paragraphs),  # type: ignore[arg-type]
            source_event_ids=data.get("source_event_ids", ()),  # type: ignore[arg-type]
            created_at=data.get("created_at", 0.0),
        )

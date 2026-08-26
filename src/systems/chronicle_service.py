"""Generate validated Chronicle chapters from persisted factual events."""

from __future__ import annotations

import time
import unicodedata
import uuid
from typing import Any, Mapping

from src.classes.chronicle import ChronicleChapter, ChronicleParagraph, ChronicleReference, ChronicleSegment
from src.classes.event import Event
from src.i18n.template_resolver import resolve_locale_template_path
from src.run.log import get_logger
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ProviderCallError


CHRONICLE_TASK_NAME = "chronicle_chapter"
CHRONICLE_TEMPLATE_FILENAME = "chronicle_chapter.txt"
MAX_CHRONICLE_CANDIDATES = 64

CHRONICLE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "paragraphs"],
    "properties": {
        "title": {"type": "string"},
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source_event_ids", "segments"],
                "properties": {
                    "source_event_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "segments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["text", "reference"],
                            "properties": {
                                "text": {"type": "string"},
                                "reference": {
                                    "anyOf": [
                                        {"type": "null"},
                                        {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "required": [
                                                "id",
                                                "kind",
                                                "label",
                                                "target_id",
                                                "claim_kind",
                                                "source_event_ids",
                                            ],
                                            "properties": {
                                                "id": {"type": "string"},
                                                "kind": {
                                                    "type": "string",
                                                    "enum": ["avatar", "sect", "region", "event"],
                                                },
                                                "label": {"type": "string"},
                                                "target_id": {
                                                    "anyOf": [
                                                        {"type": "string"},
                                                        {"type": "null"},
                                                    ],
                                                },
                                                "claim_kind": {
                                                    "anyOf": [
                                                        {"type": "string", "enum": ["fact", "inference"]},
                                                        {"type": "null"},
                                                    ],
                                                },
                                                "source_event_ids": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


class ChronicleDraftError(ValueError):
    """The provider returned a structurally invalid or unauditable draft."""


def _event_dict(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "month_stamp": int(event.month_stamp),
        "content": event.content,
        "is_major": bool(event.is_major),
        "is_story": bool(event.is_story),
        "event_type": event.event_type,
        "fact_kind": str(event.fact_kind),
        "related_avatar_ids": [str(value) for value in (event.related_avatars or [])],
        "related_sect_ids": [str(value) for value in (event.related_sects or [])],
        "causal_source_event_ids": [link.cause_event_id for link in (event.causal_links or [])],
    }


class ChronicleService:
    async def _call_model(self, world: Any, infos: dict[str, Any]) -> Mapping[str, Any]:
        locale = str((getattr(world, "run_config_snapshot", {}) or {}).get("content_locale", "")) or None
        template = resolve_locale_template_path(CHRONICLE_TEMPLATE_FILENAME, current_locale=locale)
        return await call_llm_with_task_name(
            CHRONICLE_TASK_NAME,
            template,
            infos,
            output_schema=CHRONICLE_OUTPUT_SCHEMA,
        )

    @staticmethod
    def _world_entity_ids(world: Any) -> dict[str, set[str]]:
        avatars = getattr(getattr(world, "avatar_manager", None), "avatars", {}) or {}
        avatar_ids = {str(key) for key in avatars}
        sects: list[Any] = list(getattr(world, "existed_sects", None) or [])
        try:
            sects.extend(world.sect_context.get_active_sects())
        except (AttributeError, TypeError):
            pass
        sect_ids = {str(getattr(sect, "id", sect)) for sect in sects}
        game_map = getattr(world, "map", None)
        regions = getattr(game_map, "regions", {}) or {}
        return {"avatar": avatar_ids, "sect": sect_ids, "region": {str(key) for key in regions}}

    @staticmethod
    def _world_entities(world: Any) -> dict[str, list[dict[str, str]]]:
        avatars = getattr(getattr(world, "avatar_manager", None), "avatars", {}) or {}
        avatar_rows = [
            {"id": str(getattr(item, "id", key)), "label": str(getattr(item, "name", getattr(item, "id", key)))}
            for key, item in avatars.items()
        ]
        sects = list(getattr(world, "existed_sects", None) or [])
        try:
            sects.extend(world.sect_context.get_active_sects())
        except (AttributeError, TypeError):
            pass
        sect_rows = [
            {"id": str(getattr(item, "id", "")), "label": str(getattr(item, "name", getattr(item, "id", "")))}
            for item in sects if getattr(item, "id", None) is not None
        ]
        regions = getattr(getattr(world, "map", None), "regions", {}) or {}
        region_rows = [
            {"id": str(key), "label": str(getattr(item, "name", key))}
            for key, item in regions.items()
        ]
        return {"avatars": avatar_rows, "sects": sect_rows, "regions": region_rows}

    @staticmethod
    def _entity_anchor_targets(world: Any) -> dict[str, tuple[str, str]]:
        grouped: dict[str, set[tuple[str, str]]] = {}
        entities = ChronicleService._world_entities(world)
        for collection, kind in (("avatars", "avatar"), ("sects", "sect"), ("regions", "region")):
            for row in entities[collection]:
                label = row["label"].strip()
                if len(label) < 2:
                    continue
                grouped.setdefault(label, set()).add((kind, row["id"]))
        unique_targets = {
            label: next(iter(targets))
            for label, targets in grouped.items()
            if len(targets) == 1
        }
        return {
            label: target
            for label, target in unique_targets.items()
            if not any(label != other and label in other for other in grouped)
        }

    @staticmethod
    def _is_latin_word_character(character: str) -> bool:
        return character == "_" or character.isdigit() or "LATIN" in unicodedata.name(character, "")

    @classmethod
    def _find_safe_entity_mention(cls, text: str, label: str, start: int = 0) -> int | None:
        latin_label = any("LATIN" in unicodedata.name(character, "") for character in label)
        cursor = start
        while True:
            found_at = text.find(label, cursor)
            if found_at < 0:
                return None
            end_at = found_at + len(label)
            before = text[found_at - 1] if found_at > 0 else ""
            after = text[end_at] if end_at < len(text) else ""
            if not latin_label or (
                (not before or not cls._is_latin_word_character(before))
                and (not after or not cls._is_latin_word_character(after))
            ):
                return found_at
            cursor = found_at + 1

    @classmethod
    def _supported_entity_targets(
        cls,
        *,
        candidate_map: dict[str, Event],
        paragraph_source_ids: tuple[str, ...],
        anchor_targets: dict[str, tuple[str, str]],
    ) -> tuple[dict[str, tuple[str, str]], set[tuple[str, str]]]:
        sources = [candidate_map[source_id] for source_id in paragraph_source_ids]
        supported: set[tuple[str, str]] = set()
        for source in sources:
            supported.update(("avatar", str(value)) for value in (source.related_avatars or []))
            supported.update(("sect", str(value)) for value in (source.related_sects or []))
        for label, target in anchor_targets.items():
            if any(cls._find_safe_entity_mention(source.content, label) is not None for source in sources):
                supported.add(target)
        return {
            label: target
            for label, target in anchor_targets.items()
            if target in supported
        }, supported

    @staticmethod
    def _validated_reference(
        reference_data: object,
        *,
        candidate_ids: set[str],
        paragraph_source_ids: tuple[str, ...],
        entity_ids: dict[str, set[str]],
        reference_ids: set[str],
        supported_entity_targets: set[tuple[str, str]],
    ) -> ChronicleReference:
        if not isinstance(reference_data, Mapping):
            raise ChronicleDraftError("Malformed Chronicle reference")
        try:
            reference = ChronicleReference.from_dict(reference_data)
        except (ValueError, TypeError, KeyError) as exc:
            raise ChronicleDraftError(f"Malformed Chronicle reference: {exc}") from exc
        if reference.id in reference_ids:
            raise ChronicleDraftError("Duplicate Chronicle reference ID")
        if not set(reference.source_event_ids) <= candidate_ids:
            raise ChronicleDraftError("Reference contains unknown source ID")
        if not set(reference.source_event_ids) <= set(paragraph_source_ids):
            raise ChronicleDraftError("Reference sources must be declared by its paragraph")
        if reference.kind == "event":
            if reference.claim_kind == "fact":
                if (
                    reference.target_id is None
                    or reference.target_id not in candidate_ids
                    or reference.target_id not in reference.source_event_ids
                ):
                    raise ChronicleDraftError("Factual event reference target is invalid")
            elif reference.claim_kind == "inference":
                if reference.target_id is not None:
                    raise ChronicleDraftError("Inference references cannot have factual targets")
            else:
                raise ChronicleDraftError("Event reference claim kind is required")
        elif reference.kind in entity_ids:
            if (
                reference.target_id is None
                or reference.target_id not in entity_ids[reference.kind]
                or reference.claim_kind is not None
            ):
                raise ChronicleDraftError("Entity reference target is invalid")
            if (reference.kind, reference.target_id) not in supported_entity_targets:
                raise ChronicleDraftError("Entity reference is not supported by paragraph sources")
        else:
            raise ChronicleDraftError("Unknown reference kind")
        reference_ids.add(reference.id)
        return reference

    @staticmethod
    def _anchor_entity_mentions(
        segments: list[ChronicleSegment],
        *,
        targets: dict[str, tuple[str, str]],
        paragraph_source_ids: tuple[str, ...],
        reference_ids: set[str],
        paragraph_index: int,
    ) -> list[ChronicleSegment]:
        labels = sorted(targets, key=lambda label: (-len(label), label))
        anchored: list[ChronicleSegment] = []
        anchor_index = 0
        for segment in segments:
            if segment.reference is not None:
                anchored.append(segment)
                continue
            text = segment.text
            cursor = 0
            while cursor < len(text):
                matches = []
                for label in labels:
                    found_at = ChronicleService._find_safe_entity_mention(text, label, cursor)
                    if found_at is not None:
                        matches.append((found_at, -len(label), label))
                if not matches:
                    anchored.append(ChronicleSegment(text=text[cursor:]))
                    break
                found_at, _, label = min(matches)
                if found_at > cursor:
                    anchored.append(ChronicleSegment(text=text[cursor:found_at]))
                kind, target_id = targets[label]
                while True:
                    reference_id = f"entity-{paragraph_index}-{anchor_index}"
                    anchor_index += 1
                    if reference_id not in reference_ids:
                        break
                reference_ids.add(reference_id)
                anchored.append(
                    ChronicleSegment(
                        text=label,
                        reference=ChronicleReference(
                            id=reference_id,
                            kind=kind,  # type: ignore[arg-type]
                            label=label,
                            target_id=target_id,
                            claim_kind=None,
                            source_event_ids=paragraph_source_ids,
                        ),
                    )
                )
                cursor = found_at + len(label)
        return anchored

    @staticmethod
    def _merge_events(world: Any, current_events: list[Event], start: int, end: int) -> list[Event]:
        manager = getattr(world, "event_manager", None)
        persisted = manager.get_events_between_months(start, end) if manager is not None else []
        merged: dict[str, Event] = {}
        for event in [*persisted, *current_events]:
            if start <= int(event.month_stamp) <= end:
                merged.setdefault(event.id, event)
        events = sorted(merged.values(), key=lambda event: (int(event.month_stamp), float(event.created_at), event.id))
        if manager is not None:
            for event in events:
                if getattr(event, "causal_links", None):
                    continue
                get_links = getattr(manager, "get_causal_links_for_event", None)
                if get_links is not None:
                    event.causal_links = list(get_links(event.id) or [])
        return events

    @staticmethod
    def _window(world: Any, current_month: int) -> tuple[int, int, str | None]:
        latest = None
        manager = getattr(world, "event_manager", None)
        if manager is not None:
            latest = manager.get_latest_chronicle_chapter()
        if latest is None:
            return max(0, current_month - 2), current_month, None
        return int(latest.end_month_stamp) + 1, current_month, latest

    @staticmethod
    def _parse_draft_impl(
        draft: Mapping[str, Any],
        *,
        world: Any,
        candidates: list[Event],
        start: int,
        end: int,
        trigger: str,
    ) -> ChronicleChapter:
        if not isinstance(draft, Mapping):
            raise ChronicleDraftError("Chronicle draft must be an object")
        candidate_map = {event.id: event for event in candidates}
        candidate_ids = set(candidate_map)
        paragraphs_data = draft.get("paragraphs")
        if not isinstance(paragraphs_data, list) or not paragraphs_data:
            raise ChronicleDraftError("Chronicle draft must have paragraphs")
        paragraphs: list[ChronicleParagraph] = []
        used_ids: set[str] = set()
        reference_ids: set[str] = set()
        entity_ids = ChronicleService._world_entity_ids(world)
        entity_targets = ChronicleService._entity_anchor_targets(world)
        for paragraph_index, paragraph_data in enumerate(paragraphs_data):
            if not isinstance(paragraph_data, Mapping):
                raise ChronicleDraftError("Malformed Chronicle paragraph")
            paragraph_sources = paragraph_data.get("source_event_ids")
            if not isinstance(paragraph_sources, list) or not paragraph_sources:
                raise ChronicleDraftError("Paragraph source_event_ids are required")
            paragraph_source_ids = tuple(str(item) for item in paragraph_sources)
            if len(set(paragraph_source_ids)) != len(paragraph_source_ids) or not set(paragraph_source_ids) <= candidate_ids:
                raise ChronicleDraftError("Paragraph contains unknown or duplicate source IDs")
            segments_data = paragraph_data.get("segments")
            if not isinstance(segments_data, list) or not segments_data:
                raise ChronicleDraftError("Paragraph segments are required")
            paragraph_anchor_targets, supported_entity_targets = ChronicleService._supported_entity_targets(
                candidate_map=candidate_map,
                paragraph_source_ids=paragraph_source_ids,
                anchor_targets=entity_targets,
            )
            segments: list[ChronicleSegment] = []
            for segment_data in segments_data:
                if not isinstance(segment_data, Mapping):
                    raise ChronicleDraftError("Malformed Chronicle segment")
                reference_data = segment_data.get("reference")
                reference = ChronicleService._validated_reference(
                    reference_data,
                    candidate_ids=candidate_ids,
                    paragraph_source_ids=paragraph_source_ids,
                    entity_ids=entity_ids,
                    reference_ids=reference_ids,
                    supported_entity_targets=supported_entity_targets,
                ) if reference_data is not None else None
                segments.append(ChronicleSegment(text=segment_data.get("text", ""), reference=reference))
            segments = ChronicleService._anchor_entity_mentions(
                segments,
                targets=paragraph_anchor_targets,
                paragraph_source_ids=paragraph_source_ids,
                reference_ids=reference_ids,
                paragraph_index=paragraph_index,
            )
            paragraphs.append(ChronicleParagraph(segments=tuple(segments), source_event_ids=paragraph_source_ids))
            used_ids.update(paragraph_source_ids)
        if not used_ids:
            raise ChronicleDraftError("Chronicle draft has no source events")
        chapter_sources = tuple(event.id for event in candidates if event.id in used_ids)
        return ChronicleChapter(
            id=str(draft.get("id") or uuid.uuid4()),
            start_month_stamp=start,
            end_month_stamp=end,
            trigger=trigger,  # type: ignore[arg-type]
            title=draft.get("title", ""),
            paragraphs=tuple(paragraphs),
            source_event_ids=chapter_sources,
            created_at=float(draft.get("created_at", time.time())),
        )

    @classmethod
    def _parse_draft(cls, draft: Mapping[str, Any], **kwargs: Any) -> ChronicleChapter:
        try:
            return cls._parse_draft_impl(draft, **kwargs)
        except ChronicleDraftError:
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise ChronicleDraftError(f"Chronicle draft has invalid structured fields: {exc}") from exc

    @staticmethod
    def _bound_candidates(candidates: list[Event]) -> list[Event]:
        if len(candidates) <= MAX_CHRONICLE_CANDIDATES:
            return candidates
        by_id = {event.id: event for event in candidates}
        required_ids = {event.id for event in candidates if event.is_major}
        frontier = list(required_ids)
        while frontier:
            event = by_id.get(frontier.pop())
            if event is None:
                continue
            for link in getattr(event, "causal_links", None) or []:
                cause_id = str(link.cause_event_id)
                if cause_id in by_id and cause_id not in required_ids:
                    required_ids.add(cause_id)
                    frontier.append(cause_id)
        required = [event for event in candidates if event.id in required_ids]
        optional = [event for event in candidates if event.id not in required_ids]
        optional_limit = MAX_CHRONICLE_CANDIDATES - len(required)
        optional = optional[-optional_limit:] if optional_limit > 0 else []
        return sorted([*required, *optional], key=lambda event: (int(event.month_stamp), float(event.created_at), event.id))

    async def maybe_generate_chapter(self, world: Any, current_events: list[Event]) -> ChronicleChapter | None:
        current_month = int(world.month_stamp)
        start, end, latest = self._window(world, current_month)
        if latest is not None and int(latest.end_month_stamp) >= current_month:
            return None
        candidates = [event for event in self._merge_events(world, current_events, start, end) if not event.is_story]
        if not candidates:
            return None
        current_major = any(int(event.month_stamp) == current_month and event.is_major for event in candidates)
        deadline = current_month - (int(latest.end_month_stamp) if latest is not None else 0) >= 3
        if not current_major and not deadline:
            return None
        trigger = "major_event" if current_major else "max_interval"
        candidates = self._bound_candidates(candidates)
        infos = {
            "start_month_stamp": start,
            "end_month_stamp": end,
            "trigger": trigger,
            "events": [_event_dict(event) for event in candidates],
            "entities": self._world_entities(world),
        }
        try:
            draft = await self._call_model(world, infos)
            return self._parse_draft(draft, world=world, candidates=candidates, start=start, end=end, trigger=trigger)
        except (LLMError, ProviderCallError, ChronicleDraftError) as exc:
            get_logger().logger.warning("Chronicle generation skipped: %s", exc)
            return None

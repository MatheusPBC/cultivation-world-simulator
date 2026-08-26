"""Generate validated Chronicle chapters from persisted factual events."""

from __future__ import annotations

import time
import uuid
from typing import Any, Mapping

from src.classes.chronicle import ChronicleChapter, ChronicleParagraph, ChronicleReference, ChronicleSegment
from src.classes.event import Event, FactKind
from src.i18n.template_resolver import resolve_locale_template_path
from src.run.log import get_logger
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ParseError, ProviderCallError


CHRONICLE_TASK_NAME = "chronicle_chapter"
CHRONICLE_TEMPLATE_FILENAME = "chronicle_chapter.txt"
MAX_CHRONICLE_CANDIDATES = 64


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
        return await call_llm_with_task_name(CHRONICLE_TASK_NAME, template, infos)

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
    def _merge_events(world: Any, current_events: list[Event], start: int, end: int) -> list[Event]:
        manager = getattr(world, "event_manager", None)
        persisted = manager.get_events_between_months(start, end) if manager is not None else []
        merged: dict[str, Event] = {}
        for event in [*persisted, *current_events]:
            if start <= int(event.month_stamp) <= end:
                merged.setdefault(event.id, event)
        return sorted(merged.values(), key=lambda event: (int(event.month_stamp), float(event.created_at), event.id))

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
    def _parse_draft(
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
        for paragraph_data in paragraphs_data:
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
            segments: list[ChronicleSegment] = []
            for segment_data in segments_data:
                if not isinstance(segment_data, Mapping):
                    raise ChronicleDraftError("Malformed Chronicle segment")
                reference_data = segment_data.get("reference")
                reference = None
                if reference_data is not None:
                    if not isinstance(reference_data, Mapping):
                        raise ChronicleDraftError("Malformed Chronicle reference")
                    reference = ChronicleReference.from_dict(reference_data)
                    if reference.id in reference_ids:
                        raise ChronicleDraftError("Duplicate Chronicle reference ID")
                    reference_ids.add(reference.id)
                    if not set(reference.source_event_ids) <= candidate_ids:
                        raise ChronicleDraftError("Reference contains unknown source ID")
                    if not set(reference.source_event_ids) <= set(paragraph_source_ids):
                        raise ChronicleDraftError("Reference sources must be declared by its paragraph")
                    if reference.kind == "event":
                        target = reference.target_id
                        if reference.claim_kind not in {"fact", "inference"}:
                            raise ChronicleDraftError("Event reference claim kind is required")
                        if reference.claim_kind == "fact":
                            if target is None or target not in candidate_ids or target not in reference.source_event_ids:
                                raise ChronicleDraftError("Factual event reference target is invalid")
                        elif reference.target_id is not None:
                            raise ChronicleDraftError("Inference references cannot have factual targets")
                    elif reference.kind in entity_ids:
                        if reference.target_id is None or reference.target_id not in entity_ids[reference.kind]:
                            raise ChronicleDraftError("Entity reference target is invalid")
                        if reference.claim_kind is not None:
                            raise ChronicleDraftError("Entity references cannot have a claim kind")
                    else:
                        raise ChronicleDraftError("Unknown reference kind")
                segments.append(ChronicleSegment(text=segment_data.get("text", ""), reference=reference))
            paragraphs.append(ChronicleParagraph(segments=tuple(segments), source_event_ids=paragraph_source_ids))
            used_ids.update(paragraph_source_ids)
        if not used_ids:
            raise ChronicleDraftError("Chronicle draft has no source events")
        chapter_source_ids = draft.get("source_event_ids")
        if chapter_source_ids is None:
            chapter_source_ids = [event.id for event in candidates if event.id in used_ids]
        if not isinstance(chapter_source_ids, list):
            raise ChronicleDraftError("Chapter source_event_ids must be a list")
        chapter_sources = tuple(str(item) for item in chapter_source_ids)
        if len(set(chapter_sources)) != len(chapter_sources) or set(chapter_sources) != used_ids:
            raise ChronicleDraftError("Chapter sources must exactly match paragraph sources")
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
        if len(candidates) > MAX_CHRONICLE_CANDIDATES:
            # Keep the newest bounded slice, but never discard a major event in
            # the current publication month.  Their direct causal evidence is
            # retained when it is present in the same pending window.
            required_ids = {
                event.id
                for event in candidates
                if int(event.month_stamp) == current_month and event.is_major
            }
            selected = candidates[-MAX_CHRONICLE_CANDIDATES:]
            selected_ids = {event.id for event in selected}
            for required_id in required_ids - selected_ids:
                required_event = next(event for event in candidates if event.id == required_id)
                selected.pop(0)
                selected.append(required_event)
            candidates = sorted(selected, key=lambda event: (int(event.month_stamp), float(event.created_at), event.id))
        infos = {
            "start_month_stamp": start,
            "end_month_stamp": end,
            "trigger": trigger,
            "events": [_event_dict(event) for event in candidates],
        }
        try:
            draft = await self._call_model(world, infos)
            return self._parse_draft(draft, world=world, candidates=candidates, start=start, end=end, trigger=trigger)
        except (LLMError, ParseError, ProviderCallError, ChronicleDraftError, ValueError, TypeError, KeyError) as exc:
            get_logger().logger.warning("Chronicle generation skipped: %s", exc)
            return None

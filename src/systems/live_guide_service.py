"""Source-backed projection for the World Journal's Live Guide."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from src.i18n.template_resolver import resolve_locale_template_path
from src.run.log import get_logger
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ProviderCallError


LIVE_GUIDE_ASK_TASK_NAME = "live_guide_ask"
LIVE_GUIDE_ASK_TEMPLATE_FILENAME = "live_guide_ask.txt"
LIVE_GUIDE_MAX_SOURCES = 20

LIVE_GUIDE_ASK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "source_event_ids"],
    "properties": {
        "answer": {"type": "string"},
        "source_event_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


class LiveGuideDraftError(ValueError):
    """The chronicler returned an answer that cannot be tied to supplied facts."""


def _trim(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    shortened = clean[: max(1, limit - 1)].rsplit(" ", 1)[0]
    return f"{shortened or clean[: limit - 1]}…"


def _paragraph_text(paragraph: Any) -> str:
    return "".join(str(getattr(segment, "text", "")) for segment in paragraph.segments).strip()


def _thread_severity(events: list[Any]) -> str:
    critical_tokens = ("death", "killed", "assassin", "war", "battle", "annihilat")
    if any(any(token in str(getattr(event, "event_type", "")).lower() for token in critical_tokens) for event in events):
        return "critical"
    if any(bool(getattr(event, "is_major", False)) for event in events):
        return "major"
    return "notable"


def _concept_key(events: list[Any]) -> str:
    haystack = " ".join(
        f"{getattr(event, 'event_type', '')} {getattr(event, 'content', '')}" for event in events
    ).lower()
    rules = (
        (("war", "battle", "attack", "assassin", "guerra", "batalha", "战争", "战斗"), "WORLD_INFO_BATTLE"),
        (("sect", "seita", "宗门"), "WORLD_INFO_SECT"),
        (("dynasty", "emperor", "dinastia", "imperador", "王朝", "皇帝"), "WORLD_INFO_DYNASTY"),
        (("death", "killed", "morte", "morreu", "死亡"), "WORLD_INFO_DEATH"),
        (("realm", "breakthrough", "cultivat", "reino", "突破", "修炼"), "WORLD_INFO_CULTIVATION"),
        (("treasure", "equipment", "artifact", "tesouro", "equipamento", "法宝"), "WORLD_INFO_EQUIPMENT_AND_ELIXIR"),
        (("region", "cidade", "região", "区域"), "WORLD_INFO_REGION"),
    )
    for tokens, key in rules:
        if any(token in haystack for token in tokens):
            return key
    return "WORLD_INFO_INTRO"


def _subjects(serialized_events: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for event in serialized_events:
        for subject in event.get("subjects") or []:
            kind = str(subject.get("type", ""))
            subject_id = str(subject.get("id", ""))
            key = (kind, subject_id)
            if kind not in {"avatar", "sect"} or not subject_id or key in seen:
                continue
            seen.add(key)
            result.append({"kind": kind, "id": subject_id, "name": str(subject.get("name", subject_id))})
    return result


def build_live_guide(
    world: Any,
    *,
    journal: dict[str, Any],
    serialize_events_for_client: Callable[..., list[dict[str, Any]]],
) -> dict[str, Any]:
    """Build a deterministic guide; no model decides facts, ranking, or links."""
    manager = world.event_manager
    latest_chapter = manager.get_latest_chronicle_chapter()
    threads: list[dict[str, Any]] = []
    used_source_ids: set[str] = set()
    event_by_id: dict[str, Any] = {}
    period_start = int((journal.get("period") or {}).get("start_month_stamp", int(world.month_stamp) - 2))

    if latest_chapter is not None:
        for index, paragraph in enumerate(latest_chapter.paragraphs):
            events = [
                manager.get_event_by_id(source_id)
                for source_id in paragraph.source_event_ids
            ]
            events = [event for event in events if event is not None]
            events = [event for event in events if int(event.month_stamp) >= period_start]
            if not events:
                continue
            serialized = serialize_events_for_client(events, world=world)
            summary = _trim(_paragraph_text(paragraph), 360)
            if not summary:
                summary = _trim(str(serialized[0].get("content") or serialized[0].get("text") or ""), 360)
            title = _trim(
                str(serialized[0].get("content") or serialized[0].get("text") or summary),
                88,
            )
            source_ids = [str(event.id) for event in events]
            threads.append(
                {
                    "id": f"{latest_chapter.id}-thread-{index}",
                    "title": title,
                    "summary": summary,
                    "severity": _thread_severity(events),
                    "primary_event_id": source_ids[0],
                    "source_event_ids": source_ids,
                    "subjects": _subjects(serialized),
                    "_sort_month_stamp": max(int(event.month_stamp) for event in events),
                }
            )
            used_source_ids.update(source_ids)
            event_by_id.update((str(event.id), event) for event in events)

    for event_dto in journal.get("highlights") or []:
        event_id = str(event_dto.get("id", ""))
        if not event_id or event_id in used_source_ids:
            continue
        event = manager.get_event_by_id(event_id)
        if event is None:
            continue
        summary = _trim(str(event_dto.get("content") or event_dto.get("text") or ""), 360)
        threads.append(
            {
                "id": f"event-thread-{event_id}",
                "title": _trim(summary, 88),
                "summary": summary,
                "severity": _thread_severity([event]),
                "primary_event_id": event_id,
                "source_event_ids": [event_id],
                "subjects": _subjects([event_dto]),
                "_sort_month_stamp": int(event.month_stamp),
            }
        )
        used_source_ids.add(event_id)
        event_by_id[event_id] = event

    threads.sort(key=lambda item: (-int(item["_sort_month_stamp"]), item["id"]))
    threads = threads[:3]
    for item in threads:
        item.pop("_sort_month_stamp", None)

    final_source_ids = list(dict.fromkeys(source_id for item in threads for source_id in item["source_event_ids"]))
    source_events = [event_by_id[source_id] for source_id in final_source_ids if source_id in event_by_id]

    month_stamp = world.month_stamp
    latest_thread_month = max((int(event.month_stamp) for event in source_events), default=-1)
    chapter_is_current = latest_chapter is not None and int(latest_chapter.end_month_stamp) >= latest_thread_month
    headline = str(getattr(latest_chapter, "title", "") or "") if chapter_is_current else ""
    if not headline and threads:
        headline = str(threads[0]["title"])
    return {
        "date": {
            "month_stamp": int(month_stamp),
            "year": int(month_stamp.get_year()),
            "month": int(month_stamp.get_month().value),
        },
        "headline": headline,
        "source_event_ids": final_source_ids,
        "threads": threads,
        "people": [
            {
                "avatar_id": str(item["avatar_id"]),
                "name": str(item["avatar_name"]),
                "current_action": str(item.get("action") or ""),
                "ambition": str(item.get("long_term_objective") or item.get("short_term_objective") or ""),
                "event_count": int(item.get("event_count") or 0),
            }
            for item in (journal.get("ongoing") or [])[:3]
        ],
        "concept": {
            "term_key": _concept_key(source_events),
            "source_event_ids": list(dict.fromkeys(str(event.id) for event in source_events)),
        },
    }


def _event_prompt_row(event: Any) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "month_stamp": int(event.month_stamp),
        "content": str(event.content),
        "event_type": str(getattr(event, "event_type", "")),
        "is_major": bool(event.is_major),
        "related_avatar_ids": [str(item) for item in (event.related_avatars or [])],
        "related_sect_ids": [str(item) for item in (event.related_sects or [])],
        "causal_source_event_ids": [
            str(link.cause_event_id) for link in (getattr(event, "causal_links", None) or [])
        ],
    }


def _fallback_answer(events: list[Any]) -> dict[str, Any]:
    if not events:
        return {"answer": "", "source_event_ids": [], "mode": "unavailable"}
    event = events[-1]
    return {
        "answer": _trim(str(event.content), 600),
        "source_event_ids": [str(event.id)],
        "mode": "fallback",
    }


async def answer_live_guide(world: Any, *, question: str, guide: dict[str, Any]) -> dict[str, Any]:
    """Answer against the guide's closed evidence set and reject unknown citations."""
    manager = world.event_manager
    events = [
        manager.get_event_by_id(source_id)
        for source_id in guide.get("source_event_ids", [])[:LIVE_GUIDE_MAX_SOURCES]
    ]
    events = [event for event in events if event is not None]
    if not events:
        return _fallback_answer([])

    locale = str((getattr(world, "run_config_snapshot", {}) or {}).get("content_locale", "")) or None
    template = resolve_locale_template_path(LIVE_GUIDE_ASK_TEMPLATE_FILENAME, current_locale=locale)
    infos = {
        "question": question.strip(),
        "date": guide["date"],
        "headline": guide.get("headline", ""),
        "facts": [_event_prompt_row(event) for event in events],
    }
    try:
        draft = await call_llm_with_task_name(
            LIVE_GUIDE_ASK_TASK_NAME,
            template,
            infos,
            output_schema=LIVE_GUIDE_ASK_SCHEMA,
        )
        if not isinstance(draft, Mapping):
            raise LiveGuideDraftError("Live Guide answer must be an object")
        answer = str(draft.get("answer", "")).strip()
        source_ids_data = draft.get("source_event_ids")
        if not answer or not isinstance(source_ids_data, list) or not source_ids_data:
            raise LiveGuideDraftError("Live Guide answer and citations are required")
        allowed_ids = {str(event.id) for event in events}
        source_ids = list(dict.fromkeys(str(item) for item in source_ids_data))
        if not set(source_ids) <= allowed_ids:
            raise LiveGuideDraftError("Live Guide answer cited an unknown event")
        return {"answer": answer, "source_event_ids": source_ids, "mode": "generated"}
    except (LLMError, ProviderCallError, LiveGuideDraftError) as exc:
        get_logger().logger.warning("Live Guide answer fell back to factual text: %s", exc)
        return _fallback_answer(events)

from __future__ import annotations

import random
from enum import StrEnum
from typing import TYPE_CHECKING

from src.classes.event import Event
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.goldfinger import merge_story_prompt_with_goldfinger
from src.classes.story_teller import StoryTeller
from src.utils.config import CONFIG

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar


class StoryEventKind(StrEnum):
    COMBAT = "combat"
    RELATIONSHIP_MAJOR = "relationship_major"
    CULTIVATION_MAJOR = "cultivation_major"
    CRAFTING = "crafting"
    AUTONOMOUS_CREATION = "autonomous_creation"
    DAILY_SOCIAL = "daily_social"
    SECT_MISSION = "sect_mission"
    WORLD_FORTUNE = "world_fortune"
    WORLD_MISFORTUNE = "world_misfortune"
    OPPORTUNITY = "opportunity"
    GATHERING = "gathering"


class StoryEventService:
    @classmethod
    def is_enabled(cls) -> bool:
        return bool(getattr(getattr(CONFIG.world, "story", None), "enabled", True))

    @classmethod
    def get_probability(cls, kind: StoryEventKind) -> float:
        if kind == StoryEventKind.GATHERING:
            return 1.0
        if kind == StoryEventKind.AUTONOMOUS_CREATION:
            raw = getattr(CONFIG.world, "autonomous_creation_story_probability", 0.0)
            try:
                prob = float(raw)
            except (TypeError, ValueError):
                return 0.0
            return max(0.0, min(1.0, prob))

        story_cfg = getattr(CONFIG.world, "story", None)
        if story_cfg is None:
            return 0.0

        prob_cfg = getattr(story_cfg, "probabilities", None)
        if prob_cfg is None:
            return 0.0

        raw = getattr(prob_cfg, kind.value, 0.0)
        try:
            prob = float(raw)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, prob))

    @classmethod
    def should_trigger(cls, kind: StoryEventKind) -> bool:
        if not cls.is_enabled():
            return False
        if kind == StoryEventKind.GATHERING:
            return True
        return random.random() < cls.get_probability(kind)

    @staticmethod
    def _normalize_related_avatar_ids(related_avatar_ids: list[str] | None) -> list[str] | None:
        if not related_avatar_ids:
            return None
        normalized = [str(avatar_id) for avatar_id in related_avatar_ids if avatar_id is not None]
        return normalized or None

    @staticmethod
    def _filter_actors(actors: list[Avatar | None]) -> list[Avatar]:
        return [actor for actor in actors if actor is not None]

    @classmethod
    async def maybe_create_story(
        cls,
        *,
        kind: StoryEventKind,
        month_stamp,
        start_text: str,
        result_text: str,
        source_event: Event,
        actors: list[Avatar | None],
        related_avatar_ids: list[str] | None,
        prompt: str = "",
        allow_relation_changes: bool = False,
    ) -> Event | None:
        if not isinstance(source_event, Event) or not str(source_event.id).strip():
            raise ValueError("source_event must be a persisted Event anchor")

        # 历史命名沿用中；当前仅用于让 StoryTeller 选择双人故事模板，
        # 不代表故事阶段会直接修改角色关系。
        if not cls.should_trigger(kind):
            return None

        filtered_actors = cls._filter_actors(actors)
        if not filtered_actors:
            return None

        final_start_text = (start_text or "").strip() or (result_text or "").strip()
        final_result_text = (result_text or "").strip() or final_start_text
        if not final_result_text:
            return None
        enriched_prompt = merge_story_prompt_with_goldfinger(prompt, *filtered_actors)

        story = await StoryTeller.tell_story(
            final_start_text,
            final_result_text,
            *filtered_actors,
            prompt=enriched_prompt,
            allow_relation_changes=allow_relation_changes,
        )
        story_event = Event(
            month_stamp=month_stamp,
            content=story,
            related_avatars=cls._normalize_related_avatar_ids(related_avatar_ids),
            is_major=False,
            is_story=True,
            event_type="action_story",
            causal_origin=CausalOrigin.LLM_INTERPRETATION,
        )
        story_event.causal_links.append(CausalLink(
            event_id=story_event.id,
            cause_event_id=source_event.id,
            relation=CausalRelation.CONTRIBUTED_TO,
        ))
        return story_event

    @classmethod
    async def maybe_create_gathering_story(
        cls,
        *,
        month_stamp,
        gathering_info: str,
        events_text: str,
        details_text: str,
        related_avatars: list[Avatar],
        source_event: Event,
        prompt: str = "",
    ) -> Event | None:
        if not isinstance(source_event, Event) or not str(source_event.id).strip():
            raise ValueError("source_event must be a persisted Event anchor")
        if not cls.should_trigger(StoryEventKind.GATHERING):
            return None
        if not related_avatars:
            return None
        enriched_prompt = merge_story_prompt_with_goldfinger(prompt, *related_avatars)

        story = await StoryTeller.tell_gathering_story(
            gathering_info=gathering_info,
            events_text=events_text,
            details_text=details_text,
            related_avatars=related_avatars,
            prompt=enriched_prompt,
        )
        story_event = Event(
            month_stamp=month_stamp,
            content=story,
            related_avatars=[avatar.id for avatar in related_avatars],
            is_major=False,
            is_story=True,
            event_type="gathering_story",
            causal_origin=CausalOrigin.LLM_INTERPRETATION,
        )
        story_event.causal_links.append(CausalLink(
            event_id=story_event.id,
            cause_event_id=source_event.id,
            relation=CausalRelation.CONTRIBUTED_TO,
        ))
        return story_event

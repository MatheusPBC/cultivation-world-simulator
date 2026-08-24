"""
月度个人解读（EventAppraisal）生成。

本模块只做一件事：为本月已经发生的、受支持的人际事件，生成直接参与者
对彼此的个人解读，并把结果 **挂载** 到 `event.appraisals` 上。它不写库、
不改关系、不产生新事实，也不是第二条执行路径——真正的持久化仍然由
`finalize_step` -> `EventStorage.add_event` 在同一个事务里完成。

参与者契约（唯一、显式、可测）：
    每个受支持的事件类型在 `_PARTICIPANT_KEYS` 中声明恰好两个
    “结构化参与者 ID”键，这些键由事件生产者写进 `render_params`。
    ID 只允许来自这些结构化字段，永远不从正文（prose）里推断，
    也不做任何模糊文本匹配。

失败语义：解读生成永远不会暂停、中止或回滚当月模拟。provider 异常、
候选缺失、重复候选、伪造候选 ID、字段异常、情绪非法或响应不完整，
都只影响受影响的那些候选，其余候选照常使用 AI 结果。

见 docs/specs/personal-appraisal-politics.md（“Monthly generation”）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable
import uuid

from src.classes.emotions import EmotionType
from src.classes.event_appraisal import (
    MAX_APPRAISAL_SUMMARY_LENGTH,
    AppraisalSource,
    EventAppraisal,
)
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.run.log import get_logger
from src.utils.config import CONFIG
from src.utils.llm import call_llm_with_task_name
from src.utils.strings import to_json_str_with_intent

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar
    from src.classes.core.world import World
    from src.classes.event import Event


# 单月最多送进 AI 的候选数；超出的候选走确定性规则兜底。
MAX_AI_APPRAISAL_CANDIDATES = 16

APPRAISAL_TASK_NAME = "event_appraisal"
APPRAISAL_TEMPLATE_FILENAME = "event_appraisal.txt"

# 每个受支持事件类型声明的两个结构化参与者 ID 键。
# 键名沿用各生产者已有的语义角色，不再另造第三套命名。
_PARTICIPANT_KEYS: dict[str, tuple[str, str]] = {
    "battle_result": ("killer_id", "victim_id"),
    "battle_kill": ("killer_id", "victim_id"),
    "bond_lovers_formed": ("avatar_a_id", "avatar_b_id"),
    "bond_lovers_rejected": ("avatar_a_id", "avatar_b_id"),
    "bond_sworn_sibling_formed": ("avatar_a_id", "avatar_b_id"),
    "bond_sworn_sibling_rejected": ("avatar_a_id", "avatar_b_id"),
    "bond_master_disciple_formed": ("avatar_a_id", "avatar_b_id"),
}

# 每个事件类型两个方向的角色名：(第一个 ID 的角色, 第二个 ID 的角色)。
_PARTICIPANT_ROLES: dict[str, tuple[str, str]] = {
    "battle_result": ("winner", "loser"),
    "battle_kill": ("killer", "victim"),
    "bond_lovers_formed": ("partner", "partner"),
    "bond_lovers_rejected": ("suitor", "rejecter"),
    "bond_sworn_sibling_formed": ("sworn_sibling", "sworn_sibling"),
    "bond_sworn_sibling_rejected": ("proposer", "rejecter"),
    "bond_master_disciple_formed": ("bonded", "bonded"),
}


@dataclass(frozen=True)
class AppraisalRuleProfile:
    personal_importance: float
    valence: float
    persistence: float
    primary_emotion: EmotionType
    summary_source: str


# 确定性兜底：只根据事件类型与方向角色给出合理数值，不发明新事实、
# 不改变事件结果，summary 只复述“我方视角”，不新增情节。
_RULE_PROFILES: dict[str, AppraisalRuleProfile] = {
    "winner": AppraisalRuleProfile(
        0.45, 0.25, 0.30, EmotionType.CALM, "I prevailed over {focus_name} in that fight."
    ),
    "loser": AppraisalRuleProfile(
        0.60, -0.50, 0.50, EmotionType.ANGRY, "{focus_name} defeated me in that fight."
    ),
    # `battle_kill` 的 victim 按定义已经死亡，永远不会成为 appraiser，
    # 因此这里只有 killer 一侧的画像。
    "killer": AppraisalRuleProfile(
        0.70, -0.20, 0.60, EmotionType.CALM, "I took {focus_name}'s life."
    ),
    "partner": AppraisalRuleProfile(
        0.85, 0.90, 0.80, EmotionType.HAPPY, "{focus_name} and I became lovers."
    ),
    "suitor": AppraisalRuleProfile(
        0.55, -0.45, 0.40, EmotionType.SAD, "{focus_name} refused my confession."
    ),
    "rejecter": AppraisalRuleProfile(
        0.30, -0.10, 0.20, EmotionType.CONFUSED, "I turned {focus_name} down."
    ),
    "sworn_sibling": AppraisalRuleProfile(
        0.70, 0.80, 0.70, EmotionType.HAPPY, "{focus_name} and I became sworn siblings."
    ),
    "proposer": AppraisalRuleProfile(
        0.45, -0.35, 0.35, EmotionType.SAD, "{focus_name} refused to become my sworn sibling."
    ),
    "bonded": AppraisalRuleProfile(
        0.80, 0.85, 0.80, EmotionType.HAPPY, "{focus_name} and I are bound as master and disciple."
    ),
}

_DEFAULT_RULE_PROFILE = AppraisalRuleProfile(
    0.40, 0.0, 0.30, EmotionType.CALM, "What happened between {focus_name} and me stayed with me."
)


@dataclass(frozen=True)
class AppraisalCandidate:
    """一个待生成的解读：appraiser 对 focus 就 event 的个人解读。"""

    candidate_id: str
    event: "Event"
    appraiser: "Avatar"
    focus: "Avatar"
    role: str


def _is_named(avatar: "Avatar | None") -> bool:
    if avatar is None:
        return False
    return bool(str(getattr(avatar, "name", "") or "").strip())


def _can_appraise(avatar: "Avatar | None") -> bool:
    """只有在世且有名字的角色才会形成个人解读。

    被解读的一方（focus）只要求有名字：`battle_kill` 的受害者按定义已经
    死亡，若也要求 focus 在世，杀人事件将永远无法产生任何解读。
    """
    return _is_named(avatar) and not getattr(avatar, "is_dead", False)


def _resolve_participants(world: "World", event: "Event") -> tuple["Avatar", "Avatar"] | None:
    """从结构化 render_params 中解析恰好两个参与者；任一条件不满足则返回 None。"""
    keys = _PARTICIPANT_KEYS.get(event.event_type)
    if keys is None:
        return None

    params = event.render_params or {}
    first_id = params.get(keys[0])
    second_id = params.get(keys[1])
    if not first_id or not second_id:
        return None
    if str(first_id) == str(second_id):
        return None

    manager = world.avatar_manager
    first = manager.get_avatar(str(first_id))
    second = manager.get_avatar(str(second_id))
    if first is None or second is None:
        return None
    return first, second


def build_appraisal_candidates(world: "World", events: Iterable["Event"]) -> list[AppraisalCandidate]:
    """为本月事件构造候选解读，A 评价 B 与 B 评价 A 各一条。

    只接受：重要（is_major）、非故事、受支持类型、结构化提供了恰好两个
    参与者 ID 的事件。每个方向单独判定资格：appraiser（评价者）必须在世
    且有名字；focus（被评价者）只要求有名字，允许已经死亡——
    `battle_kill` 的受害者按定义已经死亡，若也要求 focus 在世，
    杀人事件将永远无法产生任何解读。
    """
    candidates: list[AppraisalCandidate] = []
    for event in events:
        if not getattr(event, "is_major", False) or getattr(event, "is_story", False):
            continue
        participants = _resolve_participants(world, event)
        if participants is None:
            continue

        first, second = participants
        roles = _PARTICIPANT_ROLES.get(event.event_type, ("participant", "participant"))
        for appraiser, focus, role in (
            (first, second, roles[0]),
            (second, first, roles[1]),
        ):
            # 死者不会形成新的记忆；无名者不进入解读体系。
            # 单侧缺失是正常结果（如 battle_kill 只有凶手一侧）。
            if not _can_appraise(appraiser) or not _is_named(focus):
                continue
            candidates.append(
                AppraisalCandidate(
                    candidate_id=uuid.uuid4().hex,
                    event=event,
                    appraiser=appraiser,
                    focus=focus,
                    role=role,
                )
            )
    return candidates


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _build_rule_appraisal(candidate: AppraisalCandidate) -> EventAppraisal:
    profile = _RULE_PROFILES.get(candidate.role, _DEFAULT_RULE_PROFILE)
    summary = t(profile.summary_source, focus_name=candidate.focus.name)
    return EventAppraisal(
        event_id=candidate.event.id,
        appraiser_avatar_id=str(candidate.appraiser.id),
        focus_avatar_id=str(candidate.focus.id),
        personal_importance=profile.personal_importance,
        valence=profile.valence,
        persistence=profile.persistence,
        primary_emotion=profile.primary_emotion,
        summary=summary[:MAX_APPRAISAL_SUMMARY_LENGTH],
        source=AppraisalSource.RULE,
    )


def _build_llm_appraisal(candidate: AppraisalCandidate, item: dict[str, Any]) -> EventAppraisal | None:
    """把一条 AI 输出转成 EventAppraisal；字段异常时返回 None 交给规则兜底。"""
    importance = _coerce_number(item.get("personal_importance"))
    valence = _coerce_number(item.get("valence"))
    persistence = _coerce_number(item.get("persistence"))
    if importance is None or valence is None or persistence is None:
        return None

    try:
        emotion = EmotionType(str(item.get("primary_emotion", "")))
    except ValueError:
        return None

    raw_summary = item.get("summary")
    if not isinstance(raw_summary, str):
        return None
    summary = raw_summary.strip()
    if not summary:
        return None

    return EventAppraisal(
        event_id=candidate.event.id,
        appraiser_avatar_id=str(candidate.appraiser.id),
        focus_avatar_id=str(candidate.focus.id),
        personal_importance=_clamp(importance, 0.0, 1.0),
        valence=_clamp(valence, -1.0, 1.0),
        persistence=_clamp(persistence, 0.0, 1.0),
        primary_emotion=emotion,
        summary=summary[:MAX_APPRAISAL_SUMMARY_LENGTH],
        source=AppraisalSource.LLM,
    )


def _serialize_candidate(candidate: AppraisalCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "appraiser_name": candidate.appraiser.name,
        "focus_name": candidate.focus.name,
        "role": candidate.role,
        "event_type": candidate.event.event_type,
        "event_text": str(candidate.event.content),
    }


def _resolve_template_path() -> Path:
    return resolve_locale_template_path(
        APPRAISAL_TEMPLATE_FILENAME,
        preferred_dir=CONFIG.paths.templates,
    )


async def _request_ai_appraisals(candidates: list[AppraisalCandidate]) -> dict[str, dict[str, Any]]:
    """一次批量调用；返回 candidate_id -> 原始条目。失败时返回空字典。"""
    serialized = [_serialize_candidate(item) for item in candidates]
    infos = {
        "candidate_count": len(candidates),
        # `candidates` 是结构化载荷（供本模块与测试消费），
        # `candidates_json` 是模板真正插值的文本形式。
        "candidates": serialized,
        "candidates_json": to_json_str_with_intent(serialized),
    }
    try:
        result = await call_llm_with_task_name(
            task_name=APPRAISAL_TASK_NAME,
            template_path=_resolve_template_path(),
            infos=infos,
        )
    except Exception as exc:  # provider / parse / timeout：整批退回规则兜底
        get_logger().logger.warning("Event appraisal batch failed, using rule fallback: %s", exc)
        return {}

    if not isinstance(result, dict):
        return {}
    raw_items = result.get("appraisals")
    if not isinstance(raw_items, list):
        return {}

    known_ids = {item.candidate_id for item in candidates}
    seen_counts: dict[str, int] = {}
    first_entry: dict[str, dict[str, Any]] = {}
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        candidate_id = str(entry.get("candidate_id", ""))
        # 伪造 ID（不在 known_ids 里）直接丢弃。
        if candidate_id not in known_ids:
            continue
        seen_counts[candidate_id] = seen_counts.get(candidate_id, 0) + 1
        first_entry.setdefault(candidate_id, entry)

    # 一个已知候选如果在响应里出现了不止一次，说明这条结果本身不可信
    # （模型echo错了、或者输出被截断重复），整条候选作废交给规则兜底，
    # 而不是悄悄采用第一条——那会把一次不可信的重复伪装成正常结果。
    return {
        candidate_id: entry
        for candidate_id, entry in first_entry.items()
        if seen_counts[candidate_id] == 1
    }


async def generate_appraisals_for_events(world: "World", events: Iterable["Event"]) -> None:
    """为本月事件生成个人解读，并挂载到各自的 `event.appraisals`。

    本函数永远不抛异常：任何失败都退化为确定性规则兜底。
    """
    try:
        candidates = build_appraisal_candidates(world, events)
        if not candidates:
            return

        ai_candidates = candidates[:MAX_AI_APPRAISAL_CANDIDATES]
        ai_results = await _request_ai_appraisals(ai_candidates) if ai_candidates else {}

        for candidate in candidates:
            try:
                appraisal = None
                entry = ai_results.get(candidate.candidate_id)
                if entry is not None:
                    appraisal = _build_llm_appraisal(candidate, entry)
                if appraisal is None:
                    appraisal = _build_rule_appraisal(candidate)
                candidate.event.appraisals.append(appraisal)
            except Exception as exc:
                # 单个候选的构建异常只丢弃这一条，绝不能拖垮同批其余候选。
                get_logger().logger.error(
                    "Event appraisal build failed for candidate %s: %s", candidate.candidate_id, exc
                )
    except Exception as exc:  # 解读失败绝不暂停或回滚当月
        get_logger().logger.error("Event appraisal generation failed: %s", exc)

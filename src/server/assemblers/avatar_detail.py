from __future__ import annotations

from typing import Any, Callable


def build_avatar_detail(
    avatar: Any,
    *,
    resolve_avatar_pic_id: Callable[[Any], int],
) -> dict[str, Any]:
    info = avatar.get_structured_info()
    info["pic_id"] = resolve_avatar_pic_id(avatar)
    info["realm_id"] = avatar.cultivation_progress.realm.value
    info["personal_appraisals"] = _build_personal_appraisals(avatar)
    return info


def build_emotion_display(emotion: Any) -> dict[str, str]:
    """把 EmotionType 转成前端可直接渲染的 {name, emoji, desc}。

    前端 vue-i18n 词条里没有 "emotion_angry" 这类原始枚举值，只有后端
    gettext 才认识它们，所以任何要展示给玩家的情绪都必须在这里、
    在后端完成翻译，而不是把原始枚举值传给前端再指望它能翻译。
    """
    from src.classes.emotions import EMOTION_EMOJIS, EmotionType
    from src.i18n import t

    return {
        "name": t(emotion.value),
        "emoji": EMOTION_EMOJIS.get(emotion, EMOTION_EMOJIS[EmotionType.CALM]),
        "desc": t(emotion.value),
    }


def resolve_appraisal_focus_name(
    focus_avatar_id: str,
    *,
    focus_avatar: Any | None,
    source_event: Any | None,
) -> str:
    """解析被解读者的显示名，活人优先，其次回落到来源事件的名称快照。

    `AvatarManager.cleanup_long_dead_avatars` 会在死亡 50 年后彻底移除
    角色，此时 `get_avatar` 返回 None。而 `persistence=1.0` 的解读永远
    不衰减，所以"对早已作古的仇敌的终身怨恨"恰恰是最可能失去名字的那
    一条。`Event.subject_snapshots` 正是为这种情况存在的（见
    src/classes/event.py），这里复用它而不是渲染空名字。
    """
    name = str(getattr(focus_avatar, "name", "") or "") if focus_avatar is not None else ""
    if name:
        return name
    snapshots = getattr(source_event, "subject_snapshots", None) or {}
    return str(snapshots.get(str(focus_avatar_id), "") or "")


def _build_personal_appraisals(avatar: Any) -> list[dict[str, Any]]:
    """本角色作为 appraiser 的个人解读，按当前有效权重降序，最多 10 条。

    见 docs/specs/personal-appraisal-politics.md（"Query and UI"）。
    """
    from src.systems.sect_decision_context import MIN_APPRAISAL_EFFECTIVE_WEIGHT
    from src.systems.time import get_date_str

    world = getattr(avatar, "world", None)
    event_manager = getattr(world, "event_manager", None) if world is not None else None
    if event_manager is None:
        return []

    # `Memórias marcantes` 有明确的下限：spec 把定性强度定义为
    # strong >= 0.65 / moderate >= 0.35 / weak >= 0.15，0.15 以下没有
    # 对应的展示分级，因此这里过滤掉，而不是让它们渲染成 "weak"。
    # 缺失存储的情况已由上面的 event_manager is None 分支处理；
    # 这里不吞掉真实的查询异常。
    scored_items = event_manager.get_scored_event_appraisals(
        str(avatar.id), int(world.month_stamp),
        min_effective_weight=MIN_APPRAISAL_EFFECTIVE_WEIGHT, limit=10,
    )

    entries: list[dict[str, Any]] = []
    for scored in scored_items:
        appraisal = scored.appraisal
        focus_avatar = world.avatar_manager.get_avatar(appraisal.focus_avatar_id)
        source_event = event_manager.get_event_by_id(appraisal.event_id)
        entries.append(
            {
                "appraisal_id": appraisal.id,
                "focus_avatar_id": appraisal.focus_avatar_id,
                "focus_avatar_name": resolve_appraisal_focus_name(
                    appraisal.focus_avatar_id,
                    focus_avatar=focus_avatar,
                    source_event=source_event,
                ),
                "emotion": build_emotion_display(appraisal.primary_emotion),
                "summary": appraisal.summary,
                "source_event_id": appraisal.event_id,
                "source_event_date": get_date_str(int(scored.source_event_month_stamp)),
                "valence": appraisal.valence,
                "effective_weight": scored.effective_weight,
            }
        )
    return entries

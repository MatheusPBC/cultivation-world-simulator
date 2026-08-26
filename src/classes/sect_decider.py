from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.classes.agent_decision import AgentDecision
from src.classes.alignment import Alignment
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import Event, FactKind
from src.classes.sect_ranks import get_rank_from_realm
from src.classes.state_delta import StateDelta
from src.config import get_settings_service
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.run.log import get_logger
from src.classes.technique import (
    Technique,
    TechniqueAttribute,
    is_attribute_compatible_with_root,
    techniques_by_name,
)
from src.systems.sect_decision_context import (
    MAX_APPRAISALS_PER_TARGET,
    MIN_APPRAISAL_EFFECTIVE_WEIGHT,
)
from src.systems.single_choice import (
    SectRecruitmentRequest,
    resolve_sect_recruitment,
)
from src.utils.config import CONFIG
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ParseError
from src.utils.llm.validation import is_llm_runtime_configured
from src.utils.strings import to_json_str_with_intent

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar
    from src.classes.core.sect import Sect
    from src.classes.core.world import World
    from src.systems.sect_decision_context import SectDecisionContext


DIPLOMACY_ACTION_DECLARE_WAR = "declare_war"
DIPLOMACY_ACTION_SEEK_PEACE = "seek_peace"
_VALID_DIPLOMACY_ACTIONS = frozenset({DIPLOMACY_ACTION_DECLARE_WAR, DIPLOMACY_ACTION_SEEK_PEACE})

# 语义外交状态，用于 StateDelta 的 before/after。
_DIPLOMACY_STATUS_WAR = "war"
_DIPLOMACY_STATUS_PEACE = "peace"


def normalize_sect_pair_id(sect_a_id: int, sect_b_id: int) -> str:
    """规范化的宗门对 ID：`min:max`，与谁发起该动作无关。"""
    first, second = sorted((int(sect_a_id), int(sect_b_id)))
    return f"{first}:{second}"


@dataclass(slots=True)
class SectDecisionResult:
    events: list[Event] = field(default_factory=list)
    war_declared_count: int = 0
    peace_made_count: int = 0
    recruitment_count: int = 0
    expulsion_count: int = 0
    technique_reward_count: int = 0
    support_count: int = 0
    summary_text: str = ""
    # 本轮决策的审计事件（fact_kind=DECISION），每轮恒有一条，包括
    # 无动作与规则兜底轮次。
    decision_event: Event | None = None


@dataclass(slots=True)
class DiplomacyAction:
    """一次已通过校验的外交动作及其引用的个人解读证据。

    `appraisal_ids` 可以为空——纯战略动作不需要任何私人记忆作为依据。
    """

    action: str
    other_sect_id: int
    appraisal_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SectDecisionPlan:
    diplomacy_actions: list[DiplomacyAction] = field(default_factory=list)
    recruit_avatar_ids: list[str] = field(default_factory=list)
    expel_avatar_ids: list[str] = field(default_factory=list)
    reward_avatar_ids: list[str] = field(default_factory=list)
    support_avatar_ids: list[str] = field(default_factory=list)
    thinking: str = ""


class SectDecider:
    """
    按配置周期执行的宗门行政决策执行器。
    """

    @classmethod
    async def decide(
        cls,
        sect: "Sect",
        decision_context: "SectDecisionContext",
        world: "World",
    ) -> SectDecisionResult:
        result = SectDecisionResult()

        recruit_cost = int(getattr(CONFIG.sect, "recruit_cost", 500))
        support_amount = int(getattr(CONFIG.sect, "support_amount", 300))
        plan = await cls._plan(sect, decision_context, world, recruit_cost=recruit_cost, support_amount=support_amount)

        # 每一轮都要留下一条审计记录，包括规则兜底与“本轮什么都不做”。
        # 决策事件先建立，后续制度动作才能把 MOTIVATED_BY 指向它。
        decision = AgentDecision(
            month_stamp=int(world.month_stamp),
            subject_kind="sect",
            subject_id=str(sect.id),
            source="llm" if plan is not None else "rule",
            considered_count=len(decision_context.diplomacy_targets),
            thinking=str(getattr(plan, "thinking", "") or ""),
        )
        decision_event = Event(
            world.month_stamp,
            t("{sect_name} concluded a round of sect decisions", sect_name=sect.name),
            related_sects=[int(sect.id)],
            is_major=False,
            fact_kind=FactKind.DECISION,
            causal_payload={"deltas": [], "decision": decision.to_dict()},
        )
        result.decision_event = decision_event

        cls._process_diplomacy(
            sect=sect,
            decision_context=decision_context,
            world=world,
            result=result,
            actions=list(plan.diplomacy_actions) if plan is not None else [],
            decision=decision,
            decision_event=decision_event,
        )

        await cls._process_recruitment(
            sect=sect,
            decision_context=decision_context,
            world=world,
            recruit_cost=recruit_cost,
            result=result,
            selected_ids=set(plan.recruit_avatar_ids) if plan is not None else None,
            decision=decision,
        )

        cls._process_members(
            sect=sect,
            world=world,
            support_amount=support_amount,
            result=result,
            expel_ids=set(plan.expel_avatar_ids) if plan is not None else None,
            reward_ids=set(plan.reward_avatar_ids) if plan is not None else None,
            support_ids=set(plan.support_avatar_ids) if plan is not None else None,
            decision=decision,
        )

        result.summary_text = cls._build_summary(sect, result)
        # 制度动作全部执行完毕后，把最终的 chosen_chain 写回审计事件。
        decision_event.causal_payload = {"deltas": [], "decision": decision.to_dict()}
        result.events.append(decision_event)
        return result

    @classmethod
    async def _plan(
        cls,
        sect: "Sect",
        decision_context: "SectDecisionContext",
        world: "World",
        *,
        recruit_cost: int,
        support_amount: int,
    ) -> SectDecisionPlan | None:
        if not cls._llm_available():
            cls._warn_plan_skip(sect, "LLM runtime config unavailable")
            return None

        infos = {
            "sect_name": sect.name,
            "world_info": to_json_str_with_intent(cls._serialize_world_info(world)),
            "world_lore": world.world_lore.text,
            "decision_context_info": to_json_str_with_intent(cls._serialize_context(decision_context)),
            "decision_interval_years": int(getattr(CONFIG.sect, "decision_interval_years", 5)),
            "recruit_cost": recruit_cost,
            "support_amount": support_amount,
        }

        try:
            result = await call_llm_with_task_name(
                task_name="sect_decider",
                template_path=cls._resolve_template_path(),
                infos=infos,
            )
            return cls._parse_plan(result, decision_context)
        except (LLMError, ParseError, Exception) as exc:
            cls._warn_plan_skip(sect, f"LLM plan failed: {exc}")
            return None

    @classmethod
    def _llm_available(cls) -> bool:
        profile, api_key = get_settings_service().get_llm_runtime_config()
        return is_llm_runtime_configured(profile, api_key)

    @classmethod
    def _warn_plan_skip(cls, sect: "Sect", reason: str) -> None:
        get_logger().logger.warning(
            "SectDecider using fallback execution for %s(%s): %s",
            getattr(sect, "name", "unknown"),
            getattr(sect, "id", "unknown"),
            reason,
        )

    @classmethod
    def _resolve_template_path(cls) -> Path:
        return resolve_locale_template_path(
            "sect_decider.txt",
            preferred_dir=CONFIG.paths.templates,
        )

    @classmethod
    def _serialize_world_info(cls, world: "World") -> dict[str, Any]:
        try:
            info = world.get_info(detailed=True)
            if isinstance(info, dict):
                return info
        except Exception:
            pass
        return {}

    @classmethod
    def _serialize_context(cls, ctx: "SectDecisionContext") -> dict[str, Any]:
        return {
            "basic_structured": dict(ctx.basic_structured),
            "basic_text": ctx.basic_text,
            "identity": dict(ctx.identity),
            "power": dict(ctx.power),
            "territory": dict(ctx.territory),
            "self_assessment": dict(ctx.self_assessment),
            "economy": dict(ctx.economy),
            "rule": dict(ctx.rule),
            "diplomacy_targets": list(ctx.diplomacy_targets),
            "active_wars": list(ctx.active_wars),
            "recruitment_candidates": list(ctx.recruitment_candidates),
            "member_candidates": list(ctx.member_candidates),
            "relations": list(ctx.relations),
            "relations_summary": ctx.relations_summary,
            "history": {
                "summary_text": str(ctx.history.get("summary_text", "")),
            },
        }

    @classmethod
    def _parse_plan(
        cls,
        payload: dict[str, Any] | Any,
        decision_context: "SectDecisionContext",
    ) -> SectDecisionPlan | None:
        if not isinstance(payload, dict):
            return None

        recruit_valid = {str(item["avatar_id"]) for item in decision_context.recruitment_candidates}
        member_valid = {str(item["avatar_id"]) for item in decision_context.member_candidates}

        def _pick_ids(key: str, valid_ids: set[str]) -> list[str]:
            raw = payload.get(key, [])
            if not isinstance(raw, list):
                return []
            deduped: list[str] = []
            seen: set[str] = set()
            for item in raw:
                value = str(item)
                if value in valid_ids and value not in seen:
                    seen.add(value)
                    deduped.append(value)
            return deduped

        return SectDecisionPlan(
            diplomacy_actions=cls._parse_diplomacy_actions(payload, decision_context),
            recruit_avatar_ids=_pick_ids("recruit_avatar_ids", recruit_valid),
            expel_avatar_ids=_pick_ids("expel_avatar_ids", member_valid),
            reward_avatar_ids=_pick_ids("reward_avatar_ids", member_valid),
            support_avatar_ids=_pick_ids("support_avatar_ids", member_valid),
            thinking=str(payload.get("thinking", "") or ""),
        )

    @classmethod
    def _parse_diplomacy_actions(
        cls,
        payload: dict[str, Any],
        decision_context: "SectDecisionContext",
    ) -> list[DiplomacyAction]:
        """校验模型给出的外交动作与其引用的个人解读证据。

        证据必须来自该目标自己的上下文——那份上下文已经保证了
        “appraiser 是本宗现任在世掌门、focus 是对方现任在世掌门”。
        因此未知、伪造、重复、跨目标以及引用了前任掌门（本轮上下文中
        不存在）的引用，都会在这里被拒绝。任何一条引用不合法，只作废
        该条外交动作，其余动作与其他决策字段照常执行。
        """
        allowed_appraisals_by_target: dict[int, set[str]] = {}
        for item in decision_context.diplomacy_targets:
            if item.get("other_sect_id") is None:
                continue
            allowed_appraisals_by_target[int(item["other_sect_id"])] = {
                str(entry.get("appraisal_id", ""))
                for entry in (item.get("personal_appraisals") or [])
            }

        raw_actions = payload.get("diplomacy_actions", [])
        if not isinstance(raw_actions, list):
            return []

        actions: list[DiplomacyAction] = []
        seen_targets: set[int] = set()
        for raw in raw_actions:
            if not isinstance(raw, dict):
                continue
            action_name = str(raw.get("action", ""))
            if action_name not in _VALID_DIPLOMACY_ACTIONS:
                continue
            try:
                other_sect_id = int(raw.get("other_sect_id"))
            except (TypeError, ValueError):
                continue
            allowed_appraisals = allowed_appraisals_by_target.get(other_sect_id)
            if allowed_appraisals is None:
                # 目标不在本轮外交候选中：不允许凭空发明对手。
                continue
            # 同一目标只接受一条外交动作，避免同轮自相矛盾。
            if other_sect_id in seen_targets:
                continue

            raw_ids = raw.get("appraisal_ids", [])
            if not isinstance(raw_ids, list):
                continue
            citations: list[str] = [str(item) for item in raw_ids]
            if len(set(citations)) != len(citations):
                cls._warn_invalid_citation(other_sect_id, "duplicated appraisal citation")
                continue
            if any(citation not in allowed_appraisals for citation in citations):
                cls._warn_invalid_citation(other_sect_id, "unknown or mismatched appraisal citation")
                continue

            seen_targets.add(other_sect_id)
            actions.append(
                DiplomacyAction(
                    action=action_name,
                    other_sect_id=other_sect_id,
                    appraisal_ids=citations,
                )
            )
        return actions

    @classmethod
    def _warn_invalid_citation(cls, other_sect_id: int, reason: str) -> None:
        get_logger().logger.warning(
            "Discarding sect diplomacy action against sect %s: %s", other_sect_id, reason
        )

    @classmethod
    def _process_diplomacy(
        cls,
        *,
        sect: "Sect",
        decision_context: "SectDecisionContext",
        world: "World",
        result: SectDecisionResult,
        actions: list[DiplomacyAction],
        decision: AgentDecision,
        decision_event: Event,
    ) -> None:
        target_by_id = {
            int(item["other_sect_id"]): item
            for item in decision_context.diplomacy_targets
            if item.get("other_sect_id") is not None
        }
        source_event_by_appraisal = cls._map_appraisal_to_source_event(decision_context)
        cited_source_event_ids: list[str] = []

        for action in actions:
            target = target_by_id.get(int(action.other_sect_id))
            if target is None:
                continue

            # 以“执行时的真实外交状态”为准，而不是上下文快照：同一轮里
            # 另一个宗门可能已经改变了这对关系，用快照会写出错误的
            # before 值，或重复执行一次已经成立的状态转移。
            live_state = world.get_sect_diplomacy_state(
                int(sect.id), int(action.other_sect_id), current_month=int(world.month_stamp)
            )
            before_status = str(live_state.get("status", _DIPLOMACY_STATUS_PEACE) or _DIPLOMACY_STATUS_PEACE)

            if action.action == DIPLOMACY_ACTION_DECLARE_WAR:
                if before_status == _DIPLOMACY_STATUS_WAR:
                    continue
                after_status = _DIPLOMACY_STATUS_WAR
                world.declare_sect_war(
                    sect_a_id=int(sect.id),
                    sect_b_id=int(action.other_sect_id),
                    reason=str(target.get("other_sect_name", "") or ""),
                )
                result.war_declared_count += 1
                content = t(
                    "{sect_name} declared war on {target_name}; from this point on, the two sects are at war.",
                    sect_name=sect.name,
                    target_name=target["other_sect_name"],
                )
            else:
                if before_status != _DIPLOMACY_STATUS_WAR:
                    continue
                after_status = _DIPLOMACY_STATUS_PEACE
                world.make_sect_peace(
                    sect_a_id=int(sect.id),
                    sect_b_id=int(action.other_sect_id),
                    reason=str(target.get("other_sect_name", "") or ""),
                )
                result.peace_made_count += 1
                content = t(
                    "{sect_name} made peace with {target_name}, and the state of war between them came to an end.",
                    sect_name=sect.name,
                    target_name=target["other_sect_name"],
                )

            # Event 先建立（拿到它的真实 id），StateDelta 再引用该 id 构造——
            # 避免先序列化一个 event_id="" 的 delta 再回填，那样容易在
            # 忘记回填时留下一个不指向自己的 delta。
            transition_event = Event(
                month_stamp=world.month_stamp,
                content=content,
                related_sects=[int(sect.id), int(action.other_sect_id)],
                is_major=True,
                fact_kind=FactKind.STATE_TRANSITION,
            )
            delta = StateDelta(
                event_id=transition_event.id,
                owner_kind="sect_diplomacy",
                owner_id=normalize_sect_pair_id(sect.id, action.other_sect_id),
                aspect="status",
                before=before_status,
                after=after_status,
            )
            transition_event.causal_payload = {"deltas": [delta.to_dict()]}
            # 结果事件由本次决策引发。
            transition_event.causal_links.append(
                CausalLink(
                    event_id=transition_event.id,
                    cause_event_id=decision_event.id,
                    relation=CausalRelation.MOTIVATED_BY,
                )
            )
            result.events.append(transition_event)

            decision.chosen_chain.append(
                {
                    "action_name": action.action,
                    "params": {"other_sect_id": int(action.other_sect_id)},
                    "appraisal_ids": list(action.appraisal_ids),
                }
            )
            for appraisal_id in action.appraisal_ids:
                source_event_id = source_event_by_appraisal.get(appraisal_id)
                if source_event_id and source_event_id not in cited_source_event_ids:
                    cited_source_event_ids.append(source_event_id)

        # 决策事件由被引用的那些原始事件所激励。
        for source_event_id in cited_source_event_ids:
            decision_event.causal_links.append(
                CausalLink(
                    event_id=decision_event.id,
                    cause_event_id=source_event_id,
                    relation=CausalRelation.MOTIVATED_BY,
                )
            )

    @classmethod
    def _record_institutional_step(cls, decision: AgentDecision, action_name: str, avatar_id: str) -> None:
        """把一次已经执行的非外交制度动作记入审计链。

        `appraisal_ids` 恒为空：个人解读只是外交证据，不参与人事决策。
        """
        decision.chosen_chain.append(
            {
                "action_name": action_name,
                "params": {"avatar_id": str(avatar_id)},
                "appraisal_ids": [],
            }
        )

    @classmethod
    def _map_appraisal_to_source_event(cls, decision_context: "SectDecisionContext") -> dict[str, str]:
        mapping: dict[str, str] = {}
        for item in decision_context.diplomacy_targets:
            for entry in item.get("personal_appraisals") or []:
                appraisal_id = str(entry.get("appraisal_id", ""))
                source_event_id = str(entry.get("source_event_id", ""))
                if appraisal_id and source_event_id:
                    mapping[appraisal_id] = source_event_id
        return mapping

    @classmethod
    async def _process_recruitment(
        cls,
        *,
        sect: "Sect",
        decision_context: "SectDecisionContext",
        world: "World",
        recruit_cost: int,
        result: SectDecisionResult,
        selected_ids: set[str] | None,
        decision: AgentDecision,
    ) -> None:
        avatars = getattr(getattr(world, "avatar_manager", None), "avatars", {}) or {}
        for candidate in decision_context.recruitment_candidates:
            if selected_ids is not None and candidate["avatar_id"] not in selected_ids:
                continue
            if int(getattr(sect, "magic_stone", 0)) < recruit_cost:
                break
            if not candidate.get("alignment_recruitable", False):
                continue
            if not candidate.get("race_recruitable", True):
                continue

            avatar = avatars.get(candidate["avatar_id"])
            if avatar is None or getattr(avatar, "is_dead", False):
                continue
            if getattr(avatar, "sect", None) is not None:
                continue
            if not sect.accepts_avatar_race(avatar):
                continue

            outcome = await resolve_sect_recruitment(
                SectRecruitmentRequest(
                    sect=sect,
                    avatar=avatar,
                    cost=recruit_cost,
                )
            )
            result.events.append(
                Event(
                    month_stamp=world.month_stamp,
                    content=outcome.result_text,
                    related_avatars=[avatar.id],
                    related_sects=[int(sect.id)],
                    is_major=False,
                )
            )

            if not outcome.accepted:
                continue
            if int(getattr(sect, "magic_stone", 0)) < recruit_cost:
                continue

            sect.magic_stone -= recruit_cost
            avatar.join_sect(sect, get_rank_from_realm(avatar.cultivation_progress.realm))
            result.recruitment_count += 1
            cls._record_institutional_step(decision, "recruit", avatar.id)
            result.events.append(
                Event(
                    month_stamp=world.month_stamp,
                    content=t(
                        "{sect_name} spent {cost} spirit stones to recruit {avatar_name}; {avatar_name} officially became a disciple of the sect.",
                        sect_name=sect.name,
                        cost=recruit_cost,
                        avatar_name=avatar.name,
                    ),
                    related_avatars=[avatar.id],
                    related_sects=[int(sect.id)],
                    is_major=True,
                )
            )

    @classmethod
    def _process_members(
        cls,
        *,
        sect: "Sect",
        world: "World",
        support_amount: int,
        result: SectDecisionResult,
        expel_ids: set[str] | None,
        reward_ids: set[str] | None,
        support_ids: set[str] | None,
        decision: AgentDecision,
    ) -> None:
        sorted_members = sect.get_living_members_sorted_by_status()
        if support_ids is None:
            support_limit = max(1, int(getattr(CONFIG.sect, "support_top_n_per_cycle", 2) or 2))
            support_candidates = [
                avatar
                for avatar in sorted_members
                if int(getattr(getattr(avatar, "magic_stone", None), "value", 0)) < support_amount
            ]
            support_ids = {
                str(getattr(avatar, "id", ""))
                for avatar in support_candidates[:support_limit]
            }

        for avatar in sorted_members:
            if getattr(avatar, "is_dead", False):
                continue

            avatar_id = str(getattr(avatar, "id", ""))

            if sect.is_member_rule_breaker(avatar) and (expel_ids is None or avatar_id in expel_ids):
                avatar.leave_sect()
                result.expulsion_count += 1
                cls._record_institutional_step(decision, "expel", avatar_id)
                result.events.append(
                    Event(
                        month_stamp=world.month_stamp,
                        content=t(
                            "{sect_name} judged that {avatar_name} had gravely violated the sect rules and expelled them from the sect.",
                            sect_name=sect.name,
                            avatar_name=avatar.name,
                        ),
                        related_avatars=[avatar.id],
                        related_sects=[int(sect.id)],
                        is_major=True,
                    )
                )
                continue

            reward_technique = cls._pick_reward_technique(sect, avatar)
            if (
                reward_ids is None or avatar_id in reward_ids
            ) and reward_technique is not None and cls._can_replace_technique(avatar, reward_technique):
                avatar.technique = reward_technique
                result.technique_reward_count += 1
                cls._record_institutional_step(decision, "reward_technique", avatar_id)
                result.events.append(
                    Event(
                        month_stamp=world.month_stamp,
                        content=t(
                            "{sect_name} bestowed the technique \"{technique_name}\" upon {avatar_name}.",
                            sect_name=sect.name,
                            technique_name=reward_technique.name,
                            avatar_name=avatar.name,
                        ),
                        related_avatars=[avatar.id],
                        related_sects=[int(sect.id)],
                        is_major=True,
                    )
                )

            if support_ids is not None and avatar_id not in support_ids:
                continue
            if int(getattr(sect, "magic_stone", 0)) < support_amount:
                continue
            current_stones = int(getattr(getattr(avatar, "magic_stone", None), "value", 0))
            if current_stones >= support_amount:
                continue

            sect.magic_stone -= support_amount
            avatar.magic_stone += support_amount
            result.support_count += 1
            cls._record_institutional_step(decision, "support", avatar_id)
            result.events.append(
                Event(
                    month_stamp=world.month_stamp,
                    content=t(
                        "{sect_name} granted {amount} spirit stones to {avatar_name} in support of their cultivation.",
                        sect_name=sect.name,
                        amount=support_amount,
                        avatar_name=avatar.name,
                    ),
                    related_avatars=[avatar.id],
                    related_sects=[int(sect.id)],
                    is_major=False,
                )
            )

    @classmethod
    def _pick_reward_technique(cls, sect: "Sect", avatar: "Avatar") -> Technique | None:
        candidates: list[Technique] = []
        for technique_name in getattr(sect, "technique_names", []) or []:
            technique = techniques_by_name.get(technique_name)
            if technique is None:
                continue
            if not technique.is_allowed_for(avatar):
                continue
            if technique.attribute == TechniqueAttribute.EVIL and getattr(avatar, "alignment", None) != Alignment.EVIL:
                continue
            if not is_attribute_compatible_with_root(technique.attribute, avatar.root):
                continue
            candidates.append(technique)

        if not candidates:
            return None
        return random.choice(candidates)

    @classmethod
    def _grade_rank(cls, technique: Technique | None) -> int:
        grade = getattr(getattr(technique, "grade", None), "value", "")
        order = {"LOWER": 1, "MIDDLE": 2, "UPPER": 3}
        return order.get(str(grade), 0)

    @classmethod
    def _can_replace_technique(cls, avatar: "Avatar", new_technique: Technique) -> bool:
        current_technique = getattr(avatar, "technique", None)
        return cls._grade_rank(current_technique) <= cls._grade_rank(new_technique)

    @classmethod
    def _build_summary(cls, sect: "Sect", result: SectDecisionResult) -> str:
        parts = []
        if result.recruitment_count:
            parts.append(t("recruited {count} rogue cultivators", count=result.recruitment_count))
        if result.war_declared_count:
            parts.append(t("declared war {count} times", count=result.war_declared_count))
        if result.peace_made_count:
            parts.append(t("made peace {count} times", count=result.peace_made_count))
        if result.expulsion_count:
            parts.append(t("expelled {count} members", count=result.expulsion_count))
        if result.technique_reward_count:
            parts.append(t("bestowed techniques {count} times", count=result.technique_reward_count))
        if result.support_count:
            parts.append(t("granted spirit-stone support {count} times", count=result.support_count))
        if not parts:
            return t(
                "{sect_name} focused this round of sect decisions on consolidation and observation, with no major adjustments made.",
                sect_name=sect.name,
            )
        return t("{sect_name} this round of sect decisions:", sect_name=sect.name) + " " + "、".join(parts) + "。"

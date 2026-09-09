from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.classes.agent_decision import AgentDecision
from src.classes.alignment import Alignment
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
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
from src.systems.single_choice import (
    SectRecruitmentRequest,
    resolve_sect_recruitment,
)
from src.systems.sect_member_support import transfer_sect_member_support
from src.utils.config import CONFIG
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ParseError
from src.utils.llm.runtime_mode import is_test_mode_enabled, is_world_test_mode
from src.utils.llm.test_mode_fallbacks import resolve_test_mode_task
from src.utils.llm.validation import is_llm_runtime_configured
from src.utils.strings import to_json_str_with_intent

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar
    from src.classes.core.sect import Sect
    from src.classes.core.world import World
    from src.systems.sect_decision_context import SectDecisionContext


@dataclass(slots=True)
class SectDecisionResult:
    events: list[Event] = field(default_factory=list)
    recruitment_count: int = 0
    expulsion_count: int = 0
    technique_reward_count: int = 0
    support_count: int = 0
    summary_text: str = ""
    # 本轮决策的审计事件（fact_kind=DECISION），每轮恒有一条，包括
    # 无动作与规则兜底轮次。
    decision_event: Event | None = None


@dataclass(slots=True)
class SectDecisionPlan:
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
        # Recruiting and supporting both move `sect.magic_stone`, so the office
        # that could authorize that has to have a living holder. Asked before
        # planning: with nobody able to spend, no provider is consulted about
        # spending, and the round still leaves an honest audit record.
        may_spend = cls._may_dispose_treasury(sect, world)
        may_administer = cls._may_administer_sect(sect, world)
        # Planning is worth doing when the sect can do *something*; each act
        # then asks for its own scope at its own mutation point.
        plan = (
            await cls._plan(
                sect,
                decision_context,
                world,
                recruit_cost=recruit_cost,
                support_amount=support_amount,
            )
            if (may_spend or may_administer)
            else None
        )

        deterministic_plan = bool(
            plan is not None and (is_world_test_mode(world) or is_test_mode_enabled())
        )

        # 每一轮都要留下一条审计记录，包括规则兜底与“本轮什么都不做”。
        # 决策事件先建立，后续制度动作才能把 MOTIVATED_BY 指向它。
        decision = AgentDecision(
            month_stamp=int(world.month_stamp),
            subject_kind="sect",
            subject_id=str(sect.id),
            source="rule" if deterministic_plan or plan is None else "llm",
            considered_count=len(decision_context.member_candidates),
            thinking=str(getattr(plan, "thinking", "") or ""),
        )
        decision_event = Event(
            world.month_stamp,
            t("{sect_name} concluded a round of sect decisions", sect_name=sect.name),
            related_sects=[int(sect.id)],
            is_major=False,
            fact_kind=FactKind.DECISION,
            causal_origin=(
                CausalOrigin.DETERMINISTIC
                if deterministic_plan
                else (
                    CausalOrigin.LLM_INTERPRETATION
                    if plan is not None
                    else CausalOrigin.ACTOR_DECISION
                )
            ),
            causal_payload={"deltas": [], "decision": decision.to_dict()},
        )
        result.decision_event = decision_event

        if may_spend:
            await cls._process_recruitment(
                sect=sect,
                decision_context=decision_context,
                world=world,
                recruit_cost=recruit_cost,
                result=result,
                selected_ids=set(plan.recruit_avatar_ids) if plan is not None else set(),
                decision=decision,
                decision_event=decision_event,
            )

        cls._process_members(
            sect=sect,
            world=world,
            support_amount=support_amount,
            result=result,
            # No plan means nobody was chosen, not everybody: an absent plan
            # must never read as "expel every rule-breaker" or "reward all".
            expel_ids=set(plan.expel_avatar_ids) if plan is not None else set(),
            reward_ids=set(plan.reward_avatar_ids) if plan is not None else set(),
            support_ids=set(plan.support_avatar_ids) if plan is not None else set(),
            decision=decision,
            decision_event=decision_event,
            may_spend=may_spend,
            may_administer=may_administer,
        )

        result.summary_text = cls._build_summary(sect, result)
        # 制度动作全部执行完毕后，把最终的 chosen_chain 写回审计事件。
        decision_event.causal_payload = {"deltas": [], "decision": decision.to_dict()}
        result.events.append(decision_event)
        return result

    @staticmethod
    def _may_act_for_sect(sect: "Sect", world: "World", scope) -> bool:
        """Whether this sect can really act under this scope right now.

        No material control is required: neither a treasury nor a membership
        roll is territorial.
        """
        from src.classes.mechanical_language import EntityRef
        from src.systems.institution_authority import can_actor_act_for

        owner = EntityRef("sect", str(sect.id))
        return can_actor_act_for(
            world,
            owner,
            owner,
            scope,
            current_month=int(world.month_stamp),
        ).allowed

    @classmethod
    def _may_dispose_treasury(cls, sect: "Sect", world: "World") -> bool:
        from src.classes.institution import AuthorityScope

        return cls._may_act_for_sect(
            sect, world, AuthorityScope.TREASURY_DISPOSITION
        )

    @classmethod
    def _may_administer_sect(cls, sect: "Sect", world: "World") -> bool:
        """Ending a membership or replacing what a member was taught.

        Its own scope, not `RECOGNITION`: endorsing a public rite says nothing
        about who may do either of these.
        """
        from src.classes.institution import AuthorityScope

        return cls._may_act_for_sect(
            sect, world, AuthorityScope.SECT_ADMINISTRATION
        )

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
        infos = {
            "sect_name": sect.name,
            "world_info": to_json_str_with_intent(cls._serialize_world_info(world)),
            "world_lore": world.world_lore.text,
            "decision_context_info": to_json_str_with_intent(
                cls._serialize_context(decision_context)
            ),
            "decision_interval_years": int(
                getattr(CONFIG.sect, "decision_interval_years", 5)
            ),
            "recruit_cost": recruit_cost,
            "support_amount": support_amount,
        }

        if is_world_test_mode(world) or is_test_mode_enabled():
            fallback = resolve_test_mode_task("sect_decider", infos)
            return cls._parse_plan(fallback, decision_context)

        if not cls._llm_available():
            cls._warn_plan_skip(sect, "LLM runtime config unavailable")
            return None

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
            "SectDecider skipping unplanned execution for %s(%s): %s",
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
            # Observable Dao answers may inform a choice but never alter a
            # relation or create an institutional action by themselves.
            "celestial_dao": list(ctx.celestial_dao),
            # A public court conflict is context for judgment, not a diplomacy command.
            "imperial_crisis": dict(ctx.imperial_crisis)
            if ctx.imperial_crisis
            else None,
            # Read-only regional observations; these never authorize or execute
            # a new action by themselves.
            "regional_semantics": list(ctx.regional_semantics),
            "institutional_presence": list(ctx.institutional_presence),
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

        recruit_valid = {
            str(item["avatar_id"]) for item in decision_context.recruitment_candidates
        }
        member_valid = {
            str(item["avatar_id"]) for item in decision_context.member_candidates
        }

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
            recruit_avatar_ids=_pick_ids("recruit_avatar_ids", recruit_valid),
            expel_avatar_ids=_pick_ids("expel_avatar_ids", member_valid),
            reward_avatar_ids=_pick_ids("reward_avatar_ids", member_valid),
            support_avatar_ids=_pick_ids("support_avatar_ids", member_valid),
            thinking=str(payload.get("thinking", "") or ""),
        )

    @classmethod
    def _record_institutional_step(
        cls, decision: AgentDecision, action_name: str, avatar_id: str
    ) -> None:
        """把一次已经执行的宗门行政动作记入审计链。

        `appraisal_ids` 恒为空：个人解读从不参与人事决策，宣战也不再是
        本执行器的输出——它是 ``src.systems.institutional_war`` 拥有的
        独立制度决策。
        """
        decision.chosen_chain.append(
            {
                "action_name": action_name,
                "params": {"avatar_id": str(avatar_id)},
                "appraisal_ids": [],
            }
        )

    @classmethod
    async def _process_recruitment(
        cls,
        *,
        sect: "Sect",
        decision_context: "SectDecisionContext",
        world: "World",
        recruit_cost: int,
        result: SectDecisionResult,
        selected_ids: set[str],
        decision: AgentDecision,
        decision_event: Event,
    ) -> None:
        avatars = getattr(getattr(world, "avatar_manager", None), "avatars", {}) or {}
        for candidate in decision_context.recruitment_candidates:
            if candidate["avatar_id"] not in selected_ids:
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
            # Asked again per candidate before the invitation: a sect that can
            # no longer spend should not be inviting anyone.
            if not cls._may_dispose_treasury(sect, world):
                break

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
            # Re-read everything the acceptance rested on: the resolver was
            # awaited, and authority, life, membership and funds can all have
            # moved meanwhile. Without this the await would be the way past
            # the gate.
            if not cls._may_dispose_treasury(sect, world):
                break
            if getattr(avatar, "is_dead", False):
                continue
            if getattr(avatar, "sect", None) is not None:
                continue
            # `join_sect` refuses a race the sect does not accept, silently, so
            # eligibility is re-read here too: otherwise the treasury would be
            # debited and a membership delta written for a join that never
            # happened.
            if not sect.accepts_avatar_race(avatar):
                continue
            if int(getattr(sect, "magic_stone", 0)) < recruit_cost:
                continue

            before_sect = int(getattr(sect, "magic_stone", 0))
            avatar.join_sect(
                sect, get_rank_from_realm(avatar.cultivation_progress.realm)
            )
            if getattr(avatar, "sect", None) is not sect:
                # The owner refused after all; nothing is spent and no fact is
                # written for a membership that does not exist.
                continue
            sect.magic_stone -= recruit_cost
            result.recruitment_count += 1
            cls._record_institutional_step(decision, "recruit", avatar.id)
            # A real transition of two owners, not prose: the treasury really
            # fell and the avatar really joined, cited to the decision that
            # chose it.
            recruit_event = Event(
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
                fact_kind=FactKind.STATE_TRANSITION,
                causal_origin=CausalOrigin.ACTOR_DECISION,
            )
            recruit_event.causal_payload = {
                "deltas": [
                    StateDelta(
                        event_id=recruit_event.id,
                        owner_kind="sect",
                        owner_id=str(sect.id),
                        aspect="magic_stone",
                        before=str(before_sect),
                        after=str(sect.magic_stone),
                        magnitude=-recruit_cost,
                    ).to_dict(),
                    StateDelta(
                        event_id=recruit_event.id,
                        owner_kind="avatar",
                        owner_id=str(avatar.id),
                        aspect="sect_membership",
                        before="none",
                        after=str(sect.id),
                    ).to_dict(),
                ]
            }
            recruit_event.causal_links.append(
                CausalLink(
                    event_id=recruit_event.id,
                    cause_event_id=decision_event.id,
                    relation=CausalRelation.MOTIVATED_BY,
                )
            )
            result.events.append(recruit_event)

    @classmethod
    def _process_members(
        cls,
        *,
        sect: "Sect",
        world: "World",
        support_amount: int,
        result: SectDecisionResult,
        expel_ids: set[str],
        reward_ids: set[str],
        support_ids: set[str],
        decision: AgentDecision,
        decision_event: Event,
        may_spend: bool,
        may_administer: bool,
    ) -> None:
        for avatar in sect.get_living_members_sorted_by_status():
            if getattr(avatar, "is_dead", False):
                continue

            avatar_id = str(getattr(avatar, "id", ""))

            if (
                avatar_id in expel_ids
                and sect.is_member_rule_breaker(avatar)
                # Re-read at the mutation point: membership, life and the
                # authority to end it can all have moved since the plan.
                and getattr(avatar, "sect", None) is sect
                and may_administer
                and cls._may_administer_sect(sect, world)
            ):
                avatar.leave_sect()
                if getattr(avatar, "sect", None) is sect:
                    # The owner refused; no fact is written for a departure
                    # that did not happen.
                    continue
                result.expulsion_count += 1
                cls._record_institutional_step(decision, "expel", avatar_id)
                expel_event = Event(
                    month_stamp=world.month_stamp,
                    content=t(
                        "{sect_name} found {avatar_name} incompatible with its rules and ended their membership.",
                        sect_name=sect.name,
                        avatar_name=avatar.name,
                    ),
                    related_avatars=[avatar.id],
                    related_sects=[int(sect.id)],
                    is_major=True,
                    fact_kind=FactKind.STATE_TRANSITION,
                    causal_origin=CausalOrigin.ACTOR_DECISION,
                )
                expel_event.causal_payload = {
                    "deltas": [
                        StateDelta(
                            event_id=expel_event.id,
                            owner_kind="avatar",
                            owner_id=str(avatar.id),
                            aspect="sect_membership",
                            before=str(sect.id),
                            after="none",
                        ).to_dict()
                    ]
                }
                expel_event.causal_links.append(
                    CausalLink(
                        event_id=expel_event.id,
                        cause_event_id=decision_event.id,
                        relation=CausalRelation.MOTIVATED_BY,
                    )
                )
                result.events.append(expel_event)
                continue

            reward_technique = cls._pick_reward_technique(sect, avatar)
            before_technique = getattr(avatar, "technique", None)
            if (
                avatar_id in reward_ids
                and reward_technique is not None
                and cls._can_replace_technique(avatar, reward_technique)
                # Granting the same technique changes nothing, so it is not an
                # act and leaves no fact behind.
                and not cls._same_technique(before_technique, reward_technique)
                and getattr(avatar, "sect", None) is sect
                and may_administer
                and cls._may_administer_sect(sect, world)
            ):
                avatar.technique = reward_technique
                result.technique_reward_count += 1
                cls._record_institutional_step(decision, "reward_technique", avatar_id)
                reward_event = Event(
                    month_stamp=world.month_stamp,
                    content=t(
                        '{sect_name} bestowed the technique "{technique_name}" upon {avatar_name}.',
                        sect_name=sect.name,
                        technique_name=reward_technique.name,
                        avatar_name=avatar.name,
                    ),
                    related_avatars=[avatar.id],
                    related_sects=[int(sect.id)],
                    is_major=True,
                    fact_kind=FactKind.STATE_TRANSITION,
                    causal_origin=CausalOrigin.ACTOR_DECISION,
                )
                reward_event.causal_payload = {
                    "deltas": [
                        StateDelta(
                            event_id=reward_event.id,
                            owner_kind="avatar",
                            owner_id=str(avatar.id),
                            aspect="technique",
                            # By id, the same identity the save writes.
                            before=(
                                str(before_technique.id)
                                if before_technique is not None
                                else "none"
                            ),
                            after=str(reward_technique.id),
                        ).to_dict()
                    ]
                }
                reward_event.causal_links.append(
                    CausalLink(
                        event_id=reward_event.id,
                        cause_event_id=decision_event.id,
                        relation=CausalRelation.MOTIVATED_BY,
                    )
                )
                result.events.append(reward_event)

            if avatar_id not in support_ids:
                continue
            # Support spends the treasury, so it needs the same authority the
            # round was gated on, re-read at the mutation point. Expulsion and
            # a technique reward move no treasury and are left as they were.
            if not may_spend or not cls._may_dispose_treasury(sect, world):
                continue
            before_sect = int(getattr(sect, "magic_stone", 0))
            before_avatar = int(
                getattr(getattr(avatar, "magic_stone", None), "value", 0)
            )
            if not transfer_sect_member_support(sect, avatar, amount=support_amount):
                continue
            result.support_count += 1
            cls._record_institutional_step(decision, "support", avatar_id)
            support_event = Event(
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
                fact_kind=FactKind.STATE_TRANSITION,
                causal_origin=CausalOrigin.ACTOR_DECISION,
            )
            support_event.causal_payload = {
                "deltas": [
                    StateDelta(
                        event_id=support_event.id,
                        owner_kind="sect",
                        owner_id=str(sect.id),
                        aspect="magic_stone",
                        before=str(before_sect),
                        after=str(sect.magic_stone),
                        magnitude=-support_amount,
                    ).to_dict(),
                    StateDelta(
                        event_id=support_event.id,
                        owner_kind="avatar",
                        owner_id=str(avatar.id),
                        aspect="magic_stone",
                        before=str(before_avatar),
                        after=str(avatar.magic_stone.value),
                        magnitude=support_amount,
                    ).to_dict(),
                ]
            }
            support_event.causal_links.append(
                CausalLink(
                    event_id=support_event.id,
                    cause_event_id=decision_event.id,
                    relation=CausalRelation.MOTIVATED_BY,
                )
            )
            result.events.append(support_event)

    @classmethod
    def _pick_reward_technique(cls, sect: "Sect", avatar: "Avatar") -> Technique | None:
        candidates: list[Technique] = []
        for technique_name in getattr(sect, "technique_names", []) or []:
            technique = techniques_by_name.get(technique_name)
            if technique is None:
                continue
            if not technique.is_allowed_for(avatar):
                continue
            if (
                technique.attribute == TechniqueAttribute.EVIL
                and getattr(avatar, "alignment", None) != Alignment.EVIL
            ):
                continue
            if not is_attribute_compatible_with_root(technique.attribute, avatar.root):
                continue
            candidates.append(technique)

        # What the member already cultivates competes in the same ranking. Were
        # it excluded, two techniques of the same grade would keep replacing
        # each other year after year for no gain.
        current_technique = getattr(avatar, "technique", None)
        pool = list(candidates)
        if current_technique is not None:
            pool.append(current_technique)
        if not pool:
            return None
        best = max(pool, key=cls._technique_order)
        if current_technique is not None and cls._same_technique(
            best, current_technique
        ):
            return None
        return best

    @classmethod
    def _technique_order(cls, technique: Technique) -> tuple[int, int]:
        """Best first: higher grade, then the lower stable id.

        The id, never the name: names are localized, so ranking by them would
        make the engine's choice depend on the reader's language.
        """
        return (cls._grade_rank(technique), -int(getattr(technique, "id", 0)))

    @staticmethod
    def _same_technique(left: Technique | None, right: Technique | None) -> bool:
        if left is None or right is None:
            return left is right
        return int(getattr(left, "id", 0)) == int(getattr(right, "id", 0))

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
            parts.append(
                t("recruited {count} rogue cultivators", count=result.recruitment_count)
            )
        if result.expulsion_count:
            parts.append(t("expelled {count} members", count=result.expulsion_count))
        if result.technique_reward_count:
            parts.append(
                t(
                    "bestowed techniques {count} times",
                    count=result.technique_reward_count,
                )
            )
        if result.support_count:
            parts.append(
                t(
                    "granted spirit-stone support {count} times",
                    count=result.support_count,
                )
            )
        if not parts:
            return t(
                "{sect_name} focused this round of sect decisions on consolidation and observation, with no major adjustments made.",
                sect_name=sect.name,
            )
        return (
            t("{sect_name} this round of sect decisions:", sect_name=sect.name)
            + " "
            + "、".join(parts)
            + "。"
        )

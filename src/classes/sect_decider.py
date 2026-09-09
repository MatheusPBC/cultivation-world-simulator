from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from src.classes.agent_decision import AgentDecision
from src.classes.alignment import Alignment
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_affordance import (
    DomainAffordance,
    DomainDecisionKind,
)
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.sect_ranks import get_rank_from_realm
from src.classes.state_delta import StateDelta
from src.i18n import t
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
from src.systems.sect_member_support import (
    is_eligible_support_member,
    transfer_sect_member_support,
)
from src.utils.config import CONFIG
from src.systems.domain_affordance_registry import (
    AffordanceContext,
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
    stale_affordance_blocked_event,
    validate_actor_decision,
)
from src.systems.domain_decision_interpreter import interpret_domain_affordances

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
        *,
        llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
        injected_decision=None,
    ) -> SectDecisionResult:
        result = SectDecisionResult()
        trigger = Event(
            world.month_stamp,
            t("{sect_name} opened its annual administration round.", sect_name=sect.name),
            event_type="sect_annual_administration_opened",
            related_sects=[int(sect.id)],
            is_major=False,
            fact_kind=FactKind.OCCURRENCE,
            causal_origin=CausalOrigin.DETERMINISTIC,
            render_params={"sect_id": str(sect.id)},
        )
        context = AffordanceContext(
            world, "sect_annual", EntityRef("sect", str(sect.id)), trigger
        )
        options = DOMAIN_AFFORDANCES.compose(context)
        decision, decision_event = await interpret_domain_affordances(
            world,
            domain="sect_annual",
            actor_ref=context.actor_ref,
            actor_label=sect.name,
            trigger_event=trigger,
            affordances=options,
            task_name="sect_annual_interpreter",
            template_name="sect_annual_interpreter.txt",
            extra_context={"sect": sect.name, "context": cls._serialize_context(decision_context)},
            llm_call=llm_call,
            injected_decision=injected_decision,
        )
        result.events.extend((trigger, decision_event))
        result.decision_event = decision_event
        if decision.decision is DomainDecisionKind.ACT:
            try:
                option = next(
                    (
                        item for item in DOMAIN_AFFORDANCES.compose(context)
                        if item.id == decision.selected_affordance_id
                    ),
                    None,
                )
                if option is None:
                    raise StaleAffordanceError("annual sect affordance became stale")
                executed = await DOMAIN_AFFORDANCES.execute_async(
                    context, option.id, result=result, decision_event=decision_event
                )
                if executed not in result.events:
                    result.events.append(executed)
            except StaleAffordanceError:
                result.events.append(
                    stale_affordance_blocked_event(
                        context,
                        decision_event_id=decision_event.id,
                        selected_affordance_id=decision.selected_affordance_id or "",
                    )
                )
        result.summary_text = cls._build_summary(sect, result)
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
    async def _execute_option(
        cls, sect, context, world, option, result, decision_event
    ) -> None:
        """Execute one revalidated annual affordance.

        The registry owns composition/recomposition. Recruitment remains here
        because its canonical candidate response is asynchronous; its existing
        executor rechecks authority, membership, funds and race after await.
        """
        decision = AgentDecision.from_dict(decision_event.causal_payload["decision"])
        avatar_id = str(option.parameters["avatar_id"])
        action = option.action_kind
        if action == "sect_annual_recruit":
            await cls._process_recruitment(
                sect=sect, candidates=({"avatar_id": avatar_id, "alignment_recruitable": True, "race_recruitable": True},), world=world,
                recruit_cost=int(option.parameters["recruit_cost"]), result=result,
                selected_ids={avatar_id}, decision=decision, decision_event=decision_event,
                revalidate=lambda: DOMAIN_AFFORDANCES.revalidate(context, option.id),
            )
        elif action == "sect_annual_expel":
            cls._process_members(
                sect=sect, world=world, support_amount=0, result=result,
                expel_ids={avatar_id}, reward_ids=set(), support_ids=set(),
                decision=decision, decision_event=decision_event, may_spend=False,
                may_administer=True,
            )
        elif action == "sect_annual_reward":
            expected = int(option.parameters["technique_id"])
            current = getattr(
                next(
                    (item for item in sect.get_living_members_sorted_by_status() if str(item.id) == avatar_id),
                    None,
                ),
                "technique",
                None,
            )
            if str(option.parameters["before_technique_id"]) != str(
                getattr(current, "id", "none") if current is not None else "none"
            ):
                raise StaleAffordanceError("member technique changed after selection")
            avatar = next(
                (item for item in sect.get_living_members_sorted_by_status() if str(item.id) == avatar_id),
                None,
            )
            if avatar is None or getattr(cls._pick_reward_technique(sect, avatar), "id", None) != expected:
                raise StaleAffordanceError("selected technique is no longer canonical")
            cls._process_members(
                sect=sect, world=world, support_amount=0, result=result,
                expel_ids=set(), reward_ids={avatar_id}, support_ids=set(),
                decision=decision, decision_event=decision_event, may_spend=False,
                may_administer=True,
            )
        elif action == "sect_annual_support":
            cls._process_members(
                sect=sect, world=world, support_amount=int(option.parameters["support_amount"]), result=result,
                expel_ids=set(), reward_ids=set(), support_ids={avatar_id},
                decision=decision, decision_event=decision_event, may_spend=True,
                may_administer=False,
            )
        else:
            raise StaleAffordanceError("unknown annual sect affordance")
        decision_event.causal_payload["decision"] = decision.to_dict()

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
    async def _process_recruitment(
        cls,
        *,
        sect: "Sect",
        candidates: Any,
        world: "World",
        recruit_cost: int,
        result: SectDecisionResult,
        selected_ids: set[str],
        decision: AgentDecision,
        decision_event: Event,
        revalidate=None,
    ) -> None:
        avatars = getattr(getattr(world, "avatar_manager", None), "avatars", {}) or {}
        for candidate in candidates:
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
            if str(outcome.sect_id) != str(sect.id) or str(outcome.avatar_id) != str(avatar.id):
                raise StaleAffordanceError("recruitment outcome names another actor")
            choice = outcome.decision
            selected_key = str(choice.selected_key)
            accepted = selected_key == "ACCEPT" if selected_key in {"ACCEPT", "REJECT"} else False
            if bool(outcome.accepted) != accepted:
                raise StaleAffordanceError("recruitment outcome disagrees with its choice")
            response_event = Event(
                month_stamp=world.month_stamp,
                content=outcome.result_text,
                related_avatars=[avatar.id], related_sects=[int(sect.id)],
                fact_kind=FactKind.DECISION,
                causal_origin=CausalOrigin.ACTOR_DECISION,
                causal_payload={"deltas": [], "decision": AgentDecision(
                    month_stamp=int(world.month_stamp), subject_kind="avatar",
                    subject_id=str(avatar.id), source=str(getattr(choice.source, "value", choice.source)),
                    considered_count=2, chosen_chain=[{"selected_key": str(choice.selected_key)}],
                    thinking=str(choice.thinking),
                ).to_dict()},
            )
            response_event.causal_links.append(CausalLink(
                event_id=response_event.id, cause_event_id=decision_event.id,
                relation=CausalRelation.RESPONSE_TO,
            ))
            result.events.append(response_event)

            if not accepted:
                continue
            if revalidate is not None:
                revalidate()
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
            recruit_event.causal_links.append(
                CausalLink(
                    event_id=recruit_event.id,
                    cause_event_id=response_event.id,
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


def sect_annual_affordances(context: AffordanceContext):
    """Offer exactly the annual actions grounded in current sect state."""
    if context.actor_ref.kind != "sect":
        return ()
    sect = next(
        (item for item in getattr(context.world, "existed_sects", ()) if str(item.id) == context.actor_ref.id),
        None,
    )
    if sect is None or not getattr(sect, "is_active", False):
        return ()
    options: list[DomainAffordance] = []
    recruit_cost = int(getattr(CONFIG.sect, "recruit_cost", 500))
    support_amount = int(getattr(CONFIG.sect, "support_amount", 300))
    evidence = (context.trigger_event.id,)
    if SectDecider._may_dispose_treasury(sect, context.world):
        avatars = getattr(context.world.avatar_manager, "avatars", {})
        for avatar_id, avatar in sorted(avatars.items(), key=lambda item: str(item[0])):
            avatar_id = str(avatar_id)
            if (
                avatar is None or getattr(avatar, "is_dead", False)
                or getattr(avatar, "sect", None) is not None
                or not sect.is_alignment_recruitable(avatar.alignment)
                or not sect.accepts_avatar_race(avatar)
                or int(getattr(sect, "magic_stone", 0)) < recruit_cost
            ):
                continue
            options.append(DomainAffordance(
                context.domain, context.actor_ref, "sect_annual_recruit",
                (EntityRef("avatar", avatar_id),),
                    {"avatar_id": avatar_id, "recruit_cost": recruit_cost}, 0.4, evidence,
            ))
        for avatar in sect.get_living_members_sorted_by_status():
            avatar_id = str(avatar.id)
            if is_eligible_support_member(sect, avatar, amount=support_amount):
                options.append(DomainAffordance(
                    context.domain, context.actor_ref, "sect_annual_support",
                    (EntityRef("avatar", avatar_id),),
                    {"avatar_id": avatar_id, "support_amount": support_amount},
                    max(0.0, min(1.0, 1.0 - int(avatar.magic_stone.value) / support_amount)), evidence,
                ))
    if SectDecider._may_administer_sect(sect, context.world):
        for avatar in sect.get_living_members_sorted_by_status():
            avatar_id = str(avatar.id)
            if sect.is_member_rule_breaker(avatar):
                options.append(DomainAffordance(
                    context.domain, context.actor_ref, "sect_annual_expel",
                    (EntityRef("avatar", avatar_id),), {"avatar_id": avatar_id}, 0.65, evidence,
                ))
            elif (technique := SectDecider._pick_reward_technique(sect, avatar)) is not None:
                options.append(DomainAffordance(
                    context.domain, context.actor_ref, "sect_annual_reward",
                    (EntityRef("avatar", avatar_id),),
                    {"avatar_id": avatar_id, "technique_id": int(technique.id),
                     "before_technique_id": str(getattr(getattr(avatar, "technique", None), "id", "none"))},
                    0.55, evidence,
                ))
    return tuple(options)


async def execute_sect_annual_affordance(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event: Event | None = None,
    result: SectDecisionResult | None = None,
    **_: Any,
) -> Event:
    """Registered annual executor; all owner mutations remain below this gate."""
    validate_actor_decision(decision_event, context, option, label="annual sect")
    sect = next(
        (item for item in getattr(context.world, "existed_sects", ()) if str(item.id) == context.actor_ref.id),
        None,
    )
    if sect is None or result is None or decision_event is None:
        raise StaleAffordanceError("annual sect actor or decision disappeared")
    before = len(result.events)
    await SectDecider._execute_option(sect, context, context.world, option, result, decision_event)
    if len(result.events) <= before:
        event = Event(
            context.world.month_stamp,
            t("The selected annual sect action made no canonical change."),
            event_type="sect_annual_action_noop",
            fact_kind=FactKind.OCCURRENCE,
            causal_payload={"deltas": []},
        )
        event.causal_links.append(CausalLink(
            event_id=event.id,
            cause_event_id=decision_event.id,
            relation=CausalRelation.MOTIVATED_BY,
        ))
        return event
    return result.events[-1]


DOMAIN_AFFORDANCES.register_provider("sect_annual", sect_annual_affordances)
for _annual_action in (
    "sect_annual_recruit",
    "sect_annual_expel",
    "sect_annual_reward",
    "sect_annual_support",
):
    DOMAIN_AFFORDANCES.register_executor(_annual_action, execute_sect_annual_affordance)

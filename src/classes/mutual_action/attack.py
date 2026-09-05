from __future__ import annotations

from .mutual_action import PressureAction
from src.i18n import t
from src.classes.action.cooldown import cooldown_action
from src.classes.action_runtime import ActionResult, ActionStatus
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.relation.relation_delta_service import RelationDeltaService
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar
    from src.classes.core.world import World


@cooldown_action
class MutualAttack(PressureAction):
    """The one publicly offered way an Avatar opens hostilities.

    This action *is* the initiative.  It resolves no battle and inflicts no
    damage: it states that hostility began, snapshots who was involved and
    who saw it, and then lets the target answer.  The answer -- a flight, a
    successful escape, a counterattack -- is a separate fact that points back
    here, so one initiative yields exactly one aggression however it ends.

    The internal ``Attack`` is `register_action(actual=False)` and stays
    that way: it exists only as an engine-installed response and can never
    itself begin hostilities.
    """

    # 多语言 ID
    ACTION_NAME_ID = "mutual_attack_action_name"
    DESC_ID = "mutual_attack_description"
    REQUIREMENTS_ID = "mutual_attack_requirements"
    
    # 不需要翻译的常量
    EMOJI = "⚔️"
    PARAMS = {"target_avatar": "AvatarName"}
    RESPONSE_ACTIONS = ["Escape", "Attack"]
    # 攻击冷却：避免同月连刷攻击
    ACTION_CD_MONTHS: int = 3
    # 攻击是大事（长期记忆）
    IS_MAJOR: bool = True
    # 目标的应对是一条真实事实：它承载友好度的真实前后值，并回指发起事实。
    SHOW_RESPONSE_EVENT: bool = True

    def __init__(self, avatar: "Avatar", world: "World"):
        super().__init__(avatar, world)
        # 执行边界只重验一次：第一帧是敌意真正开始的时刻，之后的帧只是在
        # 等目标的回应，不该因为目标走开而把已经发生的敌意判为没发生。
        self._execution_validated = False
        self._hostility_attempted = False
        # 本次发起所产生的侵略事实 id（若有）。运行时证据，不进存档。
        self._aggression_event_id = ""
        # 本次发起的事实 id：有侵略事实时就是它，否则是 `start` 的发起事件。
        # 回应永远指向其中一条，因此既不会没有原因，也不会挂空链接。
        self._initiative_event_id = ""
        # `start` 产出的发起事件本体。执行边界要给它补上「哪一个决定选了
        # 这次发起」的链接，而它此刻还在本月尚未落库的事件列表里，所以补
        # 链接不会产生第二条持久化记录。
        self._initiative_event: Event | None = None
        # 发起时锁定的目标 id。基类每帧都会用名字重新解析目标，等待期间
        # 改名/顶替都可能解析到另一个人；结算只认这个 id。
        self._target_avatar_id = ""
        # 目标这次回应自己的决定事实 id（若记录了）。
        self._defence_decision_event_id = ""
        # 回应是否真的落地。目标在等待期间死亡或走远时不落地，也就没有
        # 回应事实可言——但已经发生的敌意不会因此被撤销。
        self._response_settled = False
        # `_settle_response` 读到的真实友好度变化，交给回应事件承载。
        self._relation_transitions: tuple[tuple[str, int, int], ...] = ()
        # 目标一侧自己的决定事实，由 `step` 内部产生后随结果一起返回。
        self._pending_response_events: list[Event] = []

    def _can_start(self, target: "Avatar") -> tuple[bool, str]:
        """攻击无额外检查条件"""
        from src.classes.observe import is_within_observation
        if not is_within_observation(self.avatar, target):
            return False, t("Target not within interaction range")
        return True, ""

    def start(self, target_avatar: "Avatar|str") -> Event:
        """The initiation fact, remembered as this action's own initiative.

        Every hostility has a factual initiative, whether or not it is also an
        inter-sect aggression.  Keeping this event's id is what lets a purely
        personal fight's response still name a cause.
        """

        event = super().start(target_avatar)
        event_id = str(getattr(event, "id", "") or "")
        if event_id and getattr(event, "content", ""):
            self._initiative_event_id = event_id
            self._initiative_event = event
        return event

    def step(self, target_avatar: "Avatar|str") -> ActionResult:
        """The real execution boundary, then the wait for an answer.

        Several phases sit between committing a plan and executing it, so the
        target may have died, moved out of perception or become unresolvable.
        The same predicate is reused rather than a second copy of the rules,
        and a failure here ends the action without any hostility having
        happened.  Note this cannot live in ``start``: ``commit_next_plan``
        assigns ``action_origin`` *after* calling ``start``, so ``start`` can
        only ever see the fail-closed default and would never prove an
        initiating choice.
        """

        extra_events: list[Event] = []
        if not self._execution_validated:
            # Keyword, not positional: `cooldown_action` wraps `can_start` as
            # `can_start(self, **params)`.
            can_start, reason = self.can_start(target_avatar=target_avatar)
            if not can_start:
                self.avatar._record_plan_rejection(
                    self.name, {"target_avatar": target_avatar}, reason
                )
                return ActionResult(status=ActionStatus.FAILED, events=[])
            self._execution_validated = True
            extra_events = self._record_hostility(target_avatar)
            self._attribute_initiative(target_avatar)

        result = super().step(target_avatar)
        pending, self._pending_response_events = self._pending_response_events, []
        if extra_events or pending:
            result.events = [*extra_events, *pending, *result.events]
        return result

    def _record_hostility(self, target_avatar: "Avatar|str") -> list[Event]:
        """The single aggression fact for this initiative, if it is one.

        Most attacks are not inter-sect aggression, and returning nothing is
        the normal outcome: the fight still happens, the personal action and
        its response are still recorded, and no institution gains a cause.
        The snapshot is taken here, before any response or outcome, so
        memberships and witnesses describe the world as it was when hostility
        began.
        """

        from src.systems.avatar_aggression import (
            TARGET_SELECTOR_PARAM,
            capture_aggression_snapshot,
            record_deliberate_attack,
        )

        if self._hostility_attempted:
            return []
        self._hostility_attempted = True
        target = self._get_target_avatar(target_avatar)
        # The selector has to be the exact one the decision recorded.  A
        # programmatically installed Avatar object is not a selector, so it
        # proves no choice and fails closed.
        if target is None:
            return []
        # Pinned once, here: from now on this initiative concerns this exact
        # Avatar, whatever the selector resolves to later.
        self._target_avatar_id = str(target.id)
        if not isinstance(target_avatar, str) or not target_avatar.strip():
            return []
        snapshot = capture_aggression_snapshot(
            self.world,
            self.avatar,
            target,
            params={TARGET_SELECTOR_PARAM: target_avatar},
            action_origin=self.action_origin,
        )
        if snapshot is None:
            return []
        event = record_deliberate_attack(
            self.world, snapshot, initiator=self.avatar, target=target
        )
        if event is None:
            return []
        self._aggression_event_id = event.id
        # The canonical hostility fact is the better initiative to cite when
        # there is one; the plain initiation event remains the fallback.
        self._initiative_event_id = event.id
        return [event]

    def _attribute_initiative(self, target_avatar: "Avatar|str") -> None:
        """Name the decision that chose this initiative, on the initiation fact.

        Every hostility has an author, not only the inter-sect ones.  The
        initiation event is still in this month's uncommitted event list, so
        adding the citation here records no second fact.  Without a validated
        decision -- a reactive install, a restored save, a chain that chose
        something else -- nothing is attached rather than a guess.
        """

        from src.systems.avatar_aggression import TARGET_SELECTOR_PARAM
        from src.systems.avatar_decision import committed_decision_event_id

        event = self._initiative_event
        if event is None or not isinstance(target_avatar, str) or not target_avatar.strip():
            return
        decision_event_id = committed_decision_event_id(
            self.avatar,
            action_name=type(self).__name__,
            params={TARGET_SELECTOR_PARAM: target_avatar},
            action_origin=self.action_origin,
        )
        if decision_event_id is None:
            return
        event.causal_origin = CausalOrigin.ACTOR_DECISION
        if not any(
            link.cause_event_id == decision_event_id
            and link.relation is CausalRelation.MOTIVATED_BY
            for link in event.causal_links
        ):
            event.causal_links.append(
                CausalLink(
                    event_id=event.id,
                    cause_event_id=decision_event_id,
                    relation=CausalRelation.MOTIVATED_BY,
                )
            )

    def _settle_response(self, target_avatar: "Avatar", response_name: str) -> None:
        # 回应可能在等待若干帧之后才落地。已经发生的敌意是既成事实，但
        # 迟到的回应不得对一个已经死亡或走远的目标产生物质后果，所以这里
        # 只重验目标本身，不再牵扯发起者当下的冒险意愿。
        # 也不得换人：名字可能已经指向另一个角色，只有当初锁定的那一位才
        # 承担这次回应。
        if self._target_avatar_id and str(getattr(target_avatar, "id", "")) != self._target_avatar_id:
            return
        if self._is_dead_avatar(target_avatar):
            return
        target_ok, _reason = self._can_start(target_avatar)
        if not target_ok:
            return
        fb = str(response_name).strip()
        # 数值政策不变：仍是配置里的固定增量。变的只是它现在留下证据——
        # 前后值从关系状态本身读取，因为夹取与身份下限都可能吸收一部分。
        before_a_to_b = self.avatar.get_friendliness(target_avatar)
        before_b_to_a = target_avatar.get_friendliness(self.avatar)
        a_to_b, b_to_a = RelationDeltaService.get_fixed_delta("attack", "started")
        RelationDeltaService.apply_bidirectional_delta(self.avatar, target_avatar, a_to_b, b_to_a)
        self._relation_transitions = (
            (
                f"{self.avatar.id}->{target_avatar.id}",
                before_a_to_b,
                self.avatar.get_friendliness(target_avatar),
            ),
            (
                f"{target_avatar.id}->{self.avatar.id}",
                before_b_to_a,
                target_avatar.get_friendliness(self.avatar),
            ),
        )

        if fb not in {"Escape", "Attack"}:
            self._response_settled = True
            return
        # Internal response execution resolves through the canonical query
        # layer, which accepts Avatar ids.  A name may be changed or reused
        # between this choice and the later Escape/Attack execution; the id is
        # the same initiator this response actually observed.
        params = {"avatar_name": str(self.avatar.id)}
        installed = self._set_target_immediate_action(
            target_avatar, fb, params, push_start_event=False
        )
        self._response_settled = True
        if not installed:
            # 目标本来就在做同名同参的动作。那个动作有它自己的来历，本次
            # 回应不得把出处记到它头上，也不得把发起事实挂到它的结果上。
            return
        self._carry_initiative_to_response(target_avatar)
        self._pending_response_events.extend(
            self._record_defence_decision(target_avatar, fb, params)
        )

    def _handle_response_result(self, target_avatar: "Avatar", result: dict) -> ActionResult:
        """Reject a stale reply before the base class mutates the target.

        ``MutualAction._handle_response_result`` writes ``target.thinking``
        before delegating to ``_settle_response``.  That is normally harmless,
        but a queued reply is no longer about a target that died, moved out of
        range, or was replaced under the same name.  Validate the pinned
        identity first so none of a stale response -- thinking, relations,
        plans, decision fact, or response event -- reaches canonical state.
        The initiative remains a historical fact either way.
        """

        if (
            not self._target_avatar_id
            or str(getattr(target_avatar, "id", "")) != self._target_avatar_id
            or self._is_dead_avatar(target_avatar)
        ):
            return ActionResult(status=ActionStatus.COMPLETED, events=[])
        target_ok, _reason = self._can_start(target_avatar)
        if not target_ok:
            return ActionResult(status=ActionStatus.COMPLETED, events=[])
        return super()._handle_response_result(target_avatar, result)

    def _carry_initiative_to_response(self, target_avatar: "Avatar") -> None:
        """Let the installed response know which initiative it answers."""

        from src.systems.avatar_aggression import carry_initiating_aggression

        if not self._initiative_event_id:
            return
        current = getattr(target_avatar, "current_action", None)
        action = getattr(current, "action", None)
        carry_initiating_aggression(action, self._initiative_event_id)

    def _record_defence_decision(
        self, target_avatar: "Avatar", response_name: str, params: dict
    ) -> list[Event]:
        """The defender's own audited decision to answer this way.

        Who chose it is a real fact -- the player, the model, or the
        configured fallback -- and it is recorded as that actual source.  It
        is an audit record only: the installed response keeps
        ``REACTIVE_RESPONSE`` provenance, so a defence can never ground a new
        aggression, and this decision carries no ``StateDelta``.  Without a
        known source (a restored save, a resolver that reported none) nothing
        is recorded rather than a guess.
        """

        from src.systems.avatar_decision import (
            adopt_avatar_decision,
            build_avatar_decision_event,
        )

        source = _DEFENCE_DECISION_SOURCES.get(str(self._response_source or ""))
        if source is None:
            return []
        event = build_avatar_decision_event(
            self.world,
            target_avatar,
            [(response_name, params)],
            str(getattr(target_avatar, "thinking", "") or ""),
            "",
            source=source,
            # What was actually on the defender's menu is this action's own
            # response set, not the public action catalogue: the internal
            # ``Attack`` is not a publicly offered action at all.
            offered={name: self.get_response_label(name) for name in self.RESPONSE_ACTIONS},
        )
        adopt_avatar_decision(target_avatar, event)
        self._defence_decision_event_id = event.id
        return [event]

    def _build_response_event(self, target_avatar: "Avatar", response_name: str) -> Event | None:
        """The target's answer, carrying the friendliness it actually moved.

        Stamped with the current month rather than the month the initiative
        started: the answer can arrive later, and a state transition has to be
        dated when it happened.  Two distinct citations: ``RESPONSE_TO`` the
        initiative it answers, and ``MOTIVATED_BY`` the defender's own decision
        when one was recorded -- being provoked and choosing how to react are
        not the same cause.  Each is added only if it exists, so nothing
        dangles.  If the response never landed there is no answer to describe.
        """

        from src.classes.relation.relation_delta_service import RelationDeltaService as _Relations
        from src.systems.avatar_aggression import link_response_to_initiative

        if not self._response_settled:
            return None
        content = self._build_response_event_content(target_avatar, response_name)
        deltas: list[dict] = []
        event = Event(
            self.world.month_stamp,
            content,
            related_avatars=[self.avatar.id, target_avatar.id],
            fact_kind=FactKind.OCCURRENCE,
            causal_payload={"deltas": deltas},
        )
        deltas = _Relations.build_friendliness_deltas(event.id, self._relation_transitions)
        event.causal_payload["deltas"] = deltas
        if deltas:
            event.fact_kind = FactKind.STATE_TRANSITION
        link_response_to_initiative(event, self._initiative_event_id)
        if self._defence_decision_event_id:
            event.causal_links.append(
                CausalLink(
                    event_id=event.id,
                    cause_event_id=self._defence_decision_event_id,
                    relation=CausalRelation.MOTIVATED_BY,
                )
            )
        self._last_response_event_content = content
        return event


# `ChoiceSource` -> the audited `AgentDecision.source` it actually is.
_DEFENCE_DECISION_SOURCES = {
    "llm": "llm",
    "player_roleplay": "player",
    "fallback": "rule",
}

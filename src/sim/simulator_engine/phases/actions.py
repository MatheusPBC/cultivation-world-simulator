from __future__ import annotations

from src.classes.agent_decision import AgentDecision
from src.classes.actions import get_action_infos
from src.classes.ai import llm_ai
from src.classes.core.avatar import Avatar
from src.classes.event import Event, FactKind, is_null_event
from src.config.providers import StaticConfigProvider
from src.i18n import t
from src.run.log import get_logger
from src.sim.runtime_capabilities import get_decision_boundary_gateway


class RequiredDecisionFailed(Exception):
    """Raised when a required `action_decision` LLM call could not produce a
    result after the LLM client's own retries (provider/transport failure, or
    a parse failure that survived `CONFIG.ai.max_parse_retries`).

    Deliberately NOT a subclass of `SimulationStepAborted`:
    `SimulationPhaseRunner.run` only catches `SimulationStepAborted` (which
    means "a lifecycle command superseded this step", a normal outcome), so
    this exception propagates untouched through the phase runner,
    `Simulator.step()`, and `GameSessionRuntime.run_mutation` into
    `GameLoopRunner.run_once`, which pauses the runtime instead of silently
    retrying forever. See docs/specs/causal-world-kernel.md §6.2-6.3.
    """

    def __init__(self, avatar_ids: list[str], message: str = ""):
        self.avatar_ids = list(avatar_ids)
        super().__init__(
            message or f"required decision failed while deciding for avatars: {', '.join(self.avatar_ids)}"
        )


def _record_agent_decision(
    world,
    avatar: Avatar,
    action_name_params_pairs,
    avatar_thinking: str,
    short_term_objective: str,
) -> Event:
    """
    在决策边界把一次 LLM 决策记录为审计用的 fact_kind=DECISION 事件。

    这是一条审计记录，不是并行的规划器：模拟器内没有任何地方会读取它来
    做决策，`chosen_chain` 只是复制 `load_decide_result_chain` 已经入队
    的计划。事件本身默认被 EventQuery.include_decisions 过滤，不出现在
    时间线/记忆/世界志中，见 docs/specs/causal-world-kernel.md 5.4。
    """
    decision = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="avatar",
        subject_id=str(avatar.id),
        source="llm",
        considered_count=len(get_action_infos(avatar)),
        chosen_chain=[
            {"action_name": name, "params": params}
            for name, params in action_name_params_pairs
        ],
        thinking=avatar_thinking,
        short_term_objective=short_term_objective,
    )
    causal_payload = {"deltas": [], "decision": decision.to_dict()}
    event = Event(
        world.month_stamp,
        t("{avatar} committed to an action chain", avatar=avatar.name),
        related_avatars=[avatar.id],
        is_major=False,
        is_story=False,
        fact_kind=FactKind.DECISION,
        causal_payload=causal_payload,
    )
    # 运行时身份：一次决策可能跨月消费多个计划（见 commit_next_plan），
    # 这两个字段不随存档保存，读档/重置后随 Avatar 重建自然清空。
    avatar.current_decision_event_id = event.id
    avatar._current_decision_payload = causal_payload
    return event


async def phase_decide_actions(world, living_avatars: list[Avatar]) -> list[Event]:
    gateway = get_decision_boundary_gateway(world)
    if gateway is not None:
        gateway.before_ai_decision(world)
    controlled_avatar_id = gateway.get_controlled_avatar_id() if gateway is not None else ""

    # 只给“既没在执行动作，也没有待执行计划”的角色补决策，
    # 避免 LLM 覆盖已经排好的行动链。
    avatars_to_decide = [
        avatar
        for avatar in living_avatars
        if avatar.current_action is None and not avatar.has_plans()
        and str(getattr(avatar, "id", "")) != controlled_avatar_id
    ]
    if not avatars_to_decide:
        return []

    try:
        decide_results = await llm_ai.decide(world, avatars_to_decide)
    except Exception as exc:
        # `llm_ai.decide` / `LLMAI._decide` only reach here via an exception
        # for a real provider/parse failure (see src/classes/ai.py): a
        # response that parses but is empty, and rule-based test mode, both
        # return normally with an empty result instead of raising. So any
        # exception escaping this call is, by construction, a required
        # failure — never an indistinguishable "valid empty decision".
        raise RequiredDecisionFailed(
            [str(avatar.id) for avatar in avatars_to_decide], str(exc)
        ) from exc

    decision_events: list[Event] = []
    for avatar, result in decide_results.items():
        action_name_params_pairs, avatar_thinking, short_term_objective, _event = result
        avatar.load_decide_result_chain(
            action_name_params_pairs,
            avatar_thinking,
            short_term_objective,
        )
        decision_events.append(
            _record_agent_decision(
                world, avatar, action_name_params_pairs, avatar_thinking, short_term_objective
            )
        )
    return decision_events


def phase_commit_next_plans(living_avatars: list[Avatar]) -> list[Event]:
    events: list[Event] = []
    for avatar in living_avatars:
        if avatar.current_action is None:
            # 这里仅负责把已存在的计划推进到 current_action，
            # 不参与“该计划从哪来”的决策逻辑。
            start_event = avatar.commit_next_plan()
            if start_event is not None and not is_null_event(start_event):
                events.append(start_event)
    return events


async def _tick_action_round(avatars: list[Avatar], log_label: str) -> tuple[list[Event], set[Avatar]]:
    # 单轮动作执行。返回本轮事件，以及需要在同月继续补跑的角色。
    # 之所以要单独拆出来，是为了把“首轮执行”和“后续重试轮”复用同一套异常处理。
    events: list[Event] = []
    avatars_needing_retry: set[Avatar] = set()

    for avatar in avatars:
        try:
            new_events = await avatar.tick_action()
            if new_events:
                events.extend(new_events)

            if getattr(avatar, "_new_action_set_this_step", False):
                avatars_needing_retry.add(avatar)
        except Exception as exc:
            get_logger().logger.error(
                "Avatar %s(%s) %s failed: %s",
                avatar.name,
                avatar.id,
                log_label,
                exc,
                exc_info=True,
            )
            if hasattr(avatar, "_new_action_set_this_step"):
                avatar._new_action_set_this_step = False

    return events, avatars_needing_retry


async def phase_execute_actions(living_avatars: list[Avatar]) -> list[Event]:
    events: list[Event] = []
    max_local_rounds = StaticConfigProvider.current().max_action_rounds_per_turn()

    # 第一轮先让所有在执行动作的角色各跑一次。
    round_events, avatars_needing_retry = await _tick_action_round(
        living_avatars,
        "tick_action",
    )
    events.extend(round_events)

    round_count = 1
    # 某些动作会在 tick 内无缝接上新的 current_action。
    # 这类角色会在同一个月内继续补跑，但要受全局上限保护，避免死循环。
    while avatars_needing_retry and round_count < max_local_rounds:
        current_avatars = list(avatars_needing_retry)
        round_events, avatars_needing_retry = await _tick_action_round(
            current_avatars,
            "retry tick_action",
        )
        events.extend(round_events)
        round_count += 1

    return events

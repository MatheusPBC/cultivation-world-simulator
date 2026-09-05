from __future__ import annotations

from src.i18n import t
from src.classes.action import InstantAction
from src.classes.action.action import can_take_risk
from src.classes.action.param_options import ParamOptionSource
from src.classes.action.targeting_mixin import TargetingMixin
from src.classes.action_runtime import ActionResult, ActionStatus
from src.classes.event import Event
from src.classes.observe import is_within_observation
from src.systems.battle import decide_battle, get_effective_strength_pair
from src.systems.avatar_aggression import (
    initiating_aggression_event_id,
    link_response_to_initiative,
)
from src.utils.resolution import resolve_query

class Attack(InstantAction, TargetingMixin):
    """The internal, engine-installed fight.

    Registered `actual=False` on purpose: no decision chain may name it, so
    it is only ever installed as a response -- a counterattack to a
    ``MutualAttack``, or the consequence of a failed ``Escape``.  It therefore
    never begins hostilities and never authors an aggression fact.  What it
    does do is point its material result back at the initiative it is
    answering, when it was told which one that is.
    """

    # 多语言 ID
    ACTION_NAME_ID = "attack_action_name"
    DESC_ID = "attack_description"
    REQUIREMENTS_ID = "attack_requirements"
    STORY_PROMPT_ID = "attack_story_prompt"
    
    # 不需要翻译的常量
    EMOJI = "⚔️"
    PARAMS = {"avatar_name": "AvatarName"}
    PARAM_OPTION_SOURCES = {"avatar_name": ParamOptionSource.OBSERVABLE_AVATAR_NAME}
    
    # 战斗是大事（长期记忆）
    IS_MAJOR: bool = True
    
    @classmethod
    def get_story_prompt(cls) -> str:
        """获取故事提示词的翻译"""
        return t(cls.STORY_PROMPT_ID)

    def _execute(self, avatar_name: str) -> None:
        from src.classes.core.avatar import Avatar
        target = resolve_query(avatar_name, self.world, expected_types=[Avatar]).obj
        if target is None:
            return
        winner, loser, loser_damage, winner_damage = decide_battle(self.avatar, target)
        # 应用双方伤害
        loser.hp.reduce(loser_damage)
        winner.hp.reduce(winner_damage)
        
        # 增加双方兵器熟练度（战斗经验）
        import random
        proficiency_gain = random.uniform(1.0, 3.0)
        self.avatar.increase_weapon_proficiency(proficiency_gain)
        if target is not None:
            target.increase_weapon_proficiency(proficiency_gain)
        
        self._last_result = (winner, loser, loser_damage, winner_damage)

    def can_start(self, avatar_name: str) -> tuple[bool, str]:
        ok, reason = can_take_risk(self.avatar)
        if not ok:
            return ok, reason
        if not avatar_name:
            return False, t("Missing target parameter")
            
        from src.classes.core.avatar import Avatar
        target = resolve_query(avatar_name, self.world, expected_types=[Avatar]).obj
        if target is None:
            return False, t("Target does not exist")
        if target.is_dead:
            return False, t("Target is already dead")
        if target is self.avatar or str(getattr(target, "id", "")) == str(self.avatar.id):
            return False, t("Cannot initiate interaction with self")
        if not is_within_observation(self.avatar, target):
            return False, t("Target not within interaction range")

        return True, ""

    def step(self, avatar_name: str = "", **_params) -> ActionResult:
        # 提交阶段（`commit_next_plan`）与执行阶段之间隔着若干相位，目标可能
        # 已经死亡、离开感知范围或不再可解析。生命周期本身不会在 step 前重跑
        # can_start，所以这里复用同一个谓词而不是另写一套校验；不通过时以
        # FAILED 结束，避免把一次没有发生的战斗记成 COMPLETED（那会让
        # tick_action 去找不存在的 source event 并触发背景板回声）。
        can_start, reason = self.can_start(avatar_name)
        if not can_start:
            self.avatar._record_plan_rejection(
                self.name, {"avatar_name": avatar_name}, reason
            )
            return ActionResult(status=ActionStatus.FAILED, events=[])
        return super().step(avatar_name=avatar_name)

    def start(self, avatar_name: str) -> Event:
        from src.classes.core.avatar import Avatar
        target = resolve_query(avatar_name, self.world, expected_types=[Avatar]).obj
        target_name = target.name if target is not None else avatar_name
        # 展示双方折算战斗力（基于对手、含克制）
        s_att, s_def = get_effective_strength_pair(self.avatar, target)
        rel_ids = [self.avatar.id]
        if target is not None:
            try:
                rel_ids.append(target.id)
            except Exception:
                pass
        content = t("{attacker} initiates battle against {target} (Power: {attacker} {att_power} vs {target} {def_power})",
                   attacker=self.avatar.name, target=target_name, 
                   att_power=int(s_att), def_power=int(s_def))
        event = Event(self.world.month_stamp, content, related_avatars=rel_ids, is_major=False)
        # 记录开始事件内容，供故事生成使用
        self._start_event_content = event.content
        return event

    async def finish(self, avatar_name: str) -> list[Event]:
        res = self._last_result
        if not (isinstance(res, tuple) and len(res) == 4):
            return []
        
        from src.classes.core.avatar import Avatar
        target = resolve_query(avatar_name, self.world, expected_types=[Avatar]).obj
        start_text = getattr(self, '_start_event_content', "")
        
        from src.systems.battle import handle_battle_finish
        battle_events = await handle_battle_finish(
            self.world,
            self.avatar,
            target,
            res,
            start_text,
            self.get_story_prompt(),
            check_loot=True
        )
        # 这场战斗是对某次发起的回答，不是新的发起：真实的战斗结果事件回指
        # 那条侵略事实，因果链里因此只有一个物质原因。没有被告知发起来源
        # （读档重建、独立安装）时不挂任何链接。
        aggression_event_id = initiating_aggression_event_id(self)
        if aggression_event_id:
            for event in battle_events:
                if event.event_type in {"battle_result", "battle_kill"}:
                    link_response_to_initiative(event, aggression_event_id)
        return battle_events

import random
from copy import copy

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.classes.action.attack import Attack
from src.classes.action_runtime import ActionStatus
from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.hp import HP
from src.classes.individual_consequence import IndividualConsequenceState
from src.systems.cultivation import Realm
from src.classes.core.avatar import Avatar

# 定义一个简单的 Result Mock
class MockResolutionResult:
    def __init__(self, obj):
        self.obj = obj


def _observable_target(name: str = "TargetAvatar", *, pos=(1, 1), avatar_id: str = "target-id"):
    """A target mock that can actually be measured against观察半径。"""
    target = MagicMock(spec=Avatar)
    target.name = name
    target.id = avatar_id
    target.is_dead = False
    target.pos_x, target.pos_y = pos
    return target


def test_attack_can_start_success(dummy_avatar):
    """测试攻击条件检查通过"""
    target = _observable_target()
    
    with patch("src.classes.action.attack.resolve_query") as mock_resolve:
        mock_resolve.return_value = MockResolutionResult(target)
        
        action = Attack(dummy_avatar, dummy_avatar.world)
        can_start, reason = action.can_start("TargetAvatar")
        
        assert can_start is True
        assert reason == ""

def test_attack_can_start_rejects_self(dummy_avatar):
    """不能攻击自己：目标解析回自身时必须被拒绝。"""
    with patch("src.classes.action.attack.resolve_query") as mock_resolve:
        mock_resolve.return_value = MockResolutionResult(dummy_avatar)

        action = Attack(dummy_avatar, dummy_avatar.world)
        can_start, reason = action.can_start(dummy_avatar.name)

        assert can_start is False
        assert "自己" in reason


def test_attack_can_start_rejects_target_outside_observation(dummy_avatar):
    """观察范围之外的目标不可攻击（练气感知半径 3，此处距离 20）。"""
    target = _observable_target("FarAway", pos=(20, 0))

    with patch("src.classes.action.attack.resolve_query") as mock_resolve:
        mock_resolve.return_value = MockResolutionResult(target)

        action = Attack(dummy_avatar, dummy_avatar.world)
        can_start, reason = action.can_start("FarAway")

        assert can_start is False
        assert "范围" in reason


def test_attack_can_start_fail_no_target(dummy_avatar):
    """测试目标不存在"""
    with patch("src.classes.action.attack.resolve_query") as mock_resolve:
        mock_resolve.return_value = MockResolutionResult(None)
        
        action = Attack(dummy_avatar, dummy_avatar.world)
        can_start, reason = action.can_start("Ghost")
        
        assert can_start is False
        assert "目标不存在" in reason

def test_attack_can_start_fail_dead_target(dummy_avatar):
    """测试目标已死亡"""
    target = MagicMock(spec=Avatar)
    target.is_dead = True
    
    with patch("src.classes.action.attack.resolve_query") as mock_resolve:
        mock_resolve.return_value = MockResolutionResult(target)
        
        action = Attack(dummy_avatar, dummy_avatar.world)
        can_start, reason = action.can_start("Zombie")
        
        assert can_start is False
        assert "目标已死亡" in reason

def test_attack_start_event(dummy_avatar):
    """测试开始攻击生成的事件"""
    target = MagicMock(spec=Avatar)
    target.name = "Enemy"
    target.id = "enemy-id"
    
    # Mock combat strength calculation
    with patch("src.classes.action.attack.resolve_query") as mock_resolve, \
         patch("src.classes.action.attack.get_effective_strength_pair") as mock_strength:
        
        mock_resolve.return_value = MockResolutionResult(target)
        mock_strength.return_value = (100, 80)
        
        action = Attack(dummy_avatar, dummy_avatar.world)
        event = action.start("Enemy")
        
        assert isinstance(event, Event)
        assert "TestDummy" in event.content
        assert "Enemy" in event.content
        assert "100" in event.content # 战斗力显示
        assert event.is_major is False

def test_attack_execute_logic(dummy_avatar):
    """测试执行战斗逻辑"""
    target = MagicMock(spec=Avatar)
    target.name = "Enemy"
    
    # Setup HP mocks
    dummy_avatar.hp = MagicMock()
    target.hp = MagicMock()
    
    # Setup proficiency mocks (methods on MagicMock)
    dummy_avatar.increase_weapon_proficiency = MagicMock()
    target.increase_weapon_proficiency = MagicMock()

    with patch("src.classes.action.attack.resolve_query") as mock_resolve, \
         patch("src.classes.action.attack.decide_battle") as mock_decide:
        
        mock_resolve.return_value = MockResolutionResult(target)
        
        # winner, loser, loser_damage, winner_damage
        # 假设 dummy_avatar 赢了
        mock_decide.return_value = (dummy_avatar, target, 50, 10)
        
        action = Attack(dummy_avatar, dummy_avatar.world)
        action._execute("Enemy")
        
        # 验证伤害应用
        # loser (target) takes 50 dmg
        target.hp.reduce.assert_called_with(50)
        # winner (dummy) takes 10 dmg
        dummy_avatar.hp.reduce.assert_called_with(10)
        
        # 验证熟练度增加
        assert dummy_avatar.increase_weapon_proficiency.called
        assert target.increase_weapon_proficiency.called
        
        # 验证结果保存
        assert action._last_result == (dummy_avatar, target, 50, 10)


def test_attack_rejects_counterattack_against_an_unobservable_initiator(dummy_avatar):
    """观察是有方向的：更强的发起者能看见的距离，弱者未必看得见。

    MutualAttack 允许强者在自己的半径内发起攻击，目标逃跑失败后会把
    `Attack` 排回自己的计划。此时目标仍然只有自己的感知半径，所以这条
    反击会被拒绝，而不是靠“对方能看见我”反向绕过范围检查。
    """
    from src.classes.observe import is_within_observation

    escapee = dummy_avatar  # 练气，半径 3，位于 (0, 0)
    initiator = _observable_target("Initiator", pos=(5, 0), avatar_id="initiator-id")
    initiator.cultivation_progress = MagicMock()
    initiator.cultivation_progress.realm = Realm.Foundation_Establishment
    initiator.effects = {}

    assert is_within_observation(initiator, escapee)
    assert not is_within_observation(escapee, initiator)

    with patch("src.classes.action.attack.resolve_query") as mock_resolve:
        mock_resolve.return_value = MockResolutionResult(initiator)

        action = Attack(escapee, escapee.world)
        can_start, reason = action.can_start("Initiator")

    assert can_start is False
    assert "范围" in reason


@pytest.mark.asyncio
async def test_attack_step_fails_when_target_left_observation_after_commit(dummy_avatar):
    """执行边界必须重新校验：提交后目标走远，本月不得产生任何战斗后果。"""
    attacker = dummy_avatar
    attacker.hp = HP(100, 100)
    target = copy(attacker)
    target.id = "runaway-target"
    target.name = "Runaway"
    target.hp = HP(100, 100)
    target.pos_x, target.pos_y = 1, 1
    target.individual_consequences = IndividualConsequenceState()

    world = attacker.world
    world.avatar_manager.avatars = {attacker.id: attacker, target.id: target}
    attacker.load_decide_result_chain([("Attack", {"avatar_name": "Runaway"})], "", "")

    start_event = attacker.commit_next_plan()
    assert start_event is not None  # 提交时目标还在范围内

    # 提交与执行之间目标离开了感知范围（同月内的正常位移）。
    target.pos_x, target.pos_y = 30, 30

    action = attacker.current_action.action
    rng_state_before = random.getstate()
    result = action.step(avatar_name="Runaway")

    assert result.status is ActionStatus.FAILED
    assert result.events == []
    assert getattr(action, "_last_result", None) is None
    assert attacker.hp.cur == 100 and target.hp.cur == 100
    assert random.getstate() == rng_state_before


@pytest.mark.asyncio
async def test_attack_step_fails_on_self_target_without_touching_hp_or_rng(dummy_avatar):
    """自我攻击在执行边界同样失败，不消耗随机数也不改血量。"""
    attacker = dummy_avatar
    attacker.hp = HP(100, 100)
    attacker.world.avatar_manager.avatars = {attacker.id: attacker}

    action = Attack(attacker, attacker.world)
    rng_state_before = random.getstate()
    result = action.step(avatar_name=attacker.name)

    assert result.status is ActionStatus.FAILED
    assert attacker.hp.cur == 100
    assert random.getstate() == rng_state_before


@pytest.mark.asyncio
async def test_chosen_attack_produces_decision_linked_battle_fact(dummy_avatar):
    """正常选择的 Attack 仍然产出挂到本次决策上的战斗事实与 HP delta。"""
    attacker = dummy_avatar
    attacker.hp = HP(100, 100)
    target = copy(attacker)
    target.id = "battle-target"
    target.name = "Enemy"
    target.hp = HP(100, 100)
    target.pos_x, target.pos_y = 1, 1
    target.individual_consequences = IndividualConsequenceState()

    world = attacker.world
    world.avatar_manager.avatars = {attacker.id: attacker, target.id: target}

    decision = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_id=str(attacker.id),
        source="test",
        considered_count=1,
        chosen_chain=[{"action_name": "Attack", "params": {"avatar_name": "Enemy"}}],
    )
    payload = {"deltas": [], "decision": decision.to_dict()}
    decision_event = Event(
        world.month_stamp,
        "Attacker chose battle",
        fact_kind=FactKind.DECISION,
        causal_payload=payload,
    )
    attacker.current_decision_event_id = decision_event.id
    attacker._current_decision_payload = payload

    attacker.load_decide_result_chain([("Attack", {"avatar_name": "Enemy"})], "", "")

    with patch(
        "src.classes.action.attack.decide_battle",
        return_value=(attacker, target, 30, 20),
    ), patch(
        "src.classes.story_event_service.StoryEventService.maybe_create_story",
        new_callable=AsyncMock,
        return_value=None,
    ):
        assert attacker.commit_next_plan() is not None
        events = await attacker.tick_action()

    result = next(event for event in events if event.event_type == "battle_result")
    assert result.fact_kind is FactKind.STATE_TRANSITION
    assert result.causal_origin is CausalOrigin.ACTOR_DECISION
    assert any(
        link.cause_event_id == decision_event.id
        and link.relation is CausalRelation.MOTIVATED_BY
        for link in result.causal_links
    )
    deltas = result.causal_payload["deltas"]
    assert sum(
        delta["owner_id"] == target.id and delta["aspect"] == "hp" for delta in deltas
    ) == 1
    assert sum(
        delta["owner_id"] == attacker.id and delta["aspect"] == "hp" for delta in deltas
    ) == 1
    assert target.hp.cur == 70 and attacker.hp.cur == 80

import pytest
from copy import copy
from unittest.mock import MagicMock, AsyncMock, patch
from src.systems.battle import (
    get_base_strength, 
    _combat_strength_vs, 
    _strength_diff, 
    calc_win_rate,
    handle_battle_finish,
    _SUPPRESSION_POINTS
)
from src.systems.cultivation import Realm, Stage
from src.classes.technique import TechniqueAttribute
from src.classes.death_reason import DeathType
from src.classes.hp import HP
from src.classes.individual_consequence import IndividualConsequenceState
from src.classes.causal_origin import CausalOrigin
from src.classes.causal_link import CausalRelation
from src.classes.agent_decision import AgentDecision
from src.classes.event import Event, FactKind
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.finalizer import validate_causal_integrity

# Helper to create a mock avatar
def create_mock_avatar(level, realm=None, stage=None, effects=None, technique_attr=None):
    avatar = MagicMock()
    
    # Setup cultivation progress
    cp = MagicMock()
    cp.level = level
    
    # Setup Realm Enum Mock or Real Enum
    if realm:
        cp.realm = realm
    else:
        # Fallback to Qi Refinement if not specified
        cp.realm = Realm.Qi_Refinement
        
    if stage:
        cp.stage = stage
    else:
        # Fallback to Early Stage
        cp.stage = Stage.Early_Stage
        
    avatar.cultivation_progress = cp
    
    # Setup effects
    avatar.effects = effects or {}
    
    # Setup technique
    if technique_attr:
        tech = MagicMock()
        tech.attribute = technique_attr
        avatar.technique = tech
    else:
        avatar.technique = None
        
    return avatar

class TestBattleStrength:
    def test_base_strength_qi_early_min(self):
        # 练气前期 1级
        # Base: 10, Stage: 0
        avatar = create_mock_avatar(1, Realm.Qi_Refinement, Stage.Early_Stage)
        strength = get_base_strength(avatar)
        expected = 10.0 + 0.0
        assert strength == expected

    def test_base_strength_qi_late_max(self):
        # 练气后期 30级
        # Base: 10, Stage: 5
        avatar = create_mock_avatar(30, Realm.Qi_Refinement, Stage.Late_Stage)
        strength = get_base_strength(avatar)
        expected = 10.0 + 5.0
        assert strength == pytest.approx(expected)

    def test_base_strength_foundation_early_min(self):
        # 筑基前期 31级
        # Base: 20, Stage: 0
        avatar = create_mock_avatar(31, Realm.Foundation_Establishment, Stage.Early_Stage)
        strength = get_base_strength(avatar)
        expected = 20.0 + 0.0
        assert strength == expected

    def test_base_strength_nascent_middle(self):
        # 元婴中期 105级
        # Base: 40, Stage: 2.5
        avatar = create_mock_avatar(105, Realm.Nascent_Soul, Stage.Middle_Stage)
        strength = get_base_strength(avatar)
        expected = 40.0 + 2.5
        assert strength == pytest.approx(expected)

    def test_extra_effects(self):
        # Test extra strength points from effects
        avatar = create_mock_avatar(1, Realm.Qi_Refinement, Stage.Early_Stage, effects={"extra_battle_strength_points": 5.0})
        strength = get_base_strength(avatar)
        strength = get_base_strength(avatar)
        assert strength == 15.0

class TestCombatMechanics:
    def test_realm_gap_win_rate(self):
        # 筑基前期 vs 练气巅峰
        # 筑基前期: 20.0
        # 练气巅峰: 15.0 (10 + 5)
        # Diff: 5.0
        p1 = create_mock_avatar(31, Realm.Foundation_Establishment, Stage.Early_Stage)
        p2 = create_mock_avatar(30, Realm.Qi_Refinement, Stage.Late_Stage)
        
        # Win rate check
        # p = 1 / (1 + exp(-0.15 * 5.0)) = 1 / (1 + exp(-0.75)) = 1 / (1 + 0.472) = 1 / 1.472 = 0.679
        rate = calc_win_rate(p1, p2)
        assert rate > 0.67
        assert rate < 0.69

    def test_massive_gap_win_rate(self):
        # 元婴 vs 练气
        # 元婴: 40+
        # 练气: 10+
        # Diff > 20 -> should be close to max win rate
        p1 = create_mock_avatar(91, Realm.Nascent_Soul, Stage.Early_Stage)
        p2 = create_mock_avatar(1, Realm.Qi_Refinement, Stage.Early_Stage)
        
        rate = calc_win_rate(p1, p2)
        # With cap at 0.99, but actually calculation might be slightly below 0.99 if diff isn't huge enough
        # Diff = 30, p = 1/(1+exp(-4.5)) = 0.989
        assert rate > 0.98

    def test_technique_suppression(self):
        # Test attribute suppression bonus (Metal > Wood)
        # GOLD suppresses WOOD
        p1 = create_mock_avatar(10, Realm.Qi_Refinement, Stage.Early_Stage, technique_attr=TechniqueAttribute.GOLD)
        p2 = create_mock_avatar(10, Realm.Qi_Refinement, Stage.Early_Stage, technique_attr=TechniqueAttribute.WOOD)
        
        # Base strengths are equal (same level/realm/stage)
        # P1 attacks P2: Gold vs Wood -> Bonus
        s1 = _combat_strength_vs(p2, p1) 
        
        # P2 attacks P1: Wood vs Gold -> No Bonus
        s2 = _combat_strength_vs(p1, p2)
        
        base = get_base_strength(p1)
        
        assert s1 == base + _SUPPRESSION_POINTS
        assert s2 == base
        
        diff = s1 - s2
        assert diff == _SUPPRESSION_POINTS

    def test_intra_stage_diff(self):
        # Test same stage same strength
        # Level 1 vs Level 10 (Early Stage)
        # Diff = 0
        p1 = create_mock_avatar(10, Realm.Qi_Refinement, Stage.Early_Stage)
        p2 = create_mock_avatar(1, Realm.Qi_Refinement, Stage.Early_Stage)
        
        diff = _strength_diff(p1, p2)
        expected_diff = 0.0
        assert diff == pytest.approx(expected_diff)

class TestBattleResolution:
    @pytest.mark.asyncio
    async def test_material_battle_result_uses_real_actor_decision_and_owns_deltas(
        self, dummy_avatar
    ):
        attacker = dummy_avatar
        attacker.id = "attacker"
        attacker.name = "Attacker"
        attacker.hp = HP(100, 50)
        decision = AgentDecision(
            month_stamp=int(attacker.world.month_stamp),
            subject_id=attacker.id,
            source="test",
            considered_count=1,
            chosen_chain=[{"action_name": "Attack", "params": {}}],
        )
        decision_event = Event(
            attacker.world.month_stamp,
            "Attacker chose battle",
            fact_kind=FactKind.DECISION,
            causal_payload={"deltas": [], "decision": decision.to_dict()},
        )
        attacker.current_decision_event_id = decision_event.id

        target = copy(attacker)
        target.id = "target"
        target.name = "Target"
        target.hp = HP(100, 40)
        target.individual_consequences = IndividualConsequenceState()

        async def outcome_text(*_args):
            return "A nonfatal battle"

        with patch(
            "src.classes.story_event_service.StoryEventService.maybe_create_story",
            new_callable=AsyncMock,
            return_value=None,
        ):
            events = await handle_battle_finish(
                attacker.world,
                attacker,
                target,
                (attacker, target, 30, 20),
                "Battle start",
                "Story prompt",
                outcome_text_func=outcome_text,
            )

        result = events[0]
        assert result.fact_kind is FactKind.STATE_TRANSITION
        assert result.causal_origin is CausalOrigin.ACTOR_DECISION
        assert any(
            link.cause_event_id == decision_event.id
            and link.relation is CausalRelation.MOTIVATED_BY
            for link in result.causal_links
        )
        assert all(
            delta["event_id"] == result.id
            for delta in result.causal_payload["deltas"]
        )
        validate_causal_integrity(
            SimulationStepContext.create(attacker.world), [decision_event, result]
        )

    @pytest.mark.asyncio
    async def test_nonfatal_battle_attaches_one_hp_and_injury_delta_per_avatar(
        self, dummy_avatar
    ):
        attacker = dummy_avatar
        attacker.id = "attacker"
        attacker.name = "Attacker"
        attacker.hp = HP(100, 50)

        target = copy(attacker)
        target.id = "target"
        target.name = "Target"
        target.hp = HP(100, 40)
        target.individual_consequences = IndividualConsequenceState()

        async def outcome_text(*_args):
            return "A nonfatal battle"

        with patch(
            "src.classes.story_event_service.StoryEventService.maybe_create_story",
            new_callable=AsyncMock,
            return_value=None,
        ):
            events = await handle_battle_finish(
                attacker.world,
                attacker,
                target,
                (attacker, target, 30, 20),
                "Battle start",
                "Story prompt",
                outcome_text_func=outcome_text,
            )

        assert len(events) == 1
        deltas = events[0].causal_payload["deltas"]
        assert sum(delta["owner_id"] == target.id and delta["aspect"] == "hp" for delta in deltas) == 1
        assert sum(delta["owner_id"] == attacker.id and delta["aspect"] == "hp" for delta in deltas) == 1
        assert target.individual_consequences.active_injury is not None
        assert attacker.individual_consequences.active_injury is None

    @pytest.mark.asyncio
    async def test_attacker_dies_killer_is_winner(self):
        # Setup mocks
        world = MagicMock()
        world.month_stamp = 100

        attacker = MagicMock()
        attacker.id = "attacker"
        attacker.name = "Attacker"
        attacker.hp = -10 # Dead

        defender = MagicMock()
        defender.id = "defender"
        defender.name = "Defender"
        defender.hp = 50 # Alive

        # res: (winner, loser, loser_damage, winner_damage)
        # Defender wins, Attacker loses
        res = (defender, attacker, 110, 10)

        start_content = "Battle start"
        story_prompt = "Story prompt"

        # Patch StoryTeller and handle_death
        with patch("src.classes.story_teller.StoryTeller.tell_story", new_callable=AsyncMock) as mock_tell_story, \
             patch("src.classes.death.handle_death") as mock_handle_death:
            
            mock_tell_story.return_value = "Story content"

            await handle_battle_finish(
                world,
                attacker,
                defender,
                res,
                start_content,
                story_prompt
            )

            # Assert handle_death called
            assert mock_handle_death.called

            # Get the DeathReason object passed to handle_death
            # handle_death(world, loser, death_reason)
            call_args = mock_handle_death.call_args
            death_reason = call_args[0][2]

            assert death_reason.death_type == DeathType.BATTLE
            # This verifies the fix: it should be winner.name (Defender)
            assert death_reason.killer_name == defender.name

"""Capacity is a read model over persisted StrategyState, never a planner."""

import json

from src.classes.mechanical_language import EntityRef
from src.classes.governance.models import StrategicPlan
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn
from src.sim.medieval.persistence import load_world, save_world
from src.sim.medieval.procurement import review_supply
from tests.test_medieval_strategy_response import OWNER, occupied_response_world


def test_capacity_is_multidimensional_and_only_refers_to_existing_strategy_records():
    world = create_medieval_world(73)
    polity = EntityRef("polity", "auren")
    before = world.strategy.capacity_for(polity).to_dict()

    assert before["food_reserves"]["status"] == "unreviewed"
    assert before["productive_inputs"]["status"] == "unavailable"
    assert before["territorial_defense"]["status"] == "unavailable"
    assert set(before["food_reserves"]["objective_ids"]) == {
        objective.id for objective in world.strategy.objectives.values() if objective.actor_ref == polity
        and objective.kind == "maintain_food_reserve"
    }
    assert before["food_reserves"]["plan_ids"] == ()

    refresh_reports(world)
    review_supply(world)
    after = world.strategy.capacity_for(polity).to_dict()

    assert after["food_reserves"]["status"] in {"committed", "ready", "blocked"}
    assert set(after["food_reserves"]["plan_ids"]) == {
        plan.id for plan in world.strategy.plans.values()
        if plan.objective_id in after["food_reserves"]["objective_ids"]
    }
    assert world.strategy.to_dict()["objectives"]
    assert world.strategy.to_dict()["plans"]


def test_capacity_statuses_are_rebuilt_from_plan_stages_without_new_state():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    objective = next(objective for objective in world.strategy.objectives.values()
                     if objective.actor_ref == actor and objective.kind == "maintain_food_reserve")
    world.strategy.objectives = {objective.id: objective}

    def set_stage(stage):
        world.strategy.plans = {f"plan:{objective.id}": StrategicPlan(
            id=f"plan:{objective.id}", objective_id=objective.id, stage=stage,
            last_review_day=world.clock.absolute_day, last_event_id="event:derived-only")}
        return world.strategy.capacity_for(actor).food_reserves.status

    assert set_stage("satisfied") == "ready"
    assert set_stage("acquire") == "committed"
    assert set_stage("blocked") == "blocked"


def test_persisted_objectives_and_plans_rebuild_the_same_capacity_after_load(tmp_path):
    world = create_medieval_world(73)
    refresh_reports(world)
    review_supply(world)
    actor = EntityRef("organization", "oficios-da-serra")
    expected_state = world.strategy.to_dict()
    expected_capacity = world.strategy.capacity_for(actor).to_dict()

    path = tmp_path / "strategy-capacity.mws"
    save_world(world, path)
    restored = load_world(path)

    assert restored.strategy.to_dict() == expected_state
    assert restored.strategy.capacity_for(actor).to_dict() == expected_capacity


def test_world_derived_capacity_names_only_owned_persistent_records():
    world, _, _ = occupied_response_world()
    actor = OWNER
    capacity = world.strategy.capacity_for(actor, world).to_dict()

    assert set(capacity) >= {
        "administrative_bandwidth", "diplomatic_bandwidth", "military_command",
        "project_capacity", "logistics_capacity",
    }
    military_sources = capacity["military_command"]["source_ids"]
    assert all(source in world.society.detachments or source in world.society.force_standoffs
               or source in world.society.siege_campaigns or source in world.society.garrisons
               for source in military_sources)


async def test_strategy_fragment_joins_the_existing_single_monthly_consultation(monkeypatch):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})
    seen = []

    async def call_llm_json(prompt, *args, **kwargs):
        seen.append(json.loads(prompt[prompt.index("{"):]))
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)

    _, covered = await review_institutional_decision_turn(world, OWNER, monthly_adapters())

    assert covered is True and len(seen) == 1
    capacity = seen[0]["situation"]["strategy"]["strategic_capacity"]
    assert set(capacity) == {
        "food_reserves", "productive_inputs", "territorial_defense",
        "administrative_bandwidth", "diplomatic_bandwidth", "military_command",
        "project_capacity", "logistics_capacity",
    }
    assert capacity["territorial_defense"]["status"] == "unavailable"

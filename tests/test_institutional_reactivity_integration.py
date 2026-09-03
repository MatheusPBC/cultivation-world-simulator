from pathlib import Path
from dataclasses import replace

import pytest

from src.classes.alignment import Alignment
from src.classes.core.dynasty import Dynasty
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.mechanical_language import ConditionInstance, MechanicalLanguageState
from src.classes.sect_ranks import get_rank_from_realm
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidationLayer,
    DomainInvalidationQueue,
)
from src.systems.city_reactivity import enqueue_city_transitions
from src.systems.government_reactivity import (
    enqueue_government_transitions,
    process_government_reactivity,
)
from src.systems.organization_reactivity import (
    enqueue_organization_transitions,
    process_organization_reactivity,
)
from src.systems.causal_observatory import CausalObservatory
from src.sim.simulator import Simulator
from src.run.load_map import load_cultivation_world_map
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.systems.time import MonthStamp
from src.utils.llm.runtime_mode import llm_test_mode_scope
from tests.test_government_interpreter import _setup as setup_government_condition
from tests.test_sect_decider import _create_avatar
from tests.test_causal_world_multimonth import _seed_grounded_urban_risk


def _attach_eligible_sect_member(base_world, city):
    sect = Sect(
        id=9,
        name="River Sect",
        desc="",
        member_act_style="",
        alignment=Alignment.RIGHTEOUS,
        headquarter=SectHeadQuarter("HQ", "", Path("")),
        technique_names=[],
        magic_stone=1000,
    )
    member = _create_avatar(
        base_world,
        avatar_id="river-member",
        name="River Member",
        alignment=Alignment.RIGHTEOUS,
    )
    member.pos_x, member.pos_y = city.cors[0]
    member.tile = base_world.map.get_tile(member.pos_x, member.pos_y)
    if getattr(getattr(member.tile, "region", None), "id", None) != city.id:
        member.tile.region = city
    member.magic_stone.value = 0
    member.join_sect(sect, get_rank_from_realm(member.cultivation_progress.realm))
    base_world.avatar_manager.avatars[member.id] = member
    base_world.existed_sects = [sect]
    base_world.sect_context.from_existed_sects(base_world.existed_sects)
    return sect, member


@pytest.mark.asyncio
async def test_one_regional_condition_can_drive_distinct_government_and_sect_actions(
    base_world,
):
    city, trigger, _ = setup_government_condition(base_world)
    sect, member = _attach_eligible_sect_member(base_world, city)
    emperor = _create_avatar(
        base_world,
        avatar_id="emperor-1",
        name="Test Emperor",
        alignment=Alignment.RIGHTEOUS,
    )
    emperor.pos_x, emperor.pos_y = city.cors[0]
    emperor.tile = base_world.map.get_tile(emperor.pos_x, emperor.pos_y)
    if getattr(getattr(emperor.tile, "region", None), "id", None) != city.id:
        emperor.tile.region = city
    base_world.avatar_manager.avatars[emperor.id] = emperor
    base_world.run_config_snapshot = {"test_mode": True}

    queue = DomainInvalidationQueue()
    enqueue_government_transitions(base_world, [trigger], queue)
    enqueue_organization_transitions(base_world, [trigger], queue)
    enqueue_city_transitions(base_world, [trigger], queue)

    government_events = await process_government_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )
    organization_events = await process_organization_reactivity(
        base_world,
        current_events=[trigger, *government_events],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )

    assert [event.event_type for event in government_events] == [
        "government_interpretation_decision",
        "city_maintenance_completed",
    ]
    assert [event.event_type for event in organization_events] == [
        "organization_interpretation_decision",
        "sect_member_support_completed",
    ]
    assert city.city_state.assets[0].integrity > 0.5
    assert sect.magic_stone == 700
    assert member.magic_stone.value == 300
    assert (
        queue.drain(
            layer=DomainInvalidationLayer.SEMANTIC,
            domain="city",
        )
        == []
    )
    assert (
        len(
            queue.drain(
                layer=DomainInvalidationLayer.MECHANICAL,
                domain="city",
            )
        )
        == 1
    )

    receipts = base_world.mechanical_language.reaction_receipts.values()
    assert {receipt.domain for receipt in receipts} == {
        "government:1",
        "organization:9",
    }
    assert all(receipt.completed for receipt in receipts)
    assert {
        link.cause_event_id
        for event in [government_events[-1], organization_events[-1]]
        for link in event.causal_links
    } >= {trigger.id, government_events[0].id, organization_events[0].id}

    restored_semantics = MechanicalLanguageState.from_dict(
        base_world.mechanical_language.to_dict()
    )
    assert {
        receipt.domain for receipt in restored_semantics.reaction_receipts.values()
    } == {"government:1", "organization:9"}

    for event in [trigger, *government_events, *organization_events]:
        assert base_world.event_manager.add_event(event)
    observation = CausalObservatory().observe(
        base_world,
        start_month=int(base_world.month_stamp),
        end_month=int(base_world.month_stamp),
    )
    assert observation.material_events["institutional_support"] == 1


@pytest.mark.asyncio
async def test_simulator_step_runs_government_and_organization_once_without_real_llm(
    base_world,
):
    base_world.month_stamp = MonthStamp(13)
    city, trigger, _ = setup_government_condition(base_world)
    sect, member = _attach_eligible_sect_member(base_world, city)
    emperor = _create_avatar(
        base_world,
        avatar_id="emperor-1",
        name="Test Emperor",
        alignment=Alignment.RIGHTEOUS,
    )
    emperor.pos_x, emperor.pos_y = city.cors[0]
    emperor.tile = base_world.map.get_tile(emperor.pos_x, emperor.pos_y)
    if getattr(getattr(emperor.tile, "region", None), "id", None) != city.id:
        emperor.tile.region = city
    base_world.avatar_manager.avatars[emperor.id] = emperor
    base_world.run_config_snapshot = {
        "test_mode": True,
        "npc_awakening_rate_per_month": 0.0,
        "semantic_discovery_budget_per_month": 0,
    }
    assert base_world.event_manager.add_event(trigger)

    with llm_test_mode_scope(True):
        events = await Simulator(base_world).step()

    event_types = [event.event_type for event in events]
    assert event_types.count("government_interpretation_decision") == 1
    assert event_types.count("city_maintenance_completed") == 1
    assert event_types.count("organization_interpretation_decision") == 1
    assert event_types.count("sect_member_support_completed") == 1
    assert city.city_state.assets[0].integrity > 0.5
    assert sect.magic_stone == 700
    assert member.magic_stone.value == 300
    assert {
        receipt.domain
        for receipt in base_world.mechanical_language.reaction_receipts.values()
    } == {"government:1", "organization:9"}


@pytest.mark.asyncio
async def test_institutional_receipts_and_mutations_survive_full_save_load(
    base_world,
    tmp_path,
):
    base_world.month_stamp = MonthStamp(13)
    base_world.map = load_cultivation_world_map("classic")
    city = base_world.map.regions[302]
    assert isinstance(city, CityRegion)
    base_world.dynasty = Dynasty(
        id=1,
        name="Test Dynasty",
        desc="",
        royal_surname="Test",
        current_emperor_id="emperor-1",
    )
    city.city_state.governance = replace(
        city.city_state.governance,
        controller_kind="dynasty",
        controller_id="1",
    )
    capability_id, definition_id = _seed_grounded_urban_risk(base_world, city)
    trigger = Event(
        base_world.month_stamp,
        "Grounded urban risk became active.",
        event_type="semantic_condition_activated",
        fact_kind=FactKind.DERIVED_CONDITION,
        render_params={
            "region_id": str(city.id),
            "condition_definition_id": definition_id,
        },
        id="institutional-save-trigger",
    )
    base_world.mechanical_language.add_condition_instance(
        ConditionInstance(
            id="institutional-save-condition",
            definition_id=definition_id,
            target_kind="region",
            target_id=str(city.id),
            label="urban maintenance need",
            intensity=0.9,
            started_month=int(base_world.month_stamp),
            cause_event_id=trigger.id,
        )
    )
    sect, member = _attach_eligible_sect_member(base_world, city)
    emperor = _create_avatar(
        base_world,
        avatar_id="emperor-1",
        name="Test Emperor",
        alignment=Alignment.RIGHTEOUS,
    )
    emperor.pos_x, emperor.pos_y = city.cors[0]
    emperor.tile = base_world.map.get_tile(emperor.pos_x, emperor.pos_y)
    base_world.avatar_manager.avatars[emperor.id] = emperor
    base_world.run_config_snapshot = {
        "content_locale": "zh-CN",
        "map_id": "classic",
        "test_mode": True,
        "npc_awakening_rate_per_month": 0.0,
        "semantic_discovery_budget_per_month": 0,
    }
    assert base_world.event_manager.add_event(trigger)
    simulator = Simulator(base_world)

    with llm_test_mode_scope(True):
        first_events = await simulator.step()

    assert "sect_member_support_completed" in {
        event.event_type for event in first_events
    }
    maintained_integrity = next(
        asset.integrity
        for asset in city.city_state.assets
        if capability_id in asset.capability_ids
    )
    save_path = tmp_path / "institutional-reactivity.json"
    success, message = save_game(
        base_world,
        simulator,
        base_world.existed_sects,
        save_path=save_path,
    )
    assert success, message

    loaded_world, loaded_simulator, loaded_sects = load_game(save_path)
    with llm_test_mode_scope(True):
        second_events = await loaded_simulator.step()

    assert not {
        "government_interpretation_decision",
        "organization_interpretation_decision",
        "sect_member_support_completed",
    }.intersection(event.event_type for event in second_events)
    assert {
        receipt.domain
        for receipt in loaded_world.mechanical_language.reaction_receipts.values()
    } == {"government:1", "organization:9"}
    loaded_city = loaded_world.map.regions[city.id]
    assert (
        next(
            asset.integrity
            for asset in loaded_city.city_state.assets
            if capability_id in asset.capability_ids
        )
        == maintained_integrity
    )
    loaded_sect = next(item for item in loaded_sects if item.id == sect.id)
    loaded_member = loaded_world.avatar_manager.avatars[member.id]
    assert loaded_sect.magic_stone == 700
    assert loaded_member.magic_stone.value == 300

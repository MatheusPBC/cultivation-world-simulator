"""Real-owner integration coverage for institutional relationship impacts."""

from __future__ import annotations

import pytest

from src.classes.core.dynasty import Dynasty
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.environment.city_state import CityGovernance
from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.event import Event
from src.classes.mechanical_language import EntityRef
from src.classes.regional_economy import RegionalEconomyState
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.sim.simulator_engine.finalizer import EventPersistenceError, finalize_step
from src.sim.simulator_engine.phase_registry import SimulationPhase
from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner
from src.systems.domain_affordance_registry import DOMAIN_AFFORDANCES
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institutional_aid import process_institutional_aid_shortage
from src.systems.institutional_memory import decision_context
from src.systems.institutional_relationship_impact import (
    RELATIONSHIP_IMPACT_DOMAIN,
    RelationshipAffordanceContext,
    process_institutional_relationship_impacts,
)


async def _accept_first_affordance(_task, _template, context, **_kwargs):
    return {
        "decision": "act",
        "reason": "The grounded institutional option is acceptable.",
        "selected_affordance_id": context["affordances"][0]["id"],
    }


def _setup_serializable_aid_world(world, emperor):
    """Build the aid vertical with a real Avatar, so save/load is meaningful."""
    emperor.weapon = None  # conftest's convenience MagicMock is not save data.
    world.avatar_manager.avatars[emperor.id] = emperor
    world.dynasty = Dynasty(1, "Test Dynasty", "", current_emperor_id=emperor.id)

    def city(region_id: int, stock: float, demand: float) -> CityRegion:
        region = CityRegion(
            id=region_id,
            name=f"City {region_id}",
            desc="",
            cors=[(2, 3) if region_id == 302 else (5, 3)],
            economy=RegionalEconomyState(
                stocks={"grain": stock},
                capacities={"grain": 20},
                demand_rates={"grain": demand},
                access={"grain": 1.0},
            ),
        )
        region.city_state.governance = CityGovernance("dynasty", "1", 1.0)
        world.map.regions[region_id] = region
        world.map.region_cors[region_id] = list(region.cors)
        for coordinate in region.cors:
            world.map.tiles[coordinate].region = region
        return region

    source, destination = city(302, 12, 0), city(305, 0, 2)
    world.map.set_routes((Route("aid-road", (302, 305), "road", 2, 1.0, True),))
    bootstrap_institutional_authority(world)
    shortage = Event(
        world.month_stamp,
        "The destination could not satisfy grain demand.",
        event_type="regional_resource_shortage",
        render_params={"region_id": "305", "resource_id": "grain"},
        id="shortage:relationship-runtime",
    )
    return source, destination, shortage


async def _accepted_aid(world, shortage):
    events = await process_institutional_aid_shortage(
        world,
        shortage,
        llm_call=_accept_first_affordance,
    )
    return events, next(event for event in events if event.event_type == "institutional_aid_accepted")


def _opposed_contributions(world):
    seen: list[str] = []

    def choose(institution_id: str, source: Event) -> DomainDecision:
        seen.append(institution_id)
        institution = world.institutional_authority.get_institution(institution_id)
        context = RelationshipAffordanceContext(
            world,
            RELATIONSHIP_IMPACT_DOMAIN,
            institution.owner_ref,
            source,
            event_overlays={source.id: source},
        )
        wanted_delta = 6 if institution_id == "inst:city:302" else -2
        option = next(
            option
            for option in DOMAIN_AFFORDANCES.compose(context)
            if option.parameters["delta"] == wanted_delta
        )
        return DomainDecision(DomainDecisionKind.ACT, "The known fact warrants this bounded response.", option.id)

    return seen, choose


@pytest.mark.asyncio
async def test_accepted_aid_allows_each_party_to_contribute_to_shared_relationship_prompt(
    base_world, dummy_avatar
):
    _source, _destination, shortage = _setup_serializable_aid_world(base_world, dummy_avatar)
    aid_events, accepted = await _accepted_aid(base_world, shortage)
    assert not base_world.mechanical_language.reaction_receipts

    seen, choose = _opposed_contributions(base_world)
    impact_events = await process_institutional_relationship_impacts(
        base_world,
        current_events=[accepted],
        injected_decisions=choose,
    )

    relation = base_world.institutional_relations.get_relation("inst:city:302", "inst:city:305")
    relationship_changes = [
        event
        for event in impact_events
        if event.event_type == "institutional_relationship_changed"
    ]
    assert seen == ["inst:city:302", "inst:city:305"]
    assert relation.friendliness == 4
    assert len([event for event in impact_events if event.fact_kind.value == "decision"]) == 2
    assert len(relationship_changes) == 2
    assert all(
        base_world.institutional_knowledge.contains(institution_id, event.id)
        for institution_id in ("inst:city:302", "inst:city:305")
        for event in relationship_changes
    )
    context = decision_context(base_world, "inst:city:302", event_overlays=(accepted, *impact_events))
    assert context["known_facts"][0]["event_id"] == accepted.id
    assert context["current_relations"] == [{
        "relation_id": relation.id,
        "counterpart_institution_id": "inst:city:305",
        "counterpart_name": "City 305",
        "kind": "neutral",
        "friendliness": 4,
        "evidence_event_ids": list(relation.evidence_event_ids),
    }]
    assert aid_events


@pytest.mark.asyncio
async def test_relationship_receipts_and_climate_round_trip_then_prevent_replay(
    base_world, dummy_avatar, tmp_path
):
    _source, _destination, shortage = _setup_serializable_aid_world(base_world, dummy_avatar)
    aid_events, accepted = await _accepted_aid(base_world, shortage)
    _seen, choose = _opposed_contributions(base_world)
    impact_events = await process_institutional_relationship_impacts(
        base_world, current_events=[accepted], injected_decisions=choose
    )
    assert base_world.event_manager.commit_step([shortage, *aid_events, *impact_events])
    relations_before = base_world.institutional_relations.to_dict()
    receipts_before = base_world.mechanical_language.to_dict()

    save_path = tmp_path / "relationship-runtime.json"
    success, message = save_game(base_world, Simulator(base_world), [], save_path)
    assert success, message
    loaded_world, _simulator, _sects = load_game(save_path)
    stored_accepted = loaded_world.event_manager.get_event_by_id(accepted.id)
    replayed = await process_institutional_relationship_impacts(
        loaded_world,
        current_events=[stored_accepted],
        injected_decisions=lambda *_args: pytest.fail("replayed fact must not be reconsidered"),
    )

    assert loaded_world.institutional_relations.to_dict() == relations_before
    assert loaded_world.mechanical_language.to_dict() == receipts_before
    assert replayed == []


@pytest.mark.asyncio
async def test_failed_commit_restores_relationships_receipts_calendar_and_events(
    base_world, dummy_avatar, monkeypatch
):
    _source, _destination, shortage = _setup_serializable_aid_world(base_world, dummy_avatar)
    before_month = base_world.month_stamp
    before_events = base_world.event_manager.count()
    before_relations = base_world.institutional_relations.to_dict()
    before_receipts = base_world.mechanical_language.to_dict()

    async def mutate(simulator, ctx):
        aid_events, accepted = await _accepted_aid(simulator.world, shortage)
        _seen, choose = _opposed_contributions(simulator.world)
        impact_events = await process_institutional_relationship_impacts(
            simulator.world, current_events=[accepted], injected_decisions=choose
        )
        ctx.add_events([shortage, *aid_events, *impact_events])

    phases = (
        SimulationPhase("relationship_mutate", 1, "relationship_mutate", mutate),
        SimulationPhase("finalize_step", 2, "finalize_step", lambda _simulator, ctx: finalize_step(ctx), reset_check_after=False),
    )
    monkeypatch.setattr(base_world.event_manager, "commit_step", lambda _events, _chapter: False)

    with pytest.raises(EventPersistenceError):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert base_world.institutional_relations.to_dict() == before_relations
    assert base_world.mechanical_language.to_dict() == before_receipts
    assert base_world.month_stamp == before_month
    assert base_world.event_manager.count() == before_events

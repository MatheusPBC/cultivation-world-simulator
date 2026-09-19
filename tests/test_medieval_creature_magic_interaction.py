"""One bounded material interaction between a completed ward and the drake."""

import pytest

from src.classes.event import FactKind
from src.classes.environment.creature import CREATURE_SPECIES, creature_species_definition
from src.classes.mechanical_language import EntityRef
from src.classes.research.models import Ward
from src.classes.state_delta import StateDelta
from src.sim.medieval.creatures import (apply_monthly_creature_ecology, creature_options,
                                        execute_creature_option)
from src.run.medieval_world import create_medieval_world
from src.systems.material_hazard_impacts import (
    DRAKE_POPULATION_DAMAGE_INTERACTION,
    DRAKE_SITE_DAMAGE_INTERACTION,
    HAZARD_INTERACTIONS,
    SERPENT_SITE_DAMAGE_INTERACTION,
    creature_site_damage_magnitude,
    drake_population_damage_magnitude,
    drake_site_damage_magnitude,
)
from src.sim.medieval.rites import (
    record_rite_offer,
    rite_offer_options,
    rite_sponsor_options,
    sponsor_rite,
    ward_active,
)
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.events import record_event
from src.run.medieval_creatures import DRAKE_ID, ROUTE_ID
from tests.test_medieval_creatures import buy_across_the_river, crossed_world
from src.sim.medieval.engine import MedievalSimulator
from tests.test_medieval_rites import tick_to


WARD_SPONSOR = EntityRef("organization", "liga-das-barcas")
WARD_SITE = "docas-de-portovelho"


def test_drake_damage_uses_the_engine_definition_without_a_ward():
    world = create_medieval_world(73)
    assert HAZARD_INTERACTIONS[("river_drake", "infrastructure_site")] is DRAKE_SITE_DAMAGE_INTERACTION
    assert drake_site_damage_magnitude(world, WARD_SITE) == pytest.approx(0.10)


def test_engine_uses_a_distinct_countermeasure_profile_for_hazard_resistance():
    world = create_medieval_world(73)
    site = world.map.infrastructure_sites[WARD_SITE]
    settlement = next(item for item in world.society.settlements.values()
                      if item.region_id in site.region_ids)
    world.research.wards["ward:rite:test-countermeasure"] = Ward(
        id="ward:rite:test-countermeasure", settlement_id=settlement.id,
        sponsor_ref=EntityRef("polity", "auren"), rite_id="rite:test-countermeasure",
        started_day=0, until_day=30, resistance_capability_id="river_countermeasure",
        last_event_id="event:1")
    assert drake_site_damage_magnitude(world, WARD_SITE) == pytest.approx(0.072)


def test_second_authored_species_uses_its_own_registered_hazard_law():
    world = create_medieval_world(73)
    serpent = world.creatures.creatures["creature:drake-do-lume-echo"]
    assert serpent.species == "river_serpent"
    assert HAZARD_INTERACTIONS[(serpent.species, "infrastructure_site")] is SERPENT_SITE_DAMAGE_INTERACTION
    assert creature_site_damage_magnitude(world, serpent.species, WARD_SITE) < drake_site_damage_magnitude(world, WARD_SITE)


def test_ecology_parameters_are_engine_owned_species_definitions():
    assert set(CREATURE_SPECIES) == {"river_drake", "river_serpent"}
    assert creature_species_definition("river_drake").monthly_condition_decay == 4
    assert creature_species_definition("river_serpent").habitat_stress_per_closed_route == 5
    with pytest.raises(ValueError, match="unknown creature species"):
        creature_species_definition("narrative_monster")


def test_serpent_countermeasure_profile_is_stronger_against_the_serpent_only():
    world = create_medieval_world(73)
    site = world.map.infrastructure_sites[WARD_SITE]
    settlement = next(item for item in world.society.settlements.values()
                      if item.region_id in site.region_ids)
    world.research.wards["ward:rite:test-serpent-countermeasure"] = Ward(
        id="ward:rite:test-serpent-countermeasure", settlement_id=settlement.id,
        sponsor_ref=EntityRef("polity", "auren"), rite_id="rite:test-serpent-countermeasure",
        started_day=0, until_day=40, resistance_capability_id="serpent_countermeasure",
        last_event_id="event:1")

    assert creature_site_damage_magnitude(world, "river_serpent", WARD_SITE) is None
    assert creature_site_damage_magnitude(world, "river_drake", WARD_SITE) == pytest.approx(0.10)


def test_monthly_ecology_uses_species_decay_and_only_schedules_a_future_turn():
    world = create_medieval_world(73)
    before = {item.id: item.condition for item in world.creatures.creatures.values()}
    apply_monthly_creature_ecology(world)
    drake = world.creatures.creatures["creature:drake-do-lume"]
    serpent = world.creatures.creatures["creature:drake-do-lume-echo"]
    assert drake.condition == before[drake.id] - 4
    assert serpent.condition == before[serpent.id] - 7
    assert all(event.event_type == "creature_ecology_tick" for event in world.events[-2:])
    assert not world.creatures.open_demands(drake.id)
    assert not world.creatures.open_demands(serpent.id)
    assert all(item["kind"] == "creature_review" for item in world.agenda.to_dict())


def test_monthly_ecology_reacts_to_a_canonical_closed_crossing():
    world = create_medieval_world(73)
    route = world.map.routes[ROUTE_ID]
    route.update_runtime(enabled=False)
    closure = record_event(
        world, "route_closed_for_habitat", "A travessia foi fechada por um fato material.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind="route", owner_id=route.id, aspect="enabled",
                            before="True", after="False"),),
    )
    before = {item.id: item.condition for item in world.creatures.creatures.values()}
    apply_monthly_creature_ecology(world)
    drake = world.creatures.creatures["creature:drake-do-lume"]
    assert drake.condition == before[drake.id] - 7  # 4 base + 3 habitat stress
    tick = world.events[-2] if world.events[-1].event_type == "creature_ecology_tick" else world.events[-1]
    assert tick.event_type == "creature_ecology_tick"
    assert closure.id in {link.cause_event_id for link in tick.causal_links}
    assert tick.causal_payload["ecology"] == {
        "species": "river_drake",
        "closed_route_ids": [ROUTE_ID],
        "impaired_route_ids": [ROUTE_ID],
        "habitat_stress": 3,
        "base_decay": 4,
        "total_decay": 7,
    }


def test_monthly_ecology_reacts_to_partial_operational_capacity():
    world = create_medieval_world(73)
    route = world.map.routes[ROUTE_ID]
    before_quality = route.quality
    route.update_runtime(quality=before_quality / 2)
    change = record_event(
        world, "route_capacity_reduced_for_habitat", "A capacidade da travessia caiu por dano físico.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind="route", owner_id=route.id, aspect="quality",
                            before=str(before_quality), after=str(route.quality)),),
    )
    before = world.creatures.creatures[DRAKE_ID].condition
    apply_monthly_creature_ecology(world)
    drake = world.creatures.creatures[DRAKE_ID]
    assert drake.condition == before - 6  # 4 base + ceil(0.5 * 3)
    tick = next(event for event in reversed(world.events) if event.event_type == "creature_ecology_tick")
    assert change.id in {link.cause_event_id for link in tick.causal_links}
    assert tick.causal_payload["ecology"]["impaired_route_ids"] == [ROUTE_ID]
    assert tick.causal_payload["ecology"]["closed_route_ids"] == []


async def test_unanswered_demand_can_affect_only_an_anonymous_endpoint_cohort(tmp_path):
    world = await crossed_world()
    request = next(
        option for option in creature_options(world, DRAKE_ID)
        if option.kind == "request" and option.route_id == ROUTE_ID
    )
    execute_creature_option(world, DRAKE_ID, request.id, decide(world, request).id)
    demand = next(iter(world.creatures.demands.values()))
    tick_to(world, demand.due_day + 1)

    attack = next(option for option in creature_options(world, DRAKE_ID)
                  if option.kind == "attack_population")
    group = world.society.population[attack.population_group_id]
    before = group.count
    execute_creature_option(world, DRAKE_ID, attack.id, decide(world, attack).id)
    event = world.events[-1]

    assert event.event_type == "creature_attacked_population"
    assert world.society.population[group.id].count == before - attack.population_count
    assert world.creatures.demands[demand.id].stage == "expired"
    assert HAZARD_INTERACTIONS[("river_drake", "population_group")] is DRAKE_POPULATION_DAMAGE_INTERACTION
    assert event.causal_payload["hazard_impact"]["affected_count"] == attack.population_count
    assert drake_population_damage_magnitude(world, group.id) is not None
    from src.sim.medieval.persistence import load_world, save_world, world_snapshot
    path = tmp_path / "creature-population-attack.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def decide(world, option):
    return record_event(
        world,
        "wave6_magic_decided",
        "Decisão da vertical de magia e criatura.",
        fact_kind=FactKind.DECISION,
        decision=option.decision(),
    )


async def test_completed_ward_blunts_one_drake_site_hazard():
    world = await crossed_world()
    refresh_settlement_reports(world)
    officiant = world.society.characters["character:007"]

    offer_option = next(
        option
        for option in rite_offer_options(world, officiant.id)
        if option.sponsor_ref == WARD_SPONSOR
        and option.blueprint_id == "rite-of-warding"
        and option.site_id == WARD_SITE
    )
    offer = record_rite_offer(world, officiant.id, offer_option.id)
    sponsor_option = next(
        option
        for option in rite_sponsor_options(world, WARD_SPONSOR)
        if option.offer_event_id == offer.id
    )
    ward_rite = sponsor_rite(
        world,
        WARD_SPONSOR,
        sponsor_option.id,
        decide(world, sponsor_option).id,
    )
    tick_to(world, ward_rite.due_day)
    ward = ward_active(world, "portovelho")
    assert ward is not None

    request = next(
        option
        for option in creature_options(world, DRAKE_ID)
        if option.kind == "request" and option.route_id == ROUTE_ID
    )
    execute_creature_option(world, DRAKE_ID, request.id, decide(world, request).id)
    demand = next(iter(world.creatures.demands.values()))
    tick_to(world, demand.due_day + 1)

    damage = next(
        option
        for option in creature_options(world, DRAKE_ID)
        if option.kind == "damage" and option.site_id == WARD_SITE
    )
    site_before = world.map.infrastructure_sites[WARD_SITE].integrity
    execute_creature_option(world, DRAKE_ID, damage.id, decide(world, damage).id)

    site_after = world.map.infrastructure_sites[WARD_SITE]
    assert site_before - site_after.integrity == pytest.approx(0.042)
    event = world.events[int(site_after.last_event_id.partition(":")[2]) - 1]
    assert event.event_type == "creature_damaged_site"
    assert event.causal_payload["hazard_impact"]["hazard_kind"] == "river_drake"
    assert event.causal_payload["hazard_resistance"] == {
        "standing_ward": True,
    }


async def test_serpent_population_attack_uses_its_registered_engine_law():
    world = await crossed_world()
    serpent_id = "creature:drake-do-lume-echo"
    # The shared fixture makes the primary drake hungry. One additional real
    # crossing is needed to put the authored serpent below its own threshold.
    buy_across_the_river(world)
    engine = MedievalSimulator(world)
    for _ in range(40):
        if world.creatures.creatures[serpent_id].condition < 650:
            break
        await engine.step()
    assert world.creatures.creatures[serpent_id].condition < 650
    request = next(
        option for option in creature_options(world, serpent_id)
        if option.kind == "request" and option.route_id == ROUTE_ID
    )
    execute_creature_option(world, serpent_id, request.id, decide(world, request).id)
    demand = next(item for item in world.creatures.demands.values()
                  if item.creature_id == serpent_id)
    tick_to(world, demand.due_day + 1)

    attack = next(option for option in creature_options(world, serpent_id)
                  if option.kind == "attack_population")
    group = world.society.population[attack.population_group_id]
    before = group.count
    execute_creature_option(world, serpent_id, attack.id, decide(world, attack).id)

    event = world.events[-1]
    assert event.event_type == "creature_attacked_population"
    assert world.society.population[group.id].count == before - attack.population_count
    assert event.causal_payload["hazard_impact"]["hazard_kind"] == "river_serpent"
    assert event.causal_payload["hazard_impact"]["effect"] == "reduce_population"
    assert event.causal_payload["hazard_resistance"] == {
        "standing_ward": False,
    }

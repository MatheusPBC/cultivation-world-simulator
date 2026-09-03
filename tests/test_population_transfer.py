import math

import pytest

from src.classes.causal_link import CausalRelation
from src.classes.environment.map import Map
from src.classes.environment.route import Route
from src.classes.environment.region import CityRegion
from src.classes.event import FactKind
from src.classes.mechanical_language import ConditionDefinition, ConditionInstance
from src.classes.core.world import World
from src.classes.domain_proposal import PopulationPreference
from src.systems.population_transfer import resolve_population_transfer
from src.systems.time import Month, Year, create_month_stamp


def _condition(resolve_below: float = 0.80) -> tuple[ConditionInstance, ConditionDefinition]:
    definition = ConditionDefinition(
        id="overcrowded_settlement",
        concept_id="settlement_density_pressure",
        target_kind="region",
        metric_definition_id="settlement_population_ratio",
        activate_above=0.85,
        resolve_below=resolve_below,
        activate_after_months=1,
        resolve_after_months=1,
        created_month=0,
    )
    condition = ConditionInstance(
        id="condition-1",
        definition_id=definition.id,
        target_kind="region",
        target_id="1",
        label="overcrowded settlement",
        intensity=0.9,
        started_month=1,
        cause_event_id="condition-cause",
    )
    return condition, definition


def _world_with_regions(*regions: CityRegion, connect: bool = True) -> World:
    game_map = Map(width=20, height=20)
    game_map.regions = {region.id: region for region in regions}
    if connect and regions:
        origin = regions[0]
        game_map.set_routes([
            Route(
                id=f"route-{origin.id}-{region.id}",
                endpoint_region_ids=(origin.id, region.id),
                mode="road",
                capacity=100,
                quality=0.8,
                enabled=True,
            )
            for region in regions[1:]
        ])
    return World(map=game_map, month_stamp=create_month_stamp(Year(1), Month.JANUARY))


def test_selects_destination_by_density_then_distance_and_id():
    origin = CityRegion(id=1, name="Origin", desc="", population=90.0, population_capacity=100.0, cors=[(0, 0)])
    farther_less_dense = CityRegion(id=9, name="Less dense", desc="", population=20.0, population_capacity=100.0, cors=[(15, 0)])
    nearer_more_dense = CityRegion(id=2, name="More dense", desc="", population=30.0, population_capacity=100.0, cors=[(1, 0)])
    condition, definition = _condition()
    world = _world_with_regions(origin, nearer_more_dense, farther_less_dense)

    event = resolve_population_transfer(
        world,
        origin=origin,
        condition=condition,
        condition_definition=definition,
        decision_event_id="decision-1",
    )

    assert event.event_type == "population_transfer_completed"
    assert farther_less_dense.population > 20.0
    assert nearer_more_dense.population == 30.0


def test_tie_breaks_destination_by_route_id_then_region_id():
    origin = CityRegion(id=1, name="Origin", desc="", population=90.0, population_capacity=100.0, cors=[(0, 0)])
    farther = CityRegion(id=5, name="Farther", desc="", population=20.0, population_capacity=100.0, cors=[(5, 0)])
    nearer_higher_id = CityRegion(id=4, name="Near high id", desc="", population=20.0, population_capacity=100.0, cors=[(1, 0)])
    nearer_lower_id = CityRegion(id=2, name="Near low id", desc="", population=20.0, population_capacity=100.0, cors=[(1, 0)])
    condition, definition = _condition()
    world = _world_with_regions(origin, nearer_higher_id, farther, nearer_lower_id)

    resolve_population_transfer(
        world,
        origin=origin,
        condition=condition,
        condition_definition=definition,
        decision_event_id="decision-tie",
    )

    assert nearer_lower_id.population > 20.0
    assert nearer_higher_id.population == 20.0
    assert farther.population == 20.0


def test_geometry_does_not_create_reachability_without_an_explicit_route():
    origin = CityRegion(id=1, name="Origin", desc="", population=90.0, population_capacity=100.0, cors=[(0, 0)])
    nearby = CityRegion(id=2, name="Nearby", desc="", population=20.0, population_capacity=100.0, cors=[(1, 0)])
    condition, definition = _condition()
    world = _world_with_regions(origin, nearby, connect=False)

    event = resolve_population_transfer(
        world,
        origin=origin,
        condition=condition,
        condition_definition=definition,
        decision_event_id="decision-no-route",
    )

    assert event.event_type == "population_transfer_blocked"
    assert event.causal_payload["reason"] == "no_reachable_destination_or_quantity"
    assert origin.population == 90.0
    assert nearby.population == 20.0


def test_calculates_strict_quantity_within_max_fraction():
    origin = CityRegion(id=1, name="Origin", desc="", population=90.0, population_capacity=100.0, cors=[(0, 0)])
    destination = CityRegion(id=2, name="Destination", desc="", population=20.0, population_capacity=100.0, cors=[(1, 0)])
    condition, definition = _condition(resolve_below=0.80)
    world = _world_with_regions(origin, destination)

    event = resolve_population_transfer(
        world,
        origin=origin,
        condition=condition,
        condition_definition=definition,
        decision_event_id="decision-2",
        max_fraction=0.12,
    )

    amount = event.causal_payload["affordance"]["amount"]
    assert 10.0 < amount <= 90.0 * 0.12
    assert origin.population == pytest.approx(90.0 - amount)
    assert destination.population == pytest.approx(20.0 + amount)
    assert origin.population / origin.population_capacity < definition.resolve_below
    assert math.isfinite(amount)


def test_completed_transfer_has_deltas_causality_and_preserves_total_population():
    origin = CityRegion(id=1, name="Origin", desc="", population=90.0, population_capacity=100.0, cors=[(0, 0)])
    destination = CityRegion(id=2, name="Destination", desc="", population=20.0, population_capacity=100.0, cors=[(1, 0)])
    condition, definition = _condition()
    world = _world_with_regions(origin, destination)
    total_before = origin.population + destination.population

    event = resolve_population_transfer(
        world,
        origin=origin,
        condition=condition,
        condition_definition=definition,
        decision_event_id="decision-3",
    )

    assert event.fact_kind == FactKind.STATE_TRANSITION
    assert event.event_type == "population_transfer_completed"
    assert len(event.causal_payload["deltas"]) == 2
    deltas = {delta["owner_id"]: delta for delta in event.causal_payload["deltas"]}
    assert deltas["1"]["before"] == "90.0"
    assert deltas["1"]["after"] == str(origin.population)
    assert deltas["1"]["magnitude"] < 0
    assert deltas["2"]["magnitude"] > 0
    assert event.causal_links[0].event_id == event.id
    assert event.causal_links[0].cause_event_id == "decision-3"
    assert event.causal_links[0].relation == CausalRelation.MOTIVATED_BY
    assert origin.population + destination.population == pytest.approx(total_before)


def test_partial_transfer_can_reduce_pressure_without_resolving_condition():
    origin = CityRegion(id=1, name="Origin", desc="", population=90.0, population_capacity=100.0, cors=[(0, 0)])
    destination = CityRegion(id=2, name="Destination", desc="", population=0.0, population_capacity=100.0, cors=[(1, 0)])
    condition, definition = _condition()
    world = _world_with_regions(origin, destination)

    event = resolve_population_transfer(
        world,
        origin=origin,
        condition=condition,
        condition_definition=definition,
        decision_event_id="decision-limit",
        max_fraction=0.10,
    )

    assert event.event_type == "population_transfer_completed"
    assert origin.population == pytest.approx(81.0)
    assert destination.population == pytest.approx(9.0)
    assert event.causal_payload["affordance"]["relief_complete"] is False


def test_transfer_does_not_create_the_same_pressure_at_destination():
    origin = CityRegion(
        id=1,
        name="Origin",
        desc="",
        population=105.0,
        population_capacity=100.0,
        cors=[(0, 0)],
    )
    destination = CityRegion(
        id=2,
        name="Destination",
        desc="",
        population=84.0,
        population_capacity=100.0,
        cors=[(1, 0)],
    )
    condition, definition = _condition(resolve_below=0.75)
    world = _world_with_regions(origin, destination)

    event = resolve_population_transfer(
        world,
        origin=origin,
        condition=condition,
        condition_definition=definition,
        decision_event_id="decision-safe-destination",
    )

    assert event.event_type == "population_transfer_completed"
    assert destination.population / destination.population_capacity <= (
        definition.activate_above
    )
    assert event.causal_payload["affordance"][
        "destination_safe_headroom_before"
    ] == pytest.approx(1.0)


def test_blocks_without_destination_and_does_not_mutate_state():
    origin = CityRegion(id=1, name="Origin", desc="", population=90.0, population_capacity=100.0, cors=[(0, 0)])
    full_destination = CityRegion(id=2, name="Full", desc="", population=100.0, population_capacity=100.0, cors=[(1, 0)])
    condition, definition = _condition()
    world = _world_with_regions(origin, full_destination)
    before = (origin.population, full_destination.population)

    event = resolve_population_transfer(
        world,
        origin=origin,
        condition=condition,
        condition_definition=definition,
        decision_event_id="decision-4",
    )

    assert event.fact_kind == FactKind.OCCURRENCE
    assert event.event_type == "population_transfer_blocked"
    assert event.causal_payload["outcome"] == "blocked"
    assert event.causal_payload["reason"]
    assert event.causal_links[0].cause_event_id == "decision-4"
    assert event.causal_links[0].relation == CausalRelation.MOTIVATED_BY
    assert (origin.population, full_destination.population) == before


def test_measurements_follow_metric_reading_contract_and_condition_must_match_origin():
    origin = CityRegion(id=1, name="Origin", desc="", population=90.0, population_capacity=100.0, cors=[(0, 0)])
    destination = CityRegion(id=2, name="Destination", desc="", population=20.0, population_capacity=100.0, cors=[(1, 0)])
    condition, definition = _condition()
    condition = ConditionInstance(
        id=condition.id,
        definition_id=condition.definition_id,
        target_kind="region",
        target_id="999",
        label=condition.label,
        intensity=condition.intensity,
        started_month=condition.started_month,
        cause_event_id=condition.cause_event_id,
    )
    world = _world_with_regions(origin, destination)

    event = resolve_population_transfer(
        world,
        origin=origin,
        condition=condition,
        condition_definition=definition,
        decision_event_id="decision-mismatch",
    )

    assert event.event_type == "population_transfer_blocked"
    assert origin.population == 90.0
    for reading in event.causal_payload["measurements"]:
        assert set(reading) >= {
            "key", "value", "unit", "availability", "reading_kind",
            "derived_from", "state_refs", "source_event_ids",
        }
        assert isinstance(reading["key"], dict)


def test_lower_load_preference_blocks_transfer_to_a_more_pressured_city():
    origin = CityRegion(id=1, name="Origin", desc="", population=90.0, population_capacity=100.0, cors=[(0, 0)])
    more_pressured = CityRegion(id=2, name="More pressured", desc="", population=95.0, population_capacity=100.0, cors=[(1, 0)])
    condition, definition = _condition()
    world = _world_with_regions(origin, more_pressured)

    event = resolve_population_transfer(
        world,
        origin=origin,
        condition=condition,
        condition_definition=definition,
        decision_event_id="decision-preference",
        preferences=(PopulationPreference.LOWER_SETTLEMENT_LOAD,),
    )

    assert event.event_type == "population_transfer_blocked"
    assert origin.population == 90.0
    assert more_pressured.population == 95.0

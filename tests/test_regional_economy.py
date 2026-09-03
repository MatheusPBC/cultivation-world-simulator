from src.classes.environment.region import CityRegion
from src.classes.mechanical_language import (
    MeasurementAvailability,
    MetricKey,
    PrimitiveDimension,
)
from src.classes.regional_economy import InfrastructureState, RegionalEconomyState
from src.classes.environment.tile import Tile, TileType
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidationQueue,
    DomainInvalidationLayer,
    DomainInvalidationReason,
)
from src.systems.regional_economy import phase_update_regional_economy
from src.systems.semantic_world.resolvers import resolve_metric
from src.run.load_map import load_cultivation_world_map


def _city(world, region_id=302):
    city = CityRegion(
        id=region_id,
        name="Test City",
        desc="",
        cors=[(region_id, 0)],
        population=10,
        population_capacity=100,
        economy=RegionalEconomyState(
            stocks={"grain": 12},
            capacities={"grain": 20},
            production_rates={"grain": 5},
            demand_rates={"grain": 3},
            access={"grain": 0.8},
            dependencies={"grain": 0.7},
        ),
        infrastructure=InfrastructureState(
            capacities={"transport": 4},
            quality={"roads": 0.6},
        ),
    )
    world.map.regions[region_id] = city
    return city


def test_regional_economy_state_round_trip_and_invariants():
    state = RegionalEconomyState(
        stocks={"grain": 2},
        capacities={"grain": 5},
        project_resources={"settlement_capacity_expansion": "grain"},
    )
    state.change_stock("grain", 10)
    assert state.stocks["grain"] == 5
    restored = RegionalEconomyState.from_dict(state.to_dict())
    assert restored.to_dict() == state.to_dict()


def test_resolver_reads_only_grounded_economy_and_infrastructure(base_world):
    city = _city(base_world)
    for dimension, concept, qualifiers, expected, unit in [
        (PrimitiveDimension.STOCK, "grain", (), 12, "units"),
        (PrimitiveDimension.CAPACITY, "grain", (), 20, "units"),
        (PrimitiveDimension.FLOW, "grain", (("kind", "production"),), 5, "units_per_month"),
        (PrimitiveDimension.ACCESS, "grain", (), 0.8, "ratio"),
        (PrimitiveDimension.DEPENDENCY, "grain", (), 0.7, "ratio"),
        (PrimitiveDimension.QUALITY, "roads", (), 0.6, "ratio"),
        (PrimitiveDimension.CAPACITY, "transport", (), 4, "units"),
    ]:
        reading = resolve_metric(
            base_world,
            MetricKey(
                dimension,
                "region",
                str(city.id),
                concept,
                qualifiers=qualifiers,
            ),
            target=city,
            calculated_month=int(base_world.month_stamp),
        )
        assert reading.value == expected
        assert reading.unit == unit
        assert reading.availability is MeasurementAvailability.MEASURABLE
        assert reading.state_refs

    unknown = resolve_metric(
        base_world,
        MetricKey(
            PrimitiveDimension.FLOW,
            "region",
            str(city.id),
            "ore",
            qualifiers=(("kind", "demand"),),
        ),
        target=city,
    )
    assert unknown.value is None
    assert unknown.availability is MeasurementAvailability.UNMEASURABLE


def test_explicit_production_and_demand_change_stock_with_causal_evidence(base_world):
    city = _city(base_world)
    queue = DomainInvalidationQueue()
    events = phase_update_regional_economy(base_world, invalidations=queue)
    assert city.economy.stocks["grain"] == 14
    assert [event.event_type for event in events] == [
        "regional_production",
        "regional_consumption",
    ]
    assert all(event.causal_payload and event.causal_payload["deltas"] for event in events)
    invalidations = queue.drain(layer=DomainInvalidationLayer.MECHANICAL)
    assert invalidations
    assert all(item.reason is DomainInvalidationReason.RESOURCE_STOCK_CHANGED for item in invalidations)
    assert all(item.source_event_ids for item in invalidations)


def test_shortage_is_observable_but_does_not_invent_stock_or_route(base_world):
    city = _city(base_world)
    city.economy.stocks["grain"] = 1
    city.economy.production_rates.clear()
    events = phase_update_regional_economy(base_world)
    assert city.economy.stocks["grain"] == 0
    shortage = next(event for event in events if event.event_type == "regional_resource_shortage")
    assert shortage.fact_kind.value == "occurrence"
    assert shortage.render_params["resource_id"] == "grain"
    assert len(shortage.causal_payload["measurements"]) == 2
    assert all("route" not in str(event.render_params) for event in events)


def test_map_loads_economy_as_declared_data_for_every_city():
    game_map = load_cultivation_world_map("classic")
    cities = [region for region in game_map.regions.values() if isinstance(region, CityRegion)]

    assert len(cities) == 5
    assert all("grain" in city.economy.stocks for city in cities)
    assert all("grain" in city.economy.production_rates for city in cities)
    assert all("grain" in city.economy.demand_rates for city in cities)
    assert game_map.regions[302].economy.dependencies["grain"] == 0.4
    assert all(
        city.economy.production_rates["grain"]
        == city.economy.demand_rates["grain"]
        for city in cities
    )


def test_regional_economy_survives_save_load(base_world, tmp_path):
    from src.sim.load.load_game import load_game
    from src.sim.save.save_game import save_game
    from src.sim.simulator import Simulator

    city = next(
        (region for region in base_world.map.regions.values() if isinstance(region, CityRegion)),
        None,
    )
    if city is None:
        city = CityRegion(id=302, name="Save City", desc="", cors=[(0, 0)])
        base_world.map.regions[city.id] = city
        tile = Tile(0, 0, TileType.CITY)
        tile.region = city
        base_world.map.tiles[(0, 0)] = tile
    city.economy = RegionalEconomyState(
        stocks={"grain": 12},
        capacities={"grain": 20},
        production_rates={"grain": 5},
        demand_rates={"grain": 3},
        access={"grain": 0.8},
        dependencies={"grain": 0.7},
        project_resources={"settlement_capacity_expansion": "grain"},
    )
    city.infrastructure = InfrastructureState(
        capacities={"transport": 4},
        quality={"roads": 0.6},
    )
    save_path = tmp_path / "regional_economy.json"
    success, _ = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    assert success

    loaded_world, _, _ = load_game(save_path)
    loaded_city = loaded_world.map.regions[city.id]
    assert loaded_city.economy.to_dict() == city.economy.to_dict()
    assert loaded_city.infrastructure.to_dict() == city.infrastructure.to_dict()

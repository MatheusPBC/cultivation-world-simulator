from src.run.medieval_world import create_medieval_world


def test_medieval_world_binds_every_settlement_to_the_canonical_map():
    world = create_medieval_world(seed=73)
    world.society.validate(set(world.map.regions))
    assert len(world.map.regions) == 8
    for settlement in world.society.settlements.values():
        region = world.map.regions[settlement.region_id]
        assert region.name == settlement.name
        assert region.get_region_type() == settlement.kind
        assert world.map.get_region_coordinates(settlement.region_id)
        assert "dao_tradition" not in region.get_structured_info()
    assert world.clock.absolute_day == 0
    assert world.agenda.due_days == ()


def test_trade_route_capacity_depends_on_the_actual_mountain_pass():
    world = create_medieval_world(seed=73)
    route_id = "road-pontenegro-ferroalto"
    before = world.map.get_route_operational_capacity(route_id)
    assert before > 0
    world.map.infrastructure_sites["passagem-negra"].update_runtime(integrity=0)
    assert world.map.get_route_operational_capacity(route_id) == 0
    assert world.map.routes[route_id].capacity > 0


def test_river_and_land_routes_connect_all_settlements_explicitly():
    world = create_medieval_world(seed=73)
    assert {r.mode for r in world.map.routes.values()} == {"road", "river"}
    reached = {801}
    for _ in world.map.regions:
        for route in world.map.routes.values():
            if reached.intersection(route.endpoint_region_ids):
                reached.update(route.endpoint_region_ids)
    assert reached == set(world.map.regions)
    assert world.map.get_water_bodies_touching_region(801)
    assert world.map.get_water_bodies_touching_region(802)


def test_world_randomness_is_seeded_and_not_shared_between_worlds():
    left = create_medieval_world(seed=73)
    right = create_medieval_world(seed=73)
    assert left.rng.random() == right.rng.random()
    before = right.rng.getstate()
    left.rng.random()
    assert right.rng.getstate() == before

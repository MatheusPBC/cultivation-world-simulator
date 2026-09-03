import pytest

from src.classes.environment.region import CityRegion
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.route import Route
from src.classes.event import Event
from src.classes.regional_economy import InfrastructureState, RegionalEconomyState
from src.systems.resource_transfer import resolve_resource_transfer


def _city(world, region_id: int, coordinate: tuple[int, int], stock: float, demand: float) -> CityRegion:
    city = CityRegion(
        id=region_id,
        name=f"City {region_id}",
        desc="",
        cors=[coordinate],
        economy=RegionalEconomyState(
            stocks={"grain": stock},
            capacities={"grain": 20},
            demand_rates={"grain": demand},
            access={"grain": 0.8},
        ),
        infrastructure=InfrastructureState(capacities={"transport": 5}),
    )
    world.map.regions[region_id] = city
    return city


def _decision_event(world) -> Event:
    return Event(world.month_stamp, "Supply decision.", event_type="economy_interpretation_decision")


def test_resource_transfer_blocks_route_unknown_even_when_geometry_and_city_capacity_look_valid(base_world):
    source = _city(base_world, 302, (0, 0), 12, 0)
    destination = _city(base_world, 305, (9, 9), 0, 3)
    decision = _decision_event(base_world)

    result = resolve_resource_transfer(
        base_world,
        destination=destination,
        resource_id="grain",
        decision_event_id=decision.id,
    )

    assert result.event_type == "regional_resource_transfer_blocked"
    assert result.render_params["reason"] == "route_unknown"
    assert source.economy.stocks["grain"] == 12
    assert destination.economy.stocks["grain"] == 0


def test_resource_transfer_uses_explicit_route_and_conserves_stock(base_world):
    source = _city(base_world, 302, (0, 0), 12, 0)
    destination = _city(base_world, 305, (9, 9), 0, 3)
    decision = _decision_event(base_world)
    base_world.map.set_routes([
        Route("route-17", (302, 305), "road", 2, 1.0, True),
    ])

    result = resolve_resource_transfer(
        base_world,
        destination=destination,
        resource_id="grain",
        decision_event_id=decision.id,
    )

    assert result.event_type == "regional_resource_transfer_completed"
    assert result.causal_payload["execution"]["route_id"] == "route-17"
    assert result.causal_payload["execution"]["amount"] == 2
    assert source.economy.stocks["grain"] + destination.economy.stocks["grain"] == 12
    assert result.causal_links[0].cause_event_id == decision.id


def test_resource_transfer_respects_route_infrastructure_bottleneck(base_world):
    source = _city(base_world, 302, (0, 0), 12, 0)
    destination = _city(base_world, 305, (9, 9), 0, 5)
    decision = _decision_event(base_world)
    base_world.map.set_routes([
        Route("route-17", (302, 305), "road", 10, 1.0, True),
    ])
    bridge = InfrastructureSite(
        id="bridge-17",
        kind="bridge",
        name="Bridge 17",
        cell_refs=((0, 0),),
        region_ids=(302, 305),
        route_ids=("route-17",),
        integrity=0.2,
        last_event_id="event:bridge-damaged",
    )
    base_world.map.infrastructure_sites = {bridge.id: bridge}

    result = resolve_resource_transfer(
        base_world,
        destination=destination,
        resource_id="grain",
        decision_event_id=decision.id,
    )

    assert result.event_type == "regional_resource_transfer_completed"
    assert result.causal_payload["execution"]["route_capacity"] == 10.0
    assert result.causal_payload["execution"]["transport_capacity"] == 2.0
    assert result.causal_payload["execution"]["amount"] == 2.0
    assert result.causal_payload["execution"]["route_dependency_site_ids"] == [
        "bridge-17"
    ]
    assert result.causal_payload["execution"]["route_source_event_ids"] == [
        "event:bridge-damaged"
    ]
    assert any(
        link.cause_event_id == "event:bridge-damaged"
        and link.relation.value == "contributed_to"
        for link in result.causal_links
    )


def test_route_quality_preference_uses_grounded_route_state_not_geometry(base_world):
    low_quality_source = _city(base_world, 302, (0, 0), 12, 0)
    high_quality_source = _city(base_world, 303, (50, 50), 12, 0)
    destination = _city(base_world, 305, (1, 1), 0, 3)
    decision = _decision_event(base_world)
    base_world.map.set_routes([
        Route("a-low-quality", (302, 305), "road", 10, 0.4, True),
        Route("z-high-quality", (303, 305), "road", 10, 0.9, True),
    ])

    result = resolve_resource_transfer(
        base_world,
        destination=destination,
        resource_id="grain",
        decision_event_id=decision.id,
        preferences=("higher_route_quality",),
    )

    assert result.causal_payload["execution"]["source_region_id"] == "303"
    assert result.causal_payload["execution"]["route_id"] == "z-high-quality"
    assert low_quality_source.economy.stocks["grain"] == 12
    assert high_quality_source.economy.stocks["grain"] == 9
    assert "distance_manhattan" not in result.causal_payload["execution"]


@pytest.mark.parametrize(
    "owner, field, reason",
    [
        ("destination", "stocks", "destination_stock_unknown"),
        ("destination", "capacities", "destination_capacity_unknown"),
        ("destination", "access", "destination_access_unknown"),
        ("source", "stocks", "source_stock_unknown"),
    ],
)
def test_resource_transfer_blocks_unknown_required_facts(base_world, owner, field, reason):
    source = _city(base_world, 302, (0, 0), 12, 0)
    destination = _city(base_world, 305, (9, 9), 0, 3)
    target = source if owner == "source" else destination
    getattr(target.economy, field).pop("grain")
    base_world.map.set_routes([Route("route-17", (302, 305), "road", 2, 1.0, True)])

    result = resolve_resource_transfer(
        base_world,
        destination=destination,
        resource_id="grain",
        decision_event_id="decision-transfer",
    )

    assert result.event_type == "regional_resource_transfer_blocked"
    assert result.render_params["reason"] == reason

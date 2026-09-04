from __future__ import annotations

import pytest

from src.classes.core.world import World
from src.classes.environment.climate import ClimateState, RegionalWeather
from src.classes.environment.geography import GeographyLayer
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.environment.region import NormalRegion
from src.classes.environment.tile import TileType
from src.systems.regional_hydrology import project_regional_hydrology
from src.systems.time import Month, Year, create_month_stamp


@pytest.fixture
def projection_factory():
    def build(terrain: TileType, *, with_site: bool):
        game_map = Map(width=3, height=1)
        # The unoccupied cell anchors the global elevation range used by the
        # projection to distinguish lowland from highland.
        region_elevation = 0.0 if terrain is not TileType.MOUNTAIN else 2_000.0
        anchor_elevation = 2_000.0 if region_elevation == 0.0 else 0.0
        game_map.set_geography(
            GeographyLayer(
                width=3,
                height=1,
                terrain_rows=[[terrain, terrain, TileType.PLAIN]],
                elevation_rows=[[region_elevation, region_elevation, anchor_elevation]],
                water_bodies=[],
            )
        )
        region = NormalRegion(
            id=101,
            name="Calibration region",
            desc="",
            cors=[(0, 0), (1, 0)],
        )
        game_map.regions = {region.id: region}
        game_map.region_cors = {region.id: list(region.cors)}
        if with_site:
            game_map.set_infrastructure_sites(
                [
                    InfrastructureSite(
                        id="site:calibration-drainage",
                        kind="drainage_gate",
                        name="Calibration drainage gate",
                        cell_refs=((0, 0),),
                        region_ids=(region.id,),
                        capability_ids=("drainage",),
                        integrity=1.0,
                        enabled=True,
                        last_event_id="event:calibration-site",
                    )
                ]
            )
        month = int(create_month_stamp(Year(1), Month.JANUARY))
        world = World(map=game_map, month_stamp=month)
        world.climate_state = ClimateState(
            regions={
                "101": RegionalWeather(
                    region_id="101",
                    month=month,
                    precipitation=1.0,
                    soil_saturation=1.0,
                    previous_soil_saturation=1.0,
                    source_event_id="event:maximum-rainfall",
                )
            },
            last_updated_month=month,
        )
        return project_regional_hydrology(world, region.id)

    return build


@pytest.mark.parametrize(
    ("terrain", "expected_without_site", "expected_with_site"),
    (
        (TileType.PLAIN, 0.7264, 0.5264),
        (TileType.SWAMP, 1.0, 0.812),
        (TileType.MOUNTAIN, 0.3696, 0.1696),
    ),
)
def test_maximum_weather_calibration_uses_bounded_real_projection(
    projection_factory,
    terrain: TileType,
    expected_without_site: float,
    expected_with_site: float,
) -> None:
    without_site = projection_factory(terrain, with_site=False)
    with_site = projection_factory(terrain, with_site=True)

    assert without_site is not None
    assert with_site is not None
    assert without_site.flooding == pytest.approx(expected_without_site)
    assert with_site.flooding == pytest.approx(expected_with_site)
    assert with_site.drainage > without_site.drainage
    assert with_site.flooding < without_site.flooding


def test_one_full_site_protects_plain_activation_but_not_swamp(
    projection_factory,
) -> None:
    plain = projection_factory(TileType.PLAIN, with_site=True)
    swamp = projection_factory(TileType.SWAMP, with_site=True)

    assert plain is not None
    assert swamp is not None
    assert plain.flooding < 0.72
    assert swamp.flooding > 0.72

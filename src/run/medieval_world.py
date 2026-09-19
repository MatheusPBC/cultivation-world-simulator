"""Assemble the medieval society on the existing physical map infrastructure."""

from pathlib import Path
import random

from src.classes.core.medieval_world import MedievalWorld
from src.classes.core.medieval_config import MedievalRunConfig
from src.classes.environment.map import Map
from src.classes.society import SocietyState
from src.classes.society.region import SettlementRegion
from src.run.map_source import MapSource, collect_region_coords, read_map_source
from src.run.medieval_society import create_medieval_society
from src.run.medieval_economy import create_medieval_economy
from src.run.medieval_governance import create_authority, create_strategy
from src.run.medieval_research import create_research
from src.run.medieval_creatures import create_creatures


MAP_PATH = Path(__file__).resolve().parents[2] / "static/game_configs/maps/vale-das-tres-coroas/map.json"


def build_medieval_map(source: MapSource, society: SocietyState) -> Map:
    coords = collect_region_coords(source.region_rows)
    society.validate(set(coords))
    if set(coords) != {s.region_id for s in society.settlements.values()}:
        raise ValueError("map regions and society settlements do not match")
    game_map = Map(source.width, source.height, source.map_id, "Vale das Três Coroas", source.version)
    game_map.set_geography(source.geography)
    for y, row in enumerate(source.geography.terrain_rows):
        for x, terrain in enumerate(row):
            game_map.create_tile(x, y, terrain)
    for settlement in society.settlements.values():
        region = SettlementRegion(settlement.region_id, settlement.id, coords[settlement.region_id], society)
        game_map.regions[region.id] = region
        game_map.region_cors[region.id] = region.cors
        for cell in region.cors:
            game_map.tiles[cell].region = region
    game_map.landmarks = {rid: value.to_dict() for rid, value in source.landmarks.items()}
    game_map.region_overrides = {rid: value.to_dict() for rid, value in source.region_overrides.items()}
    game_map.set_routes(source.routes)
    game_map.set_infrastructure_sites(source.infrastructure_sites)
    return game_map


def create_medieval_world(seed: int, *, character_count: int | None = None,
                          bootstrap_household_income: bool = False) -> MedievalWorld:
    society = create_medieval_society(seed, character_count=character_count)
    game_map = build_medieval_map(read_map_source(MAP_PATH), society)
    economy = create_medieval_economy(society)
    world = MedievalWorld(map=game_map, society=society, rng=random.Random(seed),
                          economy=economy,
                          authority=create_authority(society),
                          strategy=create_strategy(society, economy),
                          research=create_research(),
                          creatures=create_creatures(game_map),
                          config=MedievalRunConfig(seed=seed, character_count=len(society.characters)))
    if bootstrap_household_income:
        from src.sim.medieval.opening_income import allocate_opening_household_income
        allocate_opening_household_income(world)
    return world

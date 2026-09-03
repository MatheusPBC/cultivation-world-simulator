from __future__ import annotations

from .base import LoadContext


class RegionRuntimeLoadSection:
    key = "region_runtime"

    def load(self, context: LoadContext) -> None:
        from src.classes.environment.region import CityRegion, CultivateRegion
        from src.systems.formation import filter_expired_region_formations

        world = context.world
        world_data = context.world_data or {}
        game_map = context.game_map
        all_avatars = context.all_avatars or {}

        route_data = world_data.get("routes")
        if route_data is not None:
            from src.classes.environment.route import Route

            if not isinstance(route_data, list):
                raise ValueError("Saved routes must be a list")
            game_map.set_routes(Route.from_dict(item) for item in route_data)

        for rid_str, avatar_id in world_data.get("cultivate_regions_hosts", {}).items():
            rid = int(rid_str)
            if rid in game_map.regions:
                region = game_map.regions[rid]
                if isinstance(region, CultivateRegion) and avatar_id in all_avatars:
                    all_avatars[avatar_id].occupy_region(region)

        for rid_str, status in world_data.get("regions_status", {}).items():
            rid = int(rid_str)
            if rid in game_map.regions:
                region = game_map.regions[rid]
                if isinstance(region, CityRegion):
                    region.population = status.get("population", region.population)
                    region.population_capacity = status["population_capacity"]
                    from src.classes.environment.city_state import CityState
                    from src.classes.regional_economy import InfrastructureState, RegionalEconomyState
                    region.economy = RegionalEconomyState.from_dict(status.get("economy", {}))
                    region.infrastructure = InfrastructureState.from_dict(status.get("infrastructure", {}))
                    city_state_data = status.get("city_state")
                    if city_state_data is not None:
                        region.city_state = CityState.from_dict(
                            city_state_data,
                            city_tiles=region.cors,
                        )
                tradition = status.get("dao_tradition")
                if tradition:
                    from src.classes.celestial_dao import DaoTradition
                    region.dao_tradition = DaoTradition(tradition)

        region_formations = {}
        for rid_str, formation in (world_data.get("region_formations", {}) or {}).items():
            try:
                rid = int(rid_str)
            except (TypeError, ValueError):
                continue
            if rid not in game_map.regions or not isinstance(formation, dict):
                continue
            region_formations[rid] = dict(formation)
        game_map.region_formations = region_formations
        filter_expired_region_formations(world, int(world.month_stamp))

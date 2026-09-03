"""External stimuli used only by the causal torture harness."""

from __future__ import annotations

from dataclasses import dataclass, replace
from copy import deepcopy
import math
from typing import TYPE_CHECKING, Any

from src.classes.causal_origin import CausalOrigin
from src.classes.environment.city_state import CityGovernance, UrbanServiceDemand
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint

if TYPE_CHECKING:
    from src.classes.environment.route import Route


CAUSAL_PROBE_PROFILES = frozenset({
    "baseline",
    "population_pressure",
    "resource_shortage",
    "blocked_resource_shortage",
    "urban_service_strain",
    "institutional_urban_strain",
    "health_recovery_strain",
})

_INSTITUTIONAL_DYNASTY_ID = 91001
_INSTITUTIONAL_SECT_ID = 91002
_INSTITUTIONAL_MEMBER_ID = "causal-torture:institutional-member"
_HEALTH_AVATAR_ID = "causal-torture:health-avatar"


@dataclass(frozen=True, slots=True)
class InstitutionalUrbanStrainSetup:
    """Canonical entities installed by the institutional torture harness."""

    city: CityRegion
    dynasty: Any
    sect: Any
    member: Any


@dataclass(frozen=True, slots=True)
class HealthRecoveryStrainSetup:
    """Canonical health probe entities selected from the current world."""

    city: CityRegion
    demand: UrbanServiceDemand
    asset: Any
    avatar: Any


class CausalProbeApplicationError(RuntimeError):
    """Raised when a probe cannot be committed with its canonical mutation."""


@dataclass(frozen=True, slots=True)
class PopulationSurgeProbe:
    id: str
    month_offset: int
    region_id: int
    target_ratio: float


@dataclass(frozen=True, slots=True)
class ResourceSupplyShockProbe:
    id: str
    month_offset: int
    region_id: int
    resource_id: str
    remaining_stock_fraction: float
    production_fraction: float


@dataclass(frozen=True, slots=True)
class RouteInterruptionProbe:
    id: str
    month_offset: int
    route_id: str


@dataclass(frozen=True, slots=True)
class UrbanServiceStrainProbe:
    id: str
    month_offset: int
    region_id: int
    capability_id: str
    asset_id: str
    remaining_integrity_fraction: float


@dataclass(frozen=True, slots=True)
class AvatarInjuryProbe:
    id: str
    month_offset: int
    avatar_id: str
    target_damage_ratio: float


CausalProbe = (
    PopulationSurgeProbe
    | ResourceSupplyShockProbe
    | RouteInterruptionProbe
    | UrbanServiceStrainProbe
    | AvatarInjuryProbe
)


def build_causal_probe_schedule(world: Any, profile: str) -> tuple[CausalProbe, ...]:
    if profile == "baseline":
        return ()
    if profile == "population_pressure":
        origin = _select_population_origin(world)
        if origin is None:
            return ()
        return (
            PopulationSurgeProbe(
                id=f"population-pressure:region:{origin.id}",
                month_offset=0,
                region_id=int(origin.id),
                target_ratio=1.05,
            ),
        )
    if profile in {"resource_shortage", "blocked_resource_shortage"}:
        selected = _select_resource_supply(world)
        if selected is None:
            return ()
        destination, resource_id, route = selected
        shock = ResourceSupplyShockProbe(
            id=f"resource-shortage:region:{destination.id}:{resource_id}",
            month_offset=0,
            region_id=int(destination.id),
            resource_id=resource_id,
            remaining_stock_fraction=0.0,
            production_fraction=0.0,
        )
        if profile == "resource_shortage":
            return (shock,)
        return (
            RouteInterruptionProbe(
                id=f"route-interruption:route:{route.id}",
                month_offset=0,
                route_id=str(route.id),
            ),
            shock,
        )
    if profile in {"urban_service_strain", "institutional_urban_strain"}:
        selected = _select_urban_service_strain(world)
        if selected is None:
            return ()
        city, demand, asset = selected
        prefix = (
            "institutional-urban-strain"
            if profile == "institutional_urban_strain"
            else "urban-service-strain"
        )
        return (
            UrbanServiceStrainProbe(
                id=f"{prefix}:region:{city.id}:{demand.capability_id}:{asset.id}",
                month_offset=0,
                region_id=int(city.id),
                capability_id=demand.capability_id,
                asset_id=asset.id,
                remaining_integrity_fraction=0.5,
            ),
        )
    if profile == "health_recovery_strain":
        selected = _select_urban_service_strain(world, capability_id="healing")
        if selected is None:
            return ()
        city, demand, asset = selected
        avatar = getattr(world, "avatar_manager", None)
        avatar = (
            avatar.get_avatar(_HEALTH_AVATAR_ID)
            if avatar is not None and hasattr(avatar, "get_avatar")
            else None
        )
        if avatar is None or getattr(avatar, "is_dead", False):
            return ()
        return (
            AvatarInjuryProbe(
                id=f"health-recovery-strain:avatar:{avatar.id}",
                month_offset=0,
                avatar_id=str(avatar.id),
                target_damage_ratio=0.4,
            ),
            UrbanServiceStrainProbe(
                id=f"health-recovery-strain:region:{city.id}:{demand.capability_id}:{asset.id}",
                month_offset=0,
                region_id=int(city.id),
                capability_id=demand.capability_id,
                asset_id=asset.id,
                remaining_integrity_fraction=0.5,
            ),
        )
    raise ValueError(f"Unknown causal probe profile: {profile}")


def _city_anchor(world: Any, city: CityRegion) -> Any:
    anchor = next(
        (
            world.map.tiles.get((int(x), int(y)))
            for x, y in sorted(city.cors)
            if (int(x), int(y)) in world.map.tiles
        ),
        None,
    )
    if anchor is None:
        anchor = next(
            (tile for tile in world.map.tiles.values() if tile.region is city),
            None,
        )
    if anchor is None:
        raise CausalProbeApplicationError(
            "health probe target has no map tile"
        )
    anchor.region = city
    return anchor


def prepare_health_recovery_strain_world(
    world: Any,
) -> HealthRecoveryStrainSetup | None:
    """Install or reuse one canonical Avatar at a grounded healing city."""
    selected = _select_urban_service_strain(world, capability_id="healing")
    if selected is None:
        return None
    city, demand, asset = selected
    anchor = _city_anchor(world, city)

    from src.classes.core.avatar import Avatar
    from src.classes.age import Age
    from src.classes.alignment import Alignment
    from src.classes.appearance import get_appearance_by_level
    from src.classes.gender import Gender
    from src.classes.race import get_race
    from src.classes.root import Root
    from src.systems.cultivation import CultivationProgress, Realm
    from src.systems.time import MonthStamp

    avatar = world.avatar_manager.get_avatar(_HEALTH_AVATAR_ID)
    if avatar is None:
        avatar = Avatar(
            world=world,
            name="Health Harness Avatar",
            id=_HEALTH_AVATAR_ID,
            birth_month_stamp=MonthStamp(int(world.month_stamp) - 216),
            age=Age(18, Realm.Qi_Refinement, innate_max_lifespan=10000),
            gender=Gender.MALE,
            race=get_race("human"),
            cultivation_progress=CultivationProgress(0),
            pos_x=anchor.x,
            pos_y=anchor.y,
            root=Root.GOLD,
            personas=[],
            alignment=Alignment.NEUTRAL,
            base_appearance=get_appearance_by_level(5),
        )
        world.avatar_manager.register_avatar(avatar)
    if getattr(avatar, "is_dead", False):
        raise CausalProbeApplicationError("health probe avatar must remain alive")
    avatar.pos_x = anchor.x
    avatar.pos_y = anchor.y
    avatar.tile = anchor
    return HealthRecoveryStrainSetup(
        city=city,
        demand=demand,
        asset=asset,
        avatar=avatar,
    )


def prepare_institutional_urban_strain_world(world: Any) -> InstitutionalUrbanStrainSetup:
    """Prepare grounded institutional owners for the torture harness.

    This deliberately operates only on canonical ``World`` entities.  It does
    not add population records or call an LLM; repeated calls reuse the same
    harness entities and leave the selected city's population untouched.
    """
    selected = _select_urban_service_strain(world)
    if selected is None:
        raise CausalProbeApplicationError(
            "institutional urban strain requires a grounded city service"
        )
    city, _, _ = selected

    from src.classes.core.dynasty import Dynasty, dynasties_by_id
    from src.classes.core.sect import Sect, sects_by_id
    from src.classes.core.avatar import Avatar
    from src.classes.age import Age
    from src.classes.alignment import Alignment
    from src.classes.gender import Gender
    from src.classes.items.magic_stone import MagicStone
    from src.classes.appearance import get_appearance_by_level
    from src.classes.race import get_race
    from src.classes.root import Root
    from src.classes.sect_ranks import SectRank
    from src.systems.cultivation import CultivationProgress, Realm
    from src.systems.sect_member_support import support_amount
    from src.systems.time import MonthStamp

    anchor = next(
        (
            world.map.tiles.get((int(x), int(y)))
            for x, y in sorted(city.cors)
            if (int(x), int(y)) in world.map.tiles
        ),
        None,
    )
    if anchor is None:
        anchor = next(
            (tile for tile in world.map.tiles.values() if tile.region is city),
            None,
        )
    if anchor is None:
        raise CausalProbeApplicationError(
            "institutional urban strain target has no map tile"
        )
    # Test worlds may inject a CityRegion after map construction.  Rebinding
    # the canonical tile keeps the member's location grounded in that city.
    anchor.region = city

    dynasty = getattr(world, "dynasty", None)
    if not isinstance(dynasty, Dynasty) or int(getattr(dynasty, "id", 0)) != _INSTITUTIONAL_DYNASTY_ID:
        template = min(dynasties_by_id.values(), key=lambda item: int(item.id), default=None)
        if template is None:
            raise CausalProbeApplicationError(
                "institutional urban strain requires a configured dynasty"
            )
        dynasty = deepcopy(template)
        dynasty.id = _INSTITUTIONAL_DYNASTY_ID
        dynasty.template_name = str(template.name)
        world.dynasty = dynasty

    existed_sects = list(getattr(world, "existed_sects", []) or [])
    sect = next(
        (
            item
            for item in existed_sects
            if isinstance(item, Sect) and int(getattr(item, "id", 0)) == _INSTITUTIONAL_SECT_ID
        ),
        None,
    )
    sect_created = sect is None
    if sect is None:
        template = min(
            (item for item in sects_by_id.values() if getattr(item, "is_active", True)),
            key=lambda item: int(item.id),
            default=None,
        )
        if template is None:
            raise CausalProbeApplicationError(
                "institutional urban strain requires a configured active sect"
            )
        sect = deepcopy(template)
        sect.id = _INSTITUTIONAL_SECT_ID
        sect.members.clear()
        existed_sects.append(sect)
    sect.is_active = True
    if sect_created:
        sect.magic_stone = max(
            int(getattr(sect, "magic_stone", 0)),
            support_amount() * 2,
        )
    unique_sects: list[Sect] = []
    seen_sect_ids: set[int] = set()
    for item in existed_sects:
        sect_id = int(getattr(item, "id", 0))
        if sect_id in seen_sect_ids:
            continue
        seen_sect_ids.add(sect_id)
        unique_sects.append(item)
    world.existed_sects = unique_sects
    if hasattr(world, "_sect_context") and world._sect_context is not None:
        world._sect_context.from_existed_sects(world.existed_sects)

    dynasty.current_emperor_id = _INSTITUTIONAL_MEMBER_ID
    city.city_state = replace(
        city.city_state,
        governance=CityGovernance(
            controller_kind="dynasty",
            controller_id=str(dynasty.id),
            administrative_capacity=max(
                float(city.city_state.governance.administrative_capacity), 1.0
            ),
        ),
    )

    member = world.avatar_manager.get_avatar(_INSTITUTIONAL_MEMBER_ID)
    member_created = member is None
    if member is None:
        x, y = anchor.x, anchor.y
        member = Avatar(
            world=world,
            name="Institutional Harness Member",
            id=_INSTITUTIONAL_MEMBER_ID,
            birth_month_stamp=MonthStamp(int(world.month_stamp) - 216),
            age=Age(18, Realm.Qi_Refinement, innate_max_lifespan=10000),
            gender=Gender.MALE,
            race=get_race("human"),
            cultivation_progress=CultivationProgress(0),
            pos_x=x,
            pos_y=y,
            root=Root.GOLD,
            personas=[],
            alignment=Alignment.NEUTRAL,
            base_appearance=get_appearance_by_level(5),
        )
        world.avatar_manager.register_avatar(member)
    if getattr(member, "is_dead", False):
        raise CausalProbeApplicationError(
            "institutional torture member must remain alive"
        )
    x, y = anchor.x, anchor.y
    member.pos_x = x
    member.pos_y = y
    member.tile = anchor
    if getattr(member, "sect", None) is not sect:
        member.join_sect(sect, SectRank.OuterDisciple)
    if member_created:
        member.magic_stone = MagicStone(0)

    return InstitutionalUrbanStrainSetup(
        city=city,
        dynasty=dynasty,
        sect=sect,
        member=member,
    )


def _cities(world: Any) -> list[CityRegion]:
    return sorted(
        (
            region
            for region in world.map.regions.values()
            if isinstance(region, CityRegion)
        ),
        key=lambda city: int(city.id),
    )


def _select_population_origin(world: Any) -> CityRegion | None:
    cities = [city for city in _cities(world) if float(city.population_capacity) > 0]
    candidates = [
        origin
        for origin in cities
        if any(
            destination.id != origin.id
            and destination.population < destination.population_capacity
            and destination.population_ratio < origin.population_ratio
            and bool(world.map.get_routes_between(origin.id, destination.id))
            for destination in cities
        )
    ]
    return min(
        candidates,
        key=lambda city: (-city.population_ratio, int(city.id)),
        default=None,
    )


def _select_resource_supply(world: Any) -> tuple[CityRegion, str, "Route"] | None:
    candidates: list[tuple[tuple[float, int, str, str, int], CityRegion, str, Any]] = []
    cities = _cities(world)
    for destination in cities:
        for resource_id, demand in sorted(destination.economy.demand_rates.items()):
            if float(demand) <= 0 or float(destination.economy.access.get(resource_id, 0.0)) <= 0:
                continue
            for source in cities:
                if source.id == destination.id:
                    continue
                available_stock = source.economy.available_stock(resource_id)
                if available_stock is None or available_stock <= 0:
                    continue
                if float(source.economy.access.get(resource_id, 0.0)) <= 0:
                    continue
                routes = world.map.get_routes_between(
                    source.id,
                    destination.id,
                    resource_id=resource_id,
                )
                for route in routes:
                    if float(route.capacity) * float(route.quality) <= 0:
                        continue
                    candidates.append((
                        (-float(demand), int(destination.id), resource_id, route.id, int(source.id)),
                        destination,
                        resource_id,
                        route,
                    ))
    if not candidates:
        return None
    _, destination, resource_id, route = min(candidates, key=lambda item: item[0])
    return destination, resource_id, route


def _select_urban_service_strain(
    world: Any,
    *,
    capability_id: str | None = None,
) -> tuple[CityRegion, UrbanServiceDemand, Any] | None:
    """Choose the most exposed grounded city service deterministically."""
    candidates: list[tuple[tuple[float, int, str, str], CityRegion, UrbanServiceDemand, Any]] = []
    for city in _cities(world):
        for demand in sorted(city.city_state.service_demands, key=lambda item: item.capability_id):
            if capability_id is not None and demand.capability_id != capability_id:
                continue
            assets = [
                asset
                for asset in city.city_state.assets
                if (
                    demand.capability_id in asset.capability_ids
                    and asset.capacity > 0
                    and asset.quality > 0
                    and asset.integrity > 0
                )
            ]
            if not assets:
                continue
            capacity = sum(
                asset.capacity * asset.quality * asset.integrity
                for asset in assets
            )
            if capacity <= 0:
                continue
            service_load = city.population * demand.demand_per_population
            pressure = service_load / capacity
            for asset in assets:
                candidates.append(
                    (
                        (-pressure, int(city.id), demand.capability_id, asset.id),
                        city,
                        demand,
                        asset,
                    )
                )
    if not candidates:
        return None
    _, city, demand, asset = min(candidates, key=lambda item: item[0])
    return city, demand, asset


def _population_surge(world: Any, probe: PopulationSurgeProbe) -> tuple[Event, tuple[str, ...]]:
    region = world.map.regions.get(probe.region_id)
    if not isinstance(region, CityRegion):
        raise CausalProbeApplicationError("population probe target must be a city")
    target_ratio = float(probe.target_ratio)
    if not math.isfinite(target_ratio) or target_ratio <= 0:
        raise CausalProbeApplicationError("population probe ratio must be positive")
    before = float(region.population)
    after = float(region.population_capacity) * target_ratio
    if after <= before:
        raise CausalProbeApplicationError("population probe must increase canonical load")

    region.change_population(after - before)
    event = Event(
        world.month_stamp,
        t(
            "A causal probe increased population pressure in {region}.",
            region=region.name,
        ),
        event_type="causal_probe_population_surge",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.EXTERNAL_EVENT,
        render_params={
            "probe_id": probe.id,
            "region_id": str(region.id),
            "target_ratio": target_ratio,
        },
    )
    event.causal_payload = {
        "outcome": "applied",
        "probe_id": probe.id,
        "deltas": [
            StateDelta(
                event_id=event.id,
                owner_kind="region",
                owner_id=str(region.id),
                aspect="population",
                before=str(before),
                after=str(float(region.population)),
                magnitude=float(region.population) - before,
            ).to_dict(),
        ],
    }
    return event, (f"region:{region.id}",)


def _resource_supply_shock(
    world: Any,
    probe: ResourceSupplyShockProbe,
) -> tuple[Event, tuple[str, ...]]:
    region = world.map.regions.get(probe.region_id)
    if not isinstance(region, CityRegion):
        raise CausalProbeApplicationError("resource probe target must be a city")
    resource_id = str(probe.resource_id).strip()
    if (
        not resource_id
        or resource_id not in region.economy.stocks
        or resource_id not in region.economy.production_rates
    ):
        raise CausalProbeApplicationError("resource probe requires grounded stock and production")
    stock_fraction = float(probe.remaining_stock_fraction)
    production_fraction = float(probe.production_fraction)
    if any(
        not math.isfinite(value) or not 0.0 <= value <= 1.0
        for value in (stock_fraction, production_fraction)
    ):
        raise CausalProbeApplicationError("resource probe fractions must be in [0, 1]")
    stock_before = float(region.economy.stocks[resource_id])
    production_before = float(region.economy.production_rates[resource_id])
    stock_after = stock_before * stock_fraction
    production_after = production_before * production_fraction
    if stock_after == stock_before and production_after == production_before:
        raise CausalProbeApplicationError("resource probe must change canonical supply")
    region.economy.set_production_rate(resource_id, production_after)
    region.economy.set_stock(resource_id, stock_after)
    event = Event(
        world.month_stamp,
        t(
            "A causal probe reduced {resource} supply in {region}.",
            resource=resource_id,
            region=region.name,
        ),
        event_type="causal_probe_resource_supply_shock",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.EXTERNAL_EVENT,
        render_params={
            "probe_id": probe.id,
            "region_id": str(region.id),
            "resource_id": resource_id,
        },
    )
    event.causal_payload = {
        "outcome": "applied",
        "probe_id": probe.id,
        "deltas": [
            StateDelta(
                event_id=event.id,
                owner_kind="region",
                owner_id=str(region.id),
                aspect=f"resource_stock:{resource_id}",
                before=str(stock_before),
                after=str(stock_after),
                magnitude=stock_after - stock_before,
            ).to_dict(),
            StateDelta(
                event_id=event.id,
                owner_kind="region",
                owner_id=str(region.id),
                aspect=f"resource_production_rate:{resource_id}",
                before=str(production_before),
                after=str(production_after),
                magnitude=production_after - production_before,
            ).to_dict(),
        ],
    }
    return event, (f"region:{region.id}",)


def _route_interruption(
    world: Any,
    probe: RouteInterruptionProbe,
) -> tuple[Event, tuple[str, ...]]:
    route = world.map.routes.get(probe.route_id)
    if route is None or not route.enabled:
        raise CausalProbeApplicationError("route probe requires an enabled canonical route")
    route.update_runtime(enabled=False)
    event = Event(
        world.month_stamp,
        t("A causal probe interrupted route {route}.", route=route.id),
        event_type="causal_probe_route_interruption",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.EXTERNAL_EVENT,
        render_params={
            "probe_id": probe.id,
            "route_id": route.id,
            "endpoint_region_ids": [str(item) for item in route.endpoint_region_ids],
            "allowed_resource_ids": list(route.allowed_resource_ids),
        },
    )
    event.causal_payload = {
        "outcome": "applied",
        "probe_id": probe.id,
        "deltas": [
            StateDelta(
                event_id=event.id,
                owner_kind="route",
                owner_id=route.id,
                aspect="enabled",
                before="True",
                after="False",
            ).to_dict(),
        ],
    }
    return event, tuple(f"region:{region_id}" for region_id in route.endpoint_region_ids)


def _urban_service_strain(
    world: Any,
    probe: UrbanServiceStrainProbe,
) -> tuple[Event, tuple[str, ...]]:
    region = world.map.regions.get(probe.region_id)
    if not isinstance(region, CityRegion):
        raise CausalProbeApplicationError("urban service probe target must be a city")
    demand = next(
        (
            item
            for item in region.city_state.service_demands
            if item.capability_id == probe.capability_id
        ),
        None,
    )
    if demand is None:
        raise CausalProbeApplicationError(
            "urban service probe requires a declared service demand"
        )
    asset = next(
        (
            item
            for item in region.city_state.assets
            if item.id == probe.asset_id
            and demand.capability_id in item.capability_ids
        ),
        None,
    )
    if asset is None or asset.capacity <= 0 or asset.quality <= 0:
        raise CausalProbeApplicationError(
            "urban service probe requires a grounded capable asset"
        )
    fraction = float(probe.remaining_integrity_fraction)
    if not math.isfinite(fraction) or not 0.0 <= fraction < 1.0:
        raise CausalProbeApplicationError(
            "urban service probe integrity fraction must be in [0, 1)"
        )
    before = float(asset.integrity)
    after = before * fraction
    if after >= before:
        raise CausalProbeApplicationError(
            "urban service probe must reduce canonical asset integrity"
        )

    replacement = replace(asset, integrity=after)
    region.city_state = replace(
        region.city_state,
        assets=tuple(
            replacement if current.id == asset.id else current
            for current in region.city_state.assets
        ),
    )
    event = Event(
        world.month_stamp,
        t(
            "A causal probe strained {service} service in {region}.",
            service=demand.capability_id,
            region=region.name,
        ),
        event_type="causal_probe_urban_service_strain",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.EXTERNAL_EVENT,
        render_params={
            "probe_id": probe.id,
            "region_id": str(region.id),
            "capability_id": demand.capability_id,
            "asset_id": asset.id,
            "remaining_integrity_fraction": fraction,
        },
    )
    delta = StateDelta(
        event_id=event.id,
        owner_kind="region",
        owner_id=str(region.id),
        aspect="urban_asset_integrity",
        before=str(before),
        after=str(after),
        magnitude=after - before,
    )
    event.causal_payload = {
        "outcome": "applied",
        "probe_id": probe.id,
        "service_capability_id": demand.capability_id,
        "asset_id": asset.id,
        "deltas": [delta.to_dict()],
    }
    return event, (f"region:{region.id}",)


def _avatar_injury(
    world: Any,
    probe: AvatarInjuryProbe,
) -> tuple[Event, tuple[str, ...]]:
    manager = getattr(world, "avatar_manager", None)
    avatar = (
        manager.get_avatar(probe.avatar_id)
        if manager is not None and hasattr(manager, "get_avatar")
        else None
    )
    if avatar is None or getattr(avatar, "is_dead", False):
        raise CausalProbeApplicationError(
            "health probe requires a living canonical avatar"
        )
    ratio = float(probe.target_damage_ratio)
    if not math.isfinite(ratio) or not 0.25 <= ratio < 1.0:
        raise CausalProbeApplicationError(
            "health probe damage ratio must be in [0.25, 1)"
        )
    hp = getattr(avatar, "hp", None)
    before = getattr(hp, "cur", None)
    maximum = getattr(hp, "max", None)
    if (
        isinstance(before, bool)
        or isinstance(maximum, bool)
        or not isinstance(before, int)
        or not isinstance(maximum, int)
        or maximum <= 0
        or before <= 1
    ):
        raise CausalProbeApplicationError("health probe requires usable avatar HP")
    damage = max(1, int(maximum * ratio))
    damage = min(damage, before - 1)
    if damage <= 0:
        raise CausalProbeApplicationError("health probe must cause non-fatal damage")
    hp.reduce(damage)
    region = getattr(getattr(avatar, "tile", None), "region", None)
    if not isinstance(region, CityRegion):
        raise CausalProbeApplicationError(
            "health probe avatar must be located in a city"
        )
    event = Event(
        world.month_stamp,
        t(
            "A causal probe injured {avatar} without killing them.",
            avatar=avatar.name,
        ),
        related_avatars=[str(avatar.id)],
        event_type="causal_probe_avatar_injury",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.EXTERNAL_EVENT,
        render_params={
            "probe_id": probe.id,
            "avatar_id": str(avatar.id),
            "region_id": str(region.id),
            "damage": damage,
        },
    )
    event.causal_payload = {
        "outcome": "applied",
        "probe_id": probe.id,
        "damage": damage,
        "deltas": [],
    }
    from src.classes.individual_consequence import record_hp_change_from_event

    if not record_hp_change_from_event(avatar, event, before):
        raise CausalProbeApplicationError(
            "health probe could not record canonical HP change"
        )
    # The collective-health reading owns this source through the Avatar's
    # active injury.  Putting it in the generic regional carry would falsely
    # attribute unrelated settlement and economy metrics to the injury.
    return event, ()


def apply_causal_probe(world: Any, probe: CausalProbe) -> Event:
    checkpoint = SimulationMonthCheckpoint.capture(world)
    try:
        if isinstance(probe, PopulationSurgeProbe):
            event, target_refs = _population_surge(world, probe)
        elif isinstance(probe, ResourceSupplyShockProbe):
            event, target_refs = _resource_supply_shock(world, probe)
        elif isinstance(probe, RouteInterruptionProbe):
            event, target_refs = _route_interruption(world, probe)
        elif isinstance(probe, UrbanServiceStrainProbe):
            event, target_refs = _urban_service_strain(world, probe)
        elif isinstance(probe, AvatarInjuryProbe):
            event, target_refs = _avatar_injury(world, probe)
        else:
            raise TypeError(f"Unsupported causal probe: {type(probe).__name__}")
        for target_ref in target_refs:
            if isinstance(probe, UrbanServiceStrainProbe):
                pending = (
                    world.mechanical_language.pending_affinity_source_event_ids
                    .setdefault(target_ref, {})
                    .setdefault(f"urban_service:{probe.capability_id}", [])
                )
            else:
                pending = world.mechanical_language.pending_target_source_event_ids.setdefault(
                    target_ref,
                    [],
                )
            if event.id not in pending:
                pending.append(event.id)
        if not world.event_manager.commit_step([event]):
            raise CausalProbeApplicationError("causal probe event commit failed")
        return event
    except BaseException:
        checkpoint.restore()
        raise


__all__ = [
    "CAUSAL_PROBE_PROFILES",
    "CausalProbeApplicationError",
    "CausalProbe",
    "InstitutionalUrbanStrainSetup",
    "HealthRecoveryStrainSetup",
    "PopulationSurgeProbe",
    "ResourceSupplyShockProbe",
    "RouteInterruptionProbe",
    "UrbanServiceStrainProbe",
    "AvatarInjuryProbe",
    "apply_causal_probe",
    "build_causal_probe_schedule",
    "prepare_institutional_urban_strain_world",
    "prepare_health_recovery_strain_world",
]

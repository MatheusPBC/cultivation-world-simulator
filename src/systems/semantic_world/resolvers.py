from __future__ import annotations

from dataclasses import replace
from typing import Any

from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.environment.city_state import UrbanServiceDemand
from src.classes.mechanical_language.bindings import (
    GroundedMetricBinding,
    MetricResolverRegistry,
    exact_reading,
)
from src.classes.mechanical_language.models import (
    MeasurementAvailability,
    MetricKey,
    MetricReading,
    PrimitiveDimension,
    ReadingKind,
)
from src.systems.collective_health import project_collective_health
from src.systems.spiritual_ecology import (
    SPIRITUAL_ANCHOR_CONCEPT,
    SPIRITUAL_ANCHOR_QUALIFIERS,
    SPIRITUAL_ANCHOR_RATIO_CONCEPT,
    SPIRITUAL_ANCHOR_RATIO_QUALIFIERS,
    SPIRITUAL_ESSENCE_CONCEPT,
    SPIRITUAL_FORMATION_CONCEPT,
    SPIRITUAL_FORMATION_QUALIFIERS,
    SPIRITUAL_GRAVE_CONCEPT,
    SPIRITUAL_GRAVE_QUALIFIERS,
    SPIRITUAL_TREASURE_CONCEPT,
    SPIRITUAL_TREASURE_QUALIFIERS,
    resolve_spiritual_metric,
    spiritual_essence_qualifiers,
)
from src.systems.regional_hydrology import (
    CLIMATE_QUALIFIERS,
    DRAINAGE_CONCEPT,
    FLOODING_CONCEPT,
    HYDROLOGY_QUALIFIERS,
    PRECIPITATION_CONCEPT,
    SOIL_WATER_CONCEPT,
    project_regional_hydrology,
)


def _settlement_value(
    _world: Any,
    key: MetricKey,
    subject: Any,
    month: int,
) -> MetricReading | None:
    if not isinstance(subject, CityRegion):
        return None
    if key.dimension is PrimitiveDimension.LOAD:
        return exact_reading(
            key,
            subject.population,
            "ten_thousand_people",
            month,
            f"region:{subject.id}:population",
        )
    if key.dimension is PrimitiveDimension.CAPACITY:
        return exact_reading(
            key,
            subject.population_capacity,
            "ten_thousand_people",
            month,
            f"region:{subject.id}:population_capacity",
        )
    return None


def _settlement_key(dimension: PrimitiveDimension):
    def enumerate_keys(_world: Any, subject: Any):
        if isinstance(subject, CityRegion):
            yield MetricKey(dimension, "region", str(subject.id), "settlement")

    return enumerate_keys


_URBAN_SERVICE_QUALIFIERS = (("kind", "urban_service"),)


def _urban_service_demand(
    subject: CityRegion, capability_id: str
) -> UrbanServiceDemand | None:
    return next(
        (
            item
            for item in subject.city_state.service_demands
            if item.capability_id == capability_id
        ),
        None,
    )


def _urban_service_refs(
    subject: CityRegion,
    demand: UrbanServiceDemand,
) -> tuple[str, list[str]]:
    demand_ref = f"region:{subject.id}:urban_service_demand:{demand.capability_id}"
    asset_refs = [
        f"region:{subject.id}:urban_asset:{asset.id}:capacity_quality_integrity"
        for asset in subject.city_state.assets
        if demand.capability_id in asset.capability_ids
    ]
    return demand_ref, asset_refs


def _urban_service_group_refs(
    subject: CityRegion,
) -> list[str]:
    return sorted(
        f"region:{subject.id}:urban_population_group:{group.id}:profile"
        for group in subject.city_state.population_groups
    )


def _urban_service_capacity(
    subject: CityRegion,
    demand: UrbanServiceDemand,
) -> tuple[float, list[str]]:
    demand_ref, asset_refs = _urban_service_refs(subject, demand)
    capacity = subject.city_state.effective_service_capacity(demand.capability_id)
    return float(capacity), [demand_ref, *asset_refs]


def _urban_group_allocations(
    subject: CityRegion,
    demand: UrbanServiceDemand,
    capacity: float,
) -> dict[str, float]:
    """Allocate limited service capacity with weighted saturation.

    Each round allocates the remaining capacity proportionally to the
    unsatisfied groups' demand multiplied by their declared priority. A group
    that saturates at its demand leaves its unused share for the next round.
    This makes the result independent of collection order and redistributes
    surplus deterministically.
    """
    groups = tuple(subject.city_state.population_groups)
    groups_by_id = {group.id: group for group in groups}
    group_demands = {
        group.id: float(subject.population * group.population_weight * demand.demand_per_population)
        for group in groups
    }
    allocations = {group_id: 0.0 for group_id in group_demands}
    remaining_capacity = max(0.0, float(capacity))
    unsatisfied = set(group_demands)
    tolerance = 1e-12
    while unsatisfied and remaining_capacity > tolerance:
        ordered_group_ids = sorted(unsatisfied)
        total_demand = sum(group_demands[group_id] for group_id in ordered_group_ids)
        if total_demand <= tolerance:
            break
        priorities = {
            group_id: max(
                0.0,
                groups_by_id[group_id].priority_for(demand.capability_id),
            )
            for group_id in ordered_group_ids
        }
        max_priority = max(priorities.values(), default=0.0)
        weighted = {
            group_id: group_demands[group_id]
            * (priorities[group_id] / max_priority if max_priority > 0 else 0.0)
            for group_id in ordered_group_ids
        }
        total_weight = sum(weighted.values())
        if total_weight <= tolerance:
            weighted = {
                group_id: group_demands[group_id] for group_id in ordered_group_ids
            }
            total_weight = total_demand
        saturated: set[str] = set()
        distributed = 0.0
        for group_id in ordered_group_ids:
            share = remaining_capacity * weighted[group_id] / total_weight
            available = group_demands[group_id] - allocations[group_id]
            amount = min(max(0.0, share), max(0.0, available))
            allocations[group_id] += amount
            distributed += amount
            if available - amount <= tolerance:
                saturated.add(group_id)
        if distributed <= tolerance:
            break
        remaining_capacity -= distributed
        unsatisfied.difference_update(saturated)
        if not saturated and remaining_capacity <= tolerance:
            break
    return allocations


def _urban_service_value(
    _world: Any,
    key: MetricKey,
    subject: Any,
    month: int,
) -> MetricReading | None:
    if not isinstance(subject, CityRegion):
        return None
    if key.qualifiers != _URBAN_SERVICE_QUALIFIERS:
        return None
    demand = _urban_service_demand(subject, key.concept_id)
    if demand is None:
        return None
    demand_ref, asset_refs = _urban_service_refs(subject, demand)
    load = float(subject.population * demand.demand_per_population)
    if key.dimension is PrimitiveDimension.LOAD:
        if key.group_id is not None:
            return None
        return MetricReading(
            key=key,
            value=load,
            unit="service_units",
            availability=MeasurementAvailability.MEASURABLE,
            reading_kind=ReadingKind.DERIVED,
            calculated_month=month,
            state_refs=[f"region:{subject.id}:population", demand_ref],
        )
    if key.dimension is PrimitiveDimension.CAPACITY:
        if key.group_id is not None:
            return None
        capacity, refs = _urban_service_capacity(subject, demand)
        return MetricReading(
            key=key,
            value=capacity,
            unit="service_units",
            availability=MeasurementAvailability.MEASURABLE,
            reading_kind=ReadingKind.DERIVED,
            calculated_month=month,
            state_refs=refs,
        )
    if key.dimension is not PrimitiveDimension.ACCESS:
        return None
    capacity, capacity_refs = _urban_service_capacity(subject, demand)
    if key.group_id is None:
        access = 1.0 if load == 0 else min(1.0, capacity / load)
        return MetricReading(
            key=key,
            value=access,
            unit="ratio",
            availability=MeasurementAvailability.MEASURABLE,
            reading_kind=ReadingKind.DERIVED,
            calculated_month=month,
            derived_from=[
                MetricKey(
                    PrimitiveDimension.LOAD,
                    "region",
                    str(subject.id),
                    key.concept_id,
                    qualifiers=key.qualifiers,
                ).to_dict(),
                MetricKey(
                    PrimitiveDimension.CAPACITY,
                    "region",
                    str(subject.id),
                    key.concept_id,
                    qualifiers=key.qualifiers,
                ).to_dict(),
            ],
            state_refs=[f"region:{subject.id}:population", demand_ref, *capacity_refs[1:]],
        )
    group = next(
        (item for item in subject.city_state.population_groups if item.id == key.group_id),
        None,
    )
    if group is None:
        return None
    allocations = _urban_group_allocations(subject, demand, capacity)
    group_load = float(subject.population * group.population_weight * demand.demand_per_population)
    group_access = 1.0 if group_load == 0 else min(1.0, allocations[group.id] / group_load)
    group_profile_refs = _urban_service_group_refs(subject)
    return MetricReading(
        key=key,
        value=group_access,
        unit="ratio",
        availability=MeasurementAvailability.MEASURABLE,
        reading_kind=ReadingKind.DERIVED,
        calculated_month=month,
        derived_from=[
            MetricKey(
                PrimitiveDimension.LOAD,
                "region",
                str(subject.id),
                key.concept_id,
                qualifiers=key.qualifiers,
            ).to_dict(),
            MetricKey(
                PrimitiveDimension.CAPACITY,
                "region",
                str(subject.id),
                key.concept_id,
                qualifiers=key.qualifiers,
            ).to_dict(),
        ],
        state_refs=[
            f"region:{subject.id}:population",
            demand_ref,
            *capacity_refs[1:],
            *group_profile_refs,
        ],
    )


def _urban_service_keys(dimension: PrimitiveDimension):
    def enumerate_keys(_world: Any, subject: Any):
        if not isinstance(subject, CityRegion):
            return
        qualifiers = _URBAN_SERVICE_QUALIFIERS
        for demand in subject.city_state.service_demands:
            yield MetricKey(
                dimension,
                "region",
                str(subject.id),
                demand.capability_id,
                qualifiers=qualifiers,
            )
            if dimension is PrimitiveDimension.ACCESS:
                for group in subject.city_state.population_groups:
                    yield MetricKey(
                        dimension,
                        "region",
                        str(subject.id),
                        demand.capability_id,
                        group_id=group.id,
                        qualifiers=qualifiers,
                    )

    return enumerate_keys


_COLLECTIVE_HEALTH_QUALIFIERS = (("kind", "collective_health"),)


def _spiritual_essence_keys(element: str):
    qualifiers = spiritual_essence_qualifiers(element)

    def enumerate_keys(_world: Any, subject: Any):
        if getattr(subject, "essence", None) is not None:
            yield MetricKey(
                PrimitiveDimension.STOCK,
                "region",
                str(subject.id),
                SPIRITUAL_ESSENCE_CONCEPT,
                qualifiers=qualifiers,
            )

    return enumerate_keys


def _spiritual_value(
    world: Any,
    key: MetricKey,
    subject: Any,
    month: int,
) -> MetricReading | None:
    return resolve_spiritual_metric(world, key, subject, month)


def _spiritual_essence_bindings() -> list[GroundedMetricBinding]:
    return [
        GroundedMetricBinding(
            id=f"region.spiritual.essence.{element.lower()}",
            subject_kind="region",
            dimension=PrimitiveDimension.STOCK,
            concept_pattern=SPIRITUAL_ESSENCE_CONCEPT,
            unit="essence_density",
            resolver=_spiritual_value,
            enumerate_keys=_spiritual_essence_keys(element),
            required_qualifiers=spiritual_essence_qualifiers(element),
            exact_qualifiers=True,
        )
        for element in ("GOLD", "WOOD", "WATER", "FIRE", "EARTH")
    ]


def _collective_health_value(
    world: Any,
    key: MetricKey,
    subject: Any,
    month: int,
) -> MetricReading | None:
    if not isinstance(subject, CityRegion):
        return None
    view = project_collective_health(world, subject.id)
    source = (
        view.active_wounded_count
        if key.dimension is PrimitiveDimension.LOAD
        and key.concept_id == "active_wounded"
        else view.hp_deficit
        if key.dimension is PrimitiveDimension.LOAD
        and key.concept_id == "hp_deficit"
        else None
    )
    if source is not None:
        if source.value is None:
            return None
        return MetricReading(
            key=key,
            value=float(source.value),
            unit=source.unit,
            availability=source.availability,
            reading_kind=source.reading_kind,
            calculated_month=month,
            state_refs=list(source.state_refs),
            source_event_ids=list(source.source_event_ids),
        )
    if key.dimension is not PrimitiveDimension.RISK or key.concept_id != "injury_burden":
        return None
    living = view.living_avatar_count.value
    wounded = view.active_wounded_count.value
    if living is None or wounded is None:
        return None
    burden = 0.0 if float(living) <= 0 else min(1.0, float(wounded) / float(living))
    return MetricReading(
        key=key,
        value=burden,
        unit="ratio",
        availability=MeasurementAvailability.MEASURABLE,
        reading_kind=ReadingKind.DERIVED,
        calculated_month=month,
        state_refs=list(dict.fromkeys((
            *view.living_avatar_count.state_refs,
            *view.active_wounded_count.state_refs,
        ))),
        source_event_ids=list(view.active_wounded_count.source_event_ids),
    )


def _collective_health_keys(dimension: PrimitiveDimension, concept_id: str):
    def enumerate_keys(_world: Any, subject: Any):
        if isinstance(subject, CityRegion):
            yield MetricKey(
                dimension,
                "region",
                str(subject.id),
                concept_id,
                qualifiers=_COLLECTIVE_HEALTH_QUALIFIERS,
            )

    return enumerate_keys


def _regional_economy_value(
    _world: Any,
    key: MetricKey,
    subject: Any,
    month: int,
) -> MetricReading | None:
    if not isinstance(subject, CityRegion):
        return None
    economy = subject.economy
    infrastructure = subject.infrastructure
    concept_id = key.concept_id
    if key.dimension is PrimitiveDimension.STOCK and concept_id in economy.stocks:
        return exact_reading(
            key,
            economy.stocks[concept_id],
            "units",
            month,
            f"region:{subject.id}:stock:{concept_id}",
        )
    if key.dimension is PrimitiveDimension.CAPACITY:
        if concept_id in economy.capacities:
            return exact_reading(
                key,
                economy.capacities[concept_id],
                "units",
                month,
                f"region:{subject.id}:capacity:{concept_id}",
            )
        if concept_id in infrastructure.capacities:
            return exact_reading(
                key,
                infrastructure.capacities[concept_id],
                "units",
                month,
                f"region:{subject.id}:infrastructure_capacity:{concept_id}",
            )
    if key.dimension is PrimitiveDimension.FLOW:
        flow_kind = key.qualifier("kind")
        values = (
            economy.production_rates
            if flow_kind == "production"
            else economy.demand_rates
            if flow_kind == "demand"
            else {}
        )
        if concept_id in values:
            return exact_reading(
                key,
                values[concept_id],
                "units_per_month",
                month,
                f"region:{subject.id}:{flow_kind}:{concept_id}",
            )
    if key.dimension is PrimitiveDimension.ACCESS and concept_id in economy.access:
        return exact_reading(
            key,
            economy.access[concept_id],
            "ratio",
            month,
            f"region:{subject.id}:access:{concept_id}",
        )
    if (
        key.dimension is PrimitiveDimension.DEPENDENCY
        and concept_id in economy.dependencies
    ):
        return exact_reading(
            key,
            economy.dependencies[concept_id],
            "ratio",
            month,
            f"region:{subject.id}:dependency:{concept_id}",
        )
    if (
        key.dimension is PrimitiveDimension.QUALITY
        and concept_id in infrastructure.quality
    ):
        return exact_reading(
            key,
            infrastructure.quality[concept_id],
            "ratio",
            month,
            f"region:{subject.id}:infrastructure_quality:{concept_id}",
        )
    if key.dimension is PrimitiveDimension.QUALITY:
        assets = [
            asset
            for asset in subject.city_state.assets
            if concept_id in asset.capability_ids
        ]
        if assets:
            weights = [asset.capacity if asset.capacity > 0 else 1.0 for asset in assets]
            value = sum(
                asset.quality * asset.integrity * weight
                for asset, weight in zip(assets, weights, strict=True)
            ) / sum(weights)
            return MetricReading(
                key=key,
                value=value,
                unit="ratio",
                availability=MeasurementAvailability.MEASURABLE,
                reading_kind=ReadingKind.DERIVED,
                calculated_month=month,
                state_refs=[
                    f"region:{subject.id}:urban_asset:{asset.id}:quality_integrity"
                    for asset in assets
                ],
            )
    return None


def _economy_keys(dimension: PrimitiveDimension, source: str):
    def enumerate_keys(_world: Any, subject: Any):
        if not isinstance(subject, CityRegion):
            return
        economy = subject.economy
        infrastructure = subject.infrastructure
        if source == "stocks":
            concept_ids = economy.stocks
        elif source == "capacities":
            concept_ids = {*economy.capacities, *infrastructure.capacities}
        elif source == "production_rates":
            concept_ids = economy.production_rates
        elif source == "demand_rates":
            concept_ids = economy.demand_rates
        elif source == "access":
            concept_ids = economy.access
        elif source == "dependencies":
            concept_ids = economy.dependencies
        else:
            concept_ids = {
                *infrastructure.quality,
                *(
                    capability_id
                    for asset in subject.city_state.assets
                    for capability_id in asset.capability_ids
                ),
            }
        qualifiers = (
            (("kind", "production"),)
            if source == "production_rates"
            else (("kind", "demand"),)
            if source == "demand_rates"
            else ()
        )
        for concept_id in sorted(concept_ids):
            yield MetricKey(
                dimension,
                "region",
                str(subject.id),
                str(concept_id),
                qualifiers=qualifiers,
            )

    return enumerate_keys


_INFRASTRUCTURE_SITE_QUALIFIERS = (("kind", "infrastructure_site"),)
_ROUTE_OPERATIONAL_QUALIFIERS = (("kind", "route_operational"),)


def _route_operational_capacity_value(
    world: Any,
    key: MetricKey,
    subject: Any,
    month: int,
) -> MetricReading | None:
    if not isinstance(subject, Route):
        return None
    game_map = getattr(world, "map", None)
    if game_map is None or subject.id not in getattr(game_map, "routes", {}):
        return None
    dependency_sites = game_map.get_route_dependency_sites(subject.id)
    return MetricReading(
        key=key,
        value=game_map.get_route_operational_capacity(subject.id),
        unit="transport_units_per_month",
        availability=MeasurementAvailability.MEASURABLE,
        reading_kind=ReadingKind.DERIVED,
        calculated_month=month,
        state_refs=[
            f"map:route:{subject.id}:capacity",
            f"map:route:{subject.id}:quality",
            f"map:route:{subject.id}:enabled",
            *(
                state_ref
                for site in dependency_sites
                for state_ref in (
                    f"map:infrastructure_site:{site.id}:integrity",
                    f"map:infrastructure_site:{site.id}:enabled",
                    f"map:infrastructure_site:{site.id}:route:{subject.id}",
                )
            ),
        ],
        source_event_ids=list(dict.fromkeys(
            site.last_event_id
            for site in dependency_sites
            if site.last_event_id is not None
        )),
    )


def _route_operational_capacity_keys(_world: Any, subject: Any):
    if isinstance(subject, Route):
        yield MetricKey(
            PrimitiveDimension.CAPACITY,
            "route",
            subject.id,
            "transport",
            qualifiers=_ROUTE_OPERATIONAL_QUALIFIERS,
        )


def _infrastructure_sites_for_region(
    world: Any,
    subject: Any,
    *,
    capability_id: str | None = None,
) -> list[Any]:
    game_map = getattr(world, "map", None)
    sites = getattr(game_map, "infrastructure_sites", None)
    region_id = getattr(subject, "id", None)
    if not isinstance(sites, dict) or region_id is None:
        return []
    normalized_region_id = str(region_id)
    return sorted(
        (
            site
            for site in sites.values()
            if normalized_region_id in {str(item) for item in site.region_ids}
            and (
                capability_id is None
                or capability_id in site.capability_ids
            )
        ),
        key=lambda site: site.id,
    )


def _infrastructure_site_capacity_value(
    world: Any,
    key: MetricKey,
    subject: Any,
    month: int,
) -> MetricReading | None:
    sites = _infrastructure_sites_for_region(
        world,
        subject,
        capability_id=key.concept_id,
    )
    if not sites:
        return None
    return MetricReading(
        key=key,
        value=sum(site.integrity if site.enabled else 0.0 for site in sites),
        unit="site_equivalents",
        availability=MeasurementAvailability.MEASURABLE,
        reading_kind=ReadingKind.DERIVED,
        calculated_month=month,
        state_refs=[
            state_ref
            for site in sites
            for state_ref in (
                f"map:infrastructure_site:{site.id}:enabled",
                f"map:infrastructure_site:{site.id}:integrity",
                f"map:infrastructure_site:{site.id}:capability:{key.concept_id}",
            )
        ],
        source_event_ids=list(dict.fromkeys(
            site.last_event_id
            for site in sites
            if site.last_event_id is not None
        )),
    )


def _infrastructure_site_capacity_keys(world: Any, subject: Any):
    sites = _infrastructure_sites_for_region(world, subject)
    for capability_id in sorted({
        capability_id
        for site in sites
        for capability_id in site.capability_ids
    }):
        yield MetricKey(
            PrimitiveDimension.CAPACITY,
            "region",
            str(subject.id),
            capability_id,
            qualifiers=_INFRASTRUCTURE_SITE_QUALIFIERS,
        )


def _magic_stone_value(
    _world: Any,
    key: MetricKey,
    subject: Any,
    month: int,
) -> MetricReading | None:
    value = getattr(subject, "magic_stone", None)
    if value is None:
        return None
    return exact_reading(
        key,
        float(value),
        "spirit_stone",
        month,
        f"{key.subject_kind}:{key.subject_id}:magic_stone",
    )


def _regional_hydrology_value(
    world: Any,
    key: MetricKey,
    subject: Any,
    month: int,
) -> MetricReading | None:
    region_id = getattr(subject, "id", None)
    if region_id is None:
        return None
    projection = project_regional_hydrology(world, region_id)
    if projection is None:
        return None
    values = {
        (PrimitiveDimension.LOAD, PRECIPITATION_CONCEPT): projection.precipitation,
        (PrimitiveDimension.LOAD, SOIL_WATER_CONCEPT): projection.soil_water,
        (PrimitiveDimension.CAPACITY, DRAINAGE_CONCEPT): projection.drainage,
        (PrimitiveDimension.RISK, FLOODING_CONCEPT): projection.flooding,
    }
    value = values.get((key.dimension, key.concept_id))
    if value is None:
        return None
    is_climate = key.concept_id in {PRECIPITATION_CONCEPT, SOIL_WATER_CONCEPT}
    if key.concept_id == PRECIPITATION_CONCEPT:
        state_refs = [f"climate:region:{region_id}:precipitation"]
        source_event_ids = projection.climate_source_event_ids
    elif key.concept_id == SOIL_WATER_CONCEPT:
        state_refs = [f"climate:region:{region_id}:soil_saturation"]
        source_event_ids = projection.climate_source_event_ids
    elif key.concept_id == DRAINAGE_CONCEPT:
        state_refs = list(projection.drainage_state_refs)
        source_event_ids = projection.drainage_source_event_ids
    else:
        state_refs = list(projection.flooding_state_refs)
        source_event_ids = projection.flooding_trigger_event_ids
    return MetricReading(
        key=key,
        value=value,
        unit="ratio",
        availability=MeasurementAvailability.MEASURABLE,
        reading_kind=ReadingKind.EXACT if is_climate else ReadingKind.DERIVED,
        calculated_month=month,
        state_refs=state_refs,
        source_event_ids=list(source_event_ids),
    )


def _regional_hydrology_key(
    dimension: PrimitiveDimension,
    concept_id: str,
    qualifiers: tuple[tuple[str, str], ...],
):
    def enumerate_keys(world: Any, subject: Any):
        region_id = getattr(subject, "id", None)
        if region_id is not None and project_regional_hydrology(world, region_id) is not None:
            yield MetricKey(
                dimension,
                "region",
                str(region_id),
                concept_id,
                qualifiers=qualifiers,
            )

    return enumerate_keys


DEFAULT_METRIC_RESOLVERS = MetricResolverRegistry(
    [
        GroundedMetricBinding(
            id="region.climate.precipitation",
            subject_kind="region",
            dimension=PrimitiveDimension.LOAD,
            concept_pattern=PRECIPITATION_CONCEPT,
            unit="ratio",
            resolver=_regional_hydrology_value,
            enumerate_keys=_regional_hydrology_key(
                PrimitiveDimension.LOAD,
                PRECIPITATION_CONCEPT,
                CLIMATE_QUALIFIERS,
            ),
            required_qualifiers=CLIMATE_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.climate.soil_water",
            subject_kind="region",
            dimension=PrimitiveDimension.LOAD,
            concept_pattern=SOIL_WATER_CONCEPT,
            unit="ratio",
            resolver=_regional_hydrology_value,
            enumerate_keys=_regional_hydrology_key(
                PrimitiveDimension.LOAD,
                SOIL_WATER_CONCEPT,
                CLIMATE_QUALIFIERS,
            ),
            required_qualifiers=CLIMATE_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.hydrology.drainage",
            subject_kind="region",
            dimension=PrimitiveDimension.CAPACITY,
            concept_pattern=DRAINAGE_CONCEPT,
            unit="ratio",
            resolver=_regional_hydrology_value,
            enumerate_keys=_regional_hydrology_key(
                PrimitiveDimension.CAPACITY,
                DRAINAGE_CONCEPT,
                HYDROLOGY_QUALIFIERS,
            ),
            required_qualifiers=HYDROLOGY_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.hydrology.flooding",
            subject_kind="region",
            dimension=PrimitiveDimension.RISK,
            concept_pattern=FLOODING_CONCEPT,
            unit="ratio",
            resolver=_regional_hydrology_value,
            enumerate_keys=_regional_hydrology_key(
                PrimitiveDimension.RISK,
                FLOODING_CONCEPT,
                HYDROLOGY_QUALIFIERS,
            ),
            required_qualifiers=HYDROLOGY_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="route.operational.capacity",
            subject_kind="route",
            dimension=PrimitiveDimension.CAPACITY,
            concept_pattern="transport",
            unit="transport_units_per_month",
            resolver=_route_operational_capacity_value,
            enumerate_keys=_route_operational_capacity_keys,
            required_qualifiers=_ROUTE_OPERATIONAL_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.settlement.load",
            subject_kind="region",
            dimension=PrimitiveDimension.LOAD,
            concept_pattern="settlement",
            unit="ten_thousand_people",
            resolver=_settlement_value,
            enumerate_keys=_settlement_key(PrimitiveDimension.LOAD),
        ),
        GroundedMetricBinding(
            id="region.settlement.capacity",
            subject_kind="region",
            dimension=PrimitiveDimension.CAPACITY,
            concept_pattern="settlement",
            unit="ten_thousand_people",
            resolver=_settlement_value,
            enumerate_keys=_settlement_key(PrimitiveDimension.CAPACITY),
        ),
        GroundedMetricBinding(
            id="region.infrastructure_site.capacity",
            subject_kind="region",
            dimension=PrimitiveDimension.CAPACITY,
            concept_pattern="*",
            unit="site_equivalents",
            resolver=_infrastructure_site_capacity_value,
            enumerate_keys=_infrastructure_site_capacity_keys,
            required_qualifiers=_INFRASTRUCTURE_SITE_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.urban_service.load",
            subject_kind="region",
            dimension=PrimitiveDimension.LOAD,
            concept_pattern="*",
            unit="service_units",
            resolver=_urban_service_value,
            enumerate_keys=_urban_service_keys(PrimitiveDimension.LOAD),
            required_qualifiers=_URBAN_SERVICE_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.urban_service.capacity",
            subject_kind="region",
            dimension=PrimitiveDimension.CAPACITY,
            concept_pattern="*",
            unit="service_units",
            resolver=_urban_service_value,
            enumerate_keys=_urban_service_keys(PrimitiveDimension.CAPACITY),
            required_qualifiers=_URBAN_SERVICE_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.urban_service.access",
            subject_kind="region",
            dimension=PrimitiveDimension.ACCESS,
            concept_pattern="*",
            unit="ratio",
            resolver=_urban_service_value,
            enumerate_keys=_urban_service_keys(PrimitiveDimension.ACCESS),
            required_qualifiers=_URBAN_SERVICE_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.collective_health.active_wounded",
            subject_kind="region",
            dimension=PrimitiveDimension.LOAD,
            concept_pattern="active_wounded",
            unit="avatars",
            resolver=_collective_health_value,
            enumerate_keys=_collective_health_keys(
                PrimitiveDimension.LOAD,
                "active_wounded",
            ),
            required_qualifiers=_COLLECTIVE_HEALTH_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.collective_health.hp_deficit",
            subject_kind="region",
            dimension=PrimitiveDimension.LOAD,
            concept_pattern="hp_deficit",
            unit="hp",
            resolver=_collective_health_value,
            enumerate_keys=_collective_health_keys(
                PrimitiveDimension.LOAD,
                "hp_deficit",
            ),
            required_qualifiers=_COLLECTIVE_HEALTH_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.collective_health.injury_burden",
            subject_kind="region",
            dimension=PrimitiveDimension.RISK,
            concept_pattern="injury_burden",
            unit="ratio",
            resolver=_collective_health_value,
            enumerate_keys=_collective_health_keys(
                PrimitiveDimension.RISK,
                "injury_burden",
            ),
            required_qualifiers=_COLLECTIVE_HEALTH_QUALIFIERS,
            exact_qualifiers=True,
        ),
        *_spiritual_essence_bindings(),
        GroundedMetricBinding(
            id="region.spiritual.grave_presence",
            subject_kind="region",
            dimension=PrimitiveDimension.LOAD,
            concept_pattern=SPIRITUAL_GRAVE_CONCEPT,
            unit="graves",
            resolver=_spiritual_value,
            required_qualifiers=SPIRITUAL_GRAVE_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.spiritual.formation_presence",
            subject_kind="region",
            dimension=PrimitiveDimension.LOAD,
            concept_pattern=SPIRITUAL_FORMATION_CONCEPT,
            unit="formations",
            resolver=_spiritual_value,
            required_qualifiers=SPIRITUAL_FORMATION_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.spiritual.anchor_load",
            subject_kind="region",
            dimension=PrimitiveDimension.LOAD,
            concept_pattern=SPIRITUAL_ANCHOR_CONCEPT,
            unit="anchors",
            resolver=_spiritual_value,
            required_qualifiers=SPIRITUAL_ANCHOR_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.spiritual.anchor_ratio",
            subject_kind="region",
            dimension=PrimitiveDimension.QUALITY,
            concept_pattern=SPIRITUAL_ANCHOR_RATIO_CONCEPT,
            unit="ratio",
            resolver=_spiritual_value,
            required_qualifiers=SPIRITUAL_ANCHOR_RATIO_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.spiritual.treasure_presence",
            subject_kind="region",
            dimension=PrimitiveDimension.LOAD,
            concept_pattern=SPIRITUAL_TREASURE_CONCEPT,
            unit="treasures",
            resolver=_spiritual_value,
            required_qualifiers=SPIRITUAL_TREASURE_QUALIFIERS,
            exact_qualifiers=True,
        ),
        GroundedMetricBinding(
            id="region.economy.stock",
            subject_kind="region",
            dimension=PrimitiveDimension.STOCK,
            concept_pattern="*",
            unit="units",
            resolver=_regional_economy_value,
            enumerate_keys=_economy_keys(PrimitiveDimension.STOCK, "stocks"),
        ),
        GroundedMetricBinding(
            id="region.economy.capacity",
            subject_kind="region",
            dimension=PrimitiveDimension.CAPACITY,
            concept_pattern="*",
            unit="units",
            resolver=_regional_economy_value,
            enumerate_keys=_economy_keys(PrimitiveDimension.CAPACITY, "capacities"),
        ),
        GroundedMetricBinding(
            id="region.economy.production",
            subject_kind="region",
            dimension=PrimitiveDimension.FLOW,
            concept_pattern="*",
            unit="units_per_month",
            resolver=_regional_economy_value,
            enumerate_keys=_economy_keys(
                PrimitiveDimension.FLOW,
                "production_rates",
            ),
            required_qualifiers=(("kind", "production"),),
        ),
        GroundedMetricBinding(
            id="region.economy.demand",
            subject_kind="region",
            dimension=PrimitiveDimension.FLOW,
            concept_pattern="*",
            unit="units_per_month",
            resolver=_regional_economy_value,
            enumerate_keys=_economy_keys(PrimitiveDimension.FLOW, "demand_rates"),
            required_qualifiers=(("kind", "demand"),),
        ),
        GroundedMetricBinding(
            id="region.economy.access",
            subject_kind="region",
            dimension=PrimitiveDimension.ACCESS,
            concept_pattern="*",
            unit="ratio",
            resolver=_regional_economy_value,
            enumerate_keys=_economy_keys(PrimitiveDimension.ACCESS, "access"),
        ),
        GroundedMetricBinding(
            id="region.economy.dependency",
            subject_kind="region",
            dimension=PrimitiveDimension.DEPENDENCY,
            concept_pattern="*",
            unit="ratio",
            resolver=_regional_economy_value,
            enumerate_keys=_economy_keys(
                PrimitiveDimension.DEPENDENCY,
                "dependencies",
            ),
        ),
        GroundedMetricBinding(
            id="region.infrastructure.quality",
            subject_kind="region",
            dimension=PrimitiveDimension.QUALITY,
            concept_pattern="*",
            unit="ratio",
            resolver=_regional_economy_value,
            enumerate_keys=_economy_keys(PrimitiveDimension.QUALITY, "quality"),
        ),
        GroundedMetricBinding(
            id="owner.spirit_stone.stock",
            subject_kind="*",
            dimension=PrimitiveDimension.STOCK,
            concept_pattern="spirit_stone",
            unit="spirit_stone",
            resolver=_magic_stone_value,
        ),
    ]
)


def metric_unit(key: MetricKey) -> str | None:
    return DEFAULT_METRIC_RESOLVERS.unit_for(key)


def available_metric_keys(world: Any, target: Any) -> list[MetricKey]:
    return DEFAULT_METRIC_RESOLVERS.available_keys(world, target)


def resolve_metric(
    world: Any,
    key: MetricKey,
    *,
    target: Any | None = None,
    calculated_month: int = 0,
) -> MetricReading:
    subject = target or _resolve_subject(world, key)
    return DEFAULT_METRIC_RESOLVERS.resolve(
        world,
        key,
        target=subject,
        calculated_month=calculated_month,
    )


def resolve_derived_metric(
    world: Any,
    definition: Any,
    *,
    target: Any,
    calculated_month: int,
    definitions: dict[str, Any],
) -> MetricReading:
    """Evaluate a registered definition and expose its canonical metric key."""
    from src.classes.mechanical_language.expressions import evaluate_expression
    from src.systems.semantic_world.condition_semantics import metric_leaves

    reading = evaluate_expression(
        definition.expression,
        world=world,
        target=target,
        target_kind=definition.target_kind,
        definitions=definitions,
        calculated_month=calculated_month,
    )
    leaves = metric_leaves(definition.expression, definitions)
    group_ids = {
        str(leaf["group_id"])
        for leaf in leaves
        if leaf.get("group_id") is not None
    }
    qualifier_sets = {
        tuple(
            sorted(
                (str(name), str(value))
                for name, value in dict(leaf.get("qualifiers", {}) or {}).items()
            )
        )
        for leaf in leaves
    }
    group_id = next(iter(group_ids)) if len(group_ids) == 1 else None
    qualifiers = next(iter(qualifier_sets)) if len(qualifier_sets) == 1 else ()
    return replace(
        reading,
        key=MetricKey(
            definition.dimension,
            definition.target_kind,
            str(getattr(target, "id", "")),
            definition.concept_id,
            group_id=group_id,
            qualifiers=qualifiers,
        ),
        unit=definition.unit,
    )


def _resolve_subject(world: Any, key: MetricKey) -> Any | None:
    if world is None:
        return None
    if key.subject_kind == "region":
        try:
            return world.map.regions.get(int(key.subject_id))
        except (TypeError, ValueError, AttributeError):
            return None
    if key.subject_kind == "route":
        return getattr(getattr(world, "map", None), "routes", {}).get(key.subject_id)
    if key.subject_kind == "avatar":
        return world.avatar_manager.get_avatar(key.subject_id)
    if key.subject_kind == "sect":
        return next(
            (
                sect
                for sect in world.sect_context.active_sects
                if str(sect.id) == key.subject_id
            ),
            None,
        )
    return None

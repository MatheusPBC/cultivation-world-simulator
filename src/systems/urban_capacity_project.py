"""Deterministic lifecycle for grounded settlement-capacity projects."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.environment.urban_capacity_project import (
    UrbanCapacityProject,
    UrbanCapacityProjectStatus,
)
from src.classes.environment.region import CityRegion
from src.classes.environment.city_state import UrbanAsset
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.classes.regional_economy import QUANTITY_EPSILON
from src.i18n import t
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)


PROJECT_KIND = "settlement_capacity_expansion"
BASE_PROJECT_MONTHS = 3
MAX_PROJECT_MONTHS = 24
CAPACITY_GAIN_FRACTION = 0.20
WORK_CAPACITY_REFERENCE = 10.0
# One unit of the engine's construction material is required per capacity unit.
MATERIAL_PER_CAPACITY = 1.0


@dataclass(frozen=True)
class UrbanCapacityProjectPlan:
    housing_asset: UrbanAsset
    construction_work_asset: UrbanAsset
    construction_resource_id: str
    administrative_capacity: float
    construction_work_effective_capacity: float
    required_months: int
    capacity_increase: float
    material_required: float
    available_stock: float
    access: float


def _replace_project(region: CityRegion, replacement: UrbanCapacityProject) -> None:
    projects = tuple(
        replacement if project.id == replacement.id else project
        for project in region.city_state.capacity_projects
    )
    region.city_state = replace(region.city_state, capacity_projects=projects)


def _append_project(region: CityRegion, project: UrbanCapacityProject) -> None:
    region.city_state = replace(
        region.city_state,
        capacity_projects=(*region.city_state.capacity_projects, project),
    )


def _housing_asset(region: CityRegion):
    candidates = sorted(
        (
            asset
            for asset in region.city_state.assets
            if "housing" in asset.capability_ids
            and asset.capacity > 0
            and asset.integrity > 0
        ),
        key=lambda asset: (-asset.capacity, asset.id),
    )
    return candidates[0] if candidates else None


def _construction_work_asset(region: CityRegion):
    candidates = sorted(
        (
            asset
            for asset in region.city_state.assets
            if "construction_work" in asset.capability_ids
            and asset.capacity > 0
            and asset.integrity > 0
            and asset.quality > 0
        ),
        key=lambda asset: (-asset.capacity * asset.quality * asset.integrity, asset.id),
    )
    return candidates[0] if candidates else None


def _active_project(region: CityRegion) -> bool:
    return any(
        project.kind == PROJECT_KIND
        and project.status is not UrbanCapacityProjectStatus.COMPLETED
        for project in region.city_state.capacity_projects
    )


def _project_affordance(
    region: CityRegion,
    *,
    target_settlement_ratio: float,
) -> tuple[UrbanCapacityProjectPlan | None, str]:
    if not math.isfinite(target_settlement_ratio) or not 0 < target_settlement_ratio < 1:
        raise ValueError("target settlement ratio must be finite and between zero and one")

    housing = _housing_asset(region)
    work_asset = _construction_work_asset(region)
    if region.city_state.governance.administrative_capacity <= 0:
        return None, "administrative capacity is unavailable"
    if housing is None:
        return None, "grounded housing capacity is unavailable"
    if work_asset is None:
        return None, "grounded construction work capacity is unavailable"
    if _active_project(region):
        return None, "a settlement capacity project is already active"

    resource_id = region.economy.project_resources.get(PROJECT_KIND)
    if resource_id is None:
        return None, "construction resource mapping is unavailable"
    if resource_id not in region.economy.stocks:
        return None, "construction resource is undeclared"
    if resource_id not in region.economy.access or region.economy.access[resource_id] <= 0:
        return None, "construction resource access is unavailable"

    admin = min(1.0, float(region.city_state.governance.administrative_capacity))
    effective_work = float(work_asset.capacity * work_asset.quality * work_asset.integrity)
    work_rate = min(1.0, admin * effective_work / WORK_CAPACITY_REFERENCE)
    required_months = min(
        MAX_PROJECT_MONTHS,
        max(BASE_PROJECT_MONTHS, math.ceil(BASE_PROJECT_MONTHS / work_rate)),
    )
    baseline_increase = max(
        1.0,
        min(
            float(region.population_capacity) * CAPACITY_GAIN_FRACTION,
            float(housing.capacity) * CAPACITY_GAIN_FRACTION,
        ),
    )
    desired_capacity = float(region.population) / (target_settlement_ratio * 0.98)
    capacity_increase = max(
        baseline_increase,
        desired_capacity - float(region.population_capacity),
    )
    material_required = capacity_increase * MATERIAL_PER_CAPACITY
    available = region.economy.available_stock(resource_id)
    assert available is not None
    if material_required - available > QUANTITY_EPSILON:
        return None, "insufficient available construction material"

    return UrbanCapacityProjectPlan(
        housing_asset=housing,
        construction_work_asset=work_asset,
        construction_resource_id=resource_id,
        administrative_capacity=float(region.city_state.governance.administrative_capacity),
        construction_work_effective_capacity=effective_work,
        required_months=required_months,
        capacity_increase=capacity_increase,
        material_required=material_required,
        available_stock=available,
        access=float(region.economy.access[resource_id]),
    ), ""


def can_start_urban_capacity_project(
    region: CityRegion,
    *,
    target_settlement_ratio: float = 0.75,
) -> bool:
    plan, _ = _project_affordance(
        region,
        target_settlement_ratio=target_settlement_ratio,
    )
    return plan is not None


def _event(
    world: Any,
    region: CityRegion,
    *,
    event_type: str,
    fact_kind: FactKind,
    origin: CausalOrigin,
    project_id: str | None,
    causes: tuple[tuple[str, CausalRelation], ...],
    payload: dict[str, Any],
) -> Event:
    event = Event(
        world.month_stamp,
        t("Urban capacity project in {region}: {outcome}.", region=region.name, outcome=payload["outcome"]),
        event_type=event_type,
        render_key=event_type,
        render_params={
            "region_id": str(region.id),
            "project_id": project_id or "",
            "outcome": payload["outcome"],
        },
        fact_kind=fact_kind,
        causal_origin=origin,
        causal_payload={"deltas": [], "project_id": project_id, **payload},
    )
    event.causal_links.extend(
        CausalLink(event_id=event.id, cause_event_id=cause_id, relation=relation)
        for cause_id, relation in causes
        if cause_id
    )
    return event


def _attach_deltas(event: Event, deltas: list[StateDelta]) -> None:
    for delta in deltas:
        delta.event_id = event.id
    event.causal_payload["deltas"] = [delta.to_dict() for delta in deltas]


def start_urban_capacity_project(
    world: Any,
    region: CityRegion,
    *,
    decision_event_id: str,
    trigger_event_id: str,
    target_settlement_ratio: float = 0.75,
    invalidations: DomainInvalidationQueue | None = None,
) -> Event:
    plan, reason = _project_affordance(
        region,
        target_settlement_ratio=target_settlement_ratio,
    )
    if plan is None:
        return _event(
            world,
            region,
            event_type="urban_capacity_project_blocked",
            fact_kind=FactKind.OCCURRENCE,
            origin=CausalOrigin.ACTOR_DECISION,
            project_id=None,
            causes=(
                (decision_event_id, CausalRelation.MOTIVATED_BY),
                (trigger_event_id, CausalRelation.TRIGGERED_BY),
            ),
            payload={"outcome": "blocked", "reason": reason, "project_kind": PROJECT_KIND},
        )

    event = _event(
        world,
        region,
        event_type="urban_capacity_project_started",
        fact_kind=FactKind.STATE_TRANSITION,
        origin=CausalOrigin.ACTOR_DECISION,
        project_id=None,
        causes=(
            (decision_event_id, CausalRelation.MOTIVATED_BY),
            (trigger_event_id, CausalRelation.TRIGGERED_BY),
        ),
        payload={
            "outcome": "started",
            "project_kind": PROJECT_KIND,
            "housing_asset_id": plan.housing_asset.id,
            "construction_work_asset_id": plan.construction_work_asset.id,
            "construction_resource_id": plan.construction_resource_id,
            "required_months": plan.required_months,
            "capacity_increase": plan.capacity_increase,
            "material_required": plan.material_required,
            "target_settlement_ratio": target_settlement_ratio,
            "measurements": {
                "administrative_capacity": plan.administrative_capacity,
                "housing_capacity": float(plan.housing_asset.capacity),
                "housing_integrity": float(plan.housing_asset.integrity),
                "construction_work_effective_capacity": plan.construction_work_effective_capacity,
                "available_stock": plan.available_stock,
            },
            "execution": {
                "kind": PROJECT_KIND,
                "housing_asset_id": plan.housing_asset.id,
                "construction_work_asset_id": plan.construction_work_asset.id,
                "construction_resource_id": plan.construction_resource_id,
                "access": plan.access,
            },
        },
    )
    project = UrbanCapacityProject(
        id=event.id,
        kind=PROJECT_KIND,
        status=UrbanCapacityProjectStatus.RUNNING,
        housing_asset_id=plan.housing_asset.id,
        construction_resource_id=plan.construction_resource_id,
        construction_work_asset_id=plan.construction_work_asset.id,
        started_month=int(world.month_stamp),
        required_months=plan.required_months,
        completed_months=0,
        capacity_increase=plan.capacity_increase,
        material_required=plan.material_required,
        material_consumed=0.0,
        motivation_event_ids=tuple(dict.fromkeys((decision_event_id, trigger_event_id))),
        last_event_id=event.id,
    )
    # The reservation is the only economy mutation at start, and it happens
    # before the project is attached to CityState.
    previous_city_state = region.city_state
    region.economy.reserve_stock(
        project.id,
        plan.construction_resource_id,
        plan.material_required,
    )
    try:
        _append_project(region, project)
    except Exception:
        region.city_state = previous_city_state
        region.economy.release_reservation(project.id)
        raise
    event.render_params["project_id"] = project.id
    event.causal_payload["project_id"] = project.id
    _attach_deltas(event, [
        StateDelta(
            owner_kind="region", owner_id=str(region.id),
            aspect=f"resource_reservation:{project.id}:{plan.construction_resource_id}",
            before="0", after=str(plan.material_required), magnitude=plan.material_required,
        ),
        StateDelta(
            owner_kind="region", owner_id=str(region.id),
            aspect="urban_capacity_project_status",
            before="absent", after=UrbanCapacityProjectStatus.RUNNING.value, magnitude=1.0,
        ),
    ])
    if invalidations is not None:
        invalidations.mark(DomainInvalidation(
            layer=DomainInvalidationLayer.MECHANICAL,
            domain="city",
            target_kind="region",
            target_id=str(region.id),
            reason=DomainInvalidationReason.URBAN_PROJECT_CHANGED,
            source_event_ids=(event.id,),
            revision=event.id,
        ))
    return event


def _transition_event(
    world: Any,
    region: CityRegion,
    project: UrbanCapacityProject,
    *,
    event_type: str,
    outcome: str,
    payload: dict[str, Any] | None = None,
) -> Event:
    return _event(
        world,
        region,
        event_type=event_type,
        fact_kind=FactKind.STATE_TRANSITION,
        origin=CausalOrigin.DETERMINISTIC,
        project_id=project.id,
        causes=((project.last_event_id, CausalRelation.TRIGGERED_BY),),
        payload={"outcome": outcome, "project_kind": project.kind, **(payload or {})},
    )


def _construction_reservation_issue(
    region: CityRegion,
    project: UrbanCapacityProject,
    remaining_material: float,
) -> tuple[str, float | None] | None:
    reservations = region.economy.reservations.get(project.id)
    if not reservations:
        return "construction_reservation_missing", None

    resource_id = project.construction_resource_id
    if resource_id not in reservations:
        return "construction_reservation_resource_mismatch", None
    if any(reserved_resource != resource_id for reserved_resource in reservations):
        return "construction_reservation_extra_resources", None

    reserved_material = reservations[resource_id]
    try:
        reserved_material = float(reserved_material)
    except (TypeError, ValueError):
        return "construction_reservation_invalid_quantity", None
    if not math.isfinite(reserved_material) or reserved_material < 0:
        return "construction_reservation_invalid_quantity", None
    if not math.isclose(
        reserved_material,
        remaining_material,
        rel_tol=0.0,
        abs_tol=QUANTITY_EPSILON,
    ):
        return "construction_reservation_quantity_mismatch", reserved_material
    return None


def _stall_for_reservation_issue(
    world: Any,
    region: CityRegion,
    project: UrbanCapacityProject,
    *,
    current_month: int,
    issue: tuple[str, float | None],
) -> Event:
    reason, reserved_material = issue
    remaining_material = project.material_required - project.material_consumed
    event = _transition_event(
        world,
        region,
        project,
        event_type="urban_capacity_project_stalled",
        outcome="stalled",
        payload={
            "reason": reason,
            "measurements": {
                "material_required": project.material_required,
                "material_consumed": project.material_consumed,
                "material_remaining": remaining_material,
                "reserved_material": reserved_material,
            },
            "execution": {
                "kind": PROJECT_KIND,
                "construction_resource_id": project.construction_resource_id,
                "construction_work_asset_id": project.construction_work_asset_id,
            },
        },
    )
    stalled = replace(
        project,
        status=UrbanCapacityProjectStatus.STALLED,
        last_event_id=event.id,
        last_processed_month=current_month,
    )
    _replace_project(region, stalled)
    _attach_deltas(event, [StateDelta(
        owner_kind="region",
        owner_id=str(region.id),
        aspect="urban_capacity_project_status",
        before=project.status.value,
        after=stalled.status.value,
        magnitude=0.0,
    )])
    return event


def advance_urban_capacity_projects(
    world: Any,
    *,
    invalidations: DomainInvalidationQueue | None = None,
) -> list[Event]:
    events: list[Event] = []
    regions = sorted(
        (region for region in world.map.regions.values() if isinstance(region, CityRegion)),
        key=lambda region: str(region.id),
    )
    for region in regions:
        for project in tuple(region.city_state.capacity_projects):
            if project.status is UrbanCapacityProjectStatus.COMPLETED:
                continue
            current_month = int(world.month_stamp)
            if (
                project.last_processed_month is not None
                and current_month <= project.last_processed_month
            ):
                continue
            housing = next(
                (asset for asset in region.city_state.assets if asset.id == project.housing_asset_id),
                None,
            )
            work_asset = next(
                (asset for asset in region.city_state.assets if asset.id == project.construction_work_asset_id),
                None,
            )
            grounded = (
                region.city_state.governance.administrative_capacity > 0
                and housing is not None
                and "housing" in housing.capability_ids
                and housing.capacity > 0
                and housing.integrity > 0
                and work_asset is not None
                and "construction_work" in work_asset.capability_ids
                and work_asset.capacity > 0
                and work_asset.quality > 0
                and work_asset.integrity > 0
            )
            if not grounded:
                if project.status is UrbanCapacityProjectStatus.STALLED:
                    continue
                event = _transition_event(
                    world, region, project,
                    event_type="urban_capacity_project_stalled",
                    outcome="stalled",
                    payload={
                        "measurements": {
                            "administrative_capacity": float(
                                region.city_state.governance.administrative_capacity
                            ),
                        },
                        "execution": {
                            "kind": PROJECT_KIND,
                            "housing_asset_id": project.housing_asset_id,
                            "construction_work_asset_id": project.construction_work_asset_id,
                        },
                    },
                )
                replacement = replace(
                    project,
                    status=UrbanCapacityProjectStatus.STALLED,
                    last_event_id=event.id,
                    last_processed_month=current_month,
                )
                _replace_project(region, replacement)
                _attach_deltas(event, [StateDelta(
                    owner_kind="region", owner_id=str(region.id),
                    aspect="urban_capacity_project_status",
                    before=project.status.value, after=replacement.status.value,
                    magnitude=0.0,
                )])
                events.append(event)
                continue

            current = project
            remaining_material = current.material_required - current.material_consumed
            reservation_issue = _construction_reservation_issue(
                region,
                current,
                remaining_material,
            )
            if reservation_issue is not None:
                if current.status is UrbanCapacityProjectStatus.STALLED:
                    continue
                events.append(_stall_for_reservation_issue(
                    world,
                    region,
                    current,
                    current_month=current_month,
                    issue=reservation_issue,
                ))
                continue

            if current.status is UrbanCapacityProjectStatus.STALLED:
                resumed = _transition_event(
                    world, region, current,
                    event_type="urban_capacity_project_resumed",
                    outcome="resumed",
                )
                current = replace(
                    current,
                    status=UrbanCapacityProjectStatus.RUNNING,
                    last_event_id=resumed.id,
                )
                _replace_project(region, current)
                _attach_deltas(resumed, [StateDelta(
                    owner_kind="region", owner_id=str(region.id),
                    aspect="urban_capacity_project_status",
                    before=UrbanCapacityProjectStatus.STALLED.value,
                    after=UrbanCapacityProjectStatus.RUNNING.value,
                    magnitude=0.0,
                )])
                events.append(resumed)

            assert work_asset is not None
            tranche = (
                remaining_material
                if current.completed_months + 1 == current.required_months
                else current.material_required / current.required_months
            )
            tranche = min(remaining_material, tranche)
            stock_before = float(region.economy.stocks[ current.construction_resource_id ])
            reserved_before = region.economy.reservations[current.id][current.construction_resource_id]
            region.economy.consume_reserved_stock(
                current.id,
                current.construction_resource_id,
                tranche,
            )
            stock_after = float(region.economy.stocks[current.construction_resource_id])
            reserved_after = region.economy.reservations.get(current.id, {}).get(
                current.construction_resource_id,
                0.0,
            )
            progressed = _transition_event(
                world, region, current,
                event_type="urban_capacity_project_progressed",
                outcome="progressed",
                payload={
                    "measurements": {
                        "administrative_capacity": float(
                            region.city_state.governance.administrative_capacity
                        ),
                        "construction_work_effective_capacity": float(
                            work_asset.capacity * work_asset.quality * work_asset.integrity
                        ),
                        "stock_before": stock_before,
                        "stock_after": stock_after,
                        "reservation_before": reserved_before,
                        "reservation_after": reserved_after,
                    },
                    "execution": {
                        "kind": PROJECT_KIND,
                        "construction_resource_id": current.construction_resource_id,
                        "construction_work_asset_id": current.construction_work_asset_id,
                    },
                    "material_delta": tranche,
                },
            )
            next_completed_months = current.completed_months + 1
            is_complete = next_completed_months == current.required_months
            next_material_consumed = (
                current.material_required
                if is_complete
                else current.material_consumed + tranche
            )
            advanced = replace(
                current,
                status=(
                    UrbanCapacityProjectStatus.COMPLETED
                    if is_complete
                    else UrbanCapacityProjectStatus.RUNNING
                ),
                completed_months=next_completed_months,
                material_consumed=next_material_consumed,
                last_event_id=progressed.id,
                last_processed_month=current_month,
                completed_month=current_month if is_complete else None,
            )
            _replace_project(region, advanced)
            _attach_deltas(progressed, [
                StateDelta(
                    owner_kind="region", owner_id=str(region.id),
                    aspect=f"resource_stock:{current.construction_resource_id}",
                    before=str(stock_before), after=str(stock_after), magnitude=-tranche,
                ),
                StateDelta(
                    owner_kind="region", owner_id=str(region.id),
                    aspect=f"resource_reservation:{current.id}:{current.construction_resource_id}",
                    before=str(reserved_before), after=str(reserved_after), magnitude=-tranche,
                ),
                StateDelta(
                    owner_kind="region", owner_id=str(region.id),
                    aspect="urban_capacity_project_material",
                    before=str(current.material_consumed),
                    after=str(advanced.material_consumed), magnitude=tranche,
                ),
                StateDelta(
                    owner_kind="region", owner_id=str(region.id),
                    aspect="urban_capacity_project_progress",
                    before=str(current.completed_months),
                    after=str(advanced.completed_months), magnitude=1.0,
                ),
            ])
            events.append(progressed)

            if invalidations is not None:
                invalidations.mark(DomainInvalidation(
                    layer=DomainInvalidationLayer.MECHANICAL,
                    domain="economy",
                    target_kind="region",
                    target_id=str(region.id),
                    reason=DomainInvalidationReason.RESOURCE_STOCK_CHANGED,
                    source_event_ids=(progressed.id,),
                    revision=progressed.id,
                ))

            if not is_complete:
                continue
            before_capacity = float(region.population_capacity)
            region.increase_population_capacity(advanced.capacity_increase)
            completed = _transition_event(
                world, region, advanced,
                event_type="urban_capacity_project_completed",
                outcome="completed",
            )
            completed.causal_links.append(CausalLink(
                event_id=completed.id,
                cause_event_id=project.id,
                relation=CausalRelation.CONTRIBUTED_TO,
            ))
            finished = replace(advanced, last_event_id=completed.id)
            _replace_project(region, finished)
            _attach_deltas(completed, [
                StateDelta(
                    owner_kind="region", owner_id=str(region.id),
                    aspect="population_capacity",
                    before=str(before_capacity), after=str(region.population_capacity),
                    magnitude=advanced.capacity_increase,
                ),
                StateDelta(
                    owner_kind="region", owner_id=str(region.id),
                    aspect="urban_capacity_project_status",
                    before=UrbanCapacityProjectStatus.RUNNING.value,
                    after=UrbanCapacityProjectStatus.COMPLETED.value,
                    magnitude=0.0,
                ),
            ])
            events.append(completed)
            if invalidations is not None:
                invalidations.mark(DomainInvalidation(
                    layer=DomainInvalidationLayer.MECHANICAL,
                    domain="city",
                    target_kind="region",
                    target_id=str(region.id),
                    reason=DomainInvalidationReason.POPULATION_CAPACITY_CHANGED,
                    source_event_ids=(completed.id,),
                    revision=completed.id,
                ))
    return events


__all__ = [
    "CAPACITY_GAIN_FRACTION",
    "MAX_PROJECT_MONTHS",
    "PROJECT_KIND",
    "advance_urban_capacity_projects",
    "can_start_urban_capacity_project",
    "start_urban_capacity_project",
]

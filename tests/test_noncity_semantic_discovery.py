from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.environment.region import CultivateRegion, NormalRegion
from src.classes.environment.tile import TileType
from src.classes.core.world import World
from src.classes.mechanical_language import MetricKey, PrimitiveDimension
from src.systems.semantic_world import service as semantic_service
from src.systems.semantic_world.service import evaluate_semantic_world
from src.systems.time import MonthStamp, Month, Year, create_month_stamp
from src.utils.llm.exceptions import ProviderCallError, ProviderFailureKind


CAPABILITY_ID = "regional_transit"


def _build_world(
    *,
    normal_integrity: float | None = 0.9,
    cultivate_integrity: float | None = 0.9,
) -> tuple[World, NormalRegion, CultivateRegion]:
    game_map = Map(width=2, height=1)
    for x in range(2):
        game_map.create_tile(x, 0, TileType.PLAIN)

    normal = NormalRegion(id=101, name="Várzea", desc="", cors=[(0, 0)])
    cultivate = CultivateRegion(id=202, name="Caverna", desc="", cors=[(1, 0)])
    game_map.regions = {normal.id: normal, cultivate.id: cultivate}
    game_map.region_cors = {
        normal.id: list(normal.cors),
        cultivate.id: list(cultivate.cors),
    }
    sites = []
    for region, integrity, suffix in (
        (normal, normal_integrity, "normal"),
        (cultivate, cultivate_integrity, "cultivate"),
    ):
        if integrity is not None:
            sites.append(
                InfrastructureSite(
                    id=f"site:{suffix}-gate",
                    kind="regional_gate",
                    name=f"Portão {suffix}",
                    cell_refs=region.cors,
                    region_ids=(region.id,),
                    capability_ids=(CAPABILITY_ID,),
                    integrity=integrity,
                )
            )
    game_map.set_infrastructure_sites(sites)
    return (
        World(
            map=game_map,
            month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        ),
        normal,
        cultivate,
    )


def _site_capacity_proposal() -> dict:
    return {
        "concepts": [
            {
                "id": "regional_site_capacity",
                "label": "regional site capacity",
                "concept_kind": "derived_metric",
            }
        ],
        "derived_metrics": [
            {
                "id": "regional_site_capacity",
                "concept_id": "regional_site_capacity",
                "dimension": "capacity",
                "target_kind": "region",
                "expression": {
                    "op": "metric",
                    "dimension": "capacity",
                    "concept_id": CAPABILITY_ID,
                    "qualifiers": {"kind": "infrastructure_site"},
                },
                "unit": "site_equivalents",
            }
        ],
        "conditions": [],
        "mechanic_proposals": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("region_kind", ["normal", "cultivate"])
async def test_noncity_region_with_measurable_site_can_originate_discovery(region_kind):
    world, normal, cultivate = _build_world(
        normal_integrity=0.9 if region_kind == "normal" else None,
        cultivate_integrity=0.9 if region_kind == "cultivate" else None,
    )
    llm = AsyncMock(return_value=_site_capacity_proposal())
    world.run_config_snapshot = {"semantic_discovery_budget_per_month": 1}

    await evaluate_semantic_world(world, llm_call=llm)

    source = normal if region_kind == "normal" else cultivate
    assert llm.await_count == 1
    infos = llm.await_args.args[2]
    assert infos["target"] == {
        "kind": "region",
        "id": str(source.id),
        "name": source.name,
        "region_type": region_kind,
    }
    assert any(
        metric["concept_id"] == CAPABILITY_ID
        and metric["qualifiers"] == {"kind": "infrastructure_site"}
        for metric in infos["available_metrics"]
    )
    assert "regional_site_capacity" in world.mechanical_language.derived_definitions


@pytest.mark.asyncio
async def test_noncity_discovery_respects_budget_and_retry_window():
    world, normal, _ = _build_world(cultivate_integrity=None)
    world.map.regions = {normal.id: normal}
    world.map.region_cors = {normal.id: list(normal.cors)}
    world.run_config_snapshot = {
        "semantic_discovery_budget_per_month": 1,
        "semantic_discovery_retry_after_months": 2,
    }
    failing = AsyncMock(
        side_effect=ProviderCallError(
            ProviderFailureKind.NETWORK,
            "provider failure",
        )
    )

    await evaluate_semantic_world(world, llm_call=failing)
    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
    await evaluate_semantic_world(world, llm_call=failing)
    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
    await evaluate_semantic_world(world, llm_call=failing)

    assert failing.await_count == 2


@pytest.mark.asyncio
async def test_empty_or_unknown_noncity_surface_is_not_discovery_candidate():
    world, normal, _ = _build_world(normal_integrity=None, cultivate_integrity=None)
    world.map.regions = {normal.id: normal}
    world.map.region_cors = {normal.id: list(normal.cors)}
    llm = AsyncMock(side_effect=AssertionError("no measurable surface"))
    world.run_config_snapshot = {"semantic_discovery_budget_per_month": 2}

    await evaluate_semantic_world(world, llm_call=llm)

    assert llm.await_count == 0
    assert world.mechanical_language.derived_definitions == {}


@pytest.mark.asyncio
async def test_unmeasurable_noncity_key_is_not_discovery_candidate(monkeypatch):
    world, normal, _ = _build_world(normal_integrity=None, cultivate_integrity=None)
    world.map.regions = {normal.id: normal}
    world.map.region_cors = {normal.id: list(normal.cors)}
    unknown_key = MetricKey(
        PrimitiveDimension.CAPACITY,
        "region",
        str(normal.id),
        "missing_transit",
        qualifiers=(("kind", "infrastructure_site"),),
    )
    monkeypatch.setattr(
        semantic_service,
        "available_metric_keys",
        lambda _world, _region: [unknown_key],
    )
    llm = AsyncMock(side_effect=AssertionError("unknown input reached discovery"))

    await evaluate_semantic_world(world, llm_call=llm)

    assert llm.await_count == 0


@pytest.mark.asyncio
async def test_noncity_discovered_definition_is_reused_without_second_llm_call():
    world, normal, cultivate = _build_world()
    proposal = _site_capacity_proposal()
    llm = AsyncMock(return_value=proposal)
    world.run_config_snapshot = {"semantic_discovery_budget_per_month": 1}

    await evaluate_semantic_world(world, llm_call=llm)
    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
    world.run_config_snapshot = {"semantic_discovery_budget_per_month": 0}
    await evaluate_semantic_world(world, llm_call=llm)

    assert llm.await_count == 1
    definition = world.mechanical_language.derived_definitions["regional_site_capacity"]
    assert definition.reuse_contexts == (
        f"region:{normal.id}",
        f"region:{cultivate.id}",
    )


@pytest.mark.asyncio
async def test_test_mode_does_not_call_real_provider_for_noncity_discovery():
    world, _, _ = _build_world(cultivate_integrity=None)
    world.run_config_snapshot = {
        "test_mode": True,
        "semantic_discovery_budget_per_month": 1,
    }
    provider = AsyncMock(side_effect=AssertionError("test mode must not call provider"))

    await evaluate_semantic_world(world, llm_call=provider)

    assert provider.await_count == 0
    assert (
        "infrastructure_site_regional_transit_capacity"
        in world.mechanical_language.derived_definitions
    )

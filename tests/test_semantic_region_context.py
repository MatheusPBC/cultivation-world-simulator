from src.classes.environment.city_state import (
    CityDistrict,
    CityState,
    UrbanAsset,
    UrbanPopulationGroup,
    UrbanServiceDemand,
)
from src.classes.environment.region import CityRegion, NormalRegion
from src.classes.mechanical_language import (
    Concept,
    ConceptLifecycle,
    ConditionDefinition,
    ConditionInstance,
    DerivedMetricDefinition,
    EntityRef,
    GroundingStatus,
    MechanicalLanguageState,
    PrimitiveDimension,
)
from src.server.services.game_queries import get_detail
from src.systems.semantic_world.context import (
    build_avatar_semantic_context,
    build_region_semantic_context,
    region_semantic_relevance,
)


def _seed_definition(world):
    state = world.mechanical_language
    state.concepts["settlement_density_pressure"] = Concept(
        id="settlement_density_pressure",
        label="settlement density pressure",
        concept_kind="derived_metric",
        grounding_status=GroundingStatus.GROUNDED,
        lifecycle=ConceptLifecycle.ACTIVE,
    )
    state.derived_definitions["settlement_density_pressure"] = DerivedMetricDefinition(
        id="settlement_density_pressure",
        concept_id="settlement_density_pressure",
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={
            "op": "divide",
            "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
            "right": {"op": "metric", "dimension": "capacity", "concept_id": "settlement"},
        },
        unit="ratio",
        created_month=1,
        lifecycle=ConceptLifecycle.ACTIVE,
    )
    state.condition_definitions["overcrowded_settlement"] = ConditionDefinition(
        id="overcrowded_settlement",
        concept_id="overcrowded_settlement",
        target_kind="region",
        metric_definition_id="settlement_density_pressure",
        activate_above=0.85,
        resolve_below=0.75,
        activate_after_months=2,
        resolve_after_months=2,
        created_month=1,
        lifecycle=ConceptLifecycle.ACTIVE,
    )


def test_condition_instance_keeps_causal_origin_and_expires_by_month():
    region = NormalRegion(id=1, name="Vale", desc="", cors=[(0, 0)])
    condition = ConditionInstance(
        id="formation-condition",
        definition_id="formation:healing_formation",
        target_kind="region",
        target_id="1",
        label="healing_formation",
        intensity=0.8,
        started_month=10,
        cause_event_id="event-formation",
        expires_month=16,
    )
    state = MechanicalLanguageState()
    state.add_condition_instance(condition)

    assert state.get_active_conditions(EntityRef("region", "1"), 15) == [condition]
    assert state.get_active_conditions(EntityRef("region", "1"), 16) == []
    assert "conditions" not in region.to_runtime_dict()


def test_region_semantic_context_resolves_primitives_derived_metrics_and_sources(base_world):
    city = CityRegion(id=2, name="Cidade Alta", desc="", cors=[(0, 0)], population=95, population_capacity=100)
    base_world.map.regions[city.id] = city
    _seed_definition(base_world)
    base_world.mechanical_language.add_condition_instance(ConditionInstance(
        id="condition-1",
        definition_id="overcrowded_settlement",
        target_kind="region",
        target_id="2",
        label="overcrowded settlement",
        intensity=0.8,
        started_month=12,
        cause_event_id="event-pressure",
    ))

    context = build_region_semantic_context(base_world, city)

    assert {reading["key"]["dimension"] for reading in context["readings"]} >= {"load", "capacity", "risk"}
    assert context["conditions"][0]["cause_event_id"] == "event-pressure"
    assert context["definitions"][0]["id"] == "settlement_density_pressure"
    assert context["spiritual_ecology"]["grounding_status"] == "unknown"
    assert context["collective_health"]["grounding_status"] == "grounded"
    assert context["collective_health"]["living_avatar_count"]["value"] == 0
    assert region_semantic_relevance(base_world, city) > 0.9


def test_avatar_context_uses_the_same_semantic_view(base_world, dummy_avatar):
    city = CityRegion(id=3, name="Bosque Urbano", desc="", cors=[(0, 0)], population=90, population_capacity=100)
    dummy_avatar.tile.region = city
    base_world.map.regions[city.id] = city
    _seed_definition(base_world)

    context = build_avatar_semantic_context(dummy_avatar)

    assert "Bosque Urbano" in context
    assert "settlement_density_pressure" in context
    assert "0.900" in context


def test_avatar_context_identifies_group_specific_urban_access(base_world, dummy_avatar):
    city = CityRegion(
        id=5,
        name="Cidade Desigual",
        desc="",
        cors=[(0, 0)],
        population=100,
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
            assets=(
                UrbanAsset("waterworks", "core", ("clean_water",), 50, 1.0, 1.0),
            ),
            service_demands=(UrbanServiceDemand("clean_water", 1.0),),
            population_groups=(
                UrbanPopulationGroup("commoners", 0.8, {"clean_water": 0.5}),
                UrbanPopulationGroup("cultivators", 0.2, {"clean_water": 2.0}),
            ),
        ),
    )
    dummy_avatar.tile.region = city
    base_world.map.regions[city.id] = city

    structured = build_region_semantic_context(base_world, city)
    context = build_avatar_semantic_context(dummy_avatar)

    group_ids = {
        reading["key"].get("group_id")
        for reading in structured["readings"]
        if reading["key"]["dimension"] == "access"
        and reading["key"]["concept_id"] == "clean_water"
    }
    assert group_ids == {None, "commoners", "cultivators"}
    assert "access(clean_water)[commoners]" in context
    assert "access(clean_water)[cultivators]" in context


def test_region_detail_exposes_semantic_context_without_parallel_pressure(base_world):
    city = CityRegion(id=4, name="Cidade Alta", desc="", cors=[(0, 0)], population=90, population_capacity=100)
    base_world.map.regions[city.id] = city
    _seed_definition(base_world)

    detail = get_detail(
        {"world": base_world},
        target_type="region",
        target_id=str(city.id),
        sects_by_id={},
        build_sect_detail=lambda *_: {},
        language_manager=None,
        resolve_avatar_pic_id=lambda _: 0,
    )

    assert detail["semantic_context"]["readings"]
    assert detail["city_state"]["districts"]
    assert "spiritual_ecology" in detail["semantic_context"]
    assert "collective_health" in detail["semantic_context"]
    assert "regional_pressure" not in detail
    assert "regional_capabilities" not in detail

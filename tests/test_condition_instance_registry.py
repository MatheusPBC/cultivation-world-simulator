from src.classes.environment.region import CityRegion
from src.classes.mechanical_language import (
    ConditionInstance,
    EntityRef,
    MechanicalLanguageState,
)
from src.systems.semantic_world.context import build_region_semantic_context


def _condition(
    condition_id: str,
    *,
    target_kind: str,
    target_id: str,
    resolved_month: int | None = None,
) -> ConditionInstance:
    return ConditionInstance(
        id=condition_id,
        definition_id="condition-definition",
        target_kind=target_kind,
        target_id=target_id,
        label=condition_id,
        intensity=0.7,
        started_month=1,
        cause_event_id="source-event",
        resolved_month=resolved_month,
    )


def test_condition_instances_are_owned_by_one_world_registry_and_filtered_by_entity_ref():
    state = MechanicalLanguageState()
    region_condition = _condition(
        "region-condition",
        target_kind="region",
        target_id="301",
    )
    route_condition = _condition(
        "route-condition",
        target_kind="route",
        target_id="route-301-302",
    )

    state.add_condition_instance(region_condition)
    state.add_condition_instance(route_condition)

    assert state.condition_instances == {
        region_condition.id: region_condition,
        route_condition.id: route_condition,
    }
    assert state.get_conditions_for_target(EntityRef("region", "301")) == [region_condition]
    assert state.get_conditions_for_target(EntityRef("route", "route-301-302")) == [route_condition]
    assert state.to_public_dict(EntityRef("route", "route-301-302"))["condition_instances"] == [
        route_condition.to_dict()
    ]
    assert not hasattr(CityRegion(id=301, name="City", desc="", cors=[]), "conditions")


def test_condition_registry_round_trips_region_and_non_region_targets_as_ids_and_json():
    state = MechanicalLanguageState()
    region_condition = _condition(
        "region-condition",
        target_kind="region",
        target_id="301",
    )
    avatar_condition = _condition(
        "avatar-condition",
        target_kind="avatar",
        target_id="avatar-7",
        resolved_month=4,
    )
    state.add_condition_instance(region_condition)
    state.add_condition_instance(avatar_condition)

    payload = state.to_dict()
    restored = MechanicalLanguageState.from_dict(payload)

    assert set(payload["condition_instances"]) == {"region-condition", "avatar-condition"}
    assert restored.condition_instances == {
        region_condition.id: region_condition,
        avatar_condition.id: avatar_condition,
    }
    assert restored.get_active_conditions(EntityRef("region", "301"), 2) == [region_condition]
    assert restored.get_active_conditions(EntityRef("avatar", "avatar-7"), 4) == []


def test_region_context_reads_only_conditions_targeting_that_region(base_world):
    city = CityRegion(id=301, name="City", desc="", cors=[(0, 0)])
    base_world.map.regions[city.id] = city
    regional = _condition(
        "regional-condition",
        target_kind="region",
        target_id="301",
    )
    route = _condition(
        "route-condition",
        target_kind="route",
        target_id="route-301-302",
    )
    base_world.mechanical_language.add_condition_instance(regional)
    base_world.mechanical_language.add_condition_instance(route)

    context = build_region_semantic_context(base_world, city)

    assert context["conditions"] == [regional.to_dict()]

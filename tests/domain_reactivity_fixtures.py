from src.classes.core.dynasty import Dynasty
from src.classes.environment.city_state import (
    CityDistrict,
    CityGovernance,
    CityState,
    UrbanAsset,
)
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import (
    ConditionDefinition,
    ConditionInstance,
    DerivedMetricDefinition,
    PrimitiveDimension,
)


async def select_first_affordance(_task, _template, context, **_kwargs):
    return {
        "decision": "act",
        "reason": "Select the first grounded engine option.",
        "selected_affordance_id": context["affordances"][0]["id"],
    }


def setup_government_condition(world, *, controller_id="1", integrity=0.5):
    world.dynasty = Dynasty(
        id=1,
        name="Test Dynasty",
        desc="",
        current_emperor_id="emperor-1",
    )
    city = CityRegion(
        id=301,
        name="Border City",
        desc="",
        cors=[(0, 0)],
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
            assets=(
                UrbanAsset("clinic", "core", ("healing",), 10, 0.4, integrity),
            ),
            governance=CityGovernance("dynasty", controller_id, 0.8),
        ),
    )
    world.map.regions[city.id] = city
    world.mechanical_language.derived_definitions["clinic-risk-metric"] = (
        DerivedMetricDefinition(
            id="clinic-risk-metric",
            concept_id="clinic-risk-metric",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={
                "op": "subtract",
                "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
                "right": {
                    "op": "metric",
                    "dimension": "quality",
                    "concept_id": "healing",
                },
            },
            unit="ratio",
            created_month=int(world.month_stamp),
        )
    )
    world.mechanical_language.condition_definitions["clinic-risk"] = (
        ConditionDefinition(
            id="clinic-risk",
            concept_id="clinic-risk",
            target_kind="region",
            metric_definition_id="clinic-risk-metric",
            activate_above=0.7,
            resolve_below=0.5,
            activate_after_months=1,
            resolve_after_months=1,
            created_month=int(world.month_stamp),
        )
    )
    trigger = Event(
        world.month_stamp,
        "The clinic became a regional risk.",
        event_type="semantic_condition_activated",
        fact_kind=FactKind.DERIVED_CONDITION,
        render_params={
            "region_id": "301",
            "condition_definition_id": "clinic-risk",
        },
        id="government-trigger",
    )
    condition = ConditionInstance(
        id="government-condition",
        definition_id="clinic-risk",
        target_kind="region",
        target_id="301",
        label="clinic risk",
        intensity=0.8,
        started_month=int(world.month_stamp),
        cause_event_id=trigger.id,
        source_readings=(
            {
                "key": {"dimension": "quality", "concept_id": "healing"},
                "value": 0.2,
            },
        ),
    )
    world.mechanical_language.add_condition_instance(condition)
    # A governed city needs an office that can actually act: the runtime now
    # refuses urban work when the sovereign's office has no living holder, so
    # a fixture that only names a `current_emperor_id` would describe a
    # government nobody can speak for. Registered for real, then bootstrapped.
    _register_sovereign(world)
    return city, trigger, condition


def _register_sovereign(world) -> None:
    """Give the dynasty a living, registered holder and bootstrap authority."""
    from src.classes.age import Age
    from src.classes.alignment import Alignment
    from src.classes.core.avatar import Avatar, Gender
    from src.classes.root import Root
    from src.systems.cultivation import Realm
    from src.systems.institution_bootstrap import bootstrap_institutional_authority
    from src.systems.time import Month, Year, create_month_stamp

    existing = world.avatar_manager.get_avatar(
        str(world.dynasty.current_emperor_id)
    )
    if existing is None:
        avatar = Avatar(
            world=world,
            name="Test Sovereign",
            id=str(world.dynasty.current_emperor_id),
            birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
            age=Age(30, Realm.Qi_Refinement, innate_max_lifespan=80),
            gender=Gender.MALE,
            pos_x=0,
            pos_y=0,
            root=Root.GOLD,
            personas=[],
            alignment=Alignment.RIGHTEOUS,
        )
        avatar.personas = []
        avatar.technique = None
        world.avatar_manager.register_avatar(avatar)
    bootstrap_institutional_authority(world)

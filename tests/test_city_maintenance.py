from src.classes.environment.city_state import CityDistrict, CityGovernance, CityState, UrbanAsset
from src.classes.environment.region import CityRegion
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationLayer, DomainInvalidationReason, DomainInvalidationQueue
from src.systems.city_maintenance import MAX_MAINTENANCE_IMPROVEMENT, execute_urban_maintenance


def _city(admin=0.8, integrity=0.5):
    return CityRegion(
        id=301,
        name="Border City",
        desc="",
        cors=[(0, 0)],
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
            assets=(UrbanAsset("clinic", "core", ("healing",), 10, 0.4, integrity),),
            governance=CityGovernance("dynasty", "house-1", admin),
        ),
    )


def test_maintenance_replaces_frozen_asset_with_bounded_integrity_improvement(base_world):
    city = _city(admin=0.6, integrity=0.5)
    queue = DomainInvalidationQueue()

    event = execute_urban_maintenance(
        base_world,
        city,
        capability_id="healing",
        decision_event_id="decision-1",
        trigger_event_id="trigger-1",
        invalidations=queue,
    )

    asset = city.city_state.assets[0]
    assert event.event_type == "city_maintenance_completed"
    assert asset.integrity == 0.56
    assert asset.quality == 0.4
    assert event.causal_payload["deltas"][0]["event_id"] == event.id
    assert event.causal_payload["deltas"][0]["magnitude"] <= MAX_MAINTENANCE_IMPROVEMENT
    assert queue.drain()[-1].reason is DomainInvalidationReason.INFRASTRUCTURE_CHANGED
    assert queue.drain(layer=DomainInvalidationLayer.MECHANICAL) == []


def test_maintenance_is_blocked_without_capability_or_administration(base_world):
    for capability, admin in (("missing", 0.8), ("healing", 0.0)):
        city = _city(admin=admin)
        before = city.city_state.assets[0]
        event = execute_urban_maintenance(
            base_world,
            city,
            capability_id=capability,
            decision_event_id="decision-1",
            trigger_event_id="trigger-1",
        )
        assert event.event_type == "city_maintenance_blocked"
        assert city.city_state.assets[0] == before
        assert event.causal_payload["deltas"] == []

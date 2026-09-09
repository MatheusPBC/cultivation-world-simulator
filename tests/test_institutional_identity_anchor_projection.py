from src.classes.event import Event
from src.classes.mechanical_language import EntityRef
from src.classes.environment.sect_region import SectRegion
from src.server.assemblers.institutional_chain import build_institutional_chain
from src.server.services.game_queries import get_event_causal_detail
from src.systems.institution_bootstrap import (
    bootstrap_institutional_authority,
    establish_genesis_identity_anchors,
)


def _anchor_events(world):
    bootstrap_institutional_authority(world)
    region = SectRegion(
        id=901, name="Azure Headquarters", desc="", cors=[(0, 0)],
        sect_id=7, sect_name="Azure Sect",
    )
    world.map.regions[region.id] = region
    institution = world.institutional_authority.get_institution_for_owner(
        EntityRef("sect", "7")
    )
    assert institution is not None
    produced = establish_genesis_identity_anchors(world)
    assert len(produced) == 1
    event = produced[0]
    anchor = world.institutional_authority.identity_anchors[
        event.render_params["anchor_id"]
    ]
    return institution, region, anchor, event


def test_canonical_headquarters_anchor_projects_to_sect_and_why(base_world):
    institution, region, anchor, event = _anchor_events(base_world)
    chain = build_institutional_chain(
        base_world, owner_kind="sect", owner_id="7"
    )
    rows = {item["event_id"]: item for item in chain["events"]}
    assert event.id in rows
    assert rows[event.id]["source_event_ids"] == []
    assert institution.id in {item["id"] for item in chain["institutions"]}
    assert f"inst:city:{region.id}" not in {item["id"] for item in chain["institutions"]}
    assert anchor.id == f"anchor:{institution.id}:headquarters:region:{region.id}"
    def serialize(events, **_kwargs):
        return [item.to_dict() for item in events]

    why = get_event_causal_detail(
        {"world": base_world},
        serialize_events_for_client=serialize,
        event_id=event.id,
    )
    assert why["event"]["id"] == event.id
    assert why["causes"] == []
    assert why["event"]["render_params"]["premise"] == "world_genesis"
    assert why["deltas"][0]["aspect"] == f"identity_anchor:{anchor.id}"
    del base_world.map.regions[region.id]
    after_region_cleanup = build_institutional_chain(
        base_world, owner_kind="sect", owner_id="7"
    )
    assert event.id in {item["event_id"] for item in after_region_cleanup["events"]}


def test_anchor_projection_rejects_spoofed_region_and_missing_evidence(base_world):
    _institution, region, anchor, event = _anchor_events(base_world)
    spoof = Event.from_dict({
        **event.to_dict(),
        "id": "sect-anchor-spoof",
        "render_params": {**event.render_params, "region_id": "902"},
    })
    missing = Event.from_dict({
        **event.to_dict(),
        "id": "sect-anchor-missing-evidence",
        "causal_payload": {"deltas": [{
            "event_id": "sect-anchor-missing-evidence",
            "owner_kind": "institutional_authority",
            "owner_id": anchor.institution_id,
            "aspect": f"identity_anchor:{anchor.id}",
            "before": "absent",
            "after": "established",
        }]},
    })
    base_world.event_manager.add_event(spoof)
    base_world.event_manager.add_event(missing)
    chain = build_institutional_chain(
        base_world, owner_kind="sect", owner_id="7"
    )
    row_ids = {item["event_id"] for item in chain["events"]}
    assert event.id in row_ids
    assert spoof.id not in row_ids
    assert missing.id not in row_ids

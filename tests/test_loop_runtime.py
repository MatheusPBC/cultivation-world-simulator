from types import SimpleNamespace

from src.server.loop_runtime import (
    _serialize_route_updates,
    build_auto_save_toast,
    build_avatar_updates,
    build_tick_state,
    should_trigger_auto_save,
)
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.environment.route import Route


def test_route_updates_are_derived_from_pending_site_updates():
    game_map = Map(1, 1)
    game_map.set_routes([Route("route:1", (1, 2), "road", 10, 0.8, True)])
    site = InfrastructureSite(
        id="bridge:1",
        kind="bridge",
        name="Bridge",
        cell_refs=((0, 0),),
        region_ids=(1, 2),
        route_ids=("route:1",),
    )
    game_map.infrastructure_sites = {site.id: site}
    game_map.update_infrastructure_site_runtime(site.id, integrity=0.5)

    assert _serialize_route_updates(SimpleNamespace(map=game_map)) == [{
        "id": "route:1",
        "operational_capacity": 4.0,
        "dependency_site_ids": ["bridge:1"],
    }]


def test_build_avatar_updates_includes_birth_death_and_position_deltas():
    born_avatar = SimpleNamespace(
        id="born-1",
        name="Newborn",
        pos_x=3,
        pos_y=4,
        gender=SimpleNamespace(value="male"),
        cultivation_progress=SimpleNamespace(realm=SimpleNamespace(value="QI_REFINEMENT")),
        current_action_name="行走",
    )
    dead_avatar = SimpleNamespace(id="dead-1", name="Ancestor")
    living_avatar = SimpleNamespace(
        id="live-1",
        pos_x=7,
        pos_y=8,
        current_action_name="Cultivar",
        gender=SimpleNamespace(value="female"),
        cultivation_progress=SimpleNamespace(realm=SimpleNamespace(value="FOUNDATION_ESTABLISHMENT")),
    )

    avatar_manager = SimpleNamespace(
        avatars={"born-1": born_avatar},
        pop_newly_born=lambda: ["born-1"],
        pop_newly_dead=lambda: ["dead-1"],
        get_avatar=lambda avatar_id: dead_avatar if avatar_id == "dead-1" else None,
        get_living_avatars=lambda: [born_avatar, living_avatar],
    )
    world = SimpleNamespace(avatar_manager=avatar_manager)

    updates = build_avatar_updates(
        world=world,
        resolve_avatar_pic_id=lambda avatar: 99 if avatar.id == "born-1" else 1,
        resolve_avatar_action_emoji=lambda avatar: "🚶" if avatar.id == "born-1" else "✨",
    )

    assert updates[0]["id"] == "born-1"
    assert updates[0]["pic_id"] == 99
    assert updates[0]["realm"] == "QI_REFINEMENT"
    assert updates[0]["cultivation"]["realm_id"] == "QI_REFINEMENT"
    assert updates[0]["cultivation_display"] == "练气前期"
    assert updates[0]["action_emoji"] == "🚶"
    assert updates[1] == {
        "id": "dead-1",
        "name": "Ancestor",
        "is_dead": True,
        "action": "",
    }
    assert updates[2]["id"] == "live-1"
    assert updates[2]["x"] == 7
    assert updates[2]["y"] == 8
    assert updates[2]["gender"] == "female"
    assert updates[2]["pic_id"] == 1
    assert updates[2]["realm"] == "FOUNDATION_ESTABLISHMENT"
    assert updates[2]["cultivation"]["realm_id"] == "FOUNDATION_ESTABLISHMENT"
    assert updates[2]["cultivation_display"] == "筑基前期"
    assert updates[2]["action_emoji"] == "✨"


def test_build_tick_state_uses_serializer_hooks():
    map_updates = [{
        "op": "upsert",
        "id": "mine:1",
        "site": {
            "id": "mine:1",
            "cell_refs": [[2, 3]],
            "integrity": 0.4,
            "enabled": True,
        },
    }]
    world = SimpleNamespace(
        month_stamp=SimpleNamespace(
            get_year=lambda: 120,
            get_month=lambda: SimpleNamespace(value=6),
        ),
        current_phenomenon=SimpleNamespace(id=1),
        map=SimpleNamespace(get_infrastructure_site_updates=lambda: map_updates),
    )

    state = build_tick_state(
        world=world,
        events=["evt"],
        avatar_updates=[{"id": "a"}],
        serialize_events_for_client=lambda events, *, world: [
            {"count": len(events), "has_world": world is not None}
        ],
        serialize_phenomenon=lambda phenomenon: {"id": phenomenon.id},
        serialize_active_domains=lambda _world: [{"id": "domain"}],
    )

    assert state == {
        "type": "tick",
        "year": 120,
        "month": 6,
        "events": [{"count": 1, "has_world": True}],
        "avatars": [{"id": "a"}],
        "removed_avatar_ids": [],
        "world_revision": 0,
        "poi_updates": [],
        "site_updates": [{
            "op": "upsert",
            "site": {
                "id": "mine:1",
                "cell_refs": [[2, 3]],
                "integrity": 0.4,
                "enabled": True,
                "status": "impaired",
                "x": 2,
                "y": 3,
                "clickable": True,
            },
        }],
        "route_updates": [],
        "phenomenon": {"id": 1},
        "active_domains": [{"id": "domain"}],
    }


def test_should_trigger_auto_save_respects_decade_boundary(monkeypatch):
    class DummySettingsService:
        def get_settings(self):
            return SimpleNamespace(simulation=SimpleNamespace(auto_save_enabled=True))

    monkeypatch.setattr("src.server.loop_runtime.get_settings_service", lambda: DummySettingsService())

    world = SimpleNamespace(
        start_year=100,
        month_stamp=SimpleNamespace(
            get_year=lambda: 110,
            get_month=lambda: SimpleNamespace(value=1),
        ),
    )

    assert should_trigger_auto_save(world=world) == (True, 110, 1)


def test_build_auto_save_toast_has_stable_contract():
    toast = build_auto_save_toast()

    assert toast["type"] == "toast"
    assert toast["level"] == "info"
    assert isinstance(toast["message"], str)

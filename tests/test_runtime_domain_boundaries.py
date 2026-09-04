from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from src.classes.institution import (
    InstitutionalAuthorityState,
    InstitutionalRelationsState,
    Institution,
    InstitutionKind,
)
from src.classes.mechanical_language import EntityRef
from src.server.runtime.session import GameSessionRuntime, create_default_game_state
from src.sim.runtime_capabilities import (
    DecisionBoundaryResult,
    get_decision_boundary_gateway,
)
from src.systems.institutional_diplomacy import (
    STATUS_WAR,
    get_sect_diplomacy_breakdown,
    get_sect_diplomacy_state,
    set_formal_war,
)


def test_domain_and_simulation_modules_do_not_depend_on_server_implementation():
    root = Path(__file__).parents[1] / "src"
    offenders: list[str] = []
    for directory in (root / "classes", root / "sim"):
        for path in directory.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = getattr(node, "module", "") or ""
                if module.startswith("src.server"):
                    offenders.append(f"{path.relative_to(root)}:{node.lineno}:{module}")
    assert offenders == []


def test_runtime_gateway_marks_a_controlled_avatar_at_a_decision_boundary():
    class Avatar:
        id = "avatar-1"
        name = "Tester"
        current_action = None

        @staticmethod
        def has_plans() -> bool:
            return False

    avatar = Avatar()
    runtime = GameSessionRuntime(create_default_game_state())
    session = runtime.get_roleplay_session()
    session["controlled_avatar_id"] = avatar.id
    session["status"] = "observing"

    class Manager:
        @staticmethod
        def get_avatar(avatar_id: str):
            return avatar if avatar_id == avatar.id else None

    world = SimpleNamespace(avatar_manager=Manager(), runtime=runtime)
    gateway = get_decision_boundary_gateway(world)
    assert gateway is not None
    assert (
        gateway.before_ai_decision(world) == DecisionBoundaryResult.WAITING_FOR_PLAYER
    )
    assert runtime.get_roleplay_session()["status"] == "awaiting_decision"
    assert runtime.is_effectively_paused() is True


def test_institutional_relations_own_formal_war_without_material_effects():
    authority = InstitutionalAuthorityState()
    for sect_id in (1, 2):
        authority.add_institution(
            Institution(
                kind=InstitutionKind.SECT,
                owner_ref=EntityRef("sect", str(sect_id)),
                founded_month=100,
            )
        )
    world = SimpleNamespace(
        start_year=0,
        institutional_authority=authority,
        institutional_relations=InstitutionalRelationsState(),
        event_manager=None,
    )

    relation = set_formal_war(
        world, 2, 1, current_month=101, evidence_event_ids=("event:war",)
    )

    assert relation.id in world.institutional_relations.relations
    assert (
        get_sect_diplomacy_state(world, 1, 2, current_month=101)["status"] == STATUS_WAR
    )
    assert (
        get_sect_diplomacy_breakdown(world, current_month=101, sect_ids=(1, 2))[(1, 2)][
            0
        ]["reason"]
        == "WAR_STATE"
    )

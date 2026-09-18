"""Focused contract for the generic actor decision dossier."""

import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.medieval.actor_dossier import build_actor_dossier
from tests.test_medieval_institutional_aid import REQUESTER, prepared_world

OTHER = EntityRef("polity", "valedouro")


def test_dossier_exposes_only_actors_own_known_reports_objectives_and_scopes():
    world = prepared_world()
    dossier = build_actor_dossier(world, REQUESTER)

    assert dossier["actor"] == REQUESTER.to_dict()
    assert dossier["today"] == world.clock.absolute_day

    own_reports = world.knowledge.settlements_for_actor(REQUESTER)
    assert len(dossier["known_settlement_reports"]) == len(own_reports)
    assert all(report["settlement_id"] in {r.settlement_id for r in own_reports}
              for report in dossier["known_settlement_reports"])

    assert dossier["authority_scopes"]
    assert all(scope in {"trade", "supply", "taxation", "research", "diplomacy", "military"}
              for scope in dossier["authority_scopes"])

    def _signature(objective):
        return (objective.settlement_id, objective.resource_id, objective.kind)

    own_signatures = {_signature(o) for o in world.strategy.objectives.values() if o.actor_ref == REQUESTER}
    dossier_signatures = {(item["settlement_id"], item["resource_id"], item["kind"])
                          for item in dossier["own_objectives"]}
    assert dossier_signatures == own_signatures
    # The objective's own raw id is only an internal basis (it may embed a
    # stock's address); it is not itself information the actor is owed.
    assert not any("objective_id" in item for item in dossier["own_objectives"])

    # A foreign actor's own objectives never leak into this actor's dossier.
    other_signatures = {_signature(o) for o in world.strategy.objectives.values() if o.actor_ref == OTHER}
    assert not (other_signatures & own_signatures)
    assert not (dossier_signatures & other_signatures)


def test_dossier_rejects_a_non_entity_ref_actor():
    world = prepared_world()
    with pytest.raises(TypeError):
        build_actor_dossier(world, "auren")


def test_dossier_is_json_safe_for_the_provider_prompt():
    import json

    world = prepared_world()
    dossier = build_actor_dossier(world, REQUESTER)
    json.dumps(dossier, sort_keys=True, ensure_ascii=False)

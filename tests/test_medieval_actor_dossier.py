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


def test_dossier_carries_known_memory_readings_and_derived_capacity():
    from tests.test_medieval_institutional_memory import breach_event_id
    from tests.test_medieval_institutional_aid import _breached_aid_world, PROVIDER

    world, obligation_id = _breached_aid_world()
    breach = breach_event_id(world, obligation_id)
    dossier = build_actor_dossier(world, REQUESTER)

    assert dossier["known_institutional_views"] == ({
        "subject_ref": PROVIDER.to_dict(), "reading": -4,
        "evidence_event_ids": [breach],
    },)
    assert set(dossier["strategic_capacity"]) == {
        "food_reserves", "productive_inputs", "territorial_defense",
        "administrative_bandwidth", "diplomatic_bandwidth", "military_command",
        "project_capacity", "logistics_capacity",
    }


def test_dossier_exposes_own_plan_lifecycle_without_foreign_handles():
    from src.classes.governance.models import StrategicPlan

    world = prepared_world()
    objective = next(item for item in world.strategy.objectives.values() if item.actor_ref == REQUESTER)
    world.strategy.plans[f"plan:{objective.id}"] = StrategicPlan(
        id=f"plan:{objective.id}", objective_id=objective.id, stage="blocked",
        blocker="sem_rota", last_review_day=world.clock.absolute_day, last_event_id="event:1")

    dossier = build_actor_dossier(world, REQUESTER)
    assert dossier["own_plans"] == ({
        "settlement_id": objective.settlement_id, "resource_id": objective.resource_id,
        "kind": objective.kind, "stage": "blocked", "blocker": "sem_rota",
        "last_review_day": world.clock.absolute_day,
    },)
    assert "objective_id" not in dossier["own_plans"][0]
    assert "order_ids" not in dossier["own_plans"][0]


def test_dossier_carries_only_strategic_findings_known_by_the_actor():
    from src.classes.governance.models import EspionageFinding

    world = prepared_world()
    agent = next(item for item in world.society.characters.values() if item.death_day is None)
    target = next(iter(world.society.settlements))
    known = EspionageFinding(
        id="espionage_finding:dossier-decision-known", mission_id="espionage:dossier-known",
        decision_event_id="dossier-decision-known", recipient_ref=REQUESTER,
        agent_ref=EntityRef("character", agent.id), target_ref=EntityRef("settlement", target),
        target_owner_ref=OTHER, result="failure", learned_day=world.clock.absolute_day,
        event_id="dossier-event-known")
    foreign = known.model_copy(update={
        "id": "espionage_finding:dossier-decision-foreign", "mission_id": "espionage:dossier-foreign",
        "decision_event_id": "dossier-decision-foreign", "recipient_ref": OTHER,
        "event_id": "dossier-event-foreign"})
    world.knowledge.espionage_findings[known.id] = known
    world.knowledge.espionage_findings[foreign.id] = foreign

    evidence = build_actor_dossier(world, REQUESTER)["known_strategic_evidence"]
    assert [item["finding_id"] for item in evidence] == [known.id]
    assert evidence[0]["recipient_ref"] == REQUESTER.to_dict()

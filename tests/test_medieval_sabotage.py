"""Focused causal checks for the bounded sabotage/investigation vertical."""

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment, ForcePosition
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.force import detect_force_standoffs
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_site_reports
from src.sim.medieval.sabotage import (execute_sabotage_option, investigation_options,
                                       open_investigation, sabotage_options)


AUREN = EntityRef("polity", "auren")
ESCARLIA = EntityRef("polity", "escarlia")
SITE = "passagem-negra"  # Auren's site touches Ferroalto, where Escarlia has stock.
PLACE = "ferroalto"


def decide(world, option):
    return record_event(world, "sabotage_decided", "Decisão de teste sobre uma affordance canônica.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def _present_force(world, actor, identity, *, prepared=True):
    group = next(item for item in world.society.population.values()
                 if item.settlement_id == PLACE and not any(
                     other.settlement_id == PLACE and other.people == item.people and other.occupation == "soldier"
                     for other in world.society.population.values()))
    soldiers = group.model_copy(update={"id": f"pop:{PLACE}:{actor.id}:{identity}:soldier",
                                        "occupation": "soldier", "count": 5})
    world.society.population[soldiers.id] = soldiers
    origin = record_event(world, "force_fixture", "Premissa material da coluna de teste.")
    force = Detachment(id=identity, owner_ref=actor, source_group_id=soldiers.id, count=5,
                       location_id=PLACE, destination_id=PLACE, route_ids=(), route_index=0,
                       provisions=100, stage="present", started_day=0, due_day=100,
                       decision_event_id=origin.id, last_event_id=origin.id)
    world.society.detachments[force.id] = force
    if prepared:
        position_decision = record_event(
            world, "force_position_decided", "Premissa decisória da posição local.", fact_kind=FactKind.DECISION,
            decision={"action": "prepare_force_position", "actor_ref": actor.to_dict(),
                      "selected_affordance_id": f"force-position:{force.id}:fixture"})
        start = record_event(
            world, "force_position_preparing", "Premissa de preparação local.", fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta(
                "force_position", f"force-position:{force.id}", "stage", None, "preparing"),),
            cause_ids=(position_decision.id,))
        world.clock = world.clock.advance(3)
        ready = record_event(
            world, "force_position_prepared", "Premissa de posição preparada.", fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta(
                "force_position", f"force-position:{force.id}", "stage", "preparing", "prepared"),),
            cause_ids=(start.id,))
        world.society.force_positions[f"force-position:{force.id}"] = ForcePosition(
            id=f"force-position:{force.id}", detachment_id=force.id, stage="prepared", settlement_id=PLACE,
            started_day=0, ready_day=3, last_event_id=ready.id)
        # This fixture deliberately exercises the sabotage executor, whose
        # prerequisites are current force state rather than force provenance.
    return force


def _sabotage_world(*, witness=False):
    world = create_medieval_world(73)
    attacker = _present_force(world, ESCARLIA, "detachment:saboteur")
    if witness:
        _present_force(world, AUREN, "detachment:witness", prepared=False)
        detect_force_standoffs(world, attacker.id)
    refresh_site_reports(world, site_ids=(SITE,))
    return world


def test_foreign_prepared_force_spends_tools_damages_only_integrity_and_victim_receipt_has_no_author(tmp_path):
    world = _sabotage_world()
    before = world.map.infrastructure_sites[SITE].integrity
    stock = world.economy.stocks["stock:ferroalto"]
    tools = stock.goods["tools"]
    option = next(item for item in sabotage_options(world, ESCARLIA) if item.site_id == SITE)

    with pytest.raises(ValueError, match="stale or unknown"):
        execute_sabotage_option(world, ESCARLIA, option.id + ":forged", decide(world, option).id)
    execute_sabotage_option(world, ESCARLIA, option.id, decide(world, option).id)

    site = world.map.infrastructure_sites[SITE]
    assert site.integrity == pytest.approx(before - 0.10)
    assert world.economy.stocks[stock.id].goods["tools"] == tools - 2
    event = next(item for item in world.events if item.event_type == "site_sabotaged")
    assert {delta.aspect for delta in event.deltas if delta.owner_kind == "site"} == {"integrity"}
    assert all(token not in str(world.knowledge.site_report(AUREN, SITE).model_dump())
               for token in ("escarlia", "saboteur", "detachment"))
    assert world.society.settlements[PLACE].occupier_id is None
    path = tmp_path / "sabotage.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_paid_investigation_is_inconclusive_without_prior_contact_or_attributes_known_copresent_cause():
    inconclusive = _sabotage_world()
    sabotage = next(item for item in sabotage_options(inconclusive, ESCARLIA) if item.site_id == SITE)
    execute_sabotage_option(inconclusive, ESCARLIA, sabotage.id, decide(inconclusive, sabotage).id)
    option = investigation_options(inconclusive, AUREN)[0]
    investigation = open_investigation(inconclusive, AUREN, option.id, decide(inconclusive, option).id)
    inconclusive.clock = inconclusive.clock.advance(30)
    resolve_dated(inconclusive, inconclusive.agenda.pop_due(inconclusive.clock.absolute_day))
    finding = inconclusive.knowledge.investigation_finding(AUREN, investigation.id)
    assert finding.result == "inconclusive" and finding.subject_ref is None
    assert not inconclusive.relations.memories_for(AUREN)

    attributed = _sabotage_world(witness=True)
    sabotage = next(item for item in sabotage_options(attributed, ESCARLIA) if item.site_id == SITE)
    execute_sabotage_option(attributed, ESCARLIA, sabotage.id, decide(attributed, sabotage).id)
    option = investigation_options(attributed, AUREN)[0]
    investigation = open_investigation(attributed, AUREN, option.id, decide(attributed, option).id)
    attributed.clock = attributed.clock.advance(30)
    resolve_dated(attributed, attributed.agenda.pop_due(attributed.clock.absolute_day))
    finding = attributed.knowledge.investigation_finding(AUREN, investigation.id)
    assert finding.result == "attributed" and finding.subject_ref == ESCARLIA
    assert len(attributed.relations.memories_for(AUREN)) == 1

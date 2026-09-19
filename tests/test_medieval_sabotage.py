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
from src.sim.medieval.sabotage import (accusation_options, execute_accusation, execute_sabotage_option,
                                       accusation_response_options, execute_accusation_response,
                                       investigation_options, open_investigation, sabotage_options)
from src.sim.medieval.diplomacy_context import strategic_evidence
from src.sim.medieval.creatures import creature_options, execute_creature_option
from src.sim.medieval.engine import MedievalSimulator
from src.run.medieval_creatures import DRAKE_ID
from tests.test_medieval_creatures import crossed_world


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


def test_sabotage_is_available_to_the_shared_monthly_institutional_menu():
    from src.sim.medieval.institutional_agenda import monthly_adapters

    adapters = monthly_adapters(allow_offers=False)
    adapter = next(item for item in adapters if item.name == "site_sabotage")
    assert adapter.family == "conflict"
    assert adapter.options_fn is not None and adapter.execute_fn is not None


def test_organization_with_conflict_affordance_is_included_in_monthly_turn(monkeypatch):
    """The shared boundary must not drop non-polity investigators/saboteurs."""
    world = create_medieval_world(73)
    organization = EntityRef("organization", "oficios-da-serra")
    from src.classes.society.models import Organization
    world.society.organizations[organization.id] = Organization(
        id=organization.id, name=organization.id, kind="merchant_guild", seat_id="ferroalto",
        member_ids=(), interests=())

    import src.sim.medieval.institutional_agenda as agenda
    monkeypatch.setattr(agenda, "sabotage_options", lambda _world, actor: (object(),)
                        if actor == organization else ())
    monkeypatch.setattr(agenda, "investigation_options", lambda _world, _actor: ())
    monkeypatch.setattr(agenda, "accusation_options", lambda _world, _actor: ())

    assert organization in agenda.monthly_actors(world)


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


async def test_creature_damage_offers_owner_a_canonical_investigation():
    world = await crossed_world()
    request = next(item for item in creature_options(world, DRAKE_ID) if item.kind == "request")
    execute_creature_option(world, DRAKE_ID, request.id, decide(world, request).id)
    demand = next(iter(world.creatures.demands.values()))
    while world.clock.absolute_day <= demand.due_day:
        await MedievalSimulator(world).step()

    damage = next(item for item in creature_options(world, DRAKE_ID) if item.kind == "damage")
    execute_creature_option(world, DRAKE_ID, damage.id, decide(world, damage).id)
    site = world.map.infrastructure_sites[damage.site_id]
    owner = site.owner_ref

    # The fixture world has artisans at this site; one local worker is enough
    # to exercise the existing paid-investigation owner without adding a new
    # labor path to the creature vertical.
    group = next(item for item in world.society.population.values()
                 if item.settlement_id == "portovelho")
    world.society.population[group.id] = group.model_copy(update={"occupation": "farmer"})

    options = investigation_options(world, owner)
    assert len(options) == 1
    option = options[0]
    assert option.damage_event_id == site.last_event_id
    assert world.events[int(option.damage_event_id.partition(":")[2]) - 1].event_type == "creature_damaged_site"

    investigation = open_investigation(world, owner, option.id, decide(world, option).id)
    assert investigation.investigator_ref == owner
    opened = world.events[-1]
    assert opened.event_type == "investigation_opened"
    assert {link.cause_event_id for link in opened.causal_links} >= {
        option.damage_event_id, option.report_event_id,
    }
    world.economy.validate(world)


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


def test_attributed_finding_can_be_deliberately_accused_without_creating_guilt_or_retaliation(tmp_path):
    world = _sabotage_world(witness=True)
    sabotage = next(item for item in sabotage_options(world, ESCARLIA) if item.site_id == SITE)
    execute_sabotage_option(world, ESCARLIA, sabotage.id, decide(world, sabotage).id)
    option = investigation_options(world, AUREN)[0]
    investigation = open_investigation(world, AUREN, option.id, decide(world, option).id)
    world.clock = world.clock.advance(30)
    resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))

    accusation = accusation_options(world, AUREN)
    assert len(accusation) == 1
    assert accusation_options(world, ESCARLIA) == ()
    selected = accusation[0]
    before_integrity = world.map.infrastructure_sites[SITE].integrity
    notice = execute_accusation(world, AUREN, selected.id, decide(world, selected).id)

    assert notice.recipient_ref == ESCARLIA
    assert notice.accuser_ref == AUREN
    event = next(item for item in world.events if item.id == notice.event_id)
    assert event.event_type == "investigation_accusation"
    assert {link.cause_event_id for link in event.causal_links} >= {notice.finding_event_id}
    assert world.map.infrastructure_sites[SITE].integrity == before_integrity
    assert world.knowledge.investigation_accusations_for_actor(ESCARLIA) == (notice,)
    evidence = strategic_evidence(world, ESCARLIA)
    assert any(item["kind"] == "investigation_accusation" and item["notice_id"] == notice.id
               and item["result"] == "notified" for item in evidence)
    assert accusation_options(world, AUREN) == ()
    responses = accusation_response_options(world, ESCARLIA)
    assert {item.response for item in responses} == {"deny", "request_review"}
    response = next(item for item in responses if item.response == "deny")
    response_event = execute_accusation_response(world, ESCARLIA, response.id, decide(world, response).id)
    assert response_event.event_type == "investigation_accusation_response"
    assert response_event.causal_payload["notice_id"] == notice.id
    assert response_event.causal_payload["response"] == "deny"
    assert any(item["kind"] == "investigation_accusation_response" and item["response"] == "deny"
               for item in strategic_evidence(world, ESCARLIA))
    assert any(item["kind"] == "investigation_accusation_response" and item["response"] == "deny"
               for item in strategic_evidence(world, AUREN))
    assert accusation_response_options(world, ESCARLIA) == (
        next(item for item in responses if item.response == "request_review"),
    )
    world.knowledge.validate(world)

    # The minimal sabotage fixture may carry unrelated dated work from world
    # creation; remove only entries already due so persistence can exercise the
    # accusation registry without resolving an unrelated vertical here.
    for situation_id, situation in tuple(world.agenda._situations.items()):
        if situation.due_day <= world.clock.absolute_day:
            world.agenda.cancel(situation_id)
    path = tmp_path / "accusation.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

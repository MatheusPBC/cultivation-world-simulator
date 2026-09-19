"""A pressure-backed administration concession binds terms before any owner acts."""

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.administration_concession import (
    administration_concession_offer_options, administration_concession_response_options,
    administration_transfer_fulfillment_options, fulfill_administration_transfer,
    offer_administration_concession, respond_administration_concession)
from src.sim.medieval.concurrent_civil_decision import concurrent_civil_options
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (detect_force_standoffs, establish_garrison, force_options,
                                    force_position_options, garrison_options, occupy_settlement,
                                    prepare_force_position)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import observe_present_force, refresh_settlement_reports
from src.sim.medieval.settlement_investment import (execute_settlement_investment_option,
                                                     settlement_investment_options)
from src.sim.medieval.territorial_control import (establish_territorial_control,
                                                   territorial_control_options)


ATTACKER = EntityRef("polity", "auren")
DEFENDER = EntityRef("polity", "escarlia")
TARGET = "ferroalto"


def decide(world, option):
    return record_event(world, "administration_concession_decided", "Decisão canônica sobre concessão administrativa.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def tick(world):
    world.clock = world.clock.advance(1)
    resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))


def concession_world():
    """One real prepared, occupying and investing column meets the administrator's column."""
    world = create_medieval_world(131)
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    group = next(item for item in world.society.population.values() if item.settlement_id == "campomanso")
    soldiers_id = f"pop:campomanso:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 40})
    arrival = record_event(
        world, "test_concession_column_present", "Fixture factual de coluna estrangeira presente.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment", "detachment:test-concession", "stage", None, "present"),),
    )
    own = Detachment(
        id="detachment:test-concession", owner_ref=ATTACKER, source_group_id=soldiers_id, count=40,
        location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0, provisions=320,
        stage="present", started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 30,
        decision_event_id=arrival.id, last_event_id=arrival.id,
    )
    world.society.detachments[own.id] = own
    position = force_position_options(world, ATTACKER, detachment_id=own.id)[0]
    prepare_force_position(world, ATTACKER, position.id, decide(world, position).id)
    for _ in range(3):
        tick(world)
    refresh_route_reports(world)
    observe_present_force(world, own.id)
    occupy = next(item for item in force_options(world, ATTACKER)
                  if item.detachment_id == own.id and item.kind == "occupy")
    occupy_settlement(world, ATTACKER, occupy.id, decide(world, occupy).id)
    observe_present_force(world, own.id)

    resident = next(item for item in world.society.population.values() if item.settlement_id == TARGET)
    defender_group = resident.model_copy(update={"id": f"pop:{TARGET}:{resident.people}:soldier",
                                                 "occupation": "soldier", "count": 5})
    world.society.population[defender_group.id] = defender_group
    rival_arrival = record_event(
        world, "test_concession_defender_present", "Fixture factual de coluna do administrador presente.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment", "detachment:test-concession-defender", "stage", None, "present"),),
    )
    rival = Detachment(
        id="detachment:test-concession-defender", owner_ref=DEFENDER, source_group_id=defender_group.id, count=5,
        location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0, provisions=160,
        stage="present", started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 30,
        decision_event_id=rival_arrival.id, last_event_id=rival_arrival.id,
    )
    world.society.detachments[rival.id] = rival
    detect_force_standoffs(world, rival.id)
    investment = next(item for item in settlement_investment_options(world, ATTACKER, detachment_id=own.id)
                      if item.kind == "invest")
    execute_settlement_investment_option(world, ATTACKER, investment.id, decide(world, investment).id)
    return world, own.id


def accepted_concession(world):
    offer = administration_concession_offer_options(world, ATTACKER)[0]
    proposal = offer_administration_concession(world, ATTACKER, offer.id, decide(world, offer).id)
    response = next(item for item in administration_concession_response_options(world, DEFENDER)
                    if item.proposal_id == proposal.id and item.response == "accept")
    return respond_administration_concession(world, DEFENDER, response.id, decide(world, response).id)


def test_acceptance_binds_administration_and_withdrawal_without_transferring():
    world, own_id = concession_world()
    administrator_before = world.society.settlements[TARGET].administrator_id
    proposal = accepted_concession(world)

    transfer, withdrawal = proposal.clauses
    assert proposal.status == "accepted"
    assert transfer.kind == "administration_transfer" and transfer.debtor_ref == DEFENDER
    assert withdrawal.kind == "withdrawal" and withdrawal.depends_on == (0,)
    assert world.society.settlements[TARGET].administrator_id == administrator_before == DEFENDER.id
    assert world.society.settlements[TARGET].occupier_id == ATTACKER.id
    assert world.society.detachments[own_id].stage == "present"
    assert {item.status for item in world.relations.obligations.values()} == {"active"}


def test_sustained_control_can_open_a_postwar_administration_settlement():
    world, own_id = concession_world()
    garrison = next(item for item in garrison_options(world, ATTACKER) if item.kind == "garrison")
    establish_garrison(world, ATTACKER, garrison.id, decide(world, garrison).id)
    refresh_settlement_reports(world)
    control = next(item for item in territorial_control_options(world, ATTACKER)
                   if item.kind == "establish")
    establish_territorial_control(world, ATTACKER, control.id, decide(world, control).id)
    refresh_settlement_reports(world)

    offer = next(item for item in administration_concession_offer_options(world, ATTACKER)
                 if item.kind == "postwar")
    proposal = offer_administration_concession(world, ATTACKER, offer.id, decide(world, offer).id)
    assert len(proposal.clauses) == 1
    response = next(item for item in administration_concession_response_options(world, DEFENDER)
                    if item.proposal_id == proposal.id and item.response == "accept")
    respond_administration_concession(world, DEFENDER, response.id, decide(world, response).id)

    fulfillment = administration_transfer_fulfillment_options(world, DEFENDER)[0]
    obligation = fulfill_administration_transfer(world, DEFENDER, fulfillment.id, decide(world, fulfillment).id)

    assert obligation.status == "fulfilled"
    assert world.society.settlements[TARGET].administrator_id == ATTACKER.id
    assert world.society.settlements[TARGET].occupier_id == ATTACKER.id
    assert world.society.garrisons[f"garrison:{own_id}"].stage == "active"
    assert world.society.territorial_controls[f"territorial-control:{TARGET}"].stage == "active"


def test_breached_postwar_transfer_opens_a_new_remediation_proposal():
    world, _ = concession_world()
    garrison = next(item for item in garrison_options(world, ATTACKER) if item.kind == "garrison")
    establish_garrison(world, ATTACKER, garrison.id, decide(world, garrison).id)
    refresh_settlement_reports(world)
    control = next(item for item in territorial_control_options(world, ATTACKER)
                   if item.kind == "establish")
    establish_territorial_control(world, ATTACKER, control.id, decide(world, control).id)
    refresh_settlement_reports(world)
    offer = next(item for item in administration_concession_offer_options(world, ATTACKER)
                 if item.kind == "postwar")
    proposal = offer_administration_concession(world, ATTACKER, offer.id, decide(world, offer).id)
    response = next(item for item in administration_concession_response_options(world, DEFENDER)
                    if item.proposal_id == proposal.id and item.response == "accept")
    respond_administration_concession(world, DEFENDER, response.id, decide(world, response).id)
    for _ in range(3):
        tick(world)
    breached = world.relations.obligations[f"{proposal.id}:term:0"]
    assert breached.status == "breached"
    refresh_settlement_reports(world)
    remediation = next(item for item in administration_concession_offer_options(world, ATTACKER)
                       if item.kind == "postwar_remediation")
    repaired_proposal = offer_administration_concession(world, ATTACKER, remediation.id,
                                                        decide(world, remediation).id)
    assert repaired_proposal.id != proposal.id
    assert remediation.breach_event_id == breached.breach_event_id
    response = next(item for item in administration_concession_response_options(world, DEFENDER)
                    if item.proposal_id == repaired_proposal.id and item.response == "accept")
    respond_administration_concession(world, DEFENDER, response.id, decide(world, response).id)
    fulfillment = administration_transfer_fulfillment_options(world, DEFENDER)[0]
    repaired = fulfill_administration_transfer(world, DEFENDER, fulfillment.id, decide(world, fulfillment).id)
    assert repaired.status == "fulfilled"
    assert world.relations.obligations[breached.id].status == "breached"
    assert world.society.settlements[TARGET].administrator_id == ATTACKER.id


def test_concession_offer_is_available_in_the_composed_campaign_menu():
    world, _ = concession_world()
    options = concurrent_civil_options(world, ATTACKER)
    assert any(option.id.startswith("administration-concession:") for option in options)


def test_current_administrator_fulfills_only_administration_and_persists(tmp_path):
    world, own_id = concession_world()
    proposal = accepted_concession(world)
    stocks_before = {key: item.model_dump(mode="json") for key, item in world.economy.stocks.items()}
    population_before = {key: item.model_dump(mode="json") for key, item in world.society.population.items()}
    detachments_before = {key: item.model_dump(mode="json") for key, item in world.society.detachments.items()}
    route_capacity_before = {key: world.map.get_route_operational_capacity(key) for key in world.map.routes}
    interdictors_before = dict(world.map.force_route_interdictors)
    settlement_before = world.society.settlements[TARGET]

    option = administration_transfer_fulfillment_options(world, DEFENDER)[0]
    obligation = fulfill_administration_transfer(world, DEFENDER, option.id, decide(world, option).id)

    settlement_after = world.society.settlements[TARGET]
    assert obligation.status == "fulfilled"
    assert settlement_after.administrator_id == ATTACKER.id
    assert settlement_after.occupier_id == settlement_before.occupier_id
    assert settlement_after.claimant_ids == settlement_before.claimant_ids
    assert {key: item.model_dump(mode="json") for key, item in world.economy.stocks.items()} == stocks_before
    assert {key: item.model_dump(mode="json") for key, item in world.society.population.items()} == population_before
    assert {key: item.model_dump(mode="json") for key, item in world.society.detachments.items()} == detachments_before
    assert {key: world.map.get_route_operational_capacity(key) for key in world.map.routes} == route_capacity_before
    assert world.map.force_route_interdictors == interdictors_before
    assert world.society.detachments[own_id].stage == "present"
    assert world.relations.obligations[f"{proposal.id}:term:1"].status == "active"
    assert any(event.event_type == "settlement_administration_transferred" for event in world.events)
    path = tmp_path / "administration-concession.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_rejection_and_stale_or_wrong_actor_options_change_no_material_state():
    world, _ = concession_world()
    offer = administration_concession_offer_options(world, ATTACKER)[0]
    proposal = offer_administration_concession(world, ATTACKER, offer.id, decide(world, offer).id)
    response = next(item for item in administration_concession_response_options(world, DEFENDER)
                    if item.response == "reject")
    before = world.society.settlements[TARGET].model_dump(mode="json")
    respond_administration_concession(world, DEFENDER, response.id, decide(world, response).id)
    assert world.society.settlements[TARGET].model_dump(mode="json") == before
    assert world.relations.proposals[proposal.id].status == "rejected"

    stale_world, own_id = concession_world()
    stale = administration_concession_offer_options(stale_world, ATTACKER)[0]
    stale_decision = decide(stale_world, stale)
    own = stale_world.society.detachments[own_id]
    stale_world.society.detachments[own_id] = own.model_copy(update={"provisions": 0})
    before = (len(stale_world.events), dict(stale_world.society.settlements),
              dict(stale_world.relations.proposals), dict(stale_world.relations.obligations))
    with pytest.raises(ValueError, match="stale or unknown"):
        offer_administration_concession(stale_world, ATTACKER, stale.id, stale_decision.id)
    assert (len(stale_world.events), dict(stale_world.society.settlements),
            dict(stale_world.relations.proposals), dict(stale_world.relations.obligations)) == before

    wrong_world, _ = concession_world()
    wrong = administration_concession_offer_options(wrong_world, ATTACKER)[0]
    wrong_decision = decide(wrong_world, wrong)
    before = (len(wrong_world.events), dict(wrong_world.society.settlements),
              dict(wrong_world.relations.proposals), dict(wrong_world.relations.obligations))
    with pytest.raises(ValueError, match="stale or unknown"):
        offer_administration_concession(wrong_world, DEFENDER, wrong.id, wrong_decision.id)
    assert (len(wrong_world.events), dict(wrong_world.society.settlements),
            dict(wrong_world.relations.proposals), dict(wrong_world.relations.obligations)) == before

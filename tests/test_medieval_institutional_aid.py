"""Focused contracts for the transient medieval institutional-aid vertical."""

from dataclasses import replace

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import record_event
from src.sim.medieval.institutional_aid import (
    aid_fulfillment_options,
    aid_remediation_options,
    aid_request_options,
    aid_response_options,
    fulfill_institutional_aid,
    remediate_institutional_aid,
    request_institutional_aid,
    respond_institutional_aid,
)
from src.sim.medieval.commitments import resolve_diplomacy
from src.sim.medieval.logistics import resolve_parcels
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.systems.calendar_agenda import ScheduledSituation
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


REQUESTER = EntityRef("polity", "auren")
PROVIDER = EntityRef("polity", "valedouro")


def prepared_world():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    need = world.economy.needs["pedraclara"]
    world.economy.needs[need.id] = need.model_copy(update={"missing_food": 300})
    stock = world.economy.stocks[need.stock_id]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "food": 0}})
    source = world.economy.stocks["stock:portovelho"]
    world.economy.stocks[source.id] = source.model_copy(update={"goods": {**source.goods, "food": 10000}})
    refresh_settlement_reports(world)
    return world


def decision(world, option, event_type):
    event = record_event(world, event_type, "Decisão institucional.", fact_kind=FactKind.DECISION,
                         decision=option.decision())
    return event


def test_aid_chain_hides_terms_until_provider_and_fulfills_real_freight(tmp_path):
    world = prepared_world()
    request_options = aid_request_options(world, REQUESTER)
    assert request_options
    request_option = next(item for item in request_options if item.provider_ref == PROVIDER)
    assert not any(hasattr(request_option, field) for field in ("source_stock_id", "quantity", "route_ids"))
    request_decision = decision(world, request_option, "aid request")
    request = request_institutional_aid(world, REQUESTER, request_option.id, request_decision.id)
    refresh_route_reports(world, route_ids=("river-pedraclara-portovelho",))
    provider_notices = world.knowledge.institutional_aid_for_actor(PROVIDER)
    assert len(provider_notices) == 1
    assert provider_notices[0].kind == "request"
    assert provider_notices[0].request_event_id == request.id
    assert provider_notices[0].requester_ref == REQUESTER
    assert provider_notices[0].requester_settlement_id == request_option.requester_settlement_id
    assert provider_notices[0].report_id == request_option.report_id
    assert not any(hasattr(provider_notices[0], field) for field in ("source_stock_id", "quantity", "route_ids"))
    assert not world.knowledge.institutional_aid_for_actor(REQUESTER)

    response_option = next(item for item in aid_response_options(world, PROVIDER) if item.kind == "accept")
    assert response_option.quantity and response_option.source_stock_id and response_option.route_ids
    response_decision = decision(world, response_option, "aid response")
    source_food = world.economy.stocks[response_option.source_stock_id].goods.get("food", 0)
    destination_food = world.economy.stocks[response_option.destination_stock_id].goods.get("food", 0)
    accounts_before = {key: account.balance for key, account in world.economy.accounts.items()}
    freight_count = len(world.economy.freight_orders)
    proposal = respond_institutional_aid(world, PROVIDER, response_option.id, response_decision.id)
    requester_notices = world.knowledge.institutional_aid_for_actor(REQUESTER)
    assert len(requester_notices) == 1
    assert requester_notices[0].kind == "response"
    assert requester_notices[0].response_status == "accepted"
    assert requester_notices[0].request_event_id == request.id
    assert not any(hasattr(requester_notices[0], field) for field in ("source_stock_id", "quantity", "route_ids"))
    assert tuple(notice.kind for notice in world.knowledge.institutional_aid_for_actor(PROVIDER)) == ("request",)
    assert world.economy.stocks[response_option.source_stock_id].goods.get("food", 0) == source_food
    assert world.economy.stocks[response_option.destination_stock_id].goods.get("food", 0) == destination_food
    assert {key: account.balance for key, account in world.economy.accounts.items()} == accounts_before
    assert len(world.economy.freight_orders) == freight_count
    obligation_id = next(iter(world.relations.obligations))
    fulfill_option = aid_fulfillment_options(world, PROVIDER)[0]
    fulfill_decision = decision(world, fulfill_option, "aid fulfillment")
    order = fulfill_institutional_aid(world, PROVIDER, fulfill_option.id, fulfill_decision.id)

    assert proposal.proposal_kind == "institutional_aid"
    assert order.id in world.economy.freight_orders
    assert world.relations.obligations[obligation_id].status == "fulfilled"
    fulfillment = next(e for e in world.events if e.event_type == "institutional_aid_fulfilled")
    assert order.last_event_id in {link.cause_event_id for link in fulfillment.causal_links}
    save_world(world, tmp_path / "aid.mws")
    assert world_snapshot(load_world(tmp_path / "aid.mws")) == world_snapshot(world)


def test_stale_or_wrong_aid_decisions_do_not_mutate_world():
    world = prepared_world()
    option = aid_request_options(world, REQUESTER)[0]
    wrong = record_event(world, "aid decision", "Decisão inválida.", fact_kind=FactKind.DECISION,
                         decision={**option.decision(), "actor_ref": PROVIDER.to_dict()})
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="actor|authority|option"):
        request_institutional_aid(world, REQUESTER, option.id, wrong.id)
    assert world_snapshot(world) == before

    stale = decision(world, option, "stale aid request")
    world.clock = world.clock.advance(1)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="current|stale|option"):
        request_institutional_aid(world, REQUESTER, option.id, stale.id)
    assert world_snapshot(world) == before


def test_aid_response_requires_a_valid_private_provider_notice():
    world = prepared_world()
    request_option = next(item for item in aid_request_options(world, REQUESTER) if item.provider_ref == PROVIDER)
    request_decision = decision(world, request_option, "aid request")
    request_institutional_aid(world, REQUESTER, request_option.id, request_decision.id)
    refresh_route_reports(world, route_ids=("river-pedraclara-portovelho",))
    response_option = next(item for item in aid_response_options(world, PROVIDER) if item.kind == "reject")
    notice = world.knowledge.institutional_aid_for_actor(PROVIDER)[0]

    del world.knowledge.institutional_aid_notices[notice.id]
    assert not aid_response_options(world, PROVIDER)
    response_decision = decision(world, response_option, "missing aid notice")
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale|unknown"):
        respond_institutional_aid(world, PROVIDER, response_option.id, response_decision.id)
    assert world_snapshot(world) == before

    forged = notice.model_copy(update={"requester_ref": PROVIDER})
    world.knowledge.institutional_aid_notices[forged.id] = forged
    assert not aid_response_options(world, PROVIDER)
    with pytest.raises(ValueError, match="institutional aid"):
        world_snapshot(world)


def test_aid_rejection_notifies_only_the_requester():
    world = prepared_world()
    request_option = next(item for item in aid_request_options(world, REQUESTER) if item.provider_ref == PROVIDER)
    request_decision = decision(world, request_option, "aid request")
    request = request_institutional_aid(world, REQUESTER, request_option.id, request_decision.id)
    reject_option = next(item for item in aid_response_options(world, PROVIDER) if item.kind == "reject")
    reject_decision = decision(world, reject_option, "aid rejection")
    response = respond_institutional_aid(world, PROVIDER, reject_option.id, reject_decision.id)

    assert response.event_type == "institutional_aid_rejected"
    requester_notices = world.knowledge.institutional_aid_for_actor(REQUESTER)
    assert len(requester_notices) == 1
    assert requester_notices[0].request_event_id == request.id
    assert requester_notices[0].kind == "response"
    assert requester_notices[0].response_status == "rejected"
    assert tuple(notice.kind for notice in world.knowledge.institutional_aid_for_actor(PROVIDER)) == ("request",)


def _breached_aid_world():
    world = prepared_world()
    request_option = next(item for item in aid_request_options(world, REQUESTER)
                          if item.provider_ref == PROVIDER)
    request_decision = decision(world, request_option, "aid request")
    request_institutional_aid(world, REQUESTER, request_option.id, request_decision.id)
    refresh_route_reports(world, route_ids=("river-pedraclara-portovelho",))
    response_option = next(item for item in aid_response_options(world, PROVIDER) if item.kind == "accept")
    response_decision = decision(world, response_option, "aid response")
    respond_institutional_aid(world, PROVIDER, response_option.id, response_decision.id)
    obligation_id = next(iter(world.relations.obligations))
    world.clock = world.clock.advance(32)
    resolve_diplomacy(world, [ScheduledSituation(obligation_id, "diplomacy", 32)])
    return world, obligation_id


def test_remediation_requires_current_private_route_reports_and_is_atomic_when_stale():
    world, obligation_id = _breached_aid_world()
    assert not aid_remediation_options(world, PROVIDER)

    refresh_route_reports(world, route_ids=("river-pedraclara-portovelho",))
    option = aid_remediation_options(world, PROVIDER)[0]
    world.clock = world.clock.advance(30)
    assert not aid_remediation_options(world, PROVIDER)

    stale_decision = decision(world, option, "stale aid remediation")
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale|unknown|route"):
        from src.sim.medieval.institutional_aid import remediate_institutional_aid
        remediate_institutional_aid(world, PROVIDER, option.id, stale_decision.id)
    assert world_snapshot(world) == before
    assert world.relations.obligations[obligation_id].status == "breached"


def test_breach_remediation_preserves_history_and_validates_after_parcel_progress(tmp_path):
    world, obligation_id = _breached_aid_world()
    refresh_route_reports(world, route_ids=("river-pedraclara-portovelho",))
    option = aid_remediation_options(world, PROVIDER)[0]
    decision_event = decision(world, option, "aid remediation")
    balances = {key: account.balance for key, account in world.economy.accounts.items()}

    order = remediate_institutional_aid(world, PROVIDER, option.id, decision_event.id)
    obligation = world.relations.obligations[obligation_id]
    assert obligation.status == "remediated"
    assert obligation.breach_event_id == option.breach_event_id
    assert obligation.remediation_material_event_id == order.last_event_id
    assert order.decision_ids == (decision_event.id,)
    opened = next(event for event in world.events if event.id == order.last_event_id)
    assert opened.event_type == "freight_opened"
    assert decision_event.id in {link.cause_event_id for link in opened.causal_links}
    assert balances == {key: account.balance for key, account in world.economy.accounts.items()}

    world.clock = world.clock.advance(1)
    resolve_parcels(world, [item for item in world.agenda.pop_due(world.clock.absolute_day)
                            if item.kind == "cargo"])
    path = tmp_path / "remediated-aid.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)


def test_request_is_visible_without_provider_surplus_but_response_only_rejects():
    world = prepared_world()
    for stock in tuple(world.economy.stocks.values()):
        if stock.owner_ref == PROVIDER:
            world.economy.stocks[stock.id] = stock.model_copy(
                update={"goods": {**stock.goods, "food": 0}})
    request_option = next(item for item in aid_request_options(world, REQUESTER)
                          if item.provider_ref == PROVIDER)
    request_decision = decision(world, request_option, "aid request without surplus")
    request_institutional_aid(world, REQUESTER, request_option.id, request_decision.id)
    response_options = aid_response_options(world, PROVIDER)
    assert response_options and all(item.kind == "reject" for item in response_options)


def test_fulfillment_rejects_a_stale_private_route_without_mutation():
    world = prepared_world()
    request_option = next(item for item in aid_request_options(world, REQUESTER)
                          if item.provider_ref == PROVIDER)
    request_decision = decision(world, request_option, "aid request")
    request_institutional_aid(world, REQUESTER, request_option.id, request_decision.id)
    refresh_route_reports(world, route_ids=("river-pedraclara-portovelho",))
    response_option = next(item for item in aid_response_options(world, PROVIDER) if item.kind == "accept")
    response_decision = decision(world, response_option, "aid response")
    respond_institutional_aid(world, PROVIDER, response_option.id, response_decision.id)
    option = aid_fulfillment_options(world, PROVIDER)[0]
    world.clock = world.clock.advance(30)
    assert not aid_fulfillment_options(world, PROVIDER)
    stale_decision = decision(world, option, "stale aid fulfillment")
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale|unknown|option|route"):
        fulfill_institutional_aid(world, PROVIDER, option.id, stale_decision.id)
    assert world_snapshot(world) == before


def _run_aid_chain(world):
    request_option = next(item for item in aid_request_options(world, REQUESTER)
                          if item.provider_ref == PROVIDER)
    request_decision = decision(world, request_option, "aid request")
    request_institutional_aid(world, REQUESTER, request_option.id, request_decision.id)
    refresh_route_reports(world, route_ids=("river-pedraclara-portovelho",))
    response_option = next(item for item in aid_response_options(world, PROVIDER) if item.kind == "accept")
    response_decision = decision(world, response_option, "aid response")
    respond_institutional_aid(world, PROVIDER, response_option.id, response_decision.id)
    fulfill_option = aid_fulfillment_options(world, PROVIDER)[0]
    fulfill_decision = decision(world, fulfill_option, "aid fulfillment")
    order = fulfill_institutional_aid(world, PROVIDER, fulfill_option.id, fulfill_decision.id)
    return order, world.relations.obligations[fulfill_option.obligation_id]


def test_second_identical_aid_chain_keeps_first_fulfillment_receipt(tmp_path):
    world = prepared_world()
    first_order, first_obligation = _run_aid_chain(world)
    first_events = tuple(world.events)
    world.relations.validate(world)

    second_order, second_obligation = _run_aid_chain(world)

    for field in ("source_id", "destination_id", "resource_id", "quantity", "route_ids", "owner_ref"):
        assert getattr(second_order, field) == getattr(first_order, field)
    assert first_order.quantity > 0
    assert first_order.id != second_order.id
    assert first_order.decision_ids != second_order.decision_ids
    assert first_obligation.id != second_obligation.id
    assert first_obligation.material_event_id != second_obligation.material_event_id
    assert first_obligation.status == second_obligation.status == "fulfilled"
    assert world.relations.obligations[first_obligation.id] == first_obligation
    assert world.economy.freight_orders[first_order.id] == first_order
    assert tuple(world.events[:len(first_events)]) == first_events

    world.clock = world.clock.advance(1)
    resolve_parcels(world, [item for item in world.agenda.pop_due(world.clock.absolute_day)
                           if item.kind == "cargo"])
    for order, obligation in ((first_order, first_obligation), (second_order, second_obligation)):
        assert world.economy.freight_orders[order.id].last_event_id != obligation.material_event_id
        assert world.relations.obligations[obligation.id] == obligation
    world.relations.validate(world)
    save_world(world, tmp_path / "two-chains.mws")
    assert world_snapshot(load_world(tmp_path / "two-chains.mws")) == world_snapshot(world)


@pytest.mark.parametrize("tamper", ["swap", "reuse", "missing_order", "material_decision", "final_decision"])
def test_identical_aid_chains_reject_invalid_material_provenance(tamper):
    world = prepared_world()
    first_order, first = _run_aid_chain(world)
    second_order, second = _run_aid_chain(world)
    world.relations.validate(world)

    if tamper in {"swap", "reuse"}:
        pairs = ((first, second), (second, first)) if tamper == "swap" else ((second, first),)
        for obligation, other in pairs:
            world.relations.obligations[obligation.id] = obligation.model_copy(
                update={"material_event_id": other.material_event_id})
            index = next(i for i, event in enumerate(world.events) if event.id == obligation.last_event_id)
            final = world.events[index]
            world.events[index] = final.model_copy(update={
                "causal_links": tuple(replace(link, cause_event_id=other.material_event_id)
                                      if link.cause_event_id == obligation.material_event_id else link
                                      for link in final.causal_links),
                "deltas": tuple(replace(delta, after=other.material_event_id)
                                if delta.aspect == "material_event_id" else delta for delta in final.deltas)})
    elif tamper == "missing_order":
        del world.economy.freight_orders[second_order.id]
    else:
        event_id = second.material_event_id if tamper == "material_decision" else second.last_event_id
        index = next(i for i, event in enumerate(world.events) if event.id == event_id)
        event = world.events[index]
        world.events[index] = event.model_copy(update={
            "causal_links": tuple(replace(link, cause_event_id=first_order.decision_ids[0])
                                  if link.cause_event_id == second_order.decision_ids[0] else link
                                  for link in event.causal_links)})

    message = ("material receipt cannot fulfill multiple obligations" if tamper == "reuse"
               else "fulfillment requires the negotiated freight receipt")
    with pytest.raises(ValueError, match=message):
        world.relations.validate(world)

"""The fallback policy only selects enumerated options and never invents terms."""

from src.sim.medieval.institutional_aid_policy import review_institutional_aid
from src.sim.medieval.procurement import review_supply
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from tests.test_medieval_institutional_aid import prepared_world


def pressured_world():
    """Reuse the aid fixture and give the requester a real blocked food plan."""
    world = prepared_world()
    review_supply(world)
    refresh_route_reports(world)
    return world


def advance(world, days=1):
    world.clock = world.clock.advance(days)
    refresh_settlement_reports(world)
    refresh_route_reports(world)


def first_request(world):
    """The request the policy actually chose, with its own parties."""
    notice = next(item for _, item in sorted(world.knowledge.institutional_aid_notices.items())
                  if item.kind == "request")
    return notice, notice.requester_ref, notice.recipient_ref


def test_policy_runs_request_response_and_fulfillment_on_consecutive_days():
    world = pressured_world()
    assert any(item.stage == "blocked" for item in world.strategy.plans.values())

    review_institutional_aid(world, allow_requests=True)
    notice, requester, provider = first_request(world)
    request = next(item for item in world.events if item.id == notice.request_event_id)
    assert request.event_type == "institutional_aid_requested"
    assert notice.requested_food > 0
    assert not world.relations.obligations, "a request binds nothing"

    def requests_for(place):
        return len([item for item in world.events if item.event_type == "institutional_aid_requested"
                    and any(delta.owner_kind == "aid_request" and delta.aspect == "requester_settlement_id"
                            and delta.after == place for delta in item.deltas)])

    # An unanswered chain already blocks a second request for the same place,
    # whichever other institution could be asked.
    place = notice.requester_settlement_id
    open_requests = requests_for(place)
    review_institutional_aid(world, allow_requests=True)
    assert requests_for(place) == open_requests

    advance(world)
    accounts = {key: item.balance for key, item in world.economy.accounts.items()}
    stocks = {key: dict(item.goods) for key, item in world.economy.stocks.items()}
    review_institutional_aid(world, allow_requests=False)
    obligation = next(item for item in world.relations.obligations.values()
                      if world.relations.proposals[item.proposal_id].proposer_ref == requester
                      and world.relations.proposals[item.proposal_id].counterparty_ref == provider)
    accepted = next(item for item in world.events if item.id == obligation.last_event_id)
    assert accepted.event_type == "institutional_aid_accepted" and accepted.day == world.clock.absolute_day
    assert obligation.status == "active"
    assert {key: item.balance for key, item in world.economy.accounts.items()} == accounts
    assert {key: dict(item.goods) for key, item in world.economy.stocks.items()} == stocks
    assert not world.economy.freight_orders, "acceptance moves no stock and no money"
    # The running commitment keeps that chain closed as well.
    committed_requests = requests_for(place)
    review_institutional_aid(world, allow_requests=True)
    assert requests_for(place) == committed_requests

    advance(world)
    review_institutional_aid(world, allow_requests=False)
    assert world.relations.obligations[obligation.id].status == "fulfilled"
    clause = world.relations.proposals[obligation.proposal_id].clauses[0]
    order = next(item for item in world.economy.freight_orders.values()
                 if item.source_id == clause.source_stock_id)
    assert (order.destination_id, order.resource_id, order.quantity) == (
        clause.destination_stock_id, "food", clause.quantity)
    assert order.owner_ref == clause.creditor_ref


def test_a_provider_without_surplus_or_route_only_rejects():
    world = pressured_world()
    # No institution anywhere holds food above its own reserve, so every
    # enumerated response can only be a refusal.
    for key, stock in list(world.economy.stocks.items()):
        if stock.owner_ref.kind == "polity":
            world.economy.stocks[key] = stock.model_copy(update={"goods": {**stock.goods, "food": 0}})

    review_institutional_aid(world, allow_requests=True)
    notice, requester, provider = first_request(world)
    # The direct notice states the need and nothing of the provider's side.
    assert notice.requested_food > 0
    assert not any(hasattr(notice, field) for field in ("source_stock_id", "quantity", "route_ids", "surplus"))
    assert notice.recipient_ref == provider and notice.requester_ref == requester

    advance(world)
    # The provider recomposes from the notice alone: erasing the requester's own
    # report cannot change the answer, because the response never reads it.
    for key, report in list(world.knowledge.settlement_reports.items()):
        if report.recipient_ref == requester:
            del world.knowledge.settlement_reports[key]
    review_institutional_aid(world, allow_requests=False)

    rejected = [item for item in world.events if item.event_type == "institutional_aid_rejected"
                and notice.request_event_id in {link.cause_event_id for link in item.causal_links}]
    assert len(rejected) == 1
    assert not world.relations.obligations and not world.economy.freight_orders
    response = next(item for item in world.knowledge.institutional_aid_for_actor(requester)
                    if item.kind == "response" and item.request_event_id == notice.request_event_id)
    assert response.response_status == "rejected" and response.requested_food == notice.requested_food

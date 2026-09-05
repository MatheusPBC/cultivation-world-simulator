from __future__ import annotations

import random
from unittest.mock import AsyncMock

import pytest

from src.classes.age import Age
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.dynasty import Dynasty
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.environment.city_state import CityGovernance
from src.classes.environment.region import CityRegion
from src.classes.regional_economy import RegionalEconomyState
from src.classes.core.world import World
from src.run.load_map import load_cultivation_world_map
from src.sim.simulator import Simulator
from src.sim.simulator_engine.finalizer import EventPersistenceError
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.time import Month, Year, create_month_stamp


def _barter_world() -> World:
    world = World(
        map=load_cultivation_world_map("classic"),
        month_stamp=create_month_stamp(Year(100), Month.JANUARY),
    )
    emperor = Avatar(
        world=world,
        name="Commerce Emperor",
        id="commerce-emperor",
        birth_month_stamp=create_month_stamp(Year(70), Month.JANUARY),
        age=Age(30, Realm.Qi_Refinement),
        gender=Gender.MALE,
    )
    world.avatar_manager.register_avatar(emperor)
    world.dynasty = Dynasty(1, "Commerce Dynasty", "", current_emperor_id=emperor.id)
    world.run_config_snapshot = {
        "map_id": "classic",
        "test_mode": True,
        "provider": "test",
        "npc_awakening_rate_per_month": 0.0,
        "economy_interpreter_llm_budget_per_month": 0,
        "institutional_commitment_fulfillment_llm_budget_per_month": 0,
        "domain_affordance_action_urgency_threshold": 1.0,
    }
    source = world.map.regions[302]
    destination = world.map.regions[305]
    assert isinstance(source, CityRegion)
    assert isinstance(destination, CityRegion)
    assert world.map.get_routes_between(source.id, destination.id)
    source.city_state.governance = CityGovernance("dynasty", "1", 1.0)
    destination.city_state.governance = CityGovernance("dynasty", "1", 1.0)
    # Each city has one current need and a different unreserved surplus.  This
    # is deliberately a material fixture, not a narrative quota.
    source.economy = RegionalEconomyState(
        stocks={"grain": 20.0, "medicine": 0.0},
        capacities={"grain": 30.0, "medicine": 30.0},
        demand_rates={"grain": 0.0, "medicine": 2.0},
        access={"grain": 1.0, "medicine": 1.0},
    )
    destination.economy = RegionalEconomyState(
        stocks={"grain": 0.0, "medicine": 20.0},
        capacities={"grain": 30.0, "medicine": 30.0},
        demand_rates={"grain": 2.0, "medicine": 0.0},
        access={"grain": 1.0, "medicine": 1.0},
    )
    bootstrap_institutional_authority(world)
    return world


async def _choose_barter_only(original, *args, **kwargs):
    domain = kwargs["domain"]
    affordances = tuple(kwargs["affordances"])
    selected = None
    if domain == "institutional_resource_request":
        selected = next(
            (
                item for item in affordances
                if item.action_kind == "request_reciprocal_trade"
            ),
            None,
        )
    elif domain == "institutional_resource_response":
        selected = next((item for item in affordances if item.action_kind == "accept_reciprocal_trade"), None)
    elif domain == "institutional_commitment_fulfillment":
        selected = next((item for item in affordances if item.action_kind == "fulfill_resource_transfer_term"), None)
    decision = (
        DomainDecision(DomainDecisionKind.ACT, "Controlled commerce witness.", selected.id)
        if selected is not None
        else DomainDecision(DomainDecisionKind.MAINTAIN, "No controlled commerce action.")
    )
    return await original(*args, **{**kwargs, "injected_decision": decision})


async def _run_barter_witness(world: World, monkeypatch, *, steps: int = 4) -> tuple[list, AsyncMock, Simulator]:
    import src.systems.institutional_resource_commitment as commitments

    original = commitments.interpret_domain_affordances

    async def controlled(*args, **kwargs):
        return await _choose_barter_only(original, *args, **kwargs)

    provider = AsyncMock(side_effect=AssertionError("test mode must not call a provider"))
    monkeypatch.setattr(commitments, "interpret_domain_affordances", controlled)
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)
    simulator = Simulator(world)
    events: list = []
    for _ in range(steps):
        events.extend(await simulator.step())
        if sum(event.event_type == "institutional_commitment_term_fulfilled" for event in events) >= 2:
            break
    return events, provider, simulator


@pytest.mark.asyncio
async def test_normal_simulator_step_completes_two_leg_barter_without_provider(monkeypatch):
    world = _barter_world()
    events, provider, _simulator = await _run_barter_witness(world, monkeypatch)

    proposal = next(event for event in events if event.event_type == "institutional_trade_proposed")
    accepted = next(event for event in events if event.event_type == "institutional_trade_accepted")
    offer = proposal.causal_payload["institutional_trade_offer"]
    assert len(offer["legs"]) == 2
    assert {leg["resource_id"] for leg in offer["legs"]} == {"grain", "medicine"}
    decisions = [event for event in events if event.fact_kind.value == "decision"]
    assert all(event.causal_payload["deltas"] == [] for event in decisions)

    commitment = world.institutional_relations.commitments[accepted.causal_payload["commitment_id"]]
    assert len(commitment.terms) == 2
    assert {term.subject.id for term in commitment.terms} == {"grain", "medicine"}
    assert {term.status.value for term in commitment.terms} == {"fulfilled"}
    transfers = [event for event in events if event.event_type == "regional_resource_transfer_completed"]
    fulfilled = [event for event in events if event.event_type == "institutional_commitment_term_fulfilled"]
    assert len(transfers) == len(fulfilled) == 2
    assert {event.causal_payload["term_id"] for event in transfers} == {term.id for term in commitment.terms}
    assert {event.causal_payload["term_id"] for event in fulfilled} == {term.id for term in commitment.terms}
    by_id = {event.id: event for event in events}

    def ancestor_types(event):
        pending = [event.id]
        found = set()
        while pending:
            event_id = pending.pop()
            if event_id in found:
                continue
            found.add(event_id)
            current = by_id.get(event_id)
            if current is not None:
                pending.extend(link.cause_event_id for link in current.causal_links)
        return {by_id[event_id].event_type for event_id in found if event_id in by_id}

    required_witness = {
        "institutional_resource_request_interpretation_decision",
        "institutional_trade_proposed",
        "institutional_resource_response_interpretation_decision",
        "institutional_trade_accepted",
        "institutional_commitment_fulfillment_interpretation_decision",
        "regional_resource_transfer_completed",
        "institutional_commitment_term_fulfilled",
    }
    assert all(required_witness <= ancestor_types(event) for event in fulfilled)
    assert all(
        f"memory:{institution_id}:{event.id}" in world.institutional_relations.memories
        for event in fulfilled
        for institution_id in commitment.party_ids
    )
    assert provider.await_count == provider.call_count == 0


@pytest.mark.asyncio
async def test_failed_normal_step_rolls_back_two_leg_barter(monkeypatch):
    world = _barter_world()
    accepted_events, provider, simulator = await _run_barter_witness(world, monkeypatch, steps=1)
    assert any(event.event_type == "institutional_trade_accepted" for event in accepted_events)
    before_stocks = {
        int(region_id): dict(world.map.regions[region_id].economy.stocks)
        for region_id in (302, 305)
    }
    before_institutional = (
        world.institutional_authority.to_dict(),
        world.institutional_knowledge.to_dict(),
        world.institutional_relations.to_dict(),
    )
    before_month = world.month_stamp
    before_event_count = world.event_manager.count()
    before_rng = random.getstate()
    before_receipts = dict(world.mechanical_language.reaction_receipts)
    attempted_events: list = []

    def fail_commit(events, _chapter):
        attempted_events.extend(events)
        return False

    monkeypatch.setattr(world.event_manager, "commit_step", fail_commit)

    with pytest.raises(EventPersistenceError):
        await simulator.step()

    assert sum(event.event_type == "regional_resource_transfer_completed" for event in attempted_events) == 2
    assert {
        int(region_id): dict(world.map.regions[region_id].economy.stocks)
        for region_id in (302, 305)
    } == before_stocks
    assert (
        world.institutional_authority.to_dict(),
        world.institutional_knowledge.to_dict(),
        world.institutional_relations.to_dict(),
    ) == before_institutional
    assert world.month_stamp == before_month
    assert world.event_manager.count() == before_event_count
    assert world.mechanical_language.reaction_receipts == before_receipts
    assert random.getstate() == before_rng
    assert provider.await_count == provider.call_count == 0


@pytest.mark.asyncio
async def test_partial_barter_fulfillment_breaches_then_remediates_only_open_leg(monkeypatch):
    """Both legs stay independent after acceptance and reuse the shared owner."""

    import src.systems.institutional_resource_commitment as commitments

    world = _barter_world()
    mode = {"value": "accept"}
    late_source_id = {"value": None}
    original = commitments.interpret_domain_affordances

    async def controlled(*args, **kwargs):
        domain = kwargs["domain"]
        actor_id = kwargs["actor_ref"].id
        options = tuple(kwargs["affordances"])
        selected = None
        if mode["value"] == "accept":
            action = {
                "institutional_resource_request": "request_reciprocal_trade",
                "institutional_resource_response": "accept_reciprocal_trade",
            }.get(domain)
            selected = next((item for item in options if item.action_kind == action), None)
        elif domain == "institutional_commitment_fulfillment" and (
            (mode["value"] == "partial" and actor_id == "302")
            or (mode["value"] == "remediate" and actor_id == late_source_id["value"])
        ):
            selected = next(
                (item for item in options if item.action_kind == "fulfill_resource_transfer_term"),
                None,
            )
        elif (
            mode["value"] == "remediate"
            and domain == "institutional_commitment_remediation"
            and actor_id == late_source_id["value"]
        ):
            selected = next(
                (item for item in options if item.action_kind == "propose_resource_transfer_remediation"),
                None,
            )
        decision = (
            DomainDecision(DomainDecisionKind.ACT, "Controlled partial barter witness.", selected.id)
            if selected is not None
            else DomainDecision(DomainDecisionKind.MAINTAIN, "Controlled no action.")
        )
        return await original(*args, **{**kwargs, "injected_decision": decision})

    provider = AsyncMock(side_effect=AssertionError("test mode must not call a provider"))
    monkeypatch.setattr(commitments, "interpret_domain_affordances", controlled)
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)
    simulator = Simulator(world)
    events = list(await simulator.step())
    accepted = next(event for event in events if event.event_type == "institutional_trade_accepted")
    commitment = world.institutional_relations.commitments[accepted.causal_payload["commitment_id"]]
    early_term = next(
        term for term in commitment.terms
        if dict(term.parameters)["source_region_id"] == "302"
    )
    late_term = next(term for term in commitment.terms if term.id != early_term.id)
    late_source_id["value"] = dict(late_term.parameters)["source_region_id"]

    # Month two fulfills only the grain sender (302); later request domains are
    # explicitly MAINTAIN, so no second trade can be opened by this fixture.
    mode["value"] = "partial"
    for _ in range(3):
        events.extend(await simulator.step())

    commitment = world.institutional_relations.commitments[commitment.id]
    early_term = next(term for term in commitment.terms if term.id == early_term.id)
    late_term = next(term for term in commitment.terms if term.id == late_term.id)
    breach = next(
        event for event in events
        if event.event_type == "institutional_commitment_term_breached"
        and event.causal_payload["term_id"] == late_term.id
    )
    assert early_term.status.value == "fulfilled"
    assert late_term.status.value == "breached"
    assert late_term.breach_event_ids == (breach.id,)
    assert sum(event.event_type == "institutional_trade_proposed" for event in events) == 1
    assert [
        event.causal_payload["term_id"]
        for event in events
        if event.event_type == "regional_resource_transfer_completed"
    ] == [early_term.id]

    mode["value"] = "remediate"
    events.extend(await simulator.step())  # independent remediation decision
    events.extend(await simulator.step())  # its later independent fulfillment

    commitment = world.institutional_relations.commitments[commitment.id]
    early_term = next(term for term in commitment.terms if term.id == early_term.id)
    late_term = next(term for term in commitment.terms if term.id == late_term.id)
    assert early_term.status.value == "fulfilled"
    assert late_term.status.value == "remediated"
    assert late_term.breach_event_ids == (breach.id,)
    term_transfers = {
        event.causal_payload["term_id"]: event
        for event in events
        if event.event_type == "regional_resource_transfer_completed"
    }
    assert set(term_transfers) == {early_term.id, late_term.id}
    assert all(
        event.causal_payload["execution"]["source_region_id"]
        == dict(next(term for term in commitment.terms if term.id == term_id).parameters)["source_region_id"]
        for term_id, event in term_transfers.items()
    )
    remediated = next(
        event for event in events
        if event.event_type == "institutional_commitment_term_remediated"
        and event.causal_payload["term_id"] == late_term.id
    )
    assert any(link.cause_event_id == breach.id and link.relation.value == "resolves" for link in remediated.causal_links)
    assert provider.await_count == provider.call_count == 0

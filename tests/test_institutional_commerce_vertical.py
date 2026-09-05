"""Focused backend coverage for reciprocal city-to-city barter."""

from types import SimpleNamespace

import pytest

from src.classes.age import Age
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.dynasty import Dynasty
from src.classes.environment.city_state import CityGovernance
from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.core.world import World
from src.classes.regional_economy import RegionalEconomyState
from src.run.load_map import load_cultivation_world_map
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.sim.simulator_engine.finalizer import validate_causal_integrity
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    AffordanceContext,
    StaleAffordanceError,
)
from src.systems.economy_reactivity import process_economy_reactivity
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institutional_memory import decision_context
from src.systems.institutional_commerce import PROPOSE_ACTION
from src.systems.institutional_resource_commitment import (
    REQUEST_DOMAIN,
    RESPONSE_DOMAIN,
)
from src.systems.time import Month, Year, create_month_stamp

TRADE_ACTIONS = {"request_reciprocal_trade", "accept_reciprocal_trade"}


def _setup(base_world, *, source_medicine_demand: float | None = 2.0):
    emperor = Avatar(
        world=base_world,
        name="Commerce Emperor",
        id="commerce-emperor",
        birth_month_stamp=0,
        age=Age(30, Realm.Qi_Refinement),
        gender=Gender.MALE,
    )
    base_world.avatar_manager.register_avatar(emperor)
    base_world.dynasty = Dynasty(1, "Test Dynasty", "", current_emperor_id=emperor.id)

    def city(region_id: int, economy: RegionalEconomyState) -> CityRegion:
        region = CityRegion(
            id=region_id,
            name=f"City {region_id}",
            desc="",
            cors=[(region_id % 10, region_id // 10)],
            economy=economy,
        )
        region.city_state.governance = CityGovernance("dynasty", "1", 1.0)
        base_world.map.regions[region_id] = region
        return region

    partner_demand = {"grain": 0.0}
    if source_medicine_demand is not None:
        partner_demand["medicine"] = source_medicine_demand
    partner = city(
        302,
        RegionalEconomyState(
            stocks={"grain": 20.0, "medicine": 0.0},
            capacities={"grain": 30.0, "medicine": 30.0},
            demand_rates=partner_demand,
            access={"grain": 1.0, "medicine": 1.0},
        ),
    )
    proposer = city(
        305,
        RegionalEconomyState(
            stocks={"grain": 0.0, "medicine": 20.0},
            capacities={"grain": 30.0, "medicine": 30.0},
            demand_rates={"grain": 2.0, "medicine": 0.0},
            access={"grain": 1.0, "medicine": 1.0},
        ),
    )
    base_world.map.set_routes((Route("trade-road", (302, 305), "road", 5, 1.0, True),))
    bootstrap_institutional_authority(base_world)
    shortage = Event(
        base_world.month_stamp,
        "City 305 could not satisfy grain demand.",
        event_type="regional_resource_shortage",
        render_params={"region_id": "305", "resource_id": "grain"},
        id="shortage:305:grain",
    )
    return partner, proposer, shortage


def _request_options(world, shortage):
    return DOMAIN_AFFORDANCES.compose(
        AffordanceContext(world, REQUEST_DOMAIN, EntityRef("region", "305"), shortage)
    )


def _select_action(action_kind):
    async def _call(_task, _template, context, **_kwargs):
        selected = next(
            (
                item
                for item in context["affordances"]
                if item["action_kind"] == action_kind
            ),
            None,
        )
        if selected is None:
            return {"decision": "maintain", "reason": "No matching option."}
        return {
            "decision": "act",
            "reason": "The grounded option is acceptable.",
            "selected_affordance_id": selected["id"],
        }

    return _call


def _trade_then(second):
    """Propose the reciprocal exchange, then let ``second`` answer it."""

    async def _call(task, template, context, **kwargs):
        if context["context"].get("role") == "proposer":
            return await _select_action(PROPOSE_ACTION)(
                task, template, context, **kwargs
            )
        return await second(task, template, context, **kwargs)

    return _call


async def _act_on_first(_task, _template, context, **_kwargs):
    if not context["affordances"]:
        return {"decision": "maintain", "reason": "Nothing grounded."}
    return {
        "decision": "act",
        "reason": "The grounded option is acceptable.",
        "selected_affordance_id": context["affordances"][0]["id"],
    }


@pytest.mark.asyncio
async def test_one_decision_offers_aid_and_trade_and_trade_opens_two_terms(base_world):
    partner, proposer, shortage = _setup(base_world)

    options = _request_options(base_world, shortage)
    assert {option.action_kind for option in options} == {
        "request_institutional_aid",
        "request_reciprocal_trade",
    }
    trade_option = next(
        option for option in options if option.action_kind == PROPOSE_ACTION
    )
    inbound, outbound = trade_option.parameters["legs"]
    # Both legs come from real deficits and surplus, bounded independently.
    assert inbound["resource_id"] == "grain" and inbound["amount"] == 2.0
    assert outbound["resource_id"] == "medicine" and outbound["amount"] == 2.0
    assert inbound["source_region_id"] == "302"
    assert outbound["source_region_id"] == "305"

    trade_call = _trade_then(_act_on_first)
    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=trade_call,
    )

    assert [event.event_type for event in events[:4]] == [
        "institutional_resource_request_interpretation_decision",
        "institutional_trade_proposed",
        "institutional_resource_response_interpretation_decision",
        "institutional_trade_accepted",
    ]
    # One stimulus, one proposer decision: no competing second dispatch.
    assert (
        [event.event_type for event in events].count(
            "institutional_resource_request_interpretation_decision"
        )
        == 1
    )
    proposal = events[1]
    offer = proposal.causal_payload["institutional_trade_offer"]
    assert set(offer) == {
        "proposer_institution_id",
        "counterparty_institution_id",
        "legs",
        "urgency",
    }
    assert offer["proposer_institution_id"] == "inst:city:305"
    assert offer["counterparty_institution_id"] == "inst:city:302"

    accepted = events[3]
    commitment = base_world.institutional_relations.commitments[
        accepted.causal_payload["commitment_id"]
    ]
    assert len(commitment.terms) == 2
    assert [term.subject.id for term in commitment.terms] == ["grain", "medicine"]
    assert [term.obligor_institution_id for term in commitment.terms] == [
        "inst:city:302",
        "inst:city:305",
    ]
    assert all(term.status.value == "active" for term in commitment.terms)
    # Accepted obligations reserve nothing and move nothing.
    assert partner.economy.stocks == {"grain": 20.0, "medicine": 0.0}
    assert proposer.economy.stocks == {"grain": 0.0, "medicine": 20.0}
    assert partner.economy.reservations == {} == proposer.economy.reservations
    validate_causal_integrity(SimpleNamespace(world=base_world), [shortage, *events])


@pytest.mark.asyncio
async def test_counterparty_refusal_is_independent_and_binds_nothing(base_world):
    partner, proposer, shortage = _setup(base_world)

    async def refuse(_task, _template, _context, **_kwargs):
        return {"decision": "maintain", "reason": "The exchange is unwelcome."}

    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_trade_then(refuse),
    )

    assert [event.event_type for event in events[:4]] == [
        "institutional_resource_request_interpretation_decision",
        "institutional_trade_proposed",
        "institutional_resource_response_interpretation_decision",
        "institutional_trade_refused",
    ]
    assert base_world.institutional_relations.commitments == {}
    assert partner.economy.stocks == {"grain": 20.0, "medicine": 0.0}
    assert proposer.economy.stocks == {"grain": 0.0, "medicine": 20.0}


@pytest.mark.asyncio
async def test_unsupported_response_identifier_refuses_nothing_and_mutates_nothing(
    base_world,
):
    partner, proposer, shortage = _setup(base_world)

    async def invalid_response(_task, _template, _context, **_kwargs):
        return {
            "decision": "act",
            "reason": "An identifier that was never offered.",
            "selected_affordance_id": "affordance:not-offered",
        }

    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_trade_then(invalid_response),
    )

    types = [event.event_type for event in events]
    assert "institutional_trade_proposed" in types
    assert "institutional_trade_refused" not in types
    assert "institutional_trade_accepted" not in types
    response_decision = events[2]
    assert response_decision.causal_payload["interpretation"]["source"] == "llm_rejected"
    assert base_world.institutional_relations.commitments == {}
    assert partner.economy.stocks == {"grain": 20.0, "medicine": 0.0}
    assert proposer.economy.stocks == {"grain": 0.0, "medicine": 20.0}


@pytest.mark.asyncio
async def test_stale_stock_between_proposal_and_acceptance_blocks_the_exchange(
    base_world,
):
    partner, proposer, shortage = _setup(base_world)
    context = AffordanceContext(
        base_world, REQUEST_DOMAIN, EntityRef("region", "305"), shortage
    )
    trade_option = next(
        option
        for option in DOMAIN_AFFORDANCES.compose(context)
        if option.action_kind == PROPOSE_ACTION
    )
    proposal = DOMAIN_AFFORDANCES.execute(
        context,
        trade_option.id,
        decision_event_id="decision:proposal",
    )
    response_context = AffordanceContext(
        base_world, RESPONSE_DOMAIN, EntityRef("region", "302"), proposal
    )
    acceptance = DOMAIN_AFFORDANCES.compose(response_context)[0]

    # The counterparty's own surplus disappears while it is still deciding.
    partner.economy.set_stock("grain", 1.0)
    assert DOMAIN_AFFORDANCES.compose(response_context) == ()
    with pytest.raises(StaleAffordanceError):
        DOMAIN_AFFORDANCES.execute(
            response_context,
            acceptance.id,
            decision_event_id="decision:acceptance",
        )
    assert base_world.institutional_relations.commitments == {}
    assert partner.economy.stocks["grain"] == 1.0
    assert proposer.economy.stocks["medicine"] == 20.0

    # A reserved donor buffer is equally not shippable surplus.
    partner.economy.set_stock("grain", 20.0)
    partner.economy.reserve_stock("project:wall", "grain", 19.0)
    assert DOMAIN_AFFORDANCES.compose(response_context) == ()


@pytest.mark.asyncio
async def test_route_and_authority_loss_remove_the_offer_without_mutation(base_world):
    partner, proposer, shortage = _setup(base_world)
    assert any(
        option.action_kind == PROPOSE_ACTION
        for option in _request_options(base_world, shortage)
    )

    base_world.map.routes["trade-road"].update_runtime(enabled=False)
    assert not any(
        option.action_kind == PROPOSE_ACTION
        for option in _request_options(base_world, shortage)
    )
    base_world.map.routes["trade-road"].update_runtime(enabled=True)

    partner.city_state.governance = CityGovernance("dynasty", "999", 1.0)
    assert not any(
        option.action_kind == PROPOSE_ACTION
        for option in _request_options(base_world, shortage)
    )
    assert partner.economy.stocks == {"grain": 20.0, "medicine": 0.0}
    assert proposer.economy.stocks == {"grain": 0.0, "medicine": 20.0}


def test_unknown_partner_demand_is_not_a_zero_need_and_blocks_export(base_world):
    _partner, _proposer, shortage = _setup(base_world, source_medicine_demand=None)

    assert not any(
        option.action_kind == PROPOSE_ACTION
        for option in _request_options(base_world, shortage)
    )


def test_offer_is_only_enumerated_for_the_shortage_owner(base_world):
    _partner, _proposer, shortage = _setup(base_world)

    options = DOMAIN_AFFORDANCES.compose(
        AffordanceContext(
            base_world, REQUEST_DOMAIN, EntityRef("region", "302"), shortage
        )
    )
    assert not any(option.action_kind == PROPOSE_ACTION for option in options)


def _canonical_world() -> tuple[World, CityRegion, CityRegion, Event]:
    """A world on the shipped map, so a save can be reloaded and re-read."""

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
    partner = world.map.regions[302]
    proposer = world.map.regions[305]
    assert isinstance(partner, CityRegion) and isinstance(proposer, CityRegion)
    partner.city_state.governance = CityGovernance("dynasty", "1", 1.0)
    proposer.city_state.governance = CityGovernance("dynasty", "1", 1.0)
    partner.economy = RegionalEconomyState(
        stocks={"grain": 20.0, "medicine": 0.0},
        capacities={"grain": 30.0, "medicine": 30.0},
        demand_rates={"grain": 0.0, "medicine": 2.0},
        access={"grain": 1.0, "medicine": 1.0},
    )
    proposer.economy = RegionalEconomyState(
        stocks={"grain": 0.0, "medicine": 20.0},
        capacities={"grain": 30.0, "medicine": 30.0},
        demand_rates={"grain": 2.0, "medicine": 0.0},
        access={"grain": 1.0, "medicine": 1.0},
    )
    bootstrap_institutional_authority(world)
    shortage = Event(
        world.month_stamp,
        "City 305 could not satisfy grain demand.",
        event_type="regional_resource_shortage",
        render_params={"region_id": "305", "resource_id": "grain"},
        id="shortage:305:grain:canonical",
    )
    return world, partner, proposer, shortage


@pytest.mark.asyncio
async def test_both_legs_transfer_independently_and_survive_save_load(tmp_path):
    world, partner, proposer, shortage = _canonical_world()
    opening = await process_economy_reactivity(
        world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_trade_then(_act_on_first),
    )
    assert world.event_manager.commit_step([shortage, *opening])
    commitment_id = next(
        event for event in opening if event.event_type == "institutional_trade_accepted"
    ).causal_payload["commitment_id"]

    world.month_stamp = world.month_stamp + 1
    fulfilling = await process_economy_reactivity(
        world,
        current_events=[],
        invalidations=DomainInvalidationQueue(),
        llm_call=_act_on_first,
    )
    assert world.event_manager.commit_step(fulfilling)

    transfers = [
        event
        for event in fulfilling
        if event.event_type == "regional_resource_transfer_completed"
    ]
    fulfilled = [
        event
        for event in fulfilling
        if event.event_type == "institutional_commitment_term_fulfilled"
    ]
    assert len(transfers) == len(fulfilled) == 2
    commitment = world.institutional_relations.commitments[commitment_id]
    assert {term.status.value for term in commitment.terms} == {"fulfilled"}
    assert {event.causal_payload["term_id"] for event in fulfilled} == {
        term.id for term in commitment.terms
    }
    # Two real reciprocal shipments in opposite directions and resources.
    assert partner.economy.stocks == {"grain": 18.0, "medicine": 2.0}
    assert proposer.economy.stocks == {"grain": 2.0, "medicine": 18.0}
    validate_causal_integrity(SimpleNamespace(world=world), fulfilling)

    save_path = tmp_path / "commerce.json"
    ok, _ = save_game(world, Simulator(world), [], save_path=save_path)
    assert ok
    loaded_world, _, _ = load_game(save_path)
    reloaded = loaded_world.institutional_relations.commitments[commitment_id]
    assert [
        (term.id, term.subject.id, term.status.value, dict(term.parameters))
        for term in reloaded.terms
    ] == [
        (term.id, term.subject.id, term.status.value, dict(term.parameters))
        for term in commitment.terms
    ]
    for event in fulfilled:
        stored = loaded_world.event_manager.get_event_by_id(event.id)
        assert stored is not None
        assert {link.cause_event_id for link in stored.causal_links} == {
            link.cause_event_id for link in event.causal_links
        }


@pytest.mark.asyncio
async def test_answered_proposal_never_binds_a_second_commitment(base_world):
    _partner, _proposer, shortage = _setup(base_world)
    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_trade_then(_act_on_first),
    )
    proposal = next(
        event for event in events if event.event_type == "institutional_trade_proposed"
    )
    response_context = AffordanceContext(
        base_world, RESPONSE_DOMAIN, EntityRef("region", "302"), proposal
    )
    assert DOMAIN_AFFORDANCES.compose(response_context) == ()

    # The same proposal stays answered once its terms are no longer open.
    commitment = next(iter(base_world.institutional_relations.commitments.values()))
    for term in commitment.terms:
        base_world.institutional_relations.fulfill_term(
            commitment.id,
            term.id,
            settled_month=int(base_world.month_stamp),
            event_id=proposal.id,
            authority_state=base_world.institutional_authority,
        )
    assert DOMAIN_AFFORDANCES.compose(response_context) == ()
    assert len(base_world.institutional_relations.commitments) == 1


@pytest.mark.asyncio
async def test_test_mode_negotiates_without_any_provider(base_world):
    _partner, _proposer, shortage = _setup(base_world)
    base_world.run_config_snapshot = {
        "test_mode": True,
        "domain_affordance_action_urgency_threshold": 1.0,
    }

    async def forbidden(*_args, **_kwargs):
        raise AssertionError("test mode must not call a provider")

    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=forbidden,
    )

    negotiation_decisions = [
        event
        for event in events
        if event.fact_kind is FactKind.DECISION
        and str((event.render_params or {}).get("domain", "")).startswith(
            "institutional_"
        )
        and not str((event.render_params or {}).get("domain", "")).startswith(
            "institutional_relationship"
        )
    ]
    assert negotiation_decisions
    assert {
        event.causal_payload["interpretation"]["source"]
        for event in negotiation_decisions
    } == {"rule"}


@pytest.mark.asyncio
async def test_refused_exchange_stays_legible_in_institutional_memory(base_world):
    _partner, _proposer, shortage = _setup(base_world)

    async def refuse(_task, _template, _context, **_kwargs):
        return {"decision": "maintain", "reason": "The exchange is unwelcome."}

    events = await process_economy_reactivity(
        base_world,
        current_events=[shortage],
        invalidations=DomainInvalidationQueue(),
        llm_call=_trade_then(refuse),
    )
    proposal = next(
        event for event in events if event.event_type == "institutional_trade_proposed"
    )
    refusal = next(
        event for event in events if event.event_type == "institutional_trade_refused"
    )
    assert refusal.render_params == {
        "proposer_region_id": "305",
        "counterparty_region_id": "302",
        "inbound_resource_id": "grain",
        "inbound_amount": 2.0,
        "outbound_resource_id": "medicine",
        "outbound_amount": 2.0,
    }

    context = decision_context(
        base_world,
        "inst:city:305",
        event_overlays=(proposal, refusal),
    )
    remembered = next(
        fact for fact in context["known_facts"] if fact["event_id"] == refusal.id
    )
    # A refusal opens no commitment, so who declined and what was on the table
    # must be readable from the refusal's own grounded render params.
    assert remembered["render_params"] == refusal.render_params

    proposal_fact = next(
        (fact for fact in context["known_facts"] if fact["event_id"] == proposal.id),
        None,
    )
    if proposal_fact is not None:
        assert [
            (leg["resource_id"], leg["source_region_id"])
            for leg in proposal_fact["institutional_metadata"]["legs"]
        ] == [("grain", "302"), ("medicine", "305")]

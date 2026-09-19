"""Focused causal coverage for productive-site conveyance.

Conveyance deliberately has no KnowledgeState notice: the seller's decision
receipt is the canonical, actor-addressed offer and the buyer reconstructs the
same engine-owned option from that receipt.  Persisting another copy would
create a second source of truth for the exact site, bindings, and terms.
"""

import copy

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.core.infrastructure import validate_infrastructure
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.economy.expansion import ExpansionProject
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import _delta, produce_monthly
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world
from src.sim.medieval.productive_conveyance import (
    accept_site_conveyance,
    conveyance_acceptance_options,
    productive_site_conveyance_options,
    propose_site_conveyance,
    record_conveyance_acceptance,
)


SELLER = EntityRef("organization", "oficios-da-serra")
BUYER = EntityRef("polity", "escarlia")
FACILITY_ID = "works:oficinas-da-serra"


def _staged_world():
    world = create_medieval_world(73)
    seller_option = next(
        option for option in productive_site_conveyance_options(world, SELLER)
        if option.buyer_ref == BUYER
    )
    proposal = propose_site_conveyance(world, seller_option.id)
    acceptance_option = conveyance_acceptance_options(world, BUYER)[0]
    acceptance = record_conveyance_acceptance(world, acceptance_option.id, BUYER)
    return world, seller_option, proposal, acceptance_option, acceptance


def test_state_transition_without_delta_is_rejected_as_non_material():
    world = create_medieval_world(73)
    with pytest.raises(ValueError, match="material delta"):
        record_event(world, "invalid_material_claim", "Texto sem mudança canônica.",
                     fact_kind=FactKind.STATE_TRANSITION, deltas=())


def test_buyer_reconstitutes_the_exact_seller_offer_without_a_knowledge_notice():
    world = create_medieval_world(73)
    seller_option = next(
        option for option in productive_site_conveyance_options(world, SELLER)
        if option.buyer_ref == BUYER
    )
    proposal = propose_site_conveyance(world, seller_option.id)

    acceptance_option = conveyance_acceptance_options(world, BUYER)[0]
    assert acceptance_option.site_id == seller_option.site_id
    assert acceptance_option.facility_id == seller_option.facility_id
    assert acceptance_option.seller_ref == seller_option.seller_ref
    assert acceptance_option.buyer_ref == seller_option.buyer_ref
    assert acceptance_option.stock_id == seller_option.stock_id
    assert acceptance_option.payroll_account_id == seller_option.payroll_account_id
    assert proposal.fact_kind is FactKind.DECISION
    assert proposal.causal_origin is CausalOrigin.ACTOR_DECISION
    assert proposal.deltas == ()
    assert proposal.decision == seller_option.decision()
    assert acceptance_option.decision() == {
        "action": "accept_productive_site_conveyance",
        "actor_ref": BUYER.to_dict(),
        "selected_affordance_id": acceptance_option.id,
    }
    assert not hasattr(world.knowledge, "productive_site_conveyances")


def test_a_site_with_a_second_production_line_cannot_be_conveyed():
    world, seller_option, _, acceptance_option, acceptance = _staged_world()
    facility = world.economy.facilities[FACILITY_ID]
    # A commissioned line shares its anchor's site; handing the site over while
    # rebinding a single facility would leave the other one owned by the seller.
    line = facility.model_copy(update={"id": f"line:{facility.site_id}:{facility.recipe_id}"})
    world.economy.facilities[line.id] = line
    world.economy.validate(world)

    assert productive_site_conveyance_options(world, SELLER) == ()
    assert conveyance_acceptance_options(world, BUYER) == ()
    before_sites = copy.deepcopy(world.map.infrastructure_sites)
    before_facilities = copy.deepcopy(world.economy.facilities)
    with pytest.raises(ValueError):
        accept_site_conveyance(world, acceptance_option.id, decision_event_id=acceptance.id)
    assert world.map.infrastructure_sites == before_sites
    assert world.economy.facilities == before_facilities
    world.economy.validate(world)
    validate_infrastructure(world)


def test_llm_interpretation_cannot_be_used_as_conveyance_consent():
    world, _, proposal, acceptance_option, acceptance = _staged_world()
    # A text interpretation may repeat the exact option, but it is not an
    # actor decision and therefore cannot reach the material owner.
    interpreted = record_event(
        world,
        "productive_site_conveyance_interpreted",
        "A interpretação descreveu a transferência como provável.",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        decision=acceptance.decision,
        cause_ids=(proposal.id,),
    )
    before_sites = copy.deepcopy(world.map.infrastructure_sites)
    before_facilities = copy.deepcopy(world.economy.facilities)
    with pytest.raises(ValueError):
        accept_site_conveyance(world, acceptance_option.id, decision_event_id=interpreted.id)
    assert world.map.infrastructure_sites == before_sites
    assert world.economy.facilities == before_facilities


def test_conveyance_changes_only_canonical_bindings_and_later_production_uses_buyer():
    world, seller_option, proposal, acceptance_option, acceptance = _staged_world()
    site = world.map.infrastructure_sites[seller_option.site_id]
    facility = world.economy.facilities[seller_option.facility_id]
    old_stock_id = facility.stock_id
    old_payroll_account_id = facility.payroll_account_id
    stocks_before = copy.deepcopy(world.economy.stocks)
    accounts_before = copy.deepcopy(world.economy.accounts)

    event = accept_site_conveyance(world, acceptance_option.id, decision_event_id=acceptance.id)

    assert event.fact_kind is FactKind.STATE_TRANSITION
    assert event.causal_origin is CausalOrigin.DETERMINISTIC
    assert event.deltas
    assert any(link.cause_event_id == proposal.id for link in event.causal_links)
    assert any(link.cause_event_id == acceptance.id for link in event.causal_links)
    assert world.economy.stocks == stocks_before
    assert world.economy.accounts == accounts_before
    assert site.owner_ref == BUYER
    assert site.maintainer_ref == BUYER
    assert site.last_event_id == event.id
    facility = world.economy.facilities[seller_option.facility_id]
    assert facility.stock_id == seller_option.stock_id
    assert facility.stock_id != old_stock_id
    assert facility.payroll_account_id == seller_option.payroll_account_id
    assert facility.payroll_account_id != old_payroll_account_id
    assert facility.last_event_id == event.id

    # Production is authorized by the current buyer-owned binding.  It may
    # produce other facilities in the same call, so inspect this line only.
    before_goods = copy.deepcopy(world.economy.stocks[seller_option.stock_id].goods)
    produce_monthly(world)
    buyer_facility = world.economy.facilities[FACILITY_ID]
    assert buyer_facility.last_batches > 0
    assert world.economy.stocks[buyer_facility.stock_id].owner_ref == BUYER
    assert world.economy.stocks[buyer_facility.stock_id].goods != before_goods
    world.economy.validate(world)
    validate_infrastructure(world)


def test_save_load_preserves_receipts_and_recomposes_no_transient_affordance(tmp_path):
    world, seller_option, _, acceptance_option, acceptance = _staged_world()
    event = accept_site_conveyance(world, acceptance_option.id, decision_event_id=acceptance.id)
    path = tmp_path / "conveyance.mws"
    save_world(world, path)
    resumed = load_world(path)

    assert [item.event_type for item in resumed.events] == [
        "productive_site_conveyance_proposed",
        "productive_site_conveyance_accepted",
        "productive_site_conveyed",
    ]
    assert resumed.map.infrastructure_sites[seller_option.site_id].last_event_id == event.id
    assert resumed.economy.facilities[FACILITY_ID].stock_id == seller_option.stock_id
    assert resumed.economy.facilities[FACILITY_ID].payroll_account_id == seller_option.payroll_account_id
    assert productive_site_conveyance_options(resumed, SELLER) == ()
    assert conveyance_acceptance_options(resumed, BUYER) == ()


@pytest.mark.parametrize("mutation", ["invented", "stale", "foreign_stock", "authority", "active_project"])
def test_rejected_conveyance_is_atomic_for_stale_or_conflicting_current_state(mutation):
    world, seller_option, _, acceptance_option, acceptance = _staged_world()
    before_events = copy.deepcopy(world.events)
    before_sites = copy.deepcopy(world.map.infrastructure_sites)
    before_facilities = copy.deepcopy(world.economy.facilities)
    before_stocks = copy.deepcopy(world.economy.stocks)
    before_accounts = copy.deepcopy(world.economy.accounts)

    option_id = acceptance_option.id
    decision_id = acceptance.id
    if mutation == "invented":
        invented = record_event(
            world,
            "productive_site_conveyance_accepted",
            "Uma decisão inválida tentou inventar os termos da transferência.",
            fact_kind=FactKind.DECISION,
            decision={**acceptance.decision, "option_id": "conveyance:invented"},
        )
        option_id = "conveyance:invented"
        decision_id = invented.id
    elif mutation == "stale":
        world.clock = world.clock.advance(1)
    elif mutation == "foreign_stock":
        stock = world.economy.stocks[seller_option.stock_id]
        other_settlement = next(
            item.id for item in world.society.settlements.values()
            if item.id != stock.location_id
        )
        world.economy.stocks[stock.id] = stock.model_copy(update={"location_id": other_settlement})
    elif mutation == "authority":
        office = world.authority.offices["office:polity:escarlia"]
        world.authority.offices[office.id] = office.model_copy(update={"scopes": ("taxation",)})
    elif mutation == "active_project":
        decision = record_event(
            world,
            "expansion_decided",
            "Uma obra concorrente foi decidida materialmente.",
            fact_kind=FactKind.DECISION,
            decision={
                "action": "expand",
                "actor_ref": SELLER.to_dict(),
                "facility_id": FACILITY_ID,
                "blueprint_id": "workshop-extension",
            },
        )
        started = record_event(
            world,
            "expansion_started",
            "Projeto concorrente em andamento.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("expansion", f"expansion:{decision.id}", "stage", None, "waiting"),),
            cause_ids=(decision.id,),
        )
        world.economy.expansions[f"expansion:{decision.id}"] = ExpansionProject(
            id=f"expansion:{decision.id}",
            facility_id=FACILITY_ID,
            blueprint_id="workshop-extension",
            owner_ref=SELLER,
            decision_event_id=decision.id,
            started_day=world.clock.absolute_day,
            last_event_id=started.id,
        )

    with pytest.raises(ValueError):
        accept_site_conveyance(world, option_id, decision_event_id=decision_id)

    # The fixture mutations above may append their own decision/receipt; the
    # executor itself must append no material conveyance event on rejection.
    if mutation not in {"invented", "active_project"}:
        assert world.events == before_events
    assert world.map.infrastructure_sites == before_sites
    assert world.economy.facilities == before_facilities
    if mutation != "foreign_stock":
        assert world.economy.stocks == before_stocks
    if mutation != "authority":
        assert world.economy.accounts == before_accounts
    assert not any(item.event_type == "productive_site_conveyed" for item in world.events)

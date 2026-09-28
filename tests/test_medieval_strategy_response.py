"""A known occupation may create intent, never an automatic army."""

import asyncio
import json

import pytest

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.economy.models import Stock
from src.classes.governance.authority import headquarters_holder, political_holder
from src.classes.governance.knowledge import settlement_report_id
from src.classes.governance.knowledge import campaign_supply_notice_id
from src.classes.governance.models import CampaignSupplyNotice
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _causes, _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.force import raise_detachment
from src.sim.medieval.field_engagement import _fatigue_level
from src.sim.medieval.force import detect_force_standoffs
from src.sim.medieval.force_contact_policy import review_force_contacts, review_id as force_contact_review_id
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.strategy_response import (REVIEW_KIND, defense_action_options,
                                                 adopt_occupied_settlement_defense,
                                                 defense_adoption_options,
                                                 review_strategy_responses_with_provider,
                                                 schedule_campaign_logistics_review)
from tests.medieval_ai_helpers import provider_selection_stub
from tests.test_medieval_field_engagement import add_column
from src.systems.calendar_agenda import ScheduledSituation


OWNER = EntityRef("polity", "auren")
OCCUPIER = EntityRef("polity", "escarlia")
SOURCE = "campomanso"
TARGET = "pedraclara"


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def occupied_response_world():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == SOURCE)
    soldiers_id = f"pop:{SOURCE}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 20})
    occupation = record_event(
        world, "test_strategy_occupation", "Fixture factual de ocupação observável.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "strategy_response_fixture",
            "source_refs": [{"kind": "scenario", "id": "strategy_response_fixture"},
                            {"kind": "settlement", "id": TARGET}],
            "observed_day": world.clock.absolute_day}},
        deltas=(_delta("settlement", TARGET, "occupier_id", None, OCCUPIER.id),))
    world.society.set_occupation(TARGET, OCCUPIER.id)
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    report = world.knowledge.settlement_report(OWNER, TARGET)
    assert report is not None and report.occupier_id == OCCUPIER.id
    return world, occupation.id, report


def choose_first(monkeypatch):
    async def call_llm_json(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        if all(item["id"].startswith("detachment-command-appoint:")
               for item in payload["choices"]):
            return {"selected_id": ai_decider.NO_ACTION}
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


def authorize_defense(world):
    due = tick(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    order = next(event for event in world.events
                 if event.event_type == "strategy_defense_political_ordered")
    assert order.causal_origin == CausalOrigin.ACTOR_DECISION
    source = order.causal_payload["decision_source"]
    assert source["kind"] == "provider"
    assert source["receipt_event_id"] in {link.cause_event_id for link in order.causal_links}
    assert not world.society.detachments


def test_political_no_action_cannot_mobilize_or_substitute_headquarters(monkeypatch):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))

    async def no_action(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    before = world_snapshot(world)
    assert not asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    refusal = next(event for event in world.events if event.event_type == "strategy_defense_political_declined")
    assert refusal.decision["actor_ref"] == political_holder(world, OWNER).to_dict()
    assert refusal.causal_origin == CausalOrigin.ACTOR_DECISION
    assert refusal.decision["selected_affordance_id"] == ai_decider.NO_ACTION
    assert refusal.causal_payload["decision_source"]["kind"] == "provider"
    assert not any(event.event_type == "strategy_defense_force_decided" for event in world.events)
    assert world.strategy.plans[plan.id].stage == "adopted"
    assert world_snapshot(world)["economy"] == before["economy"]
    assert not world.society.detachments


def test_pending_political_order_survives_save_before_headquarters_turn(monkeypatch, tmp_path):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    authorize_defense(world)
    order = next(event for event in world.events
                 if event.event_type == "strategy_defense_political_ordered")
    path = tmp_path / "pending-political-order.mws"
    save_world(world, path)
    world = load_world(path)
    prompts = []

    async def choose_and_capture(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        prompts.append(payload)
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_and_capture)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    headquarters_prompt = next(item for item in prompts
                               if item["you_are"] == headquarters_holder(world, OWNER).to_dict())
    assert headquarters_prompt["situation"]["political_order"] == {
        "event_id": order.id,
        "issued_day": order.day,
        "issuer_ref": political_holder(world, OWNER).to_dict(),
        "authorized_action": "prepare_defense",
        "operational_plan_id": next(iter(world.strategy.plans)),
    }
    decision = next(event for event in world.events if event.event_type == "strategy_defense_force_decided")
    order = next(event for event in world.events if event.event_type == "strategy_defense_political_ordered")
    assert order.id in {link.cause_event_id for link in decision.causal_links}
    assert world.society.detachments


def test_same_person_cannot_be_political_principal_and_headquarters(monkeypatch):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    authorize_defense(world)
    office = world.authority.offices["office:polity:auren:headquarters"]
    world.authority.offices[office.id] = office.model_copy(update={"holder_ref": political_holder(world, OWNER)})
    assert headquarters_holder(world, OWNER) is None
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    assert not world.society.detachments


def test_provider_adopts_then_existing_raise_marches_with_causal_chain(monkeypatch):
    world, occupation_id, report = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2, "ai_max_calls": 10})
    choose_first(monkeypatch)

    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))
    objective = world.strategy.objectives[plan.objective_id]
    assert objective.kind == "defend_occupied_settlement" and plan.stage == "adopted"
    adoption = next(event for event in world.events if event.event_type == "strategy_defense_adopted")
    assert report.event_id in {link.cause_event_id for link in adoption.causal_links}
    assert occupation_id not in {link.cause_event_id for link in adoption.causal_links}
    assert not world.society.detachments

    authorize_defense(world)
    due = tick(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    raised = next(item for item in world.society.detachments.values() if item.owner_ref == OWNER)
    assert raised.stage == "marching" and raised.destination_id == TARGET
    assert world.strategy.plans[plan.id].stage == "mobilized"
    assert world.strategy.plans[plan.id].detachment_id == raised.id
    force_decision = next(event for event in world.events if event.event_type == "strategy_defense_force_decided")
    political = next(event for event in world.events if event.event_type == "strategy_defense_political_ordered")
    for decision in (force_decision, political):
        assert decision.causal_origin == CausalOrigin.ACTOR_DECISION
        source = decision.causal_payload["decision_source"]
        assert source["kind"] == "provider"
        assert source["receipt_event_id"] in {link.cause_event_id for link in decision.causal_links}
    material = next(event for event in world.events if event.event_type == "detachment_raised")
    headquarters = headquarters_holder(world, OWNER)
    own_briefing = world.knowledge.settlement_report(headquarters, TARGET)
    assert headquarters.kind == "character" and headquarters != OWNER
    assert force_decision.decision["actor_ref"] == headquarters.to_dict()
    assert force_decision.decision["institution_ref"] == OWNER.to_dict()
    assert force_decision.decision["operational_plan_id"] == plan.id
    assert political.decision["actor_ref"] == political_holder(world, OWNER).to_dict()
    assert political.day < force_decision.day
    assert political.id in {link.cause_event_id for link in force_decision.causal_links}
    assert own_briefing.event_id in {link.cause_event_id for link in force_decision.causal_links}
    assert force_decision.id in {link.cause_event_id for link in material.causal_links}
    assert all(delta.owner_kind not in {"stock", "account", "detachment"} for delta in adoption.deltas)


def test_one_campaign_reaches_named_commander_after_distinct_policy_and_hq_decisions(monkeypatch):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 32,
                                                   "ai_max_calls": 100})
    choose_first(monkeypatch)

    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))
    authorize_defense(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    column = next(item for item in world.society.detachments.values() if item.owner_ref == OWNER)
    while column.stage == "marching":
        tick(world)
        column = world.society.detachments[column.id]
    assert column.location_id == TARGET

    resident = next(item for item in world.society.population.values()
                    if item.settlement_id == "ferroalto")
    rival_group_id = f"pop:ferroalto:{resident.people}:soldier"
    world.society.population[rival_group_id] = resident.model_copy(
        update={"id": rival_group_id, "occupation": "soldier", "count": 1})
    rival, _ = add_column(world, rival_group_id, identity="detachment:strategy-contact-rival",
                          owner=OCCUPIER, count=20, location_id=TARGET)
    detect_force_standoffs(world, rival.id)
    # The co-presence receipt creates one private notice for each institution.
    from src.classes.governance.knowledge import force_contact_notice_id
    standoff = next(item for item in world.society.force_standoffs.values()
                    if set(item.detachment_ids) == {column.id, rival.id})
    notice = world.knowledge.force_contact_notices[force_contact_notice_id(standoff.id, OWNER)]
    commander = world.society.characters["character:002"]
    world.society.characters[commander.id] = commander.model_copy(update={"location_id": TARGET})
    asked = []

    async def choose_campaign_actor(_world, actor, _situation, choices, **_kwargs):
        asked.append(actor)
        if actor == OWNER:
            return next(item["id"] for item in choices if item["id"].startswith("detachment-command-appoint:"))
        assert actor == EntityRef("character", commander.id)
        return next(item["id"] for item in choices if ":press:" in item["id"])

    monkeypatch.setattr(ai_decider, "select_option", provider_selection_stub(choose_campaign_actor))
    due_contact = tick(world)
    contact = next(item for item in due_contact if item.id == force_contact_review_id(notice.id))
    asyncio.run(review_force_contacts(world, (contact,)))
    appointed = world.society.detachment_commands[column.id]
    assert appointed.character_id == commander.id
    due_command = tick(world)
    assert any(item.kind == "detachment_command_review" for item in due_command)
    asyncio.run(review_force_contacts(world, due_command))

    policy_decision = next(item for item in world.events
                           if item.event_type == "strategy_defense_political_ordered")
    headquarters_decision = next(item for item in world.events
                                 if item.event_type == "strategy_defense_force_decided")
    command_decision = next(item for item in world.events
                            if item.event_type == "detachment_commander_decided")
    assert policy_decision.decision["actor_ref"] == political_holder(world, OWNER).to_dict()
    assert headquarters_decision.decision["actor_ref"] == headquarters_holder(world, OWNER).to_dict()
    assert command_decision.decision["actor_ref"] == EntityRef("character", commander.id).to_dict()
    assert policy_decision.day < headquarters_decision.day < command_decision.day
    assert notice.event_id in {link.cause_event_id for link in command_decision.causal_links}
    assert appointed.last_event_id in {link.cause_event_id for link in command_decision.causal_links}
    assert world.strategy.plans[plan.id].detachment_id == column.id
    assert asked == [OWNER, EntityRef("character", commander.id)]


def test_qg_can_withdraw_after_a_real_delay_is_resolved_but_not_with_open_supply(monkeypatch):
    from src.sim.medieval.force import campaign_logistics_withdrawal_options

    async def build_present_column():
        world, _, _ = occupied_response_world()
        world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 8,
                                                       "ai_max_calls": 32})
        choose_first(monkeypatch)
        await review_strategy_responses_with_provider(world, allow_adoptions=True)
        plan = next(iter(world.strategy.plans.values()))
        due = tick(world)
        assert await review_strategy_responses_with_provider(world, due)
        assert any(event.event_type == "strategy_defense_political_ordered" for event in world.events)
        due = tick(world)
        assert await review_strategy_responses_with_provider(world, due)
        plan = world.strategy.plans[plan.id]
        column = world.society.detachments[plan.detachment_id]
        while column.stage == "marching":
            tick(world)
            column = world.society.detachments[column.id]
        return world, plan, column

    world, plan, column = asyncio.run(build_present_column())
    headquarters = headquarters_holder(world, OWNER)
    delay = record_event(world, "cargo_delayed", "A remessa foi atrasada por capacidade logística real.",
                         fact_kind=FactKind.OCCURRENCE,
                         cause_ids=(column.last_event_id,))
    opened_id = f"event:{len(world.events) + 1}"
    notice_id = campaign_supply_notice_id(column.id, opened_id)
    opened = record_event(
        world, "campaign_supply_observed", "A instituição recebeu a leitura do atraso na própria campanha.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("campaign_supply_notice", notice_id, "state", None, "open"),),
        cause_ids=_causes(delay.id, column.last_event_id))
    closed = record_event(
        world, "campaign_supply_lapsed", "A remessa atrasada foi resolvida sem nova obrigação pendente.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("campaign_supply_notice", notice_id, "state", "open", "lapsed"),),
        cause_ids=(opened.id, delay.id))
    world.knowledge.campaign_supply_notices[notice_id] = CampaignSupplyNotice(
        id=notice_id, recipient_ref=OWNER, detachment_id=column.id, settlement_id=column.location_id,
        threshold=column.provisions + 1, observed_provisions=column.provisions,
        event_id=opened.id, learned_day=opened.day, state="lapsed", last_event_id=closed.id)
    review_ids = schedule_campaign_logistics_review(world, column.id)
    assert review_ids == (f"strategy-response-review:{plan.id}",)
    assert world.agenda.get(review_ids[0]).due_day == world.clock.absolute_day + 1

    options = campaign_logistics_withdrawal_options(world, OWNER, plan.id)
    assert options
    # A live, still-undispatched request may be lapsed by an explicit QG
    # withdrawal; it must not prevent the actor from choosing to leave.
    pending_id = f"event:{len(world.events) + 1}"
    pending_notice_id = campaign_supply_notice_id(column.id, pending_id)
    pending_event = record_event(
        world, "campaign_supply_observed", "A nova necessidade aguarda uma decisão do QG.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("campaign_supply_notice", pending_notice_id, "state", None, "open"),),
        cause_ids=(delay.id,))
    world.knowledge.campaign_supply_notices[pending_notice_id] = CampaignSupplyNotice(
        id=pending_notice_id, recipient_ref=OWNER, detachment_id=column.id,
        settlement_id=column.location_id, threshold=column.provisions + 1,
        observed_provisions=column.provisions, event_id=pending_event.id,
        learned_day=pending_event.day, last_event_id=pending_event.id)
    options = campaign_logistics_withdrawal_options(world, OWNER, plan.id)
    assert options

    option = options[0]
    situation = ScheduledSituation(f"strategy-response-review:{plan.id}", REVIEW_KIND,
                                   world.clock.absolute_day)
    async def choose_withdraw(_world, actor, _context, choices, **_kwargs):
        assert actor == headquarters
        assert option.id in {item["id"] for item in choices}
        return option.id

    monkeypatch.setattr(ai_decider, "select_option", provider_selection_stub(choose_withdraw))
    assert asyncio.run(review_strategy_responses_with_provider(world, (situation,)))
    returned = world.society.detachments[column.id]
    assert returned.stage == "marching"
    assert returned.destination_id == option.destination_id
    assert world.strategy.plans[plan.id].stage == "withdrawn"
    assert world.knowledge.campaign_supply_notices[pending_notice_id].state == "lapsed"
    decision = next(event for event in reversed(world.events)
                    if event.event_type == "strategy_defense_logistics_review_decided")
    movement = next(event for event in reversed(world.events)
                    if event.event_type == "detachment_withdrawal_started")
    assert decision.id in {link.cause_event_id for link in movement.causal_links}
    assert delay.id in {link.cause_event_id for link in world.event_index()[
        world.strategy.plans[plan.id].last_event_id].causal_links}


def test_actual_delayed_campaign_cargo_reaches_qg_withdrawal_turn(monkeypatch, tmp_path):
    from src.sim.medieval.campaign_supply import (campaign_stock_id, observe_campaign_supply_needs,
                                                   review_campaign_supplies, _transition_notice)
    from src.sim.medieval.dated import resolve_dated
    from src.sim.medieval.logistics import _record_parcel, open_order

    async def scenario():
        world, _, _ = occupied_response_world()
        world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 8,
                                                       "ai_max_calls": 32})
        choose_first(monkeypatch)
        await review_strategy_responses_with_provider(world, allow_adoptions=True)
        plan = next(iter(world.strategy.plans.values()))
        await review_strategy_responses_with_provider(world, tick(world))
        await review_strategy_responses_with_provider(world, tick(world))
        plan = world.strategy.plans[plan.id]
        column = world.society.detachments[plan.detachment_id]
        while column.stage == "marching":
            tick(world)
            column = world.society.detachments[column.id]

        pressure = record_event(
            world, "campaign_supply_fixture_pressure", "Fixture pressiona a reserva real da coluna.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("detachment", column.id, "provisions", column.provisions, 3),),
            cause_ids=(column.last_event_id,))
        column = column.model_copy(update={"provisions": 3, "last_event_id": pressure.id})
        world.society.detachments[column.id] = column
        notice = next(item for item in observe_campaign_supply_needs(world) if item.detachment_id == column.id)
        campaign_stock = world.economy.stocks[campaign_stock_id(column.id)]
        source_id = "stock:actual-campaign-delay-source"
        world.economy.stocks[source_id] = Stock(
            id=source_id, owner_ref=OWNER, location_id=column.location_id, capacity=1000,
            goods={"food": 500}, last_event_ids={"food": pressure.id})

        def open_supply(notice, suffix):
            headquarters = headquarters_holder(world, OWNER)
            decision = record_event(
                world, "campaign_supply_decided", "O QG autorizou uma remessa de campanha.",
                fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                causal_payload={"decision_source": {"kind": "api"}},
                decision={"action": "campaign_supply_test", "actor_ref": headquarters.to_dict(),
                          "selected_affordance_id": f"campaign-supply-test:{suffix}"},
                cause_ids=(notice.event_id,))
            quantity = 1 if suffix == "first" else 15
            order = open_order(world, source_id, campaign_stock.id, "food", quantity, (),
                               decision_ids=(decision.id,), cause_ids=(notice.event_id,))
            transition = record_event(
                world, "campaign_supply_dispatched", "A remessa foi entregue à logística.",
                fact_kind=FactKind.STATE_TRANSITION,
                deltas=(_delta("campaign_supply_notice", notice.id, "state", "open", "dispatched"),),
                cause_ids=(decision.id, order.last_event_id))
            _transition_notice(world, notice, "dispatched", transition, freight_id=order.id)
            return order

        first_order = open_supply(notice, "first")
        world.agenda.cancel(f"campaign-supply-review:{notice.id}")
        first_parcel = next(item for item in world.economy.parcels.values() if item.order_id == first_order.id)
        world.agenda.cancel(first_parcel.id)
        world.clock = world.clock.advance(1)
        delayed = _record_parcel(
            world, first_parcel, first_parcel.model_copy(update={"due_day": world.clock.absolute_day + 2}),
            "cargo_delayed", "A capacidade diária reteve o frete original.")
        followup = next(item for item in observe_campaign_supply_needs(world) if item.detachment_id == column.id)
        assert delayed.id in {link.cause_event_id for link in world.event_index()[followup.event_id].causal_links}
        world.clock = world.clock.advance(1)
        due = world.agenda.pop_due(world.clock.absolute_day)
        resolve_dated(world, due)
        await review_campaign_supplies(world, due)
        assert world.knowledge.campaign_supply_notices[followup.id].state == "open"
        assert not campaign_logistics_withdrawal_options(world, OWNER, plan.id), (
            "the real pending parcel still targets the campaign bag"
        )

        world.clock = world.clock.advance(1)
        due = world.agenda.pop_due(world.clock.absolute_day)
        resolve_dated(world, due)  # original delayed parcel arrives before the QG reviews
        assert world.knowledge.campaign_supply_notices[notice.id].state == "fulfilled"
        scheduled = world.agenda.get(f"strategy-response-review:{plan.id}")
        assert scheduled is not None and scheduled.due_day == world.clock.absolute_day + 1
        world.clock = world.clock.advance(1)
        due = world.agenda.pop_due(world.clock.absolute_day)
        resolve_dated(world, due)
        assert campaign_logistics_withdrawal_options(world, OWNER, plan.id)
        return world, plan, due, delayed.id, followup.id

    from src.sim.medieval.force import campaign_logistics_withdrawal_options
    world, plan, due, delayed_id, followup_notice_id = asyncio.run(scenario())
    selected = []

    async def choose_withdraw(_world, actor, context, choices, **_kwargs):
        assert actor == headquarters_holder(world, OWNER)
        choice = next(item for item in choices if item["id"].startswith("campaign-delay-withdraw:"))
        assert choice["lapsed_supply_notice_ids"] == [followup_notice_id]
        assert any(route["affordance_id"] == choice["id"]
                   and route["lapsed_supply_notice_ids"] == [followup_notice_id]
                   for route in context["withdrawal_routes"])
        assert followup_notice_id in choice["label"]
        selected.append(choice["id"])
        return choice["id"]

    monkeypatch.setattr(ai_decider, "select_option", provider_selection_stub(choose_withdraw))
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    assert selected
    assert world.strategy.plans[plan.id].stage == "withdrawn"
    assert world.society.detachments[plan.detachment_id].stage == "marching"
    decision = next(event for event in reversed(world.events)
                    if event.event_type == "strategy_defense_logistics_review_decided")
    assert decision.decision["actor_ref"] == headquarters_holder(world, OWNER).to_dict()
    assert delayed_id in {link.cause_event_id for link in decision.causal_links}
    lapsed = next(event for event in reversed(world.events)
                  if event.event_type == "campaign_supply_lapsed"
                  and any(delta.owner_kind == "campaign_supply_notice"
                          and delta.owner_id == followup_notice_id
                          and delta.after == "lapsed" for delta in event.deltas))
    assert decision.id in {link.cause_event_id for link in lapsed.causal_links}
    assert world.knowledge.campaign_supply_notices[followup_notice_id].event_id in {
        link.cause_event_id for link in lapsed.causal_links
    }
    movement = next(event for event in reversed(world.events)
                    if event.event_type == "detachment_withdrawal_started")
    assert decision.id in {link.cause_event_id for link in movement.causal_links}
    updated = world.event_index()[world.strategy.plans[plan.id].last_event_id]
    assert delayed_id in {link.cause_event_id for link in updated.causal_links}
    path = tmp_path / "campaign-delay-qg-withdrawal.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_defense_menu_can_choose_sustained_column_with_real_daily_rations(monkeypatch, tmp_path):
    world, _, _ = occupied_response_world()
    stock = next(item for item in world.economy.stocks.values()
                 if item.owner_ref == OWNER and item.location_id == SOURCE)
    before_food = stock.goods.get("food", 0)
    premise = record_event(
        world, "test_defense_food_premise", "Premissa factual de estoque para expedição prolongada.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "strategy_response_fixture",
            "source_refs": [{"kind": "scenario", "id": "strategy_response_fixture"},
                            {"kind": "stock", "id": stock.id}],
            "observed_day": world.clock.absolute_day}},
        deltas=(_delta("stock", stock.id, "food", before_food, before_food + 3000),))
    world.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, "food": before_food + 3000},
        "last_event_ids": {**stock.last_event_ids, "food": premise.id}})
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))
    options = defense_action_options(world, OWNER, plan.id)
    assert {item.days for item in options} == {10, 40}
    sustained = next(item for item in options if item.days == 40)
    authorize_defense(world)

    async def choose_sustained(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        if all(item["id"].startswith("detachment-command-appoint:")
               for item in payload["choices"]):
            return {"selected_id": ai_decider.NO_ACTION}
        assert any("40 dias" in choice["label"] for choice in payload["choices"])
        return {"selected_id": sustained.id}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_sustained)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    column = world.society.detachments[world.strategy.plans[plan.id].detachment_id]
    assert column.provisions == column.count * 40
    raised = next(event for event in world.events if event.event_type == "detachment_raised")
    assert premise.id in {link.cause_event_id for link in raised.causal_links}
    assert world.economy.stocks[stock.id].goods["food"] == before_food + 3000 - column.provisions

    for _ in range(30):
        tick(world)
    current = world.society.detachments[column.id]
    assert current.stage == "present" and current.location_id == TARGET
    assert current.provisions == column.count * 10
    assert _fatigue_level(world, current) == 1
    assert sum(event.event_type == "detachment_supplied" and any(
        delta.owner_kind == "detachment" and delta.owner_id == column.id and delta.aspect == "provisions"
        for delta in event.deltas) for event in world.events) == 30
    path = tmp_path / "sustained-defense-column.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_mobilized_plan_survives_load_and_reconsiders_lost_column(monkeypatch, tmp_path):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    authorize_defense(world)
    due = tick(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    plan = next(iter(world.strategy.plans.values()))
    assert plan.stage == "mobilized" and plan.detachment_id is not None
    assert world.agenda.get(f"strategy-response-review:{plan.id}").due_day == 32
    path = tmp_path / "mobilized-plan.mws"
    save_world(world, path)
    world = load_world(path)
    # Only dated force laws and the owner's own monthly observation run here;
    # no provider is asked to maintain or replace the army automatically.
    world.config = world.config.model_copy(update={"ai_enabled": False})
    for day in range(3, 33):
        due = tick(world)
        if day == 30:
            refresh_settlement_reports(world)
        if day == 32:
            assert world.strategy.plans[plan.id].stage == "mobilized"
            assert asyncio.run(review_strategy_responses_with_provider(world, due))
    current = world.strategy.plans[plan.id]
    assert world.society.detachments[plan.detachment_id].stage == "disbanded"
    assert current.stage == "adopted" and current.detachment_id is None
    assert current.blocker == "coluna indisponível; reconsiderar meios"
    assert world.agenda.get(f"strategy-response-review:{plan.id}").due_day == 33
    final_path = tmp_path / "reconsidered-plan.mws"
    save_world(world, final_path)
    assert world_snapshot(load_world(final_path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(final_path)["ok"] is True


@pytest.mark.parametrize("occupier_after", [None, OWNER.id])
def test_mobilized_plan_closes_only_after_own_fresh_report(monkeypatch, tmp_path, occupier_after):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    authorize_defense(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    plan = next(iter(world.strategy.plans.values()))
    assert plan.stage == "mobilized"

    # The earlier column may lapse without supply. Resolve the occupation at
    # the observation boundary, as a separate explicit material fixture fact.
    assert world.strategy.plans[plan.id].stage == "mobilized"
    for day in range(3, 32):
        tick(world)
    end = record_event(
        world, "test_strategy_occupation_resolved", "Fixture factual do fim da ocupação estrangeira.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "strategy_response_fixture",
            "source_refs": [{"kind": "scenario", "id": "strategy_response_fixture"},
                            {"kind": "settlement", "id": TARGET}],
            "observed_day": world.clock.absolute_day}},
        deltas=(_delta("settlement", TARGET, "occupier_id", OCCUPIER.id, occupier_after),))
    world.society.set_occupation(TARGET, occupier_after)
    refresh_settlement_reports(world)
    report = world.knowledge.settlement_report(OWNER, TARGET)
    assert report is not None and report.occupier_id == occupier_after
    events = world.event_index()
    frontier = [report.event_id]
    seen = set()
    while frontier:
        event_id = frontier.pop()
        if event_id in seen:
            continue
        seen.add(event_id)
        frontier.extend(link.cause_event_id for link in events[event_id].causal_links)
    assert end.id in seen

    due = tick(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    closed = world.strategy.plans[plan.id]
    assert closed.stage == "closed" and closed.detachment_id is None
    receipt = world.event_index()[closed.last_event_id]
    assert report.event_id in {link.cause_event_id for link in receipt.causal_links}
    path = tmp_path / "observed-campaign-end.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_reoccupation_after_clear_report_blocks_stale_closure(monkeypatch):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    authorize_defense(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    plan = next(iter(world.strategy.plans.values()))
    record_event(world, "test_strategy_occupation_ended", "Fixture factual do fim da ocupação.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("settlement", TARGET, "occupier_id", OCCUPIER.id, None),))
    world.society.set_occupation(TARGET, None)
    for day in range(3, 32):
        tick(world)
        if day == 30:
            refresh_settlement_reports(world)
    assert world.knowledge.settlement_report(OWNER, TARGET).occupier_id is None
    record_event(world, "test_strategy_reoccupation", "Fixture factual de nova ocupação.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("settlement", TARGET, "occupier_id", None, OCCUPIER.id),))
    world.society.set_occupation(TARGET, OCCUPIER.id)

    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    current = world.strategy.plans[plan.id]
    assert current.stage == "blocked" and current.detachment_id == plan.detachment_id
    assert current.blocker == "relatório local contradito; aguardar nova observação"
    assert world.agenda.get(f"strategy-response-review:{plan.id}").due_day == 62
    world.strategy.validate(world)


def test_blocked_defense_reopens_when_material_means_return(monkeypatch, tmp_path):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))
    own_stocks = tuple(item for item in world.economy.stocks.values() if item.owner_ref == OWNER)
    original_food = {stock.id: stock.goods.get("food", 0) for stock in own_stocks}
    removed = record_event(
        world, "test_defense_food_unavailable", "Premissa material de falta de provisões.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "strategy_response_fixture",
            "source_refs": [{"kind": "scenario", "id": "strategy_response_fixture"},
                            {"kind": "stock", "id": own_stocks[0].id}],
            "observed_day": world.clock.absolute_day}},
        deltas=tuple(_delta("stock", stock.id, "food", original_food[stock.id], 0)
                     for stock in own_stocks))
    for stock in own_stocks:
        world.economy.stocks[stock.id] = stock.model_copy(update={
            "goods": {**stock.goods, "food": 0},
            "last_event_ids": {**stock.last_event_ids, "food": removed.id}})

    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    assert world.strategy.plans[plan.id].stage == "blocked"
    assert world.strategy.plans[plan.id].detachment_id is None
    assert world.agenda.get(f"strategy-response-review:{plan.id}").due_day == 31
    assert not defense_action_options(world, OWNER, plan.id)

    restored = record_event(
        world, "test_defense_food_restored", "Premissa material de novas provisões.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(_delta("stock", stock.id, "food", 0, original_food[stock.id] + 3000)
                     for stock in own_stocks), cause_ids=(removed.id,))
    for stock in own_stocks:
        current_stock = world.economy.stocks[stock.id]
        world.economy.stocks[stock.id] = current_stock.model_copy(update={
            "goods": {**current_stock.goods, "food": original_food[stock.id] + 3000},
            "last_event_ids": {**current_stock.last_event_ids, "food": restored.id}})
    for day in range(2, 31):
        tick(world)
        if day == 30:
            refresh_route_reports(world)
            refresh_settlement_reports(world)
    assert defense_action_options(world, OWNER, plan.id)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    assert not world.society.detachments
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    current = world.strategy.plans[plan.id]
    assert current.stage == "mobilized" and current.detachment_id in world.society.detachments
    material = world.event_index()[world.society.detachments[current.detachment_id].last_event_id]
    assert restored.id in {link.cause_event_id for link in material.causal_links}
    path = tmp_path / "blocked-defense-resumed.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_defense_no_action_preserves_a_later_choice(monkeypatch):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))
    authorize_defense(world)

    async def no_action(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    assert not asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    assert world.strategy.plans[plan.id].stage == "adopted"
    assert not world.society.detachments
    refusal = next(event for event in world.events if event.event_type == "strategy_defense_operational_declined")
    assert refusal.decision["actor_ref"] == headquarters_holder(world, OWNER).to_dict()
    assert refusal.causal_origin == CausalOrigin.ACTOR_DECISION
    assert refusal.decision["selected_affordance_id"] == ai_decider.NO_ACTION
    assert refusal.causal_payload["decision_source"]["kind"] == "provider"
    assert world.agenda.get(f"strategy-response-review:{plan.id}").due_day == 32

    for day in range(3, 32):
        tick(world)
        if day == 30:
            refresh_route_reports(world)
            refresh_settlement_reports(world)
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, tick(world)))
    assert world.strategy.plans[plan.id].stage == "mobilized"


def test_operational_mobilization_rejects_institutional_or_missing_briefing(monkeypatch):
    world, _, _ = occupied_response_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 10})
    choose_first(monkeypatch)
    assert asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    plan = next(iter(world.strategy.plans.values()))
    authorize_defense(world)
    due = tick(world)
    option = defense_action_options(world, OWNER, plan.id)[0]
    forged = record_event(world, "test_institutional_operational_decision", "Decisão da instituição, não do QG.",
                          fact_kind=FactKind.DECISION,
                          decision={"action": "raise_detachment", "actor_ref": OWNER.to_dict(),
                                    "institution_ref": OWNER.to_dict(), "operational_plan_id": plan.id,
                                    "selected_affordance_id": option.id})
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="current headquarters decision"):
        raise_detachment(world, OWNER, option.id, forged.id, days=option.days,
                         operational_plan_id=plan.id)
    assert world_snapshot(world) == before

    headquarters = headquarters_holder(world, OWNER)
    world.knowledge.settlement_reports.pop(settlement_report_id(headquarters, TARGET))
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    assert world.strategy.plans[plan.id].stage == "blocked"
    assert not world.society.detachments


def test_missing_stale_forged_or_no_action_never_adopts(monkeypatch):
    empty = create_medieval_world(73)
    assert not defense_adoption_options(empty, OWNER)

    world, _, _ = occupied_response_world()
    option = defense_adoption_options(world, OWNER)[0]
    before = world_snapshot(world)
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def forged(prompt, *args, **kwargs):
        return {"selected_id": option.id + ":forged"}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", forged)
    with pytest.raises(ai_decider.ProviderDecisionRequired):
        asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
    assert not world.strategy.plans and world_snapshot(world)["society"] == before["society"]

    silent, _, _ = occupied_response_world()
    silent.config = silent.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})

    async def no_action(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    assert not asyncio.run(review_strategy_responses_with_provider(silent, allow_adoptions=True))
    assert not silent.strategy.plans

    stale, _, _ = occupied_response_world()
    stale.clock = stale.clock.advance(31)
    assert not defense_adoption_options(stale, OWNER)


@pytest.mark.parametrize("mismatch", ["action", "actor", "affordance", "origin"])
def test_defense_adoption_owner_rejects_nonmatching_decisions(mismatch):
    world, _, _ = occupied_response_world()
    option = defense_adoption_options(world, OWNER)[0]
    decision = record_event(
        world, "test_defense_adoption_decision", "Fixture de escolha explícita.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}}, decision=option.decision())
    if mismatch == "action":
        payload = {**decision.decision, "action": "other_action"}
    elif mismatch == "actor":
        payload = {**decision.decision, "actor_ref": OCCUPIER.to_dict()}
    elif mismatch == "affordance":
        payload = {**decision.decision, "selected_affordance_id": "invented"}
    else:
        payload = decision.decision
    world.events[-1] = decision.model_copy(update={
        "decision": payload,
        "causal_origin": CausalOrigin.DETERMINISTIC if mismatch == "origin" else decision.causal_origin,
        "causal_payload": None if mismatch == "origin" else decision.causal_payload,
    })
    before = world_snapshot(world)

    with pytest.raises(ValueError, match="decision"):
        adopt_occupied_settlement_defense(world, OWNER, option.id, decision.id)
    assert world_snapshot(world) == before


def test_saved_plan_and_changed_authority_route_or_occupation_block_executor_atomically(tmp_path, monkeypatch):
    def saved_adopted(label):
        world, _, _ = occupied_response_world()
        world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2, "ai_max_calls": 10})
        choose_first(monkeypatch)
        asyncio.run(review_strategy_responses_with_provider(world, allow_adoptions=True))
        plan = next(iter(world.strategy.plans.values()))
        authorize_defense(world)
        path = tmp_path / f"strategy-response-{label}.mws"
        save_world(world, path)
        restored = load_world(path)
        assert world_snapshot(load_world(path)) == world_snapshot(restored)
        return restored, restored.strategy.plans[plan.id]

    world, plan = saved_adopted("occupation")

    # The provider saw a real raise affordance, but the canonical condition
    # changed before its selected ID reached the force owner.
    async def close_occupation_then_choose(prompt, *args, **kwargs):
        world.society.set_occupation(TARGET, None)
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", close_occupation_then_choose)
    due = tick(world)
    before = world_snapshot(world)
    assert asyncio.run(review_strategy_responses_with_provider(world, due))
    assert world.strategy.plans[plan.id].stage == "blocked"
    assert not world.society.detachments
    assert world_snapshot(world)["economy"] == before["economy"]
    assert not defense_action_options(world, OWNER, plan.id)

    authority_world, authority_plan = saved_adopted("authority")

    async def remove_authority_then_choose(prompt, *args, **kwargs):
        office = authority_world.authority.offices["office:polity:auren"]
        authority_world.authority.offices[office.id] = office.model_copy(
            update={"scopes": tuple(scope for scope in office.scopes if scope != "military")})
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", remove_authority_then_choose)
    authority_due = tick(authority_world)
    authority_economy = world_snapshot(authority_world)["economy"]
    assert asyncio.run(review_strategy_responses_with_provider(authority_world, authority_due))
    assert authority_world.strategy.plans[authority_plan.id].stage == "blocked"
    assert not authority_world.society.detachments
    assert world_snapshot(authority_world)["economy"] == authority_economy

    route_world, route_plan = saved_adopted("route")
    original = defense_action_options(route_world, OWNER, route_plan.id)[0]

    async def close_selected_route_then_choose(prompt, *args, **kwargs):
        for route_id in original.route_ids:
            route_world.map.routes[route_id].update_runtime(enabled=False)
        return {"selected_id": original.id}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", close_selected_route_then_choose)
    route_due = tick(route_world)
    route_economy = world_snapshot(route_world)["economy"]
    with pytest.raises(ai_decider.ProviderDecisionRequired):
        asyncio.run(review_strategy_responses_with_provider(route_world, route_due))
    assert route_world.strategy.plans[route_plan.id].stage == "adopted"
    assert not route_world.society.detachments
    assert world_snapshot(route_world)["economy"] == route_economy

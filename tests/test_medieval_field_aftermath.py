"""A field victory permits a choice; it never grants settlement control by itself."""

import copy
import json

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import headquarters_holder, political_holder
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.field_aftermath_policy import (execute_field_aftermath_option,
                                                      field_aftermath_options,
                                                      review_field_aftermaths, review_id)
from src.sim.medieval.field_engagement import (field_engagement_join_options,
                                               field_engagement_offer_options,
                                               join_field_engagement, offer_field_engagement)
from src.sim.medieval.economy import _delta
from src.sim.medieval.force import (detect_force_standoffs, force_position_options,
                                    headquarters_withdrawal_options, prepare_force_position,
                                    raise_detachment, raise_options)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import observe_present_agent, refresh_settlement_reports
from src.sim.medieval.strategy_response import (POLITICAL_MANDATE_SUSPENDED,
                                                POLITICAL_RESULT_REVIEW_KIND, _set_plan,
                                                adopt_occupied_settlement_defense,
                                                defense_adoption_options,
                                                political_campaign_review_options,
                                                review_strategy_responses_with_provider)
from src.sim.medieval.routing import supply_path


OWNER = EntityRef("polity", "auren")
RIVAL = EntityRef("polity", "escarlia")
HOME = "campomanso"
TARGET = "salgueiro"


def decide(world, option):
    return record_event(world, "field_aftermath_decided", "Decisão canônica após combate.",
                        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                        decision=option.decision(),
                        causal_payload={"decision_source": {"kind": "api"}})


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def disband_losing_column(world, notice):
    option = next(item for item in field_aftermath_options(
        world, notice.recipient_ref, outcome_notice_id=notice.id)
        if item.decision()["action"] == "disband_detachment")
    decision = record_event(
        world, "field_aftermath_decided", "A instituição dissolveu sua coluna sobrevivente.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision=option.decision(), cause_ids=(notice.event_id,))
    return execute_field_aftermath_option(world, notice.recipient_ref, notice.id, option.id, decision.id)


def resolved_field_engagement_world(*, with_strategy_plan=False, own_soldiers=30, rival_soldiers=1,
                                   prepare_column=True):
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": own_soldiers})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    supply_days = 40 if not prepare_column else 20
    raised = next(item for item in raise_options(world, OWNER, days=supply_days)
                  if item.destination_id == TARGET)
    own = raise_detachment(world, OWNER, raised.id, decide(world, raised).id, days=supply_days)
    while world.society.detachments[own.id].stage == "marching":
        tick(world)
    if prepare_column:
        position = force_position_options(world, OWNER, detachment_id=own.id)[0]
        prepare_force_position(world, OWNER, position.id, decide(world, position).id)
        for _ in range(3):
            tick(world)
    own = world.society.detachments[own.id]

    resident = next(item for item in world.society.population.values() if item.settlement_id == "ferroalto")
    rival_group = resident.model_copy(update={"id": f"pop:ferroalto:{resident.people}:soldier",
                                              "occupation": "soldier", "count": rival_soldiers})
    world.society.population[rival_group.id] = rival_group
    rival = Detachment(id="detachment:aftermath-rival", owner_ref=RIVAL, source_group_id=rival_group.id,
                       count=rival_soldiers, location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0,
                       provisions=rival_soldiers * (20 if not prepare_column else 1), stage="present",
                       started_day=world.clock.absolute_day,
                       due_day=world.clock.absolute_day + 1, decision_event_id=own.decision_event_id,
                       last_event_id=own.last_event_id)
    world.society.detachments[rival.id] = rival
    detect_force_standoffs(world, rival.id)
    offer = field_engagement_offer_options(world, OWNER)[0]
    engagement = offer_field_engagement(world, OWNER, offer.id, decide(world, offer).id)
    # The defender's independent answer is a next-day contact turn, not an
    # immediate consequence of the challenge.
    tick(world)
    join = field_engagement_join_options(world, RIVAL)[0]
    join_field_engagement(world, RIVAL, join.id, decide(world, join).id)
    if with_strategy_plan:
        settlement = world.society.settlements[TARGET]
        claims = tuple(sorted((*settlement.claimant_ids, OWNER.id)))
        record_event(
            world, "test_occupied_claimed_settlement", "Fixture factual de reivindicação e ocupação.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("settlement", TARGET, "administrator_id", settlement.administrator_id, OWNER.id),
                    _delta("settlement", TARGET, "claimant_ids", settlement.claimant_ids, claims),
                    _delta("settlement", TARGET, "occupier_id", None, RIVAL.id)))
        world.society.settlements[TARGET] = settlement.model_copy(
            update={"administrator_id": OWNER.id, "claimant_ids": claims})
        world.society.set_occupation(TARGET, RIVAL.id)
        observe_present_agent(world, OWNER, TARGET)
        adoption, = defense_adoption_options(world, OWNER)
        plan = adopt_occupied_settlement_defense(world, OWNER, adoption.id,
                                                 decide(world, adoption).id)
        raised_event = next(event for event in reversed(world.events)
                            if event.event_type == "detachment_raised"
                            and any(delta.owner_kind == "detachment" and delta.owner_id == own.id
                                    for delta in event.deltas))
        _set_plan(world, plan, "mobilized", detachment_id=own.id, causes=(raised_event.id,))
        refresh_settlement_reports(world)
    winner = next(notice for notice in world.knowledge.field_engagement_outcome_notices.values()
                  if notice.recipient_ref == OWNER)
    return world, engagement.id, winner


@pytest.mark.parametrize("field", ["own_prepared", "own_supplied"])
def test_outcome_notice_conditions_must_match_the_recorded_combat_terms(field):
    world, _, notice = resolved_field_engagement_world()
    assert getattr(notice, field) is True
    world.knowledge.field_engagement_outcome_notices[notice.id] = notice.model_copy(
        update={field: False})

    with pytest.raises(ValueError, match="invalid field engagement outcome notice"):
        world.knowledge.validate(world)


def test_local_combat_reading_reaches_headquarters_only_through_physical_bulletin():
    world, engagement_id, _ = resolved_field_engagement_world()
    headquarters = headquarters_holder(world, OWNER)
    headquarters_character = world.society.characters[headquarters.id]
    assert supply_path(world, TARGET, headquarters_character.location_id) is not None

    refresh_settlement_reports(world)

    report = world.knowledge.settlement_report(headquarters, TARGET)
    assert report.publisher_ref == OWNER
    assert report is not None and report.channel == "settlement_bulletin"
    reading, = (item for item in report.field_engagements if item.engagement_id == engagement_id)
    assert reading.winner_ref == OWNER
    assert reading.challenger_casualties == world.society.field_engagements[engagement_id].challenger_casualties
    local = world.knowledge.settlement_report(OWNER, TARGET)
    local_event = world.event_index()[local.event_id]
    assert any(link.cause_event_id == reading.event_id for link in local_event.causal_links)
    delivery = world.event_index()[report.event_id]
    assert delivery.event_type == "settlement_report_received"
    assert any(link.cause_event_id != reading.event_id for link in delivery.causal_links)


async def test_headquarters_independently_withdraws_only_from_its_battle_and_route_reports(monkeypatch, tmp_path):
    world, engagement_id, _ = resolved_field_engagement_world(with_strategy_plan=True)
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    headquarters = headquarters_holder(world, OWNER)
    report = world.knowledge.settlement_report(headquarters, TARGET)
    options = headquarters_withdrawal_options(world, OWNER, report)
    option = next(item for item in options if item.destination_id == HOME)
    assert option.plan_id is not None
    stale_world = copy.deepcopy(world)
    for key, route_report in tuple(stale_world.knowledge.route_reports.items()):
        if route_report.recipient_ref == headquarters:
            stale_world.knowledge.route_reports[key] = route_report.model_copy(update={
                "observed_day": stale_world.clock.absolute_day - 30})
    assert headquarters_withdrawal_options(
        stale_world, OWNER, stale_world.knowledge.settlement_report(headquarters, TARGET)) == ()
    path = tmp_path / "headquarters-battle-response.mws"
    save_world(world, path)
    world = load_world(path)
    headquarters = headquarters_holder(world, OWNER)
    report = world.knowledge.settlement_report(headquarters, TARGET)
    options = headquarters_withdrawal_options(world, OWNER, report)
    option = next(item for item in options if item.destination_id == HOME)
    due = next(item for item in world.agenda.to_dict()
               if item["kind"] == "headquarters_field_response_review"
               and engagement_id in item["id"])

    async def choose_withdrawal(prompt):
        payload = json.loads(prompt[prompt.index("{"):])
        selected = next((item["id"] for item in payload["choices"] if HOME in item["label"]),
                        ai_decider.NO_ACTION)
        return {"selected_id": selected}

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 20,
                                                   "ai_max_calls": 20})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_withdrawal)
    maintained = copy.deepcopy(world)

    async def choose_maintain(prompt):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_maintain)
    maintained.clock = maintained.clock.advance(1)
    maintained_due = maintained.agenda.pop_due(maintained.clock.absolute_day)
    from src.sim.medieval.dated import resolve_dated
    resolve_dated(maintained, maintained_due)
    await review_field_aftermaths(maintained, maintained_due)
    maintained_decision = next(event for event in reversed(maintained.events)
                               if event.event_type == "headquarters_field_response_decided")
    assert maintained_decision.decision["action"] == "maintain"
    assert maintained_decision.decision["selected_affordance_id"] == ai_decider.NO_ACTION
    assert maintained_decision.causal_origin == CausalOrigin.ACTOR_DECISION
    maintained_source = maintained_decision.causal_payload["decision_source"]
    assert maintained_source["kind"] == "provider"
    assert maintained_source["receipt_event_id"] in {
        link.cause_event_id for link in maintained_decision.causal_links
    }
    assert maintained.society.detachments[option.detachment_id].stage == "present"
    assert maintained.strategy.plans[option.plan_id].stage == "mobilized"

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_withdrawal)
    scheduled = world.agenda.get(due["id"])
    assert scheduled is not None
    world.clock = world.clock.advance(1)
    due_situations = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due_situations)
    await review_field_aftermaths(world, due_situations)

    detachment = world.society.detachments[option.detachment_id]
    decision = next(event for event in reversed(world.events)
                    if event.event_type == "headquarters_field_response_decided")
    assert decision.decision["action"] == "withdraw_detachment"
    assert decision.decision["actor_ref"] == headquarters.to_dict()
    assert decision.causal_origin == CausalOrigin.ACTOR_DECISION
    source = decision.causal_payload["decision_source"]
    assert source["kind"] == "provider"
    assert source["receipt_event_id"] in {link.cause_event_id for link in decision.causal_links}
    assert detachment.stage == "marching" and detachment.destination_id == HOME, decision.decision
    movement = world.event_index()[detachment.last_event_id]
    assert movement.causal_origin == CausalOrigin.ACTOR_DECISION
    assert movement.causal_payload == {"decision_event_id": decision.id,
                                       "actor_ref": headquarters.to_dict(),
                                       "selected_affordance_id": decision.decision["selected_affordance_id"]}
    causes = {link.cause_event_id for link in decision.causal_links}
    route_receipts = {event.id for event in world.events
                      if event.event_type in {"route_observed", "route_report_received"}}
    assert {report.event_id, world.society.field_engagements[engagement_id].last_event_id} <= causes
    assert causes & route_receipts
    plan = world.strategy.plans[option.plan_id]
    assert plan.stage == "withdrawn" and plan.detachment_id == detachment.id
    plan_update = world.event_index()[plan.last_event_id]
    assert plan_update.event_type == "strategy_defense_plan_updated"
    assert {decision.id, movement.id} <= {
        link.cause_event_id for link in plan_update.causal_links
    }
    save_world(world, path)
    loaded = load_world(path)
    assert loaded.strategy.plans[option.plan_id] == plan


async def test_headquarters_can_withdraw_after_an_indecisive_battle(monkeypatch):
    world, engagement_id, _ = resolved_field_engagement_world(
        with_strategy_plan=True, own_soldiers=30, rival_soldiers=2, prepare_column=False)
    engagement = world.society.field_engagements[engagement_id]
    assert engagement.winner_ref is None
    detachment_id = (engagement.challenger_detachment_id if engagement.challenger_ref == OWNER
                     else engagement.defender_detachment_id)
    assert world.society.detachments[detachment_id].stage == "present"

    refresh_route_reports(world)
    refresh_settlement_reports(world)
    headquarters = headquarters_holder(world, OWNER)
    report = world.knowledge.settlement_report(headquarters, TARGET)
    assert report.publisher_ref == OWNER
    reading = next(item for item in report.field_engagements if item.engagement_id == engagement_id)
    assert reading.winner_ref is None
    option = next(item for item in headquarters_withdrawal_options(world, OWNER, report)
                  if item.detachment_id == detachment_id and item.destination_id == HOME)

    async def choose_retreat(prompt):
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": next(item["id"] for item in payload["choices"]
                                    if item["id"] == option.id)}

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 20,
                                                   "ai_max_calls": 20})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_retreat)
    due = [item for item in world.agenda.pop_due(world.clock.absolute_day + 1)
           if item.kind == "headquarters_field_response_review" and report.event_id in item.id]
    assert due
    world.clock = world.clock.advance(1)
    resolve_dated(world, due)
    await review_field_aftermaths(world, due)

    decision = next(event for event in reversed(world.events)
                    if event.event_type == "headquarters_field_response_decided")
    movement = world.event_index()[world.society.detachments[detachment_id].last_event_id]
    assert decision.decision["selected_affordance_id"] == option.id
    assert movement.event_type == "detachment_withdrawal_started"
    assert movement.causal_payload["decision_event_id"] == decision.id
    assert movement.causal_payload["selected_affordance_id"] == option.id
    assert world.strategy.plans[option.plan_id].stage == "withdrawn"


@pytest.mark.parametrize(("disposition", "expected_stage", "own_soldiers", "rival_soldiers", "expected_outcome"), [
    ("suspend", "blocked", 30, 1, "won"),
    ("maintain", "mobilized", 30, 1, "won"),
    ("no_action", "mobilized", 30, 1, "won"),
    ("suspend", "blocked", 1, 300, "lost")])
async def test_political_holder_reviews_its_delivered_campaign_result(monkeypatch, tmp_path, disposition,
                                                                       expected_stage, own_soldiers, rival_soldiers,
                                                                       expected_outcome):
    world, engagement_id, notice = resolved_field_engagement_world(
        with_strategy_plan=True, own_soldiers=own_soldiers, rival_soldiers=rival_soldiers)
    assert notice.outcome == expected_outcome
    principal = political_holder(world, OWNER)
    report = world.knowledge.settlement_report(principal, TARGET)
    assert report is not None and report.channel == "settlement_bulletin"
    options = political_campaign_review_options(world, report, engagement_id=engagement_id)
    chosen = (next(item for item in options if item.disposition == disposition)
              if disposition != "no_action" else None)
    assert any(item["kind"] == POLITICAL_RESULT_REVIEW_KIND and engagement_id in item["id"]
               for item in world.agenda.to_dict())

    async def choose(prompt):
        return {"selected_id": chosen.id if chosen else ai_decider.NO_ACTION}

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 20,
                                                   "ai_max_calls": 20})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose)
    world.clock = world.clock.advance(1)
    due_situations = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due_situations)
    assert await review_strategy_responses_with_provider(world, due_situations)

    plan = next(item for item in world.strategy.plans.values() if item.detachment_id is not None)
    assert plan.stage == expected_stage
    decision = next(event for event in reversed(world.events)
                    if event.event_type == "strategy_defense_political_result_decided")
    if chosen is not None:
        assert decision.decision == chosen.decision()
    else:
        assert decision.decision["action"] == "no_action"
        assert decision.decision["selected_affordance_id"] == ai_decider.NO_ACTION
    assert decision.decision["actor_ref"] == principal.to_dict()
    causes = {link.cause_event_id for link in decision.causal_links}
    assert {report.event_id, world.society.field_engagements[engagement_id].last_event_id} <= causes
    if disposition == "suspend":
        assert plan.blocker == POLITICAL_MANDATE_SUSPENDED
        plan_update = world.event_index()[plan.last_event_id]
        assert decision.id in {link.cause_event_id for link in plan_update.causal_links}
        path = tmp_path / "political-campaign-result.mws"
        save_world(world, path)
        assert load_world(path).strategy.plans[plan.id] == plan
    else:
        assert plan.blocker is None
    assert not political_campaign_review_options(world, report, engagement_id=engagement_id)


def test_settlement_combat_reading_cannot_change_recorded_casualties():
    world, _, _ = resolved_field_engagement_world()
    refresh_settlement_reports(world)
    local = world.knowledge.settlement_report(OWNER, TARGET)
    reading = local.field_engagements[0]
    world.knowledge.settlement_reports[local.id] = local.model_copy(update={
        "field_engagements": (reading.model_copy(update={"challenger_casualties": reading.challenger_casualties + 1}),)
    })

    with pytest.raises(ValueError, match="settlement observation requires its own typed receipt"):
        world.knowledge.validate(world)


async def test_victory_schedules_private_review_and_explicit_occupy_preserves_assets(tmp_path, monkeypatch):
    world, engagement_id, notice = resolved_field_engagement_world()
    loser_notice = next(item for item in world.knowledge.field_engagement_outcome_notices.values()
                        if item.engagement_id == engagement_id and item.outcome == "lost")
    scheduled = world.agenda.get(review_id(notice.id))
    assert scheduled is not None and scheduled.due_day == world.clock.absolute_day + 2
    losing_review = world.agenda.get(review_id(loser_notice.id))
    assert losing_review is not None and losing_review.due_day == world.clock.absolute_day + 1
    assert world.society.field_engagements[engagement_id].winner_ref == OWNER
    assert world.society.settlements[TARGET].occupier_id is None
    assert world.society.detachments[loser_notice.own_detachment_id].stage == "present"
    disband_losing_column(world, loser_notice)

    path = tmp_path / "field-aftermath.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

    tick(world)  # loser review is now inert because its column chose to disband
    due = tick(world)
    stock_before = {key: item.model_dump(mode="json") for key, item in world.economy.stocks.items()}
    account_before = {key: item.model_dump(mode="json") for key, item in world.economy.accounts.items()}
    administration_before = world.society.settlements[TARGET].administrator_id
    prompts = []

    async def choose_occupy(prompt, *args, **kwargs):
        prompts.append(prompt)
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": next(item["id"] for item in payload["choices"]
                               if item["label"].startswith("Ocupar"))}

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                   "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_occupy)
    await review_field_aftermaths(world, due)

    assert world.society.settlements[TARGET].occupier_id == OWNER.id
    assert world.society.settlements[TARGET].administrator_id == administration_before
    assert {key: item.model_dump(mode="json") for key, item in world.economy.stocks.items()} == stock_before
    assert {key: item.model_dump(mode="json") for key, item in world.economy.accounts.items()} == account_before
    assert "counterparty_strength_band" not in prompts[0]
    assert "provisions" not in prompts[0] and "route_ids" not in prompts[0]
    assert not any(event.event_type in {"battle_resolved", "loot_taken"} for event in world.events)


async def test_provider_off_or_no_action_leaves_victory_without_occupation(monkeypatch):
    world, _, notice = resolved_field_engagement_world()
    due = tick(world)
    before = world_snapshot(world)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    await review_field_aftermaths(world, due)
    assert world_snapshot(world) == before

    silent, _, _ = resolved_field_engagement_world()
    silent_due = tick(silent)

    async def no_action(*_args, **_kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    silent.config = silent.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                     "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    await review_field_aftermaths(silent, silent_due)
    assert silent.society.settlements[TARGET].occupier_id is None
    winner_due = tick(silent)
    await review_field_aftermaths(silent, winner_due)
    assert silent.society.settlements[TARGET].occupier_id is None
    assert not any(event.event_type in {"settlement_occupied", "battle_resolved", "loot_taken"}
                   for event in silent.events[-2:])


async def test_defeated_institution_decides_to_disband_its_surviving_column(monkeypatch):
    world, _, _ = resolved_field_engagement_world()
    notice = next(item for item in world.knowledge.field_engagement_outcome_notices.values()
                  if item.recipient_ref == RIVAL)
    detachment_id = notice.own_detachment_id
    assert world.society.detachments[detachment_id].stage == "present"
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                   "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def choose_disband(prompt):
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": next(item["id"] for item in payload["choices"]
                                    if item["label"].startswith("Dissolver"))}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_disband)
    due = tick(world)
    await review_field_aftermaths(world, due)

    decision = next(event for event in reversed(world.events)
                    if event.event_type == "field_aftermath_decided")
    assert decision.decision["actor_ref"] == RIVAL.to_dict()
    assert decision.decision["action"] == "disband_detachment"
    assert decision.causal_origin == CausalOrigin.ACTOR_DECISION
    source = decision.causal_payload["decision_source"]
    assert source["kind"] == "provider"
    assert source["receipt_event_id"] in {link.cause_event_id for link in decision.causal_links}
    disband = world.event_index()[world.society.detachments[detachment_id].last_event_id]
    assert disband.event_type == "detachment_disbanded"
    assert disband.causal_origin == CausalOrigin.ACTOR_DECISION
    assert disband.causal_payload["decision_event_id"] == decision.id
    assert notice.event_id in {link.cause_event_id for link in decision.causal_links}
    assert world.society.settlements[TARGET].occupier_id is None


async def test_defeated_institution_can_choose_a_known_material_withdrawal(monkeypatch):
    world, _, _ = resolved_field_engagement_world(prepare_column=False)
    notice = next(item for item in world.knowledge.field_engagement_outcome_notices.values()
                  if item.recipient_ref == RIVAL)
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    withdrawal = next(item for item in field_aftermath_options(
        world, RIVAL, outcome_notice_id=notice.id)
        if item.decision()["action"] == "withdraw_detachment")
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 10,
                                                   "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def choose_withdrawal(prompt):
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": next((item["id"] for item in payload["choices"]
                                      if item["id"] == withdrawal.id), ai_decider.NO_ACTION)}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_withdrawal)
    await review_field_aftermaths(world, tick(world))

    detachment = world.society.detachments[withdrawal.detachment_id]
    decision = next(event for event in reversed(world.events)
                    if event.event_type == "field_aftermath_decided")
    movement = world.event_index()[detachment.last_event_id]
    assert detachment.stage == "marching" and detachment.destination_id == withdrawal.destination_id
    assert decision.decision["selected_affordance_id"] == withdrawal.id
    assert decision.decision["actor_ref"] == RIVAL.to_dict()
    assert decision.causal_origin == CausalOrigin.ACTOR_DECISION
    source = decision.causal_payload["decision_source"]
    assert source["kind"] == "provider"
    assert source["receipt_event_id"] in {link.cause_event_id for link in decision.causal_links}
    assert movement.causal_origin == CausalOrigin.ACTOR_DECISION
    assert movement.causal_payload["decision_event_id"] == decision.id
    assert notice.event_id in {link.cause_event_id for link in decision.causal_links}


async def test_ai_enabled_aftermath_pauses_when_provider_disappears(monkeypatch):
    world, _, notice = resolved_field_engagement_world()
    due = tick(world)
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                   "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    before = world_snapshot(world)
    with pytest.raises(ProviderDecisionRequired):
        await review_field_aftermaths(world, due)
    assert world_snapshot(world) == before
    assert world.society.settlements[TARGET].occupier_id is None


async def test_provider_stale_aftermath_rolls_back_simulator_transaction(monkeypatch):
    world, _, notice = resolved_field_engagement_world()
    await review_field_aftermaths(world, tick(world))  # defeated side has no offline automatic response
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                   "ai_max_calls": 10})
    before = world_snapshot(world)
    real_options = field_aftermath_options(world, OWNER, outcome_notice_id=notice.id)

    async def choose_first(_world, _actor, _situation, choices, **_kwargs):
        return choices[0]["id"]

    monkeypatch.setattr(ai_decider, "select_option", choose_first)
    calls = 0

    def stale_after_selection(candidate, actor, *, outcome_notice_id=None):
        nonlocal calls
        calls += 1
        return real_options if calls == 1 else ()

    monkeypatch.setattr("src.sim.medieval.field_aftermath_policy.field_aftermath_options",
                        stale_after_selection)
    with pytest.raises(ProviderDecisionRequired, match="stale"):
        await MedievalSimulator(world).step()
    assert world_snapshot(world) == before


def test_stale_authority_or_supervening_occupier_block_aftermath_atomically():
    world, _, notice = resolved_field_engagement_world()
    loser_notice = next(item for item in world.knowledge.field_engagement_outcome_notices.values()
                        if item.outcome == "lost")
    disband_losing_column(world, loser_notice)
    option = next(item for item in field_aftermath_options(world, OWNER, outcome_notice_id=notice.id)
                  if item.decision()["action"] == "occupy_settlement")
    with pytest.raises(ValueError, match="stale or unknown"):
        execute_field_aftermath_option(world, OWNER, notice.id, option.id + ":forged", decide(world, option).id)
    assert world.society.settlements[TARGET].occupier_id is None

    authority_lost = copy.deepcopy(world)
    office = authority_lost.authority.offices["office:polity:auren"]
    authority_lost.authority.offices[office.id] = office.model_copy(
        update={"scopes": tuple(scope for scope in office.scopes if scope != "military")})
    with pytest.raises(ValueError, match="stale or unknown"):
        execute_field_aftermath_option(authority_lost, OWNER, notice.id, option.id,
                                       decide(authority_lost, option).id)
    assert authority_lost.society.settlements[TARGET].occupier_id is None

    occupied = copy.deepcopy(world)
    occupied.society.set_occupation(TARGET, RIVAL.id)
    with pytest.raises(ValueError, match="no longer possible"):
        execute_field_aftermath_option(occupied, OWNER, notice.id, option.id, decide(occupied, option).id)
    assert occupied.society.settlements[TARGET].occupier_id == RIVAL.id

"""Institutional knowledge trains a real column only through material work."""

import json

import pytest

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.field_engagement import field_strength
from src.sim.medieval.field_engagement import (field_engagement_offer_options,
                                               field_engagement_join_options, offer_field_engagement,
                                               join_field_engagement)
from src.sim.medieval.force import detect_force_standoffs
from src.sim.medieval.force_training import start_training, training_adapters, training_options
from src.sim.medieval import ai_decider
from src.sim.medieval.campaign_supply import (_bag_capacity, _provision_capacity,
                                              campaign_stock_id, ensure_campaign_stock)
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import learn_technology
from src.systems.calendar_agenda import ScheduledSituation


OWNER = EntityRef("polity", "auren")
RIVAL = EntityRef("polity", "escarlia")
SETTLEMENT = "campomanso"


def world_with_column():
    world = create_medieval_world(73)
    group = next(item for item in world.society.population.values()
                 if item.settlement_id == SETTLEMENT and item.occupation == "soldier")
    source_id = group.id
    decision = record_event(world, "fixture_column_decided", "Coluna presente na premissa pressionada.",
                            fact_kind=FactKind.DECISION,
                            decision={"action": "raise_detachment", "actor_ref": OWNER.to_dict()})
    arrival = record_event(world, "fixture_column_present", "A coluna está no assentamento.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("detachment", "detachment:drill", "stage", None, "present"),),
                           cause_ids=(decision.id,))
    column = Detachment(id="detachment:drill", owner_ref=OWNER, source_group_id=source_id,
                        count=group.count, location_id=SETTLEMENT, destination_id=SETTLEMENT,
                        provisions=220, stage="present", started_day=world.clock.absolute_day,
                        due_day=world.clock.absolute_day + 1,
                        decision_event_id=decision.id, last_event_id=arrival.id)
    world.society.detachments[column.id] = column
    world.agenda.schedule(ScheduledSituation(column.id, "force", column.due_day))
    return world, column.id


def learn(world, technology_id):
    decision = record_event(world, "fixture_research_decided", "Ensino da técnica militar.",
                            fact_kind=FactKind.DECISION,
                            decision={"action": "research", "actor_ref": OWNER.to_dict(),
                                      "technology_id": technology_id})
    learn_technology(world, OWNER, technology_id, "teaching", (decision.id,))


def decide(world, option):
    return record_event(world, "detachment_training_decided", "Instrução da coluna escolhida.",
                        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                        causal_payload={"decision_source": {"kind": "api"}}, decision=option.decision())


def tick(world):
    world.clock = world.clock.advance(1)
    resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))


def test_knowledge_alone_grants_no_strength_but_paid_dated_training_does(tmp_path):
    world, column_id = world_with_column()
    column = world.society.detachments[column_id]
    baseline = field_strength(world, column)[0]
    learn(world, "field_drill")
    assert field_strength(world, world.society.detachments[column_id])[0] == baseline
    option = training_options(world, OWNER, detachment_id=column_id)[0]
    assert option.id in {item.id for item in training_adapters()[0].options_fn(world, OWNER)}
    assert "detachment_training" in {item.name for item in monthly_adapters()}
    before_tools = world.economy.stocks[option.stock_id].goods["tools"]
    training = start_training(world, OWNER, option.id, decide(world, option).id)
    assert world.economy.stocks[option.stock_id].goods["tools"] == before_tools - option.tool_cost
    assert field_strength(world, world.society.detachments[column_id])[0] == baseline
    for _ in range(2):
        tick(world)
        assert world.society.detachment_trainings[training.id].stage == "training"
        assert field_strength(world, world.society.detachments[column_id])[0] == baseline
    tick(world)
    assert world.society.detachment_trainings[training.id].stage == "completed"
    assert field_strength(world, world.society.detachments[column_id])[0] == baseline + column.count
    completion = world.event_index()[world.society.detachment_trainings[training.id].last_event_id]
    assert completion.event_type == "detachment_training_completed"
    path = tmp_path / "trained-column.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    assert field_strength(restored, restored.society.detachments[column_id])[0] == baseline + column.count
    restored.society.detachment_trainings[training.id] = restored.society.detachment_trainings[
        training.id].model_copy(update={"knowledge_event_id": "event:1"})
    with pytest.raises(ValueError, match="training lacks"):
        world_snapshot(restored)


def test_stale_selection_and_supply_lapse_cannot_train_or_create_strength():
    world, column_id = world_with_column()
    learn(world, "field_drill")
    option = training_options(world, OWNER, detachment_id=column_id)[0]
    decision = decide(world, option)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale or unknown"):
        start_training(world, OWNER, option.id + ":forged", decision.id)
    assert world_snapshot(world) == before
    training = start_training(world, OWNER, option.id, decision.id)
    column = world.society.detachments[column_id]
    world.society.detachments[column_id] = column.model_copy(update={"provisions": column.count})
    unsupplied_strength = field_strength(world, world.society.detachments[column_id])[0]
    tick(world)
    assert world.society.detachment_trainings[training.id].stage == "lapsed"
    assert field_strength(world, world.society.detachments[column_id])[0] == unsupplied_strength


def test_siegecraft_requires_separate_instruction_after_field_drill():
    world, column_id = world_with_column()
    column = world.society.detachments[column_id]
    baseline = field_strength(world, column)[0]
    learn(world, "field_drill")
    learn(world, "siegecraft")
    assert not any(item.technology_id == "siegecraft" for item in training_options(world, OWNER))
    drill = next(item for item in training_options(world, OWNER) if item.technology_id == "field_drill")
    start_training(world, OWNER, drill.id, decide(world, drill).id)
    for _ in range(3):
        tick(world)
    advanced = next(item for item in training_options(world, OWNER) if item.technology_id == "siegecraft")
    assert advanced.tool_cost == 2
    training = start_training(world, OWNER, advanced.id, decide(world, advanced).id)
    for _ in range(3):
        tick(world)
    assert world.society.detachment_trainings[training.id].stage == "completed"
    assert field_strength(world, world.society.detachments[column_id])[0] == baseline + 2 * column.count


@pytest.mark.asyncio
async def test_field_logistics_is_chosen_in_monthly_menu_before_equipping_existing_bag(tmp_path, monkeypatch):
    world, column_id = world_with_column()
    column = world.society.detachments[column_id]
    bag = ensure_campaign_stock(world, column)
    baseline_bag = bag.capacity
    baseline_provisions = _provision_capacity(world, column)
    learn(world, "field_drill")
    learn(world, "field_logistics")
    assert _bag_capacity(world, column) == baseline_bag
    assert _provision_capacity(world, column) == baseline_provisions
    assert not any(item.technology_id == "field_logistics" for item in training_options(world, OWNER))

    drill = next(item for item in training_options(world, OWNER) if item.technology_id == "field_drill")
    start_training(world, OWNER, drill.id, decide(world, drill).id)
    for _ in range(3):
        tick(world)
    assert _bag_capacity(world, world.society.detachments[column_id]) == baseline_bag

    logistics = next(item for item in training_options(world, OWNER)
                     if item.technology_id == "field_logistics")
    before_tools = world.economy.stocks[logistics.stock_id].goods["tools"]
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 256,
                                                    "ai_max_calls": 1000})
    from src.sim.medieval.institutional_agenda import (monthly_actors, monthly_adapters,
                                                        review_monthly_institutional_turn)
    from src.sim.medieval.institutional_decision_turn import _by_id

    adapters = monthly_adapters()
    assert OWNER in monthly_actors(world)
    current = _by_id(world, OWNER, adapters)
    assert logistics.id in current
    training_adapter = next(item for item in adapters if item.name == "detachment_training")
    logistics_label = training_adapter.label_fn(logistics)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    selected = []
    provider_ids = []

    async def choose_field_logistics(prompt, *_args, **_kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        choice = next((item for item in payload["choices"] if item["label"] == logistics_label), None)
        if payload["you_are"]["id"] == OWNER.id and choice is not None:
            # The provider sees an opaque alias because the canonical ID embeds
            # a private stock identifier; the engine resolves it back to the
            # current logistics affordance.
            selected.append(logistics.id)
            provider_ids.append(choice["id"])
            return {"selected_id": choice["id"]}
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_field_logistics)
    await review_monthly_institutional_turn(world)
    assert selected == [logistics.id]
    assert len(provider_ids) == 1 and provider_ids[0].startswith("choice:")
    assert provider_ids[0] != logistics.id
    decision = next(item for item in world.events
                    if item.fact_kind is FactKind.DECISION
                    and item.decision == logistics.decision())
    assert decision.causal_origin is CausalOrigin.ACTOR_DECISION
    assert decision.causal_payload["decision_source"]["kind"] == "provider"
    training = next(item for item in world.society.detachment_trainings.values()
                    if item.technology_id == "field_logistics")
    assert world.economy.stocks[logistics.stock_id].goods["tools"] == before_tools - logistics.tool_cost
    assert world.economy.stocks[logistics.stock_id].goods["tools"] == before_tools - logistics.tool_cost
    for _ in range(2):
        tick(world)
        assert _bag_capacity(world, world.society.detachments[column_id]) == baseline_bag
    tick(world)
    column = world.society.detachments[column_id]
    completion_id = world.society.detachment_trainings[training.id].last_event_id
    equipped = next(event for event in world.events if event.event_type == "campaign_baggage_equipped")
    assert completion_id in {link.cause_event_id for link in equipped.causal_links}
    assert world.economy.stocks[campaign_stock_id(column_id)].capacity == _bag_capacity(world, column)
    assert _bag_capacity(world, column) == baseline_bag + column.count * 5 * world.economy.resources["food"].bulk
    assert _provision_capacity(world, column) == baseline_provisions + column.count * 5
    path = tmp_path / "logistics-column.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_paid_field_drill_research_and_training_reach_a_material_field_battle(tmp_path):
    world, column_id = world_with_column()
    # The prepared column remains stationary while the research subsystem is
    # advanced by monthly owner calls; its next real daily upkeep resumes on
    # day 181, leaving the three-day training window fully supplied.
    column = world.society.detachments[column_id]
    upkeep_window = record_event(
        world, "fixture_research_window", "A coluna preparada permanece no local durante a janela de pesquisa.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment", column.id, "due_day", column.due_day, 181),),
        cause_ids=(column.last_event_id,),
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "test_research_and_training_window",
            "source_refs": [{"kind": "scenario", "id": "field_drill_composition"}],
            "observed_day": world.clock.absolute_day,
        }})
    world.society.detachments[column.id] = column.model_copy(
        update={"due_day": 181, "last_event_id": upkeep_window.id})
    world.agenda.cancel(column_id)
    world.agenda.schedule(ScheduledSituation(column_id, "force", 181))
    from src.sim.medieval.economy import monthly_workforce
    from src.sim.medieval.research import (progress_research, researcher_work_options,
                                           start_research)
    from src.sim.medieval.research_policy import execute_research_option, research_options
    from src.systems.time import WorldClock

    research = next(item for item in research_options(world, OWNER)
                    if item.technology_id == "field_drill")
    research_stock_before = world.economy.stocks[research.stock_id].goods["tools"]
    research_funds_before = world.economy.accounts[research.account_id].balance
    sponsor_decision = record_event(
        world, "research_option_decided", "A instituição financiou o exercício de campo.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}}, decision=research.decision())
    execute_research_option(world, OWNER, research.id, sponsor_decision.id)
    world.agenda.cancel(f"character-rite-offer-review:{research.researcher_id}:{sponsor_decision.id}")
    world.clock = WorldClock(1)
    work_option = researcher_work_options(world, research.researcher_id)[0]
    researcher_decision = record_event(
        world, "researcher_work_accepted", "A pesquisadora aceitou trabalho remunerado.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}}, decision=work_option.decision(),
        cause_ids=(sponsor_decision.id,))
    project = start_research(
        world, technology_id=work_option.technology_id, site_id=work_option.site_id,
        stock_id=work_option.stock_id, account_id=work_option.account_id,
        researcher_id=work_option.researcher_id,
        sponsor_decision_id=work_option.sponsor_decision_id,
        researcher_decision_id=researcher_decision.id)
    assert not world.knowledge.knows(OWNER, "field_drill")
    for day in (30, 60, 90, 120, 150, 180):
        world.clock = WorldClock(day)
        progress_research(world, monthly_workforce(world))
    knowledge = next(item for item in world.knowledge.technologies.values()
                     if item.owner_ref == OWNER and item.technology_id == "field_drill")
    assert knowledge.channel == "research"
    assert world.research.projects[project.id].stage == "completed"
    assert world.economy.stocks[research.stock_id].goods["tools"] < research_stock_before
    assert world.economy.accounts[research.account_id].balance < research_funds_before

    baseline = field_strength(world, world.society.detachments[column_id])[0]
    option = next(item for item in training_options(world, OWNER, detachment_id=column_id)
                  if item.technology_id == "field_drill")
    training_stock_before = world.economy.stocks[option.stock_id].goods["tools"]
    rations_before = world.society.detachments[column_id].provisions
    training = start_training(world, OWNER, option.id, decide(world, option).id)
    assert world.economy.stocks[option.stock_id].goods["tools"] == training_stock_before - option.tool_cost
    assert field_strength(world, world.society.detachments[column_id])[0] == baseline
    for _ in range(3):
        tick(world)
    completed = world.society.detachment_trainings[training.id].last_event_id
    trained_strength = field_strength(world, world.society.detachments[column_id])[0]
    assert trained_strength == baseline + world.society.detachments[column_id].count
    assert world.society.detachments[column_id].provisions == rations_before - 3 * world.society.detachments[column_id].count

    resident = next(item for item in world.society.population.values()
                    if item.settlement_id == "ferroalto" and item.occupation == "soldier")
    source_id = resident.id
    rival_decision = record_event(world, "fixture_rival_decided", "Coluna rival presente.",
                                  fact_kind=FactKind.DECISION,
                                  decision={"action": "raise_detachment", "actor_ref": RIVAL.to_dict()})
    arrival = record_event(world, "fixture_rival_present", "Presença física rival.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("detachment", "detachment:drill-rival", "stage", None, "present"),),
                           cause_ids=(rival_decision.id,))
    rival = Detachment(id="detachment:drill-rival", owner_ref=RIVAL, source_group_id=source_id,
                       count=resident.count, location_id=SETTLEMENT, destination_id=SETTLEMENT,
                       provisions=160, stage="present", started_day=world.clock.absolute_day,
                       due_day=world.clock.absolute_day + 1,
                       decision_event_id=rival_decision.id, last_event_id=arrival.id)
    world.society.detachments[rival.id] = rival
    world.agenda.schedule(ScheduledSituation(rival.id, "force", rival.due_day))
    detect_force_standoffs(world, rival.id)
    offered = field_engagement_offer_options(world, OWNER)[0]
    offer_field_engagement(world, OWNER, offered.id, decide(world, offered).id)
    tick(world)
    joined = field_engagement_join_options(world, RIVAL)[0]
    join_field_engagement(world, RIVAL, joined.id, decide(world, joined).id)
    battle = next(event for event in reversed(world.events)
                  if event.event_type == "field_engagement_resolved")
    assert completed in {link.cause_event_id for link in battle.causal_links}
    assert knowledge.event_id in {link.cause_event_id for link in battle.causal_links}
    path = tmp_path / "trained-battle.mws"
    save_world(world, path)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True

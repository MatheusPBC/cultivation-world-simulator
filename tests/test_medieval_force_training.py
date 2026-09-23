"""Institutional knowledge trains a real column only through material work."""

import pytest

from src.classes.event import FactKind
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
                 if item.settlement_id == SETTLEMENT)
    source_id = f"pop:{SETTLEMENT}:{group.people}:soldier:drill"
    world.society.population[source_id] = group.model_copy(
        update={"id": source_id, "occupation": "soldier", "count": 20})
    decision = record_event(world, "fixture_column_decided", "Coluna presente na premissa pressionada.",
                            fact_kind=FactKind.DECISION,
                            decision={"action": "raise_detachment", "actor_ref": OWNER.to_dict()})
    arrival = record_event(world, "fixture_column_present", "A coluna está no assentamento.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("detachment", "detachment:drill", "stage", None, "present"),),
                           cause_ids=(decision.id,))
    column = Detachment(id="detachment:drill", owner_ref=OWNER, source_group_id=source_id,
                        count=20, location_id=SETTLEMENT, destination_id=SETTLEMENT,
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
                        fact_kind=FactKind.DECISION, decision=option.decision())


def tick(world):
    world.clock = world.clock.advance(1)
    resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))


def test_knowledge_alone_grants_no_strength_but_paid_dated_training_does(tmp_path):
    world, column_id = world_with_column()
    baseline = field_strength(world, world.society.detachments[column_id])[0]
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
    assert field_strength(world, world.society.detachments[column_id])[0] == baseline + 20
    completion = world.event_index()[world.society.detachment_trainings[training.id].last_event_id]
    assert completion.event_type == "detachment_training_completed"
    path = tmp_path / "trained-column.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    assert field_strength(restored, restored.society.detachments[column_id])[0] == baseline + 20
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
    tick(world)
    assert world.society.detachment_trainings[training.id].stage == "lapsed"
    assert field_strength(world, world.society.detachments[column_id])[0] == 40


def test_siegecraft_requires_separate_instruction_after_field_drill():
    world, column_id = world_with_column()
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
    assert field_strength(world, world.society.detachments[column_id])[0] == 100


def test_field_logistics_equips_existing_bag_only_after_own_dated_training(tmp_path):
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
    training = start_training(world, OWNER, logistics.id, decide(world, logistics).id)
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


def test_field_battle_cites_the_column_training_instead_of_institutional_knowledge(tmp_path):
    world, column_id = world_with_column()
    learn(world, "field_drill")
    option = training_options(world, OWNER)[0]
    training = start_training(world, OWNER, option.id, decide(world, option).id)
    for _ in range(3):
        tick(world)
    completed = world.society.detachment_trainings[training.id].last_event_id

    resident = next(item for item in world.society.population.values()
                    if item.settlement_id == "ferroalto")
    source_id = f"pop:ferroalto:{resident.people}:soldier:battle"
    world.society.population[source_id] = resident.model_copy(
        update={"id": source_id, "occupation": "soldier", "count": 20})
    rival_decision = record_event(world, "fixture_rival_decided", "Coluna rival presente.",
                                  fact_kind=FactKind.DECISION,
                                  decision={"action": "raise_detachment", "actor_ref": RIVAL.to_dict()})
    arrival = record_event(world, "fixture_rival_present", "Presença física rival.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("detachment", "detachment:drill-rival", "stage", None, "present"),),
                           cause_ids=(rival_decision.id,))
    rival = Detachment(id="detachment:drill-rival", owner_ref=RIVAL, source_group_id=source_id,
                       count=20, location_id=SETTLEMENT, destination_id=SETTLEMENT,
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
    path = tmp_path / "trained-battle.mws"
    save_world(world, path)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True

"""A paid bilateral technique transfer only matters after local field work."""

from dataclasses import replace

from src.classes.event import FactKind
from src.classes.society.force import Detachment
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.field_engagement import field_strength
from src.sim.medieval.force_training import start_training, training_options
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import learn_technology
from src.sim.medieval.teaching import teach_technology
from src.sim.medieval.technology_sale import (
    execute_technology_sale, record_technology_sale_acceptance,
    record_technology_sale_request, technology_sale_acceptance_options,
    technology_sale_options,
)
from src.sim.medieval.technology_sighting import disclosure_options, execute_disclosure
from src.systems.calendar_agenda import ScheduledSituation
from tests.test_medieval_force_training import OWNER, RIVAL, decide, learn, tick, world_with_column


def test_bilateral_teaching_needs_local_training_before_field_effect(tmp_path):
    world, column_id = world_with_column()
    source = record_event(world, "fixture_teacher_research_decided", "Pesquisa prévia da instituição docente.",
                          fact_kind=FactKind.DECISION,
                          decision={"action": "research", "actor_ref": RIVAL.to_dict(),
                                    "technology_id": "field_drill"})
    learn_technology(world, RIVAL, "field_drill", "research", (source.id,))
    column = world.society.detachments[column_id]
    baseline = field_strength(world, column)[0]
    assert not training_options(world, OWNER, detachment_id=column_id)

    terms = {"technology_id": "field_drill", "teacher_ref": RIVAL.to_dict(),
             "student_ref": OWNER.to_dict()}
    teacher = record_event(world, "teaching_offered", "Ensinar a doutrina conhecida.",
                           fact_kind=FactKind.DECISION,
                           decision={**terms, "action": "teach", "actor_ref": RIVAL.to_dict()})
    learner = record_event(world, "teaching_accepted", "Receber a instrução.",
                           fact_kind=FactKind.DECISION,
                           decision={**terms, "action": "learn", "actor_ref": OWNER.to_dict()})
    teach_technology(world, teacher.id, learner.id)
    acquired = world.knowledge.technologies["technology:polity:auren:field_drill"]
    assert acquired.channel == "teaching"
    assert field_strength(world, world.society.detachments[column_id])[0] == baseline

    option = next(item for item in training_options(world, OWNER, detachment_id=column_id)
                  if item.technology_id == "field_drill")
    tools_before = world.economy.stocks[option.stock_id].goods["tools"]
    training = start_training(world, OWNER, option.id, decide(world, option).id)
    assert world.economy.stocks[option.stock_id].goods["tools"] == tools_before - option.tool_cost
    for _ in range(3):
        tick(world)
    assert world.society.detachment_trainings[training.id].stage == "completed"
    assert field_strength(world, world.society.detachments[column_id])[0] == baseline + column.count
    completion = world.event_index()[world.society.detachment_trainings[training.id].last_event_id]
    assert acquired.event_id in {link.cause_event_id for link in completion.causal_links}

    path = tmp_path / "taught-and-trained.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_paid_technique_sale_needs_local_training_before_field_effect(tmp_path):
    world, _ = world_with_column()
    learn(world, "field_drill")
    # Pressured-map premise: the buyer has a usable military instruction site.
    site = world.map.infrastructure_sites["minas-de-ferroalto"]
    world.map.infrastructure_sites[site.id] = replace(
        site, capability_ids=(*site.capability_ids, "military_training"))
    disclosure = next(option for option in disclosure_options(world, OWNER)
                      if option.recipient_ref == RIVAL and option.technology_id == "field_drill")
    disclosed = record_event(world, "technology_disclosure_decided", "Divulgar a técnica.",
                             fact_kind=FactKind.DECISION, decision=disclosure.decision(),
                             cause_ids=disclosure.causes())
    sighting = execute_disclosure(world, disclosure, disclosed.id)

    resident = next(group for group in world.society.population.values()
                    if group.settlement_id == "ferroalto")
    source_id = f"pop:ferroalto:{resident.people}:soldier:diffusion"
    world.society.population[source_id] = resident.model_copy(
        update={"id": source_id, "occupation": "soldier", "count": 20})
    raised = record_event(world, "fixture_rival_column_decided", "Coluna na premissa pressionada.",
                          fact_kind=FactKind.DECISION,
                          decision={"action": "raise_detachment", "actor_ref": RIVAL.to_dict()})
    arrival = record_event(world, "fixture_rival_column_present", "Coluna presente em Ferroalto.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("detachment", "detachment:diffusion", "stage", None, "present"),),
                           cause_ids=(raised.id,))
    column = Detachment(id="detachment:diffusion", owner_ref=RIVAL, source_group_id=source_id,
                        count=20, location_id="ferroalto", destination_id="ferroalto",
                        provisions=220, stage="present", started_day=world.clock.absolute_day,
                        due_day=world.clock.absolute_day + 1,
                        decision_event_id=raised.id, last_event_id=arrival.id)
    world.society.detachments[column.id] = column
    world.agenda.schedule(ScheduledSituation(column.id, "force", column.due_day))
    baseline = field_strength(world, column)[0]
    assert not training_options(world, RIVAL, detachment_id=column.id)

    sale = next(option for option in technology_sale_options(world, RIVAL)
                if option.technology_id == "field_drill")
    buyer_balance = world.economy.accounts[sale.buyer_account_id].balance
    request = record_technology_sale_request(world, RIVAL, sale.id)
    acceptance = next(option for option in technology_sale_acceptance_options(world, OWNER)
                      if option.request_event_id == request.id)
    consent = record_technology_sale_acceptance(world, OWNER, acceptance.id)
    receipt = execute_technology_sale(world, RIVAL, sale.id, request.id, consent.id)
    learned = world.knowledge.technologies[f"technology:polity:{RIVAL.id}:field_drill"]
    assert learned.channel == "sale" and sighting.event_id in {
        link.cause_event_id for link in receipt.causal_links}
    assert world.economy.accounts[sale.buyer_account_id].balance == buyer_balance - sale.amount
    assert field_strength(world, world.society.detachments[column.id])[0] == baseline

    training_option = next(option for option in training_options(world, RIVAL, detachment_id=column.id)
                           if option.technology_id == "field_drill")
    tools_before = world.economy.stocks[training_option.stock_id].goods["tools"]
    training = start_training(world, RIVAL, training_option.id, decide(world, training_option).id)
    assert world.economy.stocks[training_option.stock_id].goods["tools"] == tools_before - training_option.tool_cost
    assert field_strength(world, world.society.detachments[column.id])[0] == baseline
    for _ in range(3):
        tick(world)
    assert world.society.detachment_trainings[training.id].stage == "completed"
    assert field_strength(world, world.society.detachments[column.id])[0] == baseline + 20
    completed = world.event_index()[world.society.detachment_trainings[training.id].last_event_id]
    assert learned.event_id in {link.cause_event_id for link in completed.causal_links}

    path = tmp_path / "sold-and-trained.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True

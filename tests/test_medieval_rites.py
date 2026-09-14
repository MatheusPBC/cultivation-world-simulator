"""A rite is paid work with witnesses: bounded relief, never created matter."""

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.rites import (record_rite_offer, rite_offer_options, rite_sponsor_options,
                                    rite_stop_options, sponsor_rite, stop_rite)
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports

SPONSOR = EntityRef("organization", "ordem-da-aurora")
PLACE = "pedraclara"
BLUEPRINT = "rite-of-restoration"


def decide(world, option):
    return record_event(world, "rite_decided", "Decisão institucional sobre o rito.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def ailing_world(health=700):
    """Prepared distress: Pedraclara is unwell and the order keeps a healer."""
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    need = world.economy.needs[PLACE]
    world.economy.needs[need.id] = need.model_copy(update={"health": health})
    healer = next(item for item in sorted(world.society.characters.values(), key=lambda c: c.id)
                  if item.death_day is None and item.location_id == PLACE)
    world.society.characters[healer.id] = healer.model_copy(
        update={"skills": healer.skills.model_copy(update={"restoration_magic": 40})})
    refresh_settlement_reports(world)
    return world, world.society.characters[healer.id]


def totals(world):
    return ({key: sum(item.goods.get(key, 0) for item in world.economy.stocks.values())
             for key in world.economy.resources},
            sum(item.balance for item in world.economy.accounts.values()),
            sum(item.count for item in world.society.population.values()))


def started(world, healer):
    offer_option = next(item for item in rite_offer_options(world, healer.id) if item.sponsor_ref == SPONSOR)
    offer = record_rite_offer(world, healer.id, offer_option.id)
    sponsor_option = next(item for item in rite_sponsor_options(world, SPONSOR) if item.offer_event_id == offer.id)
    return offer, sponsor_rite(world, SPONSOR, sponsor_option.id, decide(world, sponsor_option).id)


def tick_to(world, day):
    while world.clock.absolute_day < day:
        world.clock = world.clock.advance(1)
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))


def test_a_paid_rite_relieves_local_health_and_is_visible_while_it_runs(tmp_path):
    world, healer = ailing_world()
    goods, money, people = totals(world)
    blueprint = world.research.rite_blueprints[BLUEPRINT]
    before_health = world.economy.needs[PLACE].health

    offer, rite = started(world, healer)
    assert offer.fact_kind == FactKind.DECISION and not offer.deltas
    assert rite.stage == "officiating" and rite.due_day == rite.started_day + blueprint.days
    assert totals(world) == (goods, money, people), "starting consumes nothing"
    assert world.economy.needs[PLACE].health == before_health

    refresh_settlement_reports(world)
    report = world.knowledge.settlement_report(EntityRef("polity", "auren"), PLACE)
    assert report.rite_underway is True
    assert BLUEPRINT not in report.observation() and rite.stock_id not in report.observation()
    assert str(blueprint.min_skill) not in report.observation()

    tick_to(world, rite.due_day)

    done = world.research.rites[rite.id]
    assert done.stage == "completed"
    assert world.economy.needs[PLACE].health == before_health + blueprint.health_gain_permille
    after_goods, after_money, after_people = totals(world)
    for resource_id, amount in blueprint.inputs.items():
        assert after_goods[resource_id] == goods[resource_id] - amount
    assert after_money == money and after_people == people, "no money or people were created"
    assert world.economy.payrolls[rite.id].gross == blueprint.assistants * blueprint.wage_per_worker
    receipt = next(item for item in world.events if item.id == done.last_event_id)
    assert receipt.event_type == "rite_completed"
    assert any(delta.owner_kind == "subsistence" and delta.aspect == "health" for delta in receipt.deltas)
    assert not any(item.event_type in {"creature_attacked", "spell_cast"} for item in world.events)

    refresh_settlement_reports(world)
    assert world.knowledge.settlement_report(EntityRef("polity", "auren"), PLACE).rite_underway is False
    path = tmp_path / "rite.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_local_observation_and_assembly_denial_interrupt_on_the_next_dated_tick(tmp_path):
    world, healer = ailing_world()
    _, rite = started(world, healer)
    before_health = world.economy.needs[PLACE].health
    goods, money, people = totals(world)

    # Forged and replayed selections change nothing.
    cancel = next(item for item in rite_stop_options(world, SPONSOR) if item.kind == "cancel")
    with pytest.raises(ValueError, match="stale|unknown"):
        stop_rite(world, SPONSOR, cancel.id + ":forged", decide(world, cancel).id)
    assert world.research.rites[rite.id].stage == "officiating"

    # A local military column observes only the bounded public work. It needs
    # a genuine prepared position before it can deny assembly on the next tick.
    outsider = EntityRef("polity", "auren")
    assert not any(item.kind == "interrupt" for item in rite_stop_options(world, outsider))
    from src.classes.society.force import Detachment
    from src.sim.medieval.force import force_position_options, prepare_force_position
    from src.sim.medieval.assembly_denial import assembly_denial_options, execute_assembly_denial_option
    assert not assembly_denial_options(world, outsider), "a report alone is not a local armed denial"
    cohort = next(item for item in world.society.population.values() if item.settlement_id == PLACE)
    soldiers = cohort.model_copy(update={"id": f"pop:{PLACE}:{cohort.people}:soldier",
                                         "occupation": "soldier", "count": 5})
    world.society.population[soldiers.id] = soldiers
    world.society.detachments["detachment:outsider"] = Detachment(
        id="detachment:outsider", owner_ref=outsider, source_group_id=soldiers.id, count=5,
            location_id=PLACE, destination_id=PLACE, route_ids=(), route_index=0, provisions=25,
        stage="present", started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 1,
        decision_event_id=rite.sponsor_decision_id, last_event_id=rite.last_event_id)
    refresh_settlement_reports(world)
    goods, money, people = totals(world)

    observation = world.knowledge.rite_observation(outsider, rite.site_id)
    assert observation is not None and observation.settlement_id == PLACE
    assert set(observation.model_dump()) == {"id", "recipient_ref", "settlement_id", "site_id", "stage",
                                             "observed_day", "assistants_band", "event_id", "channel"}
    assert rite.officiant_id not in str(observation.model_dump())
    assert rite.stock_id not in str(observation.model_dump())
    assert rite.account_id not in str(observation.model_dump())
    assert rite.blueprint_id not in str(observation.model_dump())

    position_option = next(item for item in force_position_options(world, outsider)
                           if item.detachment_id == "detachment:outsider")
    position_decision = record_event(world, "force_position_decided", "Preparar posição local.",
                                     fact_kind=FactKind.DECISION, decision=position_option.decision())
    position = prepare_force_position(world, outsider, position_option.id, position_decision.id)
    tick_to(world, position.ready_day)
    denial = next(item for item in assembly_denial_options(world, outsider)
                  if item.detachment_id == "detachment:outsider" and item.kind == "deny")
    denial_decision = record_event(world, "assembly_denial_decided", "Negar assembleia observada.",
                                   fact_kind=FactKind.DECISION, decision=denial.decision())
    with pytest.raises(ValueError, match="stale|unknown"):
        execute_assembly_denial_option(world, outsider, denial.id + ":forged", denial_decision.id)
    assert rite.site_id not in world.society.assembly_denials
    execute_assembly_denial_option(world, outsider, denial.id, denial_decision.id)
    assert rite.site_id in world.society.assembly_denials
    assert world.research.rites[rite.id].stage == "officiating"
    tick_to(world, world.clock.absolute_day + 1)

    stopped = world.research.rites[rite.id]
    assert stopped.stage == "interrupted"
    assert world.economy.needs[PLACE].health == before_health, "interruption cures nothing"
    after_goods, after_money, after_people = totals(world)
    blueprint = world.research.rite_blueprints[BLUEPRINT]
    for resource_id, amount in blueprint.inputs.items():
        assert after_goods[resource_id] == goods[resource_id] - amount, "committed reagents were lost"
    assert after_money == money and after_people == people
    assert rite.id not in world.economy.payrolls, "an interrupted rite pays no assistants"
    assert world.society.settlements[PLACE].occupier_id is None
    assert not any(item.event_type in {"battle_resolved", "casualties_taken"} for item in world.events)
    assert world.agenda.get(rite.id) is None
    assert any(item.event_type == "assembly_denied" for item in world.events)
    interrupted_event = next(item for item in world.events if item.event_type == "rite_interrupted")
    denial_event = next(item for item in world.events if item.event_type == "assembly_denied")
    assert denial_event.id in {link.cause_event_id for link in interrupted_event.causal_links}
    path = tmp_path / "rite-denied.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

    # Departure revokes only the physical denial. It cannot survive the column.
    from src.sim.medieval.force import DISBAND_ACTION, execute_force_option, force_options
    disband = next(item for item in force_options(world, outsider)
                   if item.detachment_id == "detachment:outsider" and item.kind == "disband")
    disband_decision = record_event(world, "detachment_decided", "Dissolver coluna local.",
                                    fact_kind=FactKind.DECISION, decision=disband.decision())
    execute_force_option(world, outsider, disband.id, disband_decision.id, DISBAND_ACTION)
    assert rite.site_id not in world.society.assembly_denials
    assert any(item.event_type == "assembly_denial_lifted" for item in world.events)
    refresh_settlement_reports(world)
    assert world.knowledge.settlement_report(outsider, PLACE).rite_underway is False

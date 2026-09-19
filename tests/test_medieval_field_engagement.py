"""A joined field engagement is deterministic and never grants territory."""

import asyncio
import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.field_engagement import (field_engagement_join_options, field_engagement_offer_options,
                                               field_strength, join_field_engagement, offer_field_engagement)
from src.sim.medieval.force import (detect_force_standoffs, force_position_options,
                                    prepare_force_position, raise_detachment, raise_options,
                                    withdraw_detachment, withdrawal_options)
from src.sim.medieval.force_command import (APPOINT_ACTION, SET_DOCTRINE_ACTION,
                                            appoint_detachment_commander, detachment_command_options,
                                            effective_doctrine, set_detachment_doctrine)
from src.sim.medieval.force_contact_policy import review_force_contacts
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import learn_technology
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


OWNER = EntityRef("polity", "auren")
RIVAL = EntityRef("polity", "escarlia")
HOME = "campomanso"
TARGET = "salgueiro"


def decide(world, option):
    return record_event(world, "field_engagement_decided", "Decisão canônica de campo.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def prepared_challenger_world(*, challenger_count=30, defender_count=50, defender_provisions=100, prepared=True):
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": challenger_count})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    raise_option = next(item for item in raise_options(world, OWNER, days=20) if item.destination_id == TARGET)
    own = raise_detachment(world, OWNER, raise_option.id, decide(world, raise_option).id, days=20)
    while world.society.detachments[own.id].stage == "marching":
        tick(world)
    if prepared:
        position = force_position_options(world, OWNER, detachment_id=own.id)[0]
        prepare_force_position(world, OWNER, position.id, decide(world, position).id)
        for _ in range(3):
            tick(world)
    own = world.society.detachments[own.id]

    resident = next(item for item in world.society.population.values() if item.settlement_id == "ferroalto")
    rival_group = resident.model_copy(update={"id": f"pop:ferroalto:{resident.people}:soldier",
                                              "occupation": "soldier", "count": defender_count})
    world.society.population[rival_group.id] = rival_group
    rival = Detachment(id="detachment:engagement-rival", owner_ref=RIVAL, source_group_id=rival_group.id,
                       count=defender_count, location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0,
                       provisions=defender_provisions, stage="present", started_day=world.clock.absolute_day,
                       due_day=world.clock.absolute_day + 1, decision_event_id=own.decision_event_id,
                       last_event_id=own.last_event_id)
    world.society.detachments[rival.id] = rival
    standoff = detect_force_standoffs(world, rival.id)[0]
    return world, own.id, rival.id, standoff.id


def offer(world, *, detachment_id=None, counterparty_detachment_id=None):
    option = next(item for item in field_engagement_offer_options(world, OWNER)
                  if ((detachment_id is None or item.detachment_id == detachment_id)
                      and (counterparty_detachment_id is None
                           or counterparty_detachment_id in world.society.force_standoffs[item.standoff_id].detachment_ids)))
    return offer_field_engagement(world, OWNER, option.id, decide(world, option).id)


def add_column(world, source_id, *, identity, owner, count, location_id=TARGET, stage="present"):
    """A factual fixture column; its people remain in the real source cohort."""
    source = world.society.population[source_id]
    world.society.population[source.id] = source.model_copy(update={"count": source.count + count})
    arrival = record_event(world, "test_reinforcement_present", "Fixture factual de coluna adicional.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("detachment", identity, "stage", None, stage),))
    route_ids = () if stage == "present" else (next(iter(world.map.routes)),)
    column = Detachment(
        id=identity, owner_ref=owner, source_group_id=source.id, count=count,
        location_id=location_id, destination_id=HOME if stage == "marching" else location_id,
        route_ids=route_ids, route_index=0, provisions=count * 10,
        stage=stage, started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 30,
        decision_event_id=arrival.id, last_event_id=arrival.id,
    )
    world.society.detachments[column.id] = column
    return column, arrival.id


def press_reinforcement(world, source_id, *, identity, owner, count, commander_id):
    """A real prior contact plus an effective press order makes support eligible."""
    column, arrival_id = add_column(world, source_id, identity=identity, owner=owner, count=count)
    detect_force_standoffs(world, column.id)
    commander = world.society.characters[commander_id]
    world.society.characters[commander.id] = commander.model_copy(update={"location_id": TARGET})
    appoint = next(item for item in detachment_command_options(world, owner, detachment_id=column.id)
                   if item.decision()["action"] == APPOINT_ACTION)
    appoint_detachment_commander(world, owner, appoint.id, decide(world, appoint).id)
    press = next(item for item in detachment_command_options(world, owner, detachment_id=column.id)
                 if item.decision()["action"] == SET_DOCTRINE_ACTION and item.doctrine == "press")
    set_detachment_doctrine(world, owner, press.id, decide(world, press).id)
    tick(world)
    assert effective_doctrine(world, column.id) == "press"
    return world.society.detachments[column.id], arrival_id


def set_doctrine(world, owner, detachment_id, doctrine):
    option = next(item for item in detachment_command_options(world, owner, detachment_id=detachment_id)
                  if item.decision()["action"] == SET_DOCTRINE_ACTION and item.doctrine == doctrine)
    return set_detachment_doctrine(world, owner, option.id, decide(world, option).id)


def resolve_offer(world, *, detachment_id=None, counterparty_detachment_id=None):
    engagement = offer(world, detachment_id=detachment_id, counterparty_detachment_id=counterparty_detachment_id)
    tick(world)
    join = field_engagement_join_options(world, RIVAL)[0]
    return join_field_engagement(world, RIVAL, join.id, decide(world, join).id)


async def accept_through_provider(world, monkeypatch, prompts):
    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": next(choice["id"] for choice in payload["choices"]
                               if choice["label"].startswith("Aceitar o combate"))}

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    due = tick(world)
    rival_notice = world.knowledge.force_contacts_for_actor(RIVAL)[0]
    await review_force_contacts(world, (next(item for item in due if item.id.endswith(rival_notice.id)),))


async def test_prepared_supplied_thirty_beats_hungry_fifty_with_only_field_effects(tmp_path, monkeypatch):
    world, own_id, rival_id, standoff_id = prepared_challenger_world()
    challenger = world.society.detachments[own_id]
    defender = world.society.detachments[rival_id]
    assert field_strength(world, challenger) == (120, True, True)
    assert field_strength(world, defender) == (100, False, False)
    people_before = world.society.total_population
    engagement = offer(world)
    assert engagement.status == "offered" and world.society.detachments[own_id].stage == "present"
    assert len(world.knowledge.field_engagement_offer_notices) == 1

    prompts = []
    await accept_through_provider(world, monkeypatch, prompts)
    engagement = world.society.field_engagements[engagement.id]
    assert engagement.status == "resolved" and engagement.winner_ref == OWNER
    assert (engagement.challenger_casualties, engagement.defender_casualties) == (2, 10)
    assert world.society.total_population == people_before - 12
    assert world.society.detachments[own_id].count == 28
    assert world.society.detachments[rival_id].stage == "disbanded"
    assert all(world.society.detachments[item].count > 0 for item in (own_id, rival_id))
    assert world.society.force_positions[f"force-position:{own_id}"].stage == "prepared"
    assert world.society.force_standoffs[standoff_id].stage == "resolved"
    assert world.society.settlements[TARGET].occupier_id is None
    resolution = next(event for event in world.events if event.event_type == "field_engagement_resolved")
    assert any(delta.aspect == f"terrain_modifier:{own_id}" for delta in resolution.deltas)
    assert any(delta.aspect == f"fatigue_level:{own_id}" for delta in resolution.deltas)
    morale_delta = next(delta for delta in resolution.deltas if delta.aspect == f"morale_level:{own_id}")
    assert int(morale_delta.after) in {0, 1, 2}
    assert "30" not in prompts[0] and "provisions" not in prompts[0] and "anchor_site_id" not in prompts[0]
    assert all(notice.counterparty_strength_band in {"1-9", "10-24", "25-49", "50-99", "100+"}
               for notice in world.knowledge.field_engagement_outcome_notices.values())

    path = tmp_path / "field-engagement.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    assert not any(event.event_type in {"battle_resolved", "loot_taken"} for event in world.events)


def test_learned_field_drill_has_only_a_bounded_material_strength_effect():
    world, own_id, _, _ = prepared_challenger_world(prepared=False)
    detachment = world.society.detachments[own_id]
    before = field_strength(world, detachment)
    decision = record_event(
        world, "field_training_decided", "Autorizar exercício de campo.",
        fact_kind=FactKind.DECISION,
        decision={"action": "research", "actor_ref": OWNER.to_dict(), "technology_id": "field_drill"},
    )
    learn_technology(world, OWNER, "field_drill", "teaching", (decision.id,))
    after = field_strength(world, detachment)
    assert before == (detachment.count * 3, False, True)
    assert after == (detachment.count * 4, False, True)
    assert after[0] - before[0] == detachment.count


def test_siegecraft_requires_field_drill_and_adds_only_one_more_strength_step():
    world, own_id, _, _ = prepared_challenger_world(prepared=False)
    detachment = world.society.detachments[own_id]
    blocked = record_event(
        world, "siegecraft_without_drill", "Tentativa de aprender cerco sem base.",
        fact_kind=FactKind.DECISION,
        decision={"action": "research", "actor_ref": OWNER.to_dict(), "technology_id": "siegecraft"},
    )
    with pytest.raises(ValueError, match="prerequisites"):
        learn_technology(world, OWNER, "siegecraft", "teaching", (blocked.id,))
    first = record_event(
        world, "field_training_decided", "Autorizar exercício de campo.",
        fact_kind=FactKind.DECISION,
        decision={"action": "research", "actor_ref": OWNER.to_dict(), "technology_id": "field_drill"},
    )
    learn_technology(world, OWNER, "field_drill", "teaching", (first.id,))
    second = record_event(
        world, "siegecraft_training_decided", "Autorizar instrução de engenharia de cerco.",
        fact_kind=FactKind.DECISION,
        decision={"action": "research", "actor_ref": OWNER.to_dict(), "technology_id": "siegecraft"},
    )
    learn_technology(world, OWNER, "siegecraft", "teaching", (second.id, first.id))
    assert field_strength(world, detachment)[0] == detachment.count * 5


def test_withdrawal_or_missing_join_lapses_without_battle():
    world, _, rival_id, _ = prepared_challenger_world(defender_provisions=999)
    engagement = offer(world)
    withdrawal = withdrawal_options(world, RIVAL, detachment_id=rival_id)[0]
    withdraw_detachment(world, RIVAL, withdrawal.id, decide(world, withdrawal).id)
    while world.society.field_engagements[engagement.id].status == "offered":
        tick(world)
    assert world.society.field_engagements[engagement.id].status == "lapsed"
    assert not world.knowledge.field_engagement_outcome_notices
    assert not any(event.event_type in {"field_engagement_resolved", "battle_resolved", "loot_taken"}
                   for event in world.events)


def test_tie_is_symmetric_and_stale_or_provider_off_cannot_start_combat(monkeypatch):
    world, own_id, rival_id, standoff_id = prepared_challenger_world(challenger_count=30, defender_count=30,
                                                                       defender_provisions=999, prepared=False)
    option = field_engagement_offer_options(world, OWNER)[0]
    with pytest.raises(ValueError, match="stale or unknown"):
        offer_field_engagement(world, OWNER, option.id + ":forged", decide(world, option).id)
    assert not world.society.field_engagements

    offer(world)
    tick(world)
    join = field_engagement_join_options(world, RIVAL)[0]
    result = join_field_engagement(world, RIVAL, join.id, decide(world, join).id)
    assert result.winner_ref is None and (result.challenger_casualties, result.defender_casualties) == (3, 3)
    assert world.society.detachments[own_id].count == world.society.detachments[rival_id].count == 27
    assert world.society.force_standoffs[standoff_id].stage == "active"

    blocked, _, _, _ = prepared_challenger_world()
    notice = blocked.knowledge.force_contacts_for_actor(OWNER)[0]
    before = world_snapshot(blocked)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    asyncio.run(review_force_contacts(blocked, (blocked.agenda.get(f"force-contact-review:{notice.id}"),)))
    assert world_snapshot(blocked) == before

    silent, _, _, _ = prepared_challenger_world()
    engagement = offer(silent)
    silent.config = silent.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def no_action(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    due = tick(silent)
    rival_notice = silent.knowledge.force_contacts_for_actor(RIVAL)[0]
    asyncio.run(review_force_contacts(silent, (next(item for item in due if item.id.endswith(rival_notice.id)),)))
    assert silent.society.field_engagements[engagement.id].status == "offered"
    assert not silent.knowledge.field_engagement_outcome_notices


def test_present_reinforcement_changes_result_debits_cohorts_and_cleans_losing_side():
    baseline, _, _, _ = prepared_challenger_world(challenger_count=30, defender_count=70,
                                                   defender_provisions=999)
    assert resolve_offer(baseline).winner_ref == RIVAL

    world, own_id, rival_id, _ = prepared_challenger_world(challenger_count=30, defender_count=70,
                                                            defender_provisions=999)
    primary = world.society.detachments[own_id]
    reinforcement, _ = press_reinforcement(
        world, primary.source_group_id, identity="detachment:engagement-reinforcement",
        owner=OWNER, count=70, commander_id="character:002")
    rival_reinforcement, _ = press_reinforcement(
        world, world.society.detachments[rival_id].source_group_id,
        identity="detachment:engagement-rival-reinforcement",
        owner=RIVAL, count=30, commander_id="character:012")
    source_before = world.society.population[reinforcement.source_group_id].count
    reinforcement_cause_id = reinforcement.last_event_id

    result = resolve_offer(world, detachment_id=own_id, counterparty_detachment_id=rival_id)

    assert result.winner_ref == OWNER
    assert result.challenger_casualties == 16
    assert result.defender_casualties == 20
    assert 0 < world.society.detachments[own_id].count < 30
    assert 0 < world.society.detachments[reinforcement.id].count < 70
    assert (source_before - world.society.population[reinforcement.source_group_id].count
            == result.challenger_casualties)
    resolution = next(event for event in world.events if event.event_type == "field_engagement_resolved")
    assert reinforcement_cause_id in {link.cause_event_id for link in resolution.causal_links}
    assert any(delta.aspect == f"challenger_column:{reinforcement.id}" for delta in resolution.deltas)
    assert any(delta.owner_kind == "detachment" and delta.owner_id == reinforcement.id and delta.aspect == "count"
               for delta in resolution.deltas)
    rival_notice = next(item for item in world.knowledge.field_engagement_outcome_notices.values()
                        if item.recipient_ref == RIVAL)
    assert rival_notice.own_detachment_id == rival_id
    assert rival_notice.own_casualties == result.defender_casualties
    assert rival_notice.counterparty_strength_band == "100+"
    assert world.society.detachments[rival_id].stage == "disbanded"
    assert world.society.detachments[rival_reinforcement.id].stage == "disbanded"
    assert world.society.detachments[rival_id].count > 0
    assert world.society.detachments[rival_reinforcement.id].count > 0
    assert all(standoff.stage != "active" or not {rival_id, rival_reinforcement.id}.intersection(standoff.detachment_ids)
               for standoff in world.society.force_standoffs.values())
    assert not any(item.stage == "active" and item.detachment_id in {rival_id, rival_reinforcement.id}
                   for item in world.society.route_interdictions.values())


def test_only_prior_press_columns_reinforce_and_no_action_leaves_offer_open(monkeypatch):
    world, own_id, _, _ = prepared_challenger_world(challenger_count=30, defender_count=70,
                                                     defender_provisions=999)
    primary = world.society.detachments[own_id]
    hold, _ = press_reinforcement(world, primary.source_group_id, identity="detachment:engagement-hold",
                                  owner=OWNER, count=40, commander_id="character:002")
    set_doctrine(world, OWNER, hold.id, "hold")
    # A fresh factual rival contact means the hold exclusion, rather than a
    # stale sighting, controls this column at resolution.
    rival_marker, _ = add_column(world, world.society.detachments["detachment:engagement-rival"].source_group_id,
                                 identity="detachment:engagement-marker", owner=RIVAL, count=1)
    detect_force_standoffs(world, rival_marker.id)
    tick(world)
    assert effective_doctrine(world, hold.id) == "hold"
    engagement = offer(world, detachment_id=own_id, counterparty_detachment_id="detachment:engagement-rival")
    arrival, _ = press_reinforcement(world, primary.source_group_id, identity="detachment:engagement-arrival",
                                     owner=OWNER, count=20, commander_id="character:012")

    join = field_engagement_join_options(world, RIVAL)[0]
    result = join_field_engagement(world, RIVAL, join.id, decide(world, join).id)

    assert result.winner_ref == RIVAL
    resolution = next(event for event in world.events if event.event_type == "field_engagement_resolved")
    assert next(delta.after for delta in resolution.deltas if delta.aspect == "challenger_terms") == (
        "columns=1;count=30;strength=120")
    assert world.society.detachments[hold.id].count == 40
    assert world.society.detachments[arrival.id].count == 20
    assert effective_doctrine(world, arrival.id) == "press"
    assert world.society.field_engagements[engagement.id].status == "resolved"

    silent, own_id, _, _ = prepared_challenger_world(challenger_count=30, defender_count=70,
                                                      defender_provisions=999)
    reinforcement, _ = add_column(silent, silent.society.detachments[own_id].source_group_id,
                                  identity="detachment:engagement-no-action", owner=OWNER, count=40)
    engagement = offer(silent)
    silent.config = silent.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def no_action(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    due = tick(silent)
    rival_notice = silent.knowledge.force_contacts_for_actor(RIVAL)[0]
    asyncio.run(review_force_contacts(silent, (next(item for item in due if item.id.endswith(rival_notice.id)),)))
    assert silent.society.field_engagements[engagement.id].status == "offered"
    assert silent.society.detachments[reinforcement.id].count == 40

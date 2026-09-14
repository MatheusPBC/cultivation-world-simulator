"""Memory keeps relevance of known facts; Knowledge still owns knowing them."""

import sqlite3

import pytest

from src.classes.governance.diplomacy import institutional_memory_id
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.institutional_aid import aid_remediation_options, remediate_institutional_aid
from src.sim.medieval.institutional_memory import (BREACH_VIEW, MEMORY_SPAN_DAYS, effective_salience,
                                                   institutional_view, memories_of)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from tests.test_medieval_institutional_aid import PROVIDER, REQUESTER, _breached_aid_world, decision


def breach_event_id(world, obligation_id):
    return world.relations.obligations[obligation_id].breach_event_id


def test_breach_records_notices_and_memories_for_both_parties():
    world, obligation_id = _breached_aid_world()
    breach = breach_event_id(world, obligation_id)
    event = next(item for item in world.events if item.id == breach)
    assert event.event_type == "commitment_breached"

    for party in (REQUESTER, PROVIDER):
        memory = memories_of(world, party, breach)
        assert memory is not None and memory.id == institutional_memory_id(party, breach)
        assert memory.recorded_day == memory.last_reinforced_day == event.day
        assert any(delta.owner_kind == "institutional_memory" and delta.owner_id == memory.id
                   and delta.aspect == "recorded_day" and delta.after == str(event.day)
                   for delta in event.deltas), "the breach fact itself declares the memory"
        assert any(notice.recipient_ref == party and notice.event_id == breach
                   for notice in world.knowledge.notices.values())
    # Relevance only; the memory copies no content from Knowledge.
    assert set(memories_of(world, REQUESTER, breach).model_dump()) == {
        "id", "institution_ref", "event_id", "recorded_day", "last_reinforced_day"}


def test_only_the_creditor_reads_the_breach_against_the_debtor():
    world, obligation_id = _breached_aid_world()
    assert institutional_view(world, REQUESTER, PROVIDER) == BREACH_VIEW
    assert institutional_view(world, PROVIDER, REQUESTER) == 0, "the wronged debtor invents no penalty"
    assert institutional_view(world, PROVIDER, PROVIDER) == 0
    assert institutional_view(world, REQUESTER, REQUESTER) == 0


def test_salience_decays_on_read_without_mutating_anything():
    world, obligation_id = _breached_aid_world()
    breach = breach_event_id(world, obligation_id)
    memory = memories_of(world, REQUESTER, breach)
    before = world_snapshot(world)

    assert effective_salience(world, memory) == 1000
    world.clock = world.clock.advance(MEMORY_SPAN_DAYS // 2)
    half = effective_salience(world, memory)
    assert 400 <= half <= 600
    assert institutional_view(world, REQUESTER, PROVIDER) == BREACH_VIEW * half // 1000
    world.clock = world.clock.advance(MEMORY_SPAN_DAYS)
    assert effective_salience(world, memory) == 0
    assert institutional_view(world, REQUESTER, PROVIDER) == 0

    assert world.relations.memories[memory.id] == memory
    assert {key: value for key, value in world_snapshot(world).items() if key != "clock_day"} == {
        key: value for key, value in before.items() if key != "clock_day"}


def test_remediation_preserves_the_breach_and_moves_the_creditor_view_to_minus_two(tmp_path):
    world, obligation_id = _breached_aid_world()
    breach = breach_event_id(world, obligation_id)
    refresh_route_reports(world, route_ids=("river-pedraclara-portovelho",))
    option = aid_remediation_options(world, PROVIDER)[0]
    decision_event = decision(world, option, "aid remediation")

    remediate_institutional_aid(world, PROVIDER, option.id, decision_event.id)

    obligation = world.relations.obligations[obligation_id]
    assert obligation.status == "remediated" and obligation.breach_event_id == breach
    assert next(item for item in world.events if item.id == breach).event_type == "commitment_breached"
    receipt = next(item for item in world.events if item.id == obligation.last_event_id)
    for party in (REQUESTER, PROVIDER):
        repair = memories_of(world, party, receipt.id)
        assert repair is not None and repair.recorded_day == receipt.day
        assert any(notice.recipient_ref == party and notice.event_id == receipt.id
                   for notice in world.knowledge.notices.values())
        reinforced = memories_of(world, party, breach)
        assert reinforced.last_reinforced_day == receipt.day
        assert any(delta.owner_kind == "institutional_memory" and delta.owner_id == reinforced.id
                   and delta.aspect == "last_reinforced_day" and delta.after == str(receipt.day)
                   for delta in receipt.deltas)
    assert institutional_view(world, REQUESTER, PROVIDER) == -2
    assert institutional_view(world, PROVIDER, REQUESTER) == 0

    path = tmp_path / "remembered-aid.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    assert restored.relations.memories == world.relations.memories
    assert institutional_view(restored, REQUESTER, PROVIDER) == -2


def test_the_dao_snapshot_exposes_aid_evidence_without_provider_terms():
    from src.server.medieval.queries import diplomacy_view
    world, obligation_id = _breached_aid_world()
    breach = breach_event_id(world, obligation_id)
    refresh_route_reports(world, route_ids=("river-pedraclara-portovelho",))
    option = aid_remediation_options(world, PROVIDER)[0]
    remediate_institutional_aid(world, PROVIDER, option.id, decision(world, option, "aid remediation").id)

    view = diplomacy_view(world)
    obligation = next(item for item in view.obligations if item.id == obligation_id)
    assert obligation.status == "remediated" and obligation.breach_event_id == breach

    request = next(item for item in view.aid_notices if item.kind == "request")
    assert request.requested_food > 0 and request.request_event_id
    forbidden = {"source_stock_id", "destination_stock_id", "quantity", "route_ids", "surplus", "route_option_id"}
    assert not forbidden.intersection(request.model_dump())

    remembered = {item.id: item for item in view.memories}
    assert remembered and all(0 <= item.effective_salience <= 1000 for item in remembered.values())
    assert any(item.event_id == breach and item.institution_ref == REQUESTER for item in remembered.values())

    reading = next(item for item in view.aid_readings
                   if item.observer_ref == REQUESTER and item.subject_ref == PROVIDER)
    assert reading.value == -2
    assert breach in reading.evidence_event_ids and len(reading.evidence_event_ids) == 2
    assert not any(item.observer_ref == PROVIDER for item in view.aid_readings), "directions need their own evidence"


def test_previous_save_schema_is_rejected_without_migration(tmp_path):
    world, _ = _breached_aid_world()
    path = tmp_path / "old.mws"
    save_world(world, path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET schema_version=26")
    saved = path.read_bytes()
    with pytest.raises(ValueError, match="Unsupported"):
        load_world(path)
    assert path.read_bytes() == saved


@pytest.mark.parametrize("tamper", ["missing_notice", "foreign_institution", "unknown_event", "future_day"])
def test_a_memory_without_its_notice_or_fact_is_rejected(tamper):
    world, obligation_id = _breached_aid_world()
    breach = breach_event_id(world, obligation_id)
    memory = memories_of(world, REQUESTER, breach)
    if tamper == "missing_notice":
        for key, notice in list(world.knowledge.notices.items()):
            if notice.event_id == breach and notice.recipient_ref == REQUESTER:
                del world.knowledge.notices[key]
    elif tamper == "foreign_institution":
        stranger = next(EntityRef("polity", key) for key in sorted(world.society.polities)
                        if key not in {REQUESTER.id, PROVIDER.id})
        forged = memory.model_copy(update={"id": institutional_memory_id(stranger, breach),
                                           "institution_ref": stranger})
        world.relations.memories[forged.id] = forged
    elif tamper == "unknown_event":
        forged_id = f"event:{len(world.events) + 50}"
        world.relations.memories[institutional_memory_id(REQUESTER, forged_id)] = memory.model_copy(
            update={"id": institutional_memory_id(REQUESTER, forged_id), "event_id": forged_id})
    else:
        world.relations.memories[memory.id] = memory.model_copy(
            update={"last_reinforced_day": world.clock.absolute_day + 5})
    with pytest.raises(ValueError, match="memory"):
        world_snapshot(world)

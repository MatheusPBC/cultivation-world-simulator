"""Actor-perspective projection never leaks foreign canonical state."""

import pytest

from src.classes.mechanical_language import EntityRef
from src.classes.governance.models import DiplomaticNotice
from src.run.medieval_world import create_medieval_world
from src.server.medieval.errors import RuntimeProblem
from src.server.medieval.queries import actor_dossier
from src.sim.medieval.events import record_event
from src.classes.event import FactKind


def test_dossier_contains_only_recipient_knowledge_and_own_strategy():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    other = EntityRef("polity", "valedouro")
    record_event(world, "private_notice", "Aviso para Auren.", fact_kind=FactKind.OCCURRENCE)
    world.knowledge.notices["notice:test"] = DiplomaticNotice(
        id="notice:test", proposal_id="proposal:test", recipient_ref=actor,
        event_id=world.events[-1].id, learned_day=world.clock.absolute_day)
    world.knowledge.notices["notice:foreign"] = world.knowledge.notices["notice:test"].model_copy(
        update={"id": "notice:foreign", "recipient_ref": other})

    dossier = actor_dossier(world, actor.kind, actor.id)
    assert dossier.actor_ref == actor
    assert ("notices", "notice:test") in {(item.category, item.id) for item in dossier.entries}
    notices = [item for item in dossier.entries if item.category == "notices"]
    assert [item.id for item in notices] == ["notice:test"]
    assert all(item.payload.get("recipient_ref") == actor.to_dict() for item in notices)
    assert any(item.category == "known_fact" and item.event_id == world.events[-1].id
               for item in dossier.entries)
    assert all(item.category in {"notices", "known_fact", "strategic_objective", "strategic_plan", "authority_office"}
               for item in dossier.entries)


def test_own_activity_and_office_do_not_grant_institutional_plans_or_future_authority():
    from src.sim.medieval.actions import start_practice
    world = create_medieval_world(73)
    office = next(o for o in world.authority.offices.values() if o.holder_ref.kind == "character")
    actor = office.holder_ref
    office = office.model_copy(update={"ends_day": world.clock.absolute_day})
    world.authority.offices[office.id] = office
    activity = start_practice(world, actor.id, "combat")
    before = len(world.events)
    dossier = actor_dossier(world, actor.kind, actor.id, limit=100)
    role = next(e for e in dossier.entries if e.category == "authority_office" and e.id == office.id)
    assert role.payload["active"] is False and role.event_id is None and role.learned_day is None
    assert role.payload["scopes"] == list(office.scopes)
    own_work = next(e for e in dossier.entries if e.category == "current_activity")
    assert own_work.event_id == activity.decision_event_id and own_work.payload["skill"] == "combat"
    assert not any(e.category in {"strategic_objective", "strategic_plan"} for e in dossier.entries)
    assert len(world.events) == before and world.activities[activity.id] == activity
    stranger = next(c.id for c in world.society.characters.values() if c.id != actor.id)
    other = actor_dossier(world, "character", stranger, limit=100)
    assert not any(e.id in {office.id, activity.id} for e in other.entries)
    institution = actor_dossier(world, office.institution_ref.kind, office.institution_ref.id, limit=100)
    assert any(e.category == "authority_office" and e.id == office.id for e in institution.entries)
    assert not any(e.category == "current_activity" and e.id == activity.id for e in institution.entries)


def test_dossier_rejects_unknown_actor():
    world = create_medieval_world(73)
    with pytest.raises(RuntimeProblem, match="Ator não encontrado"):
        actor_dossier(world, "polity", "missing")


def test_commander_dossier_shows_own_appointment_without_private_institutional_plan():
    from tests.test_medieval_force_command import _commanded_world
    world, column_id, person_id, command = _commanded_world()
    dossier = actor_dossier(world, "character", person_id, limit=100)
    own = next(e for e in dossier.entries if e.category == "field_command")
    assert own.id == column_id and own.event_id == command.last_event_id
    assert own.payload["character_id"] == person_id
    assert not any(e.category in {"strategic_plan", "strategic_objective"} for e in dossier.entries)
    assert any(e.event_id == command.last_event_id and e.category == "known_fact" for e in dossier.entries)
    stranger = next(c.id for c in world.society.characters.values() if c.id != person_id)
    assert not any(e.category == "field_command" for e in actor_dossier(world, "character", stranger).entries)


def test_real_adherence_dossier_keeps_own_choice_date_and_receipt_without_foreign_thoughts():
    from tests.test_medieval_religion import prepared, join, ORDER
    from src.server.medieval.queries import causal_view
    world, actor = prepared()
    adherence = join(world, actor, ORDER)
    dossier = actor_dossier(world, actor.kind, actor.id)
    own = next(e for e in dossier.entries if e.category == "religious_adherence")
    assert own.payload["organization_id"] == ORDER.id and own.learned_day == adherence.joined_day
    receipt = world.event_index()[adherence.last_event_id]
    choice_id = receipt.causal_payload["decision_event_id"]
    choice = next(e for e in dossier.entries if e.event_id == choice_id and e.category == "known_fact")
    assert choice.payload["decision"] == world.event_index()[choice_id].decision
    assert choice.payload["decision"]["action"] == "accept_religious_adherence"
    assert choice.payload["decision"]["selected_affordance_id"].startswith("religious-join:")
    invitation = world.knowledge.religious_invitation_notices[adherence.invitation_id]
    why = causal_view(world, adherence.last_event_id)
    assert {choice_id, invitation.event_id} <= {e.id for e in why.causes}
    publisher_choice = world.event_index()[invitation.event_id].causal_payload["decision_event_id"]
    assert not any(e.event_id == publisher_choice for e in dossier.entries)
    stranger = next(c.id for c in world.society.characters.values() if c.id != actor.id)
    private = actor_dossier(world, "character", stranger)
    assert not any(e.event_id in {adherence.last_event_id, invitation.event_id, choice_id} for e in private.entries)


def test_ritual_participation_tracks_real_work_and_result_without_foreign_stock_or_account():
    from tests.test_medieval_rites import ailing_world, started, tick_to, SPONSOR
    from src.server.medieval.queries import causal_view
    world, healer = ailing_world()
    _, rite = started(world, healer)
    pending = actor_dossier(world, "character", healer.id)
    activity = next(e for e in pending.entries if e.category == "ritual_activity")
    assert activity.payload["stage"] == "officiating" and activity.payload["role"] == "officiant"
    assert activity.payload["planned_cost"] == world.research.rite_blueprints[rite.blueprint_id].cost
    assert "stock_id" not in activity.payload and "account_id" not in activity.payload
    tick_to(world, rite.due_day)
    completed = world.research.rites[rite.id]
    dossier = actor_dossier(world, "character", healer.id)
    activity = next(e for e in dossier.entries if e.category == "ritual_activity")
    assert activity.payload["stage"] == "completed" and activity.event_id == completed.last_event_id
    receipt = next(e for e in dossier.entries if e.category == "known_fact" and e.event_id == completed.last_event_id)
    assert receipt.payload["deltas"]
    assert all(d["owner_kind"] not in {"stock", "account", "money_account"} for d in receipt.payload["deltas"])
    assert not any(e.event_id == rite.sponsor_decision_id for e in dossier.entries)
    sponsor = actor_dossier(world, SPONSOR.kind, SPONSOR.id)
    contract = next(e for e in sponsor.entries if e.category == "ritual_activity")
    assert contract.payload["stock_id"] == rite.stock_id and contract.payload["role"] == "sponsor"
    sponsor_receipt = next(e for e in sponsor.entries if e.category == "known_fact" and e.event_id == completed.last_event_id)
    assert any(d["owner_kind"] == "stock" for d in sponsor_receipt.payload["deltas"])
    why = causal_view(world, activity.event_id)
    assert any(d.owner_kind == "stock" for d in why.event.deltas), "Dao retains complete material evidence"
    stranger = next(c.id for c in world.society.characters.values() if c.id != healer.id)
    assert not any(e.category == "ritual_activity" for e in actor_dossier(world, "character", stranger).entries)


def test_dossier_exposes_only_known_causal_links():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    own = record_event(world, "own_decision", "Auren decidiu.", fact_kind=FactKind.DECISION,
                       decision={"action": "observe", "actor_ref": actor.to_dict()})
    hidden = record_event(world, "foreign_fact", "Fato estrangeiro.", fact_kind=FactKind.OCCURRENCE)
    visible = record_event(world, "visible_fact", "Fato recebido.", fact_kind=FactKind.OCCURRENCE,
                           cause_ids=(own.id, hidden.id))
    world.knowledge.notices["notice:causal"] = DiplomaticNotice(
        id="notice:causal", proposal_id="proposal:causal", recipient_ref=actor,
        event_id=visible.id, learned_day=world.clock.absolute_day)

    dossier = actor_dossier(world, actor.kind, actor.id)
    visible_entry = next(item for item in dossier.entries if item.id == f"fact:{visible.id}")
    assert visible_entry.cause_event_ids == [own.id]
    assert visible_entry.causal_depth == 1
    assert hidden.id not in visible_entry.cause_event_ids
    assert any(item.id == f"fact:{own.id}" for item in dossier.entries)


def test_dossier_reports_known_multi_hop_depth_without_leaking_unknown_causes():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    first = record_event(world, "known_first", "Primeiro fato conhecido.", fact_kind=FactKind.DECISION,
                         decision={"action": "observe", "actor_ref": actor.to_dict()})
    second = record_event(world, "known_second", "Segundo fato conhecido.", fact_kind=FactKind.OCCURRENCE,
                          cause_ids=(first.id,))
    third = record_event(world, "known_third", "Terceiro fato conhecido.", fact_kind=FactKind.OCCURRENCE,
                         cause_ids=(second.id,))
    world.knowledge.notices["notice:multi-hop-second"] = DiplomaticNotice(
        id="notice:multi-hop-second", proposal_id="proposal:multi-hop-second", recipient_ref=actor,
        event_id=second.id, learned_day=world.clock.absolute_day)
    world.knowledge.notices["notice:multi-hop"] = DiplomaticNotice(
        id="notice:multi-hop", proposal_id="proposal:multi-hop", recipient_ref=actor,
        event_id=third.id, learned_day=world.clock.absolute_day)

    dossier = actor_dossier(world, actor.kind, actor.id)
    entry = next(item for item in dossier.entries if item.id == f"fact:{third.id}")
    assert entry.causal_depth == 2
    assert entry.cause_event_ids == [second.id]


def test_dossier_pages_known_history_without_losing_or_leaking_entries():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    events = [record_event(
        world, f"known_decision_{index}", f"Decisão conhecida {index}.",
        fact_kind=FactKind.DECISION,
        decision={"action": "observe", "actor_ref": actor.to_dict()},
    ) for index in range(3)]
    foreign = record_event(world, "foreign_fact", "Fato de outra instituição.", fact_kind=FactKind.OCCURRENCE)

    full = actor_dossier(world, actor.kind, actor.id, limit=100)
    first = actor_dossier(world, actor.kind, actor.id, limit=2)
    new = record_event(
        world, "newer_decision", "Uma decisão posterior.", fact_kind=FactKind.DECISION,
        decision={"action": "observe", "actor_ref": actor.to_dict()},
    )
    pages = list(first.entries)
    next_after = first.next_after
    while next_after:
        page = actor_dossier(world, actor.kind, actor.id, after=next_after, limit=2)
        pages.extend(page.entries)
        next_after = page.next_after
    visible_ids = {item.event_id for item in pages if item.category == "known_fact"}

    assert len(first.entries) == 2
    assert first.has_more is True and first.next_after
    assert pages == full.entries
    assert visible_ids == {event.id for event in events}
    assert all(item.event_id != new.id for item in pages)
    assert all(item.event_id != foreign.id for item in pages)
    with pytest.raises(RuntimeProblem, match="Cursor de dossiê inválido"):
        actor_dossier(world, actor.kind, actor.id, after="invalid")

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
    assert all(item.category in {"notices", "known_fact", "strategic_objective", "strategic_plan"}
               for item in dossier.entries)


def test_dossier_rejects_unknown_actor():
    world = create_medieval_world(73)
    with pytest.raises(RuntimeProblem, match="Ator não encontrado"):
        actor_dossier(world, "polity", "missing")


def test_dossier_exposes_only_known_causal_links():
    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    foreign = EntityRef("polity", "valedouro")
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

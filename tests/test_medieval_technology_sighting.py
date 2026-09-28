"""A technical sighting is evidence for a bargain, never technical knowledge."""

from dataclasses import replace

import pytest

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.systems.time import WorldClock
from tests.test_medieval_research import authorize, prepared, work


HOLDER = EntityRef("polity", "escarlia")
RECIPIENT = EntityRef("polity", "auren")


def world_with_metallurgy():
    world = prepared()
    authorize(world)
    for day in (30, 60, 90):
        work(world, day)
    return world


def disclose(world):
    from src.sim.medieval.technology_sighting import disclosure_options, execute_disclosure

    option = next(item for item in disclosure_options(world, HOLDER)
                  if item.recipient_ref == RECIPIENT and item.technology_id == "metallurgy")
    decision = record_event(world, "technical_disclosure_decided", "Divulgar técnica própria a um destinatário alcançável.",
                            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                            causal_payload={"decision_source": {"kind": "api"}},
                            decision=option.decision(), cause_ids=option.causes())
    return execute_disclosure(world, option, decision.id)


def test_sighting_gates_requested_teaching_and_rejection_changes_no_material_owner(tmp_path):
    from src.classes.governance.diplomacy import PaymentClause, TeachingClause, offer_intent
    from src.sim.medieval.diplomacy import offer_proposal, respond_proposal
    from src.sim.medieval.diplomacy_policy import teaching_request_options, _execute_offer

    world = world_with_metallurgy()
    terms = (
        PaymentClause(debtor_ref=RECIPIENT, creditor_ref=HOLDER, due_day=110,
                      source_account_id="treasury:auren", target_account_id="treasury:escarlia", amount=100),
        TeachingClause(debtor_ref=HOLDER, creditor_ref=RECIPIENT, due_day=115,
                       depends_on=(0,), technology_id="metallurgy"),
    )
    denied = record_event(world, "diplomatic_decision", "Pedir técnica sem evidência.",
                          fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                          causal_payload={"decision_source": {"kind": "api"}},
                          decision=offer_intent(RECIPIENT, HOLDER, terms, 105, None))
    with pytest.raises(ValueError, match="technology sighting"):
        offer_proposal(world, RECIPIENT, HOLDER, terms, 105, decision_event_id=denied.id)
    assert not teaching_request_options(world, RECIPIENT)

    sighting = disclose(world)
    assert sighting.holder_ref == HOLDER and sighting.recipient_ref == RECIPIENT
    assert not world.knowledge.knows(RECIPIENT, "metallurgy")
    option = next(item for item in teaching_request_options(world, RECIPIENT)
                  if item.technology_id == "metallurgy")
    request = record_event(world, "diplomatic_decision", "Pedir ensino por indício técnico atual.",
                           fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                           causal_payload={"decision_source": {"kind": "api"}},
                           decision=option.decision(), cause_ids=option.causes())
    assert _execute_offer(world, option, request.id)
    proposal = world.relations.proposals[f"proposal:{request.id}"]
    before = (world.economy.to_dict(), world.authority.to_dict(),
              dict(world.knowledge.technologies), dict(world.knowledge.technology_sightings))
    rejection = record_event(world, "diplomatic_decision", "Recusar proposta de ensino.", fact_kind=FactKind.DECISION,
                             causal_origin=CausalOrigin.ACTOR_DECISION,
                             causal_payload={"decision_source": {"kind": "api"}},
                             decision={"action": "respond_proposal", "actor_ref": HOLDER.to_dict(),
                                       "proposal_id": proposal.id, "response": "reject"}, cause_ids=(proposal.last_event_id,))
    respond_proposal(world, proposal.id, "reject", decision_event_id=rejection.id)
    assert world.relations.proposals[proposal.id].status == "rejected"
    assert (world.economy.to_dict(), world.authority.to_dict(),
            dict(world.knowledge.technologies), dict(world.knowledge.technology_sightings)) == before
    save_world(world, tmp_path / "sighting.mws")
    assert world_snapshot(load_world(tmp_path / "sighting.mws")) == world_snapshot(world)


def test_disclosure_is_private_expiring_evidence_and_invalid_selection_teaches_nothing():
    from src.sim.medieval.diplomacy_policy import teaching_request_options
    from src.sim.medieval.technology_sighting import disclosure_options, execute_disclosure

    world = world_with_metallurgy()
    # The fixture gives a single reachable, currently mandated recipient.  It
    # makes the channel boundary visible without inventing a broadcast rule.
    world.authority.offices = {key: office for key, office in world.authority.offices.items()
                               if office.institution_ref in {HOLDER, RECIPIENT}}
    options = disclosure_options(world, HOLDER)
    assert options and {item.recipient_ref for item in options} == {RECIPIENT}
    forged = record_event(world, "technical_disclosure_interpreted", "Payload sem escolha do titular.",
                          fact_kind=FactKind.DECISION, decision=options[0].decision(),
                          cause_ids=options[0].causes())
    before_forged = world_snapshot(world)
    with pytest.raises(ValueError, match="exact current decision"):
        execute_disclosure(world, options[0], forged.id)
    assert world_snapshot(world) == before_forged

    before = world_snapshot(world)
    invalid = replace(options[0], id="technology-disclosure:invented")
    with pytest.raises(ValueError, match="absent or stale"):
        execute_disclosure(world, invalid, "event:missing")
    # NO_ACTION is represented by not executing an option; it has no owner
    # mutation. An invented ID likewise cannot enter the executor.
    assert world_snapshot(world) == before

    sighting = disclose(world)
    assert list(world.knowledge.technology_sightings) == [sighting.id]
    assert not world.knowledge.knows(RECIPIENT, "metallurgy")
    assert teaching_request_options(world, RECIPIENT)
    world.clock = WorldClock(sighting.expires_day)
    assert sighting.id in world.knowledge.technology_sightings
    assert not teaching_request_options(world, RECIPIENT)
    assert not world.knowledge.knows(RECIPIENT, "metallurgy")


def test_disclosure_failure_after_receipt_does_not_publish_partial_knowledge(monkeypatch):
    import src.sim.medieval.technology_sighting as sightings

    world = world_with_metallurgy()
    option = next(item for item in sightings.disclosure_options(world, HOLDER)
                  if item.recipient_ref == RECIPIENT and item.technology_id == "metallurgy")
    decision = record_event(world, "technical_disclosure_decided", "Divulgar técnica própria.",
                            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                            causal_payload={"decision_source": {"kind": "api"}},
                            decision=option.decision(), cause_ids=option.causes())
    before = world_snapshot(world)
    record = sightings.record_event

    def fail_after_receipt(*args, **kwargs):
        record(*args, **kwargs)
        raise RuntimeError("injected failure after sighting receipt")

    monkeypatch.setattr(sightings, "record_event", fail_after_receipt)
    with pytest.raises(RuntimeError, match="after sighting receipt"):
        sightings.execute_disclosure(world, option, decision.id)
    assert world_snapshot(world) == before
    assert not world.knowledge.technology_sightings

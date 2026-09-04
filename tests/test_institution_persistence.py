import json

from src.classes.institution import (
    AuthorityClaim,
    AuthorityClaimStatus,
    AuthorityScope,
    CommitmentTerm,
    CommitmentTermKind,
    CommitmentTermStatus,
    Institution,
    InstitutionalCommitment,
    InstitutionalFactKnowledge,
    InstitutionalMemory,
    InstitutionalOffice,
    InstitutionKind,
    KnowledgeChannel,
    RecognitionRecord,
    RecognitionStance,
)
from src.classes.mechanical_language import EntityRef
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import Event
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator


def test_save_load_preserves_cross_linked_institutional_state(base_world, tmp_path, monkeypatch):
    authority = base_world.institutional_authority
    dynasty = Institution(
        kind=InstitutionKind.DYNASTY,
        owner_ref=EntityRef("dynasty", "wei"),
        founded_month=0,
    )
    sect = Institution(
        kind=InstitutionKind.SECT,
        owner_ref=EntityRef("sect", "aurora"),
        founded_month=0,
    )
    authority.add_institution(dynasty)
    authority.add_institution(sect)
    office = InstitutionalOffice(
        institution_id=dynasty.id,
        office_key="sovereign",
        scopes=(AuthorityScope.RECOGNITION, AuthorityScope.COMMITMENT_NEGOTIATION),
    )
    authority.add_office(office)
    claim = AuthorityClaim(
        office_id=office.id,
        claimant_ref=EntityRef("avatar", "claimant"),
        opened_month=1,
        status=AuthorityClaimStatus.ACTIVE,
        evidence_event_ids=("event:claim",),
        source_kind="imperial_crisis",
    )
    authority.add_claim(claim)

    knowledge = base_world.institutional_knowledge
    fact = InstitutionalFactKnowledge(
        institution_id=dynasty.id,
        event_id="event:promise",
        learned_month=1,
        channel=KnowledgeChannel.OWN_ACTION,
        learned_from_event_id="event:promise",
    )
    knowledge.record(fact, authority)

    term = CommitmentTerm(
        id="term:grain-aid",
        index=0,
        kind=CommitmentTermKind.RESOURCE_TRANSFER,
        obligor_institution_id=sect.id,
        beneficiary_institution_id=dynasty.id,
        subject=EntityRef("resource", "grain"),
        status=CommitmentTermStatus.REMEDIATED,
        proposed_month=1,
        due_month=3,
        breached_month=4,
        resolved_month=5,
        parameters=(("amount", 50),),
        evidence_event_ids=("event:promise", "event:remediation"),
        breach_event_ids=("event:breach",),
    )
    commitment = InstitutionalCommitment(
        party_ids=(dynasty.id, sect.id),
        opened_month=1,
        terms=(term,),
        origin_event_id="event:promise",
        closed_month=5,
    )
    memory = InstitutionalMemory(
        institution_id=dynasty.id,
        event_id=fact.event_id,
        salience=0.7,
        recorded_month=1,
        last_reinforced_month=1,
        factors=(("relative_scale", 0.4),),
    )
    recognition = RecognitionRecord(
        recognizer_institution_id=sect.id,
        claim_id=claim.id,
        stance=RecognitionStance.RECOGNIZE,
        since_month=1,
        evidence_event_ids=("event:recognition",),
    )
    relations = base_world.institutional_relations
    relations.add_commitment(commitment, authority)
    relations.add_memory(memory, knowledge, authority)
    relations.add_recognition(recognition, authority)

    claim_event = Event(base_world.month_stamp, "claim", id="event:claim")
    promise_event = Event(
        base_world.month_stamp,
        "promise",
        id="event:promise",
        causal_links=[
            CausalLink(cause_event_id=claim_event.id, relation=CausalRelation.RESPONSE_TO)
        ],
    )
    breach_event = Event(
        base_world.month_stamp,
        "breach",
        id="event:breach",
        causal_links=[
            CausalLink(cause_event_id=promise_event.id, relation=CausalRelation.TRIGGERED_BY)
        ],
    )
    remediation_event = Event(
        base_world.month_stamp,
        "remediation",
        id="event:remediation",
        causal_links=[
            CausalLink(cause_event_id=breach_event.id, relation=CausalRelation.RESOLVES)
        ],
    )
    recognition_event = Event(base_world.month_stamp, "recognition", id="event:recognition")
    for event in (claim_event, promise_event, breach_event, remediation_event, recognition_event):
        assert base_world.event_manager.add_event(event)
    assert base_world.event_manager.cleanup(keep_major=False) == 0

    expected = (
        authority.to_dict(),
        knowledge.to_dict(),
        relations.to_dict(),
    )
    save_path = tmp_path / "institutional-state.json"
    ok, _ = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    assert ok
    save_data = json.loads(save_path.read_text(encoding="utf-8"))
    assert "events" not in save_data
    sidecar = save_path.parent / save_data["meta"]["events_db"]
    assert sidecar.is_file()
    assert sidecar.name != "institutional-state_events.db"

    loaded_world, _, _ = load_game(save_path)
    assert (
        loaded_world.institutional_authority.to_dict(),
        loaded_world.institutional_knowledge.to_dict(),
        loaded_world.institutional_relations.to_dict(),
    ) == expected
    loaded_remediated = next(iter(loaded_world.institutional_relations.commitments.values()))
    assert loaded_remediated.terms[0].breach_event_ids == ("event:breach",)
    loaded_remediation = loaded_world.event_manager.get_event_by_id("event:remediation")
    assert loaded_remediation is not None
    assert {
        link.cause_event_id
        for link in loaded_world.event_manager.get_causal_links_for_event(
            loaded_remediation.id
        )
    } == {"event:breach"}

    import src.sim.save.save_game as save_module

    real_replace = save_module.os.replace

    def fail_json_publication(source, destination):
        if destination == save_path:
            raise OSError("simulated JSON publication failure")
        return real_replace(source, destination)

    monkeypatch.setattr(save_module.os, "replace", fail_json_publication)
    failed, _ = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    assert failed is False
    reloaded_world, _, _ = load_game(save_path)
    assert reloaded_world.event_manager.get_event_by_id("event:remediation") is not None
import json

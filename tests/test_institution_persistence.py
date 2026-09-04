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
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator


def test_save_load_preserves_cross_linked_institutional_state(base_world, tmp_path):
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
        status=CommitmentTermStatus.ACTIVE,
        proposed_month=1,
        due_month=3,
        parameters=(("amount", 50),),
        evidence_event_ids=("event:promise",),
    )
    commitment = InstitutionalCommitment(
        party_ids=(dynasty.id, sect.id),
        opened_month=1,
        terms=(term,),
        origin_event_id="event:promise",
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

    expected = (
        authority.to_dict(),
        knowledge.to_dict(),
        relations.to_dict(),
    )
    save_path = tmp_path / "institutional-state.json"
    ok, _ = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    assert ok

    loaded_world, _, _ = load_game(save_path)
    assert (
        loaded_world.institutional_authority.to_dict(),
        loaded_world.institutional_knowledge.to_dict(),
        loaded_world.institutional_relations.to_dict(),
    ) == expected

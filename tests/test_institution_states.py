from dataclasses import replace

import pytest

from src.classes.institution import (
    AuthorityClaim,
    AuthorityClaimStatus,
    AuthorityScope,
    CommitmentTerm,
    CommitmentTermKind,
    CommitmentTermStatus,
    IdentityAnchorKind,
    Institution,
    InstitutionKind,
    InstitutionalCommitment,
    InstitutionalFactKnowledge,
    InstitutionalIdentityAnchor,
    InstitutionalMemory,
    InstitutionalOffice,
    InstitutionalRelation,
    InstitutionalRelationKind,
    KnowledgeChannel,
    RecognitionRecord,
    RecognitionStance,
    InstitutionalAuthorityState,
    InstitutionalKnowledgeState,
    InstitutionalRelationsState,
)
from src.classes.mechanical_language import EntityRef


def ref(kind: str, entity_id: str) -> EntityRef:
    return EntityRef(kind, entity_id)


def institution(kind: str, entity_id: str) -> Institution:
    owner_kind = "region" if kind == "city" else kind
    return Institution(
        kind=InstitutionKind(kind),
        owner_ref=ref(owner_kind, entity_id),
        founded_month=1,
    )


def authority_fixture() -> tuple[
    InstitutionalAuthorityState, Institution, InstitutionalOffice, AuthorityClaim
]:
    state = InstitutionalAuthorityState()
    city = institution("city", "101")
    state.add_institution(city)
    office = InstitutionalOffice(
        institution_id=city.id,
        office_key="governor",
        scopes=(AuthorityScope.RECOGNITION, AuthorityScope.URBAN_ADMINISTRATION),
    )
    state.add_office(office)
    claim = AuthorityClaim(
        office_id=office.id,
        claimant_ref=ref("avatar", "avatar-1"),
        opened_month=2,
        status=AuthorityClaimStatus.ACTIVE,
        evidence_event_ids=("event:claim",),
        source_kind="test",
    )
    state.add_claim(claim)
    return state, city, office, claim


def test_state_shapes_are_exact_and_schema_is_strict():
    assert set(InstitutionalAuthorityState().to_dict()) == {
        "model_version",
        "institutions",
        "offices",
        "claims",
        "identity_anchors",
    }
    assert set(InstitutionalRelationsState().to_dict()) == {
        "model_version",
        "relations",
        "commitments",
        "memories",
        "recognitions",
    }
    assert set(InstitutionalKnowledgeState().to_dict()) == {
        "model_version",
        "known_facts",
    }
    with pytest.raises(ValueError):
        InstitutionalAuthorityState.from_dict(
            {**InstitutionalAuthorityState().to_dict(), "obsolete": {}}
        )
    with pytest.raises(ValueError):
        InstitutionalKnowledgeState.from_dict(
            {"model_version": 2, "known_facts": {}}, InstitutionalAuthorityState()
        )


def test_authority_state_rejects_corrupt_refs_and_duplicate_scope_offices():
    state, city, office, claim = authority_fixture()
    # Multiple active claimants are valid; only office scopes are exclusive.
    state.add_claim(replace(claim, claimant_ref=ref("avatar", "avatar-2"), id=""))
    assert len(state.claims) == 2
    assert state.get_institution_for_owner(city.owner_ref) == city
    assert state.office_for_scope(city.id, AuthorityScope.RECOGNITION) == office
    assert len(state.active_claims(office.id)) == 2
    defeated = replace(
        claim,
        status=AuthorityClaimStatus.DEFEATED,
        closed_month=3,
        closed_event_id="event:defeat",
    )
    state.replace_claim(defeated)
    with pytest.raises(ValueError, match="invalid authority claim transition"):
        state.replace_claim(claim)
    with pytest.raises(ValueError, match="one office per authority scope"):
        state.add_office(
            InstitutionalOffice(
                institution_id=city.id,
                office_key="deputy",
                scopes=(AuthorityScope.RECOGNITION,),
            )
        )
    bad = state.to_dict()
    bad_claim = bad["claims"].pop(claim.id)
    bad_claim["office_id"] = "office:missing"
    bad_claim["id"] = "claim:office:missing:avatar-1:2"
    bad["claims"][bad_claim["id"]] = bad_claim
    with pytest.raises(ValueError, match="unknown office"):
        InstitutionalAuthorityState.from_dict(bad)
    bad = state.to_dict()
    anchor = InstitutionalIdentityAnchor(
        institution_id=city.id,
        kind=IdentityAnchorKind.HEADQUARTERS,
        subject=ref("region", "101"),
        established_month=1,
        evidence_event_ids=("event:founding",),
    )
    bad_anchor = {**anchor.to_dict(), "institution_id": "inst:missing"}
    bad_anchor["id"] = "anchor:inst:missing:headquarters:region:101"
    bad["identity_anchors"][bad_anchor["id"]] = bad_anchor
    with pytest.raises(ValueError, match="unknown institution"):
        InstitutionalAuthorityState.from_dict(bad)


def test_knowledge_is_idempotent_and_memory_requires_known_fact():
    authority, _, _, _ = authority_fixture()
    knowledge = InstitutionalKnowledgeState()
    first = InstitutionalFactKnowledge(
        institution_id="inst:city:101",
        event_id="event:aid",
        learned_month=2,
        channel=KnowledgeChannel.PUBLIC_FACT,
        learned_from_event_id="event:knowledge-aid",
    )
    later = InstitutionalFactKnowledge(
        institution_id="inst:city:101",
        event_id="event:aid",
        learned_month=9,
        channel=KnowledgeChannel.FORMAL_NOTICE,
        learned_from_event_id="event:knowledge-aid-later",
    )
    assert knowledge.record(first, authority) is first
    assert knowledge.record(later, authority) is first
    assert knowledge.known_facts[first.id].learned_month == 2
    assert (
        knowledge.known_facts[first.id].learned_from_event_id == "event:knowledge-aid"
    )
    memory = InstitutionalMemory(
        institution_id="inst:city:101",
        event_id="event:aid",
        salience=0.7,
        recorded_month=2,
        last_reinforced_month=2,
        factors=(),
    )
    relations = InstitutionalRelationsState()
    with pytest.raises(ValueError, match="requires known fact"):
        relations.add_memory(memory, InstitutionalKnowledgeState(), authority)
    relations.add_memory(memory, knowledge, authority)
    assert relations.memories[memory.id] == memory


def test_three_state_round_trip_validates_cross_state_references():
    authority, city, office, claim = authority_fixture()
    anchor = InstitutionalIdentityAnchor(
        institution_id=city.id,
        kind=IdentityAnchorKind.HEADQUARTERS,
        subject=ref("region", "101"),
        established_month=1,
        evidence_event_ids=("event:founding",),
    )
    authority.add_identity_anchor(anchor)
    sect = institution("sect", "7")
    authority.add_institution(sect)
    knowledge = InstitutionalKnowledgeState()
    fact = InstitutionalFactKnowledge(
        institution_id=city.id,
        event_id="event:aid",
        learned_month=3,
        channel=KnowledgeChannel.PUBLIC_FACT,
        learned_from_event_id="event:knowledge-aid",
    )
    knowledge.record(fact, authority)
    relation = InstitutionalRelation(
        institution_a_id=city.id,
        institution_b_id=sect.id,
        kind=InstitutionalRelationKind.ALLIED,
        friendliness=40,
        since_month=3,
        evidence_event_ids=("event:allied",),
    )
    term = CommitmentTerm(
        id="term:aid",
        index=0,
        kind=CommitmentTermKind.RESOURCE_TRANSFER,
        obligor_institution_id=sect.id,
        beneficiary_institution_id=city.id,
        subject=ref("resource", "grain"),
        status=CommitmentTermStatus.ACTIVE,
        proposed_month=3,
        parameters=(("amount", 5),),
        evidence_event_ids=("event:commitment",),
    )
    commitment = InstitutionalCommitment(
        party_ids=(city.id, sect.id),
        opened_month=3,
        terms=(term,),
        origin_event_id="event:commitment",
    )
    memory = InstitutionalMemory(
        institution_id=city.id,
        event_id=fact.event_id,
        salience=0.8,
        recorded_month=3,
        last_reinforced_month=3,
        factors=(("relative_scale", 0.5),),
    )
    recognition = RecognitionRecord(
        recognizer_institution_id=city.id,
        claim_id=claim.id,
        stance=RecognitionStance.RECOGNIZE,
        since_month=3,
        evidence_event_ids=("event:recognition",),
    )
    with pytest.raises(ValueError, match="unknown institution"):
        InstitutionalKnowledgeState().record(
            replace(fact, institution_id="inst:missing", id=""), authority
        )
    with pytest.raises(ValueError, match="unknown institution"):
        InstitutionalRelationsState().add_relation(
            replace(relation, institution_a_id="inst:missing", id=""), authority
        )
    with pytest.raises(ValueError, match="unknown institution"):
        InstitutionalRelationsState().add_commitment(
            replace(commitment, party_ids=(city.id, sect.id, "inst:missing")), authority
        )
    relations = InstitutionalRelationsState()
    relations.add_relation(relation, authority)
    relations.add_commitment(commitment, authority)
    relations.add_memory(memory, knowledge, authority)
    relations.add_recognition(recognition, authority)

    breached_term = replace(
        term,
        status=CommitmentTermStatus.BREACHED,
        breached_month=4,
        breach_event_ids=("event:breach",),
        evidence_event_ids=term.evidence_event_ids + ("event:breach",),
    )
    breached_commitment = replace(commitment, terms=(breached_term,))
    relations.replace_commitment(breached_commitment, authority)
    with pytest.raises(ValueError, match="invalid commitment term transition"):
        relations.replace_commitment(commitment, authority)

    assert relations.get_relation(sect.id, city.id) == relation
    assert relations.commitments_for(city.id) == (breached_commitment,)
    assert relations.memories_for(city.id) == (memory,)

    relations.replace_memory(replace(memory, salience=0.9), knowledge, authority)

    restored_authority = InstitutionalAuthorityState.from_dict(authority.to_dict())
    restored_knowledge = InstitutionalKnowledgeState.from_dict(
        knowledge.to_dict(), restored_authority
    )
    restored_relations = InstitutionalRelationsState.from_dict(
        relations.to_dict(), restored_authority, restored_knowledge
    )
    assert restored_authority == authority
    assert restored_knowledge == knowledge
    assert restored_relations == relations

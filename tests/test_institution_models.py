from dataclasses import FrozenInstanceError, replace

import pytest

from src.classes.institution.models import (
    AuthorityClaim,
    AuthorityClaimStatus,
    AuthorityScope,
    CommitmentAggregateStatus,
    CommitmentTerm,
    CommitmentTermKind,
    CommitmentTermStatus,
    IdentityAnchorKind,
    Institution,
    InstitutionalCommitment,
    InstitutionalFactKnowledge,
    InstitutionalIdentityAnchor,
    InstitutionalMemory,
    InstitutionalOffice,
    InstitutionalRelation,
    InstitutionalRelationKind,
    InstitutionKind,
    KnowledgeChannel,
    RecognitionRecord,
    RecognitionStance,
)
from src.classes.mechanical_language import EntityRef


def ref(kind: str, entity_id: str) -> EntityRef:
    return EntityRef(kind=kind, id=entity_id)


def make_institution(kind: InstitutionKind, entity_id: str) -> Institution:
    owner_kind = "region" if kind is InstitutionKind.CITY else kind.value
    return Institution(kind=kind, owner_ref=ref(owner_kind, entity_id), founded_month=3)


def make_term(
    *,
    index: int = 0,
    status: CommitmentTermStatus = CommitmentTermStatus.ACTIVE,
    breach_event_ids: tuple[str, ...] = (),
    remediation_of_term_id: str | None = None,
) -> CommitmentTerm:
    return CommitmentTerm(
        id=f"term:{index}",
        index=index,
        kind=CommitmentTermKind.RESOURCE_TRANSFER,
        obligor_institution_id="inst:dynasty:a",
        beneficiary_institution_id="inst:sect:b",
        subject=ref("resource", "grain"),
        status=status,
        proposed_month=4,
        due_month=8,
        breached_month=9
        if status
        in {
            CommitmentTermStatus.BREACHED,
            CommitmentTermStatus.REMEDIATION_PROPOSED,
            CommitmentTermStatus.REMEDIATED,
        }
        else None,
        resolved_month=10
        if status
        in {
            CommitmentTermStatus.FULFILLED,
            CommitmentTermStatus.REMEDIATED,
            CommitmentTermStatus.CANCELLED,
            CommitmentTermStatus.EXPIRED,
        }
        else None,
        parameters=(("amount", 5),),
        evidence_event_ids=("evt:proposal",),
        breach_event_ids=breach_event_ids,
        remediation_of_term_id=remediation_of_term_id,
    )


def test_frozen_lifecycle_enum_values_are_exact():
    assert {item.value for item in AuthorityClaimStatus} == {
        "active",
        "withdrawn",
        "defeated",
        "expired",
    }
    assert {item.value for item in CommitmentTermStatus} == {
        "proposed",
        "active",
        "fulfilled",
        "breached",
        "remediation_proposed",
        "remediated",
        "cancelled",
        "expired",
    }


def test_institution_and_office_have_canonical_ids_and_round_trip():
    institution = make_institution(InstitutionKind.CITY, "r-1")
    assert institution.id == "inst:city:r-1"
    assert institution.is_active(3)
    assert not replace(institution, dissolved_month=4).is_active(4)
    assert Institution.from_dict(institution.to_dict()) == institution
    with pytest.raises(ValueError, match="invalid Institution keys"):
        Institution.from_dict({**institution.to_dict(), "legacy_name": "discard me"})
    office = InstitutionalOffice(
        institution_id=institution.id,
        office_key="governor",
        scopes=(AuthorityScope.RECOGNITION, AuthorityScope.URBAN_ADMINISTRATION),
        holder_ref=ref("avatar", "av-1"),
        holder_since_month=4,
    )
    assert office.id == "office:inst:city:r-1:governor"
    assert office.scopes == (
        AuthorityScope.RECOGNITION,
        AuthorityScope.URBAN_ADMINISTRATION,
    )
    assert InstitutionalOffice.from_dict(office.to_dict()) == office
    with pytest.raises(ValueError):
        InstitutionalOffice(
            institution_id=office.institution_id,
            office_key="governor",
            scopes=(AuthorityScope.RECOGNITION, AuthorityScope.RECOGNITION),
        )
    with pytest.raises(ValueError):
        InstitutionalOffice(
            institution_id="inst:dynasty:a",
            office_key="governor",
            scopes=(AuthorityScope.RECOGNITION,),
            holder_ref=ref("avatar", "x"),
        )


def test_invalid_institution_refs_and_months_are_rejected():
    with pytest.raises(ValueError):
        Institution(
            kind=InstitutionKind.DYNASTY, owner_ref=ref("sect", "s"), founded_month=0
        )
    with pytest.raises(ValueError):
        Institution(
            kind=InstitutionKind.CITY, owner_ref=ref("city", "c"), founded_month=0
        )
    with pytest.raises(ValueError):
        Institution(
            kind=InstitutionKind.DYNASTY,
            owner_ref=ref("dynasty", "d"),
            founded_month=-1,
        )
    with pytest.raises(ValueError):
        Institution(
            kind=InstitutionKind.DYNASTY,
            owner_ref=ref("dynasty", "d"),
            founded_month=5,
            dissolved_month=4,
        )


def test_claim_lifecycle_relation_and_round_trip():
    claim = AuthorityClaim(
        office_id="office:inst:dynasty:a:emperor",
        claimant_ref=ref("avatar", "av-1"),
        opened_month=5,
        status=AuthorityClaimStatus.ACTIVE,
        evidence_event_ids=("evt:claim",),
        source_kind="imperial_crisis",
    )
    assert claim.id == "claim:office:inst:dynasty:a:emperor:av-1:5"
    assert AuthorityClaim.from_dict(claim.to_dict()) == claim
    with pytest.raises(ValueError):
        AuthorityClaim(
            office_id=claim.office_id,
            claimant_ref=claim.claimant_ref,
            opened_month=5,
            status=AuthorityClaimStatus.WITHDRAWN,
            evidence_event_ids=("evt:claim",),
            source_kind="imperial_crisis",
        )
    relation = InstitutionalRelation(
        institution_a_id="inst:dynasty:a",
        institution_b_id="inst:sect:b",
        kind=InstitutionalRelationKind.ALLIED,
        friendliness=100,
        since_month=2,
        evidence_event_ids=("evt:alliance",),
    )
    assert relation.id == "relation:inst:dynasty:a:inst:sect:b"
    assert InstitutionalRelation.from_dict(relation.to_dict()) == relation
    with pytest.raises(ValueError):
        InstitutionalRelation(
            institution_a_id="inst:sect:b",
            institution_b_id="inst:dynasty:a",
            kind=InstitutionalRelationKind.ALLIED,
            friendliness=0,
            since_month=2,
            evidence_event_ids=("evt:alliance",),
        )
    with pytest.raises(ValueError):
        InstitutionalRelation(
            institution_a_id="inst:dynasty:a",
            institution_b_id="inst:sect:b",
            kind=InstitutionalRelationKind.NEUTRAL,
            friendliness=101,
            since_month=2,
            evidence_event_ids=(),
        )


def test_term_parameters_are_sorted_immutable_and_breach_history_is_preserved():
    term = CommitmentTerm(
        id="term:0:urban",
        index=0,
        kind=CommitmentTermKind.URBAN_PROJECT,
        obligor_institution_id="inst:dynasty:a",
        beneficiary_institution_id="inst:sect:b",
        subject=ref("region", "r-1"),
        status=CommitmentTermStatus.BREACHED,
        proposed_month=1,
        due_month=2,
        breached_month=3,
        parameters=(("z", True), ("amount", 7)),
        evidence_event_ids=("evt:p",),
        breach_event_ids=("evt:b",),
    )
    assert term.id == "term:0:urban"
    assert term.parameters == (("amount", 7), ("z", True))
    with pytest.raises(FrozenInstanceError):
        term.status = CommitmentTermStatus.REMEDIATED
    assert CommitmentTerm.from_dict(term.to_dict()) == term
    with pytest.raises(ValueError):
        make_term(status=CommitmentTermStatus.BREACHED)
    remediated = make_term(
        status=CommitmentTermStatus.REMEDIATED,
        breach_event_ids=("evt:b",),
        remediation_of_term_id="term:0:old",
    )
    assert CommitmentTerm.from_dict(remediated.to_dict()) == remediated
    with pytest.raises(ValueError):
        CommitmentTerm(
            id="term:bad",
            index=0,
            kind=CommitmentTermKind.RESOURCE_TRANSFER,
            obligor_institution_id="inst:dynasty:a",
            beneficiary_institution_id="inst:sect:b",
            subject=ref("resource", "x"),
            status=CommitmentTermStatus.ACTIVE,
            proposed_month=1,
            parameters=(("amount", 1), ("bad", object())),
            evidence_event_ids=("evt",),
        )
    with pytest.raises(ValueError, match="positive amount"):
        CommitmentTerm(
            id="term:no-amount",
            index=0,
            kind=CommitmentTermKind.RESOURCE_TRANSFER,
            obligor_institution_id="inst:dynasty:a",
            beneficiary_institution_id="inst:sect:b",
            subject=ref("resource", "grain"),
            status=CommitmentTermStatus.ACTIVE,
            proposed_month=1,
            evidence_event_ids=("evt",),
        )
    with pytest.raises(ValueError, match="resolved_month"):
        CommitmentTerm(
            id="term:premature-resolution",
            index=0,
            kind=CommitmentTermKind.RESOURCE_TRANSFER,
            obligor_institution_id="inst:dynasty:a",
            beneficiary_institution_id="inst:sect:b",
            subject=ref("resource", "grain"),
            status=CommitmentTermStatus.ACTIVE,
            proposed_month=1,
            resolved_month=2,
            parameters=(("amount", 1),),
            evidence_event_ids=("evt",),
        )
    with pytest.raises(ValueError, match="present together"):
        CommitmentTerm(
            id="term:orphan-breach",
            index=0,
            kind=CommitmentTermKind.RESOURCE_TRANSFER,
            obligor_institution_id="inst:dynasty:a",
            beneficiary_institution_id="inst:sect:b",
            subject=ref("resource", "grain"),
            status=CommitmentTermStatus.EXPIRED,
            proposed_month=1,
            resolved_month=2,
            parameters=(("amount", 1),),
            evidence_event_ids=("evt",),
            breach_event_ids=("evt:breach",),
        )


def test_commitment_aggregate_precedence_and_closed_month_invariant():
    terms = (
        make_term(index=0, status=CommitmentTermStatus.FULFILLED),
        make_term(index=1, status=CommitmentTermStatus.ACTIVE),
    )
    commitment = InstitutionalCommitment(
        party_ids=("inst:sect:b", "inst:dynasty:a"),
        opened_month=1,
        terms=terms,
        origin_event_id="evt:commitment",
    )
    assert commitment.party_ids == ("inst:dynasty:a", "inst:sect:b")
    assert commitment.aggregate_status is CommitmentAggregateStatus.ACTIVE
    assert commitment.id == "commitment:evt:commitment"
    assert InstitutionalCommitment.from_dict(commitment.to_dict()) == commitment
    breached = InstitutionalCommitment(
        party_ids=commitment.party_ids,
        opened_month=1,
        terms=(
            make_term(
                index=0,
                status=CommitmentTermStatus.BREACHED,
                breach_event_ids=("evt:b",),
            ),
            make_term(
                index=1,
                status=CommitmentTermStatus.REMEDIATION_PROPOSED,
                breach_event_ids=("evt:b2",),
                remediation_of_term_id="term:0",
            ),
        ),
        origin_event_id="evt:breached",
    )
    assert breached.aggregate_status is CommitmentAggregateStatus.BREACHED
    closed = InstitutionalCommitment(
        party_ids=commitment.party_ids,
        opened_month=1,
        terms=(make_term(index=0, status=CommitmentTermStatus.FULFILLED),),
        origin_event_id="evt:closed",
        closed_month=10,
    )
    assert closed.aggregate_status is CommitmentAggregateStatus.FULFILLED
    with pytest.raises(ValueError):
        InstitutionalCommitment(
            party_ids=commitment.party_ids,
            opened_month=1,
            terms=terms,
            origin_event_id="evt:open",
            closed_month=10,
        )
    with pytest.raises(ValueError, match="term IDs must be unique"):
        InstitutionalCommitment(
            party_ids=commitment.party_ids,
            opened_month=1,
            terms=(make_term(index=0), replace(make_term(index=1), id="term:0")),
            origin_event_id="evt:duplicate-terms",
        )


def test_memory_anchor_recognition_knowledge_and_round_trip():
    memory = InstitutionalMemory(
        institution_id="inst:dynasty:a",
        event_id="evt:1",
        salience=0.5,
        recorded_month=2,
        last_reinforced_month=3,
        factors=(("commitment_breach", 1.0), ("relative_scale", 0.2)),
    )
    assert memory.factors == (("commitment_breach", 1.0), ("relative_scale", 0.2))
    assert InstitutionalMemory.from_dict(memory.to_dict()) == memory
    with pytest.raises(ValueError):
        InstitutionalMemory(
            institution_id="inst:dynasty:a",
            event_id="evt:1",
            salience=1.1,
            recorded_month=2,
            last_reinforced_month=3,
            factors=(),
        )
    anchor = InstitutionalIdentityAnchor(
        institution_id="inst:dynasty:a",
        kind=IdentityAnchorKind.FOUNDER,
        subject=ref("avatar", "av-1"),
        established_month=0,
        evidence_event_ids=("evt:founding",),
    )
    assert InstitutionalIdentityAnchor.from_dict(anchor.to_dict()) == anchor
    with pytest.raises(ValueError):
        InstitutionalIdentityAnchor(
            institution_id="inst:dynasty:a",
            kind=IdentityAnchorKind.FOUNDER,
            subject=ref("item", "wrong"),
            established_month=0,
            evidence_event_ids=("evt",),
        )
    recognition = RecognitionRecord(
        recognizer_institution_id="inst:sect:b",
        claim_id="claim:x",
        stance=RecognitionStance.REJECT,
        since_month=4,
        evidence_event_ids=("evt:r",),
    )
    assert recognition.id == "recognition:inst:sect:b:claim:x"
    assert RecognitionRecord.from_dict(recognition.to_dict()) == recognition
    knowledge = InstitutionalFactKnowledge(
        institution_id="inst:sect:b",
        event_id="evt:x",
        learned_month=4,
        channel=KnowledgeChannel.PUBLIC_FACT,
        learned_from_event_id="evt:announcement",
    )
    assert InstitutionalFactKnowledge.from_dict(knowledge.to_dict()) == knowledge

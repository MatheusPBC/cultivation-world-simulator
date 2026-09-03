import pytest

from src.classes.domain_proposal import (
    GovernmentDecision,
    GovernmentDecisionKind,
    GovernmentIntentKind,
    GovernmentUrbanIntentProposal,
    OrganizationDecision,
    OrganizationDecisionKind,
    OrganizationIntentKind,
    SectMemberSupportIntentProposal,
)


def test_government_intent_carries_ids_but_no_mechanical_amount():
    intent = GovernmentUrbanIntentProposal(
        action_kind=GovernmentIntentKind.URBAN_MAINTENANCE,
        subject_kind="dynasty",
        subject_id="7",
        region_id="301",
        capability_id="sanitation",
        motivation_event_ids=("condition-event",),
    )
    decision = GovernmentDecision(
        GovernmentDecisionKind.URBAN_MAINTENANCE,
        "The governed city has a grounded maintenance affordance.",
        intent,
    )

    serialized = decision.to_dict()
    assert serialized["action_intent"]["subject_id"] == "7"
    assert serialized["action_intent"]["region_id"] == "301"
    assert "amount" not in serialized["action_intent"]


def test_government_decision_rejects_mismatched_intent():
    intent = GovernmentUrbanIntentProposal(
        action_kind=GovernmentIntentKind.URBAN_CAPACITY_PROJECT,
        subject_kind="dynasty",
        subject_id="7",
        region_id="301",
        project_kind="settlement_capacity_expansion",
        motivation_event_ids=("condition-event",),
    )

    with pytest.raises(ValueError, match="must agree"):
        GovernmentDecision(
            GovernmentDecisionKind.URBAN_MAINTENANCE,
            "Mismatch",
            intent,
        )


def test_organization_support_intent_carries_member_but_no_transfer_amount():
    intent = SectMemberSupportIntentProposal(
        action_kind=OrganizationIntentKind.SUPPORT_MEMBER,
        subject_kind="sect",
        subject_id="3",
        member_id="avatar-9",
        region_id="301",
        motivation_event_ids=("condition-event",),
    )
    decision = OrganizationDecision(
        OrganizationDecisionKind.SUPPORT_MEMBER,
        "A member in the affected region is eligible for institutional support.",
        intent,
    )

    serialized = decision.to_dict()
    assert serialized["action_intent"]["member_id"] == "avatar-9"
    assert serialized["action_intent"]["subject_kind"] == "sect"
    assert "amount" not in serialized["action_intent"]


def test_no_action_cannot_smuggle_an_institutional_intent():
    intent = SectMemberSupportIntentProposal(
        action_kind=OrganizationIntentKind.SUPPORT_MEMBER,
        subject_kind="sect",
        subject_id="3",
        member_id="avatar-9",
        region_id="301",
        motivation_event_ids=("condition-event",),
    )

    with pytest.raises(ValueError, match="maintain"):
        OrganizationDecision(
            OrganizationDecisionKind.MAINTAIN,
            "No action",
            intent,
        )


@pytest.mark.parametrize("motivation_event_ids", [(), ("",), ("  ",)])
def test_institutional_intents_require_real_causal_event_ids(motivation_event_ids):
    with pytest.raises(ValueError, match="causal motivation"):
        SectMemberSupportIntentProposal(
            action_kind=OrganizationIntentKind.SUPPORT_MEMBER,
            subject_kind="sect",
            subject_id="3",
            member_id="avatar-9",
            region_id="301",
            motivation_event_ids=motivation_event_ids,
        )

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
import uuid


class PopulationDecisionKind(StrEnum):
    ACT = "act"
    MAINTAIN = "maintain"


class PopulationIntentKind(StrEnum):
    POPULATION_TRANSFER = "population_transfer"


class PopulationPreference(StrEnum):
    LOWER_SETTLEMENT_LOAD = "lower_settlement_load"
    AVAILABLE_CAPACITY = "available_capacity"


@dataclass(frozen=True, slots=True)
class PopulationTransferIntentProposal:
    action_kind: PopulationIntentKind
    subject_kind: str
    subject_id: str
    motivation_event_ids: tuple[str, ...]
    preferences: tuple[PopulationPreference, ...] = ()
    reason: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.subject_kind != "population" or not self.subject_id.startswith(
            "region:"
        ):
            raise ValueError(
                "population action intents require a region population subject"
            )
        if not self.motivation_event_ids:
            raise ValueError("action intents require causal motivation")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_type": "action_intent",
            "action_kind": self.action_kind.value,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "motivation_event_ids": list(self.motivation_event_ids),
            "preferences": [item.value for item in self.preferences],
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PopulationTransferIntentProposal":
        if data["proposal_type"] != "action_intent":
            raise ValueError("unsupported proposal type")
        return cls(
            id=str(data["id"]),
            action_kind=PopulationIntentKind(str(data["action_kind"])),
            subject_kind=str(data["subject_kind"]),
            subject_id=str(data["subject_id"]),
            motivation_event_ids=tuple(
                str(item) for item in data["motivation_event_ids"]
            ),
            preferences=tuple(
                PopulationPreference(str(item)) for item in data["preferences"]
            ),
            reason=str(data["reason"]),
        )


@dataclass(frozen=True, slots=True)
class PopulationDecision:
    decision: PopulationDecisionKind
    reason: str
    action_intent: PopulationTransferIntentProposal | None = None

    def __post_init__(self) -> None:
        if self.decision is PopulationDecisionKind.ACT and self.action_intent is None:
            raise ValueError("an acting population decision requires an action intent")
        if (
            self.decision is PopulationDecisionKind.MAINTAIN
            and self.action_intent is not None
        ):
            raise ValueError(
                "a maintain population decision cannot carry an action intent"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "action_intent": self.action_intent.to_dict()
            if self.action_intent is not None
            else None,
        }


class EconomyDecisionKind(StrEnum):
    ACT = "act"
    MAINTAIN = "maintain"


class EconomyIntentKind(StrEnum):
    RESOURCE_TRANSFER = "resource_transfer"


class EconomyPreference(StrEnum):
    AVAILABLE_SUPPLY = "available_supply"
    HIGHER_ROUTE_QUALITY = "higher_route_quality"


@dataclass(frozen=True, slots=True)
class ResourceTransferIntentProposal:
    action_kind: EconomyIntentKind
    subject_kind: str
    subject_id: str
    resource_id: str
    motivation_event_ids: tuple[str, ...]
    preferences: tuple[EconomyPreference, ...] = ()
    reason: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.action_kind is not EconomyIntentKind.RESOURCE_TRANSFER:
            raise ValueError("unsupported economy intent")
        if self.subject_kind != "region" or not self.subject_id.startswith("region:"):
            raise ValueError("economy action intents require a region subject")
        if not self.resource_id or not self.motivation_event_ids:
            raise ValueError(
                "resource transfer intents require resource and motivation"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_type": "resource_transfer_intent",
            "action_kind": self.action_kind.value,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "resource_id": self.resource_id,
            "motivation_event_ids": list(self.motivation_event_ids),
            "preferences": [item.value for item in self.preferences],
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceTransferIntentProposal":
        if data["proposal_type"] != "resource_transfer_intent":
            raise ValueError("unsupported proposal type")
        return cls(
            id=str(data["id"]),
            action_kind=EconomyIntentKind(str(data["action_kind"])),
            subject_kind=str(data["subject_kind"]),
            subject_id=str(data["subject_id"]),
            resource_id=str(data["resource_id"]),
            motivation_event_ids=tuple(
                str(item) for item in data["motivation_event_ids"]
            ),
            preferences=tuple(
                EconomyPreference(str(item)) for item in data.get("preferences", [])
            ),
            reason=str(data.get("reason", "")),
        )


@dataclass(frozen=True, slots=True)
class EconomyDecision:
    decision: EconomyDecisionKind
    reason: str
    action_intent: ResourceTransferIntentProposal | None = None

    def __post_init__(self) -> None:
        if self.decision is EconomyDecisionKind.ACT and self.action_intent is None:
            raise ValueError("an acting economy decision requires an action intent")
        if (
            self.decision is EconomyDecisionKind.MAINTAIN
            and self.action_intent is not None
        ):
            raise ValueError(
                "a maintain economy decision cannot carry an action intent"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "action_intent": self.action_intent.to_dict()
            if self.action_intent
            else None,
        }


class CityDecisionKind(StrEnum):
    MAINTAIN = "maintain"
    URBAN_MAINTENANCE = "urban_maintenance"
    URBAN_CAPACITY_PROJECT = "urban_capacity_project"


class CityIntentKind(StrEnum):
    URBAN_MAINTENANCE = "urban_maintenance"
    URBAN_CAPACITY_PROJECT = "urban_capacity_project"


@dataclass(frozen=True, slots=True)
class CityCapacityProjectIntentProposal:
    """A request to start a grounded project; the engine owns every number."""

    action_kind: CityIntentKind
    subject_kind: str
    subject_id: str
    project_kind: str
    motivation_event_ids: tuple[str, ...]
    reason: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.action_kind is not CityIntentKind.URBAN_CAPACITY_PROJECT:
            raise ValueError("unsupported city capacity project intent")
        if self.subject_kind != "city" or not self.subject_id.startswith("region:"):
            raise ValueError("city intents require a region city subject")
        if self.project_kind != "settlement_capacity_expansion":
            raise ValueError("unsupported urban capacity project kind")
        if not self.motivation_event_ids:
            raise ValueError("city intents require causal motivation")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_type": "city_capacity_project_intent",
            "action_kind": self.action_kind.value,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "project_kind": self.project_kind,
            "motivation_event_ids": list(self.motivation_event_ids),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class CityMaintenanceIntentProposal:
    """A typed request to maintain one grounded urban capability.

    The interpreter may select the capability, but never the amount of work or
    the resulting delta.  Those values belong to the deterministic executor.
    """

    action_kind: CityIntentKind
    subject_kind: str
    subject_id: str
    capability_id: str
    motivation_event_ids: tuple[str, ...]
    reason: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.action_kind is not CityIntentKind.URBAN_MAINTENANCE:
            raise ValueError("unsupported city intent")
        if self.subject_kind != "city" or not self.subject_id.startswith("region:"):
            raise ValueError("city intents require a region city subject")
        if not self.capability_id.strip():
            raise ValueError("city maintenance requires a capability")
        if not self.motivation_event_ids:
            raise ValueError("city intents require causal motivation")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_type": "city_action_intent",
            "action_kind": self.action_kind.value,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "capability_id": self.capability_id,
            "motivation_event_ids": list(self.motivation_event_ids),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CityMaintenanceIntentProposal":
        if data["proposal_type"] != "city_action_intent":
            raise ValueError("unsupported proposal type")
        return cls(
            id=str(data["id"]),
            action_kind=CityIntentKind(str(data["action_kind"])),
            subject_kind=str(data["subject_kind"]),
            subject_id=str(data["subject_id"]),
            capability_id=str(data["capability_id"]),
            motivation_event_ids=tuple(
                str(item) for item in data["motivation_event_ids"]
            ),
            reason=str(data.get("reason", "")),
        )


@dataclass(frozen=True, slots=True)
class CityDecision:
    decision: CityDecisionKind
    reason: str
    action_intent: (
        CityMaintenanceIntentProposal | CityCapacityProjectIntentProposal | None
    ) = None

    def __post_init__(self) -> None:
        if (
            self.decision is not CityDecisionKind.MAINTAIN
            and self.action_intent is None
        ):
            raise ValueError("an acting city decision requires an action intent")
        if (
            self.decision is CityDecisionKind.MAINTAIN
            and self.action_intent is not None
        ):
            raise ValueError("maintain cannot carry an action intent")
        if self.decision is CityDecisionKind.URBAN_MAINTENANCE and not isinstance(
            self.action_intent, CityMaintenanceIntentProposal
        ):
            raise ValueError("urban maintenance requires a maintenance intent")
        if self.decision is CityDecisionKind.URBAN_CAPACITY_PROJECT and not isinstance(
            self.action_intent, CityCapacityProjectIntentProposal
        ):
            raise ValueError(
                "urban capacity project requires a capacity project intent"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "action_intent": self.action_intent.to_dict()
            if self.action_intent
            else None,
        }


class GovernmentDecisionKind(StrEnum):
    MAINTAIN = "maintain"
    URBAN_MAINTENANCE = "urban_maintenance"
    URBAN_CAPACITY_PROJECT = "urban_capacity_project"


class GovernmentIntentKind(StrEnum):
    URBAN_MAINTENANCE = "urban_maintenance"
    URBAN_CAPACITY_PROJECT = "urban_capacity_project"


@dataclass(frozen=True, slots=True)
class GovernmentUrbanIntentProposal:
    """A dynasty's request for an existing deterministic city affordance."""

    action_kind: GovernmentIntentKind
    subject_kind: str
    subject_id: str
    region_id: str
    motivation_event_ids: tuple[str, ...]
    capability_id: str = ""
    project_kind: str = ""
    reason: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.subject_kind != "dynasty" or not self.subject_id.strip():
            raise ValueError("government intents require a dynasty subject")
        if not self.region_id.strip():
            raise ValueError("government intents require a governed region")
        if not self.motivation_event_ids or any(
            not str(event_id).strip() for event_id in self.motivation_event_ids
        ):
            raise ValueError("government intents require causal motivation")
        if self.action_kind is GovernmentIntentKind.URBAN_MAINTENANCE:
            if not self.capability_id.strip() or self.project_kind:
                raise ValueError("government maintenance requires only a capability")
        elif self.action_kind is GovernmentIntentKind.URBAN_CAPACITY_PROJECT:
            if (
                self.project_kind != "settlement_capacity_expansion"
                or self.capability_id
            ):
                raise ValueError(
                    "government capacity projects require the supported project kind"
                )
        else:
            raise ValueError("unsupported government intent")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_type": "government_urban_intent",
            "action_kind": self.action_kind.value,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "region_id": self.region_id,
            "motivation_event_ids": list(self.motivation_event_ids),
            "capability_id": self.capability_id,
            "project_kind": self.project_kind,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class GovernmentDecision:
    decision: GovernmentDecisionKind
    reason: str
    action_intent: GovernmentUrbanIntentProposal | None = None

    def __post_init__(self) -> None:
        if (
            self.decision is GovernmentDecisionKind.MAINTAIN
            and self.action_intent is not None
        ):
            raise ValueError("maintain cannot carry a government intent")
        if (
            self.decision is not GovernmentDecisionKind.MAINTAIN
            and self.action_intent is None
        ):
            raise ValueError("an acting government decision requires an intent")
        if (
            self.action_intent is not None
            and self.decision.value != self.action_intent.action_kind.value
        ):
            raise ValueError("government decision and intent must agree")

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "action_intent": self.action_intent.to_dict()
            if self.action_intent
            else None,
        }


class OrganizationDecisionKind(StrEnum):
    MAINTAIN = "maintain"
    SUPPORT_MEMBER = "support_member"


class OrganizationIntentKind(StrEnum):
    SUPPORT_MEMBER = "support_member"


@dataclass(frozen=True, slots=True)
class SectMemberSupportIntentProposal:
    """A sect's intent to support one eligible member; the owner sets the amount."""

    action_kind: OrganizationIntentKind
    subject_kind: str
    subject_id: str
    member_id: str
    region_id: str
    motivation_event_ids: tuple[str, ...]
    reason: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.action_kind is not OrganizationIntentKind.SUPPORT_MEMBER:
            raise ValueError("unsupported organization intent")
        if self.subject_kind != "sect" or not self.subject_id.strip():
            raise ValueError("organization intents require a sect subject")
        if not self.member_id.strip() or not self.region_id.strip():
            raise ValueError("sect support requires a member and region")
        if not self.motivation_event_ids or any(
            not str(event_id).strip() for event_id in self.motivation_event_ids
        ):
            raise ValueError("organization intents require causal motivation")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_type": "sect_member_support_intent",
            "action_kind": self.action_kind.value,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "member_id": self.member_id,
            "region_id": self.region_id,
            "motivation_event_ids": list(self.motivation_event_ids),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class OrganizationDecision:
    decision: OrganizationDecisionKind
    reason: str
    action_intent: SectMemberSupportIntentProposal | None = None

    def __post_init__(self) -> None:
        if (
            self.decision is OrganizationDecisionKind.MAINTAIN
            and self.action_intent is not None
        ):
            raise ValueError("maintain cannot carry an organization intent")
        if (
            self.decision is OrganizationDecisionKind.SUPPORT_MEMBER
            and self.action_intent is None
        ):
            raise ValueError("member support requires an organization intent")
        if self.action_intent is not None and not isinstance(
            self.action_intent, SectMemberSupportIntentProposal
        ):
            raise ValueError("organization decisions require a sect support intent")
        if (
            self.action_intent is not None
            and self.action_intent.action_kind
            is not OrganizationIntentKind.SUPPORT_MEMBER
        ):
            raise ValueError("organization decision and intent must agree")

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "action_intent": self.action_intent.to_dict()
            if self.action_intent
            else None,
        }

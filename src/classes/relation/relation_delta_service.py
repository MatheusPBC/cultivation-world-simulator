from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from src.i18n import t
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.relation.relation import NumericRelation, Relation
from src.classes.relation.relations import add_friendliness
from src.classes.state_delta import StateDelta
from src.utils.config import CONFIG
from src.utils.llm import call_llm_with_task_name

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar


@dataclass(frozen=True)
class RelationDelta:
    from_avatar: "Avatar"
    to_avatar: "Avatar"
    delta: int
    reason: str


class RelationshipValence(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    AMBIVALENT = "ambivalent"


class RelationshipIntensity(StrEnum):
    MILD = "mild"
    MODERATE = "moderate"
    STRONG = "strong"


@dataclass(frozen=True)
class DirectionalRelationshipImpact:
    valence: RelationshipValence | str
    intensity: RelationshipIntensity | str

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "valence", RelationshipValence(self.valence))
            object.__setattr__(self, "intensity", RelationshipIntensity(self.intensity))
        except ValueError as exc:
            raise ValueError("Invalid directional relationship impact") from exc

    def to_dict(self) -> dict[str, str]:
        return {"valence": self.valence.value, "intensity": self.intensity.value}


@dataclass(frozen=True)
class RelationshipImpactProposal:
    """Independent qualitative readings for both directions of a relation.

    Numeric friendliness remains owned by this service.  The interpreter can
    only select a valence and a bounded intensity; it cannot write a delta.
    """

    a_to_b: DirectionalRelationshipImpact
    b_to_a: DirectionalRelationshipImpact

    def __post_init__(self) -> None:
        if not isinstance(self.a_to_b, DirectionalRelationshipImpact) or not isinstance(
            self.b_to_a, DirectionalRelationshipImpact
        ):
            raise ValueError("Relationship impact requires both typed directions")

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {"a_to_b": self.a_to_b.to_dict(), "b_to_a": self.b_to_a.to_dict()}


class RelationDeltaService:
    TEMPLATE_PATH = CONFIG.paths.templates / "relationship_impact.txt"
    INTENSITY_TO_DELTA = {
        RelationshipIntensity.MILD: 2,
        RelationshipIntensity.MODERATE: 4,
        RelationshipIntensity.STRONG: 6,
    }

    @staticmethod
    def get_action_mode(action_key: str) -> str:
        action_modes = getattr(CONFIG.social.relation, "action_modes", None)
        return str(getattr(action_modes, action_key, "fixed") or "fixed").lower()

    @staticmethod
    def get_fixed_delta(action_key: str, outcome_key: str) -> tuple[int, int]:
        fixed_deltas = getattr(CONFIG.social.relation, "fixed_deltas", None)
        action_config = getattr(fixed_deltas, action_key, None)
        outcome_config = getattr(action_config, outcome_key, None)
        if outcome_config is None:
            return 0, 0
        return int(getattr(outcome_config, "a_to_b", 0)), int(getattr(outcome_config, "b_to_a", 0))

    @classmethod
    async def propose_relationship_impact(
        cls,
        *,
        action_key: str,
        avatar_a: "Avatar",
        avatar_b: "Avatar",
        event_text: str,
    ) -> RelationshipImpactProposal:
        mode = cls.get_action_mode(action_key)
        if mode != "llm":
            return RelationshipImpactProposal(
                DirectionalRelationshipImpact("ambivalent", "mild"),
                DirectionalRelationshipImpact("ambivalent", "mild"),
            )

        infos = {
            "avatar_a_name": avatar_a.name,
            "avatar_b_name": avatar_b.name,
            "avatar_a_personas": "、".join(p.get_info() for p in avatar_a.personas[:3]) if avatar_a.personas else t("None"),
            "avatar_b_personas": "、".join(p.get_info() for p in avatar_b.personas[:3]) if avatar_b.personas else t("None"),
            "avatar_a_to_b_numeric_relation": str(avatar_a.get_numeric_relation(avatar_b)),
            "avatar_b_to_a_numeric_relation": str(avatar_b.get_numeric_relation(avatar_a)),
            "avatar_a_to_b_friendliness": avatar_a.get_friendliness(avatar_b),
            "avatar_b_to_a_friendliness": avatar_b.get_friendliness(avatar_a),
            "identity_relations": "、".join(
                sorted(rel.value for rel in (avatar_a.get_relation_state(avatar_b).identity_relations if avatar_a.get_relation_state(avatar_b) else set()))
            ) or t("None"),
            "event_text": event_text,
        }
        result = await call_llm_with_task_name("relationship_impact", cls.TEMPLATE_PATH, infos)
        try:
            return RelationshipImpactProposal(
                DirectionalRelationshipImpact(**dict(result["a_to_b"])),
                DirectionalRelationshipImpact(**dict(result["b_to_a"])),
            )
        except (KeyError, TypeError, ValueError):
            return RelationshipImpactProposal(
                DirectionalRelationshipImpact("ambivalent", "mild"),
                DirectionalRelationshipImpact("ambivalent", "mild"),
            )

    @classmethod
    def apply_relationship_impact(
        cls,
        avatar_a: "Avatar",
        avatar_b: "Avatar",
        proposal: RelationshipImpactProposal,
        *,
        source_event: Event,
        action_key: str,
        allowed_a_to_b: frozenset[RelationshipValence],
        allowed_b_to_a: frozenset[RelationshipValence],
    ) -> Event:
        """Convert qualitative categories to bounded, owner-applied deltas."""

        def resolve(
            impact: DirectionalRelationshipImpact,
            allowed: frozenset[RelationshipValence],
        ) -> int:
            if impact.valence not in allowed or impact.valence in {
                RelationshipValence.NEUTRAL,
                RelationshipValence.AMBIVALENT,
            }:
                return 0
            amount = cls.INTENSITY_TO_DELTA[impact.intensity]
            return amount if impact.valence is RelationshipValence.POSITIVE else -amount

        requested_a_to_b = resolve(proposal.a_to_b, allowed_a_to_b)
        requested_b_to_a = resolve(proposal.b_to_a, allowed_b_to_a)
        before_a_to_b = avatar_a.get_friendliness(avatar_b)
        before_b_to_a = avatar_b.get_friendliness(avatar_a)
        if requested_a_to_b or requested_b_to_a:
            cls.apply_bidirectional_delta(
                avatar_a,
                avatar_b,
                requested_a_to_b,
                requested_b_to_a,
            )
        after_a_to_b = avatar_a.get_friendliness(avatar_b)
        after_b_to_a = avatar_b.get_friendliness(avatar_a)
        changed = before_a_to_b != after_a_to_b or before_b_to_a != after_b_to_a
        event = Event(
            avatar_a.world.month_stamp,
            t(
                "Relationship impact for {action} was interpreted.",
                action=action_key,
            ),
            related_avatars=[avatar_a.id, avatar_b.id],
            event_type=("relationship_transition" if changed else "relationship_interpretation"),
            fact_kind=(FactKind.STATE_TRANSITION if changed else FactKind.OCCURRENCE),
            causal_origin=(CausalOrigin.DETERMINISTIC if changed else CausalOrigin.LLM_INTERPRETATION),
            render_params={"action_key": action_key},
            causal_payload={
                "deltas": [],
                "relationship_impact": proposal.to_dict(),
            },
        )
        if changed:
            deltas = []
            for owner_id, before, after in (
                (f"{avatar_a.id}->{avatar_b.id}", before_a_to_b, after_a_to_b),
                (f"{avatar_b.id}->{avatar_a.id}", before_b_to_a, after_b_to_a),
            ):
                if before == after:
                    continue
                deltas.append(
                    StateDelta(
                        event_id=event.id,
                        owner_kind="relationship",
                        owner_id=owner_id,
                        aspect="friendliness",
                        before=str(before),
                        after=str(after),
                        magnitude=after - before,
                    ).to_dict()
                )
            event.causal_payload["deltas"] = deltas
        event.causal_links.append(
            CausalLink(
                event_id=event.id,
                cause_event_id=source_event.id,
                relation=CausalRelation.RESPONSE_TO,
            )
        )
        return event

    @staticmethod
    def apply_bidirectional_delta(
        avatar_a: "Avatar",
        avatar_b: "Avatar",
        a_to_b: int,
        b_to_a: int,
    ) -> None:
        current_month = int(avatar_a.world.month_stamp)
        add_friendliness(avatar_a, avatar_b, a_to_b, current_month=current_month)
        add_friendliness(avatar_b, avatar_a, b_to_a, current_month=current_month)

    @staticmethod
    def set_hostility(avatar_a: "Avatar", avatar_b: "Avatar") -> None:
        current_month = int(avatar_a.world.month_stamp)
        add_friendliness(avatar_a, avatar_b, -1000, current_month=current_month)
        add_friendliness(avatar_b, avatar_a, -1000, current_month=current_month)

    @staticmethod
    def get_numeric_relation_rank(relation: NumericRelation) -> int:
        ranks = {
            NumericRelation.ARCHENEMY: 0,
            NumericRelation.DISLIKED: 1,
            NumericRelation.STRANGER: 2,
            NumericRelation.FRIEND: 3,
            NumericRelation.BEST_FRIEND: 4,
        }
        if not isinstance(relation, NumericRelation):
            relation = NumericRelation.STRANGER
        return ranks[relation]

    @staticmethod
    def is_friend_or_better(avatar_a: "Avatar", avatar_b: "Avatar") -> bool:
        return RelationDeltaService.get_numeric_relation_rank(avatar_a.get_numeric_relation(avatar_b)) >= RelationDeltaService.get_numeric_relation_rank(NumericRelation.FRIEND)

    @staticmethod
    def has_identity(avatar_a: "Avatar", avatar_b: "Avatar", relation: Relation) -> bool:
        return avatar_a.has_identity_relation(avatar_b, relation)


__all__ = [
    "DirectionalRelationshipImpact",
    "RelationDelta",
    "RelationDeltaService",
    "RelationshipImpactProposal",
    "RelationshipIntensity",
    "RelationshipValence",
]

"""Raised detachments: people and provisions that physically stand somewhere.

A detachment owns no territory, no stock and no authority. It records which
soldiers of a real cohort are away, where they are, what they still carry and
how they are moving. Occupation is a separate settlement fact and never a
property of this record.
"""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from src.classes.mechanical_language import EntityRef
from .models import Count, Identity, SocietyValue


PositiveCount = Annotated[int, Field(strict=True, gt=0)]


class Detachment(SocietyValue):
    id: Identity
    owner_ref: EntityRef
    source_group_id: Identity
    count: PositiveCount
    location_id: Identity
    destination_id: Identity
    route_ids: tuple[Identity, ...] = ()
    route_index: Count = 0
    provisions: Count = 0
    stage: Literal["marching", "present", "disbanded"] = "marching"
    started_day: Count
    due_day: Count
    decision_event_id: Identity
    last_event_id: Identity


class ForceStandoff(SocietyValue):
    """A factual armed contact between two present detachments.

    This is neither a battle nor an occupation. It keeps the physical pair and
    place that observers encountered, so each owner may later choose whether
    to stand its own column down. The force records themselves retain their
    owners and material means; this record deliberately copies neither.
    """
    id: Identity
    detachment_ids: tuple[Identity, Identity]
    settlement_id: Identity
    started_day: Count
    started_event_id: Identity
    stage: Literal["active", "resolved"] = "active"
    resolved_day: Count | None = None
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if self.detachment_ids[0] >= self.detachment_ids[1]:
            raise ValueError("standoff detachments must be distinct and ordered")
        if (self.stage == "active") != (self.resolved_day is None):
            raise ValueError("standoff resolution state is inconsistent")
        if self.resolved_day is not None and self.resolved_day < self.started_day:
            raise ValueError("standoff cannot resolve before it starts")
        return self


class ForcePosition(SocietyValue):
    """A detachment's dated preparation at the place where it stands.

    It is neither terrain control nor a combat modifier.  The record names an
    optional already-existing map site only as an anchor for later evidence;
    it creates no site and grants no material benefit in this vertical.
    """
    id: Identity
    detachment_id: Identity
    stage: Literal["preparing", "prepared"] = "preparing"
    settlement_id: Identity
    anchor_site_id: Identity | None = None
    started_day: Count
    ready_day: Count
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_timing(self):
        if self.id != f"force-position:{self.detachment_id}" or self.ready_day != self.started_day + 3:
            raise ValueError("force position identity or preparation time is inconsistent")
        return self


class DetachmentCommand(SocietyValue):
    """One real person's current command of one physically present column.

    The registry is deliberately keyed by detachment ID, not by an office or
    title.  Authority remains in ``AuthorityState`` and is re-read whenever a
    command is appointed or kept; this record only joins an already-existing
    person to an already-existing column.
    """
    id: Identity
    detachment_id: Identity
    character_id: Identity
    institution_ref: EntityRef
    office_id: Identity
    doctrine: Literal["hold", "press"] | None = None
    doctrine_effective_day: Count | None = None
    # Retains the active doctrine while a replacement waits for tomorrow.  It
    # is mechanical transition state, not a second tactical preference.
    previous_doctrine: Literal["hold", "press"] | None = None
    appointed_day: Count
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if (self.id != self.detachment_id
                or (self.doctrine is None) != (self.doctrine_effective_day is None)
                or (self.doctrine_effective_day is not None
                    and self.doctrine_effective_day <= self.appointed_day)):
            raise ValueError("detachment command identity or doctrine timing is inconsistent")
        return self


class FieldEngagement(SocietyValue):
    """One voluntary, resolved-or-lapsed clash between two contact columns."""
    id: Identity
    standoff_id: Identity
    challenger_ref: EntityRef
    defender_ref: EntityRef
    challenger_detachment_id: Identity
    defender_detachment_id: Identity
    settlement_id: Identity
    offered_day: Count
    expires_day: Count
    decision_event_id: Identity
    offer_event_id: Identity
    status: Literal["offered", "resolved", "lapsed"] = "offered"
    winner_ref: EntityRef | None = None
    challenger_casualties: Count = 0
    defender_casualties: Count = 0
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if (self.id != f"field-engagement:{self.decision_event_id}" or self.challenger_ref == self.defender_ref
                or self.challenger_detachment_id == self.defender_detachment_id
                or self.expires_day <= self.offered_day):
            raise ValueError("field engagement identity or parties are inconsistent")
        if self.status == "offered" and (self.winner_ref is not None
                                          or self.challenger_casualties or self.defender_casualties):
            raise ValueError("open field engagement has no outcome")
        if self.status == "lapsed" and (self.winner_ref is not None
                                          or self.challenger_casualties or self.defender_casualties):
            raise ValueError("lapsed field engagement has no outcome")
        return self


class RouteInterdiction(SocietyValue):
    """A prepared present column's single physical restriction of one route."""
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    route_id: Identity
    settlement_id: Identity
    investment_id: Identity | None = None
    started_day: Count
    decision_event_id: Identity
    stage: Literal["active", "lifted"] = "active"
    lifted_day: Count | None = None
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if (not (self.id == f"route-interdiction:{self.decision_event_id}"
                 or self.id.startswith(f"route-interdiction:{self.decision_event_id}:investment:"))
                or (self.stage == "active") != (self.lifted_day is None)
                or (self.lifted_day is not None and self.lifted_day < self.started_day)):
            raise ValueError("route interdiction identity or lifecycle is inconsistent")
        return self


class SettlementInvestment(SocietyValue):
    """One prepared column's bounded pressure over every usable local exit.

    The settlement and the routes retain their normal owners.  This record is
    only the provenance tying together the already-existing force interdictors
    that make the pressure physical.
    """
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    settlement_id: Identity
    route_ids: tuple[Identity, ...]
    route_interdiction_ids: tuple[Identity, ...]
    started_day: Count
    decision_event_id: Identity
    stage: Literal["active", "lifted"] = "active"
    lifted_day: Count | None = None
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if (self.id != f"settlement-investment:{self.decision_event_id}"
                or not self.route_ids or tuple(sorted(set(self.route_ids))) != self.route_ids
                or len(self.route_ids) != len(self.route_interdiction_ids)
                or len(set(self.route_interdiction_ids)) != len(self.route_interdiction_ids)
                or (self.stage == "active") != (self.lifted_day is None)
                or (self.lifted_day is not None and self.lifted_day < self.started_day)):
            raise ValueError("settlement investment identity or lifecycle is inconsistent")
        return self


class AssemblyDenial(SocietyValue):
    """The active, local denial of assembly at one existing site.

    It is an occupied physical posture, not a change to the site or to the
    rite's sponsor.  The registry holds only active denials; the lifted fact
    remains in history after a column leaves.
    """
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    settlement_id: Identity
    started_day: Count
    decision_event_id: Identity
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if self.id.startswith("assembly-denial:"):
            raise ValueError("assembly denial must be keyed by its site ID")
        return self

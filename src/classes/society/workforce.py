"""Dated local or cross-settlement changes of economic occupation.

This is deliberately narrower than education or a generic skill system.  A
transition records a paid occupational conversion made possible by a real
labour deficit (including a return to farming when food production is blocked).
While it is active
the people remain members of their source cohort, but Society marks them
unavailable to every other material use.  When ``destination_settlement_id``
differs from the source group's own settlement, the same conversion also
relocates the recruited people there once the current travel time this
sponsor's own route knowledge names has actually elapsed; a customs
checkpoint's merchant demand never recruits beyond its own settlement in this
version.
"""

from typing import Annotated, Literal

from pydantic import Field

from src.classes.mechanical_language import EntityRef
from .models import Count, Identity, SocietyValue


PositiveCount = Annotated[int, Field(strict=True, gt=0)]


class WorkforceTransition(SocietyValue):
    id: Identity
    source_group_id: Identity
    target_group_id: Identity
    sponsor_ref: EntityRef
    demand_id: Identity
    notice_id: Identity
    work_kind: Literal["facility", "repair", "customs"]
    work_id: Identity
    target_occupation: Literal["farmer", "artisan", "merchant"]
    destination_settlement_id: Identity
    count: PositiveCount
    stipend_per_person: PositiveCount
    started_day: Count
    due_day: Count
    decision_event_id: Identity
    last_event_id: Identity

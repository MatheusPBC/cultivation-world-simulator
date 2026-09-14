"""Dated local changes of economic occupation.

This is deliberately narrower than education or a generic skill system.  A
transition only records a paid, local farmer-to-artisan or farmer-to-merchant
conversion that was made possible by a real labour deficit.  While it is active
the people remain members of their source cohort, but Society marks them
unavailable to every other material use.
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
    target_occupation: Literal["artisan", "merchant"]
    count: PositiveCount
    stipend_per_person: PositiveCount
    started_day: Count
    due_day: Count
    decision_event_id: Identity
    last_event_id: Identity

"""Aggregate generations. There are no names, families or lineages here."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .models import Count, Identity, People, SocietyValue

MATURITY_DAYS_BY_PEOPLE: dict[People, int] = {
    "human": 15 * 360,
    "elf": 25 * 360,
    "dwarf": 20 * 360,
    "orc": 12 * 360,
}


class BirthCohort(SocietyValue):
    """One dated batch of new residents, waiting to become working age.

    The batch is a promise about a real dependent cohort, never a claim on
    people who are still there: deprivation and migration may reduce them, and
    maturation moves only whoever actually remains.
    """

    id: Identity
    settlement_id: Identity
    people: People
    count: Annotated[int, Field(strict=True, gt=0)]
    born_day: Count
    maturity_days: Count
    matures_day: Count
    stage: Literal["pending", "matured"] = "pending"
    birth_event_id: Identity
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if (self.id != f"birth-cohort:{self.birth_event_id}:{self.settlement_id}:{self.people}"
                or self.maturity_days != MATURITY_DAYS_BY_PEOPLE[self.people]
                or self.matures_day != self.born_day + self.maturity_days):
            raise ValueError("birth cohort identity or maturity is inconsistent")
        return self

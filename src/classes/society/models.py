"""Medieval identities. Wealth, knowledge and authority have separate owners."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


People = Literal["human", "elf", "dwarf", "orc"]
Occupation = Literal["farmer", "artisan", "merchant", "scholar", "soldier", "dependent"]
Identity = Annotated[str, Field(min_length=1, pattern=r"^\S(?:.*\S)?$")]
Count = Annotated[int, Field(strict=True, ge=0)]
Skill = Annotated[int, Field(strict=True, ge=0, le=100)]
Disposition = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class SocietyValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Skills(SocietyValue):
    combat: Skill = 0
    command: Skill = 0
    diplomacy: Skill = 0
    commerce: Skill = 0
    investigation: Skill = 0
    craftsmanship: Skill = 0
    elemental_magic: Skill = 0
    protection_magic: Skill = 0
    restoration_magic: Skill = 0
    evocation_magic: Skill = 0


class Personality(SocietyValue):
    ambition: Disposition = 0.5
    compassion: Disposition = 0.5
    loyalty: Disposition = 0.5
    caution: Disposition = 0.5
    curiosity: Disposition = 0.5


class Character(SocietyValue):
    id: Identity
    name: Identity
    people: People
    birth_day: int = Field(strict=True)
    location_id: Identity
    population_group_id: Identity | None
    skills: Skills = Field(default_factory=Skills)
    personality: Personality = Field(default_factory=Personality)
    motivations: tuple[Identity, ...] = ()
    titles: tuple[Identity, ...] = ()
    death_day: Count | None = None

    @model_validator(mode="after")
    def check_life(self):
        if self.death_day is not None:
            if self.death_day < self.birth_day or self.population_group_id is not None:
                raise ValueError("dead characters must be archived outside living population")
        elif self.population_group_id is None:
            raise ValueError("living characters require a population group")
        return self


class PopulationGroup(SocietyValue):
    """Count includes named living members, not an additional anonymous population."""

    id: Identity
    settlement_id: Identity
    people: People
    occupation: Occupation
    count: Count


class Settlement(SocietyValue):
    id: Identity
    region_id: int = Field(strict=True, gt=0)
    name: Identity
    kind: Literal["city", "village"]
    administrator_id: Identity | None
    occupier_id: Identity | None = None
    claimant_ids: tuple[Identity, ...] = ()
    housing_capacity: Count


class Polity(SocietyValue):
    id: Identity
    name: Identity
    capital_id: Identity
    government: Literal["crown", "council", "league"]
    interests: tuple[Identity, ...]


class Organization(SocietyValue):
    id: Identity
    name: Identity
    kind: Literal["noble_house", "merchant_guild", "arcane_tower", "religious_order", "cult"]
    seat_id: Identity
    member_ids: tuple[Identity, ...]
    interests: tuple[Identity, ...]

    @model_validator(mode="after")
    def unique_members(self):
        if len(set(self.member_ids)) != len(self.member_ids):
            raise ValueError("duplicate organization members")
        return self

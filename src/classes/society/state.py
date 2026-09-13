"""Canonical population and identity owner for the medieval simulation."""

from dataclasses import dataclass, field

from .models import Character, Occupation, Organization, Polity, PopulationGroup, Settlement
from .serialization import REGISTRIES, SocietySerialization


@dataclass
class SocietyState(SocietySerialization):
    characters: dict[str, Character] = field(default_factory=dict)
    settlements: dict[str, Settlement] = field(default_factory=dict)
    polities: dict[str, Polity] = field(default_factory=dict)
    organizations: dict[str, Organization] = field(default_factory=dict)
    population: dict[str, PopulationGroup] = field(default_factory=dict)

    @property
    def total_population(self) -> int:
        return sum(group.count for group in self.population.values())

    def population_at(self, settlement_id: str) -> int:
        return sum(g.count for g in self.population.values() if g.settlement_id == settlement_id)

    def validate(self, region_ids: set[int] | None = None) -> None:
        for name, model in REGISTRIES.items():
            for key, value in getattr(self, name).items():
                if not isinstance(value, model) or key != value.id:
                    raise ValueError(f"invalid {name} registry identity")
        seen_regions = set()
        for settlement in self.settlements.values():
            if settlement.region_id in seen_regions:
                raise ValueError("duplicate settlement region")
            seen_regions.add(settlement.region_id)
            if region_ids is not None and settlement.region_id not in region_ids:
                raise ValueError("settlement references unknown map region")
            for polity_id in (settlement.administrator_id, settlement.occupier_id, *settlement.claimant_ids):
                if polity_id is not None and polity_id not in self.polities:
                    raise ValueError("settlement references unknown polity")
            if len(set(settlement.claimant_ids)) != len(settlement.claimant_ids):
                raise ValueError("duplicate territorial claims")
        for polity in self.polities.values():
            if polity.capital_id not in self.settlements:
                raise ValueError("unknown capital settlement")
        for organization in self.organizations.values():
            if organization.seat_id not in self.settlements:
                raise ValueError("unknown organization seat")
            if any(member not in self.characters for member in organization.member_ids):
                raise ValueError("unknown organization member")
        named_counts: dict[str, int] = {}
        for character in self.characters.values():
            if character.location_id not in self.settlements:
                raise ValueError("unknown character location")
            if character.death_day is not None:
                continue
            group = self.population.get(character.population_group_id)
            if group is None or group.people != character.people:
                raise ValueError("invalid character population reference")
            named_counts[group.id] = named_counts.get(group.id, 0) + 1
        demographics = set()
        for group in self.population.values():
            if group.settlement_id not in self.settlements:
                raise ValueError("unknown population settlement")
            key = (group.settlement_id, group.people, group.occupation)
            if key in demographics:
                raise ValueError("duplicate population cohort")
            demographics.add(key)
            if named_counts.get(group.id, 0) > group.count:
                raise ValueError("named population exceeds cohort count")

    def _select_people(self, group_id: str, count: int, character_ids: tuple[str, ...]):
        if type(count) is not int or count <= 0:
            raise ValueError("count must be a positive integer")
        group = self.population[group_id]
        if len(set(character_ids)) != len(character_ids) or len(character_ids) > count:
            raise ValueError("invalid named selection")
        selected = []
        for character_id in character_ids:
            character = self.characters.get(character_id)
            if character is None or character.death_day is not None or character.population_group_id != group_id:
                raise ValueError("selected character is not in this population")
            selected.append(character)
        named_count = sum(c.population_group_id == group_id for c in self.characters.values())
        if count > group.count or count - len(selected) > group.count - named_count:
            raise ValueError("insufficient anonymous population; select named members explicitly")
        return group, selected

    def transfer_people(
        self, group_id: str, destination_id: str, occupation: Occupation,
        count: int, character_ids: tuple[str, ...] = (),
    ) -> str:
        """Migrate or reassign workers; recruitment is reassignment to soldier.

        All checks precede mutation. Named residents are part of the transfer,
        never an addition to its count. Temporary travel has its own owner and
        must not call this operation until residence actually changes.
        """
        group, selected = self._select_people(group_id, count, character_ids)
        if destination_id not in self.settlements:
            raise ValueError("unknown destination settlement")
        if (group.settlement_id, group.occupation) == (destination_id, occupation):
            raise ValueError("transfer must change residence or occupation")
        target = next((g for g in self.population.values() if
            (g.settlement_id, g.people, g.occupation) == (destination_id, group.people, occupation)), None)
        target_id = target.id if target else f"pop:{destination_id}:{group.people}:{occupation}"
        if target is None and target_id in self.population:
            raise ValueError("population ID collision")
        updated_target = PopulationGroup(
            id=target_id, settlement_id=destination_id, people=group.people,
            occupation=occupation, count=(target.count if target else 0) + count,
        )
        updated_source = group.model_copy(update={"count": group.count - count})
        characters = {
            c.id: c.model_copy(update={"population_group_id": target_id, "location_id": destination_id})
            for c in selected
        }
        self.population.update({group.id: updated_source, target_id: updated_target})
        self.characters.update(characters)
        return target_id

    def remove_people(
        self, group_id: str, count: int, *, day: int, character_ids: tuple[str, ...] = (),
    ) -> None:
        """Record actual deaths, preserving named histories outside living cohorts."""
        if type(day) is not int or day < 0:
            raise ValueError("day must be a non-negative integer")
        group, selected = self._select_people(group_id, count, character_ids)
        if any(c.birth_day > day for c in selected):
            raise ValueError("death precedes birth")
        self.population[group.id] = group.model_copy(update={"count": group.count - count})
        for character in selected:
            self.characters[character.id] = character.model_copy(update={
                "death_day": day, "population_group_id": None,
            })

    def set_occupation(self, settlement_id: str, polity_id: str | None) -> None:
        """Physical occupation alone neither grants administration nor erases claims."""
        if polity_id is not None and polity_id not in self.polities:
            raise ValueError("unknown occupying polity")
        settlement = self.settlements[settlement_id]
        self.settlements[settlement_id] = settlement.model_copy(update={"occupier_id": polity_id})

"""Build seeded medieval identities from the PT-BR authored content catalog."""

import json
from pathlib import Path
import random

from src.classes.society import (
    Character, Organization, Personality, Polity, PopulationGroup,
    Settlement, Skills, SocietyState,
)


CATALOG_PATH = Path(__file__).resolve().parents[2] / "static/game_configs/medieval/society.json"


def create_medieval_society(
    seed: int, *, character_count: int | None = None, catalog_path: Path = CATALOG_PATH,
) -> SocietyState:
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    if data["catalog_version"] != 1 or data["locale"] != "pt-BR":
        raise ValueError("unsupported society catalog")
    rng = random.Random(seed)
    society = SocietyState()
    for raw in data["polities"]:
        polity = Polity.model_validate(raw)
        if polity.id in society.polities:
            raise ValueError("duplicate polity")
        society.polities[polity.id] = polity
    weights = data["people_weights"]
    if not weights or any(type(w) is not int or w <= 0 for w in weights.values()):
        raise ValueError("people weights must be positive integers")
    weight_sum = sum(weights.values())
    for raw in data["settlements"]:
        settlement = Settlement.model_validate(raw)
        if settlement.id in society.settlements:
            raise ValueError("duplicate settlement")
        society.settlements[settlement.id] = settlement
        total = data["population_totals"][settlement.id]
        if type(total) is not int or total < 0:
            raise ValueError("population must be a non-negative integer")
        allocated = {people: total * weight // weight_sum for people, weight in weights.items()}
        # Largest remainders preserve the exact population even for small villages.
        priority = sorted(weights, key=lambda p: (-(total * weights[p] % weight_sum), p))
        for people in priority[:total - sum(allocated.values())]:
            allocated[people] += 1
        occupation = "artisan" if settlement.kind == "city" else "farmer"
        for people, count in allocated.items():
            group_id = f"pop:{settlement.id}:{people}:{occupation}"
            society.population[group_id] = PopulationGroup(
                id=group_id, settlement_id=settlement.id, people=people,
                occupation=occupation, count=count,
            )
    names = [f"{first} {family}" for family in data["family_names"] for first in data["first_names"]]
    rng.shuffle(names)
    count = data["character_count"] if character_count is None else character_count
    if type(count) is not int or count < 0 or count > len(names) or len(set(names)) != len(names):
        raise ValueError("invalid character count or duplicate names")
    groups = list(society.population.values())
    group_named_count = {group.id: 0 for group in groups}
    settlement_named_count = {settlement_id: 0 for settlement_id in society.settlements}
    skill_names = list(Skills.model_fields)
    for index in range(count):
        available = [g for g in groups if group_named_count[g.id] < g.count]
        if not available:
            raise ValueError("named characters exceed available population")
        # Pick the least represented cohort so each community receives named actors.
        preferred_people = list(weights)[index % len(weights)]
        group = min(available, key=lambda g: (
            settlement_named_count[g.settlement_id], g.people != preferred_people,
            group_named_count[g.id], g.id,
        ))
        group_named_count[group.id] += 1
        settlement_named_count[group.settlement_id] += 1
        skill_values = {name: rng.randint(5, 30) for name in skill_names}
        skill_values[skill_names[index % len(skill_names)]] = rng.randint(50, 85)
        character_id = f"character:{index + 1:03d}"
        society.characters[character_id] = Character(
            id=character_id, name=names[index], people=group.people,
            birth_day=-rng.randint(20, 65) * 360 - rng.randint(0, 359),
            location_id=group.settlement_id, population_group_id=group.id,
            skills=Skills(**skill_values),
            personality=Personality(**{name: round(rng.random(), 3) for name in Personality.model_fields}),
            motivations=tuple(rng.sample(data["motivations"], 2)),
        )
    for index, raw in enumerate(data["organizations"]):
        organization = Organization.model_validate({
            **raw,
            "member_ids": [
                c.id for i, c in enumerate(society.characters.values())
                if i % len(data["organizations"]) == index
            ],
        })
        if organization.id in society.organizations:
            raise ValueError("duplicate organization")
        society.organizations[organization.id] = organization
    society.validate()
    return society

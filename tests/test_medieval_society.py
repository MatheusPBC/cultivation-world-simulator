import json

import pytest

from src.classes.society import SocietyState
from src.run.medieval_society import create_medieval_society


def test_initial_society_has_multiple_governments_and_mixed_populations():
    society = create_medieval_society(seed=73)
    society.validate()
    assert len(society.polities) == 3
    assert len(society.characters) == 12
    assert {c.location_id for c in society.characters.values()} == set(society.settlements)
    assert sum(s.kind == "city" for s in society.settlements.values()) == 3
    assert sum(s.kind == "village" for s in society.settlements.values()) == 5
    assert {o.kind for o in society.organizations.values()} >= {
        "noble_house", "merchant_guild", "arcane_tower", "religious_order", "cult"
    }
    for settlement_id in society.settlements:
        assert {g.people for g in society.population.values() if g.settlement_id == settlement_id} == {
            "human", "elf", "dwarf", "orc"
        }
    assert society.total_population == 10900
    assert sum(g.count for g in society.population.values()) == society.total_population


def test_seeded_society_serializes_without_shared_objects_or_cultivation_fields():
    society = create_medieval_society(seed=73)
    payload = json.loads(json.dumps(society.to_dict(), allow_nan=False))
    loaded = SocietyState.from_dict(payload)
    assert loaded.to_dict() == society.to_dict()
    assert create_medieval_society(seed=73).to_dict() == payload
    assert create_medieval_society(seed=74).to_dict() != payload
    assert all("cultivation_progress" not in c for c in payload["characters"].values())
    assert all("combat" in c["skills"] and "diplomacy" in c["skills"] for c in payload["characters"].values())


def test_recruiting_a_named_worker_preserves_population_and_removes_the_worker():
    society = create_medieval_society(seed=73)
    character = next(iter(society.characters.values()))
    group = society.population[character.population_group_id]
    original_count = group.count
    soldier_id = f"pop:{group.settlement_id}:{group.people}:soldier"
    original_soldiers = society.population[soldier_id].count
    total = society.total_population
    target = society.transfer_people(group.id, group.settlement_id, "soldier", 1, (character.id,))
    assert society.total_population == total
    assert society.population[group.id].count == original_count - 1
    assert society.population[target].count == original_soldiers + 1
    assert society.characters[character.id].population_group_id == target
    society.validate()


def test_migration_changes_residence_but_does_not_duplicate_people():
    society = create_medieval_society(seed=73)
    character = next(iter(society.characters.values()))
    group = society.population[character.population_group_id]
    destination = next(s for s in society.settlements if s != group.settlement_id)
    total = society.total_population
    target = society.transfer_people(group.id, destination, group.occupation, 10, (character.id,))
    assert society.total_population == total
    assert society.population[target].settlement_id == destination
    assert society.characters[character.id].location_id == destination
    society.validate()


def test_anonymous_losses_cannot_accidentally_kill_named_characters():
    society = create_medieval_society(seed=73)
    character = next(iter(society.characters.values()))
    group = society.population[character.population_group_id]
    before = society.to_dict()
    with pytest.raises(ValueError, match="named"):
        society.remove_people(group.id, group.count, day=10)
    assert society.to_dict() == before


def test_named_death_changes_population_once_and_retains_history():
    society = create_medieval_society(seed=73)
    character = next(iter(society.characters.values()))
    total = society.total_population
    society.remove_people(character.population_group_id, 1, day=10, character_ids=(character.id,))
    assert society.total_population == total - 1
    assert society.characters[character.id].death_day == 10
    assert society.characters[character.id].population_group_id is None
    assert society.characters[character.id].name == character.name
    society.validate()


def test_malformed_saved_population_and_dangling_references_are_rejected():
    payload = create_medieval_society(seed=73).to_dict()
    first = next(iter(payload["characters"]))
    payload["characters"][first]["population_group_id"] = "missing"
    with pytest.raises(ValueError, match="population"):
        SocietyState.from_dict(payload)


def test_occupation_does_not_grant_administration_or_erase_claims():
    society = create_medieval_society(seed=73)
    settlement = next(iter(society.settlements.values()))
    invader = next(p for p in society.polities if p != settlement.administrator_id)
    original_admin = settlement.administrator_id
    original_claims = settlement.claimant_ids
    society.set_occupation(settlement.id, invader)
    assert society.settlements[settlement.id].occupier_id == invader
    assert society.settlements[settlement.id].administrator_id == original_admin
    assert society.settlements[settlement.id].claimant_ids == original_claims


def test_infeasible_migration_leaves_the_entire_society_unchanged():
    society = create_medieval_society(seed=73)
    group = next(iter(society.population.values()))
    before = society.to_dict()
    with pytest.raises(ValueError):
        society.transfer_people(group.id, "missing", "soldier", 2)
    assert society.to_dict() == before


def test_character_count_is_configurable_without_creating_extra_people():
    small = create_medieval_society(seed=73, character_count=6)
    large = create_medieval_society(seed=73, character_count=60)
    assert len(small.characters) == 6
    assert len(large.characters) == 60
    assert small.total_population == large.total_population == 10900

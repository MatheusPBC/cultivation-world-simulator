"""Two material ends of a life, both engine-owned laws and neither a story.

Sustained deprivation kills: ``consume_monthly`` already accumulates the real
shortfall in ``SettlementNeeds.health``, dropping it by this cycle's pressure
and raising it when the ration is met. Only when that accumulator sits at its
floor *and* the same cycle still recorded a deficit does a settlement lose
people, by a fixed permille of the cohorts that were actually counted as
needing rations. Nothing is drawn at random, nobody is chosen, and a single bad
month kills no one.

A named person also reaches the end of a lifetime. That fact releases nothing
but the person: assets, offices, columns and administrations keep their owners,
and the existing revocations decide what stops working.
"""

from src.classes.event import FactKind

from .economy import _causes, _delta
from .events import record_event
from .force_command import revoke_invalid_detachment_commands

# Permille of the counted residents lost in one cycle at the floor of health.
DEPRIVATION_PERMILLE = 20
HEALTH_FLOOR = 0
# Twelve months of thirty days; a lifetime is declared, never sampled.
LIFESPAN_DAYS = 70 * 360


def _living_named(world, group_id):
    return sum(1 for item in world.society.characters.values()
               if item.death_day is None and item.population_group_id == group_id)


def _deprivation_deaths(world, available=None):
    """Cohorts of a settlement whose own subsistence receipt is at the floor."""
    day = world.clock.absolute_day
    removed = {}
    for need_id in sorted(world.economy.needs):
        need = world.economy.needs[need_id]
        if need.health > HEALTH_FLOOR or need.missing_food <= 0:
            continue
        groups = [item for _, item in sorted(world.society.population.items())
                  if item.settlement_id == need_id]
        losses = []
        for group in groups:
            # The people who starve are exactly the ones the same cycle counted
            # as eating from this settlement, never those away with a column,
            # a journey or another settlement's ration.
            counted = max(0, world.society.available_count(group.id))
            anonymous = max(0, group.count - _living_named(world, group.id))
            deaths = min(counted * DEPRIVATION_PERMILLE // 1000, anonymous)
            if deaths > 0:
                losses.append((group, deaths))
        if not losses:
            continue
        settlement = world.society.settlements[need_id]
        event = record_event(
            world, "deprivation_deaths",
            f"{settlement.name}: {sum(count for _, count in losses)} pessoas morreram de privação sustentada.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=tuple(_delta("population_group", group.id, "count", group.count, group.count - count)
                         for group, count in losses),
            cause_ids=_causes(need.last_event_id, *(group.last_event_id for group, _ in losses)))
        for group, count in losses:
            # Named residents are never consumed by an aggregate loss; the
            # owner refuses a count that would reach them.
            world.society.remove_people(group.id, count, day=day)
            world.society.population[group.id] = world.society.population[group.id].model_copy(
                update={"last_event_id": event.id})
            removed[group.id] = removed.get(group.id, 0) + count
            if available is not None and group.id in available:
                available[group.id] = max(0, available[group.id] - count)
    return removed


def _lifetime_deaths(world):
    """A declared lifetime ends; no asset, office or command changes hands."""
    day = world.clock.absolute_day
    ended = []
    for character_id in sorted(world.society.characters):
        character = world.society.characters[character_id]
        group = world.society.population.get(character.population_group_id)
        if (character.death_day is not None or group is None
                or day - character.birth_day < LIFESPAN_DAYS):
            continue
        event = record_event(
            world, "character_lifetime_ended",
            f"{character.name} chegou ao fim da vida; nenhum bem, cargo ou coluna mudou de dono.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("character", character.id, "death_day", None, day),
                    _delta("population_group", group.id, "count", group.count, group.count - 1)),
            cause_ids=_causes(group.last_event_id))
        world.society.remove_people(group.id, 1, day=day, character_ids=(character.id,))
        world.society.population[group.id] = world.society.population[group.id].model_copy(
            update={"last_event_id": event.id})
        ended.append(character.id)
    return tuple(ended)


def apply_monthly_mortality(world, available=None):
    """Run both laws on this cycle's real state, then let revocations follow."""
    removed = _deprivation_deaths(world, available)
    ended = _lifetime_deaths(world)
    if removed or ended:
        # Death invalidates a tactical command immediately; every other
        # dependency (rite, apprenticeship, research, activity) already fails
        # or cancels through its own dated resolution.
        revoke_invalid_detachment_commands(world)
    return removed, ended


__all__ = ["DEPRIVATION_PERMILLE", "LIFESPAN_DAYS", "apply_monthly_mortality"]

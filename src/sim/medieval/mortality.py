"""Two material ends of a life, both engine-owned laws and neither a story.

Sustained deprivation kills: ``consume_monthly`` already accumulates the real
shortfall in ``SettlementNeeds.health``, dropping it by this cycle's pressure
and raising it when the ration is met. Only when that accumulator sits at its
floor *and* the same cycle still recorded a deficit does a settlement lose
people, by a fixed permille of each named cohort's currently available,
receipt-recorded deficit. Nothing is drawn at random, nobody is chosen, and a
single bad month kills no one.

A named person also reaches the end of a lifetime. That fact releases nothing
but the person: assets, offices, columns and administrations keep their owners,
and the existing revocations decide what stops working.
"""

from src.classes.event import FactKind

from .economy import _causes, _delta
from .events import _recorded_event, record_event
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
    """Apply deprivation only to cohorts named as unmet by the same receipt."""
    day = world.clock.absolute_day
    plans = []
    # Validate every floor/deficit receipt before appending any death event or
    # changing a population count.  A stale or malformed causal reading must
    # fail closed rather than partially applying this monthly law.
    for need_id in sorted(world.economy.needs):
        need = world.economy.needs[need_id]
        if need.health > HEALTH_FLOOR or need.missing_food <= 0:
            continue
        receipt = _recorded_event(world.events, need.last_event_id)
        payload = receipt.causal_payload if receipt is not None else None
        subsistence = payload.get("subsistence") if isinstance(payload, dict) else None
        group_ids = subsistence.get("household_group_ids") if isinstance(subsistence, dict) else None
        unmet = subsistence.get("unmet_by_group") if isinstance(subsistence, dict) else None
        if (receipt is None or receipt.event_type != "subsistence_resolved"
                or receipt.fact_kind is not FactKind.STATE_TRANSITION
                or receipt.day != day
                or not isinstance(subsistence, dict)
                or subsistence.get("settlement_id") != need_id
                or subsistence.get("missing_food") != need.missing_food
                or not isinstance(group_ids, list)
                or any(not isinstance(group_id, str) for group_id in group_ids)
                or len(group_ids) != len(set(group_ids))
                or not isinstance(unmet, dict)):
            raise ValueError("deprivation requires the current canonical subsistence receipt")
        if (any(group_id not in world.society.population
                or world.society.population[group_id].settlement_id != need_id
                for group_id in group_ids)
                or any(group_id not in group_ids or type(amount) is not int or amount <= 0
                       for group_id, amount in unmet.items())
                or sum(unmet.values()) != need.missing_food):
            raise ValueError("deprivation receipt has an invalid unmet_by_group payload")
        groups = [world.society.population[group_id] for group_id in group_ids]
        plans.append((need, receipt, groups, unmet))
    removed = {}
    for need, receipt, groups, unmet in plans:
        need_id = need.id
        losses = []
        for group in sorted(groups, key=lambda item: item.id):
            # The people who starve are exactly the ones the same cycle counted
            # as eating from this settlement, never those away with a column,
            # a journey or another settlement's ration.
            deficit = unmet.get(group.id, 0)
            counted = min(max(0, world.society.available_count(group.id)), deficit)
            # Current availability may exclude reserved people; cap anonymous
            # losses against that same pool so named residents and reservations
            # cannot be consumed by an aggregate cohort decrement.
            anonymous = max(0, counted - _living_named(world, group.id))
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
            cause_ids=_causes(receipt.id, *(group.last_event_id for group, _ in losses)),
            causal_payload={
                "source_subsistence_event_id": receipt.id,
                "settlement_id": need_id,
                "losses_by_group": {
                    group.id: {"exposed": min(max(0, world.society.available_count(group.id)), unmet[group.id]),
                               "deficit": unmet[group.id], "loss": count}
                    for group, count in losses
                },
            })
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

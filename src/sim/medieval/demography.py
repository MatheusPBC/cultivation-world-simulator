"""New residents and the day they become working age; both engine-owned laws.

A fed settlement with room to house people grows, by a fixed permille of the
adults its own subsistence cycle actually counted. Newborns join the local
``dependent`` cohort, where the existing rules already make them eat and make
them useless for work: no recipe employs a dependent, so growth in plenty is
what produces the shortfall of a later cycle, with nobody writing that.

Becoming working age is dated, not a monthly fraction: each batch carries its
own maturity day and, when it comes, only the people who actually remain are
moved. Nothing is drawn at random, no person is named and no family exists.
"""

from src.classes.event import FactKind
from src.classes.society.demography import MATURITY_DAYS, BirthCohort
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _causes, _delta
from .events import record_event

# Per thirty-day cycle, applied to the counted adults of one people.
BIRTH_PERMILLE = 3
HEALTH_THRESHOLD = 800
DEPENDENT = "dependent"
MATURE_OCCUPATION = "farmer"
MATURITY_KIND = "generation_maturity"


def _living_named(world, group_id):
    return sum(1 for item in world.society.characters.values()
               if item.death_day is None and item.population_group_id == group_id)


def _adult_base(world, settlement_id, people):
    """Residents of this people that this cycle counted, minus the dependents."""
    return sum(max(0, world.society.available_count(group.id))
               for group in world.society.population.values()
               if group.settlement_id == settlement_id and group.people == people
               and group.occupation != DEPENDENT)


def _peoples(world, settlement_id):
    return sorted({group.people for group in world.society.population.values()
                   if group.settlement_id == settlement_id})


def apply_monthly_births(world):
    """Deterministic growth where this cycle was fed and there is room."""
    day = world.clock.absolute_day
    born = {}
    for settlement_id in sorted(world.economy.needs):
        need = world.economy.needs[settlement_id]
        settlement = world.society.settlements[settlement_id]
        if need.missing_food > 0 or need.health < HEALTH_THRESHOLD:
            continue
        for people in _peoples(world, settlement_id):
            room = settlement.housing_capacity - world.society.population_at(settlement_id)
            base = _adult_base(world, settlement_id, people)
            count = min(base * BIRTH_PERMILLE // 1000, max(0, room))
            if count <= 0:
                continue
            adults = tuple(group for group in sorted(world.society.population.values(), key=lambda g: g.id)
                           if group.settlement_id == settlement_id and group.people == people
                           and group.occupation != DEPENDENT)
            existing = next((group for group in world.society.population.values()
                             if (group.settlement_id, group.people, group.occupation)
                             == (settlement_id, people, DEPENDENT)), None)
            before = existing.count if existing is not None else 0
            identity = f"birth-cohort:event:{len(world.events) + 1}:{settlement_id}:{people}"
            group_id = existing.id if existing is not None else f"pop:{settlement_id}:{people}:{DEPENDENT}"
            event = record_event(
                world, "settlement_births",
                f"{settlement.name}: {count} novos habitantes nasceram num ciclo alimentado.",
                fact_kind=FactKind.STATE_TRANSITION,
                deltas=(_delta("population_group", group_id, "count", before, before + count),
                        _delta("birth_cohort", identity, "count", None, count)),
                cause_ids=_causes(need.last_event_id, *(group.last_event_id for group in adults)))
            world.society.add_people(settlement_id, people, DEPENDENT, count)
            world.society.population[group_id] = world.society.population[group_id].model_copy(
                update={"last_event_id": event.id})
            cohort = BirthCohort(id=identity, settlement_id=settlement_id, people=people, count=count,
                                 born_day=day, matures_day=day + MATURITY_DAYS,
                                 birth_event_id=event.id, last_event_id=event.id)
            world.society.birth_cohorts[cohort.id] = cohort
            world.agenda.schedule(ScheduledSituation(cohort.id, MATURITY_KIND, cohort.matures_day))
            born[cohort.id] = count
    return born


def _dependent_group(world, settlement_id, people):
    return next((group for group in world.society.population.values()
                 if (group.settlement_id, group.people, group.occupation)
                 == (settlement_id, people, DEPENDENT)), None)


def resolve_generation_maturity(world, situations):
    """Only whoever really remains becomes working age; nobody is invented."""
    for situation in sorted(situations, key=lambda item: item.id):
        cohort = world.society.birth_cohorts.get(situation.id)
        if (situation.kind != MATURITY_KIND or cohort is None or cohort.stage != "pending"
                or cohort.matures_day != world.clock.absolute_day):
            raise ValueError("unknown or inconsistent dated generation")
        source = _dependent_group(world, cohort.settlement_id, cohort.people)
        available = 0 if source is None else max(
            0, min(source.count - _living_named(world, source.id), world.society.available_count(source.id)))
        moved = min(cohort.count, available)
        deltas = [_delta("birth_cohort", cohort.id, "stage", "pending", "matured"),
                  _delta("birth_cohort", cohort.id, "matured_count", cohort.count, moved)]
        target_id = f"pop:{cohort.settlement_id}:{cohort.people}:{MATURE_OCCUPATION}"
        if moved > 0:
            target = world.society.population.get(target_id)
            deltas.append(_delta("population_group", source.id, "count", source.count, source.count - moved))
            deltas.append(_delta("population_group", target_id, "count",
                                 target.count if target else 0, (target.count if target else 0) + moved))
        settlement = world.society.settlements[cohort.settlement_id]
        event = record_event(
            world, "generation_matured",
            f"{settlement.name}: {moved} de {cohort.count} habitantes alcançaram a idade de trabalho.",
            fact_kind=FactKind.STATE_TRANSITION, deltas=tuple(deltas),
            cause_ids=_causes(cohort.birth_event_id, cohort.last_event_id,
                              source.last_event_id if source is not None else None))
        if moved > 0:
            world.society.transfer_people(source.id, cohort.settlement_id, MATURE_OCCUPATION, moved)
            for group_id in (source.id, target_id):
                world.society.population[group_id] = world.society.population[group_id].model_copy(
                    update={"last_event_id": event.id})
        world.society.birth_cohorts[cohort.id] = cohort.model_copy(
            update={"stage": "matured", "last_event_id": event.id})


__all__ = ["BIRTH_PERMILLE", "HEALTH_THRESHOLD", "MATURITY_KIND", "apply_monthly_births",
           "resolve_generation_maturity"]

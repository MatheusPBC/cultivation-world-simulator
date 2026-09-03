from __future__ import annotations

import random

from src.classes.core.dynasty import Dynasty, dynasties_by_id
from src.classes.gender import Gender
from src.classes.race import get_race
from src.utils.df import game_configs, get_str


def _pick_dynasty_template() -> Dynasty:
    templates = list(dynasties_by_id.values())
    if not templates:
        raise ValueError("No dynasty templates loaded from dynasty.csv")

    weights = [max(0.0, float(getattr(item, "weight", 1.0) or 1.0)) for item in templates]
    if not any(weights):
        return random.choice(templates)
    return random.choices(templates, weights=weights, k=1)[0]


def _pick_royal_surname() -> str:
    surname_rows = game_configs.get("last_name", []) or []
    candidates = [
        get_str(row, "last_name")
        for row in surname_rows
        if get_str(row, "last_name") and not get_str(row, "sect_id")
    ]
    if not candidates:
        raise ValueError("No royal surname candidates loaded from last_name.csv")
    return random.choice(candidates)


def _pick_given_name(gender: Gender) -> str:
    given_name_rows = game_configs.get("given_name", []) or []
    candidates = [
        get_str(row, "given_name")
        for row in given_name_rows
        if get_str(row, "given_name")
        and not get_str(row, "sect_id")
        and get_str(row, "gender") == ("1" if gender is Gender.MALE else "0")
    ]
    if not candidates:
        raise ValueError("No emperor given-name candidates loaded from given_name.csv")
    return random.choice(candidates)


def _build_royal_avatar(world, dynasty: Dynasty, *, gender: Gender, age_years: int):
    """Create one royal through the same planner/factory path as other avatars."""
    from src.classes.age import Age
    from src.sim.avatar_init.factory import AvatarFactory
    from src.sim.avatar_init.planning import MortalPlanner

    surname = str(getattr(dynasty, "royal_surname", "") or "")
    if not surname:
        raise ValueError("Dynasty royal surname is required before generating emperor")

    name = f"{surname}{_pick_given_name(gender)}"
    age = Age(age_years)
    plan = MortalPlanner.plan(world, name=name, age=age, level=1, allow_relations=False)
    plan.gender = gender
    plan.race = get_race("human")
    plan.sect = None
    plan.surname = surname
    avatar = AvatarFactory.build_from_plan(world, world.month_stamp, name=name, age=age, plan=plan, attach_relations=False)
    world.avatar_manager.register_avatar(avatar)
    return avatar


def generate_emperor_avatar(world, dynasty: Dynasty):
    """Create an initial emperor, consort, and two adult children."""
    from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR

    emperor = _build_royal_avatar(world, dynasty, gender=Gender.MALE, age_years=random.randint(35, 55))
    consort = _build_royal_avatar(world, dynasty, gender=Gender.FEMALE, age_years=random.randint(30, 50))
    emperor.become_lovers_with(consort)
    children = [
        _build_royal_avatar(world, dynasty, gender=Gender.MALE, age_years=random.randint(18, 28)),
        _build_royal_avatar(world, dynasty, gender=Gender.FEMALE, age_years=random.randint(18, 28)),
    ]
    for child in children:
        emperor.acknowledge_child(child)
        consort.acknowledge_child(child)

    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    emperor.court_reputation = max(700, int(getattr(emperor, "court_reputation", 0)))
    dynasty.current_emperor_id = str(emperor.id)
    dynasty.add_royal_house_member(emperor.id, blood=True)
    dynasty.add_royal_house_member(consort.id)
    for child in children:
        dynasty.add_royal_house_member(child.id, blood=True)
    return emperor


def generate_dynasty() -> Dynasty:
    template = _pick_dynasty_template()
    royal_surname = _pick_royal_surname()
    return template.create_runtime(royal_surname=royal_surname)

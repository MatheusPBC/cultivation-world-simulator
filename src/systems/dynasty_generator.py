from __future__ import annotations

import random

from src.classes.core.dynasty import Dynasty, dynasties_by_id
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


def _pick_emperor_given_name() -> str:
    given_name_rows = game_configs.get("given_name", []) or []
    candidates = [
        get_str(row, "given_name")
        for row in given_name_rows
        if get_str(row, "given_name") and not get_str(row, "sect_id") and get_str(row, "gender") == "1"
    ]
    if not candidates:
        raise ValueError("No emperor given-name candidates loaded from given_name.csv")
    return random.choice(candidates)


def generate_emperor_avatar(world, dynasty: Dynasty):
    """Create the sovereign through the normal Avatar lifecycle."""
    surname = str(getattr(dynasty, "royal_surname", "") or "")
    if not surname:
        raise ValueError("Dynasty royal surname is required before generating emperor")

    from src.classes.age import Age
    from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR
    from src.sim.avatar_init import create_random_mortal
    age_years = random.randint(30, 60)
    given_name = _pick_emperor_given_name()
    avatar = create_random_mortal(world, world.month_stamp, f"{surname}{given_name}", Age(age_years), level=1)
    avatar.official_rank = OFFICIAL_GRAND_COUNCILOR
    avatar.court_reputation = max(700, int(getattr(avatar, "court_reputation", 0)))
    world.avatar_manager.register_avatar(avatar)
    dynasty.current_emperor_id = str(avatar.id)
    return avatar


def generate_dynasty() -> Dynasty:
    template = _pick_dynasty_template()
    royal_surname = _pick_royal_surname()
    return template.create_runtime(royal_surname=royal_surname)

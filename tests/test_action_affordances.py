"""
Player/API-facing affordances -- a separate builder from get_action_infos /
get_action_infos_str, which must stay prompt-shrinking (see
docs/specs/causal-world-kernel.md section 5.5 and task-4-brief.md).
"""
from src.classes.action.breakthrough import Breakthrough
from src.classes.actions import build_action_affordances, get_action_infos_str, ALL_ACTUAL_ACTION_NAMES
from src.systems.cultivation import CultivationProgress, REALM_ORDER, LEVELS_PER_REALM


def test_build_action_affordances_lists_every_actual_action(dummy_avatar):
    affordances = build_action_affordances(dummy_avatar)

    names = {entry["action_name"] for entry in affordances}
    assert names == set(ALL_ACTUAL_ACTION_NAMES)


def test_build_action_affordances_marks_unavailable_action_with_reason(dummy_avatar):
    dummy_avatar.cultivation_progress = CultivationProgress(level=15, exp=0)

    affordances = build_action_affordances(dummy_avatar)
    breakthrough = next(e for e in affordances if e["action_name"] == "Breakthrough")

    assert breakthrough["available"] is False
    assert breakthrough["require"] == Breakthrough.get_requirements()
    assert breakthrough["require"] != ""


def test_build_action_affordances_marks_available_action(dummy_avatar):
    dummy_avatar.cultivation_progress = CultivationProgress(level=30, exp=0)

    affordances = build_action_affordances(dummy_avatar)
    breakthrough = next(e for e in affordances if e["action_name"] == "Breakthrough")

    assert breakthrough["available"] is True


def test_build_action_affordances_tolerates_empty_requirement_text(dummy_avatar):
    """Actions without REQUIREMENTS_ID must not invent a reason (spec 5.5)."""
    affordances = build_action_affordances(dummy_avatar)

    assert all("require" in entry for entry in affordances)


def test_action_infos_str_is_byte_identical_with_affordances_present(dummy_avatar):
    """Adding build_action_affordances must not perturb the prompt-facing path
    at all -- get_action_infos_str still excludes impossible actions and its
    output text is unaffected by the new builder existing."""
    dummy_avatar.cultivation_progress = CultivationProgress(level=15, exp=0)
    before = get_action_infos_str(dummy_avatar)

    # Calling the new affordance builder must have no side effect on the
    # prompt path.
    build_action_affordances(dummy_avatar)

    after = get_action_infos_str(dummy_avatar)
    assert before == after
    assert "Breakthrough" not in before


def test_action_infos_str_still_excludes_impossible_actions(dummy_avatar):
    max_level = len(REALM_ORDER) * LEVELS_PER_REALM
    dummy_avatar.cultivation_progress = CultivationProgress(level=max_level, exp=0)

    assert "Breakthrough" not in get_action_infos_str(dummy_avatar)

    affordances = build_action_affordances(dummy_avatar)
    breakthrough = next(e for e in affordances if e["action_name"] == "Breakthrough")
    assert breakthrough["available"] is False

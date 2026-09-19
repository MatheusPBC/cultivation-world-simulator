"""Monthly owner turn for standing garrisons.

Force-contact reviews are still responsible for bilateral responses.  A
garrison's own institution, however, must be able to review withdrawal or
rotation even when no rival is currently visible.  This adapter only exposes
the existing ``force.garrison_options`` and delegates execution back to that
owner; it creates no second military state.
"""

from src.classes.mechanical_language import EntityRef

from .force import (establish_garrison,
                    garrison_options, rotate_garrison, withdraw_garrison)
from .institutional_decision_turn import DiscretionaryAdapter


def garrison_actors(world):
    # Organizations may hold a military office too.  The monthly boundary
    # must discover the same canonical affordance for them instead of
    # silently restricting garrison management to polities.
    candidates = {
        EntityRef("polity", identity) for identity in world.society.polities
    }
    candidates.update(office.institution_ref for office in world.authority.offices.values()
                      if office.institution_ref.kind == "organization")
    return tuple(sorted(
        {option.actor_ref for actor in candidates for option in garrison_options(world, actor)},
        key=lambda ref: (ref.kind, ref.id)))


def _situation(world, actor, options):
    return {
        "you_are": actor.to_dict(),
        "garrisons": [
            {"id": option.id, "settlement_id": option.settlement_id,
             "detachment_id": option.detachment_id, "kind": option.kind,
             "daily_wage": option.daily_wage}
            for option in options
        ],
        "today": world.clock.absolute_day,
    }


def _label(option):
    if option.kind == "rotate":
        return "Rotacionar a coluna da guarnição por uma presença própria abastecida."
    if option.kind == "withdraw":
        return "Retirar voluntariamente o dever da guarnição."
    return "Estabelecer uma guarnição paga para sustentar a ocupação."


def _causes(world, option):
    detachment = world.society.detachments.get(option.detachment_id)
    causes = [item.last_event_id for item in (detachment,) if item is not None and item.last_event_id]
    existing = world.society.garrisons.get(f"garrison:{option.detachment_id}")
    if existing is not None and existing.last_event_id:
        causes.append(existing.last_event_id)
    replacement_id = getattr(option, "replacement_detachment_id", None)
    replacement = world.society.detachments.get(replacement_id) if replacement_id else None
    if replacement is not None and replacement.last_event_id:
        causes.append(replacement.last_event_id)
    return tuple(dict.fromkeys(causes))


def _execute(world, actor, option_id, decision_event_id):
    option = next((item for item in garrison_options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("garrison option is stale or unknown")
    if option.kind == "rotate":
        return rotate_garrison(world, actor, option.id, decision_event_id)
    if option.kind == "withdraw":
        return withdraw_garrison(world, actor, option.id, decision_event_id)
    return establish_garrison(world, actor, option.id, decision_event_id)


def garrison_adapters():
    return (DiscretionaryAdapter(
        name="garrison_management", family="campaign",
        options_fn=garrison_options, label_fn=_label, causes_fn=_causes,
        execute_fn=_execute, situation_fn=_situation),)


__all__ = ["garrison_actors", "garrison_adapters"]

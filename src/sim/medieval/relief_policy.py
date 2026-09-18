from src.classes.mechanical_language import EntityRef

from .institutional_decision_turn import DiscretionaryAdapter
from .relief import distribute_relief, relief_settlement_options


def _options(world, actor):
    return relief_settlement_options(world, actor.id) if actor.kind == "polity" else ()


def _situation(world, actor, options):
    return {
        "you_are": actor.to_dict(),
        "settlement_reports": [
            {"settlement_id": report.settlement_id, "missing_food": report.missing_food,
             "health": report.health, "unrest": report.unrest,
             "observed_day": report.observed_day, "event_id": report.event_id}
            for report in world.knowledge.settlements_for_actor(actor) if report.publisher_ref == actor
        ],
        "today": world.clock.absolute_day,
    }


def _causes(world, option):
    report = world.knowledge.settlement_reports.get(option.report_id)
    return (report.event_id,) if report is not None else ()


def relief_actors(world):
    return [EntityRef("polity", polity_id) for polity_id in sorted(world.society.polities)
            if relief_settlement_options(world, polity_id)]


def relief_adapters(on_executed=None):
    def _execute(world, actor, option_id, decision_event_id):
        distribute_relief(world, option_id, decision_event_id=decision_event_id)
        if on_executed is not None:
            on_executed()

    def _label(option):
        return (f"Distribuir {option.quantity} rações de ajuda gratuita ao assentamento "
                f"{option.settlement_id} a partir do próprio estoque.")

    return (DiscretionaryAdapter(
        name="relief", family="relief", options_fn=_options,
        label_fn=_label,
        causes_fn=_causes, execute_fn=_execute,
        claim_fn=lambda option: ("relief", option.polity_id), situation_fn=_situation),)

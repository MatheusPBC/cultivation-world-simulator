from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef

from .institutional_decision_turn import DiscretionaryAdapter
from .actor_dossier import _latest_food_affordability, _own_production_readings
from .events import record_event
from .relief import (distribute_relief, execute_relief_transfer,
                     relief_settlement_options, relief_transfer_options)


# Offline runs need a declared safety policy, not an invisible material
# transfer.  Keep the floor aligned with the public food-demand cap: a tiny
# one-ration accounting remainder is not enough to make an institution spend
# its one bounded fallback action, while a real collective shortfall is.
FALLBACK_MIN_SHORTFALL = 20


def _options(world, actor):
    return relief_settlement_options(world, actor.id) if actor.kind == "polity" else ()


def _transfer_options(world, actor):
    return relief_transfer_options(world, actor) if actor.kind == "polity" else ()


def _situation(world, actor, options):
    return {
        "you_are": actor.to_dict(),
        "own_production_readings": _own_production_readings(world, actor),
        "settlement_reports": [
            {"settlement_id": report.settlement_id, "missing_food": report.missing_food,
             "health": report.health, "unrest": report.unrest,
             "observed_day": report.observed_day, "event_id": report.event_id,
             **_latest_food_affordability(world, report)}
            for report in world.knowledge.settlements_for_actor(actor) if report.publisher_ref == actor
        ],
        "today": world.clock.absolute_day,
    }


def _transfer_situation(world, actor, options):
    return {
        "you_are": actor.to_dict(),
        "transfers": [{"id": option.id,
                       "destination_settlement_id": option.destination_settlement_id,
                       "quantity": option.quantity,
                       "route_count": len(option.route_ids)}
                      for option in options],
        "today": world.clock.absolute_day,
    }


def _causes(world, option):
    report = world.knowledge.settlement_reports.get(option.report_id)
    if report is None:
        return ()
    affordability = _latest_food_affordability(world, report)
    return tuple(dict.fromkeys(item for item in (report.event_id, affordability["affordability_event_id"])
                               if item))


def relief_actors(world):
    return [EntityRef("polity", polity_id) for polity_id in sorted(world.society.polities)
            if relief_settlement_options(world, polity_id)
            or relief_transfer_options(world, EntityRef("polity", polity_id))]


def _transfer_causes(world, option):
    destination = world.knowledge.settlement_reports.get(option.destination_report_id)
    causes = [option.source_inventory_event_id]
    if destination is not None:
        causes.append(destination.event_id)
        affordability = _latest_food_affordability(world, destination)
        if affordability["affordability_event_id"]:
            causes.append(affordability["affordability_event_id"])
    for route_id in option.route_ids:
        report = world.knowledge.route_report(option.actor_ref, route_id)
        fiscal = world.knowledge.fiscal_route_report(option.actor_ref, route_id)
        causes.extend(item.event_id for item in (report, fiscal) if item is not None)
    return tuple(dict.fromkeys(causes))


def review_relief_fallback(world, *, excluded_actors=()):
    """Choose at most one urgent local relief act per polity.

    This exists only when the provider is disabled.  It is a named actor
    policy over the normal direct-distribution affordances: it never names a
    stock, quantity or target that the relief owner did not make available,
    and its decision remains a normal causal fact before Economy executes.
    Routed transfer remains a separate, provider-selected choice because it
    depends on a fresh route/fiscal offer at dispatch. A provider-enabled
    world keeps the whole competing menu and receives no fallback choice from
    this function.
    """
    excluded = set(excluded_actors)
    executed = []
    for actor in relief_actors(world):
        if actor in excluded:
            continue
        candidates = []
        for option in relief_settlement_options(world, actor.id):
            report = world.knowledge.settlement_reports.get(option.report_id)
            if report is not None and report.missing_food >= FALLBACK_MIN_SHORTFALL:
                candidates.append((report.missing_food, option.quantity, option.id, option))
        if not candidates:
            continue
        # ``min`` with negative material readings gives descending urgency and
        # coverage while keeping the affordance ID as a stable tie-breaker.
        _, _, _, option = min(candidates, key=lambda item: (-item[0], -item[1], item[2]))
        causes = _causes(world, option)
        action = "relief_distribution_decided"
        content = "A administração escolheu uma distribuição urgente entre as opções de ajuda enumeradas."
        decision = record_event(
            world, action, content, fact_kind=FactKind.DECISION,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            decision=option.decision(), cause_ids=causes)
        executed.append(distribute_relief(world, option.id, decision_event_id=decision.id))
    return tuple(executed)


def relief_adapters(on_executed=None):
    def _execute(world, actor, option_id, decision_event_id):
        distribute_relief(world, option_id, decision_event_id=decision_event_id)
        if on_executed is not None:
            on_executed()

    def _label(option):
        return (f"Distribuir {option.quantity} rações de ajuda gratuita ao assentamento "
                f"{option.settlement_id} a partir do próprio estoque.")

    def _transfer_label(option):
        return (f"Enviar {option.quantity} rações do estoque próprio para "
                f"{option.destination_settlement_id} por uma rota observada.")

    def _execute_transfer(world, actor, option_id, decision_event_id):
        return execute_relief_transfer(world, actor, option_id, decision_event_id)

    return (DiscretionaryAdapter(
        name="relief", family="relief", options_fn=_options,
        label_fn=_label,
        causes_fn=_causes, execute_fn=_execute,
        claim_fn=lambda option: ("relief", option.polity_id), situation_fn=_situation),
        DiscretionaryAdapter(
            name="relief_transfer", family="relief", options_fn=_transfer_options,
            label_fn=_transfer_label, causes_fn=_transfer_causes, execute_fn=_execute_transfer,
            claim_fn=lambda option: ("relief", option.actor_ref.id), situation_fn=_transfer_situation),)

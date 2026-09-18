"""Civil discretionary adapters for the generic InstitutionalDecisionTurn.

A polity under food pressure may see, in the very same prompt, an
engine-owned ``SupplyObjectiveOption`` (execute the current supply plan for
one objective), any currently valid ``AidRequestOption`` for the same
shortage, and any currently valid ``RepairAuthorizationOption`` for a site it
maintains, plus NO_ACTION. None of these expose supplier, quantity, route,
provider, blueprint, stock or account: those stay engine-owned inside their
existing executors. This module introduces no new option type, resource, term
or route, and never relaxes institutional aid's or infrastructure's own
gating (open chain, dated knowledge limits, observation freshness); it only
registers the existing option lists as adapters of ``institutional_decision_
turn.py`` and dispatches the chosen ID to its own, unmodified executor. Causes
given to the provider and recorded on the decision are canonical event IDs
only — the current settlement/site report and the objective's or repair's own
plan/receipt evidence, never a private quantity, stock or route.
"""

from src.classes.mechanical_language import EntityRef

from .diplomacy_policy import schedule_review
from .infrastructure import (REPAIR_AUTHORIZATION_ACTION, current_observation,
                             execute_repair_authorization_option, repair_authorization_options)
from .institutional_aid import aid_request_options, request_institutional_aid
from .institutional_aid_policy import _own_open_chain, _pressured_settlements
from .institutional_decision_turn import (DiscretionaryAdapter,
                                          review_institutional_decision_turn_with_provider)
from .procurement import SUPPLY_OBJECTIVE_ACTION, execute_supply_objective_option, supply_objective_options


def _current_aid_requests(world, actor):
    """Same gate institutional_aid_policy already uses; nothing duplicated here."""
    if actor.kind != "polity":
        return ()
    pressured = _pressured_settlements(world, actor)
    if not pressured:
        return ()
    return tuple(option for option in aid_request_options(world, actor)
                if option.requester_settlement_id in pressured
                and not _own_open_chain(world, actor, option.requester_settlement_id))


def _execute_aid_request(world, actor, option_id, decision_event_id):
    request_institutional_aid(world, actor, option_id, decision_event_id)
    schedule_review(world)


def _supply_causes(world, option):
    objective = world.strategy.objectives[option.objective_id]
    plan = world.strategy.plans.get(f"plan:{option.objective_id}")
    report = world.knowledge.settlement_report(option.actor_ref, objective.settlement_id)
    return tuple(sorted({item for item in
                         (plan.last_event_id if plan else None, report.event_id if report else None) if item}))


def _repair_causes(world, option):
    site = world.map.infrastructure_sites[option.site_id]
    report = current_observation(world, option.actor_ref, option.site_id)
    return tuple(sorted({item for item in
                         (report.event_id if report else None, site.last_event_id) if item}))


def _aid_causes(world, option):
    report = next((item for item in world.knowledge.settlements_for_actor(option.actor_ref)
                  if item.id == option.report_id), None)
    return (report.event_id,) if report else ()


SUPPLY_ADAPTER = DiscretionaryAdapter(
    name="supply_objective", options_fn=supply_objective_options,
    label_fn=lambda option: f"Executar o plano de abastecimento vigente do objetivo {option.objective_id}.",
    causes_fn=_supply_causes, execute_fn=execute_supply_objective_option,
    claim_fn=lambda option: ("objective", option.objective_id))

AID_ADAPTER = DiscretionaryAdapter(
    name="aid_request", options_fn=_current_aid_requests,
    label_fn=lambda option: f"Pedir ajuda alimentar para {option.requester_settlement_id} a {option.provider_ref.id}.",
    causes_fn=_aid_causes, execute_fn=_execute_aid_request)

REPAIR_ADAPTER = DiscretionaryAdapter(
    name="repair_authorization", options_fn=repair_authorization_options,
    label_fn=lambda option: f"Autorizar o reparo da instalação {option.site_id}.",
    causes_fn=_repair_causes, execute_fn=execute_repair_authorization_option,
    claim_fn=lambda option: ("site", option.site_id))

CIVIL_ADAPTERS = (SUPPLY_ADAPTER, AID_ADAPTER, REPAIR_ADAPTER)


def concurrent_civil_options(world, actor):
    """Recompose today's menu; every entry is untouched from its own vertical."""
    if not isinstance(actor, EntityRef) or actor.kind != "polity":
        return ()
    return (*supply_objective_options(world, actor), *_current_aid_requests(world, actor),
            *repair_authorization_options(world, actor))


async def review_concurrent_civil_decision_with_provider(world):
    """One review per polity per boundary; no persisted planner or menu state."""
    claims, covered_actors = await review_institutional_decision_turn_with_provider(world, CIVIL_ADAPTERS)
    return claims.get("objective", set()), claims.get("site", set()), covered_actors

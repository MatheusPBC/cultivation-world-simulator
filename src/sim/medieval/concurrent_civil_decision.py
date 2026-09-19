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
                             execute_repair_authorization_option, repair_authorization_options,
                             site_reactivation_adapters, site_reactivation_options)
from .institutional_aid import (
    aid_fulfillment_options,
    aid_remediation_options,
    aid_request_options,
    aid_response_options,
    fulfill_institutional_aid,
    remediate_institutional_aid,
    request_institutional_aid,
    respond_institutional_aid,
)
from .institutional_aid_policy import _known_before_today
from .institutional_aid_policy import _own_open_chain, _pressured_settlements
from .institutional_decision_turn import (DiscretionaryAdapter,
                                          review_institutional_decision_turn_with_provider)
from .procurement import (SUPPLY_OBJECTIVE_ACTION, execute_market_purchase_option,
                          execute_supply_objective_option, market_purchase_options,
                          supply_objective_options)
from .freight_recovery import (blocking_routes, execute_freight_recovery,
                               freight_recovery_options)
from .purchase_recovery import (purchase_recovery_request_options,
                                purchase_recovery_response_options,
                                request_purchase_recovery, respond_purchase_recovery)
from .expansion import expansion_adapters, expansion_options
from .research_policy import research_adapters, research_options
from .siege_campaign import (siege_campaign_adapters, siege_campaign_options,
                              siege_campaign_withdrawal_options,
                              siege_occupation_options)
from .territorial_control import territorial_control_options
from .administration_concession import (
    administration_concession_offer_options,
    administration_concession_response_options,
    administration_transfer_fulfillment_options,
    fulfill_administration_transfer,
    offer_administration_concession,
    respond_administration_concession,
)
from .campaign_ceasefire import (
    campaign_ceasefire_fulfillment_options,
    campaign_ceasefire_offer_options,
    campaign_ceasefire_response_options,
    fulfill_campaign_ceasefire,
    offer_campaign_ceasefire,
    respond_campaign_ceasefire,
)
from .relief import relief_settlement_options, relief_transfer_options
from .relief_policy import relief_adapters


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


def _current_aid_responses(world, actor):
    """Responses whose notice was known before this monthly boundary.

    The dated aid review keeps the same knowledge rule.  Reusing it here makes
    the composed menu a true replacement for the monthly provider consultation
    instead of exposing a same-day notice that the actor could not yet use.
    """
    return tuple(
        option for option in aid_response_options(world, actor)
        if _known_before_today(world, actor, option.request_event_id)
    )


def _aid_response_causes(world, option):
    return (option.request_event_id,)


def _aid_obligation_causes(world, option):
    obligation = world.relations.obligations.get(option.obligation_id)
    return (obligation.last_event_id,) if obligation is not None else ()


def _execute_aid_response(world, actor, option_id, decision_event_id):
    option = next((item for item in _current_aid_responses(world, actor) if item.id == option_id), None)
    respond_institutional_aid(world, actor, option_id, decision_event_id)
    if option is not None and option.kind == "accept":
        schedule_review(world)


def _execute_aid_fulfillment(world, actor, option_id, decision_event_id):
    fulfill_institutional_aid(world, actor, option_id, decision_event_id)


def _execute_aid_remediation(world, actor, option_id, decision_event_id):
    remediate_institutional_aid(world, actor, option_id, decision_event_id)


def _supply_causes(world, option):
    objective = world.strategy.objectives[option.objective_id]
    plan = world.strategy.plans.get(f"plan:{option.objective_id}")
    report = world.knowledge.settlement_report(option.actor_ref, objective.settlement_id)
    return tuple(sorted({item for item in
                         (plan.last_event_id if plan else None, report.event_id if report else None) if item}))


def _market_purchase_causes(world, option):
    """Expose only the dated offer/route evidence behind a market choice."""
    report = world.knowledge.reports.get(option.offer_id)
    causes = [report.event_id] if report is not None else []
    for route_id in option.route_ids:
        physical = world.knowledge.route_report(option.actor_ref, route_id)
        fiscal = world.knowledge.fiscal_route_report(option.actor_ref, route_id)
        causes.extend(item.event_id for item in (physical, fiscal) if item is not None)
    return tuple(sorted(set(causes)))


def _repair_causes(world, option):
    site = world.map.infrastructure_sites[option.site_id]
    report = current_observation(world, option.actor_ref, option.site_id)
    return tuple(sorted({item for item in
                         (report.event_id if report else None, site.last_event_id) if item}))


def _aid_causes(world, option):
    report = next((item for item in world.knowledge.settlements_for_actor(option.actor_ref)
                  if item.id == option.report_id), None)
    return (report.event_id,) if report else ()


def _supply_situation(world, actor, options):
    """Public, dated context shared by supply and market affordances.

    Option objects retain owner-private terms for executor revalidation, but
    those terms are not actor-facing. The provider receives only the actor's
    own settlement reports, public settlement/resource identities and known
    route topology. Quantities, prices, supplier handles, stock IDs, account
    IDs and objective IDs stay behind the owner boundary.
    """
    reports = tuple(sorted(
        ({"settlement_id": report.settlement_id,
          "missing_food": report.missing_food,
          "health": report.health,
          "unrest": report.unrest,
          "observed_day": report.observed_day}
         for report in world.knowledge.settlements_for_actor(actor)),
        key=lambda item: item["settlement_id"]))
    opportunities = []
    for index, option in enumerate(sorted(options, key=lambda item: item.id)):
        objective = world.strategy.objectives.get(getattr(option, "objective_id", None))
        if objective is None:
            continue
        opportunity = {
            "choice_index": index,
            "action": getattr(option, "decision", lambda: {})().get("action"),
            "settlement_id": objective.settlement_id,
            "resource_id": objective.resource_id,
            "kind": objective.kind,
        }
        route_ids = getattr(option, "route_ids", ())
        if route_ids:
            opportunity["known_route_ids"] = list(route_ids)
            # Route traffic is an aggregate, dated public observation.  The
            # provider may compare alternatives without learning which order,
            # stock or institution produced the flow.
            opportunity["route_readings"] = [
                {"route_id": report.route_id,
                 "operational_capacity": report.operational_capacity,
                 "daily_flow_bulk": report.daily_flow_bulk,
                 "travel_days": report.travel_days,
                 "observed_day": report.observed_day,
                 "event_id": report.event_id}
                for report in (world.knowledge.route_report(actor, route_id) for route_id in route_ids)
                if report is not None
            ]
        source_id = getattr(option, "source_id", None)
        report_id = getattr(option, "offer_id", None)
        source = world.economy.stocks.get(source_id) if source_id else None
        report = world.knowledge.reports.get(report_id) if report_id else None
        if source is not None:
            opportunity["source_settlement_id"] = source.location_id
        if report is not None:
            # The quote is a dated public offer already present in the actor's
            # knowledge. Do not copy its quantity: the executable amount may
            # be capped by private buyer funds and is recomputed by Economy.
            opportunity["unit_price"] = report.unit_price
            opportunity["quote_day"] = report.quote_day
        market = world.economy.markets.get(objective.settlement_id)
        if market is not None:
            # These are settlement-level public readings, not an inventory
            # disclosure. They let the institution weigh a known opportunity
            # against local pressure while the owner still recomputes every
            # material term at execution.
            opportunity["market_readings"] = {
                "settlement_id": market.id,
                "updated_day": market.updated_day,
                "observed_supply": dict(market.observed_supply),
                "observed_demand": dict(market.observed_demand),
            }
        opportunities.append(opportunity)
    return {"today": world.clock.absolute_day,
            "settlement_reports": reports,
            "opportunities": tuple(opportunities)}


SUPPLY_ADAPTER = DiscretionaryAdapter(
    name="supply_objective", options_fn=supply_objective_options,
    label_fn=lambda option: (
        "Executar o abastecimento disponível para um assentamento pressionado."),
    causes_fn=_supply_causes, execute_fn=execute_supply_objective_option,
    claim_fn=lambda option: ("objective", option.objective_id),
    family="supply", situation_fn=_supply_situation)

MARKET_PURCHASE_ADAPTER = DiscretionaryAdapter(
    name="market_purchase", options_fn=market_purchase_options,
    label_fn=lambda option: (
        f"Comprar {option.resource_id} por uma rota conhecida: "
        f"{' > '.join(option.route_ids)}."),
    causes_fn=_market_purchase_causes,
    execute_fn=execute_market_purchase_option,
    claim_fn=lambda option: ("objective", option.objective_id),
    family="supply", situation_fn=_supply_situation)

AID_ADAPTER = DiscretionaryAdapter(
    name="aid_request", options_fn=_current_aid_requests,
    label_fn=lambda option: f"Pedir ajuda alimentar para {option.requester_settlement_id} a {option.provider_ref.id}.",
    causes_fn=_aid_causes, execute_fn=_execute_aid_request)

AID_RESPONSE_ADAPTER = DiscretionaryAdapter(
    name="aid_response", options_fn=_current_aid_responses,
    label_fn=lambda option: (
        f"{'Aceitar' if option.kind == 'accept' else 'Recusar'} o pedido de ajuda "
        f"de {option.requester_ref.id}."),
    causes_fn=_aid_response_causes, execute_fn=_execute_aid_response,
    family="institutional_aid")

AID_FULFILLMENT_ADAPTER = DiscretionaryAdapter(
    name="aid_fulfillment", options_fn=aid_fulfillment_options,
    label_fn=lambda option: (
        f"Cumprir a ajuda acordada ({option.quantity} {option.resource_id})."),
    causes_fn=_aid_obligation_causes, execute_fn=_execute_aid_fulfillment,
    family="institutional_aid")

AID_REMEDIATION_ADAPTER = DiscretionaryAdapter(
    name="aid_remediation", options_fn=aid_remediation_options,
    label_fn=lambda option: (
        f"Reparar a ajuda descumprida ({option.quantity} {option.resource_id})."),
    causes_fn=lambda world, option: (option.breach_event_id,),
    execute_fn=_execute_aid_remediation, family="institutional_aid")

REPAIR_ADAPTER = DiscretionaryAdapter(
    name="repair_authorization", options_fn=repair_authorization_options,
    label_fn=lambda option: f"Autorizar o reparo da instalação {option.site_id}.",
    causes_fn=_repair_causes, execute_fn=execute_repair_authorization_option,
    claim_fn=lambda option: ("site", option.site_id))

SITE_REACTIVATION_ADAPTER = site_reactivation_adapters()[0]


def _campaign_ceasefire_causes(world, option):
    campaign_id = getattr(option, "campaign_id", None)
    campaign = world.society.siege_campaigns.get(campaign_id) if campaign_id else None
    proposal_id = getattr(option, "proposal_id", None)
    proposal = world.relations.proposals.get(proposal_id) if proposal_id else None
    return tuple(item for item in (
        campaign.last_event_id if campaign else None,
        proposal.last_event_id if proposal else None,
    ) if item)


CAMPAIGN_CEASEFIRE_OFFER_ADAPTER = DiscretionaryAdapter(
    name="campaign_ceasefire_offer", options_fn=campaign_ceasefire_offer_options,
    label_fn=lambda option: (
        f"Propor {'cessar-fogo mútuo' if option.kind == 'mutual' else 'retirada própria'} na campanha {option.campaign_id}."),
    causes_fn=_campaign_ceasefire_causes, execute_fn=offer_campaign_ceasefire,
    family="campaign")

CAMPAIGN_CEASEFIRE_RESPONSE_ADAPTER = DiscretionaryAdapter(
    name="campaign_ceasefire_response", options_fn=campaign_ceasefire_response_options,
    label_fn=lambda option: f"{'Aceitar' if option.response == 'accept' else 'Recusar'} o cessar-fogo {option.proposal_id}.",
    causes_fn=_campaign_ceasefire_causes, execute_fn=respond_campaign_ceasefire,
    family="campaign")

CAMPAIGN_CEASEFIRE_FULFILLMENT_ADAPTER = DiscretionaryAdapter(
    name="campaign_ceasefire_fulfillment", options_fn=campaign_ceasefire_fulfillment_options,
    label_fn=lambda option: f"Cumprir retirada do cessar-fogo na campanha {option.campaign_id}.",
    causes_fn=_campaign_ceasefire_causes, execute_fn=fulfill_campaign_ceasefire,
    family="campaign")


def _administration_concession_causes(world, option):
    proposal_id = getattr(option, "proposal_id", None)
    proposal = world.relations.proposals.get(proposal_id) if proposal_id else None
    campaign = world.society.force_standoffs.get(getattr(option, "standoff_id", None))
    obligation = world.relations.obligations.get(getattr(option, "obligation_id", None))
    return tuple(item for item in (
        getattr(option, "report_event_id", None),
        proposal.last_event_id if proposal else None,
        campaign.last_event_id if campaign else None,
        obligation.last_event_id if obligation else None,
    ) if item)


ADMINISTRATION_CONCESSION_OFFER_ADAPTER = DiscretionaryAdapter(
    name="administration_concession_offer", family="campaign",
    options_fn=administration_concession_offer_options,
    label_fn=lambda option: f"Oferecer cessão administrativa de {option.settlement_id} em troca de retirada.",
    causes_fn=_administration_concession_causes, execute_fn=offer_administration_concession)

ADMINISTRATION_CONCESSION_RESPONSE_ADAPTER = DiscretionaryAdapter(
    name="administration_concession_response", family="campaign",
    options_fn=administration_concession_response_options,
    label_fn=lambda option: (
        "Aceitar a cessão administrativa proposta."
        if option.response == "accept" else "Recusar a cessão administrativa proposta."),
    causes_fn=_administration_concession_causes, execute_fn=respond_administration_concession)

ADMINISTRATION_TRANSFER_FULFILLMENT_ADAPTER = DiscretionaryAdapter(
    name="administration_transfer_fulfillment", family="campaign",
    options_fn=administration_transfer_fulfillment_options,
    label_fn=lambda option: "Cumprir a transferência administrativa aceita.",
    causes_fn=_administration_concession_causes, execute_fn=fulfill_administration_transfer)


def _freight_recovery_causes(world, option):
    return (option.order_last_event_id,)


def _execute_freight_recovery(world, actor, option_id, decision_event_id):
    execute_freight_recovery(world, option_id, decision_event_id=decision_event_id)


def _freight_recovery_situation(world, actor, options):
    return {
        "you_are": actor.to_dict(),
        "today": world.clock.absolute_day,
        "blocked_shipments": [
            {"order_id": option.order_id, "kind": option.kind,
             "quantity": option.quantity,
             "blocked_route_ids": list(blocking_routes(world, world.economy.freight_orders[option.order_id])),
             "successor_route_ids": list(option.route_ids)}
            for option in options
        ],
    }


def _purchase_recovery_causes(world, option):
    order_id = getattr(option, "order_id", None)
    if order_id is not None:
        order = world.economy.freight_orders.get(order_id)
        return (order.last_event_id,) if order is not None else ()
    case = world.economy.freight_recovery_cases.get(getattr(option, "case_id", ""))
    return (case.last_event_id,) if case is not None else ()


def _execute_purchase_recovery_request(world, actor, option_id, decision_event_id):
    request_purchase_recovery(world, option_id, decision_event_id=decision_event_id)


def _execute_purchase_recovery_response(world, actor, option_id, decision_event_id):
    respond_purchase_recovery(world, option_id, decision_event_id=decision_event_id)


FREIGHT_RECOVERY_ADAPTER = DiscretionaryAdapter(
    name="freight_recovery", options_fn=freight_recovery_options,
    label_fn=lambda option: (
        f"{'Abrir uma remessa sucessora' if option.kind == 'successor' else 'Aguardar'} "
        f"para a carga bloqueada {option.order_id}."),
    causes_fn=_freight_recovery_causes, execute_fn=_execute_freight_recovery,
    family="freight_recovery", situation_fn=_freight_recovery_situation)

PURCHASE_RECOVERY_REQUEST_ADAPTER = DiscretionaryAdapter(
    name="purchase_recovery_request", options_fn=purchase_recovery_request_options,
    label_fn=lambda option: f"Pedir reenvio da compra bloqueada {option.order_id}.",
    causes_fn=_purchase_recovery_causes, execute_fn=_execute_purchase_recovery_request,
    family="purchase_recovery")

PURCHASE_RECOVERY_RESPONSE_ADAPTER = DiscretionaryAdapter(
    name="purchase_recovery_response", options_fn=purchase_recovery_response_options,
    label_fn=lambda option: (
        f"{'Aceitar' if option.kind == 'accept' else 'Recusar'} o reenvio da compra {option.case_id}."),
    causes_fn=_purchase_recovery_causes, execute_fn=_execute_purchase_recovery_response,
    family="purchase_recovery")

CIVIL_ADAPTERS = (SUPPLY_ADAPTER, MARKET_PURCHASE_ADAPTER, AID_ADAPTER,
                  AID_RESPONSE_ADAPTER, AID_FULFILLMENT_ADAPTER, AID_REMEDIATION_ADAPTER,
                  REPAIR_ADAPTER,
                  SITE_REACTIVATION_ADAPTER, FREIGHT_RECOVERY_ADAPTER,
                  PURCHASE_RECOVERY_REQUEST_ADAPTER, PURCHASE_RECOVERY_RESPONSE_ADAPTER,
                  *expansion_adapters(), *research_adapters(), *siege_campaign_adapters(),
                  CAMPAIGN_CEASEFIRE_OFFER_ADAPTER, CAMPAIGN_CEASEFIRE_RESPONSE_ADAPTER,
                  CAMPAIGN_CEASEFIRE_FULFILLMENT_ADAPTER,
                  ADMINISTRATION_CONCESSION_OFFER_ADAPTER,
                  ADMINISTRATION_CONCESSION_RESPONSE_ADAPTER,
                  ADMINISTRATION_TRANSFER_FULFILLMENT_ADAPTER,
                  *relief_adapters())


def concurrent_civil_options(world, actor):
    """Recompose today's menu; every entry is untouched from its own vertical."""
    if not isinstance(actor, EntityRef) or actor.kind != "polity":
        return ()
    return (*supply_objective_options(world, actor), *market_purchase_options(world, actor),
            *_current_aid_requests(world, actor),
            *_current_aid_responses(world, actor),
            *aid_fulfillment_options(world, actor), *aid_remediation_options(world, actor),
            *repair_authorization_options(world, actor), *site_reactivation_options(world, actor),
            *freight_recovery_options(world, actor),
            *purchase_recovery_request_options(world, actor), *purchase_recovery_response_options(world, actor),
            *expansion_options(world, actor), *research_options(world, actor),
            *siege_campaign_options(world, actor), *siege_campaign_withdrawal_options(world, actor),
            *siege_occupation_options(world, actor), *territorial_control_options(world, actor),
            *campaign_ceasefire_offer_options(world, actor),
            *campaign_ceasefire_response_options(world, actor),
            *campaign_ceasefire_fulfillment_options(world, actor),
            *administration_concession_offer_options(world, actor),
            *administration_concession_response_options(world, actor),
            *administration_transfer_fulfillment_options(world, actor),
            *(relief_settlement_options(world, actor.id) if actor.kind == "polity" else ()),
            *(relief_transfer_options(world, actor) if actor.kind == "polity" else ()))


async def review_concurrent_civil_decision_with_provider(world):
    """One review per polity per boundary; no persisted planner or menu state."""
    claims, covered_actors = await review_institutional_decision_turn_with_provider(world, CIVIL_ADAPTERS)
    return claims.get("objective", set()), claims.get("site", set()), covered_actors

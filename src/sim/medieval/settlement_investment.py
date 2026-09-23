"""Bounded settlement pressure built only from existing force route causes.

An investment does not create a siege subsystem: it is one prepared, supplied
column temporarily interdicting every currently usable exit of a settlement.
Society owns the commitment and Map owns each effective zero-capacity route.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.knowledge import settlement_pressure_notice_id
from src.classes.governance.models import SettlementPressureNotice
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import RouteInterdiction, SettlementInvestment
from src.classes.society.models import Identity

from .economy import _causes, _delta
from .events import record_event
from .route_interdiction import _current_report


INVEST_ACTION = "settlement_invest"
LIFT_ACTION = "lift_settlement_investment"


@dataclass(frozen=True)
class SettlementInvestmentOption:
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    settlement_id: Identity
    route_ids: tuple[Identity, ...]
    report_event_ids: tuple[Identity, ...]
    kind: str
    investment_id: Identity | None = None

    def decision(self):
        return {
            "action": INVEST_ACTION if self.kind == "invest" else LIFT_ACTION,
            "actor_ref": self.actor_ref.to_dict(),
            "selected_affordance_id": self.id,
        }


def _exits(world, settlement_id):
    settlement = world.society.settlements[settlement_id]
    return tuple(sorted(route.id for route in world.map.routes.values()
                        if settlement.region_id in route.endpoint_region_ids))


def _eligible_routes(world, actor, detachment):
    position = world.society.force_positions.get(f"force-position:{detachment.id}")
    if (detachment.stage != "present" or position is None or position.stage != "prepared"
            or position.settlement_id != detachment.location_id or detachment.provisions < detachment.count):
        return None
    settlement = world.society.settlements[detachment.location_id]
    # Pressure targets a foreign administration, or a foreign occupier of
    # one's own city. An unoccupied home city cannot manufacture a notice.
    if settlement.administrator_id is None:
        return None
    occupation_report_id = None
    if settlement.administrator_id == actor.id:
        # An administration may try to dislodge an actual foreign occupier of
        # its own city, but only when its present column has observed that
        # occupation locally. A free home city remains ineligible.
        report = world.knowledge.settlement_report(actor, settlement.id)
        if (settlement.occupier_id in {None, actor.id} or report is None
                or report.recipient_ref != actor or report.publisher_ref != actor
                or report.channel != "local_settlement_report"
                or report.occupier_id != settlement.occupier_id
                or not 0 <= world.clock.absolute_day - report.observed_day < 31):
            return None
        occupation_report_id = report.event_id
    route_ids = _exits(world, settlement.id)
    if not route_ids or len(route_ids) > max(1, detachment.count // 20):
        return None
    route_reports = tuple(_current_report(world, actor, route_id) for route_id in route_ids)
    if any(report is None or report.operational_capacity <= 0 or report.travel_days is None
           for report in route_reports):
        return None
    if any(world.map.get_route_operational_capacity(route_id) <= 0
           or route_id in world.map.force_route_interdictors for route_id in route_ids):
        return None
    if any(item.stage == "active" and item.settlement_id == settlement.id
           for item in world.society.settlement_investments.values()):
        return None
    sources = tuple(report.event_id for report in route_reports)
    return route_ids, sources + ((occupation_report_id,) if occupation_report_id is not None else ())


def settlement_investment_options(world, actor, *, detachment_id=None):
    """Recompose the all-exit choice; no LLM may select a route or quantity."""
    if not can_actor_act_for(world, actor, actor, "military"):
        return ()
    options = []
    for detachment in sorted(world.society.detachments.values(), key=lambda item: item.id):
        if detachment.owner_ref != actor or (detachment_id is not None and detachment.id != detachment_id):
            continue
        own = sorted((item for item in world.society.settlement_investments.values()
                      if item.detachment_id == detachment.id and item.stage == "active"), key=lambda item: item.id)
        for investment in own:
            options.append(SettlementInvestmentOption(
                id=f"settlement-investment-lift:{investment.id}:{investment.last_event_id}", actor_ref=actor,
                detachment_id=detachment.id, settlement_id=investment.settlement_id,
                route_ids=investment.route_ids, report_event_ids=(), kind="lift", investment_id=investment.id))
        if own:
            continue
        eligible = _eligible_routes(world, actor, detachment)
        if eligible is None:
            continue
        route_ids, report_ids = eligible
        position = world.society.force_positions[f"force-position:{detachment.id}"]
        options.append(SettlementInvestmentOption(
            id=(f"settlement-investment:{detachment.id}:{detachment.last_event_id}:{position.last_event_id}:"
                f"{','.join(route_ids)}:{','.join(report_ids)}"), actor_ref=actor, detachment_id=detachment.id,
            settlement_id=detachment.location_id, route_ids=route_ids, report_event_ids=report_ids, kind="invest"))
    return tuple(sorted(options, key=lambda item: item.id))


def _decision(world, decision_event_id, action):
    from .force import _decision as force_decision
    return force_decision(world, decision_event_id, action)


def execute_settlement_investment_option(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in settlement_investment_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("settlement investment option is stale or unknown")
    action = INVEST_ACTION if option.kind == "invest" else LIFT_ACTION
    decision, decided_by = _decision(candidate, decision_event_id, action)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("settlement investment has the wrong decision")
    require_authority(candidate, actor, "military")
    if option.kind == "invest":
        _invest(candidate, option, decision)
    else:
        _lift(candidate, candidate.society.settlement_investments[option.investment_id],
              cause_ids=(decision.id,), require_decision=True)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.settlement_investments.get(option.investment_id or f"settlement-investment:{decision.id}")


def _invest(world, option, decision):
    detachment = world.society.detachments[option.detachment_id]
    recomposed = _eligible_routes(world, option.actor_ref, detachment)
    if recomposed is None or recomposed != (option.route_ids, option.report_event_ids):
        raise ValueError("settlement investment is no longer possible")
    identity = f"settlement-investment:{decision.id}"
    route_interdiction_ids = tuple(f"route-interdiction:{decision.id}:investment:{route_id}"
                                   for route_id in option.route_ids)
    investment = SettlementInvestment(
        id=identity, actor_ref=option.actor_ref, detachment_id=detachment.id, settlement_id=option.settlement_id,
        route_ids=option.route_ids, route_interdiction_ids=route_interdiction_ids,
        started_day=world.clock.absolute_day, decision_event_id=decision.id, last_event_id="pending")
    entries = tuple(RouteInterdiction(
        id=interdiction_id, actor_ref=option.actor_ref, detachment_id=detachment.id, route_id=route_id,
        settlement_id=option.settlement_id, investment_id=identity, started_day=world.clock.absolute_day,
        decision_event_id=decision.id, last_event_id="pending")
        for interdiction_id, route_id in zip(route_interdiction_ids, option.route_ids))
    before = {route_id: world.map.get_route_operational_capacity(route_id) for route_id in option.route_ids}
    settlement = world.society.settlements[option.settlement_id]
    recipient_id = (settlement.occupier_id if settlement.administrator_id == option.actor_ref.id
                    else settlement.administrator_id)
    recipient = EntityRef("polity", recipient_id)
    notice_id = settlement_pressure_notice_id(identity, recipient)
    event = record_event(
        world, "settlement_invested", "Uma coluna preparada restringiu todos os acessos operacionais do assentamento.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(
            _delta("settlement_investment", identity, "stage", None, "active"),
            _delta("settlement_investment", identity, "route_ids", None, option.route_ids),
            _delta("settlement_pressure_notice", notice_id, "route_count", None, len(option.route_ids)),
            *tuple(delta for entry, route_id in zip(entries, option.route_ids) for delta in (
                _delta("route_interdiction", entry.id, "stage", None, "active"),
                _delta("route", route_id, "force_interdictor_id", None, entry.id),
                _delta("route", route_id, "operational_capacity", before[route_id], 0.0),
            )),
        ),
        cause_ids=_causes(decision.id, detachment.last_event_id,
                          world.society.force_positions[f"force-position:{detachment.id}"].last_event_id,
                          *option.report_event_ids),
    )
    for entry in entries:
        world.map.set_force_route_interdictor(entry.route_id, entry.id)
        world.society.route_interdictions[entry.id] = entry.model_copy(update={"last_event_id": event.id})
    world.society.settlement_investments[identity] = investment.model_copy(update={"last_event_id": event.id})
    world.knowledge.settlement_pressure_notices[notice_id] = SettlementPressureNotice(
        id=notice_id, recipient_ref=recipient, settlement_id=option.settlement_id, investment_id=identity,
        route_count=len(option.route_ids), event_id=event.id, learned_day=world.clock.absolute_day)
    from .route_intelligence import refresh_route_reports
    refresh_route_reports(world, route_ids=option.route_ids)
    return world.society.settlement_investments[identity]


def _lift(world, investment, *, cause_ids=(), require_decision=False):
    if investment.stage != "active":
        raise ValueError("settlement investment no longer holds")
    if require_decision:
        require_authority(world, investment.actor_ref, "military")
    entries = tuple(world.society.route_interdictions[identity] for identity in investment.route_interdiction_ids)
    if any(entry.stage != "active" or world.map.force_route_interdictors.get(entry.route_id) != entry.id
           for entry in entries):
        raise ValueError("settlement investment no longer holds its route causes")
    before = {entry.route_id: world.map.get_route_operational_capacity(entry.route_id) for entry in entries}
    for entry in entries:
        world.map.clear_force_route_interdictor(entry.route_id, entry.id)
    after = {entry.route_id: world.map.get_route_operational_capacity(entry.route_id) for entry in entries}
    event = record_event(
        world, "settlement_investment_lifted", "A pressão física da coluna sobre os acessos do assentamento terminou.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(
            _delta("settlement_investment", investment.id, "stage", "active", "lifted"),
            *tuple(delta for entry in entries for delta in (
                _delta("route_interdiction", entry.id, "stage", "active", "lifted"),
                _delta("route", entry.route_id, "force_interdictor_id", entry.id, None),
                _delta("route", entry.route_id, "operational_capacity", before[entry.route_id], after[entry.route_id]),
            )),
        ),
        cause_ids=_causes(investment.last_event_id, *cause_ids),
    )
    for entry in entries:
        world.society.route_interdictions[entry.id] = entry.model_copy(
            update={"stage": "lifted", "lifted_day": world.clock.absolute_day, "last_event_id": event.id})
    world.society.settlement_investments[investment.id] = investment.model_copy(
        update={"stage": "lifted", "lifted_day": world.clock.absolute_day, "last_event_id": event.id})
    from .route_intelligence import refresh_route_reports
    refresh_route_reports(world, route_ids=investment.route_ids)
    return event


def revoke_settlement_investments_for(world, detachment, *, cause_ids=()):
    """Departure, lapse, defeat and stand-down lift every linked route cause first."""
    lifted = []
    for investment in tuple(world.society.settlement_investments.values()):
        if investment.detachment_id == detachment.id and investment.stage == "active":
            lifted.append(_lift(world, investment, cause_ids=_causes(detachment.last_event_id, *cause_ids)))
    return tuple(lifted)


def revoke_invalid_settlement_investments(world):
    """A new non-force closure ends pressure explicitly; it never coexists silently."""
    from .logistics import _route_causes

    lifted = []
    for investment in tuple(world.society.settlement_investments.values()):
        if investment.stage != "active":
            continue
        detachment = world.society.detachments.get(investment.detachment_id)
        position = (world.society.force_positions.get(f"force-position:{investment.detachment_id}")
                    if detachment is not None else None)
        entries = tuple(world.society.route_interdictions[identity] for identity in investment.route_interdiction_ids)
        lost_routes = tuple(entry.route_id for entry in entries
                            if world.map.force_route_interdictors.get(entry.route_id) != entry.id
                            or world.map.get_route_operational_capacity(
                                entry.route_id, ignore_force_interdictor=True) <= 0)
        invalid = (detachment is None or detachment.stage != "present"
                   or detachment.location_id != investment.settlement_id
                   or detachment.provisions < detachment.count
                   or position is None or position.stage != "prepared"
                   or bool(lost_routes))
        if invalid:
            route_causes = _route_causes(world, lost_routes)
            lifted.append(_lift(world, investment, cause_ids=_causes(
                investment.last_event_id,
                detachment.last_event_id if detachment is not None and
                (detachment.stage != "present" or detachment.location_id != investment.settlement_id
                 or detachment.provisions < detachment.count) else None,
                position.last_event_id if position is not None and position.stage != "prepared" else None,
                *(event_id for route_id in lost_routes for event_id in route_causes[route_id]))))
    return tuple(lifted)


__all__ = ["INVEST_ACTION", "LIFT_ACTION", "SettlementInvestmentOption",
           "execute_settlement_investment_option", "revoke_invalid_settlement_investments",
           "revoke_settlement_investments_for", "settlement_investment_options"]

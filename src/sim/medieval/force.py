"""Raising, marching and standing: the material floor under any campaign.

Nothing here resolves a battle, a siege or a morale check. A detachment is
people who left a real cohort with real provisions, walking real routes. While
it stands supplied somewhere, its owner may record occupation of that place —
a revocable settlement fact that grants no administration, no stock, no
account and no tax. When the provisions run out the presence lapses by its own
fact and the survivors return to a cohort where they actually are.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.economy.models import MoneyAccount
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, headquarters_holder, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment, ForcePosition, ForceStandoff
from src.classes.society.force import Garrison
from src.classes.governance.knowledge import force_contact_notice_id
from src.classes.governance.models import ForceContactNotice
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .demand import reserve_quantity
from .economy import _causes, _delta, monthly_workforce
from .events import record_event
from .labor import settle_work
from .routing import known_supply_path, known_supply_path_from_region
from .travel import route_duration


RAISE_ACTION = "raise_detachment"
MARCH_ACTION = "march_detachment"
REROUTE_ACTION = "reroute_detachment"
OCCUPY_ACTION = "occupy_settlement"
DISBAND_ACTION = "disband_detachment"
STAND_DOWN_ACTION = "stand_down_from_standoff"
WITHDRAW_ACTION = "withdraw_detachment"
PREPARE_POSITION_ACTION = "prepare_force_position"
RATIONS_PER_SOLDIER_DAY = 1
WAGE_PER_SOLDIER = 2
GARRISON_WAGE_PER_SOLDIER_DAY = 1
POSITION_PREPARATION_DAYS = 3


@dataclass(frozen=True)
class RaiseOption:
    id: Identity
    actor_ref: EntityRef
    group_id: Identity
    settlement_id: Identity
    stock_id: Identity
    account_id: Identity
    count: int
    provisions: int
    days: int
    destination_id: Identity
    route_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": RAISE_ACTION, "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


@dataclass(frozen=True)
class DetachmentRerouteOption:
    """One current, institution-known alternate path around a blocked leg."""
    id: Identity
    actor_ref: EntityRef
    institution_ref: EntityRef
    plan_id: Identity
    detachment_id: Identity
    blocked_route_id: Identity
    blocked_report_id: Identity
    start_region_id: int
    route_ids: tuple[Identity, ...]
    route_report_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": REROUTE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class DetachmentRetreatOption:
    """A halted column's current HQ-known route back to own administration."""
    id: Identity
    actor_ref: EntityRef
    institution_ref: EntityRef
    plan_id: Identity
    detachment_id: Identity
    blocked_route_id: Identity
    blocked_report_id: Identity
    start_region_id: int
    destination_id: Identity
    route_ids: tuple[Identity, ...]
    route_report_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": "retreat_marching_detachment", "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class ForceOption:
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    kind: str

    def decision(self):
        return {"action": {"march": MARCH_ACTION, "occupy": OCCUPY_ACTION, "garrison": GARRISON_ACTION,
                             "disband": DISBAND_ACTION}[self.kind],
                "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


GARRISON_ACTION = "establish_garrison"
WITHDRAW_GARRISON_ACTION = "withdraw_garrison"
ROTATE_GARRISON_ACTION = "rotate_garrison"


@dataclass(frozen=True)
class GarrisonOption:
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    settlement_id: Identity
    account_id: Identity
    daily_wage: int
    kind: str = "garrison"

    def decision(self):
        action = GARRISON_ACTION if self.kind in {"garrison", "defend"} else WITHDRAW_GARRISON_ACTION
        return {"action": action, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class GarrisonRotationOption:
    """Replace one active duty with another supplied column already present.

    Rotation changes only the military duty.  The physical columns, occupation,
    administration and territorial control remain separate canonical facts.
    """
    id: Identity
    actor_ref: EntityRef
    current_detachment_id: Identity
    replacement_detachment_id: Identity
    settlement_id: Identity
    account_id: Identity
    daily_wage: int
    kind: str = "rotate"

    @property
    def detachment_id(self):
        return self.current_detachment_id

    def decision(self):
        return {"action": ROTATE_GARRISON_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class StandoffOption:
    """One owner may only dissolve its own present column at this contact."""
    id: Identity
    actor_ref: EntityRef
    standoff_id: Identity
    detachment_id: Identity

    def decision(self):
        return {"action": STAND_DOWN_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class WithdrawalOption:
    """A current, owner-known route from a standing column to own government."""
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    destination_id: Identity
    route_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": WITHDRAW_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class HeadquartersWithdrawalOption:
    """A current QG decision to return its institution's winning campaign column."""
    id: Identity
    actor_ref: EntityRef
    institution_ref: EntityRef
    plan_id: Identity | None
    engagement_id: Identity
    engagement_event_id: Identity
    settlement_report_event_id: Identity
    detachment_id: Identity
    destination_id: Identity
    route_ids: tuple[Identity, ...]
    route_report_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": WITHDRAW_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class CampaignLogisticsWithdrawalOption:
    """QG may end a supplied campaign after a real, resolved freight delay."""
    id: Identity
    actor_ref: EntityRef
    institution_ref: EntityRef
    plan_id: Identity | None
    detachment_id: Identity
    delay_notice_ids: tuple[Identity, ...]
    delay_notice_event_ids: tuple[Identity, ...]
    delay_event_ids: tuple[Identity, ...]
    position_report_id: Identity
    destination_id: Identity
    route_ids: tuple[Identity, ...]
    route_report_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": WITHDRAW_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class ForcePositionOption:
    """One own supplied column may prepare where it already stands."""
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    settlement_id: Identity
    anchor_site_id: Identity | None

    def decision(self):
        return {"action": PREPARE_POSITION_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _event(world, event_id):
    if not isinstance(event_id, str) or not event_id.startswith("event:"):
        return None
    position = event_id.partition(":")[2]
    if not position.isdecimal() or not 1 <= int(position) <= len(world.events):
        return None
    event = world.events[int(position) - 1]
    return event if event.id == event_id else None


def _decision(world, decision_event_id, action):
    event = _event(world, decision_event_id)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.causal_origin is not CausalOrigin.ACTOR_DECISION
            or event.decision is None or event.decision.get("action") != action
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("force action requires a current actor decision")
    try:
        actor = EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("force decision has an invalid actor") from exc
    return event, actor


def _decision_authorship(decision):
    return {
        "decision_event_id": decision.id,
        "actor_ref": decision.decision["actor_ref"],
        "selected_affordance_id": decision.decision["selected_affordance_id"],
    }


def _commands(world, actor):
    return isinstance(actor, EntityRef) and can_actor_act_for(world, actor, actor, "military")


def _own_stock(world, actor, settlement_id):
    return next((item for _, item in sorted(world.economy.stocks.items())
                 if item.owner_ref == actor and item.location_id == settlement_id), None)


def _own_account(world, actor):
    return next((item for _, item in sorted(world.economy.accounts.items()) if item.owner_ref == actor), None)


def recruitment_capacity(world, actor, destination_id, *, days=10):
    """Sources that could equip recruits, with people as the binding constraint.

    The future stipend and first military wage both need cash.  This reading
    never reserves either means or people; the existing owners revalidate both
    when a group accepts and when a column is eventually raised.
    """
    if not _commands(world, actor):
        return ()
    account = _own_account(world, actor)
    if account is None:
        return ()
    sources = []
    for settlement in sorted(world.society.settlements.values(), key=lambda item: item.id):
        if settlement.id == destination_id or settlement.administrator_id != actor.id:
            continue
        stock = _own_stock(world, actor, settlement.id)
        if stock is None or not known_supply_path(world, actor, settlement.id, destination_id, "food"):
            continue
        if any(group.settlement_id == settlement.id and group.occupation == "soldier"
               and world.society.available_count(group.id) > 0
               for group in world.society.population.values()):
            continue
        if not any(group.settlement_id == settlement.id and group.occupation != "soldier"
                   and group.count >= 5 and world.society.available_count(group.id) == group.count
                   for group in world.society.population.values()):
            continue
        free_food = max(0, stock.goods.get("food", 0) - reserve_quantity(world, stock.id, "food"))
        # The same canonical wage is used as a signing stipend; keep enough
        # money for the later first payroll instead of funding only an offer.
        count = min(free_food // (RATIONS_PER_SOLDIER_DAY * days),
                    account.balance // (2 * WAGE_PER_SOLDIER))
        if count > 0:
            sources.append((settlement.id, account.id, count))
    return tuple(sorted(sources, key=lambda item: (-item[2], item[0])))


def raise_options(world, actor, days=10):
    """Detachments this institution could raise today from its own means."""
    if not _commands(world, actor):
        return ()
    options = []
    for group_id in sorted(world.society.population):
        group = world.society.population[group_id]
        settlement = world.society.settlements[group.settlement_id]
        if (group.occupation != "soldier" or settlement.administrator_id != actor.id
                or world.society.available_count(group_id) <= 0):
            continue
        stock = _own_stock(world, actor, group.settlement_id)
        account = _own_account(world, actor)
        if stock is None or account is None:
            continue
        free_food = stock.goods.get("food", 0) - reserve_quantity(world, stock.id, "food")
        for destination_id in sorted(world.society.settlements):
            if destination_id == group.settlement_id:
                continue
            route = known_supply_path(world, actor, group.settlement_id, destination_id, "food")
            if not route:
                continue
            count = min(world.society.available_count(group_id), max(0, free_food // (RATIONS_PER_SOLDIER_DAY * days)))
            provisions = count * RATIONS_PER_SOLDIER_DAY * days
            if count <= 0 or account.balance < count * WAGE_PER_SOLDIER:
                continue
            options.append(RaiseOption(
                id=(f"raise-detachment:{actor.id}:{group_id}:{destination_id}:{count}:{provisions}:"
                    f"{'-'.join(route)}"),
                actor_ref=actor, group_id=group_id, settlement_id=group.settlement_id, stock_id=stock.id,
                account_id=account.id, count=count, provisions=provisions, days=days,
                destination_id=destination_id,
                route_ids=tuple(route)))
    return tuple(sorted(options, key=lambda item: item.id))


def detachment_reroute_options(world, institution_ref, plan_id, *, actor_ref=None):
    """Offer one alternate path using only the deciding actor's fresh reports.

    The HQ retains its existing path. A named commander may use the same owner
    only while physically attached to this column and only from their own
    first-hand reports; the search never consults current Map capacity as actor
    knowledge.
    """
    from .strategy_response import _political_order

    plan = world.strategy.plans.get(plan_id)
    objective = world.strategy.objectives.get(plan.objective_id) if plan else None
    detachment = world.society.detachments.get(plan.detachment_id) if plan else None
    holder = headquarters_holder(world, institution_ref)
    actor = holder if actor_ref is None else actor_ref
    actor_authorized = actor is not None and (
        can_actor_act_for(world, institution_ref, institution_ref, "military")
        if actor == holder else actor.kind == "character")
    if (plan is None or objective is None or objective.actor_ref != institution_ref
            or plan.stage not in {"mobilized", "blocked"} or detachment is None
            or detachment.owner_ref != institution_ref or detachment.stage != "marching"
            or not 0 <= detachment.route_index < len(detachment.route_ids)
            or actor is None or not actor_authorized
            or _political_order(world, plan, objective) is None):
        return ()
    if actor != holder:
        from .force_command import command_is_current
        command = world.society.detachment_commands.get(detachment.id)
        if (actor.kind != "character" or command is None or command.character_id != actor.id
                or command.institution_ref != institution_ref or command.detachment_id != detachment.id):
            return ()
        if not command_is_current(world, command):
            return ()
    held = world.event_index().get(detachment.last_event_id)
    blocked_route_id = detachment.route_ids[detachment.route_index]
    blocked_route = world.map.routes.get(blocked_route_id)
    bulk = world.economy.resources["food"].bulk if "food" in world.economy.resources else None
    report = world.knowledge.route_report(actor, blocked_route_id)
    if (held is None or held.event_type != "detachment_held" or blocked_route is None or bulk is None
            or world.map.get_route_operational_capacity(blocked_route_id) > 0
            or report is None or report.travel_days is not None or report.operational_capacity >= bulk
            or not 0 <= world.clock.absolute_day - report.observed_day < 30):
        return ()

    if detachment.route_index == 0:
        start_region_id = world.society.settlements[detachment.location_id].region_id
    else:
        previous = world.map.routes.get(detachment.route_ids[detachment.route_index - 1])
        shared = set(previous.endpoint_region_ids) & set(blocked_route.endpoint_region_ids) if previous else set()
        if len(shared) != 1:
            return ()
        start_region_id = next(iter(shared))
    destination = world.society.settlements.get(objective.settlement_id)
    if destination is None:
        return ()
    alternative = known_supply_path_from_region(
        world, actor, start_region_id, destination.region_id, "food",
        excluded_route_ids=(*detachment.route_ids[:detachment.route_index], blocked_route_id))
    if not alternative:
        return ()
    reports = tuple(world.knowledge.route_report(actor, route_id) for route_id in alternative)
    if any(item is None for item in reports):
        return ()
    report_ids = tuple(item.event_id for item in reports)
    option_id = (f"detachment-reroute:{plan.id}:{detachment.id}:{held.id}:{blocked_route_id}:"
                 f"{'-'.join(alternative)}:{report.event_id}:{'-'.join(report_ids)}")
    return (DetachmentRerouteOption(
        id=option_id, actor_ref=actor, institution_ref=institution_ref, plan_id=plan.id,
        detachment_id=detachment.id, blocked_route_id=blocked_route_id,
        blocked_report_id=report.event_id, start_region_id=start_region_id,
        route_ids=tuple(alternative), route_report_ids=report_ids),)


def reroute_detachment(world, institution_ref, plan_id, option_id, decision_event_id, *, actor_ref=None):
    """Revalidate and change only the route of a halted, real column."""
    candidate = deepcopy(world)
    option = next((item for item in detachment_reroute_options(
        candidate, institution_ref, plan_id, actor_ref=actor_ref)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("detachment reroute option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id, REROUTE_ACTION)
    if decided_by != option.actor_ref or decision.decision != option.decision():
        raise ValueError("detachment reroute has the wrong decision")
    require_authority(candidate, institution_ref, "military")
    is_current_headquarters = decided_by == headquarters_holder(candidate, institution_ref)
    if not is_current_headquarters:
        command = candidate.society.detachment_commands.get(option.detachment_id)
        from .force_command import command_is_current
        if (command is None or command.character_id != decided_by.id
                or command.institution_ref != institution_ref or not command_is_current(candidate, command)):
            raise ValueError("detachment reroute actor no longer commands this column")
    plan = candidate.strategy.plans[option.plan_id]
    objective = candidate.strategy.objectives[plan.objective_id]
    from .strategy_response import _political_order
    if _political_order(candidate, plan, objective) is None:
        raise ValueError("detachment reroute no longer has a current political order")

    detachment = candidate.society.detachments[option.detachment_id]
    prefix = detachment.route_ids[:detachment.route_index]
    region = candidate.society.settlements[detachment.location_id].region_id
    for route_id in prefix:
        route = candidate.map.routes.get(route_id)
        if (route is None or region not in route.endpoint_region_ids
                or candidate.map.get_route_operational_capacity(route_id) <= 0):
            raise ValueError("detachment reroute prefix is no longer possible")
        region = next(item for item in route.endpoint_region_ids if item != region)
    if region != option.start_region_id:
        raise ValueError("detachment reroute origin is stale")
    updated_route_ids = (*prefix, *option.route_ids)
    destination_region = candidate.society.settlements[objective.settlement_id].region_id
    for route_id in option.route_ids:
        route = candidate.map.routes.get(route_id)
        if (route is None or region not in route.endpoint_region_ids
                or not route.allows_resource("food")
                or candidate.map.get_route_operational_capacity(route_id) <= 0):
            raise ValueError("detachment reroute path is no longer physically possible")
        region = next(item for item in route.endpoint_region_ids if item != region)
    if region != destination_region:
        raise ValueError("detachment reroute does not reach the objective")

    updated = detachment.model_copy(update={"route_ids": tuple(updated_route_ids),
                                             "due_day": candidate.clock.absolute_day + 1})
    event = _record(
        candidate, detachment, updated, "detachment_rerouted",
        "O QG escolheu uma rota alternativa já observada para a coluna parada.",
        deltas=(_delta("detachment", detachment.id, "route_ids", detachment.route_ids, updated.route_ids),
                _delta("detachment", detachment.id, "due_day", detachment.due_day, updated.due_day)),
        causes=_causes(decision.id, detachment.last_event_id, option.blocked_report_id,
                       *option.route_report_ids))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return event


def detachment_retreat_options(world, institution_ref, plan_id, *, actor_ref=None):
    """Offer a valid HQ or attached commander a retreat from a held leg.

    The current map region is derived from the already-completed route prefix;
    the blocked leg itself is never traversed. Every return leg must have a
    fresh report owned by the deciding actor. A commander may return only to
    the known departure settlement of their own column.
    """
    from .strategy_response import _political_order
    from .campaign_supply import campaign_baggage_ready_for_departure

    plan = world.strategy.plans.get(plan_id)
    objective = world.strategy.objectives.get(plan.objective_id) if plan else None
    detachment = world.society.detachments.get(plan.detachment_id) if plan else None
    holder = headquarters_holder(world, institution_ref)
    actor = holder if actor_ref is None else actor_ref
    actor_authorized = actor is not None and (
        can_actor_act_for(world, institution_ref, institution_ref, "military")
        if actor == holder else actor.kind == "character")
    if (plan is None or objective is None or objective.actor_ref != institution_ref
            or plan.stage not in {"mobilized", "blocked"} or detachment is None
            or detachment.owner_ref != institution_ref or detachment.stage != "marching"
            or not 0 <= detachment.route_index < len(detachment.route_ids)
            or holder is None or not actor_authorized
            or _political_order(world, plan, objective) is None
            or not campaign_baggage_ready_for_departure(world, detachment)):
        return ()
    if actor != holder:
        from .force_command import command_is_current
        command = world.society.detachment_commands.get(detachment.id)
        if (actor.kind != "character" or command is None or command.character_id != actor.id
                or command.institution_ref != institution_ref or not command_is_current(world, command)):
            return ()
    events = world.event_index()
    held = events.get(detachment.last_event_id)
    blocked_route_id = detachment.route_ids[detachment.route_index]
    blocked_route = world.map.routes.get(blocked_route_id)
    bulk = world.economy.resources.get("food")
    blocked_report = world.knowledge.route_report(actor, blocked_route_id)
    if (held is None or held.event_type != "detachment_held" or blocked_route is None or bulk is None
            or world.map.get_route_operational_capacity(blocked_route_id) > 0
            or blocked_report is None or blocked_report.travel_days is not None
            or blocked_report.operational_capacity >= bulk.bulk
            or not 0 <= world.clock.absolute_day - blocked_report.observed_day < 30):
        return ()

    region_id = world.society.settlements[detachment.location_id].region_id
    for route_id in detachment.route_ids[:detachment.route_index]:
        route = world.map.routes.get(route_id)
        if route is None or region_id not in route.endpoint_region_ids:
            return ()
        region_id = next(item for item in route.endpoint_region_ids if item != region_id)
    if region_id not in blocked_route.endpoint_region_ids:
        return ()

    if actor != holder:
        # A field commander can always consider retracing the material route
        # their own column already traversed. This needs no cargo-capacity
        # assumption: the bag is empty and the column carries its provisions.
        destination = world.society.settlements[detachment.location_id]
        route_ids = tuple(reversed(detachment.route_ids[:detachment.route_index]))
        route_reports = tuple(world.knowledge.route_report(actor, route_id) for route_id in route_ids)
        if (destination.administrator_id != institution_ref.id or not route_ids
                or any(report is None or report.travel_days is None
                       or not 0 <= world.clock.absolute_day - report.observed_day < 30
                       for report in route_reports)):
            return ()
        current_region = region_id
        for route_id in route_ids:
            route = world.map.routes.get(route_id)
            if (route is None or current_region not in route.endpoint_region_ids
                    or not route.allows_resource("food")
                    or world.map.get_route_operational_capacity(route_id) <= 0):
                return ()
            current_region = next(item for item in route.endpoint_region_ids if item != current_region)
        if current_region != destination.region_id:
            return ()
        report_ids = tuple(item.event_id for item in route_reports)
        option_id = (f"detachment-retreat:{plan.id}:{detachment.id}:{held.id}:{blocked_route_id}:"
                     f"{destination.id}:{'-'.join(route_ids)}:{blocked_report.event_id}:"
                     f"{'-'.join(report_ids)}")
        return (DetachmentRetreatOption(
            id=option_id, actor_ref=actor, institution_ref=institution_ref, plan_id=plan.id,
            detachment_id=detachment.id, blocked_route_id=blocked_route_id,
            blocked_report_id=blocked_report.event_id, start_region_id=region_id,
            destination_id=destination.id, route_ids=route_ids, route_report_ids=report_ids),)

    options = []
    destinations = ([world.society.settlements[detachment.location_id]] if actor != holder else
                    sorted(world.society.settlements.values(), key=lambda item: item.id))
    for destination in destinations:
        if destination.administrator_id != institution_ref.id or destination.region_id == region_id:
            continue
        if actor == holder:
            destination_report = world.knowledge.settlement_report(holder, destination.id)
            if (destination_report is None or destination_report.settlement_id != destination.id
                    or not 0 <= world.clock.absolute_day - destination_report.observed_day < 31):
                continue
        route_ids = known_supply_path_from_region(
            world, actor, region_id, destination.region_id, "food",
            excluded_route_ids=(blocked_route_id,))
        if not route_ids:
            continue
        route_reports = tuple(world.knowledge.route_report(actor, route_id) for route_id in route_ids)
        if any(report is None for report in route_reports):
            continue
        report_ids = tuple(report.event_id for report in route_reports)
        option_id = (f"detachment-retreat:{plan.id}:{detachment.id}:{held.id}:{blocked_route_id}:"
                     f"{destination.id}:{'-'.join(route_ids)}:{blocked_report.event_id}:"
                     f"{'-'.join(report_ids)}")
        options.append(DetachmentRetreatOption(
            id=option_id, actor_ref=actor, institution_ref=institution_ref, plan_id=plan.id,
            detachment_id=detachment.id, blocked_route_id=blocked_route_id,
            blocked_report_id=blocked_report.event_id, start_region_id=region_id,
            destination_id=destination.id, route_ids=tuple(route_ids), route_report_ids=report_ids))
    return tuple(sorted(options, key=lambda item: item.id))


def retreat_detachment(world, institution_ref, plan_id, option_id, decision_event_id, *, actor_ref=None):
    """Replace only the untraversed route of a held column with its chosen return."""
    candidate = deepcopy(world)
    option = next((item for item in detachment_retreat_options(
        candidate, institution_ref, plan_id, actor_ref=actor_ref)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("detachment retreat option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id, "retreat_marching_detachment")
    if decided_by != option.actor_ref or decision.decision != option.decision():
        raise ValueError("detachment retreat has the wrong decision")
    require_authority(candidate, institution_ref, "military")
    is_current_headquarters = decided_by == headquarters_holder(candidate, institution_ref)
    if not is_current_headquarters:
        command = candidate.society.detachment_commands.get(option.detachment_id)
        from .force_command import command_is_current
        if (command is None or command.character_id != decided_by.id
                or command.institution_ref != institution_ref or not command_is_current(candidate, command)):
            raise ValueError("detachment retreat actor no longer commands this column")
    plan = candidate.strategy.plans[option.plan_id]
    objective = candidate.strategy.objectives[plan.objective_id]
    from .strategy_response import _political_order
    if _political_order(candidate, plan, objective) is None:
        raise ValueError("detachment retreat no longer has a current political order")
    detachment = candidate.society.detachments[option.detachment_id]
    region_id = candidate.society.settlements[detachment.location_id].region_id
    prefix = detachment.route_ids[:detachment.route_index]
    for route_id in prefix:
        route = candidate.map.routes.get(route_id)
        if route is None or region_id not in route.endpoint_region_ids:
            raise ValueError("detachment retreat position is no longer current")
        region_id = next(item for item in route.endpoint_region_ids if item != region_id)
    if region_id != option.start_region_id:
        raise ValueError("detachment retreat origin is stale")
    route_ids = (*prefix, *option.route_ids)
    for route_id in option.route_ids:
        route = candidate.map.routes.get(route_id)
        if route is None:
            raise ValueError("detachment retreat route no longer exists")
        field_commander = (decided_by.kind == "character"
                           and decided_by != headquarters_holder(candidate, institution_ref))
        minimum_capacity = (0 if field_commander else candidate.economy.resources["food"].bulk)
        capacity = candidate.map.get_route_operational_capacity(route_id)
        if (region_id not in route.endpoint_region_ids or not route.allows_resource("food")
                or (capacity <= 0 if field_commander else capacity < minimum_capacity)):
            raise ValueError("detachment retreat path is no longer physically possible")
        region_id = next(item for item in route.endpoint_region_ids if item != region_id)
    if region_id != candidate.society.settlements[option.destination_id].region_id:
        raise ValueError("detachment retreat does not reach its selected administration")
    updated = detachment.model_copy(update={"destination_id": option.destination_id,
                                             "route_ids": tuple(route_ids),
                                             "due_day": candidate.clock.absolute_day + 1})
    event = _record(
        candidate, detachment, updated, "detachment_retreat_started",
        "O QG encerrou a missão e enviou a coluna parada de volta por uma rota conhecida.",
        deltas=(_delta("detachment", detachment.id, "destination_id", detachment.destination_id,
                       option.destination_id),
                _delta("detachment", detachment.id, "route_ids", detachment.route_ids, tuple(route_ids)),
                _delta("detachment", detachment.id, "due_day", detachment.due_day, updated.due_day)),
        causes=_causes(decision.id, plan.last_event_id, detachment.last_event_id,
                       option.blocked_report_id, *option.route_report_ids))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return event


def raise_detachment(world, actor, option_id, decision_event_id, *, days=10, operational_plan_id=None):
    """Soldiers and rations leave their owners; wages are paid at once."""
    candidate = deepcopy(world)
    option = next((item for item in raise_options(candidate, actor, days=days) if item.id == option_id), None)
    if option is None:
        raise ValueError("raise option is stale or unknown")
    if operational_plan_id is None:
        decision, decided_by = _decision(candidate, decision_event_id, RAISE_ACTION)
        if decided_by != actor or decision.decision != option.decision():
            raise ValueError("raising a detachment has the wrong actor decision")
    else:
        decision = _event(candidate, decision_event_id)
        holder = headquarters_holder(candidate, actor)
        expected = {"action": RAISE_ACTION, "actor_ref": holder.to_dict() if holder else None,
                    "institution_ref": actor.to_dict(), "operational_plan_id": operational_plan_id,
                    "selected_affordance_id": option.id}
        from .strategy_response import (_headquarters_briefing, _political_order,
                                        defense_action_options)
        plan = candidate.strategy.plans.get(operational_plan_id)
        objective = candidate.strategy.objectives.get(plan.objective_id) if plan else None
        briefing_holder, briefing = _headquarters_briefing(candidate, objective) if objective else (None, None)
        political_order = _political_order(candidate, plan, objective) if objective else None
        if (holder is None or decision is None or decision.fact_kind != FactKind.DECISION
                or decision.causal_origin is not CausalOrigin.ACTOR_DECISION
                or decision.day != candidate.clock.absolute_day or decision.decision != expected
                or briefing_holder != holder or briefing is None
                or briefing.event_id not in {link.cause_event_id for link in decision.causal_links}
                or political_order is None
                or political_order.id not in {link.cause_event_id for link in decision.causal_links}
                or not any(item.id == option.id for item in defense_action_options(
                    candidate, actor, operational_plan_id))):
            raise ValueError("operational mobilization requires the current headquarters decision")
    require_authority(candidate, actor, "military")
    # The dated reports make this a valid choice for the actor, but the force
    # owner still cannot send people over a passage that has physically closed
    # since that observation.  Keep the selected route exact: a different
    # current route is a new affordance, never an implicit reroute.
    if not _route_is_current(candidate, option.settlement_id, option.destination_id, option.route_ids):
        raise ValueError("raise route is no longer possible")
    identity = f"detachment:{decision.id}"
    if identity in candidate.society.detachments:
        raise ValueError("raise decision already used")
    candidate.society._select_people(option.group_id, option.count, ())
    stock = candidate.economy.stocks[option.stock_id]
    food = stock.goods.get("food", 0)
    day = candidate.clock.absolute_day
    event = record_event(candidate, "detachment_raised",
                         f"{option.count} soldados partiram com {option.provisions} rações.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         causal_origin=CausalOrigin.ACTOR_DECISION,
                         causal_payload=_decision_authorship(decision),
                         deltas=(_delta("stock", stock.id, "food", food, food - option.provisions),
                                 _delta("detachment", identity, "stage", None, "marching"),
                                 _delta("detachment", identity, "provisions", 0, option.provisions)),
                         cause_ids=_causes(decision.id, stock.last_event_ids.get("food")))
    candidate.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, "food": food - option.provisions},
        "last_event_ids": {**stock.last_event_ids, "food": event.id}})
    detachment = Detachment(id=identity, owner_ref=actor, source_group_id=option.group_id, count=option.count,
                            location_id=option.settlement_id, destination_id=option.destination_id,
                            route_ids=option.route_ids, provisions=option.provisions, stage="marching",
                            started_day=day, due_day=day + 1, decision_event_id=decision.id, last_event_id=event.id)
    candidate.society.detachments[detachment.id] = detachment
    # The detachment is already registered, so ``monthly_workforce`` correctly
    # removes its soldiers from ordinary local availability.  Initial military
    # payroll is nevertheless owed to those same soldiers; make that explicit
    # for this one receipt instead of making detached people available to other
    # employers.
    payroll_available = monthly_workforce(candidate)
    payroll_available[option.group_id] += option.count
    settle_work(candidate, work_id=detachment.id, account_id=option.account_id, stock_id=option.stock_id,
                occupation="soldier", worker_count=option.count, wage=WAGE_PER_SOLDIER,
                available=payroll_available, production_event_id=event.id,
                required_workers={option.group_id: option.count})
    candidate.agenda.schedule(ScheduledSituation(detachment.id, "force", detachment.due_day))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachments[detachment.id]


def _rival_present(world, detachment):
    """Canonical, owner-side check: is another force actually standing here?

    This is never used to build an option. It only lets the material owner
    refuse an occupation that has become impossible, and it discloses nothing:
    the caller learns a refusal, not who is there or with what.
    """
    return any(item.location_id == detachment.location_id and item.owner_ref != detachment.owner_ref
               and item.stage != "disbanded" for item in world.society.detachments.values())


def _standoff_id(left_id, right_id):
    left_id, right_id = sorted((left_id, right_id))
    return f"force-standoff:{left_id}:{right_id}"


def _strength_band(count):
    if count <= 9:
        return "1-9"
    if count <= 24:
        return "10-24"
    if count <= 49:
        return "25-49"
    if count <= 99:
        return "50-99"
    return "100+"


def _sighting_posture(world, detachment_id, leaving_ids=()):
    if detachment_id in set(leaving_ids):
        return "leaving"
    position = world.society.force_positions.get(_position_id(detachment_id))
    return "fortified" if position is not None and position.stage == "prepared" else "present"


def observe_force_contact_sightings(world, standoff, *, leaving_ids=(), extra_cause_ids=()):
    """Refresh only changed bounded readings while Society retains the truth."""
    changes = []
    for notice in world.knowledge.force_contact_notices.values():
        if notice.standoff_id != standoff.id:
            continue
        other_id = next(item for item in standoff.detachment_ids if item != notice.own_detachment_id)
        other = world.society.detachments.get(other_id)
        if other is None:
            continue
        band, posture = _strength_band(other.count), _sighting_posture(world, other.id, leaving_ids)
        if (notice.counterparty_strength_band, notice.counterparty_posture) != (band, posture):
            changes.append((notice, band, posture))
    if not changes:
        return None
    event = record_event(
        world, "force_contact_sighting_observed", "A leitura limitada de uma coluna rival foi atualizada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(delta for notice, band, posture in changes for delta in (
            *(() if band == notice.counterparty_strength_band else
              (_delta("force_contact_notice", notice.id, "counterparty_strength_band",
                      notice.counterparty_strength_band, band),)),
            *(() if posture == notice.counterparty_posture else
              (_delta("force_contact_notice", notice.id, "counterparty_posture",
                      notice.counterparty_posture, posture),)),
            _delta("force_contact_notice", notice.id, "learned_day", notice.learned_day,
                   world.clock.absolute_day))),
        cause_ids=_causes(standoff.last_event_id,
                          *(world.society.detachments[item].last_event_id for item in standoff.detachment_ids
                            if item in world.society.detachments), *extra_cause_ids),
    )
    for notice, band, posture in changes:
        world.knowledge.force_contact_notices[notice.id] = notice.model_copy(update={
            "counterparty_strength_band": band, "counterparty_posture": posture,
            "learned_day": world.clock.absolute_day, "last_event_id": event.id})
    return event


def _active_pair(world, standoff):
    left_id, right_id = standoff.detachment_ids
    left = world.society.detachments.get(left_id)
    right = world.society.detachments.get(right_id)
    if (left is None or right is None or left.owner_ref == right.owner_ref
            or left.stage != "present" or right.stage != "present"
            or left.location_id != standoff.settlement_id or right.location_id != standoff.settlement_id):
        return None
    return left, right


def detect_force_standoffs(world, detachment_id=None):
    """Record actual co-presence as a fact, never as a battle or a demand."""
    candidates = (world.society.detachments.get(detachment_id),) if detachment_id is not None else tuple(
        item for _, item in sorted(world.society.detachments.items()))
    created = []
    for detachment in candidates:
        if detachment is None or detachment.stage != "present":
            continue
        rivals = tuple(item for _, item in sorted(world.society.detachments.items())
                       if item.id != detachment.id and item.stage == "present"
                       and item.location_id == detachment.location_id and item.owner_ref != detachment.owner_ref)
        for rival in rivals:
            identity = _standoff_id(detachment.id, rival.id)
            if identity in world.society.force_standoffs:
                observe_force_contact_sightings(world, world.society.force_standoffs[identity])
                continue
            left_id, right_id = sorted((detachment.id, rival.id))
            standoff = ForceStandoff(id=identity, detachment_ids=(left_id, right_id),
                                     settlement_id=detachment.location_id,
                                     started_day=world.clock.absolute_day, started_event_id="pending",
                                     last_event_id="pending")
            event = record_event(
                world, "armed_standoff_started", "Duas colunas rivais passaram a se encarar; nenhum combate ocorreu.",
                fact_kind=FactKind.STATE_TRANSITION,
                deltas=(_delta("force_standoff", identity, "stage", None, "active"),),
                cause_ids=_causes(detachment.last_event_id, rival.last_event_id),
            )
            standoff = standoff.model_copy(update={"started_event_id": event.id, "last_event_id": event.id})
            world.society.force_standoffs[identity] = standoff
            notices = []
            for own, other in ((detachment, rival), (rival, detachment)):
                notice = ForceContactNotice(
                    id=force_contact_notice_id(identity, own.owner_ref), recipient_ref=own.owner_ref,
                    standoff_id=identity, own_detachment_id=own.id, counterparty_ref=other.owner_ref,
                    settlement_id=detachment.location_id, event_id="pending", learned_day=world.clock.absolute_day,
                    counterparty_strength_band=_strength_band(other.count),
                    counterparty_posture=_sighting_posture(world, other.id),
                    last_event_id="pending",
                )
                notices.append(notice)
            observation = record_event(
                world, "armed_standoff_observed", "As duas colunas reconheceram uma presença armada rival.",
                fact_kind=FactKind.STATE_TRANSITION,
                deltas=tuple(delta for notice in notices for delta in (
                    _delta("force_contact_notice", notice.id, "observation", None, identity),
                    _delta("force_contact_notice", notice.id, "counterparty_strength_band", None,
                           notice.counterparty_strength_band),
                    _delta("force_contact_notice", notice.id, "counterparty_posture", None,
                           notice.counterparty_posture),
                    _delta("force_contact_notice", notice.id, "learned_day", None, notice.learned_day))),
                cause_ids=(event.id,),
            )
            for notice in notices:
                world.knowledge.force_contact_notices[notice.id] = notice.model_copy(
                    update={"event_id": observation.id, "last_event_id": observation.id})
            from .force_contact_policy import schedule_contact_review
            for notice in notices:
                schedule_contact_review(world, notice, world.clock.absolute_day + 1)
            created.append(world.society.force_standoffs[identity])
    return tuple(created)


def _resolve_standoffs_for(world, detachment_id, cause_event_id):
    """Removing physical co-presence closes its factual contact, never a war."""
    resolved = []
    for standoff in tuple(world.society.force_standoffs.values()):
        if standoff.stage != "active" or detachment_id not in standoff.detachment_ids:
            continue
        if _active_pair(world, standoff) is not None:
            continue
        # A voluntary withdrawal is the one material transition that a rival
        # can physically read as departure before the contact freezes.
        if world.society.detachments.get(detachment_id, None) is not None and \
                world.society.detachments[detachment_id].stage == "marching":
            sighting = observe_force_contact_sightings(world, standoff, leaving_ids=(detachment_id,))
            if sighting is not None:
                standoff = world.society.force_standoffs[standoff.id]
        event = record_event(
            world, "armed_standoff_resolved", "A co-presença armada cessou sem combate.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("force_standoff", standoff.id, "stage", "active", "resolved"),),
            cause_ids=_causes(cause_event_id, standoff.last_event_id),
        )
        world.society.force_standoffs[standoff.id] = standoff.model_copy(
            update={"stage": "resolved", "resolved_day": world.clock.absolute_day, "last_event_id": event.id})
        resolved.append(world.society.force_standoffs[standoff.id])
    return tuple(resolved)


def standoff_options(world, actor):
    """A known participant may stand down; it may not choose any harm."""
    if not _commands(world, actor):
        return ()
    options = []
    for notice in world.knowledge.force_contacts_for_actor(actor):
        standoff = world.society.force_standoffs.get(notice.standoff_id)
        if standoff is None or standoff.stage != "active":
            continue
        own = world.society.detachments.get(notice.own_detachment_id)
        if (own is None or own.owner_ref != actor or own.stage != "present"
                or own.location_id != standoff.settlement_id
                or notice.settlement_id != standoff.settlement_id):
            continue
        options.append(StandoffOption(
            id=f"force-standoff:{standoff.id}:{own.last_event_id}:{standoff.last_event_id}:stand-down",
            actor_ref=actor, standoff_id=standoff.id, detachment_id=own.id))
    return tuple(sorted(options, key=lambda item: item.id))


def force_options(world, actor):
    """What a standing detachment of this institution could decide today.

    Options are composed from the actor's own detachments and its own dated
    settlement reports. No foreign detachment is read here: an occupier seen in
    the actor's own report is valid knowledge, a rival column is not.
    """
    if not _commands(world, actor):
        return ()
    options = []
    for _, detachment in sorted(world.society.detachments.items()):
        if detachment.owner_ref != actor or detachment.stage == "disbanded":
            continue
        base = f"force:{detachment.id}:{detachment.last_event_id}"
        options.append(ForceOption(f"{base}:disband", actor, detachment.id, "disband"))
        settlement = world.society.settlements[detachment.location_id]
        report = world.knowledge.settlement_report(actor, detachment.location_id)
        if (detachment.stage == "present" and detachment.provisions > 0
                and settlement.administrator_id != actor.id
                and report is not None and report.settlement_id == detachment.location_id
                and report.occupier_id is None):
            options.append(ForceOption(f"{base}:occupy", actor, detachment.id, "occupy"))
    return tuple(sorted((*options, *garrison_options(world, actor)), key=lambda item: item.id))


def garrison_options(world, actor):
    """A supplied occupation, or the actor's own settlement, may take a duty.

    An occupied settlement's duty ("garrison") does not itself grant
    occupation: the settlement must already be occupied by this column.  A
    "defend" duty at the actor's own administered settlement requires no
    occupation and changes none; it only lets an already-present, already-paid
    column become a durable defensive presence at home.  Food is the column's
    current ration reserve and money is the owner's current account; both are
    checked again by the owner.
    """
    if not _commands(world, actor):
        return ()
    options = []
    for detachment in sorted(world.society.detachments.values(), key=lambda item: item.id):
        if detachment.owner_ref != actor or detachment.stage != "present":
            continue
        settlement = world.society.settlements[detachment.location_id]
        existing = world.society.garrisons.get(f"garrison:{detachment.id}")
        if (existing is not None and existing.stage == "active"
                and existing.settlement_id == settlement.id):
            options.append(GarrisonOption(
                id=f"garrison-withdraw:{detachment.id}:{existing.last_event_id}",
                actor_ref=actor, detachment_id=detachment.id, settlement_id=settlement.id,
                account_id=existing.account_id, daily_wage=0, kind="withdraw"))
            account = world.economy.accounts.get(existing.account_id)
            if account is not None and account.owner_ref == actor:
                for replacement in sorted(world.society.detachments.values(), key=lambda item: item.id):
                    if (replacement.id == detachment.id or replacement.owner_ref != actor
                            or replacement.stage != "present" or replacement.location_id != settlement.id
                            or replacement.provisions < replacement.count
                            or world.society.garrisons.get(f"garrison:{replacement.id}") is not None):
                        continue
                    wage = replacement.count * GARRISON_WAGE_PER_SOLDIER_DAY
                    if account.balance < wage:
                        continue
                    options.append(GarrisonRotationOption(
                        id=f"garrison-rotate:{detachment.id}:{replacement.id}:{existing.last_event_id}:"
                           f"{replacement.last_event_id}:{account.id}",
                        actor_ref=actor, current_detachment_id=detachment.id,
                        replacement_detachment_id=replacement.id, settlement_id=settlement.id,
                        account_id=account.id, daily_wage=wage))
            continue
        if settlement.occupier_id == actor.id:
            kind = "garrison"
        elif settlement.administrator_id == actor.id:
            kind = "defend"
        else:
            continue
        account = _own_account(world, actor)
        wage = detachment.count * GARRISON_WAGE_PER_SOLDIER_DAY
        if (detachment.provisions < detachment.count or account is None or account.balance < wage
                or existing is not None):
            continue
        options.append(GarrisonOption(
            id=f"garrison:{detachment.id}:{detachment.last_event_id}:{account.id}:{kind}",
            actor_ref=actor, detachment_id=detachment.id, settlement_id=settlement.id,
            account_id=account.id, daily_wage=wage, kind=kind))
    return tuple(options)


def _route_is_current(world, origin_id, destination_id, route_ids):
    """Owner-side Map revalidation for one exact selected route."""
    if not route_ids or origin_id not in world.society.settlements or destination_id not in world.society.settlements:
        return False
    region = world.society.settlements[origin_id].region_id
    target = world.society.settlements[destination_id].region_id
    seen = {region}
    for route_id in route_ids:
        route = world.map.routes.get(route_id)
        if (route is None or region not in route.endpoint_region_ids or not route.allows_resource("food")
                or world.map.get_route_operational_capacity(route_id) <= 0):
            return False
        region = next(item for item in route.endpoint_region_ids if item != region)
        if region in seen:
            return False
        seen.add(region)
    return region == target


def headquarters_withdrawal_options(world, institution_ref, report):
    """Enumerate withdrawals grounded in the current QG's own battle and route reports."""
    from .campaign_supply import campaign_baggage_ready_for_departure

    headquarters = headquarters_holder(world, institution_ref)
    if (institution_ref.kind != "polity" or headquarters is None
            or not can_actor_act_for(world, headquarters, institution_ref, "operations")
            or not can_actor_act_for(world, institution_ref, institution_ref, "military")
            or report.recipient_ref != headquarters or report.channel != "settlement_bulletin"
            or not 0 <= world.clock.absolute_day - report.observed_day < 30):
        return ()
    options = []
    for reading in report.field_engagements:
        engagement = world.society.field_engagements.get(reading.engagement_id)
        event = world.event_index().get(reading.event_id)
        if (engagement is None or event is None or engagement.status != "resolved"
                or engagement.last_event_id != event.id
                or institution_ref not in {engagement.challenger_ref, engagement.defender_ref}
                or reading.winner_ref != engagement.winner_ref
                or engagement.settlement_id != report.settlement_id
                or event.event_type != "field_engagement_resolved"):
            continue
        own_detachment_id = (engagement.challenger_detachment_id
                             if engagement.challenger_ref == institution_ref
                             else engagement.defender_detachment_id)
        detachment = world.society.detachments.get(own_detachment_id)
        if (detachment is None or detachment.owner_ref != institution_ref or detachment.stage != "present"
                or detachment.location_id != report.settlement_id or detachment.provisions <= 0
                or not campaign_baggage_ready_for_departure(world, detachment)):
            continue
        plan = next((item for item in world.strategy.plans.values()
                     if item.detachment_id == detachment.id and item.stage in {"mobilized", "blocked"}), None)
        for destination_id, destination in sorted(world.society.settlements.items()):
            if (destination.administrator_id != institution_ref.id or destination_id == detachment.location_id):
                continue
            destination_report = world.knowledge.settlement_report(headquarters, destination_id)
            if (destination_report is None or destination_report.channel not in {
                    "local_settlement_report", "settlement_bulletin"}
                    or not 0 <= world.clock.absolute_day - destination_report.observed_day < 30):
                continue
            route_ids = known_supply_path(world, headquarters, detachment.location_id, destination_id, "food")
            if not route_ids:
                continue
            route_reports = tuple(world.knowledge.route_report(headquarters, route_id) for route_id in route_ids)
            if any(item is None or not 0 <= world.clock.absolute_day - item.observed_day < 30
                   for item in route_reports):
                continue
            report_ids = tuple(item.event_id for item in route_reports)
            identity = (f"hq-withdraw:{institution_ref.id}:{engagement.id}:{detachment.id}:"
                        f"{destination_id}:{'-'.join(route_ids)}:{report.event_id}:{'-'.join(report_ids)}")
            options.append(HeadquartersWithdrawalOption(
                id=identity, actor_ref=headquarters, institution_ref=institution_ref,
                plan_id=plan.id if plan is not None else None, engagement_id=engagement.id,
                engagement_event_id=event.id, settlement_report_event_id=report.event_id,
                detachment_id=detachment.id, destination_id=destination_id,
                route_ids=tuple(route_ids), route_report_ids=report_ids))
    return tuple(sorted(options, key=lambda item: item.id))


def campaign_logistics_withdrawal_options(world, institution_ref, plan_id=None, *, detachment_id=None):
    """Return only QG-known withdrawals after delayed campaign freight resolved.

    A dispatched notice or live parcel blocks departure. An open, undispatched
    notice may be lapsed by the explicit withdrawal decision. Delay evidence is
    historical and factual; it only unlocks a later choice, never moves cargo.
    A plan-linked operation retains its political mandate; an unplanned column
    may be reviewed from its explicit raise decision.
    """
    from .campaign_supply import _reported_delay_events, campaign_baggage_ready_for_departure
    from .strategy_response import _plan_status, _political_order

    plan = world.strategy.plans.get(plan_id)
    objective = world.strategy.objectives.get(plan.objective_id) if plan is not None else None
    if plan_id is not None and (plan is None or objective is None or plan.stage != "mobilized"
                                or plan.detachment_id is None or objective.actor_ref != institution_ref
                                or _plan_status(world, objective)[0] is not None
                                or _political_order(world, plan, objective) is None):
        return ()
    if plan is None and detachment_id is None:
        return ()
    target_detachment_id = plan.detachment_id if plan is not None else detachment_id
    if plan is None and any(item.detachment_id == target_detachment_id
                            for item in world.strategy.plans.values()):
        return ()
    headquarters = headquarters_holder(world, institution_ref)
    detachment = world.society.detachments.get(target_detachment_id)
    if (headquarters is None or not can_actor_act_for(world, headquarters, institution_ref, "operations")
            or not can_actor_act_for(world, institution_ref, institution_ref, "military")
            or detachment is None or detachment.owner_ref != institution_ref
            or detachment.stage != "present" or detachment.provisions <= 0
            or any(notice.detachment_id == detachment.id and notice.state == "dispatched"
                   for notice in world.knowledge.campaign_supply_notices.values())
            or not campaign_baggage_ready_for_departure(world, detachment, ignore_notice=True)):
        return ()
    notices = tuple(sorted((notice for notice in world.knowledge.campaign_supply_notices.values()
                            if notice.detachment_id == detachment.id
                            and notice.recipient_ref == institution_ref
                            and notice.state in {"open", "fulfilled", "lapsed"}
                            and _reported_delay_events(world, notice)), key=lambda item: item.id))
    if not notices:
        return ()
    delay_event_ids = tuple(sorted({event_id for notice in notices
                                    for event_id in _reported_delay_events(world, notice)}))
    position = world.knowledge.settlement_report(headquarters, detachment.location_id)
    if (position is None or position.recipient_ref != headquarters
            or position.settlement_id != detachment.location_id
            or position.channel not in {"local_settlement_report", "settlement_bulletin"}
            or not 0 <= world.clock.absolute_day - position.observed_day < 30):
        return ()
    options = []
    for destination_id, destination in sorted(world.society.settlements.items()):
        if destination_id == detachment.location_id or destination.administrator_id != institution_ref.id:
            continue
        destination_report = world.knowledge.settlement_report(headquarters, destination_id)
        if (destination_report is None or destination_report.settlement_id != destination_id
                or not 0 <= world.clock.absolute_day - destination_report.observed_day < 30):
            continue
        route_ids = known_supply_path(world, headquarters, detachment.location_id, destination_id, "food")
        if not route_ids or not _route_is_current(world, detachment.location_id, destination_id, route_ids):
            continue
        route_reports = tuple(world.knowledge.route_report(headquarters, route_id) for route_id in route_ids)
        if any(report is None or not 0 <= world.clock.absolute_day - report.observed_day < 30
               for report in route_reports):
            continue
        report_ids = tuple(report.event_id for report in route_reports)
        plan_identity = plan.id if plan is not None else "standalone"
        option_id = (f"campaign-delay-withdraw:{plan_identity}:{detachment.id}:{position.event_id}:"
                     f"{'-'.join(item.id for item in notices)}:{destination_id}:"
                     f"{'-'.join(route_ids)}:{'-'.join(report_ids)}")
        options.append(CampaignLogisticsWithdrawalOption(
            id=option_id, actor_ref=headquarters, institution_ref=institution_ref,
            plan_id=plan.id if plan is not None else None,
            detachment_id=detachment.id, delay_notice_ids=tuple(item.id for item in notices),
            delay_notice_event_ids=tuple(sorted({event_id for item in notices
                                                 for event_id in (item.event_id, item.last_event_id)})),
            delay_event_ids=delay_event_ids, position_report_id=position.event_id,
            destination_id=destination_id, route_ids=tuple(route_ids), route_report_ids=report_ids))
    return tuple(sorted(options, key=lambda item: item.id))


def withdraw_campaign_after_supply_delay(world, institution_ref, plan_id, option_id, decision_event_id,
                                         *, detachment_id=None):
    """Recompose QG logistics evidence, then let Force start a physical return."""
    candidate = deepcopy(world)
    option = next((item for item in campaign_logistics_withdrawal_options(
        candidate, institution_ref, plan_id, detachment_id=detachment_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("campaign logistics withdrawal option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id, WITHDRAW_ACTION)
    if decided_by != option.actor_ref or decision.decision != option.decision():
        raise ValueError("campaign logistics withdrawal has the wrong decision")
    detachment = candidate.society.detachments[option.detachment_id]
    if not _route_is_current(candidate, detachment.location_id, option.destination_id, option.route_ids):
        raise ValueError("campaign logistics withdrawal route is no longer current")
    from .campaign_supply import _lapse_campaign_notices
    supply_lapsed = _lapse_campaign_notices(candidate, detachment.id, decision.id)
    owner_option = WithdrawalOption(id=option.id, actor_ref=institution_ref,
                                    detachment_id=option.detachment_id,
                                    destination_id=option.destination_id, route_ids=option.route_ids)
    movement = _begin_withdrawal(candidate, institution_ref, owner_option, decision.id,
                                 decision_actor_ref=option.actor_ref)
    if plan_id is not None:
        from .strategy_response import _set_plan
        plan = candidate.strategy.plans[plan_id]
        _set_plan(candidate, plan, "withdrawn", blocker="QG encerrou a campanha após atraso de abastecimento",
                  causes=(decision.id, movement.id, supply_lapsed.id if supply_lapsed else None,
                          *option.delay_event_ids,
                          *option.delay_notice_event_ids, option.position_report_id, *option.route_report_ids),
                  detachment_id=detachment.id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.strategy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachments[option.detachment_id]


def withdraw_detachment_by_headquarters(world, institution_ref, report_event_id, option_id, decision_event_id):
    """Revalidate a QG's own sourced decision before the force owner begins retreat."""
    candidate = deepcopy(world)
    headquarters = headquarters_holder(candidate, institution_ref)
    report = next((item for item in candidate.knowledge.settlement_reports.values()
                   if item.recipient_ref == headquarters and item.event_id == report_event_id), None)
    option = next((item for item in headquarters_withdrawal_options(candidate, institution_ref, report)
                   if item.id == option_id), None) if report is not None else None
    if option is None:
        raise ValueError("headquarters withdrawal option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id, WITHDRAW_ACTION)
    if (decided_by != headquarters or decision.decision != option.decision()
            or not can_actor_act_for(candidate, headquarters, institution_ref, "operations")
            or not can_actor_act_for(candidate, institution_ref, institution_ref, "military")):
        raise ValueError("headquarters withdrawal has the wrong authority or decision")
    detachment = candidate.society.detachments[option.detachment_id]
    if (detachment.stage != "present" or detachment.owner_ref != institution_ref
            or not _route_is_current(candidate, detachment.location_id, option.destination_id, option.route_ids)):
        raise ValueError("headquarters withdrawal is no longer materially possible")
    owner_option = WithdrawalOption(
        id=option.id, actor_ref=institution_ref, detachment_id=option.detachment_id,
        destination_id=option.destination_id, route_ids=option.route_ids)
    movement = _begin_withdrawal(candidate, institution_ref, owner_option, decision.id,
                                 decision_actor_ref=option.actor_ref)
    if option.plan_id is not None:
        from .strategy_response import _set_plan
        plan = candidate.strategy.plans.get(option.plan_id)
        if plan is None or plan.detachment_id != detachment.id or plan.stage not in {"mobilized", "blocked"}:
            raise ValueError("headquarters campaign plan is no longer active")
        _set_plan(candidate, plan, "withdrawn", blocker="QG encerrou a campanha após relatório de combate",
                  causes=(decision.id, movement.id), detachment_id=detachment.id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.strategy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachments[option.detachment_id]


def withdrawal_options(world, actor, *, detachment_id=None, allow_open_campaign_supply=False,
                       campaign_authorized=False):
    """Only own present columns may choose a reported route to own government.

    The composition intentionally does not consult any foreign detachment,
    inventory, route plan or authority.  A real pending campaign shipment
    makes the option absent rather than relocating its cargo.
    """
    # A persisted siege is already an institutionally authorized campaign;
    # its owner may choose to end that campaign even when no named commander
    # was appointed. Ordinary force withdrawal still requires a command.
    if not _commands(world, actor) and not campaign_authorized:
        return ()
    from .campaign_supply import campaign_baggage_ready_for_departure

    options = []
    for _, detachment in sorted(world.society.detachments.items()):
        if (detachment.owner_ref != actor or detachment.stage != "present" or detachment.provisions <= 0
                or (detachment_id is not None and detachment.id != detachment_id)
                or not campaign_baggage_ready_for_departure(
                    world, detachment, ignore_notice=allow_open_campaign_supply)):
            continue
        for destination_id, settlement in sorted(world.society.settlements.items()):
            if destination_id == detachment.location_id or settlement.administrator_id != actor.id:
                continue
            report = world.knowledge.settlement_report(actor, destination_id)
            if report is None or report.settlement_id != destination_id:
                continue
            route_ids = known_supply_path(world, actor, detachment.location_id, destination_id, "food")
            if not route_ids:
                continue
            options.append(WithdrawalOption(
                id=(f"withdraw:{detachment.id}:{detachment.last_event_id}:{destination_id}:{'-'.join(route_ids)}"),
                actor_ref=actor, detachment_id=detachment.id, destination_id=destination_id,
                route_ids=tuple(route_ids)))
    return tuple(sorted(options, key=lambda item: item.id))


def _position_id(detachment_id):
    return f"force-position:{detachment_id}"


def force_position_options(world, actor, *, detachment_id=None):
    """Current preparation choices, composed only from the owner's column and Map.

    The optional anchor is only an existing site in this settlement's region.
    It creates no terrain rule, defensive value, route restriction or control.
    """
    if not _commands(world, actor):
        return ()
    options = []
    for detachment in world.society.detachments.values():
        if (detachment.owner_ref != actor or detachment.stage != "present"
                or (detachment_id is not None and detachment.id != detachment_id)
                or _position_id(detachment.id) in world.society.force_positions
                or detachment.provisions < POSITION_PREPARATION_DAYS * detachment.count):
            continue
        settlement = world.society.settlements[detachment.location_id]
        anchors = (None, *sorted(site.id for site in world.map.infrastructure_sites.values()
                                 if settlement.region_id in site.region_ids))
        for anchor_site_id in anchors:
            anchor = anchor_site_id or "none"
            options.append(ForcePositionOption(
                id=f"force-position:{detachment.id}:{detachment.last_event_id}:{settlement.id}:{anchor}",
                actor_ref=actor, detachment_id=detachment.id, settlement_id=settlement.id,
                anchor_site_id=anchor_site_id))
    return tuple(sorted(options, key=lambda item: item.id))


def prepare_force_position(world, actor, option_id, decision_event_id):
    """Begin a three-day stationary preparation; only daily upkeep can finish it."""
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, PREPARE_POSITION_ACTION)
    if decided_by != actor:
        raise ValueError("force position has the wrong actor")
    option = next((item for item in force_position_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("force position option is stale or unknown")
    require_authority(candidate, actor, "military")
    detachment = candidate.society.detachments[option.detachment_id]
    position = ForcePosition(id=_position_id(detachment.id), detachment_id=detachment.id,
                             settlement_id=detachment.location_id, anchor_site_id=option.anchor_site_id,
                             started_day=candidate.clock.absolute_day,
                             ready_day=candidate.clock.absolute_day + POSITION_PREPARATION_DAYS,
                             last_event_id="pending")
    event = record_event(
        candidate, "force_position_preparing", "A coluna iniciou três dias de preparo no local onde está.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload=_decision_authorship(decision),
        deltas=(_delta("force_position", position.id, "stage", None, "preparing"),
                _delta("force_position", position.id, "settlement_id", None, position.settlement_id),
                _delta("force_position", position.id, "anchor_site_id", None, position.anchor_site_id),
                _delta("force_position", position.id, "ready_day", None, position.ready_day)),
        cause_ids=_causes(decision.id, detachment.last_event_id))
    candidate.society.force_positions[position.id] = position.model_copy(update={"last_event_id": event.id})
    candidate.agenda.schedule(ScheduledSituation(position.id, "force_preparation", position.ready_day))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.force_positions[position.id]


def _abandon_force_position(world, detachment, *, cause_ids=()):
    """Leaving, lapsed supply or location change never erases preparation silently."""
    position = world.society.force_positions.get(_position_id(detachment.id))
    if position is None:
        return None
    from .assembly_denial import revoke_assembly_denials_for
    revoke_assembly_denials_for(world, detachment, cause_ids=_causes(position.last_event_id, *cause_ids))
    event = record_event(
        world, "force_position_abandoned", "A posição foi abandonada porque a coluna não permaneceu no local.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("force_position", position.id, "stage", position.stage, None),),
        cause_ids=_causes(position.last_event_id, detachment.last_event_id, *cause_ids))
    del world.society.force_positions[position.id]
    world.agenda.cancel(position.id)
    return event


def _refresh_position_sightings(world, detachment, event):
    for standoff in tuple(world.society.force_standoffs.values()):
        if standoff.stage == "active" and detachment.id in standoff.detachment_ids:
            observe_force_contact_sightings(world, standoff, extra_cause_ids=(event.id,))


def resolve_force_positions(world, situations):
    """A dated completion proves three supplied stationary days, nothing else."""
    for situation in sorted(situations, key=lambda item: item.id):
        if situation.kind != "force_preparation":
            raise ValueError("unknown force preparation")
        position = world.society.force_positions.get(situation.id)
        # A force resolver may have lapsed or dissolved the column earlier in
        # this same dated turn, recording the explicit abandonment itself.
        if position is None:
            continue
        if position.stage != "preparing" or position.ready_day != world.clock.absolute_day:
            raise ValueError("inconsistent force preparation deadline")
        detachment = world.society.detachments.get(position.detachment_id)
        if (detachment is None or detachment.stage != "present"
                or detachment.location_id != position.settlement_id):
            if detachment is not None:
                _abandon_force_position(world, detachment, cause_ids=(position.last_event_id,))
            continue
        event = record_event(
            world, "force_position_prepared", "A coluna concluiu o preparo sem ganhar território ou iniciar combate.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("force_position", position.id, "stage", "preparing", "prepared"),),
            cause_ids=_causes(position.last_event_id, detachment.last_event_id))
        world.society.force_positions[position.id] = position.model_copy(update={"stage": "prepared",
                                                                                   "last_event_id": event.id})
        _refresh_position_sightings(world, detachment, event)
        from .rites import observe_rites
        observe_rites(world, settlement_id=detachment.location_id)


def _record(world, detachment, updated, event_type, content, *, deltas=(), causes=(), causal_payload=None,
            causal_origin=CausalOrigin.DETERMINISTIC):
    lifted = ()
    assembly_lifted = ()
    command_released = None
    training_lapsed = ()
    if (updated.stage != "present" or updated.location_id != detachment.location_id
            or updated.provisions < updated.count * RATIONS_PER_SOLDIER_DAY):
        from .force_training import lapse_training_for
        training_lapsed = lapse_training_for(world, detachment, cause_ids=causes)
    # A commander assigned at departure rides with the same physical column.
    # A pre-existing local command still ends when a present column leaves.
    command = world.society.detachment_commands.get(detachment.id)
    attached_command = False
    if command is not None:
        from .force_command import command_is_attached_to_march, revoke_detachment_command_for
        attached_command = (command_is_attached_to_march(world, command)
                            and updated.stage in {"marching", "present"}
                            and (updated.stage == "marching" or updated.location_id == updated.destination_id))
        if attached_command:
            if event_type in {"detachment_marched", "detachment_arrived"}:
                causes = _causes(*causes, command.last_event_id)
        elif updated.stage != "present" or updated.location_id != detachment.location_id:
            command_released = revoke_detachment_command_for(world, detachment, cause_ids=causes)
    elif updated.stage != "present" or updated.location_id != detachment.location_id:
        from .force_command import revoke_detachment_command_for
        command_released = revoke_detachment_command_for(world, detachment, cause_ids=causes)
    if (updated.stage != "present" or updated.location_id != detachment.location_id
            or updated.provisions < updated.count * RATIONS_PER_SOLDIER_DAY):
        from .assembly_denial import revoke_assembly_denials_for
        assembly_lifted = revoke_assembly_denials_for(world, detachment, cause_ids=causes)
    if updated.stage != "present" or updated.location_id != detachment.location_id:
        # Departure, movement, dissolution and lapse end only this physical
        # route cause before the force transition itself is recorded.
        from .settlement_investment import revoke_settlement_investments_for
        from .route_interdiction import revoke_route_interdictions_for
        lifted = (*revoke_settlement_investments_for(world, detachment, cause_ids=causes),
                  *revoke_route_interdictions_for(world, detachment, cause_ids=causes))
    abandoned = None
    position = world.society.force_positions.get(_position_id(detachment.id))
    if position is not None and (updated.stage != "present" or updated.location_id != position.settlement_id):
        abandoned = _abandon_force_position(world, detachment, cause_ids=causes)
    event = record_event(world, event_type, content, fact_kind=FactKind.STATE_TRANSITION,
                         causal_origin=causal_origin, causal_payload=causal_payload, deltas=deltas,
                         cause_ids=_causes(detachment.last_event_id, *causes,
                                            *(item.id for item in lifted),
                                            *(item.id for item in assembly_lifted),
                                            *(item.id for item in training_lapsed),
                                            *((command_released.id,) if command_released is not None else ()),
                                            *((abandoned.id,) if abandoned is not None else ())))
    world.society.detachments[detachment.id] = updated.model_copy(update={"last_event_id": event.id})
    # A dated resolution has already popped the current situation.  Manual
    # receipts can also replace a pending one, so make rescheduling idempotent.
    world.agenda.cancel(detachment.id)
    if updated.stage == "disbanded":
        # The record stays as history, with its payroll; only the duty ends.
        pass
    else:
        world.agenda.schedule(ScheduledSituation(detachment.id, "force", updated.due_day))
    return event


def _return_home(world, detachment):
    """Survivors rejoin a real cohort exactly where the detachment stands."""
    group = world.society.population[detachment.source_group_id]
    if group.settlement_id == detachment.location_id:
        return ()
    target_id = world.society.transfer_people(detachment.source_group_id, detachment.location_id,
                                              "soldier", detachment.count)
    return (_delta("population_group", detachment.source_group_id, "count", group.count,
                   group.count - detachment.count),
            _delta("population_group", target_id, "count",
                   world.society.population[target_id].count - detachment.count,
                   world.society.population[target_id].count))


def _clear_occupation(world, detachment):
    settlement = world.society.settlements[detachment.location_id]
    if settlement.occupier_id != detachment.owner_ref.id:
        return ()
    from .territorial_control import lapse_territorial_control
    lapse_territorial_control(
        world, settlement.id,
        cause_ids=(detachment.last_event_id,),
        reason="O controle territorial cessou quando a coluna deixou de sustentar a ocupação.",
    )
    world.society.set_occupation(settlement.id, None)
    return (_delta("settlement", settlement.id, "occupier_id", detachment.owner_ref.id, None),)


def _lapse_garrison(world, detachment, *, reason, cause_ids=()):
    """End a garrison only through a dated material failure."""
    identity = f"garrison:{detachment.id}"
    garrison = world.society.garrisons.get(identity)
    if garrison is None or garrison.stage != "active":
        return None
    deltas = [_delta("garrison", identity, "stage", "active", "lapsed")]
    deltas.extend(_clear_occupation(world, detachment))
    event = record_event(
        world, "garrison_lapsed", reason, fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(deltas), cause_ids=_causes(garrison.last_event_id, detachment.last_event_id, *cause_ids))
    world.society.garrisons[identity] = garrison.model_copy(update={"stage": "lapsed", "last_event_id": event.id})
    from .territorial_control import lapse_territorial_control
    lapse_territorial_control(world, garrison.settlement_id, cause_ids=(event.id,),
                              reason="O controle territorial cessou com a perda material da guarnição.")
    return event


def collapse_garrison_for_siege(world, garrison_id, *, campaign_event_id):
    """End only the defensive duty after a recorded material breach.

    A siege does not move the defender's people, assign the attacker as
    occupier, or transfer administration.  The detachment consequently stays
    in place for a later owner decision; this owner changes just the real
    garrison lifecycle and records the breach fact that caused it.
    """
    garrison = world.society.garrisons.get(garrison_id)
    if garrison is None or garrison.stage != "active":
        raise ValueError("siege can collapse only its current active garrison")
    detachment = world.society.detachments.get(garrison.detachment_id)
    if (detachment is None or detachment.stage != "present"
            or detachment.location_id != garrison.settlement_id):
        raise ValueError("siege garrison no longer has its physical detachment")
    event = record_event(
        world, "garrison_collapsed",
        "A guarnição colapsou após a brecha material registrada pelo cerco; nenhuma administração mudou.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("garrison", garrison.id, "stage", "active", "collapsed"),),
        cause_ids=_causes(campaign_event_id, garrison.last_event_id, detachment.last_event_id))
    world.society.garrisons[garrison.id] = garrison.model_copy(
        update={"stage": "collapsed", "last_event_id": event.id})
    from .territorial_control import lapse_territorial_control
    lapse_territorial_control(world, garrison.settlement_id, cause_ids=(event.id,),
                              reason="O controle territorial cessou quando a guarnição colapsou.")
    return event


def _maintain_garrison(world, detachment):
    """Charge one dated payroll after the column consumed today's ration.

    Continuity holds for either an occupied duty or a defensive duty at the
    owner's own administered settlement; neither implies automatic defense.
    """
    identity = f"garrison:{detachment.id}"
    garrison = world.society.garrisons.get(identity)
    if garrison is None or garrison.stage != "active":
        return None
    settlement = world.society.settlements.get(garrison.settlement_id)
    account = world.economy.accounts.get(garrison.account_id)
    source_group = world.society.population.get(detachment.source_group_id)
    wage = detachment.count * GARRISON_WAGE_PER_SOLDIER_DAY
    authorized = settlement is not None and (settlement.occupier_id == detachment.owner_ref.id
                                             or settlement.administrator_id == detachment.owner_ref.id)
    if (not authorized
            or detachment.stage != "present" or detachment.location_id != settlement.id
            or account is None or account.owner_ref != detachment.owner_ref or account.balance < wage
            or source_group is None):
        return _lapse_garrison(world, detachment,
                                reason="A guarnição cessou porque sua manutenção monetária deixou de ser possível.")
    household_id = f"household:{source_group.id}"
    household = world.economy.accounts.get(household_id)
    if household is not None and household.owner_ref != EntityRef("population_group", source_group.id):
        return _lapse_garrison(world, detachment,
                                reason="A guarnição cessou porque a conta salarial de sua coorte era inválida.")
    if household is None:
        household = MoneyAccount(id=household_id,
                                 owner_ref=EntityRef("population_group", source_group.id), balance=0)
        world.economy.accounts[household.id] = household
    event = record_event(
        world, "garrison_maintained", "A guarnição pagou a manutenção diária com o tesouro de seu proprietário.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("account", account.id, "balance", account.balance, account.balance - wage),
                _delta("account", household.id, "balance", household.balance, household.balance + wage),
                _delta("garrison", identity, "maintenance", 0, wage)),
        cause_ids=_causes(garrison.last_event_id, detachment.last_event_id, account.last_event_id,
                          source_group.last_event_id, household.last_event_id))
    world.economy.accounts[account.id] = account.model_copy(
        update={"balance": account.balance - wage, "last_event_id": event.id})
    world.economy.accounts[household.id] = household.model_copy(
        update={"balance": household.balance + wage, "last_event_id": event.id})
    world.society.garrisons[identity] = garrison.model_copy(update={"last_event_id": event.id})
    return event


def _withdraw_garrison(world, actor, option, decision):
    """End only the military duty by an explicit owner decision."""
    identity = f"garrison:{option.detachment_id}"
    garrison = world.society.garrisons.get(identity)
    detachment = world.society.detachments.get(option.detachment_id)
    if (garrison is None or garrison.stage != "active" or detachment is None
            or detachment.owner_ref != actor or detachment.stage != "present"
            or detachment.location_id != garrison.settlement_id):
        raise ValueError("garrison withdrawal is no longer possible")
    event = record_event(
        world, "garrison_withdrawn",
        "A instituição retirou voluntariamente o dever da guarnição; a coluna permaneceu no local.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": decision.id, "actor_ref": actor.to_dict(),
                        "selected_affordance_id": decision.decision["selected_affordance_id"]},
        deltas=(_delta("garrison", identity, "stage", "active", "withdrawn"),),
        cause_ids=_causes(decision.id, garrison.last_event_id, detachment.last_event_id),
    )
    world.society.garrisons[identity] = garrison.model_copy(update={
        "stage": "withdrawn", "last_event_id": event.id})
    from .territorial_control import lapse_territorial_control
    lapse_territorial_control(
        world, garrison.settlement_id, cause_ids=(event.id,),
        reason="O controle territorial cessou quando a instituição retirou a guarnição.",
    )
    return event


def _dissolve(world, detachment, event_type, content, causes=(), *, decision=None, actor=None):
    """One fact: occupation clears, people land, the duty ends."""
    garrison_event = _lapse_garrison(world, detachment,
                                      reason="A guarnição cessou quando a coluna perdeu sua sustentação física.",
                                      cause_ids=causes)
    deltas = (*_clear_occupation(world, detachment),)
    # People move before the receipt so the delta states the real counts.
    moved = _return_home(world, detachment)
    ended = detachment.model_copy(update={"stage": "disbanded", "provisions": 0,
                                          "due_day": world.clock.absolute_day})
    causal_payload = None
    causal_origin = CausalOrigin.DETERMINISTIC
    if decision is not None:
        if actor is None or decision.decision is None:
            raise ValueError("voluntary disband requires its actor decision")
        causal_origin = CausalOrigin.ACTOR_DECISION
        causal_payload = {"decision_event_id": decision.id, "actor_ref": actor.to_dict(),
                          "selected_affordance_id": decision.decision["selected_affordance_id"]}
    event = _record(world, detachment, ended, event_type, content,
                    deltas=(*deltas, *moved,
                            _delta("detachment", detachment.id, "stage", detachment.stage, "disbanded")),
                    causes=_causes(*causes, *((garrison_event.id,) if garrison_event else ())),
                    causal_origin=causal_origin, causal_payload=causal_payload)
    # A campaign bag is an Economy stock, never a hidden field on a force.
    # Dispose of anything already co-located before this physical presence is
    # forgotten; later cargo is handled by the same campaign owner.
    from .campaign_supply import dispose_campaign_baggage
    dispose_campaign_baggage(world, detachment, event.id)
    _resolve_standoffs_for(world, detachment.id, event.id)
    return event


def execute_force_option(world, actor, option_id, decision_event_id, action):
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, action)
    if decided_by != actor:
        raise ValueError("force action has the wrong actor")
    option = next((item for item in force_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("force option is stale or unknown")
    require_authority(candidate, actor, "military")
    detachment = candidate.society.detachments[option.detachment_id]
    if option.kind == "rotate":
        if action != ROTATE_GARRISON_ACTION:
            raise ValueError("garrison rotation action mismatch")
        current = candidate.society.detachments.get(option.current_detachment_id)
        replacement = candidate.society.detachments.get(option.replacement_detachment_id)
        current_garrison = candidate.society.garrisons.get(f"garrison:{option.current_detachment_id}")
        replacement_garrison = candidate.society.garrisons.get(f"garrison:{option.replacement_detachment_id}")
        account = candidate.economy.accounts.get(option.account_id)
        if (current is None or replacement is None or current_garrison is None
                or current_garrison.stage != "active" or replacement_garrison is not None
                or current.owner_ref != actor or replacement.owner_ref != actor
                or current.stage != "present" or replacement.stage != "present"
                or current.location_id != option.settlement_id or replacement.location_id != option.settlement_id
                or replacement.provisions < replacement.count or account is None
                or account.owner_ref != actor or account.balance < option.daily_wage):
            raise ValueError("garrison rotation is no longer materially possible")
        new_identity = f"garrison:{replacement.id}"
        event = record_event(
            candidate, "garrison_rotated",
            "A instituição substituiu a coluna da guarnição por outra presença abastecida; o controle permaneceu.",
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload={"decision_event_id": decision.id, "actor_ref": actor.to_dict(),
                            "selected_affordance_id": option.id},
            deltas=(_delta("garrison", current_garrison.id, "stage", "active", "withdrawn"),
                    _delta("garrison", new_identity, "stage", None, "active"),
                    _delta("garrison", new_identity, "detachment_id", None, replacement.id),
                    _delta("garrison", new_identity, "settlement_id", None, option.settlement_id)),
            cause_ids=_causes(decision.id, current_garrison.last_event_id,
                              current.last_event_id, replacement.last_event_id))
        candidate.society.garrisons[current_garrison.id] = current_garrison.model_copy(
            update={"stage": "withdrawn", "last_event_id": event.id})
        candidate.society.garrisons[new_identity] = Garrison(
            id=new_identity, detachment_id=replacement.id, settlement_id=option.settlement_id,
            account_id=account.id, decision_event_id=decision.id,
            started_day=candidate.clock.absolute_day, last_event_id=event.id)
    elif option.kind in {"garrison", "defend"}:
        if action != GARRISON_ACTION:
            raise ValueError("garrison action mismatch")
        settlement = candidate.society.settlements[detachment.location_id]
        account = candidate.economy.accounts.get(option.account_id)
        authorized = (settlement.occupier_id == actor.id if option.kind == "garrison"
                     else settlement.administrator_id == actor.id)
        if (not authorized or detachment.stage != "present"
                or detachment.location_id != option.settlement_id
                or detachment.provisions < detachment.count or account is None
                or account.owner_ref != actor
                or account.balance < option.daily_wage):
            raise ValueError("garrison is no longer supplied or funded")
        identity = f"garrison:{detachment.id}"
        garrison = Garrison(id=identity, detachment_id=detachment.id, settlement_id=settlement.id,
                            account_id=account.id, decision_event_id=decision.id,
                            started_day=candidate.clock.absolute_day, last_event_id="pending")
        content = ("A coluna estabeleceu uma guarnição material no assentamento ocupado."
                  if option.kind == "garrison" else
                  "A coluna estabeleceu uma guarnição defensiva no próprio assentamento administrado.")
        event = record_event(
            candidate, "garrison_established", content,
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload={"decision_event_id": decision.id, "actor_ref": actor.to_dict(),
                            "selected_affordance_id": option.id},
            deltas=(_delta("garrison", identity, "stage", None, "active"),
                    _delta("garrison", identity, "settlement_id", None, settlement.id),
                    _delta("garrison", identity, "detachment_id", None, detachment.id)),
            cause_ids=_causes(decision.id, detachment.last_event_id))
        candidate.society.garrisons[identity] = garrison.model_copy(update={"last_event_id": event.id})
    elif option.kind == "withdraw":
        if action != WITHDRAW_GARRISON_ACTION:
            raise ValueError("garrison withdrawal action mismatch")
        _withdraw_garrison(candidate, actor, option, decision)
    elif option.kind == "occupy":
        settlement = candidate.society.settlements[detachment.location_id]
        # The owner revalidates the physical fact the actor cannot see; the
        # refusal states nothing about who else is standing there.
        if settlement.occupier_id is not None or _rival_present(candidate, detachment):
            raise ValueError("occupation is no longer possible at this place")
        candidate.society.set_occupation(settlement.id, actor.id)
        _record(candidate, detachment, detachment, "settlement_occupied",
                f"{settlement.name}: ocupada por presença armada; a administração não mudou.",
                deltas=(_delta("settlement", settlement.id, "occupier_id", None, actor.id),),
                causes=(decision.id,))
    else:
        _dissolve(candidate, detachment, "detachment_disbanded",
                  "O destacamento foi dissolvido; as pessoas voltaram a uma coorte local.",
                  causes=(decision.id,), decision=decision, actor=actor)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachments.get(option.detachment_id)


def establish_garrison(world, actor, option_id, decision_event_id):
    return execute_force_option(world, actor, option_id, decision_event_id, GARRISON_ACTION)


def withdraw_garrison(world, actor, option_id, decision_event_id):
    return execute_force_option(world, actor, option_id, decision_event_id, WITHDRAW_GARRISON_ACTION)


def rotate_garrison(world, actor, option_id, decision_event_id):
    return execute_force_option(world, actor, option_id, decision_event_id, ROTATE_GARRISON_ACTION)


def occupy_settlement(world, actor, option_id, decision_event_id):
    return execute_force_option(world, actor, option_id, decision_event_id, OCCUPY_ACTION)


def disband_detachment(world, actor, option_id, decision_event_id):
    return execute_force_option(world, actor, option_id, decision_event_id, DISBAND_ACTION)


def stand_down_from_standoff(world, actor, option_id, decision_event_id):
    """A participant ends only its own real presence at a recognized contact."""
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, STAND_DOWN_ACTION)
    if decided_by != actor:
        raise ValueError("standoff action has the wrong actor")
    option = next((item for item in standoff_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("standoff option is stale or unknown")
    require_authority(candidate, actor, "military")
    detachment = candidate.society.detachments[option.detachment_id]
    standoff = candidate.society.force_standoffs[option.standoff_id]
    if _active_pair(candidate, standoff) is None:
        raise ValueError("armed contact is no longer current")
    _dissolve(candidate, detachment, "detachment_stood_down",
              "A coluna baixou as armas e foi dissolvida onde estava; nenhum território mudou de dono.",
              causes=(decision.id,), decision=decision, actor=actor)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachments[option.detachment_id]


def withdraw_detachment(world, actor, option_id, decision_event_id):
    """Begin a real withdrawal; later dated force ticks carry it home."""
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, WITHDRAW_ACTION)
    if decided_by != actor:
        raise ValueError("withdrawal has the wrong actor")
    option = next((item for item in withdrawal_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("withdrawal option is stale or unknown")
    _begin_withdrawal(candidate, actor, option, decision_event_id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachments[option.detachment_id]


def _begin_withdrawal(world, actor, option, decision_event_id, *, decision_actor_ref=None,
                      selected_affordance_id=None):
    """Owner-side material start shared by direct and commitment fulfillment."""
    require_authority(world, actor, "military")
    detachment = world.society.detachments[option.detachment_id]
    destination = world.society.settlements[option.destination_id]
    if (destination.administrator_id != actor.id
            or not _route_is_current(world, detachment.location_id, option.destination_id, option.route_ids)):
        raise ValueError("withdrawal is no longer possible")
    from .campaign_supply import campaign_baggage_ready_for_departure
    if not campaign_baggage_ready_for_departure(world, detachment):
        raise ValueError("withdrawal is no longer possible")
    updated = detachment.model_copy(update={"destination_id": option.destination_id, "route_ids": option.route_ids,
                                             "route_index": 0, "stage": "marching",
                                             "due_day": world.clock.absolute_day + 1})
    decision_actor = decision_actor_ref or actor
    event = _record(
        world, detachment, updated, "detachment_withdrawal_started",
        "A coluna deixou a ocupação e iniciou a retirada por uma rota conhecida até sua própria administração.",
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": decision_event_id, "actor_ref": decision_actor.to_dict(),
                        "selected_affordance_id": selected_affordance_id or option.id},
        deltas=(*_clear_occupation(world, detachment),
                _delta("detachment", detachment.id, "destination_id", detachment.destination_id, option.destination_id),
                _delta("detachment", detachment.id, "route_ids", detachment.route_ids, option.route_ids),
                _delta("detachment", detachment.id, "route_index", detachment.route_index, 0),
                _delta("detachment", detachment.id, "stage", "present", "marching")),
        causes=(decision_event_id,))
    _resolve_standoffs_for(world, detachment.id, event.id)
    return event


def _advance(world, detachment):
    """One dated leg over a route that must still be physically usable."""
    route_id = detachment.route_ids[detachment.route_index]
    day = world.clock.absolute_day
    if world.map.get_route_operational_capacity(route_id) <= 0:
        from .logistics import _route_causes
        command = world.society.detachment_commands.get(detachment.id)
        causes = _route_causes(world, (route_id,))[route_id]
        region_id = world.society.settlements[detachment.location_id].region_id
        for route_id_before_hold in detachment.route_ids[:detachment.route_index]:
            prior = world.map.routes.get(route_id_before_hold)
            if prior is None or region_id not in prior.endpoint_region_ids:
                return _record(world, detachment, detachment.model_copy(update={"due_day": day + 1}),
                               "detachment_held", "Passagem indisponível; a coluna aguarda.",
                               deltas=(_delta("detachment", detachment.id, "due_day",
                                              detachment.due_day, day + 1),),
                               causes=causes)
            region_id = next(item for item in prior.endpoint_region_ids if item != region_id)
        if command is not None:
            from .force_command import command_is_attached_to_march
            if command_is_attached_to_march(world, command):
                causes = _causes(*causes, command.last_event_id)
        held = _record(
            world, detachment, detachment.model_copy(update={"due_day": day + 1}),
            "detachment_held", "Passagem indisponível; a coluna aguarda.",
            deltas=(_delta("detachment", detachment.id, "due_day", detachment.due_day, day + 1),),
            causes=causes, causal_payload={"detachment_id": detachment.id,
                                           "blocked_route_id": route_id,
                                           "position_region_id": region_id,
                                           "prior_detachment_event_id": detachment.last_event_id})
        if command is not None:
            from .route_intelligence import observe_commander_junction_routes
            observe_commander_junction_routes(world, detachment.id, held)
        return held
    index = detachment.route_index + 1
    arrived = index >= len(detachment.route_ids)
    location = detachment.destination_id if arrived else detachment.location_id
    updated = detachment.model_copy(update={"route_index": index, "location_id": location,
                                            "stage": "present" if arrived else "marching",
                                            "due_day": day + (1 if arrived else route_duration(world, route_id))})
    commander = None
    command = world.society.detachment_commands.get(detachment.id)
    if arrived and command is not None:
        from .force_command import command_is_attached_to_march
        character = world.society.characters.get(command.character_id)
        if (character is not None and character.location_id == detachment.location_id
                and command_is_attached_to_march(world, command)):
            commander = character
    movement_deltas = [_delta("detachment", detachment.id, "route_index", detachment.route_index, index),
                       _delta("detachment", detachment.id, "location_id", detachment.location_id, location),
                       _delta("detachment", detachment.id, "stage", detachment.stage, updated.stage),
                       *_move_empty_campaign_baggage(world, detachment, location)]
    if commander is not None:
        movement_deltas.append(_delta("character", commander.id, "location_id",
                                      commander.location_id, location))
    position_region_id = None
    if not arrived:
        position_region_id = world.society.settlements[detachment.location_id].region_id
        for traversed_route_id in updated.route_ids[:index]:
            traversed = world.map.routes[traversed_route_id]
            position_region_id = next(item for item in traversed.endpoint_region_ids
                                      if item != position_region_id)
    event = _record(world, detachment, updated,
                    "detachment_arrived" if arrived else "detachment_marched",
                    "A coluna chegou ao destino." if arrived else "A coluna avançou um trecho.",
                    deltas=tuple(movement_deltas),
                    causal_payload={"detachment_id": detachment.id,
                                    "position_region_id": (world.society.settlements[location].region_id
                                                           if arrived else position_region_id)})
    if commander is not None:
        world.society.characters[commander.id] = commander.model_copy(update={"location_id": location})
    if arrived:
        # Standing there is observation, not control: the owner learns the
        # place through its own dated report and gains nothing else.
        from .settlement_intelligence import observe_present_force
        observe_present_force(world, detachment.id)
        detect_force_standoffs(world, detachment.id)
    else:
        from .route_intelligence import observe_commander_junction_routes
        observe_commander_junction_routes(world, detachment.id, event)
    return event


def _move_empty_campaign_baggage(world, detachment, location_id):
    """The empty temporary bag follows its real column, never its cargo."""
    from .campaign_supply import campaign_baggage_ready_for_departure, campaign_stock_id

    stock = world.economy.stocks.get(campaign_stock_id(detachment.id))
    if stock is None or stock.location_id == location_id:
        return ()
    if not campaign_baggage_ready_for_departure(world, detachment):
        raise ValueError("a committed campaign bag cannot move with withdrawal")
    world.economy.stocks[stock.id] = stock.model_copy(update={"location_id": location_id})
    return (_delta("stock", stock.id, "location_id", stock.location_id, location_id),)


def resolve_forces(world, situations):
    """Daily upkeep: eat, then move. Arrival alone changes no control."""
    for situation in situations:
        detachment = world.society.detachments.get(situation.id)
        if (situation.kind != "force" or detachment is None
                or detachment.due_day != world.clock.absolute_day):
            raise ValueError("unknown or inconsistent dated force")
        eaten = detachment.count * RATIONS_PER_SOLDIER_DAY
        if detachment.provisions < eaten:
            _dissolve(world, detachment, "detachment_lapsed",
                      "Sem provisões, a presença armada cessou; nenhuma vitória foi produzida.")
            continue
        fed = detachment.model_copy(update={"provisions": detachment.provisions - eaten,
                                            "due_day": world.clock.absolute_day + 1})
        _record(world, detachment, fed, "detachment_supplied", f"A coluna consumiu {eaten} rações.",
                deltas=(_delta("detachment", detachment.id, "provisions", detachment.provisions, fed.provisions),))
        current = world.society.detachments[detachment.id]
        if current.stage == "marching":
            _advance(world, current)
        elif current.stage == "present":
            _maintain_garrison(world, current)
            # A persisted physical contact remains a fact even when both
            # columns were loaded or arrived in a different resolver order.
            detect_force_standoffs(world, current.id)

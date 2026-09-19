"""Turns granted to an institution that a canonical breach actually harmed.

Relations already records a breached delivery, tells both parties and leaves
the creditor holding nothing but a memory. This module adds the missing turn
and nothing else: the day after the breach the wronged institution may choose
among options the engine recomposes from *its own* knowledge, and the existing
owners execute whatever is chosen.

Nothing here decides, stores or moves anything. There is no routine that
answers a breach with force: without a provider answer the wronged institution
simply does not act, and a deadline never becomes an action.
"""

from src.classes.mechanical_language import EntityRef
from src.systems.calendar_agenda import ScheduledSituation

from .institutional_decision_turn import DiscretionaryAdapter, review_institutional_decision_turn
from .force import (DISBAND_ACTION, GARRISON_ACTION, WITHDRAW_GARRISON_ACTION, ROTATE_GARRISON_ACTION, OCCUPY_ACTION,
                    RAISE_ACTION, disband_detachment, establish_garrison, force_options,
                    occupy_settlement, raise_detachment, raise_options, withdraw_garrison, rotate_garrison)
from .territorial_control import (CONTROL_ACTION, WITHDRAW_CONTROL_ACTION,
                                  establish_territorial_control, territorial_control_options,
                                  withdraw_territorial_control)
from .institutional_memory import institutional_view
from .reciprocal_supply import OFFER_ACTION, offer_reciprocal_supply, reciprocal_supply_options

REVIEW_KIND = "recourse_review"
# How long a remembered breach still earns its creditor a turn. Memory lasts
# far longer; only the opportunity to answer this particular fact is bounded.
RECOURSE_WINDOW = 10
REPORT_SPAN_DAYS = 30

_EXECUTORS = {RAISE_ACTION: raise_detachment, OCCUPY_ACTION: occupy_settlement,
              DISBAND_ACTION: disband_detachment, OFFER_ACTION: offer_reciprocal_supply,
              CONTROL_ACTION: establish_territorial_control, WITHDRAW_CONTROL_ACTION: withdraw_territorial_control,
              GARRISON_ACTION: establish_garrison, WITHDRAW_GARRISON_ACTION: withdraw_garrison,
              ROTATE_GARRISON_ACTION: rotate_garrison}


def review_id(day):
    return f"recourse-review:{day}"


def schedule_review(world, day):
    """One concrete dated review; the deadline only grants a turn."""
    if day > world.clock.absolute_day and world.agenda.get(review_id(day)) is None:
        world.agenda.schedule(ScheduledSituation(review_id(day), REVIEW_KIND, day))


def note_breach(world, clause):
    """A breached delivery earns its institutional creditor a turn tomorrow."""
    creditor = clause.creditor_ref
    if (clause.kind != "resource_transfer" or creditor.kind != "polity"
            or creditor.id not in world.society.polities):
        return
    schedule_review(world, world.clock.absolute_day + 1)


def _known_breaches(world, creditor, day=None):
    """Unremedied breaches this creditor itself was told about, still answerable.

    Only the creditor's own obligations and its own notices are read; nothing
    is learned here about why the debtor failed or what it still holds.
    """
    day = world.clock.absolute_day if day is None else day
    events = {item.id: item for item in world.events}
    for _, obligation in sorted(world.relations.obligations.items()):
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if obligation.status != "breached" or proposal is None:
            continue
        clause = proposal.clauses[obligation.clause_index]
        breach = events.get(obligation.breach_event_id)
        if (clause.kind != "resource_transfer" or clause.creditor_ref != creditor
                or breach is None or not 0 <= day - breach.day <= RECOURSE_WINDOW):
            continue
        notice = next((item for item in sorted(world.knowledge.notices.values(), key=lambda n: n.id)
                       if item.recipient_ref == creditor and item.event_id == breach.id), None)
        if notice is not None:
            yield clause, breach, notice


def _standing(world, creditor):
    return tuple(item for _, item in sorted(world.society.detachments.items())
                 if item.owner_ref == creditor and item.stage != "disbanded")


def _reported(world, creditor, settlement_id):
    """A place this institution currently observes by its own report."""
    report = world.knowledge.settlement_report(creditor, settlement_id)
    return (report is not None and report.settlement_id == settlement_id
            and world.clock.absolute_day - report.observed_day <= REPORT_SPAN_DAYS)


def _name(world, settlement_id):
    return world.society.settlements[settlement_id].name


def recourse_options(world, creditor, debtor=None):
    """The bounded menu of current actions this institution could take today.

    Every entry is rebuilt by its own vertical from the creditor's own reports,
    own stocks, own accounts, own cohorts and own authority. A march may only
    aim at a place the creditor already observes and can already reach.
    """
    menu = []
    if debtor is not None:
        for option in reciprocal_supply_options(world, creditor, counterparty=debtor):
            menu.append((option, f"Propor a {world.society.polities[debtor.id].name} entregar "
                                 f"{option.food_quantity} de alimento em troca de {option.pledge_quantity} "
                                 f"de {option.pledge_resource_id} do próprio estoque."))
    for option in raise_options(world, creditor):
        if not _reported(world, creditor, option.destination_id):
            continue
        menu.append((option, f"Levantar {option.count} soldados em {_name(world, option.settlement_id)} "
                             f"e marchar até {_name(world, option.destination_id)} com "
                             f"{option.provisions} rações próprias."))
    for option in force_options(world, creditor):
        detachment = world.society.detachments[option.detachment_id]
        if option.kind == "occupy":
            menu.append((option, f"Ocupar {_name(world, detachment.location_id)} com a coluna já presente."))
        elif option.kind == "withdraw":
            menu.append((option, f"Retirar a guarnição de {_name(world, detachment.location_id)} sem mover a coluna."))
        elif option.kind == "rotate":
            menu.append((option, f"Rotacionar a guarnição de {_name(world, detachment.location_id)} por outra coluna abastecida."))
        else:
            menu.append((option, f"Dissolver a coluna em {_name(world, detachment.location_id)} "
                                 f"e devolver as pessoas a uma coorte local."))
    for option in territorial_control_options(world, creditor):
        menu.append((option, f"Formalizar o controle territorial de {_name(world, option.settlement_id)} "
                             "sem alterar a administração vigente."))
    return tuple(menu)


def _recourse_menu(world, creditor):
    breach = next(iter(_known_breaches(world, creditor)), None)
    if breach is None and not _standing(world, creditor):
        return ()
    return recourse_options(world, creditor, breach[0].debtor_ref if breach is not None else None)


def _recourse_situation(world, creditor, options):
    breach = next(iter(_known_breaches(world, creditor)), None)
    clause, _, notice = breach if breach is not None else (None, None, None)
    debtor = clause.debtor_ref if clause is not None else None
    return {"today": world.clock.absolute_day,
            "broken_promise": None if clause is None else {
                "debtor": clause.debtor_ref.to_dict(), "resource_id": clause.resource_id,
                "quantity": clause.quantity, "was_due_day": clause.due_day,
                "learned_day": notice.learned_day},
            "your_reading_of_them": None if debtor is None else institutional_view(world, creditor, debtor),
            "places_you_currently_observe": sorted(
                report.settlement_id for report in world.knowledge.settlements_for_actor(creditor)
                if _reported(world, creditor, report.settlement_id))}


def _recourse_causes(world, option):
    breach = next(iter(_known_breaches(world, option.actor_ref)), None)
    return (breach[1].id,) if breach is not None else ()


class _LabeledOption:
    """The vertical's own option carrying its label, so the adapter never
    depends on mutable adapter-level state or on the engine's call order."""

    def __init__(self, option, label):
        self._option = option
        self.label = label

    @property
    def id(self):
        return self._option.id

    @property
    def actor_ref(self):
        return self._option.actor_ref

    def decision(self):
        return self._option.decision()


def recourse_adapters(on_executed=None):
    def options_fn(world, actor):
        menu = _recourse_menu(world, actor)
        return tuple(_LabeledOption(option, label) for option, label in menu)

    def label_fn(option):
        return option.label

    def execute_fn(world, actor, option_id, decision_event_id):
        option = next((item for item, _ in _recourse_menu(world, actor) if item.id == option_id), None)
        if option is None:
            raise ValueError("stale or unknown recourse option")
        _EXECUTORS[option.decision()["action"]](world, actor, option.id, decision_event_id)
        if on_executed is not None:
            on_executed()

    return (DiscretionaryAdapter(
        name="recourse", family="recourse", options_fn=options_fn,
        label_fn=label_fn, causes_fn=_recourse_causes,
        execute_fn=execute_fn, situation_fn=_recourse_situation),)


async def _turn(world, creditor):
    if not _recourse_menu(world, creditor):
        return False
    changed = {"value": False}
    await review_institutional_decision_turn(
        world, creditor, recourse_adapters(on_executed=lambda: changed.__setitem__("value", True)),
        situation_fn=_recourse_situation)
    return changed["value"]


def _pending(world, creditor, day):
    """Is there still something for this institution to decide tomorrow?"""
    return bool(_standing(world, creditor)) or any(True for _ in _known_breaches(world, creditor, day))


def recourse_actors(world):
    return tuple(EntityRef("polity", identity) for identity in sorted(world.society.polities)
                 if _pending(world, EntityRef("polity", identity), world.clock.absolute_day))


def schedule_pending_recourse(world):
    day = world.clock.absolute_day + 1
    if any(_pending(world, EntityRef("polity", identity), day) for identity in world.society.polities):
        schedule_review(world, day)


async def review_recourse(world, situations):
    """Run only on a concrete dated review; one consultation per institution."""
    from .institutional_agenda import review_daily_institutional_turn
    await review_daily_institutional_turn(world, situations)

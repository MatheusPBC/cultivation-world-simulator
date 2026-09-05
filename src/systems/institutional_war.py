"""Unilateral formal declaration of war, grounded in one real aggression.

This module owns exactly one institutional choice: an authorized sect that
actually knows a real, deliberate, unanswered attack by another sect's member
against its own member may formally declare war over it.  Nothing else.

What it deliberately does not do:

* it creates no army, treasury, territory, troop, battle or resource
  transfer, and grants no authority; a declaration only changes the ``kind``
  of the canonical relation;
* it never asks the counterparty.  A declaration is unilateral by design and
  needs no consent, which is exactly why ending one does not live here -- that
  is the bilateral negotiation owned by ``institutional_peace``;
* it never treats personal aggression as an institutional order.  The reading
  states only that a member was the aggressor; the institution independently
  chooses whether that is worth a war;
* it invents nothing.  Everything the engine cannot ground -- objective, cost,
  gain -- stays ``unknown`` in the `CasusBelliReading`, and the reading never
  authorizes anything by itself.

A cause is spent the moment a declaration cites it.  A war concluded by
formal peace therefore cannot be restarted from the same historical
aggression, forever; only a genuinely new attack creates a new cause.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_affordance import (
    DomainAffordance,
    DomainDecision,
    DomainDecisionKind,
)
from src.classes.event import Event, FactKind
from src.classes.institution import (
    AuthorityScope,
    InstitutionalRelation,
    InstitutionalRelationKind,
)
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.systems.avatar_aggression import canonical_aggression
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    AffordanceContext,
    StaleAffordanceError,
    event_lookup,
    stale_affordance_blocked_event,
    validate_actor_decision,
)
from src.systems.domain_decision_interpreter import interpret_domain_affordances
from src.systems.institution_authority import can_actor_act_for
from src.systems.institutional_diplomacy import (
    WAR_DECLARED_EVENT_TYPE,
    active_sects,
    has_active_sect_institution,
    sect_by_id,
    sect_institution_id,
    sect_institution_ref,
    set_formal_war,
)
from src.systems.institutional_memory import (
    decision_context as institutional_decision_context,
    record_known_fact,
)

DECLARATION_DOMAIN = "institutional_war_declaration"
DECLARE_ACTION = "declare_institutional_war"
INTERPRETER_TEMPLATE = "institutional_war_interpreter.txt"
INTERPRETER_TASK_NAME = "institutional_war_declaration_interpreter"

# How many independently witnessed, still unanswered aggressions by the same
# sect it takes for the deterministic fallback to reach the shared
# conservative action threshold.  A single attack deliberately stays below it:
# with no interpreter available, one incident never starts a war on its own,
# while a repeated, evidenced pattern does.
AGGRESSION_URGENCY_SCALE = 3.0

UNKNOWN = "unknown"

_PAYLOAD_KEY = "war_declaration"
_ID_FIELDS = (
    "declaring_sect_id",
    "target_sect_id",
    "declaring_institution_id",
    "target_institution_id",
    "relation_id",
    "casus_belli_event_id",
    "aggressor_avatar_id",
    "victim_avatar_id",
    "authorizing_office_id",
    "authorizing_holder_avatar_id",
)
_PAYLOAD_FIELDS = frozenset(_ID_FIELDS)


@dataclass(frozen=True, slots=True)
class WarAffordanceContext(AffordanceContext):
    """Step-local causal evidence only; never World state and never persisted."""

    event_overlays: tuple[Event, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CasusBelliReading:
    """One actor's bounded reading of a cause, built only from engine facts.

    It is transient: it is handed to the interpreter as context and is never
    persisted, never carries a delta and never authorizes an action.  Every
    field the engine cannot ground in a canonical fact stays ``unknown``
    rather than being replaced by an invented number.
    """

    perceived_cause_event_id: str
    perceived_cause: str
    credibility: str
    objective: str
    reach: str
    urgency: float
    expected_cost: str
    expected_gain: str
    available_alternatives: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "perceived_cause_event_id": self.perceived_cause_event_id,
            "perceived_cause": self.perceived_cause,
            "credibility": self.credibility,
            "objective": self.objective,
            "reach": self.reach,
            "urgency": self.urgency,
            "expected_cost": self.expected_cost,
            "expected_gain": self.expected_gain,
            "available_alternatives": list(self.available_alternatives),
        }


def _overlays(context: AffordanceContext) -> tuple[Event, ...]:
    return tuple(getattr(context, "event_overlays", ()) or ())


def force_authorizer(world: Any, sect_id: int | str) -> tuple[str, str] | None:
    """The office and holder that currently authorize this sect's use of force.

    Answered from current canonical state on every call, and returned rather
    than reduced to a boolean so an option can be bound to *who* authorized
    it.  A replacement leader is a different authorizer, so an option composed
    under the previous holder no longer recomposes and cannot be executed --
    even though the institution itself is still perfectly authorized.
    """

    month = int(world.month_stamp)
    if not has_active_sect_institution(world, sect_id, current_month=month):
        return None
    sect_ref = sect_institution_ref(sect_id)
    verdict = can_actor_act_for(
        world,
        sect_ref,
        sect_ref,
        AuthorityScope.FORCE_EMPLOYMENT,
        current_month=month,
    )
    if not verdict.allowed or not verdict.office_id:
        return None
    office = world.institutional_authority.offices.get(verdict.office_id)
    if office is None or office.holder_ref is None:
        return None
    return office.id, str(office.holder_ref.id)


def can_employ_force(world: Any, sect_id: int | str) -> bool:
    return force_authorizer(world, sect_id) is not None


def has_material_force(world: Any, sect_id: int | str) -> bool:
    """The minimum real force a declaration needs, derived when it is asked.

    Read directly from the sect's currently living members through the same
    strength and risk predicates the combat path itself uses, never from
    ``total_battle_strength``: that cached scalar is refreshed once a year and
    would still claim an army after every member died, was injured or left
    while an interpreter call was in flight.  Nothing is cached or mutated
    here, and no army, capacity or troop state is introduced: a sect with no
    living member able to fight simply has no option.
    """

    from src.classes.action.action import can_take_risk
    from src.systems.battle import get_base_strength

    sect = sect_by_id(world, sect_id)
    if sect is None:
        return False
    for member in (getattr(sect, "members", {}) or {}).values():
        if bool(getattr(member, "is_dead", False)):
            continue
        if not can_take_risk(member)[0]:
            continue
        if float(get_base_strength(member)) > 0.0:
            return True
    return False


def war_declaration_payload(event: Any) -> dict[str, Any] | None:
    """The declaration carried by a fact, or None if it is not a valid one."""

    if not isinstance(event, Event):
        return None
    payload = event.causal_payload
    if not isinstance(payload, Mapping):
        return None
    raw = payload.get(_PAYLOAD_KEY)
    if not isinstance(raw, Mapping) or set(raw) != _PAYLOAD_FIELDS:
        return None
    values: dict[str, Any] = {}
    for name in _ID_FIELDS:
        value = raw.get(name)
        if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
            return None
        values[name] = value
    declaring_sect_id = values["declaring_sect_id"]
    target_sect_id = values["target_sect_id"]
    if (
        not declaring_sect_id.isdigit()
        or not target_sect_id.isdigit()
        or declaring_sect_id == target_sect_id
        or values["declaring_institution_id"] != sect_institution_id(declaring_sect_id)
        or values["target_institution_id"] != sect_institution_id(target_sect_id)
        or values["relation_id"]
        != InstitutionalRelation.id_for(
            values["declaring_institution_id"], values["target_institution_id"]
        )
    ):
        return None
    return values


def canonical_war_declaration(event: Any) -> tuple[Event, dict[str, Any]] | None:
    """One declaration fact, accepted only if it is canonical in every respect."""

    if not isinstance(event, Event):
        return None
    declaration = war_declaration_payload(event)
    if declaration is None:
        return None
    related = {str(item) for item in (event.related_sects or [])}
    if (
        event.event_type != WAR_DECLARED_EVENT_TYPE
        or event.fact_kind is not FactKind.STATE_TRANSITION
        or event.causal_origin is not CausalOrigin.ACTOR_DECISION
        or event.is_story
        or related
        != {str(declaration["declaring_sect_id"]), str(declaration["target_sect_id"])}
        or not any(
            link.relation is CausalRelation.RESPONSE_TO
            and link.cause_event_id == str(declaration["casus_belli_event_id"])
            for link in event.causal_links
        )
    ):
        return None
    return event, declaration


def _known_event_ids(
    world: Any, institution_ids: frozenset[str], overlays: tuple[Event, ...]
) -> list[str]:
    """Every canonical fact these institutions actually know, plus this step's.

    Discovery goes through the knowledge owner, which is saved state, so the
    same causes and the same spent causes reappear after a reload with no
    runtime cache anywhere.
    """

    ids = [
        fact.event_id
        for fact in world.institutional_knowledge.known_facts.values()
        if fact.institution_id in institution_ids
    ]
    ids.extend(event.id for event in overlays if isinstance(event, Event))
    return list(dict.fromkeys(ids))


def _facts_for(
    world: Any, institution_ids: frozenset[str], overlays: tuple[Event, ...]
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Known aggressions by id, and the causes already spent on a declaration."""

    lookup = event_lookup(world, overlays)
    aggressions: dict[str, dict[str, Any]] = {}
    spent: set[str] = set()
    for event_id in _known_event_ids(world, institution_ids, overlays):
        event = lookup(event_id)
        if event is None:
            continue
        # The cited actor decision is resolved and checked here, so a
        # well-shaped fact naming a dangling or foreign decision is no cause.
        found = canonical_aggression(event, lookup=lookup)
        if found is not None:
            aggressions[found[0].id] = found[1]
            continue
        declared = canonical_war_declaration(event)
        if declared is not None:
            # A cause is consumed by the declaration that cited it, whatever
            # happened to that war afterwards.  Peace can therefore never be
            # undone by replaying the same historical attack.
            spent.add(str(declared[1]["casus_belli_event_id"]))
    return aggressions, spent


def _relation_kind(
    world: Any, sect_a_id: int | str, sect_b_id: int | str
) -> InstitutionalRelationKind | None:
    relation = world.institutional_relations.get_relation(
        sect_institution_id(sect_a_id), sect_institution_id(sect_b_id)
    )
    return None if relation is None else relation.kind


def known_casus_belli(
    world: Any, sect_id: int | str, *, overlays: tuple[Event, ...] = ()
) -> list[tuple[str, dict[str, Any]]]:
    """Every unspent cause this sect may currently act on, oldest first.

    A cause qualifies only when this sect was the *victim's* side: personal
    aggression by one's own member is never a cause against the other sect.
    """

    institution_id = sect_institution_id(sect_id)
    aggressions, spent = _facts_for(world, frozenset({institution_id}), tuple(overlays))
    month = int(world.month_stamp)
    causes = [
        (event_id, aggression)
        for event_id, aggression in aggressions.items()
        if event_id not in spent
        and str(aggression["target_sect_id"]) == str(sect_id)
        and world.institutional_knowledge.contains(institution_id, event_id)
        and has_active_sect_institution(
            world, str(aggression["initiator_sect_id"]), current_month=month
        )
        and _relation_kind(world, sect_id, aggression["initiator_sect_id"])
        is not InstitutionalRelationKind.AT_WAR
    ]
    # Oldest first, with the event id only as a deterministic tie-break.
    return sorted(causes, key=lambda item: (int(item[1]["month"]), item[0]))


def _urgency(cause_count: int) -> float:
    return max(0.0, min(1.0, cause_count / AGGRESSION_URGENCY_SCALE))


def declaration_affordances(context: AffordanceContext):
    """One declaration option per unspent cause this sect actually knows.

    No known cause, no authority or no living force means no option at all,
    hence no interpreter call and no possible mutation.
    """

    world = context.world
    if context.actor_ref.kind != "sect":
        return ()
    declaring_sect_id = str(context.actor_ref.id)
    authorizer = force_authorizer(world, declaring_sect_id)
    if authorizer is None or not has_material_force(world, declaring_sect_id):
        return ()
    authorizing_office_id, authorizing_holder_avatar_id = authorizer
    overlays = _overlays(context)
    causes = known_casus_belli(world, declaring_sect_id, overlays=overlays)
    by_aggressor: dict[str, int] = {}
    for _event_id, aggression in causes:
        aggressor_sect_id = str(aggression["initiator_sect_id"])
        by_aggressor[aggressor_sect_id] = by_aggressor.get(aggressor_sect_id, 0) + 1
    declaring_institution_id = sect_institution_id(declaring_sect_id)
    options: list[DomainAffordance] = []
    for event_id, aggression in causes:
        target_sect_id = str(aggression["initiator_sect_id"])
        target_institution_id = sect_institution_id(target_sect_id)
        options.append(
            DomainAffordance(
                domain=context.domain,
                actor_ref=context.actor_ref,
                action_kind=DECLARE_ACTION,
                target_refs=(sect_institution_ref(target_sect_id),),
                parameters={
                    "declaring_sect_id": declaring_sect_id,
                    "target_sect_id": target_sect_id,
                    "declaring_institution_id": declaring_institution_id,
                    "target_institution_id": target_institution_id,
                    "relation_id": InstitutionalRelation.id_for(
                        declaring_institution_id, target_institution_id
                    ),
                    "casus_belli_event_id": event_id,
                    "aggressor_avatar_id": str(aggression["initiator_avatar_id"]),
                    "victim_avatar_id": str(aggression["target_avatar_id"]),
                    # Binding the option to who authorized it is what makes a
                    # leadership change invalidate a choice taken under the
                    # previous holder, even though the institution itself
                    # remains authorized throughout.
                    "authorizing_office_id": authorizing_office_id,
                    "authorizing_holder_avatar_id": authorizing_holder_avatar_id,
                },
                urgency=_urgency(by_aggressor[target_sect_id]),
                motivation_event_ids=(event_id,),
            )
        )
    return tuple(options)


def casus_belli_reading(
    world: Any,
    option: DomainAffordance,
    *,
    alternatives: tuple[DomainAffordance, ...] = (),
    overlays: tuple[Event, ...] = (),
) -> CasusBelliReading | None:
    """The actor's bounded reading of one option, from facts only."""

    params = dict(option.parameters)
    cause_id = str(params["casus_belli_event_id"])
    lookup = event_lookup(world, overlays)
    resolved = canonical_aggression(lookup(cause_id), lookup=lookup)
    if resolved is None:
        return None
    fact = world.institutional_knowledge.get_fact(
        str(params["declaring_institution_id"]), cause_id
    )
    if fact is None:
        return None
    return CasusBelliReading(
        perceived_cause_event_id=cause_id,
        # The cause is the typed fact, never a rendered sentence about it.
        perceived_cause="member_of_other_sect_deliberately_attacked_our_member",
        # Credibility is how this institution actually learned it, not a score.
        credibility=str(fact.channel),
        # No war-aims model exists, so an objective would have to be invented.
        objective=UNKNOWN,
        # The attack itself is the reach evidence: the aggressor really did
        # make contact with our member.  No route or military path is inferred.
        reach="demonstrated_by_attack",
        urgency=option.urgency,
        # There is no cost or spoils model.  Nothing is estimated here.
        expected_cost=UNKNOWN,
        expected_gain=UNKNOWN,
        available_alternatives=tuple(
            item.id for item in alternatives if item.id != option.id
        ),
    )


def _sect_name(world: Any, sect_id: str) -> str:
    sect = sect_by_id(world, sect_id)
    return str(getattr(sect, "name", "") or sect_id)


def _revalidated(
    context: AffordanceContext, option: DomainAffordance, decision_event: Event | None
) -> dict[str, Any]:
    """Every precondition, rechecked against current state before mutating."""

    world = context.world
    validate_actor_decision(decision_event, context, option, label="war declaration")
    params = dict(option.parameters)
    declaring_sect_id = str(params["declaring_sect_id"])
    target_sect_id = str(params["target_sect_id"])
    if context.actor_ref != sect_institution_ref(declaring_sect_id):
        raise StaleAffordanceError("war declaration names another actor")
    authorizer = force_authorizer(world, declaring_sect_id)
    if authorizer is None or not has_material_force(world, declaring_sect_id):
        raise StaleAffordanceError("force-employment authority or capacity changed")
    if authorizer != (
        str(params["authorizing_office_id"]),
        str(params["authorizing_holder_avatar_id"]),
    ):
        raise StaleAffordanceError(
            "the office holder that authorized this option was replaced"
        )
    if not has_active_sect_institution(
        world, target_sect_id, current_month=int(world.month_stamp)
    ):
        raise StaleAffordanceError("the target institution is missing or inactive")
    overlays = _overlays(context)
    causes = dict(known_casus_belli(world, declaring_sect_id, overlays=overlays))
    cause_id = str(params["casus_belli_event_id"])
    aggression = causes.get(cause_id)
    if (
        aggression is None
        or str(aggression["initiator_sect_id"]) != target_sect_id
        or str(aggression["initiator_avatar_id"]) != str(params["aggressor_avatar_id"])
        or str(aggression["target_avatar_id"]) != str(params["victim_avatar_id"])
    ):
        raise StaleAffordanceError(
            "the cause is unknown, already spent, or names another aggression"
        )
    return params


def _execute_declaration(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event: Event | None = None,
    **_: Any,
) -> Event:
    world = context.world
    params = _revalidated(context, option, decision_event)
    declaring_sect_id = str(params["declaring_sect_id"])
    target_sect_id = str(params["target_sect_id"])
    before = world.institutional_relations.get_relation(
        str(params["declaring_institution_id"]), str(params["target_institution_id"])
    )
    names = {
        "declaring": _sect_name(world, declaring_sect_id),
        "target": _sect_name(world, target_sect_id),
    }
    event = Event(
        world.month_stamp,
        t(
            "{declaring} declared war on {target} over a deliberate attack on one of its members.",
            **names,
        ),
        related_sects=[int(declaring_sect_id), int(target_sect_id)],
        is_major=True,
        event_type=WAR_DECLARED_EVENT_TYPE,
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            # The existing chain/UI contract for this event type.
            "sect_id": declaring_sect_id,
            "target_sect_id": target_sect_id,
            "reason": "deliberate_attack_on_member",
            "casus_belli_event_id": str(params["casus_belli_event_id"]),
            "authorizing_office_id": str(params["authorizing_office_id"]),
            "authorizing_holder_avatar_id": str(
                params["authorizing_holder_avatar_id"]
            ),
            "affordance_id": option.id,
        },
    )
    after = set_formal_war(
        world,
        declaring_sect_id,
        target_sect_id,
        current_month=int(world.month_stamp),
        evidence_event_ids=(event.id,),
    )
    deltas = [
        StateDelta(
            event_id=event.id,
            owner_kind="institutional_relation",
            owner_id=after.id,
            aspect=aspect,
            before=before_value,
            after=after_value,
        ).to_dict()
        for aspect, before_value, after_value in (
            ("kind", "none" if before is None else before.kind.value, after.kind.value),
            (
                "since_month",
                "none" if before is None else str(before.since_month),
                str(after.since_month),
            ),
            (
                "evidence_event_ids",
                "" if before is None else ",".join(before.evidence_event_ids),
                ",".join(after.evidence_event_ids),
            ),
        )
        if before_value != after_value
    ]
    event.causal_payload = {
        "deltas": deltas,
        "reason": "deliberate_attack_on_member",
        "casus_belli_event_id": str(params["casus_belli_event_id"]),
        _PAYLOAD_KEY: params,
    }
    event.causal_links.extend(
        CausalLink(event_id=event.id, cause_event_id=cause_id, relation=relation)
        for cause_id, relation in (
            (decision_event.id, CausalRelation.MOTIVATED_BY),
            (str(params["casus_belli_event_id"]), CausalRelation.RESPONSE_TO),
        )
        if cause_id
    )
    # Only the actual belligerents are formally notified of their own war;
    # nothing here is broadcast to the rest of the world.
    record_known_fact(
        world,
        event,
        (
            str(params["declaring_institution_id"]),
            str(params["target_institution_id"]),
        ),
    )
    return event


DOMAIN_AFFORDANCES.register_provider(DECLARATION_DOMAIN, declaration_affordances)
DOMAIN_AFFORDANCES.register_executor(DECLARE_ACTION, _execute_declaration)


InjectedDecisions = (
    Mapping[str, DomainDecision]
    | Callable[[str, str, Event], DomainDecision | None]
    | None
)


def _injected(
    injected_decisions: InjectedDecisions, sect_id: str, trigger_event: Event
) -> DomainDecision | None:
    if injected_decisions is None:
        return None
    if callable(injected_decisions):
        return injected_decisions(DECLARATION_DOMAIN, sect_id, trigger_event)
    return injected_decisions.get(f"{DECLARATION_DOMAIN}:{sect_id}")


async def process_institutional_war_declaration(
    world: Any,
    *,
    event_overlays: tuple[Event, ...] = (),
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    injected_decisions: InjectedDecisions = None,
    force_rule: bool = False,
    budget: CausalBudget | None = None,
) -> list[Event]:
    """One decision cycle of war declaration for every eligible sect.

    A sect with no known, unspent cause never reaches the interpreter, so a
    peaceful world costs nothing and produces nothing.
    """

    budget = budget or CausalBudget.from_world(world)
    overlays = tuple(event_overlays)
    produced: list[Event] = []
    for sect in active_sects(world):
        sect_id = str(sect.id)
        causes = known_casus_belli(world, sect_id, overlays=overlays)
        if not causes:
            continue
        trigger = event_lookup(world, overlays)(causes[0][0])
        if trigger is None:
            continue
        context = WarAffordanceContext(
            world,
            DECLARATION_DOMAIN,
            sect_institution_ref(sect_id),
            trigger,
            None,
            overlays,
        )
        options = DOMAIN_AFFORDANCES.compose(context)
        if not options:
            continue
        if budget is not None and not budget.consume_interpreter_call():
            continue
        readings = [
            reading.to_dict()
            for option in options
            if (
                reading := casus_belli_reading(
                    world, option, alternatives=options, overlays=overlays
                )
            )
            is not None
        ]
        decision, decision_event = await interpret_domain_affordances(
            world,
            domain=DECLARATION_DOMAIN,
            actor_ref=context.actor_ref,
            actor_label=str(getattr(sect, "name", sect_id)),
            trigger_event=trigger,
            affordances=options,
            task_name=INTERPRETER_TASK_NAME,
            template_name=INTERPRETER_TEMPLATE,
            extra_context={
                "role": "aggrieved_institution",
                "casus_belli_readings": readings,
            "institution": institutional_decision_context(
                world,
                sect_institution_id(sect_id),
                event_overlays=(trigger, *overlays),
                authority_scope=AuthorityScope.FORCE_EMPLOYMENT,
            ),
            },
            llm_call=llm_call,
            force_rule=force_rule,
            injected_decision=_injected(injected_decisions, sect_id, trigger),
        )
        produced.append(decision_event)
        overlays = (*overlays, decision_event)
        if decision.decision is not DomainDecisionKind.ACT:
            continue
        if budget is not None and not budget.consume_domain_mutation():
            continue
        try:
            declared = DOMAIN_AFFORDANCES.execute(
                context,
                decision.selected_affordance_id or "",
                decision_event=decision_event,
            )
        except StaleAffordanceError:
            # A stale, superseded or forged selection changes nothing at all.
            declared = stale_affordance_blocked_event(
                context,
                decision_event_id=decision_event.id,
                selected_affordance_id=decision.selected_affordance_id or "",
            )
        produced.append(declared)
        overlays = (*overlays, declared)
    return produced


__all__ = [
    "AGGRESSION_URGENCY_SCALE",
    "CasusBelliReading",
    "DECLARATION_DOMAIN",
    "DECLARE_ACTION",
    "INTERPRETER_TEMPLATE",
    "WarAffordanceContext",
    "can_employ_force",
    "canonical_war_declaration",
    "casus_belli_reading",
    "declaration_affordances",
    "force_authorizer",
    "has_material_force",
    "known_casus_belli",
    "process_institutional_war_declaration",
    "war_declaration_payload",
]

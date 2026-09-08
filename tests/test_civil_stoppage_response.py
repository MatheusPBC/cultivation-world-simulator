"""An independent government answer to a public work stoppage that happened.

Nothing here compels a repair. The government may act or maintain, and
maintaining is a real answer. It answers only a stoppage that canonical state
records, that it actually learned, in a city it actually administers -- and it
never pretends an interruption whose single cycle is over is still under way.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.environment.city_state import CityGovernance
from src.classes.event import Event, FactKind
from src.classes.institution import InstitutionalKnowledgeState
from src.classes.mechanical_language import EntityRef, MechanicalLanguageState
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.civil_petition import (
    PETITION_ACTION,
    STOPPAGE_ACTION,
    STOPPAGE_EVENT_TYPE,
    canonical_stoppage_payload,
    civil_response_is_open,
    stoppage_already_answered,
    stoppage_payload,
    stoppage_response_receipt_id,
)
from src.systems.government_reactivity import (
    enqueue_pending_stoppages,
    process_government_reactivity,
)
from tests.test_civil_petition import (  # reuse the civil fixtures
    _Ctx,
    _Sim,
    _condition_invalidation,
    _inject_population_choice,
    aggrieved,  # noqa: F401
)
from tests.test_civil_work_stoppage import (
    _declare,
    working_city,  # noqa: F401
)


MATERIAL_EVENT_TYPES = (
    "city_maintenance_completed",
    "urban_capacity_project_started",
)


def _advance(world, months: int = 1) -> None:
    world.month_stamp = type(world.month_stamp)(int(world.month_stamp) + months)


async def _stopped(world, working_city):  # noqa: F811
    """A real, persisted work stoppage, one cycle in the past."""
    city, trigger, condition = working_city
    world.event_manager.add_event(trigger)
    _option, decision, stoppage = await _declare(world, city, trigger, condition)
    world.event_manager.add_event(decision)
    world.event_manager.add_event(stoppage)
    _advance(world)
    return city, trigger, condition, stoppage


async def _answer(world, *, budget=None):
    """The government's own reaction cycle, through the real dispatcher."""
    invalidations = DomainInvalidationQueue()
    enqueue_pending_stoppages(world, invalidations)
    produced = await process_government_reactivity(
        world,
        current_events=[],
        invalidations=invalidations,
        budget=budget or CausalBudget.from_world(world),
    )
    return produced


def _answers_to(produced, stoppage) -> list[Event]:
    return [
        event for event in produced
        if event.fact_kind is FactKind.DECISION
        and any(link.cause_event_id == stoppage.id for link in event.causal_links)
    ]


def _institution_id(stoppage) -> str:
    return str(stoppage_payload(stoppage)["addressed_institution_id"])


def _government_context(world, stoppage, condition=None):
    from src.systems.government_interpreter import government_affordance_context

    context, _region, _dynasty = government_affordance_context(
        world, stoppage, condition
    )
    return context


@pytest.mark.asyncio
async def test_the_government_answers_a_real_stoppage_with_its_own_decision(
    base_world, working_city  # noqa: F811
):
    """The whole chain, with two independent decisions and one material owner."""
    city, _trigger, _condition, stoppage = await _stopped(base_world, working_city)
    asset_before = city.city_state.assets[0].integrity

    produced = await _answer(base_world)

    answers = _answers_to(produced, stoppage)
    assert answers, "the government never answered the persisted stoppage"
    government_decision = answers[0]
    # Two independent authors: the population that stopped working, and the
    # dynasty that answered. Both are resolved from the chain itself.
    population_decision = next(
        base_world.event_manager.get_event_by_id(link.cause_event_id)
        for link in stoppage.causal_links
        if link.relation is CausalRelation.TRIGGERED_BY
        and base_world.event_manager.get_event_by_id(link.cause_event_id) is not None
        and base_world.event_manager.get_event_by_id(link.cause_event_id).fact_kind
        is FactKind.DECISION
    )
    stopped_by = AgentDecision.from_dict(
        population_decision.causal_payload["decision"]
    )
    answered_by = AgentDecision.from_dict(
        government_decision.causal_payload["decision"]
    )
    assert stopped_by.subject_kind == "population"
    assert answered_by.subject_kind == "dynasty"
    assert population_decision.id != government_decision.id

    material = [
        event for event in produced
        if event.event_type in MATERIAL_EVENT_TYPES
        and any(
            link.cause_event_id == government_decision.id
            for link in event.causal_links
        )
    ]
    assert material, "no material owner answered the stoppage"
    assert material[0].causal_payload["deltas"], "the answer moved nothing"
    assert city.city_state.assets[0].integrity != asset_before

    # Answered exactly once, and never again.
    assert stoppage_already_answered(
        base_world, stoppage.id, _institution_id(stoppage)
    )
    _advance(base_world)
    assert not _answers_to(await _answer(base_world), stoppage)


@pytest.mark.asyncio
async def test_a_maintain_with_no_options_is_a_real_answer(
    base_world, working_city  # noqa: F811
):
    """An intact city can materially do nothing, and saying so closes the fact."""
    city, _trigger, _condition, stoppage = await _stopped(base_world, working_city)
    city.city_state.assets = [
        replace(asset, integrity=1.0) for asset in city.city_state.assets
    ]

    context = _government_context(base_world, stoppage)
    from src.systems.collective_affordances import government_affordances

    assert government_affordances(context) == ()

    produced = await _answer(base_world)

    assert _answers_to(produced, stoppage), "a maintain is still an answer"
    assert not [e for e in produced if e.event_type in MATERIAL_EVENT_TYPES]
    assert stoppage_already_answered(
        base_world, stoppage.id, _institution_id(stoppage)
    )


@pytest.mark.asyncio
async def test_a_resolved_pressure_is_answered_without_a_substitute_condition(
    base_world, working_city  # noqa: F811
):
    """The grievance is gone; the fact, and the damage, are not."""
    city, _trigger, condition, stoppage = await _stopped(base_world, working_city)
    # The pressure really resolves, on a real resolution fact of its own --
    # never on the stoppage, which did not resolve anything.
    resolution = Event(
        base_world.month_stamp,
        "The pressure abates.",
        event_type="semantic_condition_resolved",
        fact_kind=FactKind.DERIVED_CONDITION,
        causal_origin=CausalOrigin.DERIVED_CONDITION,
        render_params={
            "region_id": str(city.id),
            "condition_definition_id": str(condition.definition_id),
        },
        causal_payload={"deltas": []},
        causal_links=[CausalLink(
            event_id="",
            cause_event_id=condition.cause_event_id,
            relation=CausalRelation.RESOLVES,
        )],
    )
    base_world.event_manager.add_event(resolution)
    condition = replace(
        condition,
        resolved_month=int(base_world.month_stamp),
        resolution_event_id=resolution.id,
    )
    base_world.mechanical_language.condition_instances[condition.id] = condition
    assert not condition.is_active(int(base_world.month_stamp))

    # A still-damaged asset still yields a real option, with the urgency the
    # damage itself states -- not a decorative zero.
    context = _government_context(base_world, stoppage)
    from src.systems.collective_affordances import government_affordances

    options = government_affordances(context)
    maintenance = [o for o in options if o.action_kind == "urban_maintenance"]
    assert maintenance, "real damage produced no option without a condition"
    assert maintenance[0].urgency == pytest.approx(
        1.0 - city.city_state.assets[0].integrity
    )

    produced = await _answer(base_world)
    assert _answers_to(produced, stoppage)
    assert stoppage_already_answered(
        base_world, stoppage.id, _institution_id(stoppage)
    )
    # No substitute condition was invented to carry the answer.
    assert base_world.mechanical_language.get_active_conditions(
        EntityRef("region", str(city.id)), int(base_world.month_stamp)
    ) == []


@pytest.mark.asyncio
async def test_a_government_that_never_learned_the_stoppage_answers_nothing(
    base_world, working_city  # noqa: F811
):
    """Knowledge gates the dispatcher and the registry alike."""
    city, _trigger, condition, stoppage = await _stopped(base_world, working_city)
    base_world.institutional_knowledge.known_facts.clear()

    assert not civil_response_is_open(
        base_world, city, stoppage, stoppage_payload(stoppage), "stoppage"
    )
    # Even composed directly, with a perfectly valid condition in hand.
    from src.systems.collective_affordances import government_affordances

    assert government_affordances(
        _government_context(base_world, stoppage, condition)
    ) == ()
    assert not _answers_to(await _answer(base_world), stoppage)


@pytest.mark.asyncio
async def test_a_government_without_urban_authority_answers_nothing(
    base_world, working_city  # noqa: F811
):
    """Governing on paper is not the same as being able to act."""
    city, _trigger, _condition, stoppage = await _stopped(base_world, working_city)
    # The office loses its holder, so `can_actor_act_for` correctly refuses.
    emperor = base_world.avatar_manager.get_avatar(
        base_world.dynasty.current_emperor_id
    )
    emperor.is_dead = True

    assert not civil_response_is_open(
        base_world, city, stoppage, stoppage_payload(stoppage), "stoppage"
    )
    assert not _answers_to(await _answer(base_world), stoppage)
    assert not stoppage_already_answered(
        base_world, stoppage.id, _institution_id(stoppage)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("with_condition", [True, False])
async def test_an_unrecognised_or_foreign_stoppage_offers_nothing(
    base_world, working_city, with_condition  # noqa: F811
):
    """A trigger that merely looks like a stoppage buys no response."""
    from src.systems.collective_affordances import government_affordances

    city, trigger, condition, stoppage = await _stopped(base_world, working_city)

    forged = Event(
        base_world.month_stamp,
        "The people of nowhere stop working.",
        event_type=STOPPAGE_EVENT_TYPE,
        fact_kind=stoppage.fact_kind,
        causal_origin=stoppage.causal_origin,
        render_params={"region_id": str(city.id)},
        causal_payload={
            "deltas": [],
            "civil_work_stoppage": dict(stoppage_payload(stoppage)),
        },
    )
    # Never stored, so canonical state does not recognise it.
    assert canonical_stoppage_payload(base_world, forged) is None
    assert government_affordances(
        _government_context(
            base_world, forged, condition if with_condition else None
        )
    ) == ()

    # And a real stoppage from another city is not answerable here either.
    other = dict(stoppage_payload(stoppage))
    other["region_id"] = "999"
    assert not civil_response_is_open(base_world, city, stoppage, other, "stoppage")
    assert trigger is not None


@pytest.mark.asyncio
async def test_a_world_that_moves_on_mid_decision_blocks_but_keeps_the_choice(
    base_world, working_city  # noqa: F811
):
    """Authority lost during the await: audited as the act it really was."""
    from unittest.mock import patch

    import src.systems.government_reactivity as reactivity

    city, _trigger, _condition, stoppage = await _stopped(base_world, working_city)
    asset_before = city.city_state.assets[0].integrity
    original = reactivity.interpret_government_transition

    async def decide_then_lose_control(*args, **kwargs):
        result = await original(*args, **kwargs)
        city.city_state.governance = CityGovernance("dynasty", "2", 1.0)
        return result

    with patch.object(
        reactivity, "interpret_government_transition", decide_then_lose_control
    ):
        produced = await _answer(base_world)

    assert [e for e in produced if "blocked" in str(e.event_type)]
    assert city.city_state.assets[0].integrity == asset_before
    # The attempt happened and is closed; the audited choice stays an act.
    receipt = base_world.mechanical_language.reaction_receipts[
        stoppage_response_receipt_id(stoppage.id, _institution_id(stoppage))
    ]
    assert receipt.decision == "act"


@pytest.mark.asyncio
async def test_an_exhausted_budget_leaves_the_stoppage_unanswered(
    base_world, working_city  # noqa: F811
):
    """Budget exhaustion must not bury the fact."""
    _city, _trigger, _condition, stoppage = await _stopped(base_world, working_city)

    spent = CausalBudget.from_world(base_world)
    while spent.consume_domain_mutation():
        pass

    await _answer(base_world, budget=spent)
    assert not stoppage_already_answered(
        base_world, stoppage.id, _institution_id(stoppage)
    )

    produced = await _answer(base_world)
    assert _answers_to(produced, stoppage)
    assert stoppage_already_answered(
        base_world, stoppage.id, _institution_id(stoppage)
    )


@pytest.mark.asyncio
async def test_a_month_rollback_releases_the_response(
    base_world, working_city  # noqa: F811
):
    """The receipt is durable state, and a rolled-back month really releases it."""
    from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint

    _city, _trigger, _condition, stoppage = await _stopped(base_world, working_city)
    institution_id = _institution_id(stoppage)
    # The knowledge that makes the answer possible survived into this month.
    assert base_world.institutional_knowledge.contains(institution_id, stoppage.id)

    checkpoint = SimulationMonthCheckpoint.capture(base_world)
    await _answer(base_world)
    assert stoppage_already_answered(base_world, stoppage.id, institution_id)

    checkpoint.restore()

    assert not stoppage_already_answered(base_world, stoppage.id, institution_id)
    assert base_world.institutional_knowledge.contains(institution_id, stoppage.id)

    # And the released state is what a reload would really see: the response
    # receipt is gone from the serialized owner, the knowledge is not.
    language = MechanicalLanguageState.from_dict(
        base_world.mechanical_language.to_dict()
    )
    knowledge = InstitutionalKnowledgeState.from_dict(
        base_world.institutional_knowledge.to_dict(),
        base_world.institutional_authority,
    )
    assert (
        stoppage_response_receipt_id(stoppage.id, institution_id)
        not in language.reaction_receipts
    )
    assert knowledge.contains(institution_id, stoppage.id)


@pytest.mark.asyncio
async def test_the_real_phases_carry_pressure_to_stoppage_to_answer(
    base_world, working_city  # noqa: F811
):
    """Three real cycles through the phase hooks, with injected valid choices."""
    from src.sim.simulator_engine.phase_registry import (
        react_government,
        react_population,
    )

    city, trigger, condition = working_city
    base_world.event_manager.add_event(trigger)

    # Cycle one: the population petitions.
    first = _Ctx(base_world)
    first.invalidations.mark(_condition_invalidation(base_world, trigger, condition))
    with _inject_population_choice(PETITION_ACTION):
        await react_population(_Sim(base_world), first)
    for event in first.events:
        base_world.event_manager.add_event(event)
    _advance(base_world)

    # Cycle two: the same unresolved pressure escalates to a work stoppage.
    second = _Ctx(base_world)
    second.invalidations.mark(_condition_invalidation(base_world, trigger, condition))
    with _inject_population_choice(STOPPAGE_ACTION):
        await react_population(_Sim(base_world), second)
    stoppages = [e for e in second.events if e.event_type == STOPPAGE_EVENT_TYPE]
    assert stoppages, "react_population produced no work stoppage"
    stoppage = stoppages[0]
    for event in second.events:
        base_world.event_manager.add_event(event)
    _advance(base_world)

    # Cycle three: the government phase itself answers the stoppage.
    third = _Ctx(base_world)
    await react_government(_Sim(base_world), third)

    answers = _answers_to(third.events, stoppage)
    assert answers, "react_government never answered the persisted stoppage"
    assert stoppage_already_answered(
        base_world, stoppage.id, _institution_id(stoppage)
    )
    # The two decisions are the population's and the government's, and the
    # stoppage is what the second one answers.
    assert any(
        link.relation is CausalRelation.RESPONSE_TO
        and link.cause_event_id == stoppage.id
        for link in answers[0].causal_links
    )
    # The answer names the very interruption the region's economy records.
    assert city.economy.work_stoppage.start_event_id == stoppage.id

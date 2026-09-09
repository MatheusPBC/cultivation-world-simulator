"""The civil vertical: grounded pressure, a public petition, a free answer.

Protest only. Nothing here organizes a rebellion, names a leader, creates a
faction, or compels a repair. The population may petition, migrate, or do
neither; the government may act or maintain, and maintaining is a real answer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.classes.causal_link import CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.environment.city_state import CityGovernance
from src.classes.event import FactKind
from src.classes.institution import KnowledgeChannel
from src.classes.mechanical_language import (
    DerivedMetricDefinition,
    EntityRef,
    PrimitiveDimension,
)
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.civil_petition import (
    PETITION_ACTION,
    PETITION_EVENT_TYPE,
    already_responded,
    can_file_public_petition,
    is_detrimental_condition,
    petition_payload,
    petition_receipt_id,
)
from src.systems.collective_affordances import population_affordances
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
)
from src.systems.institution_bootstrap import (
    bootstrap_institutional_authority,
    synchronize_institutional_authority,
)
from tests.domain_reactivity_fixtures import setup_government_condition


@pytest.fixture
def aggrieved(base_world):
    """A governed city under a grounded, detrimental risk condition."""
    city, trigger, condition = setup_government_condition(base_world)
    city.population = 100
    city.population_capacity = 1000  # not crowded: migration is unattractive
    base_world.run_config_snapshot = {"test_mode": True}
    # A real living sovereign: the dynasty's office needs a holder, or
    # `can_actor_act_for` correctly refuses and nothing can be answered.
    emperor = _emperor(base_world)
    base_world.dynasty.current_emperor_id = emperor.id
    bootstrap_institutional_authority(base_world)
    # Bootstrap is idempotent and never moves an existing office's holder, so
    # the sovereign office would still name whoever the shared fixture
    # registered. Reconciliation is the runtime path that actually installs a
    # new holder, and this fixture must leave the office pointing at the
    # emperor it just declared.
    synchronize_institutional_authority(base_world)
    return city, trigger, condition


def _emperor(world):
    from src.classes.age import Age
    from src.classes.alignment import Alignment
    from src.classes.core.avatar import Avatar, Gender
    from src.classes.root import Root
    from src.systems.cultivation import Realm
    from src.systems.time import Month, Year, create_month_stamp
    from src.utils.id_generator import get_avatar_id

    avatar = Avatar(
        world=world, name="Sovereign", id=get_avatar_id(),
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(30, Realm.Qi_Refinement, innate_max_lifespan=80),
        gender=Gender.MALE, pos_x=0, pos_y=0, root=Root.GOLD,
        personas=[], alignment=Alignment.RIGHTEOUS,
    )
    avatar.personas = []
    avatar.technique = None
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _context(world, trigger, condition, region):
    """The production context builder, so the actor_ref is the real one."""
    from src.systems.population_interpreter import population_affordance_context

    context, _region, _condition = population_affordance_context(world, trigger)
    return context


def _petition_option(world, trigger, condition, region):
    options = population_affordances(_context(world, trigger, condition, region))
    return next(
        (item for item in options if item.action_kind == PETITION_ACTION), None
    )


def _decision_shape_actor(context):
    """The actor the production context really addresses."""
    return context.actor_ref


async def _decision_event(world, region, option, trigger):
    """The production decision fact, built by the real domain interpreter.

    Not a hand-shaped lookalike: the same builder the population phase uses,
    with an injected choice, so the shape under test is the shape that ships.
    """
    from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
    from src.systems.domain_decision_interpreter import interpret_domain_affordances

    context = _context(world, trigger, None, region)
    _decision, event = await interpret_domain_affordances(
        world,
        domain="population",
        actor_ref=context.actor_ref,
        actor_label=str(region.id),
        trigger_event=trigger,
        affordances=(option,),
        task_name="population_interpreter",
        template_name="population_interpreter.txt",
        force_rule=True,
        injected_decision=DomainDecision(
            DomainDecisionKind.ACT, "The people petition.", option.id
        ),
    )
    return event


class _Ctx:
    """The minimum a phase reads from the step context."""

    def __init__(self, world):
        self.events = []
        self.invalidations = DomainInvalidationQueue()
        self.causal_budget = CausalBudget.from_world(world)

    def add_events(self, new_events):
        if new_events:
            self.events.extend(new_events)


class _Sim:
    def __init__(self, world):
        self.world = world


def _condition_invalidation(world, trigger, condition):
    from src.sim.simulator_engine.domain_invalidation import (
        DomainInvalidation,
        DomainInvalidationLayer,
        DomainInvalidationReason,
    )

    return DomainInvalidation(
        layer=DomainInvalidationLayer.SEMANTIC,
        domain="population",
        target_kind="region",
        target_id=str(condition.target_id),
        reason=DomainInvalidationReason.CONDITION_ACTIVATED,
        source_event_ids=(trigger.id,),
        condition_instance_id=condition.id,
        revision=trigger.id,
    )


def _inject_population_choice(action_kind: str):
    """Make the real interpreter select the option of this kind."""
    from contextlib import contextmanager
    from unittest.mock import patch

    from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
    import src.systems.population_interpreter as interpreter

    original = interpreter.interpret_domain_affordances

    async def choose(*args, **kwargs):
        options = tuple(kwargs.get("affordances") or ())
        chosen = next(
            (item for item in options if item.action_kind == action_kind), None
        )
        decision = (
            DomainDecision(DomainDecisionKind.ACT, "The people speak.", chosen.id)
            if chosen is not None
            else DomainDecision(DomainDecisionKind.MAINTAIN, "Nothing to say.")
        )
        return await original(*args, **{**kwargs, "injected_decision": decision})

    @contextmanager
    def _scope():
        with patch.object(interpreter, "interpret_domain_affordances", choose):
            yield

    return _scope()


async def _pre_execute(world, city, trigger, condition):
    """The real option and the real decision, stopping before execution."""
    option = _petition_option(world, trigger, condition, city)
    assert option is not None
    decision = await _decision_event(world, city, option, trigger)
    return option, decision, None


async def _file_petition(world, city, trigger, condition):
    """One filed petition, through the real option, decision and executor."""
    option = _petition_option(world, trigger, condition, city)
    assert option is not None
    decision = await _decision_event(world, city, option, trigger)
    context = _context(world, trigger, condition, city)
    petition = DOMAIN_AFFORDANCES.execute(
        context, option.id,
        decision_event_id=decision.id, decision_event=decision,
    )
    return option, decision, petition


def test_only_detrimental_conditions_can_be_petitioned(base_world, aggrieved):
    city, _trigger, condition = aggrieved
    assert is_detrimental_condition(base_world, condition)

    # A high `access` reading is a good thing, not a grievance.
    base_world.mechanical_language.derived_definitions["clinic-risk-metric"] = (
        DerivedMetricDefinition(
            id="clinic-risk-metric",
            concept_id="clinic-risk-metric",
            dimension=PrimitiveDimension.ACCESS,
            target_kind="region",
            expression={"op": "constant", "value": 1.0, "unit": "ratio"},
            unit="ratio",
            created_month=int(base_world.month_stamp),
        )
    )
    assert not is_detrimental_condition(base_world, condition)
    assert not can_file_public_petition(base_world, city, condition)


def test_a_petition_is_offered_beside_migration_and_never_forced(
    base_world, aggrieved
):
    city, trigger, condition = aggrieved
    options = population_affordances(_context(base_world, trigger, condition, city))

    kinds = {option.action_kind for option in options}
    assert PETITION_ACTION in kinds
    # Offering is not deciding: NO_ACTION and migration both remain available
    # to the interpreter, which this module never overrides.
    assert all(option.action_kind != "civil_unrest" for option in options)


def test_an_uninhabited_or_ungoverned_region_offers_nothing(base_world, aggrieved):
    city, _trigger, condition = aggrieved
    city.population = 0
    assert not can_file_public_petition(base_world, city, condition)

    city.population = 100
    city.city_state.governance = CityGovernance("sect", "9", 1.0)
    assert not can_file_public_petition(base_world, city, condition)


def test_a_free_standing_condition_object_authorizes_nothing(base_world, aggrieved):
    from dataclasses import replace

    city, _trigger, condition = aggrieved
    impostor = replace(condition, id="not-registered")
    assert not can_file_public_petition(base_world, city, impostor)


def test_a_step_local_condition_can_still_be_petitioned(base_world, aggrieved):
    """The activating fact is in this phase's events, not yet in storage."""
    city, trigger, condition = aggrieved
    assert base_world.event_manager.get_event_by_id(trigger.id) is None

    assert can_file_public_petition(
        base_world, city, condition, overlays=(trigger,)
    )
    assert _petition_option(base_world, trigger, condition, city) is not None


@pytest.mark.asyncio
async def test_filing_records_the_fact_and_only_the_addressed_institution_knows(
    base_world, aggrieved
):
    city, trigger, condition = aggrieved
    option, decision, _p = await _pre_execute(base_world, city, trigger, condition)
    context = _context(base_world, trigger, condition, city)

    event = DOMAIN_AFFORDANCES.execute(
        context, option.id,
        decision_event_id=decision.id, decision_event=decision,
    )

    assert event.event_type == PETITION_EVENT_TYPE
    assert event.causal_origin is CausalOrigin.ACTOR_DECISION
    payload = petition_payload(event)
    assert payload["region_id"] == str(city.id)
    assert payload["metric_dimension"] == "risk"
    assert payload["evidence_event_ids"] == [trigger.id]
    assert payload["addressed_institution_ref"] == {"kind": "dynasty", "id": "1"}
    # It compels nothing: no material owner moved.
    assert all(
        d["owner_kind"] == "institutional_knowledge"
        for d in event.causal_payload["deltas"]
    )

    institution_id = payload["addressed_institution_id"]
    fact = base_world.institutional_knowledge.get_fact(institution_id, event.id)
    assert fact is not None
    assert fact.channel is KnowledgeChannel.FORMAL_NOTICE
    # Nobody else learned it, and no memory was fabricated.
    assert list(base_world.institutional_knowledge.known_facts.values())[0].institution_id == institution_id
    assert base_world.institutional_relations.memories_for(institution_id) == ()


@pytest.mark.asyncio
async def test_a_mismatched_decision_id_is_refused(base_world, aggrieved):
    city, trigger, condition = aggrieved
    option, decision, _p = await _pre_execute(base_world, city, trigger, condition)
    context = _context(base_world, trigger, condition, city)

    with pytest.raises(StaleAffordanceError):
        DOMAIN_AFFORDANCES.execute(
            context, option.id,
            decision_event_id="some-other-id", decision_event=decision,
        )
    assert base_world.institutional_knowledge.known_facts == {}


@pytest.mark.asyncio
async def test_the_same_grievance_is_not_petitioned_twice(base_world, aggrieved):
    city, trigger, condition = aggrieved
    option, decision, _p = await _pre_execute(base_world, city, trigger, condition)
    context = _context(base_world, trigger, condition, city)

    DOMAIN_AFFORDANCES.execute(
        context, option.id,
        decision_event_id=decision.id, decision_event=decision,
    )

    assert not can_file_public_petition(base_world, city, condition)
    assert _petition_option(base_world, trigger, condition, city) is None
    # Other domains keep reacting to the same unresolved pressure.
    assert base_world.mechanical_language.get_active_conditions(
        EntityRef("region", str(city.id)), int(base_world.month_stamp)
    )


@pytest.mark.asyncio
async def test_the_government_answers_a_persisted_petition_next_cycle(
    base_world, aggrieved
):
    """Government runs before population, so the answer is the next cycle."""
    from src.systems.government_reactivity import (
        enqueue_pending_petitions,
        process_government_reactivity,
    )

    city, trigger, condition = aggrieved
    option, decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(trigger)
    base_world.event_manager.add_event(petition)

    invalidations = DomainInvalidationQueue()
    enqueue_pending_petitions(base_world, invalidations)
    produced = await process_government_reactivity(
        base_world, current_events=[], invalidations=invalidations
    )

    decisions = [e for e in produced if e.fact_kind is FactKind.DECISION]
    assert decisions, "the government never considered the petition"
    # The petition is what it answered, and the condition stays as evidence.
    assert any(
        link.cause_event_id == petition.id
        and link.relation is CausalRelation.RESPONSE_TO
        for link in decisions[0].causal_links
    )
    # One answer per petition: a rescan raises nothing further.
    assert already_responded(base_world, petition.id)
    again = DomainInvalidationQueue()
    enqueue_pending_petitions(base_world, again)
    assert await process_government_reactivity(
        base_world, current_events=[], invalidations=again
    ) == []


@pytest.mark.asyncio
async def test_the_real_phase_hooks_answer_a_petition_next_month(
    base_world, aggrieved
):
    """Through `react_government` itself, not the helper: two real cycles."""
    from src.sim.simulator_engine.phase_registry import react_government

    from src.sim.simulator_engine.phase_registry import react_population

    city, trigger, condition = aggrieved
    base_world.event_manager.add_event(trigger)
    asset_before = city.city_state.assets[0].integrity

    # Cycle one: the population phase itself produces the petition, choosing
    # it through the real interpreter rather than a fabricated call.
    first = _Ctx(base_world)
    first.invalidations.mark(_condition_invalidation(base_world, trigger, condition))
    with _inject_population_choice(PETITION_ACTION):
        await react_population(_Sim(base_world), first)

    petitions = [e for e in first.events if e.event_type == PETITION_EVENT_TYPE]
    assert petitions, "react_population produced no petition"
    petition = petitions[0]
    # The petition names the population decision that authored it.
    authored_by = {
        link.cause_event_id for link in petition.causal_links
        if link.relation is CausalRelation.TRIGGERED_BY
    }
    population_decision = next(
        (e for e in first.events
         if e.fact_kind is FactKind.DECISION and e.id in authored_by),
        None,
    )
    assert population_decision is not None
    for event in first.events:
        base_world.event_manager.add_event(event)

    # Month advances; the government phase runs on the next cycle.
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )

    ctx = _Ctx(base_world)
    await react_government(_Sim(base_world), ctx)

    # The government really considered it, and answered the petition itself.
    answered = [
        event for event in ctx.events
        if event.fact_kind is FactKind.DECISION
        and any(
            link.cause_event_id == petition.id for link in event.causal_links
        )
    ]
    assert answered, "react_government never answered the persisted petition"
    assert already_responded(base_world, petition.id)
    government_decision = answered[0]

    # A specific material response, linked to this petition's own decision,
    # not merely any event that happens to carry a delta.
    material = [
        event for event in ctx.events
        if event.event_type in (
            "city_maintenance_completed", "urban_capacity_project_started"
        )
        and any(
            link.cause_event_id == government_decision.id
            for link in event.causal_links
        )
    ]
    assert material, "no material owner answered the petition"
    deltas = material[0].causal_payload["deltas"]
    assert deltas, "the material answer recorded no owner transition"
    assert city.city_state.assets[0].integrity != asset_before or any(
        d["before"] != d["after"] for d in deltas
    )
    # The population's own decision is still the petition's author.
    assert population_decision.fact_kind is FactKind.DECISION

    # Running the phase again next month answers nothing further.
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )
    second = _Ctx(base_world)
    await react_government(_Sim(base_world), second)
    assert not [
        event for event in second.events
        if any(link.cause_event_id == petition.id for link in event.causal_links)
    ]


@pytest.mark.asyncio
async def test_an_exhausted_budget_leaves_the_petition_pending(
    base_world, aggrieved
):
    """Budget exhaustion must not bury the grievance."""
    from src.systems.government_reactivity import (
        enqueue_pending_petitions,
        process_government_reactivity,
    )

    city, trigger, condition = aggrieved
    _option, _decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(petition)

    spent = CausalBudget.from_world(base_world)
    while spent.consume_domain_mutation():
        pass

    invalidations = DomainInvalidationQueue()
    enqueue_pending_petitions(base_world, invalidations)
    await process_government_reactivity(
        base_world, current_events=[], invalidations=invalidations, budget=spent
    )

    # Nothing was executed, so the petition is still open for the next cycle.
    assert not already_responded(base_world, petition.id)

    # And with a fresh budget the grievance really is answered.
    retry = DomainInvalidationQueue()
    enqueue_pending_petitions(base_world, retry)
    produced = await process_government_reactivity(
        base_world, current_events=[], invalidations=retry,
        budget=CausalBudget.from_world(base_world),
    )
    assert produced
    assert already_responded(base_world, petition.id)


@pytest.mark.asyncio
async def test_losing_the_controller_while_deciding_blocks_without_mutating(
    base_world, aggrieved
):
    """The world moves on mid-decision: blocked, audited, and nothing changes."""
    from unittest.mock import patch

    import src.systems.government_reactivity as reactivity
    from src.systems.government_reactivity import (
        enqueue_pending_petitions,
        process_government_reactivity,
    )

    city, trigger, condition = aggrieved
    _option, _decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(petition)
    asset_before = city.city_state.assets[0].integrity
    original = reactivity.interpret_government_transition

    async def decide_then_lose_control(*args, **kwargs):
        result = await original(*args, **kwargs)
        # The region changes hands exactly while the answer is being decided.
        city.city_state.governance = CityGovernance("dynasty", "2", 1.0)
        return result

    invalidations = DomainInvalidationQueue()
    enqueue_pending_petitions(base_world, invalidations)
    with patch.object(
        reactivity, "interpret_government_transition", decide_then_lose_control
    ):
        produced = await process_government_reactivity(
            base_world, current_events=[], invalidations=invalidations
        )

    # The attempt is audited as blocked, not silently dropped or crashed.
    blocked = [
        event for event in produced
        if "blocked" in str(event.event_type)
    ]
    assert blocked, "a stale rebuild produced no blocked audit"
    # And nothing material moved.
    assert city.city_state.assets[0].integrity == asset_before


@pytest.mark.asyncio
async def test_a_changed_controller_answers_nothing(base_world, aggrieved):
    from src.systems.government_reactivity import (
        enqueue_pending_petitions,
        process_government_reactivity,
    )

    city, trigger, condition = aggrieved
    option, decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(petition)

    # The region changes hands after the petition was addressed to A.
    city.city_state.governance = CityGovernance("dynasty", "2", 1.0)

    invalidations = DomainInvalidationQueue()
    enqueue_pending_petitions(base_world, invalidations)
    produced = await process_government_reactivity(
        base_world, current_events=[], invalidations=invalidations
    )

    assert produced == []
    assert not already_responded(base_world, petition.id)


@pytest.mark.asyncio
async def test_test_mode_reaches_no_provider(base_world, aggrieved, monkeypatch):
    from src.systems.government_reactivity import (
        enqueue_pending_petitions,
        process_government_reactivity,
    )

    provider = AsyncMock(side_effect=AssertionError("no provider call allowed"))
    monkeypatch.setattr(
        "src.systems.government_interpreter.call_llm_with_task_name", provider,
        raising=False,
    )

    city, trigger, condition = aggrieved
    option, decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(petition)

    invalidations = DomainInvalidationQueue()
    enqueue_pending_petitions(base_world, invalidations)
    await process_government_reactivity(
        base_world, current_events=[], invalidations=invalidations
    )
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_petition_survives_a_sqlite_round_trip(base_world, aggrieved, tmp_path):
    from src.classes.event_storage import EventStorage

    city, trigger, condition = aggrieved
    option, decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )

    storage = EventStorage(tmp_path / "events.db")
    try:
        assert storage.add_event(trigger) is True
        assert storage.add_event(petition) is True
        restored = storage.get_event_by_id(petition.id)
        links = storage.get_causal_links_for_event(petition.id)
    finally:
        storage.close()

    assert petition_payload(restored) == petition_payload(petition)
    assert restored.causal_payload["deltas"] == petition.causal_payload["deltas"]
    assert trigger.id in {link.cause_event_id for link in links}


@pytest.mark.asyncio
async def test_receipts_and_knowledge_survive_a_state_round_trip(
    base_world, aggrieved
):
    """The durable proof, not only the event payload.

    A reloaded world must still know the petition and still hold the receipt,
    or the same grievance would be filed again after a load.
    """
    from src.classes.institution import InstitutionalKnowledgeState
    from src.classes.mechanical_language import MechanicalLanguageState

    city, trigger, condition = aggrieved
    _option, _decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    institution_id = petition_payload(petition)["addressed_institution_id"]

    language = MechanicalLanguageState.from_dict(
        base_world.mechanical_language.to_dict()
    )
    knowledge = InstitutionalKnowledgeState.from_dict(
        base_world.institutional_knowledge.to_dict(),
        base_world.institutional_authority,
    )

    receipt_key = petition_receipt_id(str(city.id), str(condition.id))
    assert receipt_key in language.reaction_receipts
    restored_fact = knowledge.get_fact(institution_id, petition.id)
    assert restored_fact is not None
    assert restored_fact.channel is KnowledgeChannel.FORMAL_NOTICE

    # A reloaded world does not re-file the same grievance.
    base_world.mechanical_language = language
    base_world.institutional_knowledge = knowledge
    assert not can_file_public_petition(
        base_world, city, condition, overlays=(trigger,)
    )


@pytest.mark.asyncio
async def test_a_month_rollback_releases_the_petition(base_world, aggrieved):
    from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint

    city, trigger, condition = aggrieved
    option, decision, _p = await _pre_execute(base_world, city, trigger, condition)
    context = _context(base_world, trigger, condition, city)

    checkpoint = SimulationMonthCheckpoint.capture(base_world)
    DOMAIN_AFFORDANCES.execute(
        context, option.id,
        decision_event_id=decision.id, decision_event=decision,
    )
    assert base_world.institutional_knowledge.known_facts != {}

    checkpoint.restore()

    assert base_world.institutional_knowledge.known_facts == {}
    assert base_world.mechanical_language.reaction_receipts == {}
    # The grievance is open again, exactly as it was.
    assert can_file_public_petition(
        base_world, city, condition, overlays=(trigger,)
    )

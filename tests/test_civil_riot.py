"""A riot: a real crowd, a declared physical aptitude, and real damage.

Every material term is either declared in config or read from an existing
owner. Severity never becomes violence on its own: with no unmet demand, no
declared crowd damage profile, or nobody in the district, there is simply no
option. Administrative capacity plays no part -- it repairs cities, it does not
guard them.

Nothing here creates a leader, an organization, troops, or repression, and no
escalation is scripted from a petition or a stoppage.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalRelation
from src.classes.environment.city_state import (
    CityDistrict,
    UrbanAsset,
    UrbanCrowdDamageProfile,
    UrbanServiceDemand,
)
from src.classes.event import FactKind
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.civil_riot import (
    MAX_RIOT_DAMAGE,
    RIOT_ACTION,
    RIOT_EVENT_TYPE,
    aggrieved_crowd_wan,
    already_rioted,
    can_join_public_riot,
    riot_already_answered,
    riot_damage,
    riot_payload,
    riotable_targets,
    service_shortfall,
)
from src.systems.collective_affordances import population_affordances
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
)
from tests.test_civil_petition import (  # reuse the civil fixtures
    _Ctx,
    _Sim,
    _condition_invalidation,
    _context,
    _decision_event,
    aggrieved,  # noqa: F401
)

# Luna's V1 calibration, declared in config for water assets: reachable
# fabric, forty 万 of effort for a full point of integrity.
PROFILE = UrbanCrowdDamageProfile(crowd_exposure=0.6, breach_effort_wan=40.0)


def _riotable_city(city, *, profile=PROFILE, weight=1.0, capacity=10.0):
    """The fixture city, with a declared profile and a real service deficit.

    The clinic serves `healing`, the capability the fixture's grievance is
    really about. Declared demand of 1.0 per 万 against a small, damaged asset
    is a genuine shortfall, not a number chosen to force an outcome.
    """
    assets = tuple(
        replace(asset, crowd_damage_profile=profile, capacity=capacity)
        for asset in city.city_state.assets
    )
    city.city_state = replace(
        city.city_state,
        districts=tuple(
            CityDistrict(d.id, d.kind, d.tile_refs, weight)
            for d in city.city_state.districts
        ),
        assets=assets,
        service_demands=(UrbanServiceDemand("healing", 1.0),),
    )
    return city


@pytest.fixture
def rioting(base_world, aggrieved):  # noqa: F811
    city, trigger, condition = aggrieved
    return _riotable_city(city), trigger, condition


def _riot_option(base_world, city, trigger, condition):
    options = population_affordances(_context(base_world, trigger, condition, city))
    return next((o for o in options if o.action_kind == RIOT_ACTION), None)


async def _riot(base_world, city, trigger, condition):
    """One real riot, through the real option, decision and executor."""
    option = _riot_option(base_world, city, trigger, condition)
    assert option is not None, "no grounded riot was offered"
    decision = await _decision_event(base_world, city, option, trigger)
    context = _context(base_world, trigger, condition, city)
    event = DOMAIN_AFFORDANCES.execute(
        context, option.id,
        decision_event_id=decision.id, decision_event=decision,
    )
    return option, decision, event


# --------------------------------------------------------------------------
# The material law
# --------------------------------------------------------------------------


def test_the_law_reads_only_declared_material_terms(base_world, rioting):
    city, _trigger, _condition = rioting
    asset = city.city_state.assets[0]

    # effective capacity 10 * 0.4 * 0.5 = 2.0 against a declared load of 100.
    assert service_shortfall(city, "healing") == pytest.approx(0.98)
    # 100 万 in the district * 0.98 unmet * 0.20 participation.
    assert aggrieved_crowd_wan(city, asset, "healing") == pytest.approx(19.6)
    # 19.6 * 0.6 / 40 = 0.294, capped by the owner's own repair scale.
    assert riot_damage(city, asset, "healing") == pytest.approx(MAX_RIOT_DAMAGE)


def test_administrative_capacity_never_immunises_a_city(base_world, rioting):
    """Admin capacity repairs cities; it does not guard them."""
    city, trigger, condition = rioting
    asset = city.city_state.assets[0]
    baseline = riot_damage(city, asset, "healing")

    for capacity in (0.0, 1.0):
        city.city_state = replace(
            city.city_state,
            governance=replace(
                city.city_state.governance, administrative_capacity=capacity
            ),
        )
        assert riot_damage(city, asset, "healing") == pytest.approx(baseline)
        # And a fully administered city is still riotable.
        assert can_join_public_riot(
            base_world, city, condition, overlays=(trigger,)
        )


@pytest.mark.parametrize(
    "mutate,reason",
    (
        (lambda city: _riotable_city(city, profile=None), "no declared profile"),
        (lambda city: _riotable_city(city, weight=0.0), "nobody in the district"),
        (lambda city: _riotable_city(city, capacity=1000.0), "no unmet demand"),
    ),
)
def test_a_missing_material_term_offers_nothing(
    base_world, aggrieved, mutate, reason  # noqa: F811
):
    """Ignorance and sufficiency both block; neither is called immunity."""
    city, trigger, condition = aggrieved
    mutate(city)

    assert riotable_targets(
        base_world, city, condition, overlays=(trigger,)
    ) == (), reason
    assert not can_join_public_riot(
        base_world, city, condition, overlays=(trigger,)
    )
    assert _riot_option(base_world, city, trigger, condition) is None


def test_a_story_grievance_authorises_no_riot(base_world, rioting):
    """Narrative never moves matter."""
    city, trigger, condition = rioting
    trigger.is_story = True
    base_world.event_manager.add_event(trigger)

    assert riotable_targets(base_world, city, condition, overlays=(trigger,)) == ()


# --------------------------------------------------------------------------
# The menu
# --------------------------------------------------------------------------


def test_the_menu_states_the_self_harm_it_would_cause(base_world, rioting):
    """The choice can be weighed: crowd, declared effort, and service after."""
    city, trigger, condition = rioting
    option = _riot_option(base_world, city, trigger, condition)
    assert option is not None

    params = option.parameters
    assert params["asset_id"] == city.city_state.assets[0].id
    assert params["capability_id"] == "healing"
    assert params["crowd_wan"] == pytest.approx(19.6)
    assert params["breach_effort_wan"] == pytest.approx(40.0)
    # Breaking the clinic really lowers the very service being demanded.
    assert params["service_access_after_damage"] < params["service_access_now"]
    # Migration and the other civil rungs are still on the same menu.
    kinds = {
        item.action_kind
        for item in population_affordances(
            _context(base_world, trigger, condition, city)
        )
    }
    assert "file_public_petition" in kinds


# --------------------------------------------------------------------------
# The act
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_real_riot_damages_the_asset_and_lowers_the_service(
    base_world, rioting
):
    """Choice -> damage -> a worse service, with a real delta and knowledge."""
    city, trigger, condition = rioting
    asset_before = city.city_state.assets[0].integrity
    access_before = city.city_state.service_access("healing", city.population)

    option, decision, event = await _riot(base_world, city, trigger, condition)

    assert event.event_type == RIOT_EVENT_TYPE
    assert event.fact_kind is FactKind.STATE_TRANSITION
    payload = riot_payload(event)
    assert payload is not None
    assert payload["damage"] == pytest.approx(MAX_RIOT_DAMAGE)

    # A real owner transition, naming the asset unambiguously.
    delta = event.causal_payload["deltas"][0]
    assert delta["aspect"] == "urban_asset_integrity"
    assert float(delta["before"]) == pytest.approx(asset_before)
    assert event.causal_payload["asset_id"] if "asset_id" in event.causal_payload \
        else payload["asset_id"] == city.city_state.assets[0].id
    assert city.city_state.assets[0].integrity == pytest.approx(
        asset_before - MAX_RIOT_DAMAGE
    )
    # The riot really hurt the service the crowd was demanding.
    assert city.city_state.service_access("healing", city.population) < access_before

    # Authored by the population's own decision.
    assert any(
        link.relation is CausalRelation.TRIGGERED_BY
        and link.cause_event_id == decision.id
        for link in event.causal_links
    )
    audit = AgentDecision.from_dict(decision.causal_payload["decision"])
    assert audit.subject_kind == "population"

    # One riot per grievance, and only the governing institution learns it.
    assert already_rioted(base_world, str(city.id), str(condition.id))
    institution_id = payload["addressed_institution_id"]
    assert base_world.institutional_knowledge.contains(institution_id, event.id)
    assert _riot_option(base_world, city, trigger, condition) is None


@pytest.mark.asyncio
async def test_a_forged_decision_moves_nothing(base_world, rioting):
    """The owner revalidates: no decision, no damage."""
    city, trigger, condition = rioting
    option = _riot_option(base_world, city, trigger, condition)
    decision = await _decision_event(base_world, city, option, trigger)
    context = _context(base_world, trigger, condition, city)
    before = city.city_state.assets[0].integrity

    # A citation that does not match the fact being validated.
    with pytest.raises(StaleAffordanceError):
        DOMAIN_AFFORDANCES.execute(
            context, option.id,
            decision_event_id="not-this-decision", decision_event=decision,
        )
    # And no decision at all.
    with pytest.raises(StaleAffordanceError):
        DOMAIN_AFFORDANCES.execute(
            context, option.id, decision_event_id=decision.id, decision_event=None,
        )
    assert city.city_state.assets[0].integrity == pytest.approx(before)


@pytest.mark.asyncio
async def test_the_direct_owner_accepts_a_genuine_riot(base_world, rioting):
    """The baseline the refusals are measured against.

    `DomainAffordance.parameters` is a `MappingProxyType`, so a gate that
    tested for `dict` would reject every real option and make every refusal
    test pass for the wrong reason.
    """
    from src.systems.city_damage import execute_crowd_damage

    city, trigger, condition = rioting
    option = _riot_option(base_world, city, trigger, condition)
    decision = await _decision_event(base_world, city, option, trigger)
    before = city.city_state.assets[0].integrity

    event = execute_crowd_damage(
        _context(base_world, trigger, condition, city), option,
        decision_event_id=decision.id, decision_event=decision,
    )

    assert event.event_type == RIOT_EVENT_TYPE
    assert city.city_state.assets[0].integrity == pytest.approx(
        before - MAX_RIOT_DAMAGE
    )
    # One door, one complete operation: the direct owner spends the receipt and
    # records the knowledge itself, so it cannot be used to write damage for
    # free and then repeat.
    assert already_rioted(base_world, str(city.id), str(condition.id))
    assert base_world.institutional_knowledge.contains(
        riot_payload(event)["addressed_institution_id"], event.id
    )
    with pytest.raises(StaleAffordanceError):
        execute_crowd_damage(
            _context(base_world, trigger, condition, city), option,
            decision_event_id=decision.id, decision_event=decision,
        )


@pytest.mark.asyncio
async def test_a_forged_option_claiming_more_damage_is_refused(base_world, rioting):
    """The owner accepts only an option the provider composes right now."""
    from dataclasses import replace as dc_replace

    from src.systems.city_damage import execute_crowd_damage

    city, trigger, condition = rioting
    real = _riot_option(base_world, city, trigger, condition)
    before = city.city_state.assets[0].integrity
    # A well-formed option claiming total destruction. Its content differs, so
    # its canonical id differs, so the live composition does not contain it.
    forged = dc_replace(
        real, parameters={**dict(real.parameters), "damage": 1.0}, id=""
    )
    assert forged.id != real.id
    decision = await _decision_event(base_world, city, forged, trigger)
    context = _context(base_world, trigger, condition, city)

    with pytest.raises(StaleAffordanceError):
        execute_crowd_damage(
            context, forged,
            decision_event_id=decision.id, decision_event=decision,
        )
    assert city.city_state.assets[0].integrity == pytest.approx(before)


@pytest.mark.asyncio
async def test_a_riot_cannot_be_replayed_through_the_owner(base_world, rioting):
    """The spent receipt empties the live menu, so a direct call is refused."""
    from src.systems.city_damage import execute_crowd_damage

    city, trigger, condition = rioting
    option, decision, _event = await _riot(base_world, city, trigger, condition)
    after_first = city.city_state.assets[0].integrity

    with pytest.raises(StaleAffordanceError):
        execute_crowd_damage(
            _context(base_world, trigger, condition, city), option,
            decision_event_id=decision.id, decision_event=decision,
        )
    assert city.city_state.assets[0].integrity == pytest.approx(after_first)


# --------------------------------------------------------------------------
# The government's answer
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_government_answers_a_known_riot_next_cycle(base_world, rioting):
    """A real answer, on its own decision, with RESPONSE_TO and a receipt."""
    from src.systems.government_reactivity import (
        enqueue_pending_riots,
        process_government_reactivity,
    )

    city, trigger, condition = rioting
    base_world.event_manager.add_event(trigger)
    _option, decision, riot = await _riot(base_world, city, trigger, condition)
    base_world.event_manager.add_event(decision)
    base_world.event_manager.add_event(riot)
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )
    institution_id = riot_payload(riot)["addressed_institution_id"]

    invalidations = DomainInvalidationQueue()
    enqueue_pending_riots(base_world, invalidations)
    produced = await process_government_reactivity(
        base_world, current_events=[], invalidations=invalidations,
        budget=CausalBudget.from_world(base_world),
    )

    answers = [
        event for event in produced
        if event.fact_kind is FactKind.DECISION
        and any(
            link.relation is CausalRelation.RESPONSE_TO
            and link.cause_event_id == riot.id
            for link in event.causal_links
        )
    ]
    assert answers, "the government never answered the riot it knew about"
    assert AgentDecision.from_dict(
        answers[0].causal_payload["decision"]
    ).subject_kind == "dynasty"
    assert riot_already_answered(base_world, riot.id, institution_id)

    # Maintain is legitimate; if it acted, it acted through its repair menu.
    material = [
        e for e in produced
        if e.event_type in ("city_maintenance_completed",
                            "urban_capacity_project_started")
    ]
    for event in material:
        assert event.causal_payload["deltas"]
    # Nothing suppressed anybody: no force event exists in this world.
    assert not [e for e in produced if "repress" in str(e.event_type)]


def _government_context(base_world, trigger, condition=None):
    from src.systems.government_interpreter import government_affordance_context

    context, _region, _dynasty = government_affordance_context(
        base_world, trigger, condition
    )
    return context


@pytest.mark.asyncio
async def test_an_unrecognised_riot_offers_the_registry_nothing(base_world, rioting):
    """A valid condition must not launder a riot canonical state never stored."""
    from src.classes.event import Event
    from src.systems.collective_affordances import government_affordances

    city, trigger, condition = rioting
    base_world.event_manager.add_event(trigger)
    _o, _d, riot = await _riot(base_world, city, trigger, condition)

    forged = Event(
        base_world.month_stamp,
        "A crowd broke into nothing.",
        event_type=RIOT_EVENT_TYPE,
        fact_kind=riot.fact_kind,
        causal_origin=riot.causal_origin,
        render_params={"region_id": str(city.id)},
        causal_payload={
            "deltas": [],
            "civil_riot": dict(riot_payload(riot)),
        },
    )
    # Never stored, so no canonical reading exists for it.
    from src.systems.civil_riot import canonical_riot_payload

    assert canonical_riot_payload(base_world, forged) is None
    # Empty even with a perfectly valid, live condition in hand.
    assert government_affordances(
        _government_context(base_world, forged, condition)
    ) == ()
    assert government_affordances(
        _government_context(base_world, forged, None)
    ) == ()


@pytest.mark.asyncio
async def test_a_resolved_grievance_still_offers_real_repair(base_world, rioting):
    """The riot's damage outlives its cause, and the menu says so."""
    from src.systems.collective_affordances import government_affordances

    city, trigger, condition = rioting
    base_world.event_manager.add_event(trigger)
    _o, _d, riot = await _riot(base_world, city, trigger, condition)
    base_world.event_manager.add_event(riot)
    damaged = city.city_state.assets[0].integrity
    assert damaged < 1.0

    # The pressure really resolves, on its own resolution fact.
    resolved = replace(
        condition,
        resolved_month=int(base_world.month_stamp),
        resolution_event_id=trigger.id,
    )
    base_world.mechanical_language.condition_instances[resolved.id] = resolved
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )

    options = government_affordances(_government_context(base_world, riot, None))
    maintenance = [o for o in options if o.action_kind == "urban_maintenance"]
    assert maintenance, "damaged fabric produced no repair option"
    # Urgency is the real damage, not a decorative zero and not the condition.
    assert maintenance[0].urgency == pytest.approx(1.0 - damaged)


@pytest.mark.asyncio
async def test_an_unknown_riot_is_never_answered(base_world, rioting):
    """Knowledge gates the answer, exactly as it does for a stoppage."""
    from src.systems.government_reactivity import (
        enqueue_pending_riots,
        process_government_reactivity,
    )

    city, trigger, condition = rioting
    base_world.event_manager.add_event(trigger)
    _o, decision, riot = await _riot(base_world, city, trigger, condition)
    base_world.event_manager.add_event(decision)
    base_world.event_manager.add_event(riot)
    base_world.institutional_knowledge.known_facts.clear()
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )

    invalidations = DomainInvalidationQueue()
    enqueue_pending_riots(base_world, invalidations)
    produced = await process_government_reactivity(
        base_world, current_events=[], invalidations=invalidations,
        budget=CausalBudget.from_world(base_world),
    )
    assert not [
        e for e in produced
        if any(link.cause_event_id == riot.id for link in e.causal_links)
    ]


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


def test_the_profile_serialises_strictly_and_null_means_unmodelled():
    """`null` is a declared gap in knowledge, and the key is never optional."""
    profiled = UrbanAsset(
        "gate", "core", ("water",), 10.0, 0.5, 1.0, crowd_damage_profile=PROFILE
    )
    assert UrbanAsset.from_dict(profiled.to_dict()) == profiled

    plain = UrbanAsset("gate", "core", ("water",), 10.0, 0.5, 1.0)
    payload = plain.to_dict()
    assert payload["crowd_damage_profile"] is None
    assert UrbanAsset.from_dict(payload) == plain
    assert plain.crowd_damage_profile is None

    # The key itself is required: an absent one is a malformed asset.
    del payload["crowd_damage_profile"]
    with pytest.raises(ValueError):
        UrbanAsset.from_dict(payload)

    # And the object is strict.
    for bad in ({"crowd_exposure": 1.4, "breach_effort_wan": 40.0},
                {"crowd_exposure": 0.6, "breach_effort_wan": 0.0},
                {"crowd_exposure": 0.6}):
        with pytest.raises(ValueError):
            UrbanCrowdDamageProfile.from_dict(bad)


@pytest.mark.asyncio
async def test_a_month_rollback_releases_the_riot(base_world, rioting):
    """Damage, knowledge and receipt are all released together."""
    from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint

    city, trigger, condition = rioting
    option = _riot_option(base_world, city, trigger, condition)
    decision = await _decision_event(base_world, city, option, trigger)
    context = _context(base_world, trigger, condition, city)
    before = city.city_state.assets[0].integrity

    checkpoint = SimulationMonthCheckpoint.capture(base_world)
    DOMAIN_AFFORDANCES.execute(
        context, option.id,
        decision_event_id=decision.id, decision_event=decision,
    )
    assert city.city_state.assets[0].integrity < before

    checkpoint.restore()

    region = base_world.map.regions[city.id]
    assert region.city_state.assets[0].integrity == pytest.approx(before)
    assert base_world.institutional_knowledge.known_facts == {}
    assert base_world.mechanical_language.reaction_receipts == {}


# --------------------------------------------------------------------------
# The integrated proof
# --------------------------------------------------------------------------


def _prefer_riot():
    """Select a riot when the engine really offered one, else maintain."""
    from contextlib import contextmanager
    from unittest.mock import patch

    from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
    import src.systems.population_interpreter as interpreter

    original = interpreter.interpret_domain_affordances

    async def choose(*args, **kwargs):
        options = tuple(kwargs.get("affordances") or ())
        chosen = next((o for o in options if o.action_kind == RIOT_ACTION), None)
        decision = (
            DomainDecision(DomainDecisionKind.ACT, "The crowd breaks in.", chosen.id)
            if chosen is not None
            else DomainDecision(DomainDecisionKind.MAINTAIN, "Nothing offered.")
        )
        return await original(*args, **{**kwargs, "injected_decision": decision})

    @contextmanager
    def _scope():
        with patch.object(interpreter, "interpret_domain_affordances", choose):
            yield

    return _scope()


RIOT_SIM_MONTHS = 12


@pytest.mark.asyncio
async def test_a_short_real_simulation_produces_the_whole_riot_chain():
    """Real `Simulator.step` months, no provider, no forced outcome.

    Not the phase hooks: the actual step loop. The general smoke neither
    requires nor demonstrates a riot; this dedicated fixture guarantees the
    pressure and the targets, and injects only a valid selection, leaving the
    engine to do the rest. Twelve months is this test's window, chosen like the
    stoppage fixture's because the canonical definitions need roughly seven
    months to activate a grievance -- not a figure the engine imposes.
    """
    from unittest.mock import AsyncMock, patch

    from src.sim.simulator import Simulator
    from tools.institutional_smoke import _world_factory

    world = _world_factory(pressured=True, commerce=False, seed=11)(0, 11)
    city = world.map.regions[302]
    # Declared, not inferred, and pinned by this fixture so the targets are
    # guaranteed rather than dependent on which assets config happens to
    # profile. The healing demand is the scenario's own pressure.
    city.city_state = replace(
        city.city_state,
        assets=tuple(
            replace(asset, crowd_damage_profile=PROFILE)
            for asset in city.city_state.assets
        ),
    )
    profiled = {asset.id for asset in city.city_state.assets}

    provider = AsyncMock(side_effect=AssertionError("no provider call allowed"))
    simulator = Simulator(world)
    captured = []
    with patch("src.utils.llm.client.call_llm_with_template", provider), \
            _prefer_riot():
        for _ in range(RIOT_SIM_MONTHS):
            captured.extend(await simulator.step())

    provider.assert_not_awaited()
    provider.assert_not_called()

    riots = [e for e in captured if e.event_type == RIOT_EVENT_TYPE]
    assert riots, "the pressured months offered no reachable riot"
    riot = riots[0]
    payload = riot_payload(riot)
    assert payload is not None
    assert payload["asset_id"] in profiled
    assert 0.0 < payload["damage"] <= MAX_RIOT_DAMAGE

    # A real owner transition, authored by the population's own decision.
    delta = riot.causal_payload["deltas"][0]
    assert delta["aspect"] == "urban_asset_integrity"
    assert float(delta["after"]) < float(delta["before"])
    authored_by = {
        link.cause_event_id for link in riot.causal_links
        if link.relation is CausalRelation.TRIGGERED_BY
    }
    population_decision = next(
        e for e in captured
        if e.id in authored_by and e.fact_kind is FactKind.DECISION
    )
    assert AgentDecision.from_dict(
        population_decision.causal_payload["decision"]
    ).subject_kind == "population"

    # The government answered it on a later cycle, inside the same run.
    answers = [
        e for e in captured
        if e.fact_kind is FactKind.DECISION
        and any(
            link.relation is CausalRelation.RESPONSE_TO
            and link.cause_event_id == riot.id
            for link in e.causal_links
        )
    ]
    assert answers, "no government ever answered the riot"
    answered_by = AgentDecision.from_dict(answers[0].causal_payload["decision"])
    assert answered_by.subject_kind == "dynasty"
    assert answered_by.month_stamp > int(riot.month_stamp)
    assert riot_already_answered(
        world, riot.id, payload["addressed_institution_id"]
    )
    # Nothing suppressed anybody: no force owner exists in this world.
    assert not [e for e in captured if "repress" in str(e.event_type)]


@pytest.mark.asyncio
async def test_the_real_phases_carry_a_riot_to_a_government_answer(
    base_world, rioting
):
    """The same chain driven through the phase hooks, on a controlled city.

    A narrower check than the `Simulator.step` run above, not a substitute for
    it: it fixes the numbers so the service drop can be asserted exactly.
    """
    from src.sim.simulator_engine.phase_registry import (
        react_government,
        react_population,
    )

    city, trigger, condition = rioting
    base_world.event_manager.add_event(trigger)
    access_before = city.city_state.service_access("healing", city.population)

    # Cycle one: the population phase itself produces the riot.
    first = _Ctx(base_world)
    first.invalidations.mark(_condition_invalidation(base_world, trigger, condition))
    with _prefer_riot():
        await react_population(_Sim(base_world), first)
    riots = [e for e in first.events if e.event_type == RIOT_EVENT_TYPE]
    assert riots, "react_population produced no riot"
    riot = riots[0]
    for event in first.events:
        base_world.event_manager.add_event(event)

    # The city really got worse at the thing the crowd was demanding.
    assert city.city_state.service_access("healing", city.population) < access_before

    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )

    # Cycle two: the government phase answers it, with no new phase involved.
    second = _Ctx(base_world)
    await react_government(_Sim(base_world), second)

    answers = [
        event for event in second.events
        if event.fact_kind is FactKind.DECISION
        and any(
            link.relation is CausalRelation.RESPONSE_TO
            and link.cause_event_id == riot.id
            for link in event.causal_links
        )
    ]
    assert answers, "react_government never answered the persisted riot"
    assert riot_already_answered(
        base_world, riot.id, riot_payload(riot)["addressed_institution_id"]
    )

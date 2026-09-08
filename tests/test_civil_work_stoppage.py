"""A minimal, real work stoppage owned by RegionalEconomyState.

One region, one cycle, a participation share bounded by the pressure's own
severity, and only the resources whose labour dependence is *declared* in
canonical config. Base `production_rates` are never written; a rate that
really changes during a stoppage keeps its new value afterwards.
"""

from __future__ import annotations

import json

import pytest

from src.classes.causal_link import CausalRelation
from src.classes.agent_decision import AgentDecision
from src.classes.event import FactKind
from src.classes.mechanical_language import MetricKey, PrimitiveDimension
from src.classes.regional_economy import (
    MAX_STOPPAGE_PARTICIPATION,
    RegionalEconomyState,
    WorkStoppage,
)
from src.systems.civil_petition import (
    STOPPAGE_ACTION,
    STOPPAGE_ENDED_EVENT_TYPE,
    STOPPAGE_EVENT_TYPE,
    can_declare_work_stoppage,
    expire_work_stoppages,
    labor_bearing_resources,
    petition_payload,
    stoppage_already_answered,
    stoppage_participation,
    stoppage_payload,
    stoppage_response_receipt_id,
)
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
)
from src.systems.regional_economy import phase_update_regional_economy
from src.systems.semantic_world.resolvers import resolve_metric
from tests.test_civil_petition import (  # reuse the civil fixtures
    _Ctx,
    _Sim,
    _condition_invalidation,
    _context,
    _decision_event,
    _file_petition,
    _inject_population_choice,
    aggrieved,  # noqa: F401
)


@pytest.fixture
def working_city(base_world, aggrieved):  # noqa: F811
    """A city that really produces one labour concept and one that is not."""
    city, trigger, condition = aggrieved
    city.economy = RegionalEconomyState(
        stocks={"grain": 10.0, "spirit_stone": 10.0},
        capacities={"grain": 1000.0, "spirit_stone": 1000.0},
        production_rates={"grain": 10.0, "spirit_stone": 10.0},
        demand_rates={"grain": 0.0, "spirit_stone": 0.0},
        # Declared in config, never inferred from the name at runtime.
        labor_dependence={"grain": 1.0, "spirit_stone": 0.0},
    )
    return city, trigger, condition


async def _declare(world, city, trigger, condition):
    """File a petition, then declare the stoppage through the real executor."""
    _o, petition_decision, petition = await _file_petition(
        world, city, trigger, condition
    )
    # Persisted, as `finalize_step` does in production: the stoppage is a
    # later cycle's option, grounded on a petition that really exists and on
    # the population decision that really authored it.
    world.event_manager.add_event(petition_decision)
    world.event_manager.add_event(petition)
    context = _context(world, trigger, condition, city)
    from src.systems.collective_affordances import population_affordances

    option = next(
        item for item in population_affordances(context)
        if item.action_kind == STOPPAGE_ACTION
    )
    decision = await _decision_event(world, city, option, trigger)
    event = DOMAIN_AFFORDANCES.execute(
        context, option.id,
        decision_event_id=decision.id, decision_event=decision,
    )
    return option, decision, event


def _production_reading(world, region, concept_id: str) -> float:
    return resolve_metric(
        world,
        MetricKey(
            PrimitiveDimension.FLOW, "region", str(region.id), concept_id,
            qualifiers=(("kind", "production"),),
        ),
        target=region,
        calculated_month=int(world.month_stamp),
    ).value


def test_a_stoppage_lasts_exactly_one_cycle_and_is_bounded():
    stoppage = WorkStoppage(
        started_month=5, ends_month=6, participation=0.1,
        source_event_id="p", decision_event_id="d", start_event_id="s",
    )
    assert stoppage.is_active(5)
    assert not stoppage.is_active(6) and stoppage.has_expired(6)

    for bad in ({"ends_month": 7}, {"ends_month": 5}, {"started_month": -1}):
        with pytest.raises(ValueError):
            WorkStoppage(**{
                "started_month": 5, "ends_month": 6, "participation": 0.1,
                "source_event_id": "p", "decision_event_id": "d",
                "start_event_id": "s", **bad,
            })
    with pytest.raises(ValueError):
        WorkStoppage(
            started_month=5, ends_month=6,
            participation=MAX_STOPPAGE_PARTICIPATION + 0.01,
            source_event_id="p", decision_event_id="d", start_event_id="s",
        )


def test_participation_is_bounded_by_the_pressures_own_severity(working_city):
    _city, _trigger, condition = working_city
    assert 0.0 < stoppage_participation(condition) <= MAX_STOPPAGE_PARTICIPATION
    assert stoppage_participation(condition) == pytest.approx(
        MAX_STOPPAGE_PARTICIPATION * float(condition.intensity)
    )


def test_only_declared_labour_with_real_output_is_offerable(base_world, working_city):
    city, trigger, condition = working_city
    assert labor_bearing_resources(city) == ["grain"]

    # Declared labour but no output: nothing to stop.
    city.economy.set_production_rate("grain", 0.0)
    assert labor_bearing_resources(city) == []
    assert not can_declare_work_stoppage(
        base_world, city, condition, overlays=(trigger,)
    )


@pytest.mark.asyncio
async def test_a_stoppage_needs_a_prior_local_petition(base_world, working_city):
    city, trigger, condition = working_city
    # No petition yet: the option is not offered.
    assert not can_declare_work_stoppage(
        base_world, city, condition, overlays=(trigger,)
    )

    _o, petition_decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(petition_decision)
    base_world.event_manager.add_event(petition)
    assert can_declare_work_stoppage(
        base_world, city, condition, overlays=(trigger,)
    )


@pytest.mark.asyncio
async def test_a_forged_petition_authorizes_no_stoppage(base_world, working_city):
    """A well-shaped payload is a claim, not a decision that ever happened."""
    from copy import deepcopy

    from src.classes.agent_decision import AgentDecision
    from src.classes.causal_link import CausalLink

    city, trigger, condition = working_city
    _o, real_decision, real_petition = await _file_petition(
        base_world, city, trigger, condition
    )

    # A copy with real evidence and empty deltas, but no authoring decision.
    forged = deepcopy(real_petition)
    forged.id = "forged-petition"
    forged.causal_links = []
    base_world.event_manager.add_event(forged)
    # It looks exactly like a real petition, evidence and all.
    assert petition_payload(forged) is not None
    assert not can_declare_work_stoppage(
        base_world, city, condition, overlays=(trigger,)
    )

    # And one whose decision names the wrong subject is refused too.
    wrong = deepcopy(real_petition)
    wrong.id = "wrong-subject-petition"
    bad_audit = AgentDecision(
        month_stamp=int(wrong.month_stamp),
        subject_kind="region",  # the real subject is `population`
        subject_id=str(city.id),
        source="injected",
        considered_count=1,
        chosen_chain=[{
            "selected_affordance_id": wrong.causal_payload["affordance_id"]
        }],
    )
    bad_decision = deepcopy(real_decision)
    bad_decision.id = "wrong-subject-decision"
    bad_decision.causal_payload = {
        **real_decision.causal_payload, "decision": bad_audit.to_dict()
    }
    wrong.causal_links = [CausalLink(
        event_id=wrong.id,
        cause_event_id=bad_decision.id,
        relation=CausalRelation.TRIGGERED_BY,
    )]
    base_world.event_manager.add_event(bad_decision)
    base_world.event_manager.add_event(wrong)
    assert not can_declare_work_stoppage(
        base_world, city, condition, overlays=(trigger,)
    )
    assert city.economy.work_stoppage is None


@pytest.mark.asyncio
async def test_declaring_records_the_fact_and_schedules_the_next_cycle(
    base_world, working_city
):
    city, trigger, condition = working_city
    month = int(base_world.month_stamp)

    _option, decision, event = await _declare(base_world, city, trigger, condition)

    assert event.event_type == STOPPAGE_EVENT_TYPE
    # The region's economy really gains the record, so this is a transition
    # with a real delta -- not an invented status string.
    assert event.fact_kind is FactKind.STATE_TRANSITION
    delta = event.causal_payload["deltas"][0]
    assert delta["owner_kind"] == "region"
    assert delta["aspect"] == "work_stoppage"
    assert delta["before"] is None
    assert json.loads(delta["after"]) == city.economy.work_stoppage.to_dict()
    payload = event.causal_payload["civil_work_stoppage"]
    assert payload["affected_resource_ids"] == ["grain"]
    assert payload["starts_month"] == month + 1
    assert payload["ends_month"] == month + 2

    stoppage = city.economy.work_stoppage
    assert stoppage.started_month == month + 1
    assert stoppage.decision_event_id == decision.id
    assert stoppage.start_event_id == event.id
    # Not active yet: it begins on the next productive cycle.
    assert not stoppage.is_active(month)
    assert stoppage.is_active(month + 1)
    # The base rate was never written.
    assert city.economy.production_rates["grain"] == 10.0


@pytest.mark.asyncio
async def test_effective_output_falls_only_for_declared_labour(
    base_world, working_city
):
    city, trigger, condition = working_city
    await _declare(base_world, city, trigger, condition)
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )
    month = int(base_world.month_stamp)
    share = city.economy.work_stoppage.participation

    assert city.economy.effective_production_rate("grain", month) == pytest.approx(
        10.0 * (1.0 - share)
    )
    # spirit_stone declares no labour dependence, so it is untouched.
    assert city.economy.effective_production_rate("spirit_stone", month) == 10.0
    # Metrics read exactly the same number the balance will use.
    assert _production_reading(base_world, city, "grain") == pytest.approx(
        10.0 * (1.0 - share)
    )
    assert _production_reading(base_world, city, "spirit_stone") == 10.0


@pytest.mark.asyncio
async def test_the_monthly_balance_links_lost_output_to_the_stoppage(
    base_world, working_city
):
    city, trigger, condition = working_city
    _option, _decision, start = await _declare(base_world, city, trigger, condition)
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )

    events = phase_update_regional_economy(base_world)

    grain = next(
        e for e in events
        if e.render_params.get("resource_id") == "grain"
        and e.event_type == "regional_resource_balance"
    )
    share = city.economy.work_stoppage.participation
    assert grain.render_params["produced"] == pytest.approx(10.0 * (1.0 - share))
    assert grain.render_params["forgone"] == pytest.approx(10.0 * share)
    assert any(
        link.cause_event_id == start.id
        and link.relation is CausalRelation.CONTRIBUTED_TO
        for link in grain.causal_links
    )

    # The non-labour resource lost nothing and is never attributed to it.
    stone = next(
        e for e in events
        if e.render_params.get("resource_id") == "spirit_stone"
        and e.event_type == "regional_resource_balance"
    )
    assert "forgone" not in stone.render_params
    assert not any(
        link.cause_event_id == start.id for link in stone.causal_links
    )


@pytest.mark.asyncio
async def test_a_full_warehouse_forgoes_nothing_and_blames_nothing(
    base_world, working_city
):
    city, trigger, condition = working_city
    await _declare(base_world, city, trigger, condition)
    # No headroom at all: the stoppage costs this resource nothing.
    city.economy.set_capacity("grain", 10.0)
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )

    events = phase_update_regional_economy(base_world)

    grain_events = [
        e for e in events if e.render_params.get("resource_id") == "grain"
    ]
    assert all("forgone" not in e.render_params for e in grain_events)
    assert all(
        e.event_type != "regional_production_forgone" for e in grain_events
    )


@pytest.mark.asyncio
async def test_the_stoppage_expires_by_its_own_duration_with_a_fact(
    base_world, working_city
):
    city, trigger, condition = working_city
    _option, _decision, start = await _declare(base_world, city, trigger, condition)
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 2
    )

    events = expire_work_stoppages(base_world)

    assert len(events) == 1
    ended = events[0]
    assert ended.event_type == STOPPAGE_ENDED_EVENT_TYPE
    assert ended.fact_kind is FactKind.STATE_TRANSITION
    ended_delta = ended.causal_payload["deltas"][0]
    assert ended_delta["aspect"] == "work_stoppage"
    # Real before/after: the record it held, then nothing.
    assert json.loads(ended_delta["before"])["start_event_id"] == start.id
    assert ended_delta["after"] is None
    assert any(
        link.cause_event_id == start.id and link.relation is CausalRelation.RESOLVES
        for link in ended.causal_links
    )
    assert city.economy.work_stoppage is None
    # It does not renew itself.
    assert expire_work_stoppages(base_world) == []


@pytest.mark.asyncio
async def test_a_base_rate_changed_during_the_stoppage_survives_its_end(
    base_world, working_city
):
    """No snapshot restore: real changes are not overwritten."""
    city, trigger, condition = working_city
    await _declare(base_world, city, trigger, condition)
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )
    city.economy.set_production_rate("grain", 4.0)
    share = city.economy.work_stoppage.participation
    assert city.economy.effective_production_rate(
        "grain", int(base_world.month_stamp)
    ) == pytest.approx(4.0 * (1.0 - share))

    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )
    expire_work_stoppages(base_world)

    assert city.economy.production_rates["grain"] == 4.0
    assert city.economy.effective_production_rate(
        "grain", int(base_world.month_stamp)
    ) == 4.0


@pytest.mark.asyncio
async def test_a_stale_declaration_is_refused_without_mutating(
    base_world, working_city
):
    city, trigger, condition = working_city
    _o, petition_decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(petition_decision)
    base_world.event_manager.add_event(petition)
    from src.systems.collective_affordances import population_affordances

    context = _context(base_world, trigger, condition, city)
    option = next(
        item for item in population_affordances(context)
        if item.action_kind == STOPPAGE_ACTION
    )
    decision = await _decision_event(base_world, city, option, trigger)

    # A second stoppage is not stacked on the first.
    DOMAIN_AFFORDANCES.execute(
        context, option.id, decision_event_id=decision.id, decision_event=decision
    )
    first = city.economy.work_stoppage
    with pytest.raises(StaleAffordanceError):
        DOMAIN_AFFORDANCES.execute(
            context, option.id,
            decision_event_id=decision.id, decision_event=decision,
        )
    assert city.economy.work_stoppage is first

    # And a mismatched decision id authorizes nothing.
    city.economy.clear_work_stoppage()
    with pytest.raises(StaleAffordanceError):
        DOMAIN_AFFORDANCES.execute(
            context, option.id,
            decision_event_id="not-the-decision", decision_event=decision,
        )
    assert city.economy.work_stoppage is None


@pytest.mark.asyncio
async def test_the_stoppage_survives_a_state_round_trip(base_world, working_city):
    city, trigger, condition = working_city
    await _declare(base_world, city, trigger, condition)

    restored = RegionalEconomyState.from_dict(city.economy.to_dict())

    assert restored.work_stoppage == city.economy.work_stoppage
    assert restored.labor_dependence == {"grain": 1.0, "spirit_stone": 0.0}
    # Strict schema: a save missing the new fields is rejected outright.
    stale = city.economy.to_dict()
    del stale["work_stoppage"]
    with pytest.raises(ValueError):
        RegionalEconomyState.from_dict(stale)


@pytest.mark.asyncio
async def test_a_month_rollback_releases_the_stoppage(base_world, working_city):
    from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint

    city, trigger, condition = working_city
    _o, petition_decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(petition_decision)
    base_world.event_manager.add_event(petition)
    checkpoint = SimulationMonthCheckpoint.capture(base_world)

    from src.systems.collective_affordances import population_affordances

    context = _context(base_world, trigger, condition, city)
    option = next(
        item for item in population_affordances(context)
        if item.action_kind == STOPPAGE_ACTION
    )
    decision = await _decision_event(base_world, city, option, trigger)
    DOMAIN_AFFORDANCES.execute(
        context, option.id, decision_event_id=decision.id, decision_event=decision
    )
    assert city.economy.work_stoppage is not None

    checkpoint.restore()

    assert city.economy.work_stoppage is None
    assert city.economy.production_rates["grain"] == 10.0


@pytest.mark.asyncio
async def test_the_real_phases_stop_work_then_resume_it(base_world, working_city):
    """react_population ACT -> reduced cycle -> expiry and resumption."""
    from src.sim.simulator_engine.phase_registry import react_population

    city, trigger, condition = working_city
    _o, petition_decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    for event in (trigger, petition_decision, petition):
        base_world.event_manager.add_event(event)

    # Cycle one: the population phase itself declares the stoppage.
    first = _Ctx(base_world)
    first.invalidations.mark(_condition_invalidation(base_world, trigger, condition))
    with _inject_population_choice(STOPPAGE_ACTION):
        await react_population(_Sim(base_world), first)
    starts = [e for e in first.events if e.event_type == STOPPAGE_EVENT_TYPE]
    assert starts, "react_population declared no stoppage"
    start = starts[0]
    for event in first.events:
        base_world.event_manager.add_event(event)
    share = city.economy.work_stoppage.participation

    # Cycle two: the productive month really produces less, and says why.
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )
    reduced = phase_update_regional_economy(base_world)
    grain = next(
        e for e in reduced
        if e.render_params.get("resource_id") == "grain"
        and e.event_type == "regional_resource_balance"
    )
    assert grain.render_params["produced"] == pytest.approx(10.0 * (1.0 - share))
    assert any(
        link.cause_event_id == start.id for link in grain.causal_links
    )

    # Cycle three: the duration alone ends it, and output resumes in full.
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )
    resumed = phase_update_regional_economy(base_world)
    ended = [e for e in resumed if e.event_type == STOPPAGE_ENDED_EVENT_TYPE]
    assert len(ended) == 1
    assert any(
        link.cause_event_id == start.id and link.relation is CausalRelation.RESOLVES
        for link in ended[0].causal_links
    )
    grain_again = next(
        e for e in resumed
        if e.render_params.get("resource_id") == "grain"
        and e.event_type == "regional_resource_balance"
    )
    assert grain_again.render_params["produced"] == pytest.approx(10.0)
    assert "forgone" not in grain_again.render_params
    assert city.economy.work_stoppage is None


@pytest.mark.asyncio
async def test_output_consumed_entirely_still_records_the_forgone_flow(
    base_world, working_city
):
    """Net stock zero because demand ate it -- distinct from a full warehouse."""
    city, trigger, condition = working_city
    _option, _decision, start = await _declare(base_world, city, trigger, condition)
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )
    share = city.economy.work_stoppage.participation
    # Demand exactly matches what is actually produced: stock does not move,
    # but real output was still forgone.
    city.economy.set_demand_rate("grain", 10.0 * (1.0 - share))

    events = phase_update_regional_economy(base_world)

    flow = next(
        e for e in events
        if e.event_type == "regional_production_forgone"
        and e.render_params.get("resource_id") == "grain"
    )
    assert flow.fact_kind is FactKind.OCCURRENCE
    # A flow fact with no invented before/after delta.
    assert flow.causal_payload["deltas"] == []
    assert flow.render_params["forgone"] == pytest.approx(10.0 * share)
    assert flow.render_params["produced"] == pytest.approx(10.0 * (1.0 - share))
    assert flow.render_params["consumed"] == pytest.approx(10.0 * (1.0 - share))
    assert any(
        link.cause_event_id == start.id for link in flow.causal_links
    )


STOPPAGE_SIM_MONTHS = 12


def _prefer_civil_choice():
    """Pick the civil option the engine really offered, else maintain.

    Nothing is forced: when neither a petition nor a stoppage is on the menu
    the population maintains, exactly as it would without this fixture.
    """
    from contextlib import contextmanager
    from unittest.mock import patch

    from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
    import src.systems.population_interpreter as interpreter
    from src.systems.civil_petition import PETITION_ACTION

    original = interpreter.interpret_domain_affordances

    async def choose(*args, **kwargs):
        options = tuple(kwargs.get("affordances") or ())
        chosen = next(
            (o for o in options if o.action_kind == STOPPAGE_ACTION), None
        ) or next((o for o in options if o.action_kind == PETITION_ACTION), None)
        decision = (
            DomainDecision(DomainDecisionKind.ACT, "The people act.", chosen.id)
            if chosen is not None
            else DomainDecision(DomainDecisionKind.MAINTAIN, "Nothing offered.")
        )
        return await original(*args, **{**kwargs, "injected_decision": decision})

    @contextmanager
    def _scope():
        with patch.object(interpreter, "interpret_domain_affordances", choose):
            yield

    return _scope()


@pytest.mark.asyncio
async def test_a_short_real_simulation_produces_the_whole_stoppage_chain():
    """Real `Simulator.step` months, no provider, no forced outcome.

    The canonical condition definitions need roughly seven months to activate,
    so a six-month window cannot reach a grievance at all; the run is sized to
    the engine's own activation windows rather than the rules being relaxed to
    fit a shorter one.
    """
    from unittest.mock import AsyncMock, patch

    from src.sim.simulator import Simulator
    from tools.institutional_smoke import _world_factory

    world = _world_factory(pressured=True, commerce=False, seed=11)(0, 11)
    # City 302 is one the smoke scenario actually governs *and* one the
    # canonical definitions activate a condition on in this window. The
    # scenario's own pressure (a healing-access deficit) is left untouched;
    # only this city's grain labour economy is declared.
    city = world.map.regions[302]
    # Real headroom and a real deficit, so pressure is legitimate and a
    # stoppage can actually cost output.
    city.economy = RegionalEconomyState(
        stocks={"grain": 20.0},
        capacities={"grain": 30.0},
        production_rates={"grain": 10.0},
        demand_rates={"grain": 14.0},
        labor_dependence={"grain": 1.0},
    )

    provider = AsyncMock(side_effect=AssertionError("no provider call allowed"))
    simulator = Simulator(world)
    captured = []
    with patch("src.utils.llm.client.call_llm_with_template", provider), \
            _prefer_civil_choice():
        for _ in range(STOPPAGE_SIM_MONTHS):
            captured.extend(await simulator.step())

    provider.assert_not_awaited()
    provider.assert_not_called()

    starts = [e for e in captured if e.event_type == STOPPAGE_EVENT_TYPE]
    assert starts, "the pressured months offered no reachable stoppage"
    start = starts[0]

    by_id = {e.id: e for e in captured}
    # The cost really was recorded, and it points back at this start.
    costed = [
        e for e in captured
        if any(
            link.cause_event_id == start.id for link in e.causal_links
        )
        and e.event_type in (
            "regional_resource_balance", "regional_production_forgone",
        )
    ]
    assert costed, "the stoppage cost nothing that was recorded"
    assert any(
        float(e.render_params.get("forgone", 0.0)) > 0.0 for e in costed
    )

    ended = [
        e for e in captured
        if e.event_type == STOPPAGE_ENDED_EVENT_TYPE
        and any(link.cause_event_id == start.id for link in e.causal_links)
    ]
    assert ended, "the stoppage never ended"

    # The government that administers this city answered the start fact with a
    # decision of its own, inside the same real `Simulator.step` months.
    answers = [
        e for e in captured
        if e.fact_kind is FactKind.DECISION
        and any(
            link.relation is CausalRelation.RESPONSE_TO
            and link.cause_event_id == start.id
            for link in e.causal_links
        )
    ]
    assert answers, "no government ever answered the persisted stoppage"
    audit = AgentDecision.from_dict(answers[0].causal_payload["decision"])
    assert audit.subject_kind == "dynasty"
    assert audit.month_stamp > int(start.month_stamp)
    institution_id = stoppage_payload(start)["addressed_institution_id"]
    assert stoppage_already_answered(world, start.id, institution_id)
    receipt = world.mechanical_language.reaction_receipts[
        stoppage_response_receipt_id(start.id, institution_id)
    ]
    assert receipt.decision_event_ids == (answers[0].id,)
    assert receipt.completed is True

    # No cause named by the chain is missing from what this run produced.
    for event in (start, *costed, *ended):
        for link in event.causal_links:
            assert link.cause_event_id in by_id or (
                world.event_manager.get_event_by_id(link.cause_event_id) is not None
            )


@pytest.mark.asyncio
async def test_the_population_phase_can_decline_to_stop_working(
    base_world, working_city
):
    """NO_ACTION stays valid: nothing forces the next rung."""
    from src.sim.simulator_engine.phase_registry import react_population

    city, trigger, condition = working_city
    _o, petition_decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(petition_decision)
    base_world.event_manager.add_event(petition)
    base_world.event_manager.add_event(trigger)

    ctx = _Ctx(base_world)
    ctx.invalidations.mark(_condition_invalidation(base_world, trigger, condition))
    # The interpreter is offered the stoppage and selects nothing.
    with _inject_population_choice("no_such_action"):
        await react_population(_Sim(base_world), ctx)

    assert city.economy.work_stoppage is None
    assert not [e for e in ctx.events if e.event_type == STOPPAGE_EVENT_TYPE]

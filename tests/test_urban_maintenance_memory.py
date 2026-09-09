"""A completed repair is remembered by the institution that made it.

The damage already became memory; the repair did not, so a government could
answer a riot and then have no record of having answered it. This adds the
other half, on the same terms: the observed improvement on the asset's own
0..1 scale, the other three factors frozen, and nothing else.

Cause-independent by construction: a riot, a condition and a petition all
leave the same record, because what is remembered is the improvement, not what
prompted it. No gratitude, no hostility, no reputation, no grievance marked
resolved, and a partial improvement stays partial.
"""

from __future__ import annotations

import pytest

from src.classes.institution import KnowledgeChannel
from src.systems.civil_riot import riot_payload
from tests.test_civil_petition import aggrieved  # noqa: F401
from tests.test_civil_riot import (
    PROFILE,
    _riot,
    _riotable_city,
    rioting,  # noqa: F401
)

MAINTENANCE_COMPLETED = "city_maintenance_completed"


def _memories(world, institution_id: str):
    return world.institutional_relations.memories_for(institution_id)


def _dynasty_institution_id(world) -> str:
    from src.classes.mechanical_language import EntityRef

    institution = world.institutional_authority.get_institution_for_owner(
        EntityRef("dynasty", str(world.dynasty.id))
    )
    assert institution is not None
    return institution.id


async def _government_repairs(base_world, city, trigger, condition):
    """The government's own reaction cycle, through the real dispatcher."""
    from src.sim.simulator_engine.causal_budget import CausalBudget
    from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
    from src.systems.government_reactivity import (
        enqueue_government_transitions,
        process_government_reactivity,
    )

    invalidations = DomainInvalidationQueue()
    enqueue_government_transitions(base_world, [trigger], invalidations)
    return await process_government_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=invalidations,
        budget=CausalBudget.from_world(base_world),
    )


# --------------------------------------------------------------------------
# The memory itself
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_completed_repair_is_remembered_at_its_real_size(
    base_world, aggrieved  # noqa: F811
):
    """`relative_scale` is the observed improvement, not a capped ratio."""
    from src.systems.city_maintenance import MAX_MAINTENANCE_IMPROVEMENT

    city, trigger, condition = aggrieved
    institution_id = _dynasty_institution_id(base_world)
    before = city.city_state.assets[0].integrity

    produced = await _government_repairs(base_world, city, trigger, condition)

    repairs = [e for e in produced if e.event_type == MAINTENANCE_COMPLETED]
    assert repairs, "the government completed no repair"
    repair = repairs[0]
    observed = city.city_state.assets[0].integrity - before
    assert observed > 0.0

    memories = [m for m in _memories(base_world, institution_id) if m.event_id == repair.id]
    assert len(memories) == 1
    factors = dict(memories[0].factors)
    assert factors["relative_scale"] == pytest.approx(observed)
    assert factors["relative_scale"] == pytest.approx(
        float(repair.causal_payload["deltas"][0]["magnitude"])
    )
    assert factors["relative_scale"] != pytest.approx(
        observed / MAX_MAINTENANCE_IMPROVEMENT
    )
    assert factors["institutional_change"] == 0.0
    assert factors["commitment_breach"] == 0.0
    assert factors["identity_anchor_impact"] == 0.0

    # It did the work itself.
    fact = base_world.institutional_knowledge.get_fact(institution_id, repair.id)
    assert fact is not None and fact.channel is KnowledgeChannel.OWN_ACTION
    # And nothing was thanked, resented or ranked.
    assert base_world.institutional_relations.relations == {}


@pytest.mark.asyncio
async def test_a_partial_improvement_stays_partial(base_world, aggrieved):  # noqa: F811
    """Nothing claims full recovery, and the memory says exactly how much."""
    city, trigger, condition = aggrieved
    institution_id = _dynasty_institution_id(base_world)
    before = city.city_state.assets[0].integrity
    assert before < 1.0

    produced = await _government_repairs(base_world, city, trigger, condition)
    repair = next(e for e in produced if e.event_type == MAINTENANCE_COMPLETED)

    after = city.city_state.assets[0].integrity
    assert after < 1.0, "the fixture's asset should not be fully restored"
    memory = next(
        m for m in _memories(base_world, institution_id) if m.event_id == repair.id
    )
    assert dict(memory.factors)["relative_scale"] == pytest.approx(after - before)
    # The grievance is untouched: no resolution was invented.
    assert condition.resolved_month is None
    assert condition.resolution_event_id is None


@pytest.mark.asyncio
async def test_the_repair_names_the_asset_it_really_improved(
    base_world, aggrieved  # noqa: F811
):
    """Another asset of the same capability is not falsely repaired."""
    from dataclasses import replace

    from src.classes.environment.city_state import UrbanAsset

    city, trigger, condition = aggrieved
    original = city.city_state.assets[0]
    # A second, healthier asset serving the same capability.
    sibling = UrbanAsset(
        "second_clinic", original.district_id, original.capability_ids,
        original.capacity, original.quality, 0.9,
    )
    city.city_state = replace(
        city.city_state, assets=(original, sibling)
    )
    institution_id = _dynasty_institution_id(base_world)
    sibling_before = sibling.integrity

    produced = await _government_repairs(base_world, city, trigger, condition)
    repair = next(e for e in produced if e.event_type == MAINTENANCE_COMPLETED)

    # The owner repairs the worst asset; the memory names that one only.
    assert repair.render_params["asset_id"] == original.id
    memory = next(
        m for m in _memories(base_world, institution_id) if m.event_id == repair.id
    )
    assert dict(memory.factors)["relative_scale"] > 0.0
    # The sibling was not touched, and nothing records it as repaired.
    current = {item.id: item for item in city.city_state.assets}
    assert current[sibling.id].integrity == pytest.approx(sibling_before)
    assert current[original.id].integrity > original.integrity


# --------------------------------------------------------------------------
# Only a real completion remembers
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_blocked_attempt_remembers_nothing(base_world, aggrieved):  # noqa: F811
    """No improvement, no memory -- and the blocked fact still exists."""
    from dataclasses import replace

    from src.classes.environment.city_state import CityGovernance

    city, trigger, condition = aggrieved
    institution_id = _dynasty_institution_id(base_world)
    # Administrative capacity is gone, so the owner refuses the work.
    city.city_state = replace(
        city.city_state,
        governance=CityGovernance(
            city.city_state.governance.controller_kind,
            city.city_state.governance.controller_id,
            0.0,
        ),
    )

    produced = await _government_repairs(base_world, city, trigger, condition)

    assert not [e for e in produced if e.event_type == MAINTENANCE_COMPLETED]
    assert _memories(base_world, institution_id) == ()


@pytest.mark.asyncio
async def test_an_unauthorized_actor_writes_no_memory(base_world, aggrieved):  # noqa: F811
    """Fail-closed: the fact stands and nobody remembers it."""
    from src.systems.city_maintenance import execute_urban_maintenance
    from src.systems.collective_affordances import _remember_completed_maintenance
    from src.systems.government_interpreter import government_affordance_context

    city, trigger, condition = aggrieved
    institution_id = _dynasty_institution_id(base_world)
    context, _region, _dynasty = government_affordance_context(
        base_world, trigger, condition
    )
    event = execute_urban_maintenance(
        base_world, city,
        capability_id="healing",
        decision_event_id="decision",
        trigger_event_id=trigger.id,
    )
    assert event.event_type == MAINTENANCE_COMPLETED
    # The office loses its holder, so authority is correctly refused.
    holder = base_world.avatar_manager.get_avatar(
        str(base_world.dynasty.current_emperor_id)
    )
    assert holder is not None
    holder.is_dead = True

    _remember_completed_maintenance(context, city, event)

    assert _memories(base_world, institution_id) == ()
    assert not base_world.institutional_knowledge.contains(institution_id, event.id)


@pytest.mark.asyncio
async def test_a_holder_lost_before_execution_blocks_the_repair_itself(
    base_world, aggrieved  # noqa: F811
):
    """Authority is refused *before* the owner runs, not after.

    Composed with a real decision, then the office loses its holder, then the
    registry is asked to execute: it must refuse, and nothing may move -- not
    the asset, not knowledge, not memory. A memory gate alone would have let
    the city be repaired by a government nobody can speak for.
    """
    from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
    from src.systems.domain_affordance_registry import (
        DOMAIN_AFFORDANCES,
        StaleAffordanceError,
    )
    from src.systems.government_interpreter import (
        government_affordance_context,
        interpret_government_transition,
    )

    city, trigger, condition = aggrieved
    institution_id = _dynasty_institution_id(base_world)
    context, _region, _dynasty = government_affordance_context(
        base_world, trigger, condition
    )
    offered = DOMAIN_AFFORDANCES.compose(context)
    maintenance = next(o for o in offered if o.action_kind == "urban_maintenance")
    # The decision really chooses *this* repair, so a stale refusal below
    # cannot pass by way of some unrelated maintain.
    decision, decision_event = await interpret_government_transition(
        base_world, trigger, condition,
        injected_decision=DomainDecision(
            DomainDecisionKind.ACT, "Repair the clinic.", maintenance.id
        ),
    )
    assert decision.selected_affordance_id == maintenance.id
    assert decision_event is not None
    integrity_before = city.city_state.assets[0].integrity

    holder = base_world.avatar_manager.get_avatar(
        str(base_world.dynasty.current_emperor_id)
    )
    assert holder is not None
    holder.is_dead = True

    # The menu is empty now, so the very same option is no longer offered.
    assert DOMAIN_AFFORDANCES.compose(context) == ()
    with pytest.raises(StaleAffordanceError):
        DOMAIN_AFFORDANCES.execute(
            context, maintenance.id,
            decision_event_id=decision_event.id, decision_event=decision_event,
        )

    assert city.city_state.assets[0].integrity == pytest.approx(integrity_before)
    assert _memories(base_world, institution_id) == ()
    assert base_world.institutional_knowledge.known_facts == {}


@pytest.mark.asyncio
async def test_incoherent_evidence_writes_no_memory(base_world, aggrieved):  # noqa: F811
    """A magnitude no transition supports is not remembered."""
    from src.systems.city_maintenance import execute_urban_maintenance
    from src.systems.collective_affordances import _remember_completed_maintenance
    from src.systems.government_interpreter import government_affordance_context

    city, trigger, condition = aggrieved
    institution_id = _dynasty_institution_id(base_world)
    context, _region, _dynasty = government_affordance_context(
        base_world, trigger, condition
    )
    event = execute_urban_maintenance(
        base_world, city,
        capability_id="healing",
        decision_event_id="decision",
        trigger_event_id=trigger.id,
    )
    event.causal_payload["improvement"] = 0.5

    with pytest.raises(ValueError):
        _remember_completed_maintenance(context, city, event)
    assert _memories(base_world, institution_id) == ()


# --------------------------------------------------------------------------
# Damage and repair, both remembered
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_damage_and_repair_are_both_in_a_later_prompt(
    base_world, rioting  # noqa: F811
):
    """The whole point: a later decision sees what happened and what was done.

    A real riot, then the government independently selecting a valid repair,
    then both facts reaching the real interpreter boundary rendered through the
    real template on a later trigger.
    """
    from src.utils.llm.prompt import build_prompt, load_template
    from src.systems.government_interpreter import interpret_government_transition

    city, trigger, condition = rioting
    base_world.event_manager.add_event(trigger)
    institution_id = _dynasty_institution_id(base_world)

    _o, population_decision, riot = await _riot(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(population_decision)
    base_world.event_manager.add_event(riot)

    produced = await _government_repairs(base_world, city, trigger, condition)
    repair = next(
        (e for e in produced if e.event_type == MAINTENANCE_COMPLETED), None
    )
    assert repair is not None, "the government completed no repair"
    for event in produced:
        base_world.event_manager.add_event(event)

    remembered = {m.event_id for m in _memories(base_world, institution_id)}
    assert {riot.id, repair.id} <= remembered

    # Both reach the boundary on a later trigger, in the rendered text.
    captured: list[dict] = []

    async def boundary(task_name, template, infos, *, output_schema=None):
        captured.append({"template": template, "infos": infos})
        ids = list(output_schema["properties"]["selected_affordance_id"]["enum"])
        return (
            {"decision": "act", "reason": "Keep working.",
             "selected_affordance_id": ids[0]}
            if ids
            else {"decision": "maintain", "reason": "Nothing to do."}
        )

    base_world.run_config_snapshot = {}
    await interpret_government_transition(
        base_world, trigger, condition, llm_call=boundary
    )
    assert captured
    prompt = build_prompt(load_template(captured[0]["template"]), captured[0]["infos"])
    assert riot.id in prompt
    assert repair.id in prompt
    assert str(riot_payload(riot)["asset_id"]) in prompt
    assert str(repair.render_params["improvement"])[:6] in prompt


@pytest.mark.asyncio
async def test_a_repair_reinforces_no_older_riot_memory(
    base_world, rioting  # noqa: F811
):
    """Same city is not causal evidence, and no memory is erased."""
    city, trigger, condition = rioting
    institution_id = _dynasty_institution_id(base_world)
    _o, _d, riot = await _riot(base_world, city, trigger, condition)
    riot_memory = next(
        m for m in _memories(base_world, institution_id) if m.event_id == riot.id
    )
    before = (riot_memory.salience, riot_memory.last_reinforced_month)

    produced = await _government_repairs(base_world, city, trigger, condition)
    assert [e for e in produced if e.event_type == MAINTENANCE_COMPLETED]

    after = next(
        m for m in _memories(base_world, institution_id) if m.event_id == riot.id
    )
    assert (after.salience, after.last_reinforced_month) == before
    # And it is still there: nothing was erased by the repair.
    assert after.event_id == riot.id


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_month_rollback_releases_the_repair_memory(
    base_world, aggrieved  # noqa: F811
):
    from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint

    city, trigger, condition = aggrieved
    institution_id = _dynasty_institution_id(base_world)

    checkpoint = SimulationMonthCheckpoint.capture(base_world)
    produced = await _government_repairs(base_world, city, trigger, condition)
    assert [e for e in produced if e.event_type == MAINTENANCE_COMPLETED]
    assert _memories(base_world, institution_id) != ()

    checkpoint.restore()

    assert _memories(base_world, institution_id) == ()
    assert base_world.institutional_relations.memories == {}


@pytest.mark.asyncio
async def test_a_real_save_load_roundtrip_keeps_both_memories(
    base_world, aggrieved, tmp_path  # noqa: F811
):
    """Damage and repair both survive the project's own save/load."""
    from unittest.mock import patch

    from src.sim.load.load_game import load_game
    from src.sim.save.save_game import save_game
    from src.sim.simulator import Simulator
    from src.systems.institutional_memory import decision_context

    city, trigger, condition = aggrieved
    _riotable_city(city, profile=PROFILE)
    base_world.event_manager.add_event(trigger)
    institution_id = _dynasty_institution_id(base_world)

    _o, population_decision, riot = await _riot(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(population_decision)
    base_world.event_manager.add_event(riot)
    produced = await _government_repairs(base_world, city, trigger, condition)
    repair = next(e for e in produced if e.event_type == MAINTENANCE_COMPLETED)
    for event in produced:
        base_world.event_manager.add_event(event)

    expected = {
        m.event_id: dict(m.factors)
        for m in _memories(base_world, institution_id)
    }
    assert {riot.id, repair.id} <= set(expected)
    original_map = base_world.map

    save_path = tmp_path / "maintenance_memory.json"
    success, _message = save_game(
        base_world, Simulator(base_world), [], save_path
    )
    assert success
    base_world.event_manager.close()

    with patch(
        "src.run.load_map.load_cultivation_world_map", return_value=original_map
    ):
        loaded, _simulator, _sects = load_game(save_path)

    restored = {
        m.event_id: dict(m.factors) for m in _memories(loaded, institution_id)
    }
    assert restored == expected
    for event_id in (riot.id, repair.id):
        assert loaded.institutional_knowledge.contains(institution_id, event_id)
    projected = {
        fact["event_id"]
        for fact in decision_context(loaded, institution_id)["known_facts"]
    }
    assert {riot.id, repair.id} <= projected


@pytest.mark.asyncio
async def test_no_other_institution_learns_the_repair(base_world, aggrieved):  # noqa: F811
    """Only the institution that acted knows and remembers."""
    city, trigger, condition = aggrieved
    institution_id = _dynasty_institution_id(base_world)
    produced = await _government_repairs(base_world, city, trigger, condition)
    repair = next(e for e in produced if e.event_type == MAINTENANCE_COMPLETED)

    for other in base_world.institutional_authority.institutions.values():
        if other.id == institution_id:
            continue
        assert _memories(base_world, other.id) == ()
        assert not base_world.institutional_knowledge.contains(other.id, repair.id)

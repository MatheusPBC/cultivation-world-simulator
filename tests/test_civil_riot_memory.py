"""Real urban damage becomes institutional memory; speech does not.

A riot is the one civil fact that materially damaged something, so it is the
one that leaves a memory. `decision_context` projects memories rather than raw
known facts, so without this the damage vanished from every later
institutional decision the moment the response receipt closed.

Nothing here mutates anything: the integrity loss already happened in
`city_damage.execute_crowd_damage`, and this only reads the transition that
owner recorded. No hostility, no relationship change, no options or urgency
change, and no memory at all for petitions, stoppages or endorsements.
"""

from __future__ import annotations

import pytest

from src.classes.institution import KnowledgeChannel
from src.systems.civil_riot import MAX_RIOT_DAMAGE, riot_payload
from tests.test_civil_riot import (  # reuse the riot fixtures
    PROFILE,
    _riot,
    _riot_option,
    _riotable_city,
    rioting,  # noqa: F401
)
from tests.test_civil_petition import (
    _context,
    _decision_event,
    aggrieved,  # noqa: F401
)


def _memories(world, institution_id: str):
    return world.institutional_relations.memories_for(institution_id)


def _institution_id(event) -> str:
    return str(riot_payload(event)["addressed_institution_id"])


# --------------------------------------------------------------------------
# The memory itself
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_riot_leaves_one_memory_scaled_by_the_real_loss(
    base_world, rioting  # noqa: F811
):
    """`relative_scale` is the observed integrity loss, not a capped ratio."""
    city, trigger, condition = rioting
    before = city.city_state.assets[0].integrity

    _option, _decision, event = await _riot(base_world, city, trigger, condition)

    institution_id = _institution_id(event)
    memories = _memories(base_world, institution_id)
    assert len(memories) == 1
    memory = memories[0]
    assert memory.event_id == event.id

    observed = before - city.city_state.assets[0].integrity
    factors = dict(memory.factors)
    assert factors["relative_scale"] == pytest.approx(observed)
    # The loss itself, on the city's own 0..1 integrity scale. An execution cap
    # is a limit on one riot, not a scale for how large the loss was, so
    # dividing by it would amplify a small loss into a large memory.
    assert factors["relative_scale"] == pytest.approx(
        float(event.causal_payload["deltas"][0]["magnitude"])
    )
    assert factors["relative_scale"] != pytest.approx(observed / MAX_RIOT_DAMAGE)
    assert 0.0 < factors["relative_scale"] <= 1.0
    # The other three are frozen: nothing supports them.
    assert factors["institutional_change"] == 0.0
    assert factors["commitment_breach"] == 0.0
    assert factors["identity_anchor_impact"] == 0.0

    # Knowledge is unchanged in kind: a broken building is a public fact.
    fact = base_world.institutional_knowledge.get_fact(institution_id, event.id)
    assert fact is not None and fact.channel is KnowledgeChannel.PUBLIC_FACT
    # And no relationship or hostility was touched.
    assert base_world.institutional_relations.relations == {}


@pytest.mark.asyncio
async def test_the_delta_and_the_memory_state_the_same_loss(
    base_world, rioting  # noqa: F811
):
    """The memory reads the owner's transition; it never restates it."""
    city, trigger, condition = rioting
    _o, _d, event = await _riot(base_world, city, trigger, condition)

    delta = event.causal_payload["deltas"][0]
    assert delta["aspect"] == "urban_asset_integrity"
    assert delta["owner_kind"] == "region"
    assert str(delta["owner_id"]) == str(city.id)
    assert str(delta["event_id"]) == str(event.id)
    endpoints = float(delta["before"]) - float(delta["after"])
    memory = _memories(base_world, _institution_id(event))[0]
    assert dict(memory.factors)["relative_scale"] == pytest.approx(endpoints)
    assert float(riot_payload(event)["damage"]) == pytest.approx(endpoints)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "corrupt",
    (
        pytest.param(lambda payload, deltas: deltas.clear(), id="no-delta"),
        pytest.param(
            lambda payload, deltas: deltas.append(dict(deltas[0])), id="two-deltas"
        ),
        pytest.param(
            lambda payload, deltas: deltas[0].update({"after": deltas[0]["before"]}),
            id="zero-loss",
        ),
        pytest.param(
            lambda payload, deltas: deltas[0].update({"magnitude": 0.5}),
            id="magnitude-disagrees",
        ),
        pytest.param(
            lambda payload, deltas: payload.update({"damage": 0.5}),
            id="payload-disagrees",
        ),
        pytest.param(
            lambda payload, deltas: deltas[0].update({"magnitude": float("nan")}),
            id="nan-magnitude",
        ),
        pytest.param(
            lambda payload, deltas: deltas[0].update({"before": "1.5"}),
            id="endpoint-out-of-range",
        ),
        pytest.param(
            lambda payload, deltas: deltas[0].update({"owner_kind": "sect"}),
            id="wrong-owner",
        ),
    ),
)
async def test_incoherent_evidence_writes_no_memory(
    base_world, rioting, corrupt  # noqa: F811
):
    """No memory is better than a magnitude no transition supports."""
    from src.systems.civil_riot import record_riot_aftermath

    city, trigger, condition = rioting
    option = _riot_option(base_world, city, trigger, condition)
    decision = await _decision_event(base_world, city, option, trigger)
    from src.systems.city_damage import execute_crowd_damage

    event = execute_crowd_damage(
        _context(base_world, trigger, condition, city), option,
        decision_event_id=decision.id, decision_event=decision,
    )
    institution_id = _institution_id(event)
    # A world where the aftermath has not run yet.
    base_world.institutional_relations.memories.clear()

    corrupt(
        event.causal_payload["civil_riot"], event.causal_payload["deltas"]
    )

    with pytest.raises(ValueError):
        record_riot_aftermath(
            base_world,
            region=city,
            condition=condition,
            event=event,
            decision_event_id=decision.id,
            affordance_id=option.id,
        )
    assert _memories(base_world, institution_id) == ()


@pytest.mark.asyncio
async def test_a_foreign_delta_entry_is_filtered_not_fatal(
    base_world, rioting  # noqa: F811
):
    """The evidence read is a filter, not a second validator of the owner.

    An unrelated entry alongside the real one is skipped; the one canonical
    integrity delta still decides the scale.
    """
    from src.systems.city_damage import execute_crowd_damage
    from src.systems.civil_riot import record_riot_aftermath

    city, trigger, condition = rioting
    option = _riot_option(base_world, city, trigger, condition)
    decision = await _decision_event(base_world, city, option, trigger)
    event = execute_crowd_damage(
        _context(base_world, trigger, condition, city), option,
        decision_event_id=decision.id, decision_event=decision,
    )
    base_world.institutional_relations.memories.clear()
    real = dict(event.causal_payload["deltas"][0])
    event.causal_payload["deltas"].insert(0, "not-a-mapping")

    record_riot_aftermath(
        base_world, region=city, condition=condition, event=event,
        decision_event_id=decision.id, affordance_id=option.id,
    )

    memory = _memories(base_world, _institution_id(event))[0]
    assert dict(memory.factors)["relative_scale"] == pytest.approx(
        float(real["before"]) - float(real["after"])
    )


# --------------------------------------------------------------------------
# Only damage remembers
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_speech_and_interruption_leave_no_memory(base_world, aggrieved):  # noqa: F811
    """A petition, a stoppage and an endorsement are not material damage."""
    from src.classes.action_runtime import ActionOrigin
    from src.systems.civil_petition import petition_payload
    from tests.test_civic_endorsement import (
        _commit_choice,
        _resident,
    )
    from tests.test_civil_petition import _file_petition

    city, trigger, condition = aggrieved
    _o, decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(trigger)
    base_world.event_manager.add_event(decision)
    base_world.event_manager.add_event(petition)
    institution_id = str(
        petition_payload(petition)["addressed_institution_id"]
    )
    assert base_world.institutional_knowledge.contains(institution_id, petition.id)
    assert _memories(base_world, institution_id) == ()

    from src.systems.civic_endorsement import record_public_endorsement

    avatar = _resident(base_world, city)
    _commit_choice(base_world, avatar, petition)
    endorsement = record_public_endorsement(
        base_world, avatar, str(petition.id),
        action_origin=ActionOrigin.ACTOR_CHOICE,
    )
    assert endorsement is not None
    # Known, and deliberately unremembered: speech has no material magnitude.
    assert base_world.institutional_knowledge.contains(
        institution_id, endorsement.id
    )
    assert _memories(base_world, institution_id) == ()


@pytest.mark.asyncio
async def test_no_memory_reaches_another_institution(
    base_world, rioting  # noqa: F811
):
    """Isolation: the memory belongs to the institution that administers here."""
    city, trigger, condition = rioting
    _o, _d, event = await _riot(base_world, city, trigger, condition)
    institution_id = _institution_id(event)

    for other in base_world.institutional_authority.institutions.values():
        if other.id == institution_id:
            continue
        assert _memories(base_world, other.id) == ()
        assert not base_world.institutional_knowledge.contains(other.id, event.id)


# --------------------------------------------------------------------------
# It reaches a later decision, and it decays
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_damage_is_in_a_later_government_context(
    base_world, rioting  # noqa: F811
):
    """After the response receipt closes, the damage is still remembered.

    This is the whole point of the slice: the government's own decision
    context carries the known damage on a later, unrelated trigger, and the
    riot's own trigger is not what put it there.
    """
    city, trigger, condition = rioting
    base_world.event_manager.add_event(trigger)
    _o, population_decision, riot = await _riot(
        base_world, city, trigger, condition
    )
    # The whole chain is persisted, as the finalizer does: the riot cites the
    # population's decision, and the response receipt will cite the
    # government's, so leaving either out would leave a broken cause.
    base_world.event_manager.add_event(population_decision)
    base_world.event_manager.add_event(riot)
    institution_id = _institution_id(riot)

    # The riot is answered and its receipt closes.
    from src.sim.simulator_engine.causal_budget import CausalBudget
    from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
    from src.systems.civil_riot import riot_already_answered
    from src.systems.government_reactivity import (
        enqueue_pending_riots,
        process_government_reactivity,
    )

    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )
    invalidations = DomainInvalidationQueue()
    enqueue_pending_riots(base_world, invalidations)
    answered = await process_government_reactivity(
        base_world, current_events=[], invalidations=invalidations,
        budget=CausalBudget.from_world(base_world),
    )
    for produced in answered:
        base_world.event_manager.add_event(produced)
    assert riot_already_answered(base_world, riot.id, institution_id)

    # A later, unrelated government decision still sees the damage.
    from src.systems.institutional_memory import decision_context

    context = decision_context(base_world, institution_id)
    remembered = [
        fact for fact in context["known_facts"] if fact["event_id"] == riot.id
    ]
    assert remembered, "the answered riot vanished from institutional memory"
    assert remembered[0]["salience"] > 0.0
    assert remembered[0]["event_type"] == riot.event_type

    # And it really reaches the boundary on a *different* later trigger: the
    # condition's own activation, not the riot's. Rendered through the real
    # template, so this proves the text a model would read.
    from src.utils.llm.prompt import build_prompt, load_template
    from src.systems.government_interpreter import interpret_government_transition

    captured: list[dict] = []

    async def boundary(task_name, template, infos, *, output_schema=None):
        captured.append({"template": template, "infos": infos})
        ids = list(output_schema["properties"]["selected_affordance_id"]["enum"])
        return (
            {"decision": "act", "reason": "Repair it.",
             "selected_affordance_id": ids[0]}
            if ids
            else {"decision": "maintain", "reason": "Nothing to do."}
        )

    base_world.run_config_snapshot = {}
    await interpret_government_transition(
        base_world, trigger, condition, llm_call=boundary
    )
    assert captured, "the later decision never reached the boundary"
    assert captured[0]["infos"]["trigger"]["event_id"] == trigger.id
    prompt = build_prompt(load_template(captured[0]["template"]), captured[0]["infos"])
    assert riot.id in prompt
    payload = riot_payload(riot)
    assert str(payload["asset_id"]) in prompt
    assert str(payload["damage"])[:6] in prompt


@pytest.mark.asyncio
async def test_the_memory_decays_with_time(base_world, rioting):  # noqa: F811
    """Existing decay, applied to a fact that finally has a memory."""
    from src.systems.institutional_memory import effective_salience

    city, trigger, condition = rioting
    _o, _d, event = await _riot(base_world, city, trigger, condition)
    memory = _memories(base_world, _institution_id(event))[0]

    now = int(base_world.month_stamp)
    fresh = effective_salience(memory, now)
    later = effective_salience(memory, now + 120)
    assert 0.0 < later < fresh


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_month_rollback_releases_the_memory(base_world, rioting):  # noqa: F811
    """The memory is month state like the damage is."""
    from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint

    city, trigger, condition = rioting
    option = _riot_option(base_world, city, trigger, condition)
    decision = await _decision_event(base_world, city, option, trigger)

    checkpoint = SimulationMonthCheckpoint.capture(base_world)
    from src.systems.domain_affordance_registry import DOMAIN_AFFORDANCES

    event = DOMAIN_AFFORDANCES.execute(
        _context(base_world, trigger, condition, city), option.id,
        decision_event_id=decision.id, decision_event=decision,
    )
    institution_id = _institution_id(event)
    assert len(_memories(base_world, institution_id)) == 1

    checkpoint.restore()

    assert _memories(base_world, institution_id) == ()
    assert base_world.institutional_relations.memories == {}


@pytest.mark.asyncio
async def test_a_real_save_load_roundtrip_keeps_the_memory(base_world, aggrieved, tmp_path):  # noqa: F811
    """Through the project's own save/load, on the real SQLite store."""
    from unittest.mock import patch

    from src.sim.load.load_game import load_game
    from src.sim.save.save_game import save_game
    from src.sim.simulator import Simulator

    city, trigger, condition = aggrieved
    _riotable_city(city, profile=PROFILE)
    base_world.event_manager.add_event(trigger)
    _o, population_decision, event = await _riot(
        base_world, city, trigger, condition
    )
    # The whole chain is persisted, as the finalizer does: a memory whose
    # event cites a cause the store never received would be a broken cause.
    base_world.event_manager.add_event(population_decision)
    base_world.event_manager.add_event(event)
    institution_id = _institution_id(event)
    expected = dict(_memories(base_world, institution_id)[0].factors)
    original_map = base_world.map

    save_path = tmp_path / "riot_memory.json"
    success, _message = save_game(
        base_world, Simulator(base_world), [], save_path
    )
    assert success
    base_world.event_manager.close()

    with patch(
        "src.run.load_map.load_cultivation_world_map", return_value=original_map
    ):
        loaded, _simulator, _sects = load_game(save_path)

    restored = _memories(loaded, institution_id)
    assert len(restored) == 1
    assert dict(restored[0].factors) == expected
    assert restored[0].event_id == event.id
    assert loaded.institutional_knowledge.contains(institution_id, event.id)
    # And it is still projected into a decision context after the reload.
    from src.systems.institutional_memory import decision_context

    context = decision_context(loaded, institution_id)
    assert [
        fact for fact in context["known_facts"] if fact["event_id"] == event.id
    ]


@pytest.mark.asyncio
async def test_the_memory_outlives_a_change_of_holder(base_world, rioting):  # noqa: F811
    """Offices change hands; what the institution remembers does not."""
    from src.systems.institution_bootstrap import synchronize_institutional_authority
    from src.systems.institutional_memory import decision_context
    from tests.test_civil_petition import _emperor

    from src.classes.institution import AuthorityScope

    city, trigger, condition = rioting
    base_world.event_manager.add_event(trigger)
    _o, population_decision, event = await _riot(
        base_world, city, trigger, condition
    )
    # Stored, as the finalizer does: `decision_context` resolves the event a
    # memory names, and cannot project a fact it has no event for.
    base_world.event_manager.add_event(population_decision)
    base_world.event_manager.add_event(event)
    institution_id = _institution_id(event)
    before = dict(_memories(base_world, institution_id)[0].factors)
    holder_before = decision_context(
        base_world, institution_id, authority_scope=AuthorityScope.URBAN_ADMINISTRATION
    )["authorized_holder"]
    assert holder_before is not None

    old_id = str(base_world.dynasty.current_emperor_id)
    base_world.avatar_manager.get_avatar(old_id).is_dead = True
    successor = _emperor(base_world)
    successor.name = "Successor"
    base_world.dynasty.current_emperor_id = successor.id
    synchronize_institutional_authority(base_world)

    after = dict(_memories(base_world, institution_id)[0].factors)
    assert after == before
    context = decision_context(
        base_world, institution_id, authority_scope=AuthorityScope.URBAN_ADMINISTRATION
    )
    # The office really changed hands, and the institution still remembers.
    holder_after = context["authorized_holder"]
    assert holder_after is not None
    assert holder_after["holder_ref"]["id"] != holder_before["holder_ref"]["id"]
    assert holder_after["holder_ref"]["id"] == str(successor.id)
    assert [
        fact for fact in context["known_facts"] if fact["event_id"] == event.id
    ]

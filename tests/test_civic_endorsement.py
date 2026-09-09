"""One named person publicly endorsing their city's own petition.

Individual support, not leadership. No followers are counted, no organization
is formed, no authority is granted, and no new durable state exists: the fact
itself is the record, and the government answers it on its own decision.
"""

from __future__ import annotations

import pytest

from src.classes.action_runtime import ActionOrigin
from src.classes.causal_link import CausalRelation
from src.classes.environment.city_state import CityGovernance
from src.classes.event import FactKind
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.civic_endorsement import (
    ENDORSEMENT_EVENT_TYPE,
    ENDORSEMENT_WINDOW_MONTHS,
    already_endorsed,
    can_endorse_public_petition,
    endorsable_petitions,
    endorsement_already_answered,
    endorsement_fact_context,
    endorsement_payload,
    get_endorse_petition_blocker,
    record_public_endorsement,
)
from tests.test_civil_petition import (  # reuse the civil fixtures
    _Ctx,
    _Sim,
    _emperor,
    _file_petition,
    aggrieved,  # noqa: F401
)


def _resident(world, city, *, name="Resident"):
    """A living, registered avatar standing in this very city."""
    avatar = _emperor(world)  # the same real Avatar builder the fixtures use
    avatar.name = name
    avatar.tile.region = city
    return avatar


def _resident_on_map(world, city, *, name="Resident"):
    """A living, registered avatar standing on a tile the city owns."""
    avatar = _emperor(world)
    avatar.name = name
    avatar.pos_x, avatar.pos_y = city.cors[0]
    avatar.tile = world.map.get_tile(avatar.pos_x, avatar.pos_y)
    assert avatar.tile is not None and avatar.tile.region is city
    return avatar


@pytest.fixture
def petitioned(base_world, aggrieved):  # noqa: F811
    """A real, persisted petition and a resident who could endorse it."""
    city, trigger, condition = aggrieved
    return city, trigger, condition


async def _persisted_petition(base_world, city, trigger, condition):
    _o, decision, petition = await _file_petition(
        base_world, city, trigger, condition
    )
    base_world.event_manager.add_event(trigger)
    base_world.event_manager.add_event(decision)
    base_world.event_manager.add_event(petition)
    return petition


def _endorse(base_world, avatar, petition, *, origin=ActionOrigin.ACTOR_CHOICE):
    return record_public_endorsement(
        base_world, avatar, str(petition.id), action_origin=origin
    )


def _commit_choice(base_world, avatar, petition):
    """Take the avatar's own audited decision, exactly as the engine does.

    Not a hand-shaped lookalike: the same builders the action driver uses, so
    what `attach_validated_actor_decision` validates is what really ships.
    """
    from src.systems.avatar_decision import (
        adopt_avatar_decision,
        build_avatar_decision_event,
    )

    pairs = [("EndorsePublicPetition", {"cause_event_id": str(petition.id)})]
    avatar.load_decide_result_chain(
        pairs, "The people are right.", "Endorse the petition.",
        origin=ActionOrigin.ACTOR_CHOICE,
    )
    decision = build_avatar_decision_event(
        base_world, avatar, pairs,
        "The people are right.", "Endorse the petition.",
        source="llm", offered={"EndorsePublicPetition": {}},
    )
    adopt_avatar_decision(avatar, decision)
    base_world.event_manager.add_event(decision)
    return decision.id


async def _run_committed_action(avatar) -> list:
    """Drive the real action driver, not the owner directly."""
    assert avatar.commit_next_plan() is not None
    return await avatar.tick_action()


# --------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_present_resident_can_endorse_a_live_local_petition(
    base_world, petitioned
):
    """The baseline: an enumerated, executable option really exists."""
    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)

    assert get_endorse_petition_blocker(base_world, avatar, str(petition.id)) is None
    assert can_endorse_public_petition(base_world, avatar)
    offered = endorsable_petitions(base_world, avatar)
    assert [event.id for event in offered] == [petition.id]


@pytest.mark.asyncio
async def test_every_enumerated_option_is_a_value_the_boundary_accepts(
    base_world, petitioned
):
    """The param options and the executor agree, by construction."""
    from src.classes.action.endorse_public_petition import EndorsePublicPetition
    from src.classes.action.param_options import build_param_options

    city, trigger, condition = petitioned
    await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)

    options = build_param_options(EndorsePublicPetition, avatar).get(
        "cause_event_id", []
    )
    assert options, "no enumerated option was offered"
    for option in options:
        assert get_endorse_petition_blocker(
            base_world, avatar, str(option["value"])
        ) is None
    # And the action really appears for this avatar, once.
    from src.classes.actions import get_action_infos

    infos = get_action_infos(avatar)
    assert "EndorsePublicPetition" in infos


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate,expected",
    (
        (lambda w, a, c, p: setattr(a, "is_dead", True), "departed"),
        (
            lambda w, a, c, p: setattr(a.tile, "region", None),
            "in that city",
        ),
        (lambda w, a, c, p: w.avatar_manager.avatars.pop(str(a.id)), "world knows"),
        (
            lambda w, a, c, p: setattr(
                w, "month_stamp",
                type(w.month_stamp)(int(w.month_stamp) + ENDORSEMENT_WINDOW_MONTHS),
            ),
            "public notice",
        ),
        (
            lambda w, a, c, p: setattr(
                c.city_state, "governance", CityGovernance("dynasty", "2", 1.0)
            ),
            "standing institution",
        ),
    ),
)
async def test_the_rule_refuses_what_it_should(
    base_world, petitioned, mutate, expected
):
    """Dead, absent, unknown, stale, and re-controlled all refuse."""
    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    assert get_endorse_petition_blocker(base_world, avatar, str(petition.id)) is None

    mutate(base_world, avatar, city, petition)

    blocker = get_endorse_petition_blocker(base_world, avatar, str(petition.id))
    assert blocker is not None and expected in blocker
    assert _endorse(base_world, avatar, petition) is None


@pytest.mark.asyncio
async def test_a_forged_petition_authorises_no_endorsement(base_world, petitioned):
    """A well-shaped payload is a claim, not a filing the people made."""
    from copy import deepcopy

    city, trigger, condition = petitioned
    real = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)

    forged = deepcopy(real)
    forged.id = "forged-petition"
    forged.causal_links = []
    base_world.event_manager.add_event(forged)

    # It looks exactly like a petition, evidence and all.
    assert endorsement_payload(forged) is None
    from src.systems.civil_petition import petition_payload

    assert petition_payload(forged) is not None
    blocker = get_endorse_petition_blocker(base_world, avatar, forged.id)
    assert blocker is not None and "never filed" in blocker
    # And it is never enumerated.
    assert forged.id not in {
        event.id for event in endorsable_petitions(base_world, avatar)
    }


@pytest.mark.asyncio
async def test_a_petition_from_another_city_is_not_endorsable(base_world, petitioned):
    """Presence is about this city, not about caring from a distance."""
    from src.classes.environment.region import CityRegion

    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    elsewhere = CityRegion(id=399, name="Far City", desc="", cors=[(9, 9)])
    base_world.map.regions[elsewhere.id] = elsewhere
    avatar = _resident(base_world, city)
    avatar.tile.region = elsewhere

    blocker = get_endorse_petition_blocker(base_world, avatar, str(petition.id))
    assert blocker is not None and "in that city" in blocker
    assert endorsable_petitions(base_world, avatar) == []


# --------------------------------------------------------------------------
# Authorship and the whole act
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_reactive_or_missing_origin_produces_no_fact(base_world, petitioned):
    """Only a deliberate choice endorses; no permissive default exists."""
    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    _commit_choice(base_world, avatar, petition)

    known_before = set(base_world.institutional_knowledge.known_facts)

    for origin in (None, ActionOrigin.REACTIVE_RESPONSE):
        assert _endorse(base_world, avatar, petition, origin=origin) is None
    assert not already_endorsed(base_world, str(avatar.id), str(petition.id))
    # No new notice was given: the petition's own knowledge is all there is.
    assert set(base_world.institutional_knowledge.known_facts) == known_before


@pytest.mark.asyncio
async def test_an_unchosen_endorsement_produces_no_fact(base_world, petitioned):
    """No audited decision naming this exact action and parameter, no fact."""
    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    # Deliberately no committed decision at all.

    assert _endorse(base_world, avatar, petition) is None
    assert not already_endorsed(base_world, str(avatar.id), str(petition.id))


@pytest.mark.asyncio
async def test_a_real_endorsement_is_authored_noticed_and_unrepeatable(
    base_world, petitioned
):
    """The whole act: one fact, formal notice, and no second time."""
    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    decision_id = _commit_choice(base_world, avatar, petition)

    event = _endorse(base_world, avatar, petition)

    assert event is not None
    assert event.event_type == ENDORSEMENT_EVENT_TYPE
    assert event.fact_kind is FactKind.OCCURRENCE
    payload = endorsement_payload(event)
    assert payload is not None
    assert payload["avatar_id"] == str(avatar.id)
    assert payload["petition_event_id"] == str(petition.id)
    assert payload["avatar_name"] == avatar.name
    assert str(avatar.id) in (event.related_avatars or [])
    # Answering the petition it endorses, and authored by the real decision.
    assert any(
        link.relation is CausalRelation.RESPONSE_TO
        and link.cause_event_id == petition.id
        for link in event.causal_links
    )
    assert event.causal_payload["decision_source"]["decision_event_id"] == decision_id

    # The addressed government was told, by formal notice.
    from src.classes.institution import KnowledgeChannel

    institution_id = payload["addressed_institution_id"]
    fact = base_world.institutional_knowledge.get_fact(institution_id, event.id)
    assert fact is not None and fact.channel is KnowledgeChannel.FORMAL_NOTICE

    # Not repeatable, even before the finalizer has persisted the fact.
    assert already_endorsed(base_world, str(avatar.id), str(petition.id))
    blocker = get_endorse_petition_blocker(base_world, avatar, str(petition.id))
    assert blocker is not None and "already endorsed" in blocker
    assert _endorse(base_world, avatar, petition) is None
    # Nothing was granted: no authority, no receipt of the avatar's own.
    assert base_world.institutional_authority.claims == {} or all(
        str(getattr(claim, "office_id", "")) != str(avatar.id)
        for claim in base_world.institutional_authority.claims.values()
    )


@pytest.mark.asyncio
async def test_the_real_action_driver_produces_the_endorsement(
    base_world, petitioned
):
    """Through `commit_next_plan` and `tick_action`, not the owner directly."""
    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    _commit_choice(base_world, avatar, petition)

    events = await _run_committed_action(avatar)

    produced = [e for e in events if e.event_type == ENDORSEMENT_EVENT_TYPE]
    assert produced, "the real action driver produced no endorsement"
    payload = endorsement_payload(produced[0])
    assert payload is not None and payload["avatar_id"] == str(avatar.id)
    assert already_endorsed(base_world, str(avatar.id), str(petition.id))


@pytest.mark.asyncio
async def test_another_resident_may_endorse_the_same_petition(base_world, petitioned):
    """Individual support: two people, two facts, and no count anywhere."""
    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    first = _resident(base_world, city, name="First")
    second = _resident(base_world, city, name="Second")
    _commit_choice(base_world, first, petition)
    _commit_choice(base_world, second, petition)

    one = _endorse(base_world, first, petition)
    two = _endorse(base_world, second, petition)

    assert one is not None and two is not None and one.id != two.id
    # No aggregate exists to grow: the city owns no endorsement state.
    assert not hasattr(city, "endorsements")
    assert not hasattr(city.city_state, "endorsements")


@pytest.mark.asyncio
async def test_the_persisted_fact_alone_prevents_a_repeat(base_world, petitioned):
    """Once stored, the store carries the dedup -- the buffer is not needed.

    This is the case a reloaded world is in: the transient buffer never
    survives a save, so if it were the only record, the same avatar could
    endorse the same petition again after a load.
    """
    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    _commit_choice(base_world, avatar, petition)

    event = _endorse(base_world, avatar, petition)
    assert event is not None
    # The finalizer stores the fact, as it does in production.
    base_world.event_manager.add_event(event)

    # A later step, or a reloaded process, starts with no buffer at all.
    delattr(base_world, "_civic_endorsement_events_this_step")
    assert not hasattr(base_world, "_civic_endorsement_events_this_step")

    assert already_endorsed(base_world, str(avatar.id), str(petition.id))
    blocker = get_endorse_petition_blocker(base_world, avatar, str(petition.id))
    assert blocker is not None and "already endorsed" in blocker
    assert _endorse(base_world, avatar, petition) is None
    # And it is no longer offered to that avatar.
    assert str(petition.id) not in {
        str(item.id) for item in endorsable_petitions(base_world, avatar)
    }
    # A different resident is still free to endorse it.
    other = _resident(base_world, city, name="Neighbour")
    assert get_endorse_petition_blocker(
        base_world, other, str(petition.id)
    ) is None


@pytest.mark.asyncio
async def test_after_a_real_load_a_different_resident_still_gets_the_option(
    tmp_path,
):
    """The regression for the windowed-scan provenance bug.

    `EventStorage._row_to_event` builds windowed events with **no** causal
    links -- only `get_event_by_id` hydrates them from the edge table -- so
    `prior_local_petition` used to read an empty link list after a real load
    and every petition silently failed its own provenance check. Nobody could
    endorse anything again after loading a save.

    Built on a canonical map city, not a synthetic fixture region, because a
    real save/load only reconstructs cities the map loader owns.
    """
    from src.sim.load.load_game import load_game
    from src.sim.save.save_game import save_game
    from src.sim.simulator import Simulator
    from src.systems.civil_petition import PETITION_ACTION, PETITION_EVENT_TYPE
    from tests.test_civil_petition import _inject_population_choice
    from tools.institutional_smoke import _world_factory

    world = _world_factory(pressured=True, commerce=False, seed=11)(0, 11)
    city = world.map.regions[302]
    # Stand them on a tile the city really owns, rather than reassigning some
    # other tile's region -- that would corrupt district coverage and the save
    # would refuse to load, which has nothing to do with what is under test.
    endorser = _resident_on_map(world, city, name="Endorser")
    neighbour = _resident_on_map(world, city, name="Neighbour")

    simulator = Simulator(world)
    captured = []
    with _inject_population_choice(PETITION_ACTION):
        for _ in range(12):
            captured.extend(await simulator.step())

    petitions = [
        event for event in captured
        if event.event_type == PETITION_EVENT_TYPE
        and str(
            (event.causal_payload or {}).get("civil_petition", {}).get("region_id")
        ) == str(city.id)
    ]
    assert petitions, "the run produced no petition in this city"
    petition = max(petitions, key=lambda item: int(item.month_stamp))
    assert get_endorse_petition_blocker(world, endorser, str(petition.id)) is None

    _commit_choice(world, endorser, petition)
    event = _endorse(world, endorser, petition)
    assert event is not None
    world.event_manager.add_event(event)

    save_path = tmp_path / "canonical.json"
    original_map = world.map
    success, _message = save_game(world, Simulator(world), [], save_path)
    assert success
    world.event_manager.close()

    from unittest.mock import patch

    # The scenario map is handed back to the loader, as the other roundtrip
    # test does: this is a test about event provenance surviving SQLite, not
    # about map reconstruction.
    with patch(
        "src.run.load_map.load_cultivation_world_map", return_value=original_map
    ):
        loaded, _simulator, _sects = load_game(save_path)

    # Provenance survives a windowed scan now, so the petition still validates.
    loaded_neighbour = loaded.avatar_manager.get_avatar(str(neighbour.id))
    loaded_endorser = loaded.avatar_manager.get_avatar(str(endorser.id))
    assert loaded_neighbour is not None and loaded_endorser is not None
    assert get_endorse_petition_blocker(
        loaded, loaded_neighbour, str(petition.id)
    ) is None
    assert str(petition.id) in {
        str(item.id) for item in endorsable_petitions(loaded, loaded_neighbour)
    }

    # And the one who already endorsed is refused for that reason, not for a
    # provenance failure.
    assert already_endorsed(loaded, str(endorser.id), str(petition.id))
    blocker = get_endorse_petition_blocker(
        loaded, loaded_endorser, str(petition.id)
    )
    assert blocker is not None and "already endorsed" in blocker


@pytest.mark.asyncio
async def test_a_store_read_failure_never_reads_as_never_endorsed(
    base_world, petitioned
):
    """"I could not read" is not "nobody endorsed": the error propagates."""
    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)

    def _explode(*_args, **_kwargs):
        raise RuntimeError("event store unavailable")

    original = base_world.event_manager.get_events_between_months
    base_world.event_manager.get_events_between_months = _explode
    try:
        with pytest.raises(RuntimeError):
            already_endorsed(base_world, str(avatar.id), str(petition.id))
    finally:
        base_world.event_manager.get_events_between_months = original


@pytest.mark.asyncio
async def test_the_step_buffer_is_transient_and_released_by_rollback(
    base_world, petitioned
):
    """The dedup memory is this step's only, never a second durable truth."""
    from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint

    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    _commit_choice(base_world, avatar, petition)

    institution_id = None
    checkpoint = SimulationMonthCheckpoint.capture(base_world)
    event = _endorse(base_world, avatar, petition)
    assert event is not None
    institution_id = endorsement_payload(event)["addressed_institution_id"]
    assert already_endorsed(base_world, str(avatar.id), str(petition.id))
    assert base_world.institutional_knowledge.contains(institution_id, event.id)

    checkpoint.restore()

    # The month never happened: the buffer and the notice went with it.
    assert not already_endorsed(base_world, str(avatar.id), str(petition.id))
    assert not base_world.institutional_knowledge.contains(institution_id, event.id)
    assert getattr(base_world, "_civic_endorsement_events_this_step", {}) in ({}, None)
    # The buffer only ever holds this month, so it cannot accumulate.
    assert ENDORSEMENT_WINDOW_MONTHS > 1


# --------------------------------------------------------------------------
# The government's independent answer
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_government_answers_a_known_endorsement_on_its_own_decision(
    base_world, petitioned
):
    """Its own trigger, because knowledge alone never reaches the context."""
    from src.systems.government_reactivity import (
        enqueue_pending_endorsements,
        process_government_reactivity,
    )

    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    _commit_choice(base_world, avatar, petition)
    endorsement = _endorse(base_world, avatar, petition)
    assert endorsement is not None
    base_world.event_manager.add_event(endorsement)
    institution_id = endorsement_payload(endorsement)["addressed_institution_id"]
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )

    # The context really carries the endorser and the current grievance.
    context = endorsement_fact_context(base_world, endorsement, city)
    assert context["civic_endorsement"]["endorser_name"] == avatar.name
    assert context["civic_endorsement"]["condition_still_active"] is True

    invalidations = DomainInvalidationQueue()
    enqueue_pending_endorsements(base_world, invalidations)
    produced = await process_government_reactivity(
        base_world, current_events=[], invalidations=invalidations,
        budget=CausalBudget.from_world(base_world),
    )

    answers = [
        event for event in produced
        if event.fact_kind is FactKind.DECISION
        and any(
            link.relation is CausalRelation.RESPONSE_TO
            and link.cause_event_id == endorsement.id
            for link in event.causal_links
        )
    ]
    assert answers, "the government never answered the endorsement it knew about"
    assert endorsement_already_answered(base_world, endorsement.id, institution_id)
    # Any material answer came through the existing repair menu, with a delta.
    for event in produced:
        if event.event_type in (
            "city_maintenance_completed", "urban_capacity_project_started"
        ):
            assert event.causal_payload["deltas"]


@pytest.mark.asyncio
async def test_answering_the_endorsement_does_not_reset_the_petition(
    base_world, petitioned
):
    """Separate receipts: a new endorsement is a new thing to answer."""
    from src.systems.civil_petition import already_responded
    from src.systems.government_reactivity import (
        enqueue_pending_endorsements,
        enqueue_pending_petitions,
        process_government_reactivity,
    )

    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    _commit_choice(base_world, avatar, petition)
    endorsement = _endorse(base_world, avatar, petition)
    base_world.event_manager.add_event(endorsement)
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )

    # The petition is answered first.
    first = DomainInvalidationQueue()
    enqueue_pending_petitions(base_world, first)
    await process_government_reactivity(
        base_world, current_events=[], invalidations=first,
        budget=CausalBudget.from_world(base_world),
    )
    assert already_responded(base_world, petition.id)
    institution_id = endorsement_payload(endorsement)["addressed_institution_id"]
    assert not endorsement_already_answered(
        base_world, endorsement.id, institution_id
    )

    # The endorsement still gets its own answer, and the petition stays closed.
    second = DomainInvalidationQueue()
    enqueue_pending_endorsements(base_world, second)
    produced = await process_government_reactivity(
        base_world, current_events=[], invalidations=second,
        budget=CausalBudget.from_world(base_world),
    )
    assert produced
    assert endorsement_already_answered(base_world, endorsement.id, institution_id)
    assert already_responded(base_world, petition.id)


@pytest.mark.asyncio
async def test_an_unknown_endorsement_is_never_answered(base_world, petitioned):
    """Knowledge gates the answer, as it does for every civil fact."""
    from src.systems.government_reactivity import (
        enqueue_pending_endorsements,
        process_government_reactivity,
    )

    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    _commit_choice(base_world, avatar, petition)
    endorsement = _endorse(base_world, avatar, petition)
    base_world.event_manager.add_event(endorsement)
    base_world.institutional_knowledge.known_facts.clear()
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )

    invalidations = DomainInvalidationQueue()
    enqueue_pending_endorsements(base_world, invalidations)
    produced = await process_government_reactivity(
        base_world, current_events=[], invalidations=invalidations,
        budget=CausalBudget.from_world(base_world),
    )
    assert not [
        event for event in produced
        if any(link.cause_event_id == endorsement.id for link in event.causal_links)
    ]


@pytest.mark.asyncio
async def test_an_unrecognised_endorsement_offers_the_registry_nothing(
    base_world, petitioned
):
    """A valid condition must not launder a fact canonical state never stored."""
    from copy import deepcopy

    from src.systems.collective_affordances import government_affordances
    from src.systems.government_interpreter import government_affordance_context

    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    _commit_choice(base_world, avatar, petition)
    endorsement = _endorse(base_world, avatar, petition)

    forged = deepcopy(endorsement)
    forged.id = "forged-endorsement"
    # Never stored, so no canonical reading exists for it.
    from src.systems.civic_endorsement import canonical_endorsement_payload

    assert canonical_endorsement_payload(base_world, forged) is None
    for supplied in (condition, None):
        context, _region, _dynasty = government_affordance_context(
            base_world, forged, supplied
        )
        assert government_affordances(context) == ()


# --------------------------------------------------------------------------
# Through the real phase hooks
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_real_government_phase_answers_a_persisted_endorsement(
    base_world, petitioned
):
    """`react_government` itself, with no new phase involved."""
    from src.sim.simulator_engine.phase_registry import react_government

    city, trigger, condition = petitioned
    petition = await _persisted_petition(base_world, city, trigger, condition)
    avatar = _resident(base_world, city)
    _commit_choice(base_world, avatar, petition)
    endorsement = _endorse(base_world, avatar, petition)
    base_world.event_manager.add_event(endorsement)
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 1
    )

    ctx = _Ctx(base_world)
    await react_government(_Sim(base_world), ctx)

    answers = [
        event for event in ctx.events
        if event.fact_kind is FactKind.DECISION
        and any(
            link.relation is CausalRelation.RESPONSE_TO
            and link.cause_event_id == endorsement.id
            for link in event.causal_links
        )
    ]
    assert answers, "react_government never answered the persisted endorsement"
    assert endorsement_already_answered(
        base_world,
        endorsement.id,
        endorsement_payload(endorsement)["addressed_institution_id"],
    )


# --------------------------------------------------------------------------
# A small real simulation
# --------------------------------------------------------------------------


ENDORSEMENT_SIM_MONTHS = 12


def _pressured_civil_choices():
    """Let the population really file petitions; the avatar side stays free.

    Only the collective civil choice is injected, so nothing forces any avatar
    to endorse and the engine's own conservative default is untouched.
    """
    from src.systems.civil_petition import PETITION_ACTION
    from tests.test_civil_petition import _inject_population_choice

    return _inject_population_choice(PETITION_ACTION)


@pytest.mark.asyncio
async def test_a_short_real_simulation_reaches_an_endorsable_petition():
    """Real `Simulator.step` months, no provider, no forced avatar choice.

    The engine must reach a state where a living resident is genuinely offered
    this action -- a real petition, still-live grievance, standing institution
    and the avatar present -- which is the part only a real run can show.
    Twelve months is this test's window, chosen because the canonical
    definitions need roughly seven months to activate a grievance.
    """
    from unittest.mock import AsyncMock, patch

    from src.classes.environment.region import CityRegion
    from src.sim.simulator import Simulator
    from tools.institutional_smoke import _world_factory

    world = _world_factory(pressured=True, commerce=False, seed=11)(0, 11)
    # The institutional smoke scenario carries a single living avatar and none
    # in a city, so it cannot by itself show a resident being offered this.
    # The fixture therefore guarantees the resident -- the same way the riot
    # fixture guarantees a target -- and the engine does the rest.
    resident = _resident(world, world.map.regions[302], name="Townsfolk")
    provider = AsyncMock(side_effect=AssertionError("no provider call allowed"))
    simulator = Simulator(world)
    captured = []
    with patch("src.utils.llm.client.call_llm_with_template", provider), \
            _pressured_civil_choices():
        for _ in range(ENDORSEMENT_SIM_MONTHS):
            captured.extend(await simulator.step())

    provider.assert_not_awaited()
    provider.assert_not_called()

    from src.systems.civil_petition import PETITION_EVENT_TYPE

    petitions = [e for e in captured if e.event_type == PETITION_EVENT_TYPE]
    assert petitions, "the pressured months produced no petition to endorse"

    # Someone alive, registered and standing in a petitioned city is really
    # offered the action by the engine's own enumeration.
    offered_to = [
        avatar
        for avatar in world.avatar_manager.get_living_avatars()
        if isinstance(
            getattr(getattr(avatar, "tile", None), "region", None), CityRegion
        )
        and endorsable_petitions(world, avatar)
    ]
    assert offered_to, "no living resident was ever offered an endorsement"
    assert resident in offered_to or any(
        str(a.id) == str(resident.id) for a in offered_to
    )

    # And every enumerated option is one the boundary would accept.
    for avatar in offered_to:
        for event in endorsable_petitions(world, avatar):
            assert get_endorse_petition_blocker(
                world, avatar, str(event.id)
            ) is None

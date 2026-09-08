"""Runtime witnesses for who actually authored a Dao rite sponsorship.

Sponsoring is not a fact the action may assert about itself.  These tests
drive the real commit/execute lifecycle, because that is the only place the
engine installs ``ActionOrigin.ACTOR_CHOICE`` on the committed action, and
they check both ends of the chain: the fact the boundary writes, and what the
audience path is willing to count later.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.classes.action import SponsorDaoRite
from src.classes.action.param_options import build_param_options
from src.classes.action_runtime import ActionOrigin
from src.classes.causal_link import CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.celestial_dao import DaoTradition
from src.classes.core.avatar.prompt_context import build_avatar_prompt_context
from src.classes.core.dynasty import Dynasty
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.institution import (
    AuthorityScope,
    IdentityAnchorKind,
    Institution,
    InstitutionalIdentityAnchor,
    InstitutionKind,
    KnowledgeChannel,
)
from src.classes.mechanical_language import EntityRef
from src.sim.managers.event_manager import EventManager
from src.systems.institution_bootstrap import (
    bootstrap_institutional_authority,
    synchronize_institutional_authority,
)
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.finalizer import validate_causal_integrity
from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint
from src.systems.avatar_decision import (
    adopt_avatar_decision,
    build_avatar_decision_event,
)
from src.systems.institutional_memory import record_known_fact, salience_for_factors
from src.systems.celestial_dao_service import (
    RITES_REQUIRED_FOR_AUDIENCE,
    RITE_WINDOW_MONTHS,
    _is_institutional_rite,
    _sponsorship_memory_factors,
    get_sponsor_dao_rite_blocker,
    get_sponsor_institution_memory,
    process_grounded_dao_rites,
    record_dao_rite_sponsorship,
)


def _emperor_in_region(base_world, dummy_avatar, region_id: int = 7) -> CityRegion:
    """A reigning emperor whose dynasty is a bootstrapped institution.

    The bootstrap is required, not incidental: sponsorship is authorized by
    `can_actor_act_for`, which has no permissive fallback, so a world with no
    authority state has nobody who can sponsor.
    """
    region = CityRegion(
        id=region_id,
        name="Rite City",
        desc="",
        cors=[(0, 0)],
        dao_tradition=DaoTradition.BALANCE,
    )
    base_world.map.regions[region_id] = region
    dummy_avatar.tile = SimpleNamespace(region=region)
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=dummy_avatar.id
    )
    bootstrap_institutional_authority(base_world)
    return region


def _plain_avatar(base_world, name: str):
    """A registered avatar who speaks for no institution."""
    from src.classes.age import Age
    from src.classes.alignment import Alignment
    from src.classes.core.avatar import Avatar, Gender
    from src.classes.root import Root
    from src.systems.cultivation import Realm
    from src.systems.time import Month, Year, create_month_stamp
    from src.utils.id_generator import get_avatar_id

    avatar = Avatar(
        world=base_world,
        name=name,
        id=get_avatar_id(),
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement, innate_max_lifespan=80),
        gender=Gender.MALE,
        pos_x=0,
        pos_y=0,
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )
    avatar.personas = []
    avatar.technique = None
    base_world.avatar_manager.register_avatar(avatar)
    return avatar


def _dynasty_institution_id(base_world) -> str:
    return Institution.id_for(
        InstitutionKind.DYNASTY, EntityRef("dynasty", str(base_world.dynasty.id))
    )


def _popular_rite(base_world, region: CityRegion, *, month: int | None = None) -> Event:
    event = Event(
        month if month is not None else base_world.month_stamp,
        "A popular rite",
        event_type="dao_rite",
        causal_payload={"dao_rite": {"is_popular": True, "region_id": region.id}},
    )
    base_world.event_manager.add_event(event)
    return event


def _advance(base_world, months: int) -> None:
    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + months
    )


def _decide_to_sponsor(base_world, avatar, cause_event_id: str) -> Event:
    """Take the avatar's own audited decision, exactly as the engine does."""
    pairs = [("SponsorDaoRite", {"cause_event_id": str(cause_event_id)})]
    avatar.load_decide_result_chain(
        pairs, "The rite deserves the court's voice.", "Sponsor the rite.",
        origin=ActionOrigin.ACTOR_CHOICE,
    )
    decision = build_avatar_decision_event(
        base_world,
        avatar,
        pairs,
        "The rite deserves the court's voice.",
        "Sponsor the rite.",
        source="llm",
        offered={"SponsorDaoRite": {}},
    )
    adopt_avatar_decision(avatar, decision)
    base_world.event_manager.add_event(decision)
    return decision


async def _run_committed_action(avatar) -> list[Event]:
    assert avatar.commit_next_plan() is not None
    return await avatar.tick_action()


def _sponsorship_of(events) -> Event:
    return next(
        event
        for event in events
        if (event.causal_payload or {}).get("dao_rite", {}).get("is_sponsorship")
    )


@pytest.mark.asyncio
async def test_committed_sponsorship_is_an_authored_occurrence_fact(
    base_world, dummy_avatar
):
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    decision = _decide_to_sponsor(base_world, dummy_avatar, rite.id)

    events = await _run_committed_action(dummy_avatar)

    sponsorship = _sponsorship_of(events)
    # The fact records that it happened and asserts no decision of its own.
    assert sponsorship.fact_kind is FactKind.OCCURRENCE
    assert "decision" not in sponsorship.causal_payload
    # It transitions no material owner: the only deltas are the ones
    # institutional knowledge and memory append for themselves.
    assert {
        delta["owner_kind"] for delta in sponsorship.causal_payload["deltas"]
    } == {"institutional_knowledge", "institutional_memory"}
    assert sponsorship.causal_payload["dao_rite"]["sponsor_institution_id"] == (
        _dynasty_institution_id(base_world)
    )
    # "court" stays a Dao label only; it is never an EntityRef kind.
    assert sponsorship.causal_payload["dao_rite"]["sponsor_kind"] == "court"
    assert sponsorship.causal_payload["decision_source"] == {
        "kind": "avatar_action",
        "action_name": "SponsorDaoRite",
        "avatar_id": str(dummy_avatar.id),
        "decision_event_id": decision.id,
    }
    assert {
        (link.cause_event_id, link.relation)
        for link in sponsorship.causal_links
    } == {
        (rite.id, CausalRelation.MOTIVATED_BY),
        (decision.id, CausalRelation.MOTIVATED_BY),
    }
    assert _is_institutional_rite(base_world, sponsorship, {decision.id: decision})
    # The same institution cannot sponsor the same rite twice.
    assert get_sponsor_dao_rite_blocker(base_world, dummy_avatar, rite.id) is not None


@pytest.mark.asyncio
async def test_sponsorship_in_month_zero_is_still_authored(base_world, dummy_avatar):
    """Month 0 is a real month, not a missing one."""
    base_world.month_stamp = type(base_world.month_stamp)(0)
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    decision = _decide_to_sponsor(base_world, dummy_avatar, rite.id)

    events = await _run_committed_action(dummy_avatar)

    sponsorship = _sponsorship_of(events)
    assert int(sponsorship.month_stamp) == 0
    assert _is_institutional_rite(base_world, sponsorship, {decision.id: decision})


@pytest.mark.asyncio
async def test_action_rebuilt_outside_the_commit_path_sponsors_nothing(
    base_world, dummy_avatar
):
    """An action that never passed the commit boundary proves no choice.

    This is the shape a loader produces -- the action object is reconstructed
    directly, so it keeps the class fallback origin -- but it is not a real
    save/load round trip, which this slice does not cover.
    """
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)
    dummy_avatar.clear_plans()

    rebuilt = SponsorDaoRite(dummy_avatar, base_world)
    assert rebuilt.action_origin == ActionOrigin.REACTIVE_RESPONSE

    # The rite is still perfectly sponsorable; only the authorship is missing,
    # so nothing at all is recorded rather than an unauthored sponsorship.
    assert get_sponsor_dao_rite_blocker(base_world, dummy_avatar, rite.id) is None
    assert await rebuilt.finish(rite.id) == []
    assert get_sponsor_dao_rite_blocker(base_world, dummy_avatar, rite.id) is None


@pytest.mark.asyncio
async def test_persisted_sponsorship_is_recognised_without_overlays_or_cache(
    base_world, dummy_avatar, tmp_path
):
    """A stored sponsorship must still prove itself from SQLite alone.

    The consumer deliberately reads only persisted fields, so this is the
    witness that the rule survives the round trip: no step overlays, no
    runtime dedup cache, and both facts re-read out of the event store.
    """
    base_world.event_manager = EventManager.create_with_db(tmp_path / "events.db")
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    decision = _decide_to_sponsor(base_world, dummy_avatar, rite.id)

    sponsorship = _sponsorship_of(await _run_committed_action(dummy_avatar))
    assert base_world.event_manager.add_event(sponsorship) is True

    # Drop everything this step held in memory.
    delattr(base_world, "_dao_sponsorship_events_this_step")
    stored = base_world.event_manager.get_event_by_id(sponsorship.id)
    assert stored is not None and stored is not sponsorship
    assert base_world.event_manager.get_event_by_id(decision.id) is not None

    assert _is_institutional_rite(base_world, stored, {})
    # And the canonical history alone still refuses a second sponsorship.
    assert get_sponsor_dao_rite_blocker(base_world, dummy_avatar, rite.id) is not None


@pytest.mark.asyncio
async def test_a_sponsored_rite_is_no_longer_offered_as_an_option(
    base_world, dummy_avatar
):
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)

    offered = build_param_options(SponsorDaoRite, dummy_avatar)["cause_event_id"]
    assert [option["value"] for option in offered] == [rite.id]

    await _run_committed_action(dummy_avatar)

    # With nothing left to sponsor the source contributes no key at all, and
    # the action drops out of the offered set instead of being offered a rite
    # the boundary would refuse.
    assert "cause_event_id" not in build_param_options(SponsorDaoRite, dummy_avatar)
    assert SponsorDaoRite(dummy_avatar, base_world).can_possibly_start() is False


@pytest.mark.asyncio
async def test_rolling_back_the_month_releases_the_transient_dedup(
    base_world, dummy_avatar
):
    """A rolled-back sponsorship must be re-decidable, not permanently spent.

    The dedup cache lives on the World, so the month checkpoint owns it like
    any other canonical field; this is that guarantee, without driving a whole
    Simulator month.
    """
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)

    checkpoint = SimulationMonthCheckpoint.capture(base_world)
    await _run_committed_action(dummy_avatar)
    assert get_sponsor_dao_rite_blocker(base_world, dummy_avatar, rite.id) is not None

    checkpoint.restore()

    # The rite is sponsorable again, and the retry produces a real fact.
    assert get_sponsor_dao_rite_blocker(base_world, dummy_avatar, rite.id) is None
    retry = _decide_to_sponsor(base_world, dummy_avatar, rite.id)
    sponsorship = _sponsorship_of(await _run_committed_action(dummy_avatar))
    assert sponsorship.causal_payload["decision_source"]["decision_event_id"] == retry.id


@pytest.mark.asyncio
async def test_sponsorship_records_own_knowledge_and_grounded_memory(
    base_world, dummy_avatar
):
    """Knowledge is not omniscient: only the acting institution learns."""
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)
    institution_id = _dynasty_institution_id(base_world)

    sponsorship = _sponsorship_of(await _run_committed_action(dummy_avatar))

    known = base_world.institutional_knowledge.get_fact(institution_id, sponsorship.id)
    assert known is not None
    assert known.channel is KnowledgeChannel.OWN_ACTION
    assert known.learned_from_event_id == sponsorship.id
    # Nobody else learned anything from this act.
    assert [
        fact.institution_id
        for fact in base_world.institutional_knowledge.known_facts.values()
        if fact.event_id == sponsorship.id
    ] == [institution_id]

    memories = base_world.institutional_relations.memories_for(institution_id)
    memory = next(item for item in memories if item.event_id == sponsorship.id)
    factors = dict(memory.factors)
    # One act is exactly one share of the audience threshold; nothing about a
    # rite changes an office or breaches a commitment, and no anchor exists.
    assert factors == {
        "relative_scale": pytest.approx(1.0 / RITES_REQUIRED_FOR_AUDIENCE),
        "institutional_change": 0.0,
        "commitment_breach": 0.0,
        "identity_anchor_impact": 0.0,
    }
    assert memory.salience == pytest.approx(salience_for_factors(factors))


@pytest.mark.asyncio
async def test_an_anchored_region_raises_the_remembered_weight(
    base_world, dummy_avatar
):
    """The anchor factor is a real reading, not a constant left at zero."""
    region = _emperor_in_region(base_world, dummy_avatar)
    institution_id = _dynasty_institution_id(base_world)
    anchor_source = _popular_rite(base_world, region)
    base_world.institutional_authority.add_identity_anchor(
        InstitutionalIdentityAnchor(
            institution_id=institution_id,
            kind=IdentityAnchorKind.SACRED_SITE,
            subject=EntityRef("region", str(region.id)),
            established_month=int(base_world.month_stamp),
            evidence_event_ids=(anchor_source.id,),
        )
    )
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)

    sponsorship = _sponsorship_of(await _run_committed_action(dummy_avatar))

    memory = next(
        item
        for item in base_world.institutional_relations.memories_for(institution_id)
        if item.event_id == sponsorship.id
    )
    assert dict(memory.factors)["identity_anchor_impact"] == 1.0


@pytest.mark.asyncio
async def test_the_institution_reads_its_own_memory_but_a_member_does_not(
    base_world, dummy_avatar
):
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)
    sponsorship = _sponsorship_of(await _run_committed_action(dummy_avatar))
    base_world.event_manager.add_event(sponsorship)

    context = get_sponsor_institution_memory(base_world, dummy_avatar)
    assert context is not None
    assert [fact["event_id"] for fact in context["known_facts"]] == [sponsorship.id]
    assert context["known_facts"][0]["channel"] == KnowledgeChannel.OWN_ACTION.value
    assert context["authorized_holder"]["holder_ref"]["id"] == str(dummy_avatar.id)
    # The same projection has to actually reach the decision prompt, not just
    # the helper: this is the wiring the future decision reads.
    prompt_context = build_avatar_prompt_context(dummy_avatar)
    assert prompt_context["local_world"]["own_institution_memory"] == context

    # An ordinary avatar speaks for no institution and sees nothing, through
    # the same prompt path.
    member = _plain_avatar(base_world, "Commoner")
    member.tile = SimpleNamespace(region=region)
    assert get_sponsor_institution_memory(base_world, member) is None
    assert (
        build_avatar_prompt_context(member)["local_world"]["own_institution_memory"]
        is None
    )


@pytest.mark.asyncio
async def test_a_dead_office_holder_between_commit_and_finish_mutates_nothing(
    base_world, dummy_avatar
):
    """Authority is revalidated at the boundary, exactly as the rite window is."""
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)
    assert dummy_avatar.commit_next_plan() is not None
    institution_id = _dynasty_institution_id(base_world)

    dummy_avatar.is_dead = True

    assert await dummy_avatar.tick_action() == []
    assert base_world.institutional_relations.memories_for(institution_id) == ()
    assert base_world.institutional_knowledge.known_facts == {}


@pytest.mark.asyncio
async def test_losing_the_recognition_scope_between_commit_and_finish_refuses(
    base_world, dummy_avatar
):
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)
    assert dummy_avatar.commit_next_plan() is not None

    state = base_world.institutional_authority
    office = next(
        item
        for item in state.offices.values()
        if item.institution_id == _dynasty_institution_id(base_world)
    )
    state.offices[office.id] = replace(
        office,
        scopes=tuple(
            scope for scope in office.scopes if scope is not AuthorityScope.RECOGNITION
        ),
    )

    assert get_sponsor_dao_rite_blocker(base_world, dummy_avatar, rite.id) is not None
    assert await dummy_avatar.tick_action() == []


@pytest.mark.asyncio
async def test_the_sponsorship_survives_a_later_leadership_change(
    base_world, dummy_avatar
):
    """History is not unmade by who holds the office afterwards."""
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)
    sponsorship = _sponsorship_of(await _run_committed_action(dummy_avatar))
    base_world.event_manager.add_event(sponsorship)
    institution_id = _dynasty_institution_id(base_world)

    # The emperor dies and the office changes hands.
    successor = _plain_avatar(base_world, "Successor")
    dummy_avatar.is_dead = True
    base_world.dynasty.current_emperor_id = successor.id
    synchronize_institutional_authority(base_world)

    assert base_world.institutional_knowledge.contains(institution_id, sponsorship.id)
    assert _is_institutional_rite(base_world, sponsorship, {})
    memories = base_world.institutional_relations.memories_for(institution_id)
    assert [item.event_id for item in memories] == [sponsorship.id]


@pytest.mark.asyncio
async def test_recording_the_same_sponsorship_twice_is_idempotent(
    base_world, dummy_avatar
):
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)
    sponsorship = _sponsorship_of(await _run_committed_action(dummy_avatar))
    institution_id = _dynasty_institution_id(base_world)
    deltas_before = list(sponsorship.causal_payload["deltas"])

    record_known_fact(
        base_world,
        sponsorship,
        (institution_id,),
        factors=_sponsorship_memory_factors(base_world, institution_id, region.id),
        channel=KnowledgeChannel.OWN_ACTION,
    )

    assert sponsorship.causal_payload["deltas"] == deltas_before
    assert len(base_world.institutional_relations.memories_for(institution_id)) == 1


@pytest.mark.asyncio
async def test_the_step_passes_causal_integrity_with_its_decision_and_fact(
    base_world, dummy_avatar
):
    """The new knowledge and memory deltas must survive the finalizer's audit."""
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    decision = _decide_to_sponsor(base_world, dummy_avatar, rite.id)

    sponsorship = _sponsorship_of(await _run_committed_action(dummy_avatar))

    ctx = SimulationStepContext.create(base_world)
    ctx.add_events([decision, sponsorship])
    # Raises CausalIntegrityError if any delta misnames its owning event or the
    # authorship is inverted.
    validate_causal_integrity(ctx, ctx.events)


@pytest.mark.asyncio
async def test_rolling_back_the_month_releases_knowledge_and_memory(
    base_world, dummy_avatar
):
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)
    institution_id = _dynasty_institution_id(base_world)

    checkpoint = SimulationMonthCheckpoint.capture(base_world)
    await _run_committed_action(dummy_avatar)
    assert base_world.institutional_knowledge.known_facts != {}

    checkpoint.restore()

    assert base_world.institutional_knowledge.known_facts == {}
    assert base_world.institutional_relations.memories_for(institution_id) == ()


@pytest.mark.asyncio
async def test_decision_naming_another_rite_authors_no_sponsorship(
    base_world, dummy_avatar
):
    region = _emperor_in_region(base_world, dummy_avatar)
    chosen = _popular_rite(base_world, region)
    other = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, chosen.id)

    # The chain chose `chosen`; the boundary is asked to sponsor `other`.
    assert (
        record_dao_rite_sponsorship(
            base_world,
            dummy_avatar,
            other.id,
            action_origin=ActionOrigin.ACTOR_CHOICE,
        )
        is None
    )


@pytest.mark.asyncio
async def test_rite_that_went_stale_is_rejected_at_the_execution_boundary(
    base_world, dummy_avatar
):
    region = _emperor_in_region(base_world, dummy_avatar)
    rite = _popular_rite(base_world, region)
    _decide_to_sponsor(base_world, dummy_avatar, rite.id)
    assert dummy_avatar.commit_next_plan() is not None

    _advance(base_world, RITE_WINDOW_MONTHS)
    assert get_sponsor_dao_rite_blocker(base_world, dummy_avatar, rite.id) is not None
    assert await dummy_avatar.tick_action() == []


def test_future_and_story_rites_are_never_sponsorable(base_world, dummy_avatar):
    region = _emperor_in_region(base_world, dummy_avatar)
    future = _popular_rite(base_world, region, month=int(base_world.month_stamp) + 1)
    assert get_sponsor_dao_rite_blocker(base_world, dummy_avatar, future.id) is not None

    story = _popular_rite(base_world, region)
    story.is_story = True
    assert get_sponsor_dao_rite_blocker(base_world, dummy_avatar, story.id) is not None


@pytest.mark.asyncio
async def test_forged_sponsorships_never_reach_a_celestial_audience(
    base_world, dummy_avatar
):
    """A well-shaped payload is a claim, not evidence of a real sponsorship."""
    region = _emperor_in_region(base_world, dummy_avatar)
    cause = _popular_rite(base_world, region)
    cause.is_major = True
    real_decision = _decide_to_sponsor(base_world, dummy_avatar, cause.id)

    unrelated = build_avatar_decision_event(
        base_world,
        dummy_avatar,
        [("Rest", {})],
        "",
        "",
        source="llm",
        offered={"Rest": {}},
    )
    base_world.event_manager.add_event(unrelated)

    def _forged(decision_event_id: str, *, origin: CausalOrigin | None) -> Event:
        event = Event(
            base_world.month_stamp,
            "A claimed sponsorship",
            event_type="dao_rite",
            fact_kind=FactKind.OCCURRENCE,
            **({"causal_origin": origin} if origin is not None else {}),
            causal_payload={
                "deltas": [],
                "dao_rite": {
                    "sponsor_kind": "court",
                    "sponsor_id": "1",
                    "institution_name": "Test",
                    "region_id": region.id,
                    "cause_event_id": cause.id,
                    "is_popular": False,
                    "is_sponsorship": True,
                },
                "decision_source": {
                    "kind": "avatar_action",
                    "action_name": "SponsorDaoRite",
                    "avatar_id": str(dummy_avatar.id),
                    "decision_event_id": decision_event_id,
                },
            },
        )
        base_world.event_manager.add_event(event)
        return event

    overlays: dict[str, Event] = {}
    # Both of these clear the structural guards -- they carry the actor-decision
    # origin a genuine sponsorship has -- so they actually reach the lookup and
    # are rejected there: one pointer dangles, the other resolves to a real
    # decision that chose Rest.
    dangling = _forged("no-such-decision", origin=CausalOrigin.ACTOR_DECISION)
    wrong_action = _forged(unrelated.id, origin=CausalOrigin.ACTOR_DECISION)
    assert not _is_institutional_rite(base_world, dangling, overlays)
    assert not _is_institutional_rite(base_world, wrong_action, overlays)

    # A pointer to the genuine sponsorship decision, but on a fact that never
    # went through the boundary: the origin the owner writes is missing, so it
    # is stopped by the structural guard before the lookup.
    unauthored = _forged(real_decision.id, origin=None)
    assert unauthored.causal_origin is not CausalOrigin.ACTOR_DECISION
    assert not _is_institutional_rite(base_world, unauthored, overlays)

    before = list(base_world.dao_petitions)
    await process_grounded_dao_rites(base_world, [])
    assert base_world.dao_petitions == before

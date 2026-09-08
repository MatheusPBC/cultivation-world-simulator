"""Other institutions may interpret a sponsorship they actually witnessed.

Witnessing is a fact about who was present when the act happened, captured at
that exact moment.  These tests drive the real action lifecycle and the real
`economy_reactivity` gateway, and they never force a reaction: maintain is the
default and no relation kind or war is ever created.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.classes.action_runtime import ActionOrigin
from src.classes.alignment import Alignment
from src.classes.observe import is_within_observation
from src.classes.celestial_dao import DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.institution import (
    AuthorityScope,
    Institution,
    InstitutionKind,
    KnowledgeChannel,
)
from src.classes.mechanical_language import EntityRef
from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint
from src.systems.avatar_decision import (
    adopt_avatar_decision,
    build_avatar_decision_event,
)
from src.systems.economy_reactivity import process_economy_reactivity
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institutional_relationship_impact import (
    _observer_candidates,
    _reaction_pair,
    _receipt_id,
    _sponsorship,
    process_institutional_relationship_impacts,
)
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue


def _avatar(base_world, name: str, *, pos: tuple[int, int] = (0, 0)):
    from src.classes.age import Age
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
        pos_x=pos[0],
        pos_y=pos[1],
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )
    avatar.personas = []
    avatar.technique = None
    base_world.avatar_manager.register_avatar(avatar)
    return avatar


def _sect_with_patriarch(base_world, sect_id: int, name: str, patriarch) -> Sect:
    sect = Sect(
        id=sect_id,
        name=name,
        desc="",
        member_act_style="",
        alignment=Alignment.RIGHTEOUS,
        headquarter=SectHeadQuarter(name="HQ", desc="", image=Path("")),
        technique_names=[],
        orthodoxy_id="dao",
    )
    patriarch.sect = sect
    patriarch.sect_rank = "patriarch"
    sect.members = {str(patriarch.id): patriarch}
    existing = list(getattr(base_world, "existed_sects", None) or [])
    base_world.existed_sects = [*existing, sect]
    base_world.sect_context.from_existed_sects(base_world.existed_sects)
    return sect


@pytest.fixture(autouse=True)
def no_provider_calls(monkeypatch):
    """Fail loudly instead of reaching a provider, whatever the shell env is.

    These tests must never depend on ambient test mode: an unnoticed real call
    would hang the run rather than fail it.
    """

    async def _forbidden(*args, **kwargs):
        raise AssertionError("no provider call is allowed in this test")

    monkeypatch.setattr(
        "src.systems.domain_decision_interpreter.call_llm_with_task_name", _forbidden
    )
    return _forbidden


@pytest.fixture
def witnessed_world(base_world, dummy_avatar):
    """An emperor sponsoring beside two watching patriarchs and one outsider.

    Proximity is the whole point of the fixture: the two nearby patriarchs can
    actually see the sponsor, while the distant one cannot and therefore never
    becomes a witness however interested it might be.
    """
    # Declared on the World itself, so `is_world_test_mode` is true regardless
    # of the ambient ContextVar the shell may or may not have set.
    base_world.run_config_snapshot = {
        **(getattr(base_world, "run_config_snapshot", None) or {}),
        "test_mode": True,
    }
    region = CityRegion(
        id=7, name="Rite City", desc="", cors=[(0, 0)], dao_tradition=DaoTradition.BALANCE
    )
    base_world.map.regions[7] = region
    base_world.avatar_manager.register_avatar(dummy_avatar)
    dummy_avatar.tile = SimpleNamespace(region=region)
    dummy_avatar.pos_x, dummy_avatar.pos_y = 0, 0
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=dummy_avatar.id
    )

    # Observation radius at this realm is 3 on the 10x10 test map, so the two
    # neighbours are inside it and the far corner is decisively outside.
    near_a = _avatar(base_world, "NearPatriarchA", pos=(0, 1))
    near_b = _avatar(base_world, "NearPatriarchB", pos=(1, 0))
    far = _avatar(base_world, "FarPatriarch", pos=(9, 9))
    for avatar in (near_a, near_b, far):
        avatar.tile = SimpleNamespace(region=region)
    sect_a = _sect_with_patriarch(base_world, 11, "Near Sect A", near_a)
    sect_b = _sect_with_patriarch(base_world, 12, "Near Sect B", near_b)
    sect_far = _sect_with_patriarch(base_world, 13, "Far Sect", far)

    bootstrap_institutional_authority(base_world)
    return SimpleNamespace(
        region=region,
        sponsor=dummy_avatar,
        sponsor_institution_id=Institution.id_for(
            InstitutionKind.DYNASTY, EntityRef("dynasty", "1")
        ),
        witness_ids=(
            Institution.id_for(InstitutionKind.SECT, EntityRef("sect", "11")),
            Institution.id_for(InstitutionKind.SECT, EntityRef("sect", "12")),
        ),
        outsider_id=Institution.id_for(InstitutionKind.SECT, EntityRef("sect", "13")),
        sects=(sect_a, sect_b, sect_far),
    )


def _popular_rite(base_world, region) -> Event:
    event = Event(
        base_world.month_stamp,
        "A popular rite",
        event_type="dao_rite",
        causal_payload={"dao_rite": {"is_popular": True, "region_id": region.id}},
    )
    base_world.event_manager.add_event(event)
    return event


async def _sponsor(base_world, world_fixture) -> Event:
    rite = _popular_rite(base_world, world_fixture.region)
    avatar = world_fixture.sponsor
    pairs = [("SponsorDaoRite", {"cause_event_id": str(rite.id)})]
    avatar.load_decide_result_chain(
        pairs, "", "", origin=ActionOrigin.ACTOR_CHOICE
    )
    decision = build_avatar_decision_event(
        base_world, avatar, pairs, "", "", source="llm", offered={"SponsorDaoRite": {}}
    )
    adopt_avatar_decision(avatar, decision)
    base_world.event_manager.add_event(decision)
    assert avatar.commit_next_plan() is not None
    events = await avatar.tick_action()
    sponsorship = next(
        event
        for event in events
        if (event.causal_payload or {}).get("dao_rite", {}).get("is_sponsorship")
    )
    base_world.event_manager.add_event(sponsorship)
    return sponsorship


@pytest.mark.asyncio
async def test_only_present_holders_become_witnesses(base_world, witnessed_world):
    sponsorship = await _sponsor(base_world, witnessed_world)

    rite = sponsorship.causal_payload["dao_rite"]
    assert tuple(rite["witness_institution_ids"]) == witnessed_world.witness_ids
    # The distant sect is interested but was not there.
    assert witnessed_world.outsider_id not in rite["witness_institution_ids"]
    # The sponsor never witnesses itself.
    assert witnessed_world.sponsor_institution_id not in rite["witness_institution_ids"]

    knowledge = base_world.institutional_knowledge
    for witness_id in witnessed_world.witness_ids:
        fact = knowledge.get_fact(witness_id, sponsorship.id)
        assert fact is not None and fact.channel is KnowledgeChannel.MEMBER_WITNESS
        # Knowing is not remembering: no engine weight exists for an onlooker.
        assert base_world.institutional_relations.memories_for(witness_id) == ()
    assert knowledge.get_fact(witnessed_world.outsider_id, sponsorship.id) is None
    own = knowledge.get_fact(witnessed_world.sponsor_institution_id, sponsorship.id)
    assert own is not None and own.channel is KnowledgeChannel.OWN_ACTION


@pytest.mark.asyncio
async def test_each_witness_pairs_only_with_the_sponsor(base_world, witnessed_world):
    sponsorship = await _sponsor(base_world, witnessed_world)
    overlays = {sponsorship.id: sponsorship}

    assert set(_observer_candidates(base_world, sponsorship, overlays)) == set(
        witnessed_world.witness_ids
    )
    first, second = witnessed_world.witness_ids
    sponsor_id = witnessed_world.sponsor_institution_id
    # Each witness reacts about the sponsor, never about the other witness.
    assert _reaction_pair(base_world, first, sponsorship, overlays) == (
        first,
        sponsor_id,
    )
    assert _reaction_pair(base_world, second, sponsorship, overlays) == (
        second,
        sponsor_id,
    )
    assert second not in _reaction_pair(base_world, first, sponsorship, overlays)
    # The sponsor cannot react to its own act.
    assert _reaction_pair(base_world, sponsor_id, sponsorship, overlays) == ()
    assert _reaction_pair(
        base_world, witnessed_world.outsider_id, sponsorship, overlays
    ) == ()


@pytest.mark.asyncio
async def test_a_popular_rite_and_a_forged_flag_are_not_reactable(
    base_world, witnessed_world
):
    popular = _popular_rite(base_world, witnessed_world.region)
    assert _sponsorship(base_world, popular, {}) is None

    forged = Event(
        base_world.month_stamp,
        "A claimed sponsorship",
        event_type="dao_rite",
        causal_payload={
            "deltas": [],
            "dao_rite": {
                "is_sponsorship": True,
                "sponsor_institution_id": witnessed_world.sponsor_institution_id,
                "witness_institution_ids": list(witnessed_world.witness_ids),
                "cause_event_id": popular.id,
            },
        },
    )
    # A loose flag is not a source: the Dao owner refuses to call it one.
    assert _sponsorship(base_world, forged, {}) is None
    assert _observer_candidates(base_world, forged, {}) == ()


@pytest.mark.asyncio
async def test_a_dangling_sponsor_or_witness_id_offers_nothing(
    base_world, witnessed_world
):
    sponsorship = await _sponsor(base_world, witnessed_world)
    rite = sponsorship.causal_payload["dao_rite"]

    rite["witness_institution_ids"] = [
        witnessed_world.witness_ids[0],
        "inst:sect:does-not-exist",
        None,
        {"id": "inst:sect:11"},
    ]
    resolved = _sponsorship(base_world, sponsorship, {sponsorship.id: sponsorship})
    # Unknown and malformed entries are dropped, not coerced into identities.
    assert resolved["witness_institution_ids"] == (witnessed_world.witness_ids[0],)

    rite["sponsor_institution_id"] = "inst:dynasty:does-not-exist"
    assert _sponsorship(base_world, sponsorship, {sponsorship.id: sponsorship}) is None
    assert _observer_candidates(base_world, sponsorship, {}) == ()


@pytest.mark.asyncio
async def test_test_mode_maintains_and_creates_no_relation(base_world, witnessed_world):
    sponsorship = await _sponsor(base_world, witnessed_world)

    produced = await process_institutional_relationship_impacts(
        base_world, current_events=[sponsorship]
    )

    # Every witness decided, and every one of them maintained.
    assert len(produced) == len(witnessed_world.witness_ids)
    assert base_world.institutional_relations.relations == {}
    receipts = base_world.mechanical_language.reaction_receipts
    assert len(receipts) == len(witnessed_world.witness_ids)


@pytest.mark.asyncio
async def test_an_injected_positive_reading_moves_only_the_shared_climate(
    base_world, witnessed_world
):
    sponsorship = await _sponsor(base_world, witnessed_world)
    witness_id = witnessed_world.witness_ids[0]

    def _inject(institution_id: str, _event: Event) -> DomainDecision | None:
        if institution_id != witness_id:
            return None
        options = _positive_options(base_world, sponsorship, institution_id)
        return DomainDecision(
            DomainDecisionKind.ACT, "The court honoured our region's rite.",
            selected_affordance_id=options[0].id,
        )

    produced = await process_institutional_relationship_impacts(
        base_world, current_events=[sponsorship], injected_decisions=_inject
    )

    changed = [
        event
        for event in produced
        if event.event_type == "institutional_relationship_changed"
    ]
    assert len(changed) == 1
    relations = list(base_world.institutional_relations.relations.values())
    assert len(relations) == 1
    relation = relations[0]
    assert relation.friendliness == 2
    assert {relation.institution_a_id, relation.institution_b_id} == {
        witness_id,
        witnessed_world.sponsor_institution_id,
    }
    # No war, no alliance, no new relation kind.
    assert relation.kind.value == "neutral"


@pytest.mark.asyncio
async def test_an_injected_negative_reading_never_forces_war(
    base_world, witnessed_world
):
    sponsorship = await _sponsor(base_world, witnessed_world)
    witness_id = witnessed_world.witness_ids[0]

    def _inject(institution_id: str, _event: Event) -> DomainDecision | None:
        if institution_id != witness_id:
            return None
        options = [
            option
            for option in _all_options(base_world, sponsorship, institution_id)
            if option.parameters["valence"] == "negative"
            and option.parameters["intensity"] == "strong"
        ]
        return DomainDecision(
            DomainDecisionKind.ACT, "A rival court courting our people.",
            selected_affordance_id=options[0].id,
        )

    await process_institutional_relationship_impacts(
        base_world, current_events=[sponsorship], injected_decisions=_inject
    )

    relation = next(iter(base_world.institutional_relations.relations.values()))
    assert relation.friendliness == -6
    assert relation.kind.value == "neutral"


def _all_options(base_world, sponsorship: Event, institution_id: str):
    from src.systems.domain_affordance_registry import DOMAIN_AFFORDANCES
    from src.systems.institutional_relationship_impact import (
        RELATIONSHIP_IMPACT_DOMAIN,
        RelationshipAffordanceContext,
    )

    institution = base_world.institutional_authority.get_institution(institution_id)
    context = RelationshipAffordanceContext(
        base_world,
        RELATIONSHIP_IMPACT_DOMAIN,
        institution.owner_ref,
        sponsorship,
        event_overlays={sponsorship.id: sponsorship},
    )
    return DOMAIN_AFFORDANCES.compose(context)


def _positive_options(base_world, sponsorship: Event, institution_id: str):
    return [
        option
        for option in _all_options(base_world, sponsorship, institution_id)
        if option.parameters["valence"] == "positive"
        and option.parameters["intensity"] == "mild"
    ]


@pytest.mark.asyncio
async def test_the_existing_economy_reactivity_gateway_carries_the_sponsorship(
    base_world, witnessed_world, no_provider_calls
):
    """End to end through the phase that actually runs this in a month."""
    sponsorship = await _sponsor(base_world, witnessed_world)

    produced = await process_economy_reactivity(
        base_world,
        current_events=[sponsorship],
        invalidations=DomainInvalidationQueue(),
        llm_call=no_provider_calls,
    )

    reacted = [
        event
        for event in produced
        if event.render_params.get("domain") == "institutional_relationship_impact"
    ]
    assert {str(event.render_params.get("actor_id")) for event in reacted} == {
        "11",
        "12",
    }
    # Test mode keeps the climate untouched by default.
    assert base_world.institutional_relations.relations == {}


@pytest.mark.asyncio
async def test_moving_the_holder_away_does_not_unmake_the_witness_snapshot(
    base_world, witnessed_world
):
    """Eligibility is historical: who was there then, not who is here now."""
    sponsorship = await _sponsor(base_world, witnessed_world)
    witness_id = witnessed_world.witness_ids[0]
    holder = base_world.avatar_manager.get_avatar(
        str(
            base_world.institutional_authority.office_for_scope(
                witness_id, AuthorityScope.COMMITMENT_NEGOTIATION
            ).holder_ref.id
        )
    )

    # The patriarch walks to the far corner, well outside its own radius.
    holder.pos_x, holder.pos_y = 9, 9
    assert not is_within_observation(holder, witnessed_world.sponsor)

    overlays = {sponsorship.id: sponsorship}
    # The snapshot is untouched and the witness may still react.
    assert witness_id in sponsorship.causal_payload["dao_rite"][
        "witness_institution_ids"
    ]
    assert witness_id in _observer_candidates(base_world, sponsorship, overlays)
    assert _reaction_pair(base_world, witness_id, sponsorship, overlays) == (
        witness_id,
        witnessed_world.sponsor_institution_id,
    )
    produced = await process_institutional_relationship_impacts(
        base_world, current_events=[sponsorship]
    )
    assert len(produced) == len(witnessed_world.witness_ids)


@pytest.mark.asyncio
async def test_losing_the_scope_mid_interpretation_spends_no_receipt(
    base_world, witnessed_world
):
    """A maintain decided without current authority must close nothing."""
    sponsorship = await _sponsor(base_world, witnessed_world)
    witness_id = witnessed_world.witness_ids[0]
    authority = base_world.institutional_authority

    def _strip_scope(_institution_id: str, _event: Event) -> DomainDecision | None:
        # Runs while the interpreter is deciding for this observer.
        office = authority.office_for_scope(
            witness_id, AuthorityScope.COMMITMENT_NEGOTIATION
        )
        if office is not None:
            authority.offices[office.id] = replace(
                office,
                scopes=tuple(
                    scope
                    for scope in office.scopes
                    if scope is not AuthorityScope.COMMITMENT_NEGOTIATION
                ),
            )
        return None

    await process_institutional_relationship_impacts(
        base_world, current_events=[sponsorship], injected_decisions=_strip_scope
    )

    # The other witness still closed its own reaction; the stripped one did not,
    # so its fact stays open rather than being silently spent.  Compared by the
    # canonical receipt ID for this exact (institution, fact) pair.
    spent = base_world.mechanical_language.reaction_receipts
    assert _receipt_id(witness_id, sponsorship.id) not in spent
    other_id = witnessed_world.witness_ids[1]
    assert _receipt_id(other_id, sponsorship.id) in spent
    assert len(spent) == len(witnessed_world.witness_ids) - 1
    assert base_world.institutional_relations.relations == {}


@pytest.mark.asyncio
async def test_a_receipt_closes_the_fact_and_a_rollback_releases_it(
    base_world, witnessed_world
):
    sponsorship = await _sponsor(base_world, witnessed_world)
    checkpoint = SimulationMonthCheckpoint.capture(base_world)

    await process_institutional_relationship_impacts(
        base_world, current_events=[sponsorship]
    )
    receipts_after = dict(base_world.mechanical_language.reaction_receipts)
    assert receipts_after

    # Re-running the same month's fact spends nothing further.
    again = await process_institutional_relationship_impacts(
        base_world, current_events=[sponsorship]
    )
    assert again == []
    assert base_world.mechanical_language.reaction_receipts == receipts_after

    checkpoint.restore()

    # Only what happened after the capture is released: the reactions are gone
    # and the fact is open again, while the sponsorship itself -- which
    # happened before the capture -- is still known to sponsor and witnesses.
    assert base_world.mechanical_language.reaction_receipts == {}
    assert base_world.institutional_knowledge.contains(
        witnessed_world.sponsor_institution_id, sponsorship.id
    )
    for witness_id in witnessed_world.witness_ids:
        assert base_world.institutional_knowledge.contains(witness_id, sponsorship.id)
    reopened = await process_institutional_relationship_impacts(
        base_world, current_events=[sponsorship]
    )
    assert len(reopened) == len(witnessed_world.witness_ids)

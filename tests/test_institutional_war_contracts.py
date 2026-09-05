"""Focused guards for the grounded, unilateral war declaration contract."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from src.classes.action_runtime import ActionOrigin
from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.environment.sect_region import SectRegion
from src.classes.event import Event, FactKind
from src.classes.institution import AuthorityScope, InstitutionalRelationKind
from src.classes.mechanical_language import EntityRef
from src.classes.root import Root
from src.classes.sect_ranks import SectRank
from src.systems.avatar_aggression import (
    DELIBERATE_ATTACK_EVENT_TYPE,
    canonical_aggression,
    capture_aggression_snapshot,
    record_deliberate_attack,
)
from src.systems.cultivation import Realm
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
    event_lookup,
)
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institutional_diplomacy import (
    WAR_DECLARED_EVENT_TYPE,
    are_sects_at_war,
    conclude_formal_war,
    sect_institution_id,
    sect_institution_ref,
)
import src.systems.institutional_war as war
from src.systems.time import Month, Year, create_month_stamp


def _war_world(world, *, layout=((1, (0, 0)), (2, (1, 0))), disciples_at=None):
    """Active, authorized sects placed exactly where the test needs them."""

    hq = SectHeadQuarter(name="War HQ", desc="", image=Path(""))
    sects = []
    for sect_id, coordinate in layout:
        disciple_position = (
            coordinate if disciples_at is None else disciples_at[sect_id]
        )
        region = SectRegion(
            id=6000 + sect_id,
            name=f"War Sect {sect_id} HQ",
            desc="",
            sect_id=sect_id,
            sect_name=f"War Sect {sect_id}",
            cors=[coordinate],
        )
        world.map.regions[region.id] = region
        world.map.region_cors[region.id] = [coordinate]
        sect = Sect(
            id=sect_id,
            name=f"War Sect {sect_id}",
            desc="",
            member_act_style="",
            alignment=Alignment.NEUTRAL,
            headquarter=hq,
            technique_names=[],
        )
        patriarch = Avatar(
            world=world,
            name=f"War Patriarch {sect_id}",
            id=f"war-patriarch-{sect_id}",
            birth_month_stamp=create_month_stamp(Year(1), Month.JANUARY),
            age=Age(30, Realm.Qi_Refinement),
            gender=Gender.MALE,
            pos_x=coordinate[0],
            pos_y=coordinate[1],
            root=Root.GOLD,
            alignment=Alignment.NEUTRAL,
            personas=[],
        )
        patriarch.weapon = None
        patriarch.technique = None
        patriarch.join_sect(sect, SectRank.Patriarch)
        world.avatar_manager.register_avatar(patriarch)
        disciple = Avatar(
            world=world,
            name=f"War Disciple {sect_id}",
            id=f"war-disciple-{sect_id}",
            birth_month_stamp=create_month_stamp(Year(1), Month.JANUARY),
            age=Age(20, Realm.Qi_Refinement),
            gender=Gender.MALE,
            pos_x=disciple_position[0],
            pos_y=disciple_position[1],
            root=Root.GOLD,
            alignment=Alignment.NEUTRAL,
            personas=[],
        )
        disciple.weapon = None
        disciple.technique = None
        disciple.join_sect(sect, SectRank.OuterDisciple)
        world.avatar_manager.register_avatar(disciple)
        sects.append(sect)
    world.map.update_sect_regions()
    world.existed_sects = sects
    world.sect_context.from_existed_sects(sects)
    world.run_config_snapshot = {
        "test_mode": True,
        "provider": "test",
        "npc_awakening_rate_per_month": 0.0,
        # The deterministic fallback must never start a war on its own here.
        "domain_affordance_action_urgency_threshold": 1.0,
    }
    bootstrap_institutional_authority(world)
    return sects


def _patriarch(world, sect_id):
    return world.avatar_manager.get_avatar(f"war-patriarch-{sect_id}")


def _disciple(world, sect_id):
    return world.avatar_manager.get_avatar(f"war-disciple-{sect_id}")


def _decided_attack(world, initiator, target):
    """Author a real, canonical decision fact through its own owner.

    The decision event is produced by the decision boundary itself and
    committed, so the aggression it authors is grounded in an actual fact
    rather than in a payload that merely names one.

    The audited step is ``MutualAttack`` with a ``target_avatar`` selector:
    that is the one publicly offered action by which an Avatar opens
    hostilities, and therefore the only one this contract accepts.
    """

    from src.systems.avatar_decision import (
        DECISION_SOURCE_LLM,
        adopt_avatar_decision,
        build_avatar_decision_event,
        offered_actions,
    )

    pairs = [("MutualAttack", {"target_avatar": target.name})]
    decision_event = build_avatar_decision_event(
        world,
        initiator,
        pairs,
        "",
        "",
        source=DECISION_SOURCE_LLM,
        offered=offered_actions(initiator),
    )
    adopt_avatar_decision(initiator, decision_event)
    assert world.event_manager.commit_step([decision_event])
    return {"target_avatar": target.name}, decision_event


def _aggression(
    world, *, initiator=None, target=None, aggressor_sect_id=2, victim_sect_id=1
):
    initiator = initiator or _patriarch(world, aggressor_sect_id)
    target = target or _patriarch(world, victim_sect_id)
    params, _decision = _decided_attack(world, initiator, target)
    snapshot = capture_aggression_snapshot(
        world,
        initiator,
        target,
        params=params,
        action_origin=ActionOrigin.ACTOR_CHOICE,
    )
    assert snapshot is not None
    event = record_deliberate_attack(
        world, snapshot, initiator=initiator, target=target
    )
    assert world.event_manager.commit_step([event])
    return event


async def _run(world, *, injected=None):
    return await war.process_institutional_war_declaration(
        world, injected_decisions=injected
    )


def _act_on_first(world):
    def injected(_domain, sect_id, trigger):
        context = war.WarAffordanceContext(
            world,
            war.DECLARATION_DOMAIN,
            sect_institution_ref(sect_id),
            trigger,
            None,
            (),
        )
        options = DOMAIN_AFFORDANCES.compose(context)
        return DomainDecision(
            DomainDecisionKind.ACT, "Answer the attack.", options[0].id
        )

    return injected


def test_a_reactive_attack_is_never_a_cause(base_world):
    """A counterattack or failed escape never bootstraps a war.

    The victim keeps its previous, still-current decision, and that decision
    may legitimately name the very same attack.  Only the engine-written plan
    provenance separates the two, so it must be decisive on its own.
    """

    _war_world(base_world)
    initiator = _patriarch(base_world, 2)
    target = _patriarch(base_world, 1)
    params, _decision = _decided_attack(base_world, initiator, target)

    assert (
        capture_aggression_snapshot(
            base_world,
            initiator,
            target,
            params=params,
            action_origin=ActionOrigin.REACTIVE_RESPONSE,
        )
        is None
    )


def test_an_attack_the_decision_never_chose_is_not_a_cause(base_world):
    _war_world(base_world)
    initiator = _patriarch(base_world, 2)
    target = _patriarch(base_world, 1)
    _decided_attack(base_world, initiator, target)

    assert (
        capture_aggression_snapshot(
            base_world,
            initiator,
            target,
            # The audited chain names another victim, so this is another act.
            params={"target_avatar": "someone-else"},
            action_origin=ActionOrigin.ACTOR_CHOICE,
        )
        is None
    )


def test_an_attack_is_never_broadcast_to_absent_institutions(base_world):
    """Only an office holder who was there learns it; nothing is broadcast."""

    _war_world(base_world, layout=((1, (0, 0)), (2, (1, 0)), (3, (9, 9))))

    event = _aggression(base_world)

    known = base_world.institutional_knowledge
    # The two participants' own force-employment holders were the fighters.
    assert known.contains(sect_institution_id(1), event.id)
    assert known.contains(sect_institution_id(2), event.id)
    # A third sect whose patriarch was nowhere near it simply does not know.
    assert not known.contains(sect_institution_id(3), event.id)
    assert war.known_casus_belli(base_world, 3) == []


def test_a_distant_holder_who_sees_only_the_attacker_does_not_learn_it(base_world):
    """Observation is directed and per-realm: half a view is not a witness."""

    import src.systems.avatar_aggression as aggression_module

    _war_world(base_world, layout=((1, (0, 0)), (2, (1, 0)), (3, (9, 9))))
    initiator = _patriarch(base_world, 2)
    observer = _patriarch(base_world, 3)

    def sees_only_the_attacker(watcher, other):
        if watcher is observer:
            return other is initiator
        return True

    original = aggression_module.is_within_observation
    aggression_module.is_within_observation = sees_only_the_attacker
    try:
        event = _aggression(base_world)
    finally:
        aggression_module.is_within_observation = original

    assert not base_world.institutional_knowledge.contains(
        sect_institution_id(3), event.id
    )
    assert not base_world.institutional_knowledge.contains(
        sect_institution_id(3), event.id
    )
    assert base_world.institutional_knowledge.contains(sect_institution_id(1), event.id)


def test_only_the_victim_side_may_cite_the_cause(base_world):
    """Personal aggression is a cause for the attacked sect, never its author."""

    _war_world(base_world)
    event = _aggression(base_world)

    assert [cause for cause, _ in war.known_casus_belli(base_world, 1)] == [event.id]
    assert war.known_casus_belli(base_world, 2) == []


def test_the_option_carries_the_exact_grounded_parameter_contract(base_world):
    _war_world(base_world)
    event = _aggression(base_world)
    context = war.WarAffordanceContext(
        base_world,
        war.DECLARATION_DOMAIN,
        sect_institution_ref(1),
        event,
        None,
        (),
    )

    options = war.declaration_affordances(context)

    assert len(options) == 1
    option = options[0]
    assert option.action_kind == war.DECLARE_ACTION
    assert option.motivation_event_ids == (event.id,)
    assert dict(option.parameters) == {
        "declaring_sect_id": "1",
        "target_sect_id": "2",
        "declaring_institution_id": sect_institution_id(1),
        "target_institution_id": sect_institution_id(2),
        "relation_id": option.parameters["relation_id"],
        "casus_belli_event_id": event.id,
        "aggressor_avatar_id": "war-patriarch-2",
        "victim_avatar_id": "war-patriarch-1",
        # The option is bound to who authorized it, so a replacement leader
        # cannot execute a choice taken under the previous holder.
        "authorizing_office_id": "office:inst:sect:1:patriarch",
        "authorizing_holder_avatar_id": "war-patriarch-1",
    }
    reading = war.casus_belli_reading(base_world, option, alternatives=options)
    assert reading is not None
    # Nothing the engine cannot ground is ever filled in with a number.
    assert reading.objective == war.UNKNOWN
    assert reading.expected_cost == war.UNKNOWN
    assert reading.expected_gain == war.UNKNOWN
    assert reading.perceived_cause_event_id == event.id
    assert reading.reach == "demonstrated_by_attack"


def test_a_dangling_or_foreign_decision_source_is_never_a_cause(base_world):
    """A well-shaped fact naming an unverifiable decision offers nothing."""

    _war_world(base_world)
    event = _aggression(base_world)
    payload = dict(event.causal_payload["avatar_aggression"])
    assert [cause for cause, _ in war.known_casus_belli(base_world, 1)] == [event.id]

    lookup = event_lookup(base_world)
    # The real fact is grounded; the same fact citing a decision that does not
    # exist, or one authored by somebody else, is not.
    assert canonical_aggression(event, lookup=lookup) is not None
    for broken in (
        {**payload, "decision_event_id": "decision-that-never-existed"},
        {**payload, "initiator_avatar_id": "war-disciple-2"},
    ):
        forged = Event(
            base_world.month_stamp,
            event.content,
            related_avatars=[
                broken["initiator_avatar_id"],
                broken["target_avatar_id"],
            ],
            related_sects=[2, 1],
            event_type=DELIBERATE_ATTACK_EVENT_TYPE,
            fact_kind=FactKind.OCCURRENCE,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload={"deltas": [], "avatar_aggression": broken},
        )
        forged.causal_links.append(
            CausalLink(
                event_id=forged.id,
                cause_event_id=broken["decision_event_id"],
                relation=CausalRelation.MOTIVATED_BY,
            )
        )
        assert canonical_aggression(forged, lookup=lookup) is None


@pytest.mark.asyncio
async def test_replacing_the_authorizing_holder_invalidates_the_choice(base_world):
    """A new, equally authorized leader did not make the previous choice."""

    _war_world(base_world)
    _aggression(base_world)
    act = _act_on_first(base_world)

    def injected(domain, sect_id, trigger):
        decision = act(domain, sect_id, trigger)
        # The patriarch is replaced by another fully authorized holder while
        # the interpretation is in flight.
        authority = base_world.institutional_authority
        office = authority.office_for_scope(
            sect_institution_id(1), AuthorityScope.FORCE_EMPLOYMENT
        )
        authority.offices[office.id] = replace(
            office,
            id="",
            holder_ref=EntityRef("avatar", "war-disciple-1"),
            holder_since_month=int(base_world.month_stamp),
        )
        return decision

    events = await _run(base_world, injected=injected)

    assert [event for event in events if event.event_type == WAR_DECLARED_EVENT_TYPE] == []
    assert [
        event for event in events if event.event_type == "domain_affordance_blocked"
    ]
    assert not are_sects_at_war(base_world, 1, 2)


def test_an_invented_selection_mutates_nothing(base_world):
    _war_world(base_world)
    event = _aggression(base_world)
    context = war.WarAffordanceContext(
        base_world,
        war.DECLARATION_DOMAIN,
        sect_institution_ref(1),
        event,
        None,
        (),
    )

    with pytest.raises(StaleAffordanceError):
        DOMAIN_AFFORDANCES.execute(context, "aff-does-not-exist")

    assert not are_sects_at_war(base_world, 1, 2)


@pytest.mark.asyncio
async def test_maintaining_declares_no_war(base_world):
    _war_world(base_world)
    _aggression(base_world)

    events = await _run(base_world)

    assert [event for event in events if event.event_type == WAR_DECLARED_EVENT_TYPE] == []
    assert not are_sects_at_war(base_world, 1, 2)


@pytest.mark.asyncio
async def test_losing_force_authority_while_deciding_blocks_the_mutation(base_world):
    """Authority is answered at execution, never trusted from composition."""

    _war_world(base_world)
    aggression = _aggression(base_world)
    act = _act_on_first(base_world)

    def injected(domain, sect_id, trigger):
        decision = act(domain, sect_id, trigger)
        # The office holder dies between choosing and executing.
        _patriarch(base_world, 1).is_dead = True
        return decision

    events = await _run(base_world, injected=injected)

    assert [event for event in events if event.event_type == WAR_DECLARED_EVENT_TYPE] == []
    assert [
        event for event in events if event.event_type == "domain_affordance_blocked"
    ]
    assert not are_sects_at_war(base_world, 1, 2)
    assert war.known_casus_belli(base_world, 1)[0][0] == aggression.id


@pytest.mark.asyncio
async def test_declaration_writes_real_deltas_and_preserves_friendliness(base_world):
    _war_world(base_world)
    aggression = _aggression(base_world)

    events = await _run(base_world, injected=_act_on_first(base_world))

    declared = next(
        event for event in events if event.event_type == WAR_DECLARED_EVENT_TYPE
    )
    assert declared.fact_kind is FactKind.STATE_TRANSITION
    relation = base_world.institutional_relations.get_relation(
        sect_institution_id(1), sect_institution_id(2)
    )
    assert relation.kind is InstitutionalRelationKind.AT_WAR
    # No fixed opinion is injected: friendliness stays owned elsewhere.
    assert relation.friendliness == 0
    aspects = {delta["aspect"] for delta in declared.causal_payload["deltas"]}
    assert {"kind", "since_month", "evidence_event_ids"} <= aspects
    assert declared.causal_payload["casus_belli_event_id"] == aggression.id
    assert any(
        link.relation is CausalRelation.RESPONSE_TO
        and link.cause_event_id == aggression.id
        for link in declared.causal_links
    )
    assert any(
        link.relation is CausalRelation.MOTIVATED_BY for link in declared.causal_links
    )
    # Both belligerents, and only they, are formally notified of their war.
    assert base_world.institutional_knowledge.contains(
        sect_institution_id(1), declared.id
    )
    assert base_world.institutional_knowledge.contains(
        sect_institution_id(2), declared.id
    )


@pytest.mark.asyncio
async def test_a_spent_cause_can_never_restart_the_war_after_peace(base_world):
    """Formal peace cannot be undone by replaying the same historical attack."""

    _war_world(base_world)
    aggression = _aggression(base_world)
    declared_events = await _run(base_world, injected=_act_on_first(base_world))
    declared = next(
        event for event in declared_events if event.event_type == WAR_DECLARED_EVENT_TYPE
    )
    assert base_world.event_manager.commit_step(declared_events)

    conclude_formal_war(
        base_world,
        1,
        2,
        current_month=int(base_world.month_stamp),
        evidence_event_ids=(declared.id,),
    )
    assert not are_sects_at_war(base_world, 1, 2)

    assert war.known_casus_belli(base_world, 1) == []
    replayed = await _run(base_world, injected=_act_on_first(base_world))
    assert replayed == []
    assert not are_sects_at_war(base_world, 1, 2)

    # A genuinely new attack is a new cause and may be acted on again.
    fresh = _aggression(base_world)
    assert fresh.id != aggression.id
    assert fresh.event_type == DELIBERATE_ATTACK_EVENT_TYPE
    assert [cause for cause, _ in war.known_casus_belli(base_world, 1)] == [fresh.id]

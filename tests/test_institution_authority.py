from types import SimpleNamespace

from src.classes.environment.city_state import CityGovernance
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.institution import (
    AuthorityClaim,
    AuthorityClaimStatus,
    AuthorityScope,
    InstitutionalAuthorityState,
    InstitutionalOffice,
    InstitutionKind,
)
from src.classes.mechanical_language import EntityRef
from src.classes.sect_ranks import SectRank
from src.systems.institution_authority import (
    AuthorityDenial,
    can_actor_act_for,
)
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institution_bootstrap import synchronize_institutional_authority


def _avatar(avatar_id: str, *, dead: bool = False, patriarch: bool = False):
    return SimpleNamespace(
        id=avatar_id,
        is_dead=dead,
        sect_rank=SectRank.Patriarch if patriarch else None,
    )


def _world(*, emperor=None, sects=(), controller=("dynasty", "1")):
    city = CityRegion(id=7, name="City", desc="", cors=[(0, 0)])
    city.city_state.governance = CityGovernance(*controller, administrative_capacity=1)
    avatars = {avatar.id: avatar for avatar in ([emperor] if emperor else [])}
    for sect in sects:
        avatars.update({member.id: member for member in sect.members.values()})
    manager = SimpleNamespace(
        avatars=avatars,
        get_avatar=lambda avatar_id: avatars.get(str(avatar_id)),
    )
    dynasty = SimpleNamespace(id=1, current_emperor_id=emperor.id if emperor else None)
    context = SimpleNamespace(get_active_sects=lambda: list(sects))
    return SimpleNamespace(
        month_stamp=12,
        dynasty=dynasty,
        map=SimpleNamespace(regions={7: city}),
        avatar_manager=manager,
        sect_context=context,
        institutional_authority=InstitutionalAuthorityState(),
    )


def test_bootstrap_is_idempotent_and_cities_have_no_office():
    emperor = _avatar("emperor")
    patriarch = _avatar("patriarch", patriarch=True)
    sect = SimpleNamespace(id=3, is_active=True, members={patriarch.id: patriarch})
    world = _world(emperor=emperor, sects=(sect,))

    state = bootstrap_institutional_authority(world)
    first = state.to_dict()
    assert {item.kind for item in state.institutions.values()} == {
        InstitutionKind.DYNASTY,
        InstitutionKind.SECT,
        InstitutionKind.CITY,
    }
    assert (
        len(
            [
                office
                for office in state.offices.values()
                if office.institution_id.endswith(":7")
            ]
        )
        == 0
    )
    assert bootstrap_institutional_authority(world) is state
    assert state.to_dict() == first
    new_emperor = _avatar("emperor-2")
    new_patriarch = _avatar("patriarch-2", patriarch=True)
    world.avatar_manager.avatars.update(
        {"emperor-2": new_emperor, "patriarch-2": new_patriarch}
    )
    world.dynasty.current_emperor_id = "emperor-2"
    patriarch.sect_rank = None
    sect.members[new_patriarch.id] = new_patriarch
    world.month_stamp = 13
    transitions = synchronize_institutional_authority(world)
    assert transitions
    assert state.offices["office:inst:dynasty:1:sovereign"].holder_ref.id == "emperor-2"
    assert state.offices["office:inst:sect:3:patriarch"].holder_ref.id == "patriarch-2"
    assert state.offices["office:inst:dynasty:1:sovereign"].holder_since_month == 13
    world.month_stamp = 14
    world.dynasty.current_emperor_id = "emperor-3"
    emperor_3 = _avatar("emperor-3")
    world.avatar_manager.avatars[emperor_3.id] = emperor_3
    source = Event(world.month_stamp, "succession", related_avatars=["emperor-3"])
    transitions = synchronize_institutional_authority(world, current_events=(source,))
    assert any(
        source.id in {link.cause_event_id for link in event.causal_links}
        for event in transitions
    )
    assert all(event.fact_kind.value == "state_transition" for event in transitions)
    assert all(
        event.causal_payload and event.causal_payload["deltas"] for event in transitions
    )


def test_holder_and_institution_are_authorized_while_claimant_does_not_block():
    emperor = _avatar("emperor")
    world = _world(emperor=emperor)
    state = bootstrap_institutional_authority(world)
    owner = EntityRef("dynasty", "1")
    office = state.offices["office:inst:dynasty:1:sovereign"]
    claim = AuthorityClaim(
        office_id=office.id,
        claimant_ref=EntityRef("avatar", "claimant"),
        opened_month=12,
        status=AuthorityClaimStatus.ACTIVE,
        evidence_event_ids=("event:claim",),
        source_kind="test",
    )
    state.add_claim(claim)

    for actor in (owner, EntityRef("avatar", "emperor")):
        verdict = can_actor_act_for(world, actor, owner, AuthorityScope.RECOGNITION)
        assert verdict.allowed is True
        assert verdict.contesting_claim_ids == (claim.id,)
    denied = can_actor_act_for(
        world, EntityRef("avatar", "claimant"), owner, AuthorityScope.RECOGNITION
    )
    assert denied.allowed is False
    assert denied.denial is AuthorityDenial.ACTOR_NOT_AUTHORIZED


def test_city_authority_follows_city_governance_controller_and_divergence_denies():
    emperor = _avatar("emperor")
    world = _world(emperor=emperor, controller=("dynasty", "1"))
    state = bootstrap_institutional_authority(world)
    city_owner = EntityRef("region", "7")
    for actor in (
        city_owner,
        EntityRef("dynasty", "1"),
        EntityRef("avatar", "emperor"),
    ):
        verdict = can_actor_act_for(
            world, actor, city_owner, AuthorityScope.URBAN_ADMINISTRATION
        )
        assert verdict.allowed is True
        assert verdict.authorizing_institution_id == "inst:dynasty:1"
    world.map.regions[7].city_state.governance = CityGovernance(
        "dynasty", "999", administrative_capacity=1
    )
    denied = can_actor_act_for(
        world,
        EntityRef("dynasty", "1"),
        city_owner,
        AuthorityScope.URBAN_ADMINISTRATION,
    )
    assert denied.allowed is False
    assert denied.denial is AuthorityDenial.MATERIAL_CONTROL_MISSING
    assert state.offices.keys() == {"office:inst:dynasty:1:sovereign"}


def test_dead_or_dissolved_holder_and_claimant_without_office_are_denied():
    emperor = _avatar("emperor")
    world = _world(emperor=emperor)
    state = bootstrap_institutional_authority(world)
    owner = EntityRef("dynasty", "1")
    emperor.is_dead = True
    world.month_stamp = 13
    transitions = synchronize_institutional_authority(world)
    assert transitions
    dead = can_actor_act_for(world, owner, owner, AuthorityScope.RECOGNITION)
    assert dead.denial is AuthorityDenial.HOLDER_MISSING
    world.dynasty.is_active = False
    world.month_stamp = 14
    transitions = synchronize_institutional_authority(world)
    assert transitions
    assert state.institutions["inst:dynasty:1"].dissolved_month == 14
    dissolved = can_actor_act_for(world, owner, owner, AuthorityScope.RECOGNITION)
    assert dissolved.denial is AuthorityDenial.INSTITUTION_INACTIVE
    active_world = _world(emperor=_avatar("emperor"))
    bootstrap_institutional_authority(active_world)
    claimant = can_actor_act_for(
        active_world, EntityRef("avatar", "claimant"), owner, AuthorityScope.RECOGNITION
    )
    assert claimant.denial is AuthorityDenial.ACTOR_NOT_AUTHORIZED
    future_world = _world(emperor=_avatar("emperor"))
    future_state = bootstrap_institutional_authority(future_world)
    office = future_state.offices["office:inst:dynasty:1:sovereign"]
    future_state.replace_office(
        InstitutionalOffice(
            institution_id=office.institution_id,
            office_key=office.office_key,
            scopes=office.scopes,
            holder_ref=office.holder_ref,
            holder_since_month=99,
            id=office.id,
        )
    )
    future = can_actor_act_for(
        future_world, owner, owner, AuthorityScope.RECOGNITION, current_month=12
    )
    assert future.denial is AuthorityDenial.HOLDER_NOT_YET_ACTIVE

"""Faith is an independently chosen affiliation, not race or membership."""

import pytest

from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import validate_history
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.religion import (invitation_options, adherence_options,
    invite_religious_adherence, accept_religious_adherence, adherence_id)
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.settlement_intelligence import observe_present_agent
from tests.test_medieval_rites import decide, totals

ORDER = EntityRef("organization", "ordem-da-aurora")
CULT = EntityRef("organization", "coro-das-cinzas")


def prepared():
    world = create_medieval_world(73, character_count=60)
    residents = [c for c in world.society.characters.values() if c.location_id == "pedraclara"]
    assert len(residents) >= 3
    # Co-located emissaries and seats are explicit scenario premises. No resident
    # gains a belief from these institutional membership assignments.
    for actor, member in ((ORDER, residents[0]), (CULT, residents[1])):
        organization = world.society.organizations[actor.id]
        world.society.organizations[organization.id] = organization.model_copy(update={
            "seat_id": "pedraclara", "member_ids": tuple(sorted(set((*organization.member_ids, member.id))))})
        office = world.authority.offices[f"office:organization:{actor.id}"]
        world.authority.offices[office.id] = office.model_copy(update={
            "holder_ref": EntityRef("character", member.id)})
    refresh_settlement_reports(world)
    observe_present_agent(world, CULT, "pedraclara")
    return world, EntityRef("character", residents[2].id)


def invite(world, organization, recipient):
    option = next(o for o in invitation_options(world, organization) if o.recipient_ref == recipient)
    return invite_religious_adherence(world, organization, option.id, decide(world, option).id)


def join(world, actor, organization):
    notice = invite(world, organization, actor)
    option = next(o for o in adherence_options(world, actor) if o.invitation_id == notice.id)
    return accept_religious_adherence(world, actor, option.id, decide(world, option).id)


def test_two_traditions_allow_independent_choice_and_switch_without_material_gain(tmp_path):
    world, actor = prepared()
    before = totals(world)
    memberships = {key: value.member_ids for key, value in world.society.organizations.items()}
    first = invite(world, ORDER, actor)
    second = invite(world, CULT, actor)
    assert not world.society.religious_adherences
    assert len(adherence_options(world, actor)) == 2
    option = next(o for o in adherence_options(world, actor) if o.invitation_id == second.id)
    decision = decide(world, option)
    affiliation = accept_religious_adherence(world, actor, option.id, decision.id)
    assert affiliation.organization_id == CULT.id
    assert totals(world) == before
    assert {key: value.member_ids for key, value in world.society.organizations.items()} == memberships
    assert not adherence_options(world, EntityRef("character", "character:007"))
    chosen = next(o for o in adherence_options(world, actor) if o.invitation_id == first.id)
    changed = accept_religious_adherence(world, actor, chosen.id, decide(world, chosen).id)
    assert changed.organization_id == ORDER.id
    assert affiliation.last_event_id in {link.cause_event_id for link in world.event_index()[changed.last_event_id].causal_links}
    validate_history(world.events, world.clock.absolute_day)
    from src.server.medieval.queries import society_view
    view = society_view(world)
    assert view.religious_adherences == [changed]
    assert next(o for o in view.organizations if o.id == ORDER.id).doctrine
    path = tmp_path / "faith.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_collective_adherence_does_not_convert_named_residents():
    world, character = prepared()
    group_id = world.society.characters[character.id].population_group_id
    actor = EntityRef("population_group", group_id)
    affiliation = join(world, actor, ORDER)
    assert affiliation.actor_ref == actor
    assert adherence_id(character) not in world.society.religious_adherences


@pytest.mark.parametrize("blocker", ["unknown_id", "expiry", "presence", "other_actor"])
def test_invalid_adherence_has_no_partial_mutation(blocker):
    world, actor = prepared()
    invite(world, ORDER, actor)
    option = adherence_options(world, actor)[0]
    option_id = option.id
    if blocker == "unknown_id":
        option_id += ":invented"
    elif blocker == "expiry":
        world.clock = world.clock.advance(7)
    elif blocker == "presence":
        person = world.society.characters[actor.id]
        world.society.characters[person.id] = person.model_copy(update={"location_id": "ferroalto"})
    decision = decide(world, option)
    if blocker == "other_actor":
        actor = EntityRef("character", "character:007")
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale|unknown"):
        accept_religious_adherence(world, actor, option_id, decision.id)
    assert world_snapshot(world) == before


def test_late_validation_failure_rolls_back_invitation(monkeypatch):
    from src.classes.society.state import SocietyState
    world, actor = prepared()
    option = next(o for o in invitation_options(world, ORDER) if o.recipient_ref == actor)
    decision = decide(world, option)
    before = world_snapshot(world)
    def reject(self, *args, **kwargs):
        raise ValueError("prepared late religious failure")
    with monkeypatch.context() as scoped:
        scoped.setattr(SocietyState, "validate", reject)
        with pytest.raises(ValueError, match="late religious"):
            invite_religious_adherence(world, ORDER, option.id, decision.id)
    assert world_snapshot(world) == before

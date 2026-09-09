"""A sect spends its own treasury only when it really can, and really chose to.

Supporting a member moves `sect.magic_stone`. Before this, the organization
path had no authority gate at all and its executor trusted a decision **id**
rather than the decision fact -- the only collective door without
`validate_actor_decision`. `TREASURY_DISPOSITION` appeared once in the path, in
`organization_interpreter`, and only to pick which office to project into the
prompt: a projection, never a gate.

No material control is required here. A treasury is not territorial, and the
region only says where the member is.
"""

from __future__ import annotations

import pytest

from src.classes.institution import AuthorityScope
from src.classes.mechanical_language import EntityRef
# Importing the module is what registers the collective providers, and this
# suite composes before any interpretation would do it.
import src.systems.collective_affordances  # noqa: F401
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
)
from src.systems.sect_member_support import execute_sect_member_support
from src.systems.institution_authority import can_actor_act_for
from src.systems.organization_interpreter import (
    interpret_organization_transition,
    organization_affordance_context,
)
from tests.test_organization_reactivity_integration import _setup


async def _decision_for(world, sect, region, condition, trigger, option):
    """The sect's own audited decision, built by the real interpreter.

    The interpreter only ever accepts an option it actually composed, so a
    spoof is made by editing the produced decision's own selector rather than
    by asking the interpreter to bless something that was never offered.
    """
    from src.classes.domain_affordance import DomainDecision, DomainDecisionKind

    decision, event = await interpret_organization_transition(
        world, sect, region, condition, trigger,
        injected_decision=DomainDecision(
            DomainDecisionKind.ACT, "The sect supports its own.", option.id
        ),
    )
    assert decision.selected_affordance_id == option.id
    return event


def _respoof(decision_event, affordance_id: str):
    """Point a real decision at another affordance, as a forger would."""
    decision_event.causal_payload["decision"]["chosen_chain"] = [
        {"selected_affordance_id": affordance_id}
    ]
    decision_event.causal_payload["interpretation"]["selected_affordance_id"] = (
        affordance_id
    )
    return decision_event


def _only_option(world, sect, region, condition, trigger):
    context = organization_affordance_context(
        world, sect, region, condition, trigger
    )
    options = DOMAIN_AFFORDANCES.compose(context)
    assert options, "the sect was offered no support"
    return context, options[0]


async def authorized_support(world, sect, region, condition, trigger):
    """A live offer plus the real decision that selected it.

    Shared so other suites can drive the owner honestly instead of calling it
    with hand-made ids.
    """
    context, option = _only_option(world, sect, region, condition, trigger)
    decision_event = await _decision_for(
        world, sect, region, condition, trigger, option
    )
    return context, option, decision_event


def _kill_the_holder(world, sect) -> None:
    """The treasury office loses its living holder."""
    from src.systems.institutional_diplomacy import sect_institution_id

    institution_id = sect_institution_id(str(sect.id))
    office = next(
        item
        for item in world.institutional_authority.offices.values()
        if item.institution_id == institution_id and item.holder_ref is not None
    )
    holder = world.avatar_manager.get_avatar(str(office.holder_ref.id))
    assert holder is not None
    holder.is_dead = True


@pytest.mark.asyncio
async def test_a_sect_with_a_living_treasury_office_may_support(base_world):
    """The baseline the refusals are measured against."""
    sect, avatar, city, trigger, condition = _setup(base_world)
    before = int(sect.magic_stone)

    assert can_actor_act_for(
        base_world,
        EntityRef("sect", str(sect.id)),
        EntityRef("sect", str(sect.id)),
        AuthorityScope.TREASURY_DISPOSITION,
        current_month=int(base_world.month_stamp),
    ).allowed
    context, option = _only_option(base_world, sect, city, condition, trigger)
    decision_event = await _decision_for(
        base_world, sect, city, condition, trigger, option
    )

    event = DOMAIN_AFFORDANCES.execute(
        context, option.id,
        decision_event_id=decision_event.id, decision_event=decision_event,
    )

    assert event.event_type == "sect_member_support_completed"
    assert int(sect.magic_stone) < before
    assert event.causal_payload["affordance_id"] == option.id


@pytest.mark.asyncio
async def test_a_support_outside_the_sect_home_region_is_still_valid(base_world):
    """No material control: the treasury is not territorial.

    The member is in a city the sect does not own, and the support still
    stands -- the region only says where the member is.
    """
    sect, avatar, city, trigger, condition = _setup(base_world)
    # The sect neither governs nor materially controls this city.
    governance = city.city_state.governance
    assert (governance.controller_kind, governance.controller_id) != (
        "sect", str(sect.id)
    )
    assert can_actor_act_for(
        base_world,
        EntityRef("sect", str(sect.id)),
        EntityRef("sect", str(sect.id)),
        AuthorityScope.TREASURY_DISPOSITION,
        current_month=int(base_world.month_stamp),
        require_material_control=True,
        material_target_ref=EntityRef("region", str(city.id)),
    ).material_control_of is None
    assert str(getattr(avatar.tile.region, "id", "")) == str(city.id)
    before = int(sect.magic_stone)

    context, option = _only_option(base_world, sect, city, condition, trigger)
    assert option.parameters["region_id"] == str(city.id)
    decision_event = await _decision_for(
        base_world, sect, city, condition, trigger, option
    )

    DOMAIN_AFFORDANCES.execute(
        context, option.id,
        decision_event_id=decision_event.id, decision_event=decision_event,
    )

    assert int(sect.magic_stone) < before


def _through_registry(context, option, **kwargs):
    return DOMAIN_AFFORDANCES.execute(context, option.id, **kwargs)


def _through_owner(context, option, **kwargs):
    return execute_sect_member_support(context, option, **kwargs)


@pytest.mark.parametrize(
    "call", (_through_registry, _through_owner), ids=("registry", "owner")
)
@pytest.mark.asyncio
async def test_a_forged_or_mismatched_decision_moves_no_treasury(base_world, call):
    """An id is not authorship, and neither is somebody else's decision.

    Run through both doors: the owner has to refuse exactly what the registry
    refuses, or a direct call would be the way around the gate.
    """
    sect, avatar, city, trigger, condition = _setup(base_world)
    before_sect = int(sect.magic_stone)
    before_avatar = int(avatar.magic_stone.value)
    context, option = _only_option(base_world, sect, city, condition, trigger)
    decision_event = await _decision_for(
        base_world, sect, city, condition, trigger, option
    )

    # No decision fact at all: the old executor accepted exactly this.
    with pytest.raises(StaleAffordanceError):
        call(
            context, option,
            decision_event_id=decision_event.id, decision_event=None,
        )
    # A real decision cited under another id.
    with pytest.raises(StaleAffordanceError):
        call(
            context, option,
            decision_event_id="not-this-decision", decision_event=decision_event,
        )
    assert int(sect.magic_stone) == before_sect
    assert int(avatar.magic_stone.value) == before_avatar


@pytest.mark.asyncio
async def test_a_forged_option_is_not_currently_offered(base_world):
    """A well-formed option the provider never composed buys nothing.

    Called on the owner directly: a direct call must be exactly as guarded as
    the dispatched one.
    """
    from dataclasses import replace as dc_replace

    sect, avatar, city, trigger, condition = _setup(base_world)
    before = int(sect.magic_stone)
    context, real = _only_option(base_world, sect, city, condition, trigger)
    forged = dc_replace(
        real, parameters={**dict(real.parameters), "region_id": "999"}, id=""
    )
    assert forged.id != real.id
    # A real decision, then re-pointed at the forged option, as a forger would.
    decision_event = _respoof(
        await _decision_for(base_world, sect, city, condition, trigger, real),
        forged.id,
    )

    with pytest.raises(StaleAffordanceError):
        execute_sect_member_support(
            context, forged,
            decision_event_id=decision_event.id, decision_event=decision_event,
        )
    assert int(sect.magic_stone) == before


@pytest.mark.asyncio
async def test_a_resolved_condition_offers_nothing_to_the_owner(base_world):
    """A context built earlier can carry a grievance that has since resolved."""
    from dataclasses import replace as dc_replace

    sect, avatar, city, trigger, condition = _setup(base_world)
    before = int(sect.magic_stone)
    context, option, decision_event = await authorized_support(
        base_world, sect, city, condition, trigger
    )

    # The pressure really resolves in canonical state.
    base_world.mechanical_language.condition_instances[condition.id] = dc_replace(
        condition,
        resolved_month=int(base_world.month_stamp),
        resolution_event_id=trigger.id,
    )

    assert DOMAIN_AFFORDANCES.compose(context) == ()
    with pytest.raises(StaleAffordanceError):
        execute_sect_member_support(
            context, option,
            decision_event_id=decision_event.id, decision_event=decision_event,
        )
    assert int(sect.magic_stone) == before


@pytest.mark.parametrize(
    "call", (_through_registry, _through_owner), ids=("registry", "owner")
)
@pytest.mark.asyncio
async def test_authority_lost_after_the_offer_blocks_the_spend(base_world, call):
    """Composed, decided, then the office loses its holder: nothing moves."""
    sect, avatar, city, trigger, condition = _setup(base_world)
    before_sect = int(sect.magic_stone)
    before_avatar = int(avatar.magic_stone.value)
    context, option = _only_option(base_world, sect, city, condition, trigger)
    decision_event = await _decision_for(
        base_world, sect, city, condition, trigger, option
    )

    _kill_the_holder(base_world, sect)

    # The menu is empty now, so the very same option is no longer offered.
    assert DOMAIN_AFFORDANCES.compose(context) == ()
    with pytest.raises(StaleAffordanceError):
        call(
            context, option,
            decision_event_id=decision_event.id, decision_event=decision_event,
        )
    assert int(sect.magic_stone) == before_sect
    assert int(avatar.magic_stone.value) == before_avatar


@pytest.mark.asyncio
async def test_a_sect_with_no_registered_holder_is_offered_nothing(base_world):
    """Fail-closed at the provider, before any owner is reached."""
    sect, avatar, city, trigger, condition = _setup(base_world)
    base_world.institutional_authority.offices.clear()

    context = organization_affordance_context(
        base_world, sect, city, condition, trigger
    )
    assert DOMAIN_AFFORDANCES.compose(context) == ()

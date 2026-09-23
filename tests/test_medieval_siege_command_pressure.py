"""A named command changes a siege, exactly as it already changes a battle.

Field resolution has long explained an outcome by preparation, supply, terrain,
fatigue, morale and doctrine. The siege -- the form that actually decides
territory -- read none of it: only force ratio, attacker supply, elapsed days
and the defender's rations. So an institution that appointed a commander and
set a doctrine changed a skirmish and changed nothing where it mattered.

This reads the doctrine through its existing owner and adds no morale, terrain
or table of its own. A column with no current command contributes nothing, so
every authored siege wears exactly as it did before.
"""

import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.medieval.siege_campaign import _command_pressure, _garrison_wear
from src.sim.medieval.force_command import effective_doctrine

from tests.test_medieval_siege_campaign import ATTACKER, begin_siege_campaign, decide, siege_world, tick


def _command(world, detachment_id, doctrine, *, institution=ATTACKER, effective_day=1):
    """Install a current command directly; the command owner is tested elsewhere."""
    from src.classes.governance.models import AuthorityOffice
    from src.classes.society.force import DetachmentCommand

    detachment = world.society.detachments[detachment_id]
    holder = next(item for item in world.society.characters.values()
                  if item.death_day is None and item.location_id == detachment.location_id)
    office = world.authority.offices[f"office:{institution.kind}:{institution.id}"]
    world.authority.offices[office.id] = AuthorityOffice(
        id=office.id, institution_ref=institution, holder_ref=EntityRef("character", holder.id),
        scopes=office.scopes, starts_day=office.starts_day, ends_day=office.ends_day)
    from src.classes.event import FactKind
    from src.sim.medieval.events import record_event

    choice = record_event(
        world, "test_command_decided", "Doutrina escolhida pela instituição.",
        fact_kind=FactKind.DECISION,
        decision={"action": "set_detachment_doctrine", "actor_ref": institution.to_dict(),
                  "detachment_id": detachment_id, "doctrine": doctrine})
    from src.sim.medieval.economy import _delta

    previous = world.society.detachment_commands.get(detachment_id)
    receipt = record_event(
        world, "detachment_doctrine_set", "A doutrina passou a valer para a coluna.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment_command", detachment_id, "doctrine",
                       previous.doctrine if previous else None, doctrine),),
        cause_ids=(choice.id,))
    command = DetachmentCommand(
        id=detachment_id, detachment_id=detachment_id,
        character_id=holder.id, institution_ref=institution, office_id=office.id,
        doctrine=doctrine, doctrine_effective_day=effective_day,
        appointed_day=0, last_event_id=receipt.id)
    world.society.detachment_commands[command.id] = command
    return command


def wear(world, campaign):
    attacker = world.society.detachments[campaign.attacker_detachment_id]
    garrison = world.society.garrisons[campaign.defender_garrison_id]
    defender = world.society.detachments[garrison.detachment_id]
    return _garrison_wear(world, campaign, attacker, defender), attacker, defender


def test_without_a_named_command_the_wear_is_exactly_what_it_was():
    world, attacker_id, garrison_id, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    value, attacker, defender = wear(world, campaign)

    assert effective_doctrine(world, attacker.id) is None
    assert effective_doctrine(world, defender.id) is None
    assert _command_pressure(world, attacker, defender) == 0

    # The historical four-term reading, recomputed here as the reference.
    force_pressure = max(1, min(5, (attacker.count * 4) // max(1, defender.count)))
    supply_pressure = 1 if attacker.provisions >= attacker.count * 2 else 0
    elapsed_pressure = min(2, campaign.progress_days)
    defender_relief = 1 if defender.provisions >= defender.count * 4 else 0
    assert value == max(1, min(7, force_pressure + supply_pressure
                               + elapsed_pressure - defender_relief))


def test_an_attacker_pressing_wears_the_garrison_faster():
    world, attacker_id, garrison_id, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    before, attacker, defender = wear(world, campaign)

    _command(world, attacker.id, "press")
    after, _, _ = wear(world, campaign)
    assert after == before + 1
    assert _command_pressure(world, attacker, defender) == 1

    # Holding is the opposite choice and relieves the defender instead.
    _command(world, attacker.id, "hold")
    assert wear(world, campaign)[0] == before - 1


def test_a_defender_holding_resists_and_pressing_exposes_itself():
    world, attacker_id, garrison_id, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    before, attacker, defender = wear(world, campaign)

    _command(world, defender.id, "hold", institution=EntityRef("polity", defender.owner_ref.id))
    assert wear(world, campaign)[0] == before - 1

    _command(world, defender.id, "press", institution=EntityRef("polity", defender.owner_ref.id))
    assert wear(world, campaign)[0] == before + 1


def test_a_long_deployed_column_cannot_press():
    """Fatigue bites exactly where it is about sustaining effort."""
    from src.systems.time import WorldClock

    world, attacker_id, garrison_id, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    baseline, attacker, defender = wear(world, campaign)
    _command(world, attacker.id, "press")
    assert wear(world, campaign)[0] == baseline + 1

    # The same column, long in the field, no longer gains from pressing.
    world.clock = WorldClock(attacker.started_day + 30)
    attacker = world.society.detachments[attacker.id]
    assert _command_pressure(world, attacker, defender) == 0

    world.clock = WorldClock(attacker.started_day + 90)
    assert _command_pressure(world, attacker, defender) == 0, "a fadiga nunca inverte o sinal"

    # An uncommanded column is untouched by fatigue: this is a command reading.
    world.society.detachment_commands.clear()
    assert _command_pressure(world, attacker, defender) == 0


def test_the_reading_stays_inside_its_bounds_and_never_double_counts_supply():
    world, attacker_id, garrison_id, option = siege_world(defender_count=5, defender_provisions=0)
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    attacker = world.society.detachments[attacker_id]
    defender = world.society.detachments[
        world.society.garrisons[garrison_id].detachment_id]
    _command(world, attacker.id, "press")
    _command(world, defender.id, "press", institution=EntityRef("polity", defender.owner_ref.id))

    saturated = world.society.siege_campaigns[campaign.id].model_copy(update={"progress_days": 9})
    assert _garrison_wear(world, saturated, attacker, defender) == 7

    world, attacker_id, garrison_id, option = siege_world(attacker_count=40, defender_count=60,
                                                          defender_provisions=4000)
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    attacker = world.society.detachments[attacker_id]
    defender = world.society.detachments[world.society.garrisons[garrison_id].detachment_id]
    _command(world, attacker.id, "hold")
    _command(world, defender.id, "hold", institution=EntityRef("polity", defender.owner_ref.id))
    assert _garrison_wear(world, campaign, attacker, defender) == 1

    # Provisions are read once, by the caller; the command term ignores them.
    plenty = world.society.detachments[attacker.id].model_copy(
        update={"provisions": attacker.count * 100})
    assert _command_pressure(world, plenty, defender) == _command_pressure(world, attacker, defender)


def test_a_commanded_siege_still_persists_and_keeps_its_causal_receipt(tmp_path):
    from src.sim.medieval.persistence import load_world, save_world, world_snapshot

    world, attacker_id, garrison_id, option = siege_world(defender_count=60, defender_provisions=400)
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    _command(world, attacker_id, "press")
    for _ in range(2):
        tick(world)

    active = world.society.siege_campaigns[campaign.id]
    assert active.phase == "sieging" and active.progress_days == 2
    progress = next(event for event in reversed(world.events)
                    if event.event_type == "siege_campaign_progressed")
    assert any(delta.aspect == "garrison_endurance" and delta.after == str(active.garrison_endurance)
               for delta in progress.deltas)
    world.society.validate(set(world.map.regions), world)

    path = tmp_path / "commanded-siege.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

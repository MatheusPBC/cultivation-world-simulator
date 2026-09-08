"""Causal coverage for hidden-domain treasure.

The loot rules are untouched here: the same drops, the same prices, the same
automatic equipping and the same RNG. What is asserted is that the mutations
this path already performed are now recorded as canonical evidence -- one
delta per canonical save field that really moved, an engine-owned account of
the loot, and a link back to the opening that this treasure was found in.

Loot is drawn by the world, so the fact is `EXTERNAL_EVENT` and cites no
decision: nobody chose it.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.classes.causal_link import CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.gathering.hidden_domain import HiddenDomain
from src.classes.items.magic_stone import MagicStone
from src.systems.cultivation import Realm


@pytest.fixture
def domain_config():
    return [
        {
            "id": "loot_domain",
            "name": "Loot Domain",
            "desc": "",
            "required_realm": "Qi Refinement",
            "danger_prob": 0.0,   # never injure, so loot is the only fact
            "hp_loss_percent": 0.0,
            "drop_prob": 1.0,     # always drop
            "cd_years": 1,
            "open_prob": 1.0,
        }
    ]


@pytest.fixture
def domain(domain_config):
    with patch.dict("src.utils.df.game_configs", {"hidden_domain": domain_config}):
        instance = HiddenDomain()
        HiddenDomain._domain_states.clear()
        instance._active_domains = instance._load_configs()
        yield instance
        HiddenDomain._domain_states.clear()


@pytest.fixture
def explorer(base_world, dummy_avatar):
    dummy_avatar.cultivation_progress.realm = Realm.Qi_Refinement
    dummy_avatar.weapon = None
    dummy_avatar.auxiliary = None
    dummy_avatar.technique = None
    dummy_avatar.weapon_proficiency = 0.0
    dummy_avatar.magic_stone = MagicStone(0)
    # Registered, not only referenced: the month checkpoint captures the
    # canonical World graph, so an unregistered avatar would never be rolled
    # back and the rollback assertion below would prove nothing.
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.avatar_manager.get_living_avatars = lambda: [dummy_avatar]
    return dummy_avatar


async def _run(domain_instance, base_world, loot):
    with patch.object(HiddenDomain, "_generate_loot", return_value=loot), patch.object(
        HiddenDomain, "_generate_story", return_value=None
    ):
        return await domain_instance.execute(base_world)


def _treasure(events):
    return next(
        event for event in events if event.event_type == "hidden_domain_treasure"
    )


def _opening(events):
    return next(
        event for event in events if event.event_type == "hidden_domain_opened"
    )


def _deltas(event, aspect: str) -> list[dict]:
    return [
        delta
        for delta in event.causal_payload["deltas"]
        if delta["aspect"] == aspect
    ]


@pytest.mark.asyncio
async def test_a_new_weapon_records_its_equipment_and_proficiency_reset(
    domain, base_world, explorer
):
    from src.classes.items.weapon import weapons_by_id

    loot = next(iter(weapons_by_id.values()))
    explorer.weapon_proficiency = 42.0

    events = await _run(domain, base_world, loot)
    event = _treasure(events)

    assert event.causal_origin is CausalOrigin.EXTERNAL_EVENT
    assert event.fact_kind is FactKind.STATE_TRANSITION
    # Loot is drawn by the world; no decision is cited or invented.
    assert "decision" not in event.causal_payload
    assert "decision_source" not in event.causal_payload

    assert explorer.weapon is loot
    weapon_deltas = _deltas(event, "weapon_id")
    assert len(weapon_deltas) == 1
    assert weapon_deltas[0]["before"] is None
    assert weapon_deltas[0]["after"] == str(loot.id)
    assert weapon_deltas[0]["owner_id"] == str(explorer.id)
    assert weapon_deltas[0]["event_id"] == event.id

    # `change_weapon` zeroes proficiency, and that really moved.
    proficiency = _deltas(event, "weapon_proficiency")
    assert len(proficiency) == 1
    assert proficiency[0]["before"] == "42.0"
    assert proficiency[0]["after"] == "0.0"
    assert proficiency[0]["magnitude"] == -42.0
    assert explorer.weapon_proficiency == 0.0

    loot_payload = event.causal_payload["hidden_domain_loot"]
    assert loot_payload["loot_kind"] == "weapon"
    assert loot_payload["loot_id"] == loot.id
    assert loot_payload["replaced_item_id"] is None
    assert loot_payload["resale_amount"] == 0
    assert loot_payload["avatar_id"] == str(explorer.id)
    # The effective probability this draw actually used, not a re-derivation.
    assert loot_payload["drop_prob"] == 1.0
    # Everything in the account is a JSON primitive.
    import json

    assert json.loads(json.dumps(loot_payload)) == loot_payload


@pytest.mark.asyncio
async def test_replacing_a_weapon_records_the_actual_resale(
    domain, base_world, explorer
):
    from src.classes.items.weapon import weapons_by_id
    from src.classes.prices import prices

    stock = list(weapons_by_id.values())
    old, loot = stock[0], stock[1]
    explorer.weapon = old
    resale = prices.get_selling_price(old, explorer)

    events = await _run(domain, base_world, loot)
    event = _treasure(events)

    stones = _deltas(event, "magic_stone")
    assert len(stones) == 1
    assert stones[0]["before"] == "0"
    assert stones[0]["after"] == str(resale)
    assert stones[0]["magnitude"] == float(resale)
    assert explorer.magic_stone.value == resale

    loot_payload = event.causal_payload["hidden_domain_loot"]
    assert loot_payload["replaced_item_id"] == old.id
    assert loot_payload["resale_amount"] == resale
    assert _deltas(event, "weapon_id")[0]["before"] == str(old.id)


@pytest.mark.asyncio
async def test_finding_the_same_weapon_records_no_equipment_change(
    domain, base_world, explorer
):
    """Re-equipping the same ID moves no equipment, but still resets skill."""
    from src.classes.items.weapon import weapons_by_id

    loot = next(iter(weapons_by_id.values()))
    explorer.weapon = loot
    explorer.weapon_proficiency = 30.0

    events = await _run(domain, base_world, loot)
    event = _treasure(events)

    assert _deltas(event, "weapon_id") == []
    proficiency = _deltas(event, "weapon_proficiency")
    assert len(proficiency) == 1
    assert proficiency[0]["before"] == "30.0"
    assert proficiency[0]["after"] == "0.0"
    # The existing resale semantics are preserved, not corrected here.
    assert event.causal_payload["hidden_domain_loot"]["replaced_item_id"] == loot.id


@pytest.mark.parametrize("has_old", [False, True])
@pytest.mark.asyncio
async def test_an_auxiliary_records_its_own_field_and_only_resells_a_real_old(
    domain, base_world, explorer, has_old
):
    from src.classes.items.auxiliary import auxiliaries_by_id
    from src.classes.prices import prices

    stock = list(auxiliaries_by_id.values())
    loot = stock[0]
    old = None
    if has_old:
        old = stock[1]
        loot = stock[0]
        explorer.auxiliary = old
    resale = prices.get_selling_price(old, explorer) if old else 0

    events = await _run(domain, base_world, loot)
    event = _treasure(events)

    auxiliary = _deltas(event, "auxiliary_id")
    assert len(auxiliary) == 1
    assert auxiliary[0]["before"] == (str(old.id) if old else None)
    assert auxiliary[0]["after"] == str(loot.id)
    assert explorer.auxiliary is loot
    # An auxiliary touches no weapon field.
    assert _deltas(event, "weapon_id") == []
    assert _deltas(event, "weapon_proficiency") == []

    payload = event.causal_payload["hidden_domain_loot"]
    assert payload["loot_kind"] == "auxiliary"
    assert payload["replaced_item_id"] == (old.id if old else None)
    assert payload["resale_amount"] == resale
    assert explorer.magic_stone.value == resale
    stones = _deltas(event, "magic_stone")
    assert len(stones) == (1 if resale else 0)


@pytest.mark.asyncio
async def test_a_technique_records_its_own_field_and_never_resells(
    domain, base_world, explorer
):
    from src.classes.technique import techniques_by_id

    previous, loot = list(techniques_by_id.values())[:2]
    explorer.technique = previous

    events = await _run(domain, base_world, loot)
    event = _treasure(events)

    technique = _deltas(event, "technique_id")
    assert len(technique) == 1
    assert technique[0]["before"] == str(previous.id)
    assert technique[0]["after"] == str(loot.id)
    assert explorer.technique is loot
    # Learning a technique sells nothing: existing semantics preserved.
    assert _deltas(event, "magic_stone") == []
    payload = event.causal_payload["hidden_domain_loot"]
    assert payload["loot_kind"] == "technique"
    assert payload["replaced_item_id"] is None
    assert payload["resale_amount"] == 0


@pytest.mark.asyncio
async def test_the_treasure_points_back_at_the_real_opening(
    domain, base_world, explorer
):
    from src.classes.items.weapon import weapons_by_id

    events = await _run(domain, base_world, next(iter(weapons_by_id.values())))
    event = _treasure(events)
    opening = _opening(events)

    assert [
        (link.cause_event_id, link.relation) for link in event.causal_links
    ] == [(opening.id, CausalRelation.ENABLED_BY)]
    # The cause is a real fact of this same run, not a fabricated id.
    assert opening.event_type == "hidden_domain_opened"
    assert str(explorer.id) in (opening.related_avatars or [])


@pytest.mark.asyncio
async def test_losing_max_hp_to_new_gear_records_a_real_hp_change(
    domain, base_world, explorer
):
    """Equipping recalculates effects, and that can clamp current HP down.

    Losing maximum HP is not an injury, so this is recorded as an ordinary
    `hp` transition on the same loot fact rather than routed through the
    injury owner.
    """
    from copy import deepcopy

    from src.classes.items.auxiliary import auxiliaries_by_id

    stock = list(auxiliaries_by_id.values())
    generous = deepcopy(stock[0])
    generous.effects = {"extra_max_hp": 50}
    plain = deepcopy(stock[1])
    plain.effects = {}

    explorer.auxiliary = generous
    explorer.recalc_effects()
    explorer.hp.cur = explorer.hp.max
    before_hp = int(explorer.hp.cur)
    assert before_hp > 0

    events = await _run(domain, base_world, plain)
    event = _treasure(events)

    hp_deltas = _deltas(event, "hp")
    assert len(hp_deltas) == 1
    assert hp_deltas[0]["before"] == str(before_hp)
    assert hp_deltas[0]["after"] == str(int(explorer.hp.cur))
    assert hp_deltas[0]["magnitude"] == float(int(explorer.hp.cur) - before_hp)
    assert int(explorer.hp.cur) == before_hp - 50
    # The gear change itself is still recorded on the same fact.
    assert _deltas(event, "auxiliary_id")[0]["after"] == str(plain.id)


@pytest.mark.asyncio
async def test_finding_the_same_technique_changes_nothing_at_all(
    domain, base_world, explorer
):
    """A true no-op: same ID, no equipment setter, no field moves."""
    from src.classes.technique import techniques_by_id

    loot = next(iter(techniques_by_id.values()))
    explorer.technique = loot
    explorer.weapon_proficiency = 12.0

    events = await _run(domain, base_world, loot)
    event = _treasure(events)

    assert event.causal_payload["deltas"] == []
    assert event.fact_kind is FactKind.OCCURRENCE
    assert explorer.technique is loot
    assert explorer.weapon_proficiency == 12.0
    assert explorer.magic_stone.value == 0
    # It is still a fact that the treasure was found.
    assert event.causal_payload["hidden_domain_loot"]["loot_id"] == loot.id


@pytest.mark.asyncio
async def test_the_stored_treasure_still_navigates_back_to_its_opening(
    domain, base_world, explorer, tmp_path
):
    from src.classes.event_storage import EventStorage
    from src.classes.items.weapon import weapons_by_id

    events = await _run(domain, base_world, next(iter(weapons_by_id.values())))
    event = _treasure(events)
    opening = _opening(events)

    storage = EventStorage(tmp_path / "events.db")
    try:
        # The cause is stored too, so the chain is navigable and not dangling.
        assert storage.add_event(opening) is True
        assert storage.add_event(event) is True
        restored = storage.get_event_by_id(event.id)
        links = storage.get_causal_links_for_event(event.id)
        restored_opening = storage.get_event_by_id(opening.id)
    finally:
        storage.close()

    assert restored is not None
    assert restored.event_type == "hidden_domain_treasure"
    assert restored.fact_kind is event.fact_kind
    assert restored.causal_origin is CausalOrigin.EXTERNAL_EVENT
    assert restored.causal_payload["deltas"] == event.causal_payload["deltas"]
    assert (
        restored.causal_payload["hidden_domain_loot"]
        == event.causal_payload["hidden_domain_loot"]
    )

    assert [
        (link.cause_event_id, link.relation) for link in links
    ] == [(opening.id, CausalRelation.ENABLED_BY)]
    assert restored_opening is not None
    assert restored_opening.event_type == "hidden_domain_opened"


@pytest.mark.asyncio
async def test_a_failed_month_rolls_back_everything_the_loot_moved(
    domain, base_world, explorer, monkeypatch
):
    """The real month transaction, failed at persistence, restores the owners."""
    from src.classes.items.weapon import weapons_by_id
    from src.sim.simulator import Simulator
    from src.sim.simulator_engine.finalizer import EventPersistenceError, finalize_step
    from src.sim.simulator_engine.phase_registry import SimulationPhase
    from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner

    import random

    stock = list(weapons_by_id.values())
    explorer.weapon = stock[0]
    explorer.weapon_proficiency = 55.0
    before_month = base_world.month_stamp
    before_events = len(base_world.event_manager.get_recent_events(limit=1000))
    # The loot path draws twice for real here; the rollback must restore the
    # RNG as well, or a retried month would not replay the same world.
    random.seed(20260906)
    before_random_state = random.getstate()

    async def loot_phase(simulator, ctx):
        ctx.add_events(await _run(domain, simulator.world, stock[1]))

    def commit(_simulator, ctx):
        return finalize_step(ctx)

    phases = (
        SimulationPhase("loot", 1, "loot", loot_phase),
        SimulationPhase(
            "finalize_step", 2, "finalize_step", commit, reset_check_after=False
        ),
    )
    monkeypatch.setattr(
        base_world.event_manager, "commit_step", lambda _events, _chapter: False
    )

    with pytest.raises(EventPersistenceError):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert explorer.weapon.id == stock[0].id
    assert explorer.weapon_proficiency == 55.0
    assert explorer.magic_stone.value == 0
    assert base_world.month_stamp == before_month
    assert len(base_world.event_manager.get_recent_events(limit=1000)) == (
        before_events
    )
    assert random.getstate() == before_random_state

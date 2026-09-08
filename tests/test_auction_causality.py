"""Causal coverage for auction bidding and settlement.

Pricing, second-price, tie ordering, auto-equipping and refunds are unchanged.
What is asserted is that the choice is a validated, audited actor decision and
that every mutation the settlement performs is recorded against its real owner.
"""

from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.causal_link import CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.gathering.auction import Auction, AuctionLot
from src.classes.items.magic_stone import MagicStone


@pytest.fixture(autouse=True)
def no_provider(monkeypatch):
    """Any provider call is a failure, and a swallowed one is caught too.

    The auction gathers answers with `return_exceptions=True`, so raising is
    not enough on its own: the assertion after the yield is what proves the
    provider was truly never reached.
    """
    provider = AsyncMock(side_effect=AssertionError("no provider call allowed"))
    monkeypatch.setattr(
        "src.classes.gathering.auction.call_llm_with_template", provider
    )
    yield provider
    provider.assert_not_awaited()
    provider.assert_not_called()


@pytest.fixture
def bidder(base_world, dummy_avatar, mock_item_data):
    dummy_avatar.magic_stone = MagicStone(1000)
    dummy_avatar.weapon = None
    dummy_avatar.auxiliary = None
    base_world.avatar_manager.avatars[dummy_avatar.id] = dummy_avatar
    return dummy_avatar


def _lot(item, bucket: str, index: int) -> AuctionLot:
    return AuctionLot(key=f"{bucket}#{index}", bucket=bucket, index=index, item=item)


def _clone_avatar(world, template, new_id: str):
    """A second registered actor that deliberately shares the display name."""
    import copy

    clone = copy.copy(template)
    clone.id = new_id
    clone.magic_stone = MagicStone(int(template.magic_stone))
    clone.weapon = None
    clone.auxiliary = None
    clone.is_dead = False
    return clone


def _selection(avatar, levels: dict, source: str = "llm") -> dict:
    return {
        str(avatar.id): {
            "source": source,
            "levels": dict(levels),
            "rejected_lot_keys": [],
            "offered_balance": int(avatar.magic_stone),
        }
    }


async def _execute(auction, world, avatar, selections):
    auction.get_related_avatars = lambda _world: [avatar.id]

    async def collect(_world, _avatars, _lots):
        return selections

    auction.collect_bid_preferences = collect
    auction._generate_story = AsyncMock(return_value=[])
    return await auction.execute(world)


@pytest.mark.parametrize(
    "bad_level", [True, False, 2.0, 1.9, "3", None, 0, 6, 99, -1]
)
def test_only_engine_enumerated_levels_are_accepted(bad_level):
    """A level outside the offered set is not a weaker preference."""
    assert Auction._validated_need_level(bad_level) is None


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_every_offered_level_is_accepted(level):
    assert Auction._validated_need_level(level) == level


@pytest.mark.asyncio
async def test_malformed_answers_leave_the_whole_auction_untouched(
    base_world, bidder, mock_item_data, monkeypatch
):
    """The full run, not just the parser: nothing settles and nothing moves."""
    auction = Auction()
    item = mock_item_data["obj_weapon"]
    base_world.circulation.sold_weapons = [item]
    lots = auction.enumerate_lots(base_world)

    # Every value is unsupported: a quoted number, a float, a bool, out of
    # range, and a lot key that was never offered.
    llm = AsyncMock(return_value={
        lots[0].key: "5", "weapon#9": 4, "x": 2.0, "y": True, "z": 7,
    })
    monkeypatch.setattr(
        "src.classes.gathering.auction.call_llm_with_template", llm
    )
    auction.get_related_avatars = lambda _world: [bidder.id]
    auction._generate_story = AsyncMock(return_value=[])

    with patch("src.classes.prices.prices.get_price", return_value=100):
        events = await auction.execute(base_world)

    assert [e for e in events if e.event_type == "auction_settled"] == []
    assert [e for e in events if e.event_type == "auction_lot_unsold"] == []
    decision = next(e for e in events if e.event_type == "auction_bid_decision")
    assert decision.causal_payload["decision"]["chosen_chain"] == []
    assert decision.causal_payload["auction_bid_selection"]["rejected_lot_keys"]
    # Nothing bid, nothing destroyed, nothing spent.
    assert any(x is item for x in base_world.circulation.sold_weapons)
    assert bidder.magic_stone.value == 1000
    assert bidder.weapon is None


@pytest.mark.parametrize("via", ["run_config", "context_var"])
@pytest.mark.asyncio
async def test_test_mode_abstains_through_a_full_run(
    base_world, bidder, mock_item_data, no_provider, via
):
    from src.utils.llm.runtime_mode import llm_test_mode_scope

    auction = Auction()
    item = mock_item_data["obj_weapon"]
    base_world.circulation.sold_weapons = [item]
    auction.get_related_avatars = lambda _world: [bidder.id]
    auction._generate_story = AsyncMock(return_value=[])

    if via == "run_config":
        base_world.run_config_snapshot = {"test_mode": True}
        scope = nullcontext()
    else:
        base_world.run_config_snapshot = {}
        scope = llm_test_mode_scope(True)

    with scope, patch("src.classes.prices.prices.get_price", return_value=100):
        events = await auction.execute(base_world)

    decision = next(e for e in events if e.event_type == "auction_bid_decision")
    # Provenance is the existing fallback source; why is evidence.
    assert decision.causal_payload["decision"]["source"] == "fallback"
    assert decision.causal_origin is CausalOrigin.DETERMINISTIC
    assert (
        decision.causal_payload["auction_bid_selection"]["fallback_reason"]
        == "test_mode"
    )
    assert [e for e in events if e.event_type == "auction_settled"] == []
    assert any(x is item for x in base_world.circulation.sold_weapons)
    assert bidder.magic_stone.value == 1000


@pytest.mark.asyncio
async def test_two_actors_are_asked_separately_and_set_the_second_price(
    base_world, dummy_avatar, mock_item_data, monkeypatch
):
    """One call and one context per actor ID, even with identical names."""
    from src.classes.items.magic_stone import MagicStone as _MS

    auction = Auction()
    item = mock_item_data["obj_weapon"]
    base_world.circulation.sold_weapons = [item]

    first = dummy_avatar
    first.magic_stone, first.weapon, first.auxiliary = _MS(1000), None, None
    first.name = "Twin"
    second = _clone_avatar(base_world, first, "twin-2")
    base_world.avatar_manager.avatars[first.id] = first
    base_world.avatar_manager.avatars[second.id] = second

    lots = auction.enumerate_lots(base_world)
    key = lots[0].key
    seen_ids = []

    async def fake_llm(*, template_path, infos):
        seen_ids.append(infos["avatar_id"])
        # High need for the first actor, low for the second.
        return {key: 4 if infos["avatar_id"] == str(first.id) else 2}

    monkeypatch.setattr(
        "src.classes.gathering.auction.call_llm_with_template", fake_llm
    )
    auction.get_related_avatars = lambda _world: [first.id, second.id]
    auction._generate_story = AsyncMock(return_value=[])

    with patch("src.classes.prices.prices.get_price", return_value=100):
        events = await auction.execute(base_world)

    # Asked once each, addressed by ID, never merged by display name.
    assert sorted(seen_ids) == sorted([str(first.id), str(second.id)])
    decisions = {
        e.related_avatars[0]: e
        for e in events if e.event_type == "auction_bid_decision"
    }
    assert set(decisions) == {first.id, second.id}

    settlement = next(e for e in events if e.event_type == "auction_settled")
    payload = settlement.causal_payload["auction_settlement"]
    # 4 -> 300, 2 -> 80; second price is 80 + 1.
    assert payload["price_paid"] == 81
    assert payload["winner_avatar_id"] == str(first.id)
    assert payload["runner_up_avatar_id"] == str(second.id)
    assert payload["bidder_avatar_ids"] == [str(first.id), str(second.id)]

    links = {(link.cause_event_id, link.relation) for link in settlement.causal_links}
    assert (decisions[first.id].id, CausalRelation.MOTIVATED_BY) in links
    # The runner-up caused the price without having motivated the purchase.
    assert (decisions[second.id].id, CausalRelation.CONTRIBUTED_TO) in links


@pytest.mark.asyncio
async def test_a_runner_up_that_goes_stale_cannot_set_the_price(
    base_world, dummy_avatar, mock_item_data, monkeypatch
):
    from src.classes.items.magic_stone import MagicStone as _MS

    auction = Auction()
    item = mock_item_data["obj_weapon"]
    base_world.circulation.sold_weapons = [item]

    first = dummy_avatar
    first.magic_stone, first.weapon, first.auxiliary = _MS(1000), None, None
    second = _clone_avatar(base_world, first, "stale-runner-up")
    base_world.avatar_manager.avatars[first.id] = first
    base_world.avatar_manager.avatars[second.id] = second
    key = auction.enumerate_lots(base_world)[0].key

    async def fake_llm(*, template_path, infos):
        return {key: 4 if infos["avatar_id"] == str(first.id) else 2}

    monkeypatch.setattr(
        "src.classes.gathering.auction.call_llm_with_template", fake_llm
    )
    original_collect = auction.collect_bid_preferences

    async def collect(world, avatars, lots):
        selections = await original_collect(world, avatars, lots)
        second.is_dead = True  # dies after answering
        return selections

    auction.collect_bid_preferences = collect
    auction.get_related_avatars = lambda _world: [first.id, second.id]
    auction._generate_story = AsyncMock(return_value=[])

    with patch("src.classes.prices.prices.get_price", return_value=100):
        events = await auction.execute(base_world)

    settlement = next(e for e in events if e.event_type == "auction_settled")
    payload = settlement.causal_payload["auction_settlement"]
    # The stale bidder set no price: uncontested deal at 60% of 300.
    assert payload["runner_up_avatar_id"] is None
    assert payload["price_paid"] == 180
    assert payload["bidder_avatar_ids"] == [str(first.id)]
    # Its receipt still exists; only its bid was excluded.
    assert any(
        e.event_type == "auction_bid_decision" and second.id in (e.related_avatars or [])
        for e in events
    )


@pytest.mark.asyncio
async def test_a_settled_lot_records_its_owners_and_cites_its_decision(
    base_world, bidder, mock_item_data, no_provider
):
    auction = Auction()
    item = mock_item_data["obj_weapon"]
    base_world.circulation.sold_weapons = [item]
    lots = auction.enumerate_lots(base_world)
    selections = _selection(bidder, {lots[0].key: 4})

    with patch("src.classes.prices.prices.get_price", return_value=100):
        events = await _execute(auction, base_world, bidder, selections)

    decision = next(e for e in events if e.event_type == "auction_bid_decision")
    assert decision.fact_kind is FactKind.DECISION
    assert decision.causal_origin is CausalOrigin.LLM_INTERPRETATION
    assert decision.causal_payload["decision"]["source"] == "llm"
    assert decision.causal_payload["decision"]["chosen_chain"] == [{
        "action_name": "auction_bid_preference",
        "params": {"lot_key": lots[0].key, "item_id": item.id, "need_level": 4},
    }]

    settlement = next(e for e in events if e.event_type == "auction_settled")
    assert settlement.causal_origin is CausalOrigin.ACTOR_DECISION
    assert settlement.fact_kind is FactKind.STATE_TRANSITION
    assert any(
        link.cause_event_id == decision.id
        and link.relation is CausalRelation.MOTIVATED_BY
        for link in settlement.causal_links
    )

    aspects = {d["aspect"]: d for d in settlement.causal_payload["deltas"]}
    assert aspects["weapon_id"]["after"] == str(item.id)
    assert aspects["magic_stone"]["before"] == "1000"
    assert aspects["weapon_count"]["owner_kind"] == "circulation"
    assert aspects["weapon_count"]["after"] == "0"
    assert bidder.weapon is item
    assert not any(x is item for x in base_world.circulation.sold_weapons)

    payload = settlement.causal_payload["auction_settlement"]
    assert payload["lot_key"] == lots[0].key
    assert payload["winner_avatar_id"] == str(bidder.id)
    assert payload["bidder_avatar_ids"] == [str(bidder.id)]
    assert payload["price_paid"] == aspects["magic_stone"]["magnitude"] * -1


@pytest.mark.asyncio
async def test_duplicate_catalog_ids_are_separate_lots(
    base_world, bidder, mock_item_data, no_provider
):
    """Two circulating copies of one item are two lots, and only one sells."""
    auction = Auction()
    original = mock_item_data["obj_weapon"]
    first, second = original.instantiate(), original.instantiate()
    base_world.circulation.sold_weapons = [first, second]

    lots = auction.enumerate_lots(base_world)
    assert [lot.key for lot in lots] == ["weapon#0", "weapon#1"]
    assert lots[0].item_id == lots[1].item_id
    assert lots[0].item is first and lots[1].item is second

    selections = _selection(bidder, {"weapon#1": 4})
    with patch("src.classes.prices.prices.get_price", return_value=100):
        events = await _execute(auction, base_world, bidder, selections)

    settlement = next(e for e in events if e.event_type == "auction_settled")
    assert settlement.causal_payload["auction_settlement"]["lot_key"] == "weapon#1"
    # The exact instance chosen left; its twin stayed.
    assert not any(x is second for x in base_world.circulation.sold_weapons)
    assert any(x is first for x in base_world.circulation.sold_weapons)


@pytest.mark.asyncio
async def test_a_stale_first_lot_does_not_depress_later_lots(
    base_world, bidder, mock_item_data, no_provider
):
    """A lot that left circulation must not spend a hypothetical budget."""
    auction = Auction()
    original = mock_item_data["obj_weapon"]
    first, second = original.instantiate(), original.instantiate()
    base_world.circulation.sold_weapons = [first, second]
    selections = _selection(bidder, {"weapon#0": 5, "weapon#1": 5})

    async def collect(_world, _avatars, _lots):
        # The first lot disappears after the answer was given.
        base_world.circulation.sold_weapons = [second]
        return selections

    auction.get_related_avatars = lambda _world: [bidder.id]
    auction.collect_bid_preferences = collect
    auction._generate_story = AsyncMock(return_value=[])

    with patch("src.classes.prices.prices.get_price", return_value=100):
        events = await auction.execute(base_world)

    settlements = [e for e in events if e.event_type == "auction_settled"]
    assert len(settlements) == 1
    payload = settlements[0].causal_payload["auction_settlement"]
    assert payload["lot_key"] == "weapon#1"
    # All-in on a full wallet: 1000 bid, uncontested deal at 60%.
    assert payload["price_paid"] == 600
    assert bidder.magic_stone.value == 1000 - 600


@pytest.mark.asyncio
async def test_a_changed_balance_after_the_offer_cancels_the_bid(
    base_world, bidder, mock_item_data, no_provider
):
    """The ceilings were shown at a balance; spending beyond them is refused."""
    auction = Auction()
    item = mock_item_data["obj_weapon"]
    base_world.circulation.sold_weapons = [item]
    lots = auction.enumerate_lots(base_world)
    selections = _selection(bidder, {lots[0].key: 5})

    async def collect(_world, _avatars, _lots):
        bidder.magic_stone = MagicStone(10)  # no longer the offered terms
        return selections

    auction.get_related_avatars = lambda _world: [bidder.id]
    auction.collect_bid_preferences = collect
    auction._generate_story = AsyncMock(return_value=[])

    with patch("src.classes.prices.prices.get_price", return_value=100):
        events = await auction.execute(base_world)

    assert [e for e in events if e.event_type == "auction_settled"] == []
    assert bidder.magic_stone.value == 10
    assert any(x is item for x in base_world.circulation.sold_weapons)
    # The receipt survives; only the bid was refused.
    assert any(e.event_type == "auction_bid_decision" for e in events)


@pytest.mark.asyncio
async def test_a_failed_elixir_is_paid_for_and_says_so(
    base_world, bidder, mock_item_data, no_provider
):
    """Existing payment and removal are preserved; no phantom benefit."""
    auction = Auction()
    elixir = mock_item_data["obj_elixir"]
    base_world.circulation.sold_elixirs = [elixir]
    lots = auction.enumerate_lots(base_world)
    selections = _selection(bidder, {lots[0].key: 4})
    bidder.consume_elixir = lambda _item: False

    with patch("src.classes.prices.prices.get_price", return_value=100):
        events = await _execute(auction, base_world, bidder, selections)

    settlement = next(e for e in events if e.event_type == "auction_settled")
    payload = settlement.causal_payload["auction_settlement"]
    assert payload["elixir_consumed"] is False
    aspects = {d["aspect"] for d in settlement.causal_payload["deltas"]}
    assert "magic_stone" in aspects
    # Nothing was gained: no elixir delta is recorded.
    assert "consumed_elixirs" not in aspects
    assert not any(x is elixir for x in base_world.circulation.sold_elixirs)


@pytest.mark.asyncio
async def test_the_settlement_and_its_decision_survive_sqlite(
    base_world, bidder, mock_item_data, no_provider, tmp_path
):
    from src.classes.event_storage import EventStorage

    auction = Auction()
    base_world.circulation.sold_weapons = [mock_item_data["obj_weapon"]]
    lots = auction.enumerate_lots(base_world)
    selections = _selection(bidder, {lots[0].key: 4})

    with patch("src.classes.prices.prices.get_price", return_value=100):
        events = await _execute(auction, base_world, bidder, selections)

    decision = next(e for e in events if e.event_type == "auction_bid_decision")
    settlement = next(e for e in events if e.event_type == "auction_settled")

    storage = EventStorage(tmp_path / "events.db")
    try:
        assert storage.add_event(decision) is True
        assert storage.add_event(settlement) is True
        restored = storage.get_event_by_id(settlement.id)
        links = storage.get_causal_links_for_event(settlement.id)
    finally:
        storage.close()

    assert restored.causal_payload["deltas"] == settlement.causal_payload["deltas"]
    assert (
        restored.causal_payload["auction_settlement"]
        == settlement.causal_payload["auction_settlement"]
    )
    assert decision.id in {link.cause_event_id for link in links}


@pytest.mark.asyncio
async def test_a_failed_month_rolls_the_whole_auction_back(
    base_world, bidder, mock_item_data, no_provider, monkeypatch
):
    import random

    from src.sim.simulator import Simulator
    from src.sim.simulator_engine.finalizer import EventPersistenceError, finalize_step
    from src.sim.simulator_engine.phase_registry import SimulationPhase
    from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner

    auction = Auction()
    item = mock_item_data["obj_weapon"]
    base_world.circulation.sold_weapons = [item]
    lots = auction.enumerate_lots(base_world)
    selections = _selection(bidder, {lots[0].key: 4})
    before_month = base_world.month_stamp
    random.seed(20260906)
    before_random = random.getstate()

    async def auction_phase(simulator, ctx):
        with patch("src.classes.prices.prices.get_price", return_value=100):
            ctx.add_events(
                await _execute(auction, simulator.world, bidder, selections)
            )

    phases = (
        SimulationPhase("auction", 1, "auction", auction_phase),
        SimulationPhase(
            "finalize_step", 2, "finalize_step",
            lambda _sim, ctx: finalize_step(ctx), reset_check_after=False,
        ),
    )
    monkeypatch.setattr(
        base_world.event_manager, "commit_step", lambda _events, _chapter: False
    )

    with pytest.raises(EventPersistenceError):
        await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert bidder.magic_stone.value == 1000
    assert bidder.weapon is None
    assert len(base_world.circulation.sold_weapons) == 1
    assert base_world.month_stamp == before_month
    assert random.getstate() == before_random
    no_provider.assert_not_awaited()

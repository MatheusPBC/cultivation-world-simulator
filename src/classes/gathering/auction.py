from typing import Any, List, Dict, TYPE_CHECKING
from dataclasses import dataclass
import asyncio
from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.gathering.gathering import Gathering, register_gathering
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.systems.single_choice.models import ChoiceSource
from src.classes.story_event_service import StoryEventService
from src.classes.relation.relation_delta_service import (
    RelationDeltaService,
    RelationshipValence,
)
from src.utils.config import CONFIG
from src.utils.llm.client import call_llm_with_template
from src.utils.llm.runtime_mode import is_test_mode_enabled, is_world_test_mode

if TYPE_CHECKING:
    from src.classes.core.world import World
    from src.classes.core.avatar import Avatar
    from src.classes.items.item import Item

# The only need levels the engine's own bidding policy defines. A preference
# outside this set is not a weaker preference, it is not a preference at all.
OFFERED_NEED_LEVELS = (1, 2, 3, 4, 5)
BID_PREFERENCE_LABEL = "auction_bid_preference"
DECISION_EVENT_TYPE = "auction_bid_decision"
SETTLEMENT_EVENT_TYPE = "auction_settled"
UNSOLD_EVENT_TYPE = "auction_lot_unsold"


@dataclass(frozen=True)
class AuctionLot:
    """One circulating instance on offer, identified for this auction only.

    A catalog ID is not a lot identity: circulation holds independent
    instances and two of them can share an ID and compare equal, so items
    cannot key a mapping. ``key`` is the offered position, transient for this
    auction, and never persisted or registered anywhere.
    """

    key: str
    bucket: str
    index: int
    item: Any

    @property
    def item_id(self) -> Any:
        return self.item.id


@register_gathering
class Auction(Gathering):
    """
    拍卖会事件
    """
    
    # 类变量 - LLM Prompt
    STORY_PROMPT_ID = "auction_story_prompt"
    
    @classmethod
    def get_story_prompt(cls) -> str:
        """获取故事生成提示词"""
        from src.i18n import t
        return t(cls.STORY_PROMPT_ID)
    
    def is_start(self, world: "World") -> bool:
        """
        检测拍卖会是否开始
        条件：后台积攒的 sold_item_count 到达配置阈值
        """
        threshold = CONFIG.world.gathering.auction_trigger_count
        return world.circulation.sold_item_count >= threshold

    def get_related_avatars(self, world: "World") -> List[int]:
        """
        所有存活且允许参加聚会的 avatar 都参与
        """
        return [
            avatar.id 
            for avatar in world.avatar_manager.get_living_avatars()
            if self._can_avatar_join(avatar)
        ]

    def get_info(self, world: "World") -> str:
        from src.i18n import t
        return t("Auction is in progress...")

    def enumerate_lots(self, world: "World") -> List[AuctionLot]:
        """Every circulating instance on offer, in a stable offered order."""
        circulation = world.circulation
        lots: List[AuctionLot] = []
        for bucket, pool in (
            ("weapon", circulation.sold_weapons),
            ("auxiliary", circulation.sold_auxiliaries),
            ("elixir", circulation.sold_elixirs),
        ):
            for index, item in enumerate(pool):
                lots.append(AuctionLot(
                    key=f"{bucket}#{index}", bucket=bucket, index=index, item=item,
                ))
        return lots

    @staticmethod
    def _validated_need_level(raw: Any) -> int | None:
        """The offered level this answer actually selected, or nothing.

        Strict on purpose: a bool, a float, a numeric string and an
        out-of-range number are all rejected rather than coerced. Silently
        turning `7` or `"5"` into an all-in bid would let an unvalidated
        answer spend a wallet.
        """
        if isinstance(raw, bool) or not isinstance(raw, int):
            return None
        return raw if raw in OFFERED_NEED_LEVELS else None

    async def collect_bid_preferences(
        self, world: "World", avatars: List["Avatar"], lots: List[AuctionLot]
    ) -> Dict[str, Dict[str, Any]]:
        """Ask each actor, on its own, which offered levels it selects.

        One context and one call per avatar: nobody authors anybody else's
        preferences. Lots are addressed by their transient key and actors by
        their ID, never by display name. In test mode no provider is reached
        and every actor abstains.
        """
        # The ContextVar is only set inside `Simulator.step`, so a direct entry
        # into the auction must also honour the World's own RunConfig.
        if (
            is_world_test_mode(world)
            or is_test_mode_enabled()
            or not lots
            or not avatars
        ):
            # No provider is reached and nobody bids. The provenance is the
            # existing `fallback` source; why it fell back is evidence, not a
            # new kind of authorship.
            return {
                str(avatar.id): {
                    "source": ChoiceSource.FALLBACK.value,
                    "reason": "test_mode" if lots and avatars else "nothing_offered",
                    "levels": {},
                    "rejected_lot_keys": [],
                    "offered_balance": int(avatar.magic_stone),
                }
                for avatar in avatars
            }

        from src.classes.prices import prices

        lot_keys = {lot.key for lot in lots}

        def _lots_for(avatar: "Avatar") -> str:
            """What each offered level would actually commit, for this actor.

            The ceilings come from the engine's own `_calculate_bid` at this
            actor's current balance, so the actor selects a level whose
            material terms it can see instead of a bare desire score that
            secretly authorizes spending everything.
            """
            balance = int(avatar.magic_stone)
            lines = []
            for lot in lots:
                ceilings = ", ".join(
                    f"{level}->{self._calculate_bid(lot.item, level, balance)}"
                    for level in OFFERED_NEED_LEVELS
                )
                info = getattr(
                    lot.item, "get_detailed_info", lambda: str(lot.item)
                )()
                lines.append(
                    f"lot_key: {lot.key}, item_id: {lot.item_id}, "
                    f"base_price: {prices.get_price(lot.item)}, "
                    f"your_max_bid_by_level: [{ceilings}], info: {info}"
                )
            return "\n".join(lines)

        async def _ask(avatar: "Avatar") -> Any:
            return await call_llm_with_template(
                template_path=CONFIG.paths.templates / "auction_need.txt",
                infos={
                    "avatar_id": str(avatar.id),
                    "avatar_info": str(avatar.get_info(detailed=True)),
                    "current_balance": str(int(avatar.magic_stone)),
                    "lots": _lots_for(avatar),
                },
            )

        offered_balances = {
            str(avatar.id): int(avatar.magic_stone) for avatar in avatars
        }
        answers = await asyncio.gather(
            *(_ask(avatar) for avatar in avatars), return_exceptions=True
        )

        selections: Dict[str, Dict[str, Any]] = {}
        for avatar, answer in zip(avatars, answers):
            levels: Dict[str, int] = {}
            rejected: List[str] = []
            offered_balance = offered_balances[str(avatar.id)]
            if isinstance(answer, Exception) or not isinstance(answer, dict):
                # An unusable answer is recorded as such; it never becomes a
                # guessed preference.
                selections[str(avatar.id)] = {
                    "source": ChoiceSource.FALLBACK.value,
                    "reason": "unusable_answer",
                    "levels": {},
                    "rejected_lot_keys": [],
                    "offered_balance": offered_balance,
                }
                continue
            for raw_key, raw_level in answer.items():
                key = str(raw_key)
                level = self._validated_need_level(raw_level)
                if key not in lot_keys or level is None:
                    rejected.append(key)
                    continue
                levels[key] = level
            selections[str(avatar.id)] = {
                "source": ChoiceSource.LLM.value,
                "levels": levels,
                "rejected_lot_keys": rejected,
                # The balance the offered ceilings were computed at; the
                # resolver refuses to spend beyond the terms actually shown.
                "offered_balance": offered_balance,
            }
        return selections

    def build_needs(
        self,
        avatars: List["Avatar"],
        lots: List[AuctionLot],
        selections: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict["Avatar", int]]:
        """Validated selections as bids per lot, in the actors' offered order.

        Level 1 is "not wanted" and an omitted lot is no bid at all, so both
        keep the existing no-op semantics. Avatars are iterated in their given
        order so an existing tie resolves exactly as it did before.
        """
        by_key = {lot.key: lot for lot in lots}
        needs: Dict[str, Dict["Avatar", int]] = {}
        for avatar in avatars:
            chosen = (selections.get(str(avatar.id)) or {}).get("levels") or {}
            for key, level in chosen.items():
                if key not in by_key or level <= 1:
                    continue
                needs.setdefault(key, {})[avatar] = level
        return needs

    def _calculate_bid(self, item: "Item", need_level: int, current_balance: int) -> int:
        """
        计算单次出价，根据当前余额动态调整
        """
        from src.classes.prices import prices
        
        if need_level <= 1:
            return 0
            
        # 策略：
        # Need 2: min(money, base_price * 0.8)  (捡漏)
        # Need 3: min(money, base_price * 1.5)  (略微溢价)
        # Need 4: min(money, base_price * 3.0)  (高倍溢价)
        # Need 5: money                         (梭哈)
        
        base_price = prices.get_price(item)
        multipliers = {
            2: 0.8,
            3: 1.5,
            4: 3.0,
        }
        
        if need_level >= 5:
            return current_balance
        
        multiplier = multipliers.get(need_level, 0.0)
        calculated_price = int(base_price * multiplier)
        
        # 最终出价不能超过当前余额
        return min(current_balance, calculated_price)

    def resolve_auctions(
        self,
        needs: Dict[str, Dict["Avatar", int]],
        lots: List[AuctionLot],
    ) -> tuple[Dict[str, tuple["Avatar", int]], List[AuctionLot], Dict[str, Dict["Avatar", int]]]:
        """
        结算拍卖结果（按 lot key，而非物品对象）
        Returns:
            deal_results: 成交结果 {lot_key: (winner, price)}
            unsold_lots: 流拍拍品列表
            all_willing_prices: 所有的出价记录 {lot_key: {avatar: price}} (用于生成故事)
        """
        from src.classes.prices import prices

        deal_results: Dict[str, tuple["Avatar", int]] = {}
        unsold_lots: List[AuctionLot] = []
        all_willing_prices: Dict[str, Dict["Avatar", int]] = {}
        by_key = {lot.key: lot for lot in lots}

        # 1. 建立角色资金快照
        all_avatars = []
        for av_map in needs.values():
            for avatar in av_map:
                if avatar not in all_avatars:
                    all_avatars.append(avatar)
        current_balances = {av: int(av.magic_stone) for av in all_avatars}

        # 2. 拍品排序：按价值从高到低结算，优先处理贵重物品。
        # 同价时保持既有的报价顺序，避免改变原有的平局处理。
        offered_order = {lot.key: position for position, lot in enumerate(lots)}
        sorted_keys = sorted(
            [key for key in needs if key in by_key],
            key=lambda key: (-prices.get_price(by_key[key].item), offered_order[key]),
        )

        for key in sorted_keys:
            lot = by_key[key]
            item = lot.item
            avatar_needs = needs[key]
            bids = {}

            # 计算该物品的所有有效出价
            for avatar, need_val in avatar_needs.items():
                balance = current_balances.get(avatar, 0)
                if balance <= 0:
                    continue

                bid = self._calculate_bid(item, need_val, balance)
                if bid > 0:
                    bids[avatar] = bid

            if bids:
                all_willing_prices[key] = bids

            # 判定流拍
            if not bids:
                unsold_lots.append(lot)
                continue
            
            # 判定赢家 (第二价格密封拍卖)
            sorted_bids = sorted(bids.items(), key=lambda x: x[1], reverse=True)
            winner, highest_bid = sorted_bids[0]
            
            deal_price = 0
            if len(sorted_bids) >= 2:
                second_bid = sorted_bids[1][1]
                deal_price = min(highest_bid, second_bid + 1)
            else:
                # 无竞争：底价成交 (60% bid)
                deal_price = max(1, int(highest_bid * 0.6))
            
            # 只有成交价 <= 余额时才有效（理论上 calculate_bid 已经保证了 bid <= balance，
            # 但为了逻辑闭环，且 bid >= deal_price，所以 deal_price <= balance 必然成立）
            
            # 更新状态
            current_balances[winner] -= deal_price
            deal_results[key] = (winner, deal_price)

        # 只有真正被出价过、却没能成交的拍品才算流拍。
        # 无人表达意向（或全部无效）的拍品保持既有的“什么都不发生”语义，
        # 不会因为没人出价就被销毁。
        return deal_results, unsold_lots, all_willing_prices

    def build_decision_events(
        self,
        world: "World",
        avatars: List["Avatar"],
        lots: List[AuctionLot],
        selections: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Event]:
        """One audited receipt per actor, from what it actually selected.

        Built before any effect, so a settlement can only ever cite a decision
        that already exists. ``source`` states honestly how the selection was
        obtained -- an LLM answer or a fallback that selected nothing -- and is
        never guessed later at execution time.
        """
        from src.i18n import t

        by_key = {lot.key: lot for lot in lots}
        decisions: Dict[str, Event] = {}
        for avatar in avatars:
            selection = selections.get(str(avatar.id))
            if not selection:
                continue
            levels = selection.get("levels") or {}
            chosen_chain = [
                {
                    "action_name": BID_PREFERENCE_LABEL,
                    "params": {
                        "lot_key": key,
                        "item_id": by_key[key].item_id,
                        "need_level": level,
                    },
                }
                for key, level in levels.items()
                if key in by_key
            ]
            audit = AgentDecision(
                month_stamp=int(world.month_stamp),
                subject_kind="avatar",
                subject_id=str(avatar.id),
                source=str(selection.get("source", ChoiceSource.FALLBACK.value)),
                # Every offered lot was on this actor's menu.
                considered_count=len(lots),
                chosen_chain=chosen_chain,
            )
            event = Event(
                world.month_stamp,
                t("{avatar} decided how to bid at the auction.", avatar=avatar.name),
                related_avatars=[avatar.id],
                event_type=DECISION_EVENT_TYPE,
                fact_kind=FactKind.DECISION,
                # A model authored a real selection; an abstention or an
                # unusable answer selected nothing and is the engine's own
                # deterministic outcome. Neither is relabelled as the other.
                causal_origin=(
                    CausalOrigin.LLM_INTERPRETATION
                    if audit.source == ChoiceSource.LLM.value
                    else CausalOrigin.DETERMINISTIC
                ),
                causal_payload={
                    "deltas": [],
                    "decision": audit.to_dict(),
                    "auction_bid_selection": {
                        "offered_lot_keys": [lot.key for lot in lots],
                        "offered_need_levels": list(OFFERED_NEED_LEVELS),
                        "rejected_lot_keys": list(
                            selection.get("rejected_lot_keys") or []
                        ),
                        "fallback_reason": selection.get("reason"),
                        "offered_balance": selection.get("offered_balance"),
                    },
                },
            )
            decisions[str(avatar.id)] = event
        return decisions

    def _build_settlement_event(
        self,
        world: "World",
        *,
        lot: AuctionLot,
        winner: "Avatar",
        price: int,
        refund: int,
        replaced_item_id,
        consumed,
        bids: Dict["Avatar", int],
        decision_event: Event,
        runner_up_decision: Event | None,
        before_stones: int,
        before_weapon_id,
        before_weapon_data,
        before_weapon_proficiency: float,
        before_auxiliary_id,
        before_auxiliary_data,
        before_hp_cur: int,
        before_elixir_count: int,
        before_bucket_count: int,
        after_bucket_count: int,
    ) -> Event:
        """The owner's own record of what this lot actually moved."""
        from src.i18n import t

        owner_id = str(winner.id)
        deltas: List[StateDelta] = []

        def _record(aspect, before, after, magnitude=None, owner_kind="avatar",
                    delta_owner_id=None) -> None:
            if before == after:
                return
            deltas.append(StateDelta(
                owner_kind=owner_kind,
                owner_id=delta_owner_id or owner_id,
                aspect=aspect,
                before=None if before is None else str(before),
                after=None if after is None else str(after),
                magnitude=magnitude,
            ))

        after_stones = int(winner.magic_stone.value)
        _record(
            "magic_stone", before_stones, after_stones,
            magnitude=float(after_stones - before_stones),
        )
        after_weapon_id = winner.weapon.id if winner.weapon else None
        after_weapon_data = dict(winner.weapon.special_data) if winner.weapon else None
        _record("weapon_id", before_weapon_id, after_weapon_id)
        # The same catalog ID can still be a different instance; its own data
        # is what distinguishes them.
        _record("weapon_special_data", before_weapon_data, after_weapon_data)
        after_proficiency = float(winner.weapon_proficiency)
        _record(
            "weapon_proficiency", before_weapon_proficiency, after_proficiency,
            magnitude=after_proficiency - before_weapon_proficiency,
        )
        after_auxiliary_id = winner.auxiliary.id if winner.auxiliary else None
        after_auxiliary_data = (
            dict(winner.auxiliary.special_data) if winner.auxiliary else None
        )
        _record("auxiliary_id", before_auxiliary_id, after_auxiliary_id)
        _record("auxiliary_special_data", before_auxiliary_data, after_auxiliary_data)
        after_hp_cur = int(winner.hp.cur)
        _record(
            "hp", before_hp_cur, after_hp_cur,
            magnitude=float(after_hp_cur - before_hp_cur),
        )
        after_elixir_count = len(winner.elixirs)
        _record(
            "consumed_elixirs", before_elixir_count, after_elixir_count,
            magnitude=float(after_elixir_count - before_elixir_count),
        )

        # Circulation is its own owner: the pool really lost this instance,
        # even when the wallet nets to zero and the equipment ID is unchanged.
        _record(
            f"{lot.bucket}_count",
            before_bucket_count,
            after_bucket_count,
            magnitude=float(after_bucket_count - before_bucket_count),
            owner_kind="circulation",
            delta_owner_id=str(world.playthrough_id),
        )

        sorted_bids = sorted(bids.items(), key=lambda pair: pair[1], reverse=True)
        runner_up = sorted_bids[1][0] if len(sorted_bids) >= 2 else None
        # The single deal fact: the existing localized wording is preserved,
        # so no second untyped event restates it without a source.
        if runner_up is not None:
            content = t(
                "In the auction for {item_name}, {winner_name} outbid {runner_up_name} with {price} spirit stones and won the item.",
                item_name=lot.item.name, winner_name=winner.name,
                runner_up_name=runner_up.name, price=price,
            )
            related_avatars = [winner.id, runner_up.id]
        else:
            content = t(
                "At the auction, {winner_name} acquired {item_name} for {price} spirit stones.",
                winner_name=winner.name, item_name=lot.item.name, price=price,
            )
            related_avatars = [winner.id]

        event = Event(
            world.month_stamp,
            content,
            related_avatars=related_avatars,
            event_type=SETTLEMENT_EVENT_TYPE,
            fact_kind=(
                FactKind.STATE_TRANSITION if deltas else FactKind.OCCURRENCE
            ),
            causal_origin=CausalOrigin.ACTOR_DECISION,
            render_params={"lot_key": lot.key},
            causal_payload={
                "deltas": [],
                "auction_settlement": {
                    "lot_key": lot.key,
                    "lot_bucket": lot.bucket,
                    "item_id": lot.item_id,
                    "item_name": lot.item.name,
                    "winner_avatar_id": owner_id,
                    # Gross figures, stated even when they cancel out.
                    "price_paid": price,
                    "refund_received": refund,
                    "replaced_item_id": replaced_item_id,
                    "bid_count": len(bids),
                    "highest_bid": sorted_bids[0][1] if sorted_bids else None,
                    "second_bid": (
                        sorted_bids[1][1] if len(sorted_bids) >= 2 else None
                    ),
                    # The runner-up is the cause of the second price, so every
                    # actual bidder is named here by ID.
                    "runner_up_avatar_id": (
                        str(runner_up.id) if runner_up is not None else None
                    ),
                    "bidder_avatar_ids": [
                        str(bidder.id) for bidder, _ in sorted_bids
                    ],
                    "removed_instance": {
                        "item_id": lot.item_id,
                        "special_data": dict(
                            getattr(lot.item, "special_data", {}) or {}
                        ),
                    },
                    # False means paid and removed from circulation with no
                    # benefit; no phantom effect is recorded either way.
                    "elixir_consumed": consumed,
                    "circulation_removed": True,
                },
            },
        )
        for delta in deltas:
            delta.event_id = event.id
        event.causal_payload["deltas"] = [delta.to_dict() for delta in deltas]
        event.causal_links.append(CausalLink(
            event_id=event.id,
            cause_event_id=decision_event.id,
            relation=CausalRelation.MOTIVATED_BY,
        ))
        # The runner-up's own decision set the second price, so it contributed
        # to this settlement without having motivated it.
        if runner_up_decision is not None:
            event.causal_links.append(CausalLink(
                event_id=event.id,
                cause_event_id=runner_up_decision.id,
                relation=CausalRelation.CONTRIBUTED_TO,
            ))
        if runner_up is not None:
            mode = RelationDeltaService.get_action_mode("gathering")
            if mode == "llm":
                # gathering 结算点是同步函数，统一在 execute 末尾异步补 delta
                setattr(event, "_relation_delta_pair", (winner, runner_up))
        return event

    def _build_unsold_event(
        self,
        world: "World",
        lot: AuctionLot,
        *,
        before_bucket_count: int,
        after_bucket_count: int,
        special_data: dict,
    ) -> Event:
        """A lot nobody won leaves circulation; nobody chose that.

        Deterministic on purpose: this is the engine retiring an unsold lot,
        not an actor's decision, so it cites none.
        """
        from src.i18n import t

        event = Event(
            world.month_stamp,
            t("{item_name} found no buyer at the auction.", item_name=lot.item.name),
            event_type=UNSOLD_EVENT_TYPE,
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.DETERMINISTIC,
            render_params={"lot_key": lot.key},
            causal_payload={
                "deltas": [],
                "auction_unsold": {
                    "lot_key": lot.key,
                    "lot_bucket": lot.bucket,
                    "item_id": lot.item_id,
                    "item_name": lot.item.name,
                    "removed_instance": {
                        "item_id": lot.item_id,
                        "special_data": dict(special_data or {}),
                    },
                },
            },
        )
        event.causal_payload["deltas"] = [StateDelta(
            event_id=event.id,
            owner_kind="circulation",
            owner_id=str(world.playthrough_id),
            aspect=f"{lot.bucket}_count",
            before=str(before_bucket_count),
            after=str(after_bucket_count),
            magnitude=float(after_bucket_count - before_bucket_count),
        ).to_dict()]
        return event

    @staticmethod
    def _bucket_pool(world: "World", bucket: str) -> list:
        return {
            "weapon": world.circulation.sold_weapons,
            "auxiliary": world.circulation.sold_auxiliaries,
            "elixir": world.circulation.sold_elixirs,
        }[bucket]

    def _is_current_participant(self, world: "World", avatar: "Avatar") -> bool:
        """The canonical Avatar this world still holds, still able to attend.

        Identity, not just a matching ID: a stand-in object carrying the same
        ID is not this world's avatar and settles nothing.
        """
        current = world.avatar_manager.get_avatar(str(avatar.id))
        if current is not avatar or getattr(avatar, "is_dead", False):
            return False
        return self._can_avatar_join(avatar)

    async def _generate_story(
        self,
        world: "World",
        deal_results: Dict[str, tuple["Avatar", int]],
        willing_prices: Dict[str, Dict["Avatar", int]],
        lots_by_key: Dict[str, AuctionLot],
        *,
        source_event: Event | None,
    ) -> List[Event]:
        """
        生成故事 (StoryTeller)
        将本次拍卖的所有重要信息（成交、竞争）汇总传给 LLM，
        让 LLM 自行选取切入点生成故事。
        """
        from src.i18n import t
        if source_event is None:
            return []
        events = []
        
        # 1. 收集所有相关事件文本
        interaction_lines = []
        
        # 收集成交信息
        for key, (winner, deal_price) in deal_results.items():
            item = lots_by_key[key].item
            interaction_lines.append(
                t("Deal: {winner_name} acquired {item_name} for {price} spirit stones.",
                  winner_name=winner.name, item_name=item.name, price=deal_price)
            )
            
        # 收集竞争信息（压一头）
        # 这里为了避免重复太琐碎，只记录竞争激烈（参与者>=2）的情况
        rivalry_avatars = set()
        for key, bids in willing_prices.items():
            if len(bids) < 2:
                continue
            item = lots_by_key[key].item
            sorted_bids = sorted(bids.items(), key=lambda x: x[1], reverse=True)
            winner = sorted_bids[0][0]
            runner_up = sorted_bids[1][0]
            interaction_lines.append(
                t("Competition: In the auction for {item_name}, {winner_name} outbid {runner_up_name} (bid: {bid}).",
                  item_name=item.name, winner_name=winner.name, 
                  runner_up_name=runner_up.name, bid=sorted_bids[1][1])
            )
            rivalry_avatars.add(winner)
            rivalry_avatars.add(runner_up)
            
        if not interaction_lines:
            return []
            
        interaction_result = "\n".join(interaction_lines)
        
        # 2. 收集相关 items 信息
        # 只收集成交了的或者有竞争的物品
        related_keys = set(deal_results.keys())
        for key in willing_prices:
            if len(willing_prices[key]) >= 2:
                related_keys.add(key)
        related_items = [lots_by_key[key].item for key in sorted(related_keys)]


        items_info_list = []
        for item in related_items:
            info = getattr(item, "get_detailed_info", lambda: str(item))()
            items_info_list.append(
                t("Item: {item_name}, Description: {description}",
                  item_name=item.name, description=info)
            )
        items_info_str = "\n".join(items_info_list)
        
        # 3. 收集相关 avatars
        # 主要是成交者和有明显竞争行为的
        related_avatars = set()
        for winner, _ in deal_results.values():
            related_avatars.add(winner)
        related_avatars.update(rivalry_avatars)
        
        if not related_avatars:
            return []

        # 4. 调用 StoryTeller
        # 准备模板参数
        gathering_info = t(
            "Event Type: Mysterious Auction\nScene Setting: The auction takes place in a mysterious space, hosted by a mysterious figure with an unfathomable aura."
        )
        
        # 构建 details (物品信息 + 角色信息)
        # 物品信息
        details_list = []
        if items_info_str:
            details_list.append(t("【Auction Items Information】"))
            details_list.append(items_info_str)
            
        # 角色信息
        details_list.append(t("\n【Related Avatars Information】"))
        for av in related_avatars:
            # 获取详细信息
            info = av.get_info(detailed=True)
            details_list.append(f"- {av.name}: {info}")
            
        details_text = "\n".join(details_list)
        story_event = await StoryEventService.maybe_create_gathering_story(
            month_stamp=world.month_stamp,
            gathering_info=gathering_info,
            events_text=interaction_result,
            details_text=details_text,
            related_avatars=list(related_avatars),
            source_event=source_event,
            prompt=self.get_story_prompt(),
        )
        if story_event is not None:
            events.append(story_event)
        
        return events

    async def execute(self, world: "World") -> List[Event]:
        """
        执行拍卖会
        """
        events = []
        
        # 0. 检查是否有物品
        # 只要 sold_item_count >= threshold 就已经保证有物品了，但为了安全再检查一次
        if world.circulation.sold_item_count == 0:
            return []
            
        avatars = [world.avatar_manager.get_avatar(aid) for aid in self.get_related_avatars(world)]
        # 过滤掉 None
        avatars = [a for a in avatars if a]
        
        if not avatars:
            return []

        # 1. 枚举拍品并收集各自独立的出价意向
        lots = self.enumerate_lots(world)
        if not lots:
            return []
        selections = await self.collect_bid_preferences(world, avatars, lots)

        # 每位被征询者的决策回执先于任何效果产生，且不因其后失效而被抹去
        decision_events = self.build_decision_events(world, avatars, lots, selections)
        events.extend(decision_events.values())

        # 出价之前先剔除已失效的参与者：失效者不能成交，也不能凭其出价
        # 抬高第二价格。回执保留，出价不再计入。
        # 出价上限是按报价时的余额展示给本人的。若其后余额发生变化，
        # 展示过的条件已不成立：该角色本轮不再出价，而不是在其未见过的
        # 条件下超额支出。
        eligible = [
            avatar for avatar in avatars
            if self._is_current_participant(world, avatar)
            and (selections.get(str(avatar.id)) or {}).get("offered_balance")
            == int(avatar.magic_stone)
        ]
        # 报价之后可能已有拍品离开流通池。这些拍品不能参与结算：否则它们会
        # 先“花掉”竞拍者的预算，再因无法移除而跳过，从而压低后续有效拍品的
        # 出价。这里按实例身份筛选，并保留原有的 lot key，不做重新编号。
        live_lots = [
            lot for lot in lots
            if any(item is lot.item for item in self._bucket_pool(world, lot.bucket))
        ]
        needs = self.build_needs(eligible, live_lots, selections)

        # 2. 结算拍卖 (动态计算出价，处理资产穿透)
        deal_results, unsold_lots, willing_prices = self.resolve_auctions(
            needs, live_lots
        )
        
        # 3. 执行交易 (扣钱、给物品、移除 circulation)
        from src.classes.items.weapon import Weapon
        from src.classes.items.auxiliary import Auxiliary
        from src.classes.items.elixir import Elixir
        from src.classes.prices import prices
        
        by_key = {lot.key: lot for lot in lots}
        settled_keys: List[str] = []
        settlement_events: List[Event] = []

        # 处理成交物品
        for key, (winner, price) in deal_results.items():
            lot = by_key[key]
            item = lot.item

            # 结算前重新校验：当下的参与者、当下的余额、当下的那一件实例
            decision_event = decision_events.get(str(winner.id))
            if decision_event is None:
                # No audited decision, no purchase: nothing may move.
                continue
            # The receipt existing is not the same as having chosen this lot.
            # The live validated selection is the authority; the audit record
            # is evidence and is never parsed back into permission.
            selected = (selections.get(str(winner.id)) or {}).get("levels") or {}
            if selected.get(key, 1) <= 1:
                continue
            # And the price must be one this actor's own bid actually covers.
            offered_bid = willing_prices.get(key, {}).get(winner, 0)
            if price <= 0 or price > offered_bid:
                continue
            if not self._is_current_participant(world, winner):
                continue
            if int(winner.magic_stone) < price:
                continue

            lot_bids = willing_prices.get(key, {})
            ordered_bids = sorted(
                lot_bids.items(), key=lambda pair: pair[1], reverse=True
            )
            runner_up_decision = (
                decision_events.get(str(ordered_bids[1][0].id))
                if len(ordered_bids) >= 2 else None
            )

            pool = self._bucket_pool(world, lot.bucket)
            before_bucket_count = len(pool)
            if not world.circulation.remove_item(item):
                # 那一件实例已不在流通池：不成交，也不产生任何变更
                continue
            after_bucket_count = len(pool)
            settled_keys.append(key)

            before_stones = int(winner.magic_stone.value)
            before_weapon_id = winner.weapon.id if winner.weapon else None
            before_weapon_data = (
                dict(winner.weapon.special_data) if winner.weapon else None
            )
            before_weapon_proficiency = float(winner.weapon_proficiency)
            before_auxiliary_id = winner.auxiliary.id if winner.auxiliary else None
            before_auxiliary_data = (
                dict(winner.auxiliary.special_data) if winner.auxiliary else None
            )
            before_hp_cur = int(winner.hp.cur)
            before_elixir_count = len(winner.elixirs)

            # 扣钱
            winner.magic_stone -= price
            refund = 0
            replaced_item_id = None
            consumed = None

            # 给物品
            if isinstance(item, (Weapon, Auxiliary)):
                # 装备并处理旧装备
                # 特殊逻辑：拍卖会换下的旧装备直接销毁（折价回收但不再进入流通池），防止物品无限膨胀

                if isinstance(item, Weapon):
                    old_equip = winner.weapon
                    if old_equip:
                        # 计算回收价
                        replaced_item_id = old_equip.id
                        refund = prices.get_selling_price(old_equip, winner)
                        winner.magic_stone += refund
                    # 换装
                    winner.change_weapon(item)

                elif isinstance(item, Auxiliary):
                    old_equip = winner.auxiliary
                    if old_equip:
                        replaced_item_id = old_equip.id
                        refund = prices.get_selling_price(old_equip, winner)
                        winner.magic_stone += refund
                    # 换装
                    winner.change_auxiliary(item)

            elif isinstance(item, Elixir):
                # 丹药直接服用；服用失败时仍保留既有的付款与移除语义
                consumed = bool(winner.consume_elixir(item))

            settlement_events.append(self._build_settlement_event(
                world,
                lot=lot,
                winner=winner,
                price=price,
                refund=refund,
                replaced_item_id=replaced_item_id,
                consumed=consumed,
                bids=willing_prices.get(key, {}),
                decision_event=decision_event,
                runner_up_decision=runner_up_decision,
                before_stones=before_stones,
                before_weapon_id=before_weapon_id,
                before_weapon_data=before_weapon_data,
                before_weapon_proficiency=before_weapon_proficiency,
                before_auxiliary_id=before_auxiliary_id,
                before_auxiliary_data=before_auxiliary_data,
                before_hp_cur=before_hp_cur,
                before_elixir_count=before_elixir_count,
                before_bucket_count=before_bucket_count,
                after_bucket_count=after_bucket_count,
            ))

        deal_results = {key: deal_results[key] for key in settled_keys}
        events.extend(settlement_events)

        # 处理流拍物品：直接销毁（移出流通池）
        for lot in unsold_lots:
            pool = self._bucket_pool(world, lot.bucket)
            before_bucket_count = len(pool)
            special_data = dict(getattr(lot.item, "special_data", {}) or {})
            if world.circulation.remove_item(lot.item):
                events.append(self._build_unsold_event(
                    world, lot,
                    before_bucket_count=before_bucket_count,
                    after_bucket_count=len(pool),
                    special_data=special_data,
                ))


        # 5. 成交事实本身就是基础事件，不再生成第二条无来源的重复事件
        relation_events = []
        for event in settlement_events:
            pair = getattr(event, "_relation_delta_pair", None)
            if pair is None:
                continue
            winner_avatar, runner_up_avatar = pair
            proposal = await RelationDeltaService.propose_relationship_impact(
                action_key="gathering",
                avatar_a=winner_avatar,
                avatar_b=runner_up_avatar,
                event_text=event.content,
            )
            relation_events.append(
                RelationDeltaService.apply_relationship_impact(
                    winner_avatar,
                    runner_up_avatar,
                    proposal,
                    source_event=event,
                    action_key="gathering",
                    allowed_a_to_b=frozenset(RelationshipValence),
                    allowed_b_to_a=frozenset(RelationshipValence),
                )
            )
        events.extend(relation_events)

        # 6. 生成故事 (StoryTeller)
        # 故事只描述真正成交的拍品：被拒绝或失效的交易不能被讲成已经赢下
        settled_prices = {
            key: bids for key, bids in willing_prices.items() if key in settled_keys
        }
        story_events = await self._generate_story(
            world,
            deal_results,
            settled_prices,
            by_key,
            source_event=settlement_events[-1] if settlement_events else None,
        )
        events.extend(story_events)
        
        return events

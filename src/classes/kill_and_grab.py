from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass
import random

from src.i18n import t
from src.systems.single_choice import (
    ItemDisposition,
    ItemExchangeKind,
    ItemExchangeRequest,
    RejectMode,
    resolve_item_exchange,
)

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar


@dataclass(frozen=True)
class EquipmentTransfer:
    kind: str
    item_snapshot: dict
    loser_id: str
    winner_id: str


async def kill_and_grab(winner: Avatar, loser: Avatar) -> tuple[str, EquipmentTransfer | None]:
    """
    处理杀人夺宝逻辑
    
    Args:
        winner: 胜利者
        loser: 失败者（已死亡）
        
    Returns:
        str: 夺宝结果描述文本（如"并夺取了..."），如果没有夺取则为空字符串
    """
    loot_candidates = []
    
    # 检查兵器
    if loser.weapon:
        loot_candidates.append(("weapon", loser.weapon))
    
    # 检查辅助装备
    if loser.auxiliary:
        loot_candidates.append(("auxiliary", loser.auxiliary))
    
    if not loot_candidates:
        return "", None

    # 优先高境界
    loot_candidates.sort(key=lambda x: x[1].realm, reverse=True)
    # 筛选出最高优先级的那些
    best_realm = loot_candidates[0][1].realm
    best_candidates = [c for c in loot_candidates if c[1].realm == best_realm]
    loot_type, loot_item = random.choice(best_candidates)
    
    # 判定是否夺取
    item_label = t("weapon") if loot_type == "weapon" else t("auxiliary")
    # 使用 str() 来触发 Realm 的 __str__ 方法进行 i18n 翻译。
    context = t(
        "After defeating {loser}, {winner} found a {realm} {item_label} [{item_name}].",
        loser=loser.name,
        winner=winner.name,
        realm=str(loot_item.realm),
        item_label=item_label,
        item_name=loot_item.name,
    )
    
    outcome = await resolve_item_exchange(
        ItemExchangeRequest(
            avatar=winner,
            new_item=loot_item,
            kind=ItemExchangeKind(loot_type),
            scene_intro=context,
            reject_mode=RejectMode.ABANDON_NEW,
            auto_accept_when_empty=True,
        )
    )

    if outcome.accepted and outcome.action in {
        ItemDisposition.AUTO_ACCEPTED,
        ItemDisposition.REPLACED_OLD,
    }:
        if loot_type == "weapon":
            loser.change_weapon(None)
        else:
            loser.change_auxiliary(None)
        
        return t(
            "Looted {item_label} [{item_name}]. {result}",
            item_label=item_label,
            item_name=loot_item.name,
            result=outcome.result_text,
        ), EquipmentTransfer(
            kind=loot_type,
            item_snapshot={"id": getattr(loot_item, "id", None), "name": loot_item.name, "realm": str(loot_item.realm)},
            loser_id=str(getattr(loser, "id", "")),
            winner_id=str(getattr(winner, "id", "")),
        )
    
    return "", None

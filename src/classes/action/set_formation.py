from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING

from src.classes.action import InstantAction
from src.classes.action.param_options import ParamOptionSource
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.systems.formation import (
    build_formation_record,
    compute_formation_cost,
    get_formation_disk_config,
    get_formation_type_name,
    has_formation_permission,
    is_formation_allowed_in_region,
    is_valid_formation_type,
    normalize_formation_type,
    place_region_formation,
)

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar


class SetFormation(InstantAction):
    """布置阵法：装备阵盘后，在当前 region 布置一个限时区域效果。"""

    ACTION_NAME_ID = "set_formation_action_name"
    DESC_ID = "set_formation_description"
    REQUIREMENTS_ID = "set_formation_requirements"

    EMOJI = "🧭"
    PARAMS = {
        "formation_type": "FormationType",
    }
    PARAM_OPTION_SOURCES = {
        "formation_type": ParamOptionSource.AVAILABLE_FORMATION_TYPE,
    }

    def __init__(self, avatar: "Avatar", world):
        super().__init__(avatar, world)
        self._last_region = None
        self._last_formation_type = ""
        self._last_replaced = False
        self._last_cost = 0
        self._last_event: Event | None = None
        self._last_condition_attached = False

    def can_possibly_start(self) -> bool:
        if not has_formation_permission(self.avatar):
            return False
        disk_cfg = get_formation_disk_config(getattr(self.avatar, "auxiliary", None))
        if disk_cfg is None:
            return False
        region = getattr(getattr(self.avatar, "tile", None), "region", None)
        if region is None:
            return False
        from src.systems.formation import get_available_formation_types_for_region

        available = get_available_formation_types_for_region(region)
        if not available:
            return False
        stone = int(getattr(getattr(self.avatar, "magic_stone", 0), "value", getattr(self.avatar, "magic_stone", 0)) or 0)
        return any(
            stone >= compute_formation_cost(self.avatar, cfg.key, region, disk_cfg)
            for cfg in available
        )

    def can_start(self, formation_type: str) -> tuple[bool, str]:
        if not has_formation_permission(self.avatar):
            return False, t("Missing formation disk")
        disk_cfg = get_formation_disk_config(getattr(self.avatar, "auxiliary", None))
        if disk_cfg is None:
            return False, t("Missing formation disk")
        normalized = normalize_formation_type(formation_type)
        if not is_valid_formation_type(normalized):
            return False, t("Invalid formation type")

        region = getattr(getattr(self.avatar, "tile", None), "region", None)
        if region is None:
            return False, t("Current location cannot set formation")
        if not is_formation_allowed_in_region(normalized, region):
            return False, t("Formation cannot be set in current region")

        cost = compute_formation_cost(self.avatar, normalized, region, disk_cfg)
        stone = int(getattr(getattr(self.avatar, "magic_stone", 0), "value", getattr(self.avatar, "magic_stone", 0)) or 0)
        if stone < cost:
            return False, t("Not enough spirit stones")
        return True, ""

    def start(self, formation_type: str) -> Event:
        region = getattr(getattr(self.avatar, "tile", None), "region", None)
        region_name = getattr(region, "name", t("Current region"))
        formation_name = get_formation_type_name(formation_type)
        content = t(
            "{avatar} begins setting {formation} in {region}.",
            avatar=self.avatar.name,
            formation=formation_name,
            region=region_name,
        )
        return Event(self.world.month_stamp, content, related_avatars=[self.avatar.id])

    def _execute(self, formation_type: str) -> None:
        self._last_region = getattr(getattr(self.avatar, "tile", None), "region", None)
        self._last_formation_type = normalize_formation_type(formation_type)
        self._last_replaced = False
        self._last_cost = 0
        self._last_event = None
        self._last_condition_attached = False

        if self._last_region is None:
            return
        disk_cfg = get_formation_disk_config(getattr(self.avatar, "auxiliary", None))
        if disk_cfg is None or not is_valid_formation_type(self._last_formation_type):
            return
        if not is_formation_allowed_in_region(self._last_formation_type, self._last_region):
            return

        cost = compute_formation_cost(self.avatar, self._last_formation_type, self._last_region, disk_cfg)
        stone = int(getattr(getattr(self.avatar, "magic_stone", 0), "value", getattr(self.avatar, "magic_stone", 0)) or 0)
        if stone < cost:
            return

        region_name = getattr(self._last_region, "name", t("Current region"))
        formation_name = get_formation_type_name(self._last_formation_type)
        old = getattr(self.world.map, "region_formations", {}).get(int(self._last_region.id))
        if old is not None:
            content = t(
                "{avatar} set {formation} in {region}; the original formation in this region was replaced.",
                avatar=self.avatar.name,
                formation=formation_name,
                region=region_name,
            )
        else:
            content = t(
                "{avatar} set {formation} in {region}.",
                avatar=self.avatar.name,
                formation=formation_name,
                region=region_name,
            )
        event = Event(
            self.world.month_stamp,
            content,
            related_avatars=[self.avatar.id],
            is_major=True,
            event_type="formation_set",
            render_params={
                "region_id": str(self._last_region.id),
                "formation_type": self._last_formation_type,
            },
            fact_kind=FactKind.STATE_TRANSITION,
        )

        stone_before = stone
        self.avatar.magic_stone -= cost
        formation = build_formation_record(
            self.avatar,
            self._last_formation_type,
            self._last_region,
            disk_cfg,
            source_event_id=event.id,
        )
        formation["cost"] = cost
        old = place_region_formation(self.world, int(self._last_region.id), formation)
        self._last_cost = cost
        self._last_replaced = old is not None
        self._last_event = event
        event.causal_payload = {
            "deltas": [
                StateDelta(
                    event_id=event.id,
                    owner_kind="avatar",
                    owner_id=str(self.avatar.id),
                    aspect="magic_stone",
                    before=str(stone_before),
                    after=str(stone_before - cost),
                    magnitude=-float(cost),
                ).to_dict(),
                StateDelta(
                    event_id=event.id,
                    owner_kind="region",
                    owner_id=str(self._last_region.id),
                    aspect="formation",
                    before=(
                        json.dumps(old, ensure_ascii=False, sort_keys=True)
                        if old is not None else None
                    ),
                    after=json.dumps(formation, ensure_ascii=False, sort_keys=True),
                ).to_dict(),
            ]
        }
        old_source_event_id = str((old or {}).get("source_event_id", "") or "")
        if old_source_event_id:
            event.causal_links.append(CausalLink(
                event_id=event.id,
                cause_event_id=old_source_event_id,
                relation=CausalRelation.RESOLVES,
            ))

    def _attach_semantic_condition(self, event: Event, formation: dict) -> None:
        """Mirror the map-owned formation as a causal semantic condition."""
        region = self._last_region
        if region is None:
            return

        from src.classes.mechanical_language import ConditionInstance, EntityRef

        formation_type = normalize_formation_type(str(formation.get("formation_type", "")))
        kind = f"{formation_type}_formation"
        started_month = int(formation.get("start_month", self.world.month_stamp))
        duration = int(formation.get("duration", 0))
        expires_month = started_month + duration if duration > 0 else None
        semantic_state = self.world.mechanical_language
        target = EntityRef("region", str(region.id))
        active_conditions = semantic_state.get_active_conditions(
            target,
            int(self.world.month_stamp),
        )
        previous = next(
            (item for item in active_conditions if item.definition_id == f"formation:{kind}"),
            None,
        )
        # Map owns the formation record, while the world semantic registry
        # owns condition instances. Replacing a formation retires every
        # active formation condition without creating a second owner.
        for old_condition in active_conditions:
            if old_condition.definition_id.startswith("formation:"):
                semantic_state.replace_condition_instance(replace(
                    old_condition,
                    resolved_month=int(self.world.month_stamp),
                    resolution_event_id=event.id,
                ))

        condition = ConditionInstance(
            id=f"formation:{region.id}:{event.id}",
            definition_id=f"formation:{kind}",
            target_kind="region",
            target_id=str(region.id),
            label=kind,
            intensity=1.0,
            started_month=started_month,
            expires_month=expires_month,
            cause_event_id=event.id,
        )
        semantic_state.add_condition_instance(condition)

        before = previous.to_dict() if previous is not None else None
        payload = event.causal_payload or {"deltas": []}
        payload["deltas"].append(StateDelta(
            event_id=event.id,
            owner_kind="region",
            owner_id=str(region.id),
            aspect=f"condition:{kind}",
            before=json.dumps(before, ensure_ascii=False, sort_keys=True) if before is not None else None,
            after=json.dumps(condition.to_dict(), ensure_ascii=False, sort_keys=True),
        ).to_dict())
        event.causal_payload = payload

    async def finish(self, formation_type: str) -> list[Event]:
        if self._last_event is not None and not self._last_condition_attached:
            formation = getattr(self.world.map, "region_formations", {}).get(
                int(self._last_region.id),
            ) if self._last_region is not None else None
            if formation is not None:
                self._attach_semantic_condition(self._last_event, formation)
            self._last_condition_attached = True
        return [self._last_event] if self._last_event is not None else []

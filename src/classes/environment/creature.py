"""One authored sentient creature bound to a real water body and its route.

This is not a monster engine. The state holds a single physical premise — a
drake that lives in an existing water body and perceives cargo that actually
crosses its river — plus the demands it has voiced and the one restriction it
may have imposed on the Map. It owns no territory, no stock, no population and
no relations: the Map keeps route state, Economy keeps food, and Knowledge
keeps who was told what.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _CreatureValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Creature(_CreatureValue):
    """A sentient inhabitant of one water body, watching its own river."""

    id: str
    name: str
    water_body_id: str
    route_ids: tuple[str, ...]
    condition: int = Field(strict=True, ge=0, le=1000)
    hunger_threshold: int = Field(strict=True, ge=0, le=1000)
    tribute_food: int = Field(strict=True, gt=0)
    perceived_crossings: int = Field(strict=True, ge=0, default=0)
    last_perceived_day: int | None = Field(strict=True, ge=0, default=None)
    restricted_route_id: str | None = None
    restriction_event_id: str | None = None
    # A single pending material retaliation.  The site remains Map-owned;
    # these fields only bind the creature's temporary action to its causal
    # damage fact so a later repair/settlement can clear it explicitly.
    damaged_site_id: str | None = None
    damage_event_id: str | None = None
    last_event_id: str | None = None


class CreatureDemand(_CreatureValue):
    """A voiced request for food tribute on one crossing, with its own deadline."""

    id: str
    creature_id: str
    route_id: str
    food: int = Field(strict=True, gt=0)
    opened_day: int = Field(strict=True, ge=0)
    due_day: int = Field(strict=True, ge=0)
    stage: Literal["open", "satisfied", "expired", "withdrawn"] = "open"
    perception_event_id: str
    decision_event_id: str
    settled_by_ref: dict[str, str] | None = None
    last_event_id: str


@dataclass
class CreatureState:
    """Persisted creatures and their voiced demands; nothing else."""

    creatures: dict[str, Creature] = field(default_factory=dict)
    demands: dict[str, CreatureDemand] = field(default_factory=dict)

    def open_demands(self, creature_id: str) -> tuple[CreatureDemand, ...]:
        return tuple(item for _, item in sorted(self.demands.items())
                     if item.creature_id == creature_id and item.stage == "open")

    def validate(self, world=None) -> None:
        if not isinstance(self.creatures, dict) or not isinstance(self.demands, dict):
            raise ValueError("invalid creature registries")
        events = {event.id: event for event in world.events} if world is not None else {}
        for key, creature in self.creatures.items():
            if not isinstance(creature, Creature) or key != creature.id or not creature.route_ids:
                raise ValueError("invalid creature registry entry")
            Creature.model_validate(creature.model_dump(mode="json"))
            if (creature.restricted_route_id is None) != (creature.restriction_event_id is None):
                raise ValueError("a creature restriction requires its own fact")
            if (creature.damaged_site_id is None) != (creature.damage_event_id is None):
                raise ValueError("a creature damage binding requires its own fact")
            if creature.restricted_route_id is not None and creature.restricted_route_id not in creature.route_ids:
                raise ValueError("a creature can only restrict its own crossings")
            if world is None:
                continue
            water_bodies = {body.id: body for body in world.map.geography.water_bodies}
            if (creature.water_body_id not in water_bodies
                    or any(route_id not in world.map.routes for route_id in creature.route_ids)):
                raise ValueError("creature references an unknown water body or route")
            if creature.last_perceived_day is not None and creature.last_perceived_day > world.clock.absolute_day:
                raise ValueError("creature perception is ahead of the world clock")
            if creature.restriction_event_id is not None:
                event = events.get(creature.restriction_event_id)
                if (event is None or event.event_type != "creature_restricted_route"
                        or not any(delta.owner_kind == "route" and delta.owner_id == creature.restricted_route_id
                                   and delta.aspect == "enabled" and delta.after == "False"
                                   for delta in event.deltas)):
                    raise ValueError("creature restriction requires its canonical route fact")
            if creature.damage_event_id is not None:
                event = events.get(creature.damage_event_id)
                site = world.map.infrastructure_sites.get(creature.damaged_site_id)
                if (event is None or event.event_type != "creature_damaged_site"
                        or event.fact_kind.value != "state_transition" or site is None):
                    raise ValueError("creature damage requires its canonical site fact")
                site_deltas = [delta for delta in event.deltas
                               if delta.owner_kind == "site" and delta.owner_id == site.id
                               and delta.aspect == "integrity"]
                creature_deltas = [delta for delta in event.deltas
                                   if delta.owner_kind == "creature" and delta.owner_id == creature.id
                                   and delta.aspect == "damaged_site_id"]
                if (len(site_deltas) != 1 or len(creature_deltas) != 1
                        or creature_deltas[0].after != site.id
                        or float(site_deltas[0].before) <= float(site_deltas[0].after)):
                    raise ValueError("creature damage binding is no longer pending")
        for key, demand in self.demands.items():
            if (not isinstance(demand, CreatureDemand) or key != demand.id
                    or demand.due_day < demand.opened_day
                    or demand.creature_id not in self.creatures
                    or demand.route_id not in self.creatures[demand.creature_id].route_ids):
                raise ValueError("invalid creature demand")
            CreatureDemand.model_validate(demand.model_dump(mode="json"))
            if (demand.stage == "satisfied") != (demand.settled_by_ref is not None):
                raise ValueError("a satisfied demand names who settled it")
            if world is None:
                continue
            perception = events.get(demand.perception_event_id)
            decision = events.get(demand.decision_event_id)
            receipt = events.get(demand.last_event_id)
            if (perception is None or perception.event_type != "creature_perceived_cargo"
                    or decision is None or receipt is None
                    or demand.opened_day > world.clock.absolute_day):
                raise ValueError("creature demand requires its perception and decision")
            if not any(delta.owner_kind == "creature_demand" and delta.owner_id == demand.id
                       and delta.aspect == "stage" and delta.after == demand.stage for delta in receipt.deltas):
                raise ValueError("creature demand requires its own stage receipt")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {"schema_version": 2,
                "creatures": {key: item.model_dump(mode="json") for key, item in sorted(self.creatures.items())},
                "demands": {key: item.model_dump(mode="json") for key, item in sorted(self.demands.items())}}

    @classmethod
    def from_dict(cls, data: Any) -> "CreatureState":
        if (not isinstance(data, dict) or set(data) != {"schema_version", "creatures", "demands"}
                or type(data["schema_version"]) is not int or data["schema_version"] != 2
                or not isinstance(data["creatures"], dict) or not isinstance(data["demands"], dict)):
            raise ValueError("invalid creature state schema")
        creatures = {key: Creature.model_validate(raw) for key, raw in data["creatures"].items()}
        demands = {key: CreatureDemand.model_validate(raw) for key, raw in data["demands"].items()}
        state = cls(creatures=creatures, demands=demands)
        state.validate()
        return state


__all__ = ["Creature", "CreatureDemand", "CreatureState"]

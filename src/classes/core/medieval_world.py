"""Canonical medieval world root, independent of Avatar/cultivation lifecycles.

The application entrypoint is migrated separately; this is the target world
model for the fork, not a second user-selectable ruleset.
"""

from dataclasses import dataclass, field
import random
from typing import TYPE_CHECKING

from src.classes.environment.map import Map
from src.classes.society import SocietyState
from src.classes.economy import EconomyState
from src.classes.governance import AuthorityState, KnowledgeState, StrategyState
from src.classes.research import ResearchState
from src.classes.governance.diplomacy import RelationsState
from .medieval_config import MedievalRunConfig
from src.systems.calendar_agenda import WorldAgenda
from src.systems.time import WorldClock

if TYPE_CHECKING:
    from src.sim.medieval.events import WorldEvent
    from src.sim.medieval.activities import Activity


@dataclass
class MedievalWorld:
    map: Map
    society: SocietyState
    rng: random.Random
    economy: EconomyState
    config: MedievalRunConfig
    authority: AuthorityState
    strategy: StrategyState
    research: ResearchState
    relations: RelationsState = field(default_factory=RelationsState)
    knowledge: KnowledgeState = field(default_factory=KnowledgeState)
    clock: WorldClock = field(default_factory=WorldClock)
    agenda: WorldAgenda = field(default_factory=WorldAgenda)
    events: list["WorldEvent"] = field(default_factory=list)
    activities: dict[str, "Activity"] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.society.validate(set(self.map.regions))
        self.economy.validate(self)
        self.authority.validate(self)
        self.strategy.validate(self)
        self.knowledge.validate(self)
        self.research.validate(self)
        self.relations.validate(self)
        MedievalRunConfig.model_validate(self.config.model_dump())

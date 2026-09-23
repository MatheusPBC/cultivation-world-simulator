"""Canonical medieval world root, independent of Avatar/cultivation lifecycles.

The application entrypoint is migrated separately; this is the target world
model for the fork, not a second user-selectable ruleset.
"""

from dataclasses import dataclass, field, fields, is_dataclass
import copy
import random
from typing import TYPE_CHECKING

from src.classes.environment.map import Map
from src.classes.environment.creature import CreatureState
from src.classes.environment.regional_overflow import RegionalOverflowState
from src.classes.society import SocietyState
from src.classes.economy import EconomyState
from src.classes.governance import AuthorityState, KnowledgeState, StrategyState
from src.classes.research import ResearchState
from src.classes.governance.diplomacy import RelationsState
from .infrastructure import validate_infrastructure
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
    regional_overflow: RegionalOverflowState = field(default_factory=RegionalOverflowState)
    creatures: CreatureState = field(default_factory=CreatureState)
    clock: WorldClock = field(default_factory=WorldClock)
    agenda: WorldAgenda = field(default_factory=WorldAgenda)
    events: list["WorldEvent"] = field(default_factory=list)
    activities: dict[str, "Activity"] = field(default_factory=dict)
    _event_index_cache: tuple[int, int, dict[str, "WorldEvent"]] | None = field(
        default=None, repr=False, compare=False)
    _event_type_cache: tuple[int, int, dict[str, tuple["WorldEvent", ...]]] | None = field(
        default=None, repr=False, compare=False)
    _strategic_capacity_cache: tuple[tuple[int, int], dict[tuple[str, str], dict]] | None = field(
        default=None, repr=False, compare=False)
    _diplomatic_context_cache: tuple[tuple[int, int, int], dict[tuple[str, str], object]] | None = field(
        default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.society.validate(set(self.map.regions), self)
        self.economy.validate(self)
        self.authority.validate(self)
        self.strategy.validate(self)
        self.knowledge.validate(self)
        self.research.validate(self)
        self.relations.validate(self)
        self.regional_overflow.validate(self)
        self.creatures.validate(self)
        validate_infrastructure(self)
        MedievalRunConfig.model_validate(self.config.model_dump())

    def transaction_copy(self) -> "MedievalWorld":
        """Copy mutable world state while sharing the validated event prefix.

        Medieval events are append-only facts: transactional code appends a new
        event or replaces the just-created event in its own list when attaching
        derived causal payload.  It never edits a previously committed event in
        place.  Copying thousands of already validated Pydantic events for every
        dated step made long-horizon verification superlinear in practice, so a
        candidate gets its own event *list* while retaining the immutable prefix
        objects.  All domain registries, RNG state and agenda entries remain
        deep-copied and therefore rollback-safe.

        Registry containers are copied without invoking Python's generic
        deepcopy machinery for every frozen Pydantic value.  Domain owners
        replace registry entries rather than mutating them in place; copying
        the value's own mutable containers still keeps rollback safe for the
        few authored models that contain dictionaries or lists.

        The world-level ``__deepcopy__`` delegates here as well.  The event
        objects themselves remain independently deep-copyable when a caller
        explicitly copies ``world.events``; only a transactional world clone
        uses the append-only prefix sharing described above.
        """
        candidate = copy.copy(self)
        for name in self.__dataclass_fields__:
            if name == "events":
                setattr(candidate, name, list(self.events))
            elif name == "_event_index_cache":
                setattr(candidate, name, self._event_index_cache)
            elif name == "_event_type_cache":
                setattr(candidate, name, self._event_type_cache)
            elif name == "_strategic_capacity_cache":
                setattr(candidate, name, self._strategic_capacity_cache)
            elif name == "_diplomatic_context_cache":
                setattr(candidate, name, self._diplomatic_context_cache)
            elif name == "map":
                setattr(candidate, name, self.map.transaction_copy())
            elif name in {
                "society", "economy", "authority", "strategy", "research",
                "relations", "knowledge", "regional_overflow", "creatures",
            }:
                setattr(candidate, name, _copy_transaction_container(
                    getattr(self, name), share_values=name == "knowledge"))
            elif name == "activities":
                setattr(candidate, name, dict(self.activities))
            elif name == "agenda":
                agenda = copy.copy(self.agenda)
                agenda._situations = dict(self.agenda._situations)
                setattr(candidate, name, agenda)
            elif name == "clock":
                # WorldClock is frozen and contains only an integer.
                setattr(candidate, name, self.clock)
            elif name in {"rng", "config"}:
                # RNG state and the config's monthly budget ledger are mutable
                # and must never be shared between candidate and publication.
                setattr(candidate, name, copy.deepcopy(getattr(self, name)))
            else:
                setattr(candidate, name, copy.deepcopy(getattr(self, name)))
        return candidate

    def event_index(self) -> dict[str, "WorldEvent"]:
        """Return a transient index for the append-only canonical event ledger."""
        last_identity = id(self.events[-1]) if self.events else 0
        cached = self._event_index_cache
        if cached is None or cached[0] != len(self.events) or cached[1] != last_identity:
            cached = (len(self.events), last_identity, {event.id: event for event in self.events})
            self._event_index_cache = cached
        return cached[2]

    def events_of_type(self, event_type: str) -> tuple["WorldEvent", ...]:
        """Return a transient type index over the append-only event ledger."""
        last_identity = id(self.events[-1]) if self.events else 0
        cached = self._event_type_cache
        if cached is None or cached[0] != len(self.events) or cached[1] != last_identity:
            grouped = {}
            for event in self.events:
                grouped.setdefault(event.event_type, []).append(event)
            cached = (len(self.events), last_identity,
                      {kind: tuple(items) for kind, items in grouped.items()})
            self._event_type_cache = cached
        return cached[2].get(event_type, ())

    def __deepcopy__(self, memo):
        """Use the transactional clone for the medieval world's atomic forks."""
        candidate = self.transaction_copy()
        memo[id(self)] = candidate
        return candidate


def _copy_transaction_container(value, *, share_values=False):
    """Copy a domain state and its registries without validation/serialization.

    Registry values are immutable at the model boundary.  Their nested
    containers are copied recursively so an accidental in-place mutation in a
    candidate cannot alter the published world, while avoiding the much more
    expensive generic ``deepcopy`` path used for every monthly transaction.
    """
    if not is_dataclass(value):
        return copy.deepcopy(value)
    result = copy.copy(value)
    for item in fields(value):
        current = getattr(value, item.name)
        setattr(result, item.name, _copy_transaction_value(current, share_values=share_values))
    # KnowledgeState registries are tracked dictionaries.  Rebind them to the
    # candidate and clear transient validation/query projections after the
    # shallow dataclass copy; they must never share an epoch or cache with the
    # published world.
    bind = getattr(result, "_bind_registry_epoch", None)
    if bind is not None:
        bind(preserve_query=True)
    return result


def _copy_transaction_value(value, *, share_values=False):
    if isinstance(value, dict):
        return {key: _copy_transaction_value(item, share_values=share_values) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_transaction_value(item, share_values=share_values) for item in value]
    if isinstance(value, set):
        return {_copy_transaction_value(item, share_values=share_values) for item in value}
    if isinstance(value, tuple):
        # Most authored tuple fields are identity/enum scalars.  They are
        # immutable, so keep the tuple object instead of recursively visiting
        # every scalar on every transactional fork.  Tuples containing a
        # mutable/model value still take the isolated path below.
        if all(isinstance(item, (str, int, float, bool, type(None), bytes)) for item in value):
            return value
        return tuple(_copy_transaction_value(item, share_values=share_values) for item in value)
    if isinstance(value, frozenset):
        if all(isinstance(item, (str, int, float, bool, type(None), bytes)) for item in value):
            return value
        return frozenset(_copy_transaction_value(item, share_values=share_values) for item in value)
    # Frozen Pydantic values are replaced by owners, but their dictionaries
    # and lists are not deep-frozen by Pydantic.  Clone those fields without
    # re-validating every value during a transaction fork.
    if hasattr(value, "__pydantic_fields__") and hasattr(value, "__dict__"):
        if share_values:
            # Frozen scalar SocietyValue models are replaced by owners rather
            # than mutated in place.  Knowledge registries contain only these
            # scalar observation/notice values, so sharing them avoids
            # re-walking the historical index on every transaction.
            return value
        result = copy.copy(value)
        for key, item in value.__dict__.items():
            object.__setattr__(result, key, _copy_transaction_value(item, share_values=share_values))
        return result
    return value

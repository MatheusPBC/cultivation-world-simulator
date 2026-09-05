from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from types import FunctionType, MethodType, ModuleType
from typing import Any


_ATOMIC_TYPES = (
    type(None),
    bool,
    int,
    float,
    complex,
    str,
    bytes,
    range,
    FunctionType,
    MethodType,
    ModuleType,
    type,
)


def _slot_names(value: object) -> tuple[str, ...]:
    names: list[str] = []
    for cls in type(value).__mro__:
        raw_slots = cls.__dict__.get("__slots__", ())
        if isinstance(raw_slots, str):
            raw_slots = (raw_slots,)
        for name in raw_slots:
            if name not in {"__dict__", "__weakref__"}:
                names.append(name)
    return tuple(dict.fromkeys(names))


def _collect_canonical_graph(
    value: Any,
    *,
    objects: dict[int, Any],
    preserved: dict[int, Any],
    excluded_ids: set[int],
) -> None:
    value_id = id(value)
    if value_id in objects or value_id in preserved or value_id in excluded_ids:
        return
    if isinstance(value, _ATOMIC_TYPES):
        return

    if isinstance(value, dict):
        objects[value_id] = value
        for key, item in value.items():
            _collect_canonical_graph(
                key,
                objects=objects,
                preserved=preserved,
                excluded_ids=excluded_ids,
            )
            _collect_canonical_graph(
                item,
                objects=objects,
                preserved=preserved,
                excluded_ids=excluded_ids,
            )
        return

    if isinstance(value, (list, set)):
        objects[value_id] = value
        for item in value:
            _collect_canonical_graph(
                item,
                objects=objects,
                preserved=preserved,
                excluded_ids=excluded_ids,
            )
        return

    if isinstance(value, tuple):
        for item in value:
            _collect_canonical_graph(
                item,
                objects=objects,
                preserved=preserved,
                excluded_ids=excluded_ids,
            )
        return

    module_name = type(value).__module__
    if not module_name.startswith("src."):
        # Runtime handles, locks, mocks and third-party objects are not part of
        # the canonical simulation graph.  Keeping their identity also keeps
        # deepcopy away from resources that cannot be cloned safely.
        preserved[value_id] = value
        return

    objects[value_id] = value
    state = getattr(value, "__dict__", None)
    if isinstance(state, dict):
        _collect_canonical_graph(
            state,
            objects=objects,
            preserved=preserved,
            excluded_ids=excluded_ids,
        )
    for name in _slot_names(value):
        if hasattr(value, name):
            _collect_canonical_graph(
                getattr(value, name),
                objects=objects,
                preserved=preserved,
                excluded_ids=excluded_ids,
            )


def _custom_content_registry_containers() -> tuple[dict[Any, Any], ...]:
    from src.classes.custom_content import CustomContentRegistry
    from src.classes.goldfinger import goldfingers_by_id, goldfingers_by_name
    from src.classes.items.auxiliary import auxiliaries_by_id, auxiliaries_by_name
    from src.classes.items.registry import ItemRegistry
    from src.classes.items.weapon import weapons_by_id, weapons_by_name
    from src.classes.technique import techniques_by_id, techniques_by_name

    return (
        CustomContentRegistry.custom_techniques_by_id,
        CustomContentRegistry.custom_weapons_by_id,
        CustomContentRegistry.custom_auxiliaries_by_id,
        CustomContentRegistry.custom_goldfingers_by_id,
        CustomContentRegistry.next_ids,
        techniques_by_id,
        techniques_by_name,
        weapons_by_id,
        weapons_by_name,
        auxiliaries_by_id,
        auxiliaries_by_name,
        goldfingers_by_id,
        goldfingers_by_name,
        ItemRegistry._items_by_id,
    )


@dataclass(slots=True)
class SimulationMonthCheckpoint:
    """In-memory undo snapshot for one simulation month.

    The event store owns its own SQL transaction.  This checkpoint owns the
    canonical in-memory graph and restores existing object identities so
    callers holding an Avatar, Region or Sect reference do not become stale
    after a failed step.
    """

    world: Any
    random_state: object
    object_pairs: tuple[tuple[Any, Any], ...]
    registry_pairs: tuple[tuple[dict[Any, Any], dict[Any, Any]], ...]
    # The runtime handles `capture` deliberately kept by identity rather than
    # cloning: tasks, locks, connections, mocks, third-party objects.  They
    # have to be held here so `restore` can seed its own memo with the *same*
    # identities.  Without them a snapshot that references, say, a finished
    # asyncio task would make restore try to deepcopy it, which raises
    # "cannot pickle" and turns a normal rollback into a crash.
    preserved_handles: tuple[Any, ...]

    @classmethod
    def capture(cls, world: Any) -> "SimulationMonthCheckpoint":
        random_state = random.getstate()
        registry_pairs = tuple(
            (container, dict(container))
            for container in _custom_content_registry_containers()
        )
        event_manager = getattr(world, "event_manager", None)
        runtime = getattr(world, "runtime", None)
        excluded = {
            id(item)
            for item in (event_manager, runtime)
            if item is not None
        }
        objects: dict[int, Any] = {}
        preserved: dict[int, Any] = {id(world): world}
        if event_manager is not None:
            preserved[id(event_manager)] = event_manager
        if runtime is not None:
            preserved[id(runtime)] = runtime

        try:
            active_sects = tuple(world.sect_context.get_active_sects())
        except (AttributeError, TypeError):
            active_sects = ()
        _collect_canonical_graph(
            world.__dict__,
            objects=objects,
            preserved=preserved,
            excluded_ids=excluded,
        )
        for sect in active_sects:
            _collect_canonical_graph(
                sect,
                objects=objects,
                preserved=preserved,
                excluded_ids=excluded,
            )
        memo = dict(preserved)
        copy.deepcopy(world.__dict__, memo)
        for sect in active_sects:
            copy.deepcopy(sect, memo)
        object_pairs = tuple(
            (original, memo[original_id])
            for original_id, original in objects.items()
            if original_id in memo and memo[original_id] is not original
        )
        return cls(
            world=world,
            random_state=random_state,
            object_pairs=object_pairs,
            registry_pairs=registry_pairs,
            preserved_handles=tuple(preserved.values()),
        )

    def restore(self) -> None:
        snapshot_to_original = {
            id(snapshot): original
            for original, snapshot in self.object_pairs
        }
        snapshot_to_original[id(self.world)] = self.world
        # Same rule as capture, and it must be the same rule: a preserved
        # handle is restored as itself, never copied.
        for handle in self.preserved_handles:
            snapshot_to_original.setdefault(id(handle), handle)

        for original, snapshot in self.object_pairs:
            if isinstance(original, dict):
                restored = copy.deepcopy(dict(snapshot), snapshot_to_original)
                original.clear()
                original.update(restored)
                continue
            if isinstance(original, list):
                original[:] = copy.deepcopy(list(snapshot), snapshot_to_original)
                continue
            if isinstance(original, set):
                restored = copy.deepcopy(set(snapshot), snapshot_to_original)
                original.clear()
                original.update(restored)
                continue

            snapshot_state = getattr(snapshot, "__dict__", None)
            original_state = getattr(original, "__dict__", None)
            if isinstance(snapshot_state, dict) and isinstance(original_state, dict):
                restored = copy.deepcopy(dict(snapshot_state), snapshot_to_original)
                original_state.clear()
                original_state.update(restored)

            for name in _slot_names(snapshot):
                if hasattr(snapshot, name):
                    # Slot-backed value objects may be frozen dataclasses.
                    # Rollback is restoring their checkpointed identity, not
                    # performing a domain mutation, so bypass their public
                    # immutability guard just as deepcopy does.
                    object.__setattr__(
                        original,
                        name,
                        copy.deepcopy(getattr(snapshot, name), snapshot_to_original),
                    )

        for container, snapshot in self.registry_pairs:
            container.clear()
            container.update(snapshot)

        random.setstate(self.random_state)
        mechanical_language = getattr(self.world, "mechanical_language", None)
        if mechanical_language is not None and hasattr(mechanical_language, "bind_world"):
            mechanical_language.bind_world(self.world)
        event_manager = getattr(self.world, "event_manager", None)
        if event_manager is not None and hasattr(event_manager, "set_subject_resolver"):
            event_manager.set_subject_resolver(
                lambda avatar_id: self.world.avatar_manager.get_avatar(str(avatar_id))
            )

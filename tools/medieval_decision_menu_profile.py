"""Read-only profile of a saved world's monthly institutional menu work.

The checkpoint is only opened for reading. Save timing writes an independent
temporary copy, then loads that copy so checkpoint load and round-trip load are
reported separately. The monthly measurement enumerates the actual monthly
actors, recomposes each actor's current affordance menu, and builds its
composed context without asking a provider or executing a decision.
"""

import argparse
from contextlib import redirect_stdout
import cProfile
import json
from pathlib import Path
import pstats
import sys
import tempfile
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Configuration initialization emits a human-readable language notice. Keep
# import-time diagnostics off stdout so the CLI remains composable as JSON.
with redirect_stdout(sys.stderr):
    from src.sim.medieval.institutional_agenda import monthly_actors, monthly_adapters
    from src.sim.medieval.institutional_decision_turn import _by_id, _composed_situation
    from src.sim.medieval.persistence import load_world, save_world, world_snapshot


def _seconds(call):
    started = perf_counter()
    result = call()
    return result, perf_counter() - started


def _profile_summary(profile, limit):
    stats = pstats.Stats(profile)
    rows = []
    for (filename, line, function), (primitive, calls, self_seconds, cumulative, _callers) in sorted(
            stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:limit]:
        rows.append({
            "function": f"{Path(filename).name}:{line}:{function}",
            "calls": calls,
            "primitive_calls": primitive,
            "self_seconds": round(self_seconds, 6),
            "cumulative_seconds": round(cumulative, 6),
        })
    return rows


def _build_monthly_menus(world):
    adapters = monthly_adapters()
    actors = monthly_actors(world)
    option_count = 0
    actors_with_options = 0
    situation_count = 0
    for actor in actors:
        by_id = _by_id(world, actor, adapters)
        if by_id:
            actors_with_options += 1
            option_count += len(by_id)
            _composed_situation(world, actor, by_id)
            situation_count += 1
    return {
        "actor_count": len(actors),
        "actors_with_options": actors_with_options,
        "option_count": option_count,
        "composed_situation_count": situation_count,
    }


def profile_checkpoint(checkpoint_path: Path, *, profile_limit=25):
    checkpoint_path = Path(checkpoint_path).resolve(strict=True)
    world, checkpoint_load_seconds = _seconds(lambda: load_world(checkpoint_path))
    snapshot, snapshot_seconds = _seconds(lambda: world_snapshot(world))
    # Do not place this copy beside the source save: benchmark output must not
    # alter the source checkpoint or add artifacts to its directory.
    with tempfile.TemporaryDirectory(prefix="medieval-menu-profile-") as temp_dir:
        copy_path = Path(temp_dir) / "roundtrip.mws"
        _saved, save_seconds = _seconds(lambda: save_world(world, copy_path))
        _roundtrip_world, roundtrip_load_seconds = _seconds(lambda: load_world(copy_path))

    profile = cProfile.Profile()
    started = perf_counter()
    profile.enable()
    menu_metrics = _build_monthly_menus(world)
    profile.disable()
    menu_seconds = perf_counter() - started

    return {
        "checkpoint": str(checkpoint_path),
        "clock_day": world.clock.absolute_day,
        "event_count": len(world.events),
        "measurements": {
            "checkpoint_load_seconds": round(checkpoint_load_seconds, 6),
            "snapshot_seconds": round(snapshot_seconds, 6),
            "snapshot_event_count": snapshot.get("event_count"),
            "save_copy_seconds": round(save_seconds, 6),
            "roundtrip_load_seconds": round(roundtrip_load_seconds, 6),
            "monthly_decision_menu_seconds": round(menu_seconds, 6),
            **menu_metrics,
        },
        "menu_profile_top_cumulative": _profile_summary(profile, profile_limit),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path, help="path to a .mws checkpoint")
    parser.add_argument("--profile-limit", type=int, default=25,
                        help="number of cumulative profile entries to include (default: 25)")
    args = parser.parse_args(argv)
    if args.profile_limit < 1:
        parser.error("--profile-limit must be positive")
    print(json.dumps(profile_checkpoint(args.checkpoint, profile_limit=args.profile_limit),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

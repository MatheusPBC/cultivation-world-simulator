"""Profile a bounded canonical horizon from a saved medieval checkpoint.

The input save is read once and never overwritten.  The loaded world advances
only in memory through the autonomy smoke's normal no-provider execution path;
this tool writes no successor save or other artifact.
"""

import argparse
import asyncio
from contextlib import redirect_stdout
import cProfile
from hashlib import sha256
import json
from pathlib import Path
import pstats
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Keep configuration-import notices out of stdout: this tool's stdout is a
# machine-readable profiling report.
with redirect_stdout(sys.stderr):
    from src.sim.medieval.persistence import load_world
    from tools import medieval_autonomy_smoke


def _source_digest(path):
    return sha256(path.read_bytes()).hexdigest()


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


async def profile_checkpoint_horizon(checkpoint_path, *, days=30, profile_limit=25):
    """Return a cProfile report for advancing ``days`` beyond ``checkpoint_path``.

    This deliberately has no output-save argument: advancing is observable only
    in the process-local loaded object, so callers cannot accidentally replace
    the source checkpoint while measuring it.
    """
    checkpoint_path = Path(checkpoint_path).resolve(strict=True)
    if type(days) is not int or days <= 0 or days % 30:
        raise ValueError("days must be a positive multiple of 30")
    if type(profile_limit) is not int or profile_limit <= 0:
        raise ValueError("profile_limit must be positive")

    source_digest_before = _source_digest(checkpoint_path)
    world = load_world(checkpoint_path)
    source_ai_enabled = world.config.ai_enabled
    # Profiling must never turn a saved provider-enabled world into an external
    # provider call.  This is an in-memory policy override only, matching the
    # smoke's ordinary no-provider run; the source save is not rewritten.
    if source_ai_enabled:
        world.config = world.config.model_copy(update={"ai_enabled": False})
    start_day = world.clock.absolute_day
    start_event_count = len(world.events)
    target_day = start_day + days

    profile = cProfile.Profile()
    started = perf_counter()
    profile.enable()
    jumps = await medieval_autonomy_smoke.advance_world(world, target_day)
    profile.disable()
    elapsed_seconds = perf_counter() - started

    source_digest_after = _source_digest(checkpoint_path)
    source_unchanged = source_digest_before == source_digest_after
    if not source_unchanged:
        raise RuntimeError("source checkpoint changed during read-only profile")

    return {
        "source_checkpoint": str(checkpoint_path),
        "source_save_overwritten": False,
        "source_save_unchanged": True,
        "in_memory_only": True,
        "provider_mode": "normal-no-provider-policy",
        "source_ai_enabled": source_ai_enabled,
        "start": {"day": start_day, "event_count": start_event_count},
        "target": {"day": world.clock.absolute_day, "event_count": len(world.events)},
        "advanced_days": days,
        "jumps": jumps,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "profile_top_cumulative": _profile_summary(profile, profile_limit),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path, help="path to an existing .mws checkpoint")
    parser.add_argument("--days", type=int, default=30,
                        help="additional canonical horizon in days (default: 30; multiple of 30)")
    parser.add_argument("--profile-limit", type=int, default=25,
                        help="number of cumulative profile entries to include (default: 25)")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(profile_checkpoint_horizon(
            args.checkpoint, days=args.days, profile_limit=args.profile_limit))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the provider-free causal torture harness from the repository root."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run isolated deterministic causal-world torture tests."
    )
    parser.add_argument("--worlds", type=int, default=10)
    parser.add_argument("--months", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--map-id", default="classic")
    parser.add_argument(
        "--profile",
        default="baseline",
        choices=(
            "baseline",
            "population_pressure",
            "resource_shortage",
            "blocked_resource_shortage",
            "urban_service_strain",
            "institutional_urban_strain",
            "health_recovery_strain",
        ),
        help="Apply a generic causal-probe profile selected from world state.",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


async def _build_report(args: argparse.Namespace):
    from src.systems.causal_observatory import (
        CausalTortureConfig,
        CausalTortureRunner,
    )

    config = CausalTortureConfig(
        worlds=args.worlds,
        months=args.months,
        seed=args.seed,
        map_id=args.map_id,
        probe_profile=args.profile,
        test_mode=True,
        provider="test",
    )
    return await CausalTortureRunner(config).run()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.as_json:
            diagnostics = io.StringIO()
            with contextlib.redirect_stdout(diagnostics):
                report = asyncio.run(_build_report(args))
            captured = diagnostics.getvalue()
            if captured:
                print(captured, file=sys.stderr, end="")
            print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
        else:
            report = asyncio.run(_build_report(args))
            print(json.dumps(report.totals, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f"causal torture test blocked: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

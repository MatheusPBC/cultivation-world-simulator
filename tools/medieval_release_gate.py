"""Run the final medieval verification matrix and emit one auditable report.

Natural worlds are allowed to remain quiet.  A pressured run is separate and
must demonstrate the institutional aid chain.  This tool only composes the
existing smoke and causal-audit tools; it does not add a simulator, fallback
policy or material effect.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))



async def _run_smoke(*args, **kwargs):
    """Keep the gate's stdout a single JSON report.

    The smoke intentionally emits progress lines for interactive runs.  The
    release gate is also consumed by scripts, so route those lines to stderr
    instead of producing a file that merely looks like JSON but cannot be
    parsed.
    """
    with redirect_stdout(sys.stderr):
        from tools import medieval_autonomy_smoke
        return await medieval_autonomy_smoke.run(*args, **kwargs)


def _audit(path: Path) -> dict:
    with redirect_stdout(sys.stderr):
        from tools.medieval_causal_audit import audit
        return audit(path)


async def run_gate(seeds: tuple[int, ...], days: int, output_dir: Path, *, pressured: bool,
                   economic: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    natural = []
    for seed in seeds:
        save = output_dir / f"natural-{seed}.mws"
        result = await _run_smoke(seed, days, save)
        natural.append({"result": result, "audit": _audit(save)})

    pressured_run = None
    if pressured:
        seed = seeds[0]
        save = output_dir / f"pressured-socorro-{seed}.mws"
        result = await _run_smoke(seed, days, save, gov_profile="socorro")
        pressured_run = {"result": result, "audit": _audit(save)}

    economic_run = None
    if economic:
        # Same seed and horizon, explicit actor policies.  The engine is
        # unchanged: every profile selects only an engine-enumerated ID.  The
        # comparison therefore measures material alternatives, not a hidden
        # safety net.
        comparison = {}
        for profile in ("desatento", "alivio", "mercado", "mobilidade"):
            save = output_dir / f"economic-{profile}-{seeds[0]}.mws"
            result = await _run_smoke(
                seeds[0], days, save, gov_profile=profile)
            comparison[profile] = {"result": result, "audit": _audit(save)}
        quiet = comparison["desatento"]
        relief = comparison["alivio"]
        market = comparison["mercado"]
        mobility = comparison["mobilidade"]
        economic_run = {
            "comparison": comparison,
            "same_seed": True,
            "relief_selected": relief["result"]["relief_given_total"] > 0,
            "market_selected": market["result"]["market_purchases_total"] > 0,
            "mobility_selected": (
                mobility["result"].get("permanent_employment_total", 0) > 0
                or mobility["result"].get("workforce_transitions_total", 0) > 0),
            "resource_conserved": all(
                item["result"]["money_conserved"] and item["result"]["all_resources_accounted"]
                and item["result"]["save_load_equivalent"] and item["audit"]["ok"]
                for item in comparison.values()),
            "different_material_outcome": len({
                (item["result"]["missing_food_total"], item["result"]["mean_health"],
                 item["result"].get("unrest_total"))
                for item in comparison.values()
            }) > 1,
        }
        economic_run["ok"] = (economic_run["same_seed"] and economic_run["relief_selected"]
                               and economic_run["market_selected"]
                               and economic_run["mobility_selected"]
                               and economic_run["resource_conserved"]
                               and economic_run["different_material_outcome"])

    natural_ok = all(item["audit"]["ok"] and item["result"]["save_load_equivalent"]
                      and item["result"]["money_conserved"]
                      and item["result"]["all_resources_accounted"] for item in natural)
    pressured_ok = (not pressured or (
        pressured_run["audit"]["ok"]
        and pressured_run["result"]["save_load_equivalent"]
        and pressured_run["result"]["aid_requests_total"] > 0
        and pressured_run["result"]["aid_fulfilled_total"] > 0
    ))
    return {
        "days": days,
        "seeds": list(seeds),
        "natural": natural,
        "pressured": pressured_run,
        "economic": economic_run,
        "natural_ok": natural_ok,
        "pressured_ok": pressured_ok,
        "ok": natural_ok and pressured_ok and (economic_run is None or economic_run["ok"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="73,101,137",
                        help="comma-separated natural seeds (default: 73,101,137)")
    parser.add_argument("--days", type=int, default=120,
                        help="horizon in days; use 3600 for the final ten-year gate")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pressured", action="store_true",
                        help="also run the socorro fixture and require aid request/fulfillment")
    parser.add_argument("--economic", action="store_true",
                        help="compare the same pressured seed with NO_ACTION and explicit relief policies")
    args = parser.parse_args()
    try:
        seeds = tuple(int(item.strip()) for item in args.seeds.split(",") if item.strip())
    except ValueError as exc:
        parser.error(f"invalid seed list: {exc}")
    if not seeds or args.days <= 0 or args.days % 30:
        parser.error("seeds must be non-empty and days must be a positive multiple of 30")
    report = asyncio.run(run_gate(seeds, args.days, args.output_dir,
                                  pressured=args.pressured, economic=args.economic))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

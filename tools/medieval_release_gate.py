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
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The deterministic government profiles are provider-bound fixtures, not a
# budget experiment.  The monthly menu now includes organizations and
# population groups as well as polities, so the old eight-call allowance could
# abort halfway through a valid fixture with ``ProviderDecisionRequired``.
# Keep the allowance explicit and generous here; budget/latency behavior is
# exercised by the separate provider probe and decision-turn tests.
FIXTURE_AI_CALLS_PER_STEP = 256
V1_BUDGET = {
    "run_s": 3600,
    "peak_rss_bytes": 4 * 1024**3,
    "save_bytes": 512 * 1024**2,
    "save_s": 60,
    "load_s": 60,
    "monthly_p95_s": 35,
    "why_p95_s": 2,
}


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


def _checkpoint_audits(result: dict) -> list[dict]:
    return [_audit(Path(item["path"])) for item in result["checkpoints"]]


def _why_latency(save: Path) -> dict:
    """Measure 20 distributed canonical causal queries on the final save."""
    with redirect_stdout(sys.stderr):
        from src.sim.medieval.persistence import load_world
        from src.server.medieval.queries import causal_view
        world = load_world(save)
    linked = [event.id for event in world.events if event.causal_links]
    if len(linked) < 20:
        raise ValueError("final V1 gate needs at least 20 causally linked events")
    samples = []
    for index in range(20):
        event_id = linked[index * (len(linked) - 1) // 19]
        started = perf_counter()
        view = causal_view(world, event_id, after=0, limit=100)
        samples.append(perf_counter() - started)
        expected_causes = {link.cause_event_id for link in view.event.causal_links}
        if (view.event.id != event_id
                or {cause.id for cause in view.causes} != expected_causes
                or not expected_causes
                or any(not any(link.cause_event_id == event_id for link in effect.causal_links)
                       for effect in view.effects)):
            raise ValueError("why() returned an unnavigable causal link")
    return {"queries": len(samples), "p95_s": round(sorted(samples)[18], 4),
            "links_verified": True}


def _v1_budget_result(result: dict, why: dict) -> dict:
    """Apply the frozen pre-gate limits, never a post-hoc adjusted budget."""
    observed = {
        "run_s": result["elapsed_s"],
        "peak_rss_bytes": result["memory_high_water_bytes"],
        "save_bytes": result["save_bytes"],
        "save_s": result["save_elapsed_s"],
        "load_s": result["load_elapsed_s"],
        "monthly_p95_s": result["monthly_p95_seconds"],
        "why_p95_s": why["p95_s"],
    }
    checks = {name: observed[name] is not None and observed[name] <= limit
              for name, limit in V1_BUDGET.items()}
    checks["monthly_samples"] = len(result["monthly_advance_seconds"]) == 120
    checks["why_samples"] = why["queries"] == 20
    checks["why_links"] = why["links_verified"] is True
    return {"limits": dict(V1_BUDGET), "observed": observed, "checks": checks,
            "ok": all(checks.values())}


async def run_gate(seeds: tuple[int, ...], days: int, output_dir: Path, *, pressured: bool,
                   economic: bool = False, checkpoint_days: int | None = None,
                   final_v1: bool = False) -> dict:
    if final_v1 and (days != 3600 or len(seeds) != 3 or len(set(seeds)) != 3
                     or pressured or economic or checkpoint_days is None
                     or checkpoint_days <= 0
                     or checkpoint_days > 360 or 3600 % checkpoint_days):
        raise ValueError("final V1 gate requires three natural seeds, 3600 days and annual-or-finer checkpoints")
    if final_v1 and any((output_dir / f"natural-{seed}.mws").exists() for seed in seeds):
        raise ValueError("final V1 gate refuses to overwrite an existing natural save")
    output_dir.mkdir(parents=True, exist_ok=True)
    natural = []
    for seed in seeds:
        save = output_dir / f"natural-{seed}.mws"
        result = await _run_smoke(seed, days, save, checkpoint_days=checkpoint_days)
        checkpoint_audits = _checkpoint_audits(result)
        natural.append({"result": result, "audit": _audit(save),
                        "checkpoint_audits": checkpoint_audits,
                        "budget": (_v1_budget_result(result, _why_latency(save))
                                   if final_v1 else None)})

    pressured_run = None
    if pressured:
        seed = seeds[0]
        save = output_dir / f"pressured-socorro-{seed}.mws"
        result = await _run_smoke(seed, days, save, gov_profile="socorro",
                                  ai_calls_per_step=FIXTURE_AI_CALLS_PER_STEP,
                                  checkpoint_days=checkpoint_days)
        pressured_run = {"result": result, "audit": _audit(save),
                         "checkpoint_audits": _checkpoint_audits(result)}

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
                seeds[0], days, save, gov_profile=profile,
                ai_calls_per_step=FIXTURE_AI_CALLS_PER_STEP,
                checkpoint_days=checkpoint_days)
            comparison[profile] = {"result": result, "audit": _audit(save),
                                   "checkpoint_audits": _checkpoint_audits(result)}
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
                and all(audit["ok"] for audit in item["checkpoint_audits"])
                and all(checkpoint["conservation"] and checkpoint["save_load_equivalent"]
                        for checkpoint in item["result"]["checkpoints"])
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

    natural_ok = all(item["audit"]["ok"]
                      and all(audit["ok"] for audit in item["checkpoint_audits"])
                      and all(checkpoint["conservation"] and checkpoint["save_load_equivalent"]
                              for checkpoint in item["result"]["checkpoints"])
                      and item["result"]["save_load_equivalent"]
                      and item["result"]["money_conserved"]
                      and item["result"]["all_resources_accounted"]
                      and (not final_v1 or item["budget"]["ok"]) for item in natural)
    pressured_ok = (not pressured or (
        pressured_run["audit"]["ok"]
        and all(audit["ok"] for audit in pressured_run["checkpoint_audits"])
        and all(checkpoint["conservation"] and checkpoint["save_load_equivalent"]
                for checkpoint in pressured_run["result"]["checkpoints"])
        and pressured_run["result"]["save_load_equivalent"]
        and pressured_run["result"]["aid_requests_total"] > 0
        and pressured_run["result"]["aid_fulfilled_total"] > 0
    ))
    return {
        "days": days,
        "checkpoint_days": checkpoint_days,
        "seeds": list(seeds),
        "natural": natural,
        "pressured": pressured_run,
        "economic": economic_run,
        "final_v1": final_v1,
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
    parser.add_argument("--checkpoint-days", type=int, default=None,
                        help="write and audit a distinct save at each positive multiple-of-30-day interval")
    parser.add_argument("--final-v1", action="store_true",
                        help="enforce the frozen 10-year V1 budgets on three natural seeds")
    args = parser.parse_args()
    try:
        seeds = tuple(int(item.strip()) for item in args.seeds.split(",") if item.strip())
    except ValueError as exc:
        parser.error(f"invalid seed list: {exc}")
    if not seeds or args.days <= 0 or args.days % 30:
        parser.error("seeds must be non-empty and days must be a positive multiple of 30")
    if args.checkpoint_days is not None and (args.checkpoint_days <= 0 or args.checkpoint_days % 30):
        parser.error("checkpoint-days must be a positive multiple of 30")
    if args.final_v1 and (args.days != 3600 or len(seeds) != 3 or len(set(seeds)) != 3
                          or args.pressured or args.economic or args.checkpoint_days is None
                          or args.checkpoint_days <= 0
                          or args.checkpoint_days > 360 or 3600 % args.checkpoint_days):
        parser.error("--final-v1 requires three natural seeds, --days 3600 and annual-or-finer checkpoints")
    report = asyncio.run(run_gate(seeds, args.days, args.output_dir,
                                  pressured=args.pressured, economic=args.economic,
                                  checkpoint_days=args.checkpoint_days,
                                  final_v1=args.final_v1))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

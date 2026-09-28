"""Run at most ten real provider consultations on audited, in-memory worlds.

Without --allow-provider-egress this only repeats the local corpus preview.
No raw prompt, provider answer or mutated world is persisted or printed.
"""

from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sim.medieval import ai_decider
from src.sim.medieval.activities import validate_activities
from src.sim.medieval.creature_policy import _creature_turn
from src.sim.medieval.creatures import creature_options
from src.sim.medieval.events import validate_history
from src.sim.medieval.persistence import load_world, world_snapshot
from src.utils.llm import client as llm_client
from tools.medieval_provider_civil_probe import probe as civil_probe
from tools.medieval_provider_corpus_preview import _civil, preview
from tools.medieval_provider_route_review_probe import probe as route_probe

MAX_CALLS = 10
CREATURE_ID = "creature:drake-do-lume"


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


async def _creature_probe(path: Path) -> dict:
    before = _digest(path)
    world = load_world(path)
    options = {item.id for item in creature_options(world, CREATURE_ID)}
    if len(options) < 2:
        raise ValueError("creature has no current choice")
    previous_count = len(world.events)
    previous_calls = ai_decider.spent_calls(world, since_day=world.clock.absolute_day)
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": previous_calls + 1, "ai_max_calls": 0,
    })
    started = perf_counter()
    try:
        await _creature_turn(world, CREATURE_ID)
    finally:
        if _digest(path) != before:
            raise ValueError("source save changed during creature probe")
    suffix = world.events[previous_count:]
    receipts = [event for event in suffix if event.event_type in ai_decider.RECEIPT_EVENTS]
    if len(receipts) != 1 or receipts[0].deltas:
        raise ValueError("creature consultation lacks one zero-delta receipt")
    selected = (receipts[0].causal_payload or {}).get("selection", {}).get("selected_affordance_id")
    if selected not in options and selected != ai_decider.NO_ACTION:
        raise ValueError("creature selected an ID outside its current options")
    validate_history(world.events, world.clock.absolute_day, from_sequence=previous_count + 1)
    world_snapshot(world)
    validate_activities(world)
    return {"actor_ref": {"kind": "creature", "id": CREATURE_ID},
            "source_sha256_unchanged": before, "selected_id": selected,
            "offered_count": len(options), "receipt_event_id": receipts[0].id,
            "receipt_has_deltas": False,
            "material_event_count": sum(bool(event.deltas) for event in suffix),
            "elapsed_s": round(perf_counter() - started, 3), "persisted": False}


async def run(natural: Path, commitment: Path, priorities: Path, route: Path,
              natural_101: Path, natural_14: Path, *, allow_provider_egress: bool) -> dict:
    ready = await preview(natural, commitment, priorities, route, natural_101, natural_14)
    if not allow_provider_egress:
        return ready
    if not ai_decider.provider_available():
        raise ValueError("real provider is not configured")

    # Route decisions can remove the second military turn. Prepare one extra
    # distinct civil actor-state so the cap remains ten, never eleven.
    _civil(natural_14, "escarlia", {"aid_request", "relief"})
    sources = (natural, commitment, priorities, route, natural_101, natural_14)
    source_hashes = {path.resolve(): _digest(path) for path in sources}
    calls: list[dict] = []
    original_call = llm_client.call_llm_json

    async def tracked_call(prompt, *args, **kwargs):
        if len(calls) >= MAX_CALLS:
            raise ValueError("provider corpus cap of ten calls reached")
        call = {"prompt_bytes": len(prompt.encode()), "elapsed_s": None}
        calls.append(call)
        started = perf_counter()
        try:
            return await original_call(prompt, *args, **kwargs)
        finally:
            call["elapsed_s"] = round(perf_counter() - started, 3)

    cases = []
    failed_case = None
    failure_type = None
    case_name = "route_campaign"
    try:
        with patch.object(llm_client, "call_llm_json", tracked_call):
            route_result = await route_probe(route)
            cases.append({"case": case_name, "result": route_result})
            print(json.dumps({"completed_case": case_name, "consultations": len(calls)}),
                  file=sys.stderr, flush=True)
            case_name = "creature"
            cases.append({"case": case_name, "result": await _creature_probe(natural)})
            print(json.dumps({"completed_case": case_name, "consultations": len(calls)}),
                  file=sys.stderr, flush=True)
            civil_cases = [
                ("economy", natural, "auren"),
                ("near_deadline", commitment, "escarlia"),
                ("food_vs_defense", priorities, "escarlia"),
                ("seed101_auren", natural_101, "auren"),
                ("seed101_escarlia", natural_101, "escarlia"),
                ("seed14_auren", natural_14, "auren"),
                ("seed14_valedouro", natural_14, "valedouro"),
                ("reserve_seed14_escarlia", natural_14, "escarlia"),
            ]
            for case_name, path, polity_id in civil_cases[:MAX_CALLS - len(calls)]:
                cases.append({"case": case_name, "result": await civil_probe(path, polity_id)})
                print(json.dumps({"completed_case": case_name, "consultations": len(calls)}),
                      file=sys.stderr, flush=True)
    except Exception as exc:
        failed_case, failure_type = case_name, type(exc).__name__

    sources_unchanged = all(_digest(path) == source_hashes[path.resolve()] for path in sources)
    complete = failed_case is None and len(calls) == MAX_CALLS and sources_unchanged
    return {"complete": complete, "consultations": len(calls), "cases": cases,
            "failed_case": failed_case, "failure_type": failure_type,
            "prompt_bytes_total": sum(call["prompt_bytes"] for call in calls),
            "provider_call_seconds": [call["elapsed_s"] for call in calls],
            "cost_usd": None, "cost_note": "provider client exposes no usage or price metadata",
            "raw_prompts_emitted": False, "source_saves_unchanged": sources_unchanged}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--natural", type=Path, required=True)
    parser.add_argument("--commitment", type=Path, required=True)
    parser.add_argument("--priorities", type=Path, required=True)
    parser.add_argument("--route", type=Path, required=True)
    parser.add_argument("--natural-101", type=Path, required=True)
    parser.add_argument("--natural-14", type=Path, required=True)
    parser.add_argument("--allow-provider-egress", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run(args.natural, args.commitment, args.priorities,
                             args.route, args.natural_101, args.natural_14,
                             allow_provider_egress=args.allow_provider_egress))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not args.allow_provider_egress or result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Probe the commander and HQ route response on an audited pre-review save.

Only the two scheduled military reviews are consulted. Dated owners still
resolve their due physical work first. The source save is never persisted or
modified; this bounded diagnostic does not claim to be a full world tick.
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

from src.classes.causal_origin import CausalOrigin
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import validate_history
from src.sim.medieval.force_contact_policy import review_force_contacts
from src.sim.medieval.persistence import load_world, world_snapshot
from src.sim.medieval.strategy_response import review_strategy_responses_with_provider


async def probe(source: Path, *, headquarters_only: bool = False) -> dict:
    source = source.resolve()
    source_hash = sha256(source.read_bytes()).hexdigest()
    world = load_world(source)
    if not ai_decider.provider_available():
        raise ValueError("real provider is not configured")
    if world.clock.absolute_day + 1 not in world.agenda.due_days:
        raise ValueError("source has no next-day dated review")
    world.config = world.config.model_copy(update={
        "ai_enabled": True,
        "ai_calls_per_step": 2,
        "ai_max_calls": 0,
    })
    previous_count = len(world.events)
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    calls = []
    original_select = ai_decider.select_option

    async def tracked_select(candidate, actor, situation, choices, *, causes=()):
        started = perf_counter()
        selected = await original_select(candidate, actor, situation, choices, causes=causes)
        offered = {item["id"] for item in choices}
        if selected not in offered and selected != ai_decider.NO_ACTION:
            raise ValueError("provider selected an ID outside the current options")
        receipts = [event for event in candidate.events[previous_count:]
                    if event.event_type in ai_decider.RECEIPT_EVENTS]
        if not receipts or receipts[-1].deltas:
            raise ValueError("provider consultation lacks a zero-delta receipt")
        receipt = receipts[-1]
        if receipt.causal_origin is not CausalOrigin.LLM_INTERPRETATION:
            raise ValueError("provider receipt has the wrong causal origin")
        calls.append({
            "actor_ref": actor.to_dict(),
            "offered_ids": sorted(offered),
            "selected_id": selected,
            "receipt_event_id": receipt.id,
            "elapsed_s": round(perf_counter() - started, 3),
        })
        return selected

    try:
        with patch.object(ai_decider, "select_option", tracked_select):
            if not headquarters_only:
                await review_force_contacts(world, due)
            await review_strategy_responses_with_provider(world, due)
    finally:
        if sha256(source.read_bytes()).hexdigest() != source_hash:
            raise ValueError("source save changed during route review probe")

    maximum_calls = 1 if headquarters_only else 2
    if not calls or len(calls) > maximum_calls:
        raise ValueError("route review exceeded its bounded provider consultation count")
    validate_history(world.events, world.clock.absolute_day,
                     from_sequence=previous_count + 1)
    world_snapshot(world)
    suffix = world.events[previous_count:]
    return {
        "source_save": str(source),
        "source_sha256_unchanged": source_hash,
        "day": world.clock.absolute_day,
        "scope": ("dated_hq_route_review_only" if headquarters_only
                  else "dated_commander_and_hq_route_reviews_only"),
        "calls": calls,
        "material_event_count": sum(bool(event.deltas) for event in suffix),
        "story_material_event_count": sum(bool(event.deltas) and event.event_type.startswith("story")
                                          for event in suffix),
        "persisted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--headquarters-only", action="store_true",
                        help="Consult only the separate headquarters review, leaving the commander turn untouched.")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(probe(args.source, headquarters_only=args.headquarters_only)),
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

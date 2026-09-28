"""Probe one real provider choice on a saved polity's full monthly menu.

The loaded world is forked in memory. The normal composed menu, provider
receipt, decision and owner executor run on the fork only; the source save is
hashed before and after. This is a bounded provider diagnostic, not a smoke
or evidence that a natural world chose the same action.
"""

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.activities import validate_activities
from src.sim.medieval.events import validate_history
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.institutional_decision_turn import (
    _by_id,
    review_institutional_decision_turn,
)
from src.sim.medieval.persistence import load_world


def _run_probe(coroutine):
    """Run this one-shot probe without asyncio's blocking executor shutdown."""
    loop = asyncio.new_event_loop()
    executor = ThreadPoolExecutor()
    asyncio.set_event_loop(loop)
    loop.set_default_executor(executor)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        # The Codex CLI transport is synchronous and bounded. Shut its worker
        # down explicitly before closing the loop; asyncio.run() can otherwise
        # hang in shutdown_default_executor after a provider exception.
        try:
            executor.shutdown(wait=True)
        finally:
            loop.close()
            asyncio.set_event_loop(None)


async def probe(save_path: Path, polity_id: str):
    source_digest = sha256(save_path.read_bytes()).hexdigest()
    world = load_world(save_path)
    if polity_id not in world.society.polities:
        raise ValueError("unknown polity")
    actor = EntityRef("polity", polity_id)
    candidate = world.transaction_copy()
    adapters = monthly_adapters()
    options = _by_id(candidate, actor, adapters)
    if not options:
        raise ValueError("the polity has no current monthly affordance")
    if not ai_decider.provider_available():
        raise ValueError("real provider is not configured")
    previous_count = len(candidate.events)
    previous_calls = ai_decider.spent_calls(candidate, since_day=candidate.clock.absolute_day)
    candidate.config = candidate.config.model_copy(update={
        "ai_enabled": True,
        "ai_calls_per_step": previous_calls + 1,
        "ai_max_calls": 0,
    })
    started = perf_counter()
    try:
        claims, covered = await review_institutional_decision_turn(candidate, actor, adapters)
    finally:
        # A rejected, timed-out or stale provider answer must leave the
        # on-disk world just as untouched as a successful in-memory probe.
        if sha256(save_path.read_bytes()).hexdigest() != source_digest:
            raise ValueError("source save changed during provider probe")
    elapsed = perf_counter() - started
    suffix = candidate.events[previous_count:]
    receipts = [event for event in suffix if event.event_type in ai_decider.RECEIPT_EVENTS]
    if len(receipts) != 1:
        raise ValueError("expected exactly one provider receipt")
    receipt = receipts[0]
    selection = (receipt.causal_payload or {}).get("selection", {})
    selected_id = selection.get("selected_affordance_id")
    if selected_id not in options and selected_id != ai_decider.NO_ACTION:
        raise ValueError("provider selected an option outside the canonical menu")
    if receipt.deltas:
        raise ValueError("provider receipt mutated material state")
    validate_history(candidate.events, candidate.clock.absolute_day,
                     from_sequence=previous_count + 1)
    candidate.__post_init__()
    validate_activities(candidate)
    material_events = [event for event in suffix if event.deltas]
    return {
        "source_save": str(save_path),
        "source_sha256_unchanged": source_digest,
        "day": candidate.clock.absolute_day,
        "actor_ref": actor.to_dict(),
        "menu_scope": "full_monthly_institutional_menu",
        "offered_count": len(options),
        "offered_families": sorted({adapter.family_key() for adapter, _ in options.values()}),
        "selected_id": selected_id,
        "selection_valid": selected_id in options or selected_id == ai_decider.NO_ACTION,
        "receipt_event_id": receipt.id,
        "receipt_type": receipt.event_type,
        "receipt_has_deltas": bool(receipt.deltas),
        "covered": covered,
        "claims": {kind: len(items) for kind, items in claims.items()},
        "suffix_event_count": len(suffix),
        "material_event_count": len(material_events),
        "state_delta_count": sum(len(event.deltas) for event in material_events),
        "elapsed_s": round(elapsed, 3),
        "persisted": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", required=True, type=Path)
    parser.add_argument("--polity", required=True)
    args = parser.parse_args()
    result = _run_probe(probe(args.save, args.polity))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

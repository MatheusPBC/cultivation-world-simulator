"""Ask Luna once after a real aid obligation is fulfilled in an in-memory fork.

The fulfillment is an explicit API-sourced fixture decision, not a provider
choice. The old affordance must disappear before the provider sees the new
canonical menu. No save or raw prompt is written.
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

from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.activities import validate_activities
from src.sim.medieval.events import validate_history
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.institutional_aid import aid_fulfillment_options, fulfill_institutional_aid
from src.sim.medieval.institutional_decision_turn import _by_id, review_institutional_decision_turn
from src.sim.medieval.persistence import load_world, world_snapshot
from src.utils.llm import client as llm_client
from tools.medieval_provider_commitment_fixture import _setup_decision


async def probe(source: Path, previous_id: str, *, allow_provider_egress: bool) -> dict:
    source = source.resolve()
    before = sha256(source.read_bytes()).hexdigest()
    world = load_world(source)
    actor = EntityRef("polity", "valedouro")
    current = {option.id: option for option in aid_fulfillment_options(world, actor)}
    if previous_id not in current:
        raise ValueError("the previously selected fulfillment is not current in the source")
    if not allow_provider_egress:
        return {"source_sha256": before, "old_option_current_before": True,
                "real_provider_calls": 0}
    if not ai_decider.provider_available():
        raise ValueError("real provider is not configured")

    setup_start = len(world.events)
    decision = _setup_decision(world, current[previous_id], "corpus_setup_aid_fulfillment")
    fulfill_institutional_aid(world, actor, previous_id, decision.id)
    setup_events = world.events[setup_start:]
    options = _by_id(world, actor, monthly_adapters())
    if previous_id in options or not options:
        raise ValueError("fulfillment did not replace the old affordance with a new menu")
    previous_calls = ai_decider.spent_calls(world, since_day=world.clock.absolute_day)
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": previous_calls + 1, "ai_max_calls": 0,
    })
    provider_start = len(world.events)
    calls = 0
    original_call = llm_client.call_llm_json

    async def one_call(prompt, *args, **kwargs):
        nonlocal calls
        if calls:
            raise ValueError("paired cause probe allows only one provider call")
        calls += 1
        return await original_call(prompt, *args, **kwargs)

    started = perf_counter()
    try:
        with patch.object(llm_client, "call_llm_json", one_call):
            await review_institutional_decision_turn(world, actor, monthly_adapters())
    finally:
        if sha256(source.read_bytes()).hexdigest() != before:
            raise ValueError("source save changed during paired cause probe")
    suffix = world.events[provider_start:]
    receipts = [event for event in suffix if event.event_type in ai_decider.RECEIPT_EVENTS]
    if len(receipts) != 1 or receipts[0].deltas or calls != 1:
        raise ValueError("paired provider call lacks one zero-delta receipt")
    selected = (receipts[0].causal_payload or {}).get("selection", {}).get("selected_affordance_id")
    if selected == previous_id or (selected not in options and selected != ai_decider.NO_ACTION):
        raise ValueError("provider repeated an unavailable option")
    validate_history(world.events, world.clock.absolute_day, from_sequence=setup_start + 1)
    world_snapshot(world)
    validate_activities(world)
    return {"source_sha256_unchanged": before, "actor_ref": actor.to_dict(),
            "previous_id_no_longer_offered": True, "new_offered_count": len(options),
            "selected_id": selected, "selection_valid": True,
            "receipt_event_id": receipts[0].id, "receipt_has_deltas": False,
            "setup_material_events": sum(bool(event.deltas) for event in setup_events),
            "provider_material_events": sum(bool(event.deltas) for event in suffix),
            "provider_calls": calls, "elapsed_s": round(perf_counter() - started, 3),
            "persisted": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--previous-id", required=True)
    parser.add_argument("--allow-provider-egress", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(probe(args.source, args.previous_id,
                               allow_provider_egress=args.allow_provider_egress))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

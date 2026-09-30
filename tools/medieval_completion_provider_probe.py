"""Five prepared M8 cases through native turns; preview is the safe default.

Qualification/material quantities are explicit existing test premises, not
natural emergence. No source save or persistent provider settings are modified.
"""

import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.classes.mechanical_language import EntityRef
from src.config.settings_schema import LLMProfile
from src.config.settings_service import get_settings_service
from src.sim.medieval import ai_decider, character_rite_policy
from src.sim.medieval.events import validate_history
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn
from src.sim.medieval.persistence import load_world, world_snapshot
from src.sim.medieval.rites import rite_offer_options
from src.systems.calendar_agenda import ScheduledSituation
from src.utils.llm import client
from tests.test_medieval_elemental_rite import prepared_world
from tests.test_medieval_evocation import prepare, CASTER
from tests.test_medieval_religion import prepared, ORDER, CULT, invite, join


CASE_NAMES = ("faith_uncommitted", "faith_prior", "elemental", "evocation", "composed")


async def run(source, *, allow_provider_egress=False, case_names=None):
    selected_cases = CASE_NAMES if case_names is None else tuple(case_names)
    if (not selected_cases or len(set(selected_cases)) != len(selected_cases)
            or not set(selected_cases).issubset(CASE_NAMES)):
        raise ValueError("select distinct known cases")
    source_hash = sha256(source.read_bytes()).hexdigest()
    worlds = []
    for prior in (False, True):
        world, actor = prepared()
        if prior:
            join(world, actor, ORDER)
        notice = invite(world, CULT, actor)
        worlds.append(("faith_prior" if prior else "faith_uncommitted", world, actor, notice.event_id))
    world, caster = prepared_world()
    worlds.append(("elemental", world, EntityRef("character", caster),
                   rite_offer_options(world, caster)[0].report_event_id))
    world = prepare()
    worlds.append(("evocation", world, EntityRef("character", CASTER),
                   rite_offer_options(world, CASTER)[0].report_event_id))
    worlds.append(("composed", load_world(source), EntityRef("polity", "auren"), None))
    worlds = [item for item in worlds if item[0] in selected_cases]

    attempts = []
    results = []
    original_call = client.call_llm_json

    async def tracked(prompt, *args, **kwargs):
        if len(attempts) >= len(selected_cases):
            raise ValueError("selected-case attempt cap reached")
        payload = json.loads(prompt[prompt.index("{"):])
        attempts.append({"prompt_sha256": sha256(prompt.encode()).hexdigest(),
                         "offered_ids": [item["id"] for item in payload["choices"]],
                         "prompt_bytes": len(prompt.encode())})
        # One boundary consultation must be exactly one transport attempt:
        # parsing retries would otherwise silently exceed human authorization.
        kwargs["max_retries"] = 0
        return (await original_call(prompt, *args, **kwargs)
                if allow_provider_egress else {"selected_id": ai_decider.NO_ACTION})

    profile = LLMProfile(base_url="codex://oauth", api_format="codex_cli", model_name="gpt-6-luna",
                         fast_model_name="gpt-6-luna")
    service = get_settings_service()
    with patch.object(service, "get_llm_runtime_config", return_value=(profile, "")), \
            patch.object(client, "call_llm_json", tracked):
        for name, world, actor, cause in worlds:
            start = len(world.events)
            previous_attempts = len(attempts)
            world.config = world.config.model_copy(update={
                "ai_enabled": True, "ai_calls_per_step": ai_decider.spent_calls(
                    world, since_day=world.clock.absolute_day) + 1, "ai_max_calls": 0})
            try:
                if cause is not None:
                    world.clock = world.clock.advance(1)
                    situation = ScheduledSituation(
                        character_rite_policy._offer_review_id(actor.id, cause),
                        character_rite_policy.OFFER_REVIEW_KIND, world.clock.absolute_day)
                    await character_rite_policy._offer_turn(world, situation)
                else:
                    await review_institutional_decision_turn(world, actor, monthly_adapters())
                receipts = [event for event in world.events[start:]
                            if event.event_type in ai_decider.RECEIPT_EVENTS]
                assert len(attempts) == previous_attempts + 1
                assert len(receipts) == 1 and not receipts[0].deltas
                assert receipts[0].causal_origin.value == "llm_interpretation"
                selected = receipts[0].causal_payload["selection"]["selected_affordance_id"]
                validate_history(world.events, world.clock.absolute_day, from_sequence=start + 1)
                world_snapshot(world)
                results.append({"case": name, "selected_id": selected,
                                "offered_count": len(attempts[-1]["offered_ids"]),
                                "receipt_has_deltas": False,
                                "material_events": sum(bool(event.deltas) for event in world.events[start:])})
            except Exception as exc:
                chain = []
                failure = exc
                while failure is not None and len(chain) < 5:
                    chain.append(type(failure).__name__)
                    failure = failure.__cause__
                results.append({"case": name, "failure_type": type(exc).__name__,
                                "failure_chain": chain})
                break
            print(json.dumps({"case_finished": name, "attempts": len(attempts)}),
                  file=sys.stderr, flush=True)
    unchanged = sha256(source.read_bytes()).hexdigest() == source_hash
    return {"complete": len(results) == len(selected_cases) and all("failure_type" not in item for item in results) and unchanged,
            "selected_cases": list(selected_cases),
            "mode": "real_provider" if allow_provider_egress else "preview_mock_no_action",
            "real_attempts": len(attempts) if allow_provider_egress else 0,
            "source_unchanged": unchanged, "source_sha256": source_hash,
            "cases": results, "prompt_hashes": [item["prompt_sha256"] for item in attempts],
            "raw_prompts_emitted": False, "persisted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--allow-provider-egress", action="store_true")
    parser.add_argument("--cases", nargs="+", choices=CASE_NAMES, default=None)
    args = parser.parse_args()
    result = asyncio.run(run(args.source, allow_provider_egress=args.allow_provider_egress,
                             case_names=args.cases))
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["complete"] else 1)

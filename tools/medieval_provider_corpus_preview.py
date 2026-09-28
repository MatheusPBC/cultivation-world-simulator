"""Locally preview ten provider consultations without sending prompts anywhere.

This is a readiness and bounded knowledge check for the V1 corpus, not proof
that every actor-facing fragment in the whole game is private. The six saves
are supplied explicitly; outputs contain counts and hashes, never raw prompts.
Five situation families use distinct actor-state consultations, not repeated
provider calls on an identical menu.
"""

from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.creature_policy import _creature_turn
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.institutional_decision_turn import _by_id, _composed_situation
from src.sim.medieval.persistence import load_world
from tools.medieval_provider_route_review_probe import probe as route_probe


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _civil(path: Path, actor_id: str, required_names: set[str], *, due_tomorrow=False) -> dict:
    before = _digest(path)
    world = load_world(path)
    actor = EntityRef("polity", actor_id)
    options = _by_id(world, actor, monthly_adapters())
    names = {adapter.name for adapter, _ in options.values()}
    if not required_names <= names:
        raise ValueError(f"missing required civil options: {required_names - names}")
    situation = _composed_situation(world, actor, options)
    choices = [{"id": option_id, "label": adapter.label_fn(option)}
               for option_id, (adapter, option) in sorted(options.items())]
    safe_choices, _ = ai_decider._prompt_choices(choices)
    prompt = ai_decider._prompt(actor, situation, safe_choices)
    owned_reports = {(item.settlement_id, item.event_id)
                     for item in world.knowledge.settlements_for_actor(actor)}
    shown_reports = {(item["settlement_id"], item["event_id"])
                     for item in situation["known_settlement_reports"]}
    if not shown_reports <= owned_reports:
        raise ValueError("dossier disclosed a settlement report not received by the actor")
    foreign_handles = [item.id for item in (*world.economy.stocks.values(),
                                            *world.economy.accounts.values())
                       if item.owner_ref != actor and item.id in prompt]
    if foreign_handles:
        raise ValueError("prompt includes a foreign stock or account handle")
    if due_tomorrow:
        obligations = situation.get("institutional_aid", {}).get("your_accepted_obligations", ())
        if not any(item["days_until_due"] == 1 for item in obligations):
            raise ValueError("near-deadline provider prompt lacks the actor's due date")
    if _digest(path) != before:
        raise ValueError("source save changed during civil preview")
    return {"actor_ref": actor.to_dict(), "source_sha256": before,
            "offered_count": len(options), "prompt_bytes": len(prompt.encode()),
            "owned_report_count": len(shown_reports),
            "required_option_names": sorted(required_names),
            "foreign_stock_or_account_handles": 0}


async def _creature(path: Path) -> dict:
    before = _digest(path)
    world = load_world(path)
    creature_id = "creature:drake-do-lume"
    creature = world.creatures.creatures[creature_id]
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 0,
    })
    prompts = []

    async def decline(prompt):
        prompts.append(json.loads(prompt[prompt.index("{"):]))
        return {"selected_id": ai_decider.NO_ACTION}

    with patch.object(ai_decider, "provider_available", return_value=True), patch(
        "src.utils.llm.client.call_llm_json", decline
    ):
        await _creature_turn(world, creature_id)
    if len(prompts) != 1:
        raise ValueError("creature preview did not produce one current consultation")
    situation = prompts[0]["situation"]
    if (situation["condition"] != creature.condition
            or situation["crossings_you_saw"] != creature.perceived_crossings
            or not {item["event_id"] for item in situation["recent_memory"]}
                   <= set(creature.memory_event_ids)):
        raise ValueError("creature prompt exceeded its own perception and memory")
    if _digest(path) != before:
        raise ValueError("source save changed during creature preview")
    return {"actor_ref": {"kind": "creature", "id": creature_id},
            "source_sha256": before, "offered_count": len(prompts[0]["choices"]),
            "perception_matches_owner": True}


async def _route(path: Path) -> dict:
    before = _digest(path)
    world = load_world(path)
    prompts = []

    async def decline(prompt):
        prompts.append(json.loads(prompt[prompt.index("{"):]))
        return {"selected_id": ai_decider.NO_ACTION}

    with patch.object(ai_decider, "provider_available", return_value=True), patch(
        "src.utils.llm.client.call_llm_json", decline
    ):
        result = await route_probe(path)
    if len(prompts) != 2:
        raise ValueError("route preview requires separate commander and HQ turns")
    commander, headquarters = prompts
    command = world.society.detachment_commands.get(
        commander["situation"]["your_command"]["detachment_id"])
    if command is None or command.character_id != commander["you_are"]["id"]:
        raise ValueError("commander prompt is not backed by its own appointment")
    hq = EntityRef.from_dict(headquarters["you_are"])
    report_id = headquarters["situation"]["blocked_report_event_id"]
    if not any(item.recipient_ref == hq and item.event_id == report_id
               for item in world.knowledge.route_reports.values()):
        raise ValueError("HQ prompt contains a route reading it did not receive")
    if _digest(path) != before:
        raise ValueError("source save changed during route preview")
    return {"source_sha256": before, "consultations": len(result["calls"]),
            "offered_counts": [len(item["choices"]) for item in prompts],
            "commander_appointment_valid": True, "hq_route_report_owned": True}


async def preview(natural: Path, commitment: Path, priorities: Path, route: Path,
                  natural_101: Path, natural_14: Path) -> dict:
    cases = {
        "economy": _civil(natural, "auren", {"aid_request", "relief"}),
        "near_deadline": _civil(commitment, "escarlia", {"aid_fulfillment"},
                                due_tomorrow=True),
        "food_vs_defense": _civil(priorities, "escarlia", {"aid_request", "defense_adoption"}),
        "creature": await _creature(natural),
        "route_campaign": await _route(route),
        "seed101_auren": _civil(natural_101, "auren", {"aid_request", "relief"}),
        "seed101_escarlia": _civil(natural_101, "escarlia", {"aid_request", "relief"}),
        "seed14_auren": _civil(natural_14, "auren", {"aid_request", "site_construction"}),
        "seed14_valedouro": _civil(natural_14, "valedouro", {"production_priority", "relief"}),
    }
    civil_keys = [key for key in cases if key not in {"creature", "route_campaign"}]
    civil_contexts = {(cases[key]["source_sha256"], cases[key]["actor_ref"]["id"])
                      for key in civil_keys}
    if len(civil_contexts) != len(civil_keys):
        raise ValueError("corpus repeats a civil actor-state consultation")
    consultation_count = len(civil_keys) + 1 + cases["route_campaign"]["consultations"]
    if consultation_count != 10:
        raise ValueError(f"corpus has {consultation_count} consultations, expected 10")
    return {"cases": cases, "consultation_count": consultation_count,
            "real_provider_calls": 0, "raw_prompts_emitted": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--natural", type=Path, required=True)
    parser.add_argument("--commitment", type=Path, required=True)
    parser.add_argument("--priorities", type=Path, required=True)
    parser.add_argument("--route", type=Path, required=True)
    parser.add_argument("--natural-101", type=Path, required=True)
    parser.add_argument("--natural-14", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(preview(args.natural, args.commitment, args.priorities,
                                 args.route, args.natural_101, args.natural_14))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Prepare a near-deadline aid obligation for a bounded provider probe.

The source is a real saved world with a current aid request. Two explicit API
setup decisions create and accept the obligation through their normal owners.
Until the day before its deadline, a local NO_ACTION stub declines every
consultation. Those receipts are fixture behavior, never evidence of a real
provider's choices. No source save is modified or external model called.
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

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.institutional_aid import (
    aid_fulfillment_options,
    aid_request_options,
    aid_response_options,
    request_institutional_aid,
    respond_institutional_aid,
)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot


async def _no_action(_prompt: str) -> dict[str, str]:
    return {"selected_id": ai_decider.NO_ACTION}


def _setup_decision(world, option, event_type: str):
    return record_event(
        world, event_type, "Decisão explícita de preparo da situação controlada.",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision=option.decision(),
    )


async def build(source: Path, output: Path, requester_id: str, provider_id: str) -> dict:
    source = source.resolve()
    output = output.resolve()
    if source == output or output.exists():
        raise ValueError("output must be a new path distinct from the source save")
    source_hash = sha256(source.read_bytes()).hexdigest()
    world = load_world(source)
    requester = EntityRef("polity", requester_id)
    provider = EntityRef("polity", provider_id)
    request = next((item for item in aid_request_options(world, requester)
                    if item.provider_ref == provider), None)
    if request is None:
        raise ValueError("source save has no current aid request for this pair")
    request_decision = _setup_decision(world, request, "corpus_setup_aid_request")
    request_institutional_aid(world, requester, request.id, request_decision.id)
    acceptance = next((item for item in aid_response_options(world, provider)
                       if item.kind == "accept" and item.requester_ref == requester), None)
    if acceptance is None:
        raise ValueError("provider has no current material acceptance option")
    acceptance_decision = _setup_decision(world, acceptance, "corpus_setup_aid_acceptance")
    proposal = respond_institutional_aid(world, provider, acceptance.id, acceptance_decision.id)
    obligations = [item for item in world.relations.obligations.values()
                   if item.proposal_id == proposal.id and item.status == "active"]
    if len(obligations) != 1:
        raise ValueError("expected one active aid obligation")
    obligation_id = obligations[0].id
    due_day = proposal.clauses[obligations[0].clause_index].due_day
    if due_day <= world.clock.absolute_day + 1:
        raise ValueError("obligation has no preparation window")

    world.config = world.config.model_copy(update={
        "ai_enabled": True,
        "ai_calls_per_step": 256,
        "ai_max_calls": 0,
    })
    simulator = MedievalSimulator(world)
    # The local stub is deliberately confined to fixture preparation. A real
    # corpus call on the saved output must run in a separate process/config.
    with patch.object(ai_decider, "provider_available", return_value=True), patch(
        "src.utils.llm.client.call_llm_json", _no_action
    ):
        while simulator.world.clock.absolute_day < due_day - 1:
            await simulator.step()

    world = simulator.world
    obligation = world.relations.obligations[obligation_id]
    options = [item for item in aid_fulfillment_options(world, provider)
               if item.obligation_id == obligation_id]
    if (world.clock.absolute_day != due_day - 1 or obligation.status != "active"
            or not options):
        raise ValueError("near-deadline obligation is not currently fulfillable")
    validate_history(world.events, world.clock.absolute_day)
    world_snapshot(world)
    if sha256(source.read_bytes()).hexdigest() != source_hash:
        raise ValueError("source save changed while preparing fixture")
    save_world(world, output)
    restored = load_world(output)
    if world_snapshot(restored) != world_snapshot(world) or restored.events != world.events:
        raise ValueError("fixture did not survive save/load")
    return {
        "source_save": str(source),
        "source_sha256_unchanged": source_hash,
        "output_save": str(output),
        "day": world.clock.absolute_day,
        "due_day": due_day,
        "obligation_id": obligation_id,
        "provider_ref": provider.to_dict(),
        "fulfillment_affordance_ids": [item.id for item in options],
        "preparation_policy": "local_stub_NO_ACTION",
        "real_provider_calls": 0,
        "save_load_equivalent": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requester", required=True)
    parser.add_argument("--provider", required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(build(args.source, args.output, args.requester,
                                     args.provider)), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

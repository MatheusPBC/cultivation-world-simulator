"""Free two provider menus through explicit owner decisions on a cloned save.

The source is untouched. Escarlia and Auren independently reject existing
pending requests through their current response affordances; this closes the
notices that otherwise suppress new aid requests in the provider corpus.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.institutional_aid import aid_response_options, respond_institutional_aid
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.institutional_decision_turn import _by_id
from src.sim.medieval.persistence import load_world, save_world, world_snapshot


def _reject(world, provider_id: str, requester_id: str) -> str:
    provider = EntityRef("polity", provider_id)
    option = next((item for item in aid_response_options(world, provider)
                   if item.kind == "reject" and item.requester_ref.id == requester_id), None)
    if option is None:
        raise ValueError(f"{provider_id} has no current rejection option for {requester_id}")
    decision = record_event(
        world, "provider_corpus_setup_rejection", "Rejeição explícita de preparo do corpus.",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision=option.decision(),
    )
    rejected = respond_institutional_aid(world, provider, option.id, decision.id)
    if rejected is None:
        raise ValueError("the owner did not execute the selected rejection")
    return rejected.id if hasattr(rejected, "id") else option.id


def build(source: Path, output: Path) -> dict:
    source = source.resolve()
    output = output.resolve()
    if source == output or output.exists():
        raise ValueError("output must be a new path distinct from the source save")
    source_hash = sha256(source.read_bytes()).hexdigest()
    world = load_world(source)
    handled = [
        _reject(world, "escarlia", "auren"),
        _reject(world, "auren", "valedouro"),
    ]
    actors = ("auren", "escarlia", "valedouro")
    menus = {}
    for actor_id in actors:
        options = _by_id(world, EntityRef("polity", actor_id), monthly_adapters())
        names = sorted({adapter.name for adapter, _ in options.values()})
        menus[actor_id] = {"option_families": names, "option_count": len(options)}
    if not {"aid_request", "relief"} <= set(menus["auren"]["option_families"]):
        raise ValueError("Auren still lacks the current aid-request/relief menu")
    if not {"aid_request", "relief"} <= set(menus["escarlia"]["option_families"]):
        raise ValueError("Escarlia still lacks the current aid-request/relief menu")
    validate_history(world.events, world.clock.absolute_day)
    world_snapshot(world)
    if sha256(source.read_bytes()).hexdigest() != source_hash:
        raise ValueError("source save changed while preparing fixture")
    save_world(world, output)
    restored = load_world(output)
    if world_snapshot(restored) != world_snapshot(world) or restored.events != world.events:
        raise ValueError("prepared fixture did not survive save/load")
    return {"source_save": str(source), "source_sha256_unchanged": source_hash,
            "output_save": str(output), "day": world.clock.absolute_day,
            "rejected_request_ids": handled, "menus": menus,
            "preparation_source": "two explicit API actor decisions via aid owner",
            "save_load_equivalent": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

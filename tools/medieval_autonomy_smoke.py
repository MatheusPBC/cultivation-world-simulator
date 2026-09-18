"""Natural autonomous supply smoke, with elapsed-time and conservation evidence.

Governo roteirizado (Passo 3 do plano de consequência causal)
---------------------------------------------------------------
O motor não tem IA de governo própria: sem um ator instalado no lugar do
provider, o mundo roda sem ninguém sendo consultado, e "policy":
"routine-rules" no relatório é só o rótulo do modo determinístico do motor,
não um perfil de governante. Medir esse vazio e tirar conclusões sobre
governos já produziu duas conclusões erradas nesta frente (ver
docs/handoff/plano-consequencia-causal.md).

``--gov-profile`` instala um decisor determinístico e explícito no mesmo
ponto em que os testes instalam um provider falso (``ai_decider.provider_available``
e ``src.utils.llm.client.call_llm_json`` — ver
``tests/test_medieval_institutional_agenda.py`` e
``tests/test_medieval_concurrent_civil_decision.py``). Esse ponto é único
para todo o turno institucional mensal, e o turno mensal consulta dois
sujeitos políticos diferentes por meio do mesmo mecanismo:
``monthly_actors`` inclui tanto as polities (``kind == "polity"``) quanto os
grupos populacionais que têm opção cívica corrente (``kind ==
"population_group"``, via ``civic_actors``). Um decisor que respondesse
NO_ACTION para "qualquer coisa fora de relief" estaria respondendo também
PELO POVO nos meses em que ele tem opção de protesto — silenciando a revolta
em nome dela, todo mês, sem que isso fosse uma propriedade do motor. Por
isso este arquivo declara **dois** atores de teste, independentes, cada um
só respondendo pelo seu próprio sujeito:

- **Governo** (``--gov-profile``, atua só quando ``you_are.kind ==
  "polity"``): responde ao menu institucional mensal composto (diplomacia,
  socorro, reparo, ajuda, adoção de estratégia etc.), mas só tem opinião
  sobre a família "relief" — para qualquer outra família de decisão *de uma
  polity* ele sempre responde NO_ACTION. Isso é uma limitação deliberada de
  escopo desta medição (o foco é ajuda), não uma alegação de que essas
  famílias não importam, e não inclui nunca a família "civic": protesto não
  é decisão de polity.
- **Povo** (fixo, sempre ativo, atua só quando ``you_are.kind ==
  "population_group"``): o comportamento roteirizado mais simples e honesto
  para o sujeito político que o motor já filtrou por todas as suas próprias
  condições materiais (fome observada, revolta >= 300 ou saúde no chão,
  quórum do grupo, nenhum protesto já aberto naquele assentamento) — quando
  existe uma opção de **abrir** protesto (``civic-protest-open:...``) no
  menu deste grupo, ele abre. Dissolver ou recusar uma demanda cívica
  seguem fora do escopo deste ator de teste e respondem NO_ACTION; isso é
  uma limitação declarada, não uma alegação de que grupos nunca desistem.

Nenhum dos dois é fallback do motor: ambos vivem só em ``tools/``, o motor
continua sem rotina de protesto ou de ajuda, e "roteirizado" aqui significa
"decisão determinística de um ator de teste explícito", nunca "condição
automática dentro de src/sim/".

Três perfis de **governo**, todos deterministas e sem heurística de mercado
nenhuma (o comportamento do povo acima é o mesmo nos três, porque a pergunta
desta medição é sobre o governo, não sobre o povo):

- ``desatento``: sempre NO_ACTION, mesmo diante de fome relatada. É o "governo
  presente mas nunca decide nada" — o controle mais simples possível para
  saber se a mera presença de um ator consultado (em vez de nenhum ator) já
  muda o resultado.
- ``reativo``: só escolhe ajuda quando a fome relatada pelo próprio ator (o
  ``missing_food`` no relatório datado do assentamento, no fragmento de
  situação da família "relief") ultrapassa ``REACTIVE_MISSING_FOOD_THRESHOLD``
  (100 unidades). O limiar foi escolhido por estar bem acima do ruído de
  arredondamento de poucas dezenas visto nos testes de socorro, e bem abaixo
  da fome severa de várias centenas observada nas medições anteriores sem
  governo — o suficiente para distinguir "reage a um problema real" de "reage
  a qualquer sinal", sem copiar o limiar do preventivo.
- ``preventivo``: escolhe ajuda ao primeiro sinal de fome (``missing_food >
  0``) no relatório do próprio ator.

Quando a família "relief" oferece mais de uma opção (o menu sempre inclui a
fome inteira e a metade dela, cada uma limitada ao estoque físico real), os
perfis reativo e preventivo escolhem a de maior quantidade disponível: eles
decidiram agir, então cobrem o máximo que o estoque permite.

O protesto cívico nunca é decidido pelo governo, e o povo nunca decide nada
fora de abrir sua própria demanda: nenhum dos dois decisores empresta a voz
do outro, e nenhum fallback determinístico foi acrescentado dentro do
motor. Fora deste arnês (``--gov-profile`` ausente), nenhum ator é
consultado e o mundo roda exatamente como antes — sem governo e sem povo
roteirizado.
"""

import argparse
import asyncio
from collections import Counter
import cProfile
import json
from pathlib import Path
import pstats
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.persistence import save_world, load_world, world_snapshot

GOV_PROFILES = ("desatento", "reativo", "preventivo")
REACTIVE_MISSING_FOOD_THRESHOLD = 100


def food_total(world):
    return sum(s.goods.get("food", 0) for s in world.economy.stocks.values()) + sum(
        p.quantity for p in world.economy.parcels.values()
        if world.economy.freight_orders[p.order_id].resource_id == "food") + sum(
        provision.food for provision in world.economy.migration_provisions.values())


def resource_totals(world):
    totals = {rid: sum(s.goods.get(rid, 0) for s in world.economy.stocks.values()) for rid in world.economy.resources}
    for parcel in world.economy.parcels.values():
        totals[world.economy.freight_orders[parcel.order_id].resource_id] += parcel.quantity
    totals["food"] += sum(provision.food for provision in world.economy.migration_provisions.values())
    return totals


RESOURCE_EFFECTS = {"production_completed", "production_limited", "subsistence_resolved",
                    "household_purchase_completed", "household_rations_consumed", "household_provisions_purchased",
                    "migration_started", "migration_arrived", "migration_returned", "migration_rations_consumed",
                    "expansion_progressed", "research_progressed", "repair_progressed",
                    # Relief gives real food away for free: it leaves the granary and is
                    # never credited anywhere else, exactly like a ration consumed.
                    "relief_distributed"}


def ledger_resource_effects(events, resources):
    """Count true production/consumption effects, including carried provisions."""
    totals = Counter()
    for event in events:
        if event.event_type not in RESOURCE_EFFECTS:
            continue
        for delta in event.deltas:
            if delta.owner_kind == "stock" and delta.aspect in resources:
                totals[delta.aspect] += int(delta.after) - int(delta.before)
            elif delta.owner_kind == "migration_provision" and delta.aspect == "food":
                totals["food"] += int(delta.after) - int(delta.before)
    return totals


def deprivation_deaths(world):
    return sum(int(delta.before) - int(delta.after)
               for event in world.events if event.event_type == "deprivation_deaths"
               for delta in event.deltas if delta.owner_kind == "population_group")


POLITICAL_EVENTS = {"civic_protests": "civic_protest_opened",
                    "aid_requests": "institutional_aid_requested",
                    "aid_fulfilled": "institutional_aid_fulfilled",
                    "migrations_started": "migration_started",
                    "relief_given": "relief_distributed"}


def monthly_metrics(world):
    needs = tuple(world.economy.needs.values())
    day = world.clock.absolute_day
    cumulative = Counter(event.event_type for event in world.events)
    monthly = Counter(event.event_type for event in world.events if day - 30 < event.day <= day)
    return {"month": day // 30, "day": day,
            "population": world.society.total_population,
            "missing_food": sum(need.missing_food for need in needs),
            "mean_health": round(sum(need.health for need in needs) / len(needs), 2) if needs else 0,
            "mean_unrest": round(sum(need.unrest for need in needs) / len(needs), 2) if needs else 0,
            "deprivation_deaths": deprivation_deaths(world),
            **{f"{name}_month": monthly[kind] for name, kind in POLITICAL_EVENTS.items()},
            **{f"{name}_total": cumulative[kind] for name, kind in POLITICAL_EVENTS.items()},
            "settlements": {key: {"health": need.health, "unrest": need.unrest,
                                  "missing_food": need.missing_food}
                            for key, need in sorted(world.economy.needs.items())}}


def _payload_of(prompt):
    """The structured payload ``ai_decider._prompt`` appended after its prose."""
    return json.loads(prompt[prompt.index("{"):])


def _relief_choice(payload):
    """The relief option covering the most food, or None when relief has none."""
    relief_ids = [choice["id"] for choice in payload.get("choices", ())
                  if choice["id"].startswith("relief-distribute:")]
    if not relief_ids:
        return None
    return max(relief_ids, key=lambda option_id: int(option_id.split(":")[3]))


def _reported_missing_food(payload):
    """The greatest hunger this actor's own settlement reports currently show."""
    reports = payload.get("situation", {}).get("relief", {}).get("settlement_reports", ())
    return max((report.get("missing_food", 0) for report in reports), default=0)


def _actor_kind(payload):
    return payload.get("you_are", {}).get("kind")


def _desatento_decision(payload):
    return ai_decider.NO_ACTION


def _reativo_decision(payload):
    if _reported_missing_food(payload) > REACTIVE_MISSING_FOOD_THRESHOLD:
        choice = _relief_choice(payload)
        if choice is not None:
            return choice
    return ai_decider.NO_ACTION


def _preventivo_decision(payload):
    if _reported_missing_food(payload) > 0:
        choice = _relief_choice(payload)
        if choice is not None:
            return choice
    return ai_decider.NO_ACTION


GOV_DECISIONS = {"desatento": _desatento_decision, "reativo": _reativo_decision,
                 "preventivo": _preventivo_decision}


def _protest_open_choice(payload):
    """The option that opens this group's own civic demand, if the menu has one.

    The engine already gates this option behind every material precondition
    (observed hunger, unrest >= 300 or health on the floor, group quorum, no
    protest already open for that settlement) before it can appear at all —
    see ``civic_protest_options`` in ``src/sim/medieval/civic_protest.py``. If
    it is on the table, this test actor takes it.
    """
    ids = [choice["id"] for choice in payload.get("choices", ())
          if choice["id"].startswith("civic-protest-open:")]
    return ids[0] if ids else None


def _povo_decision(payload):
    """The population's own test actor: open a protest whenever it can.

    Deliberately narrower than the engine's own civic menu: dissolving an
    open protest or refusing a demand received by an administrator are both
    left to NO_ACTION, a declared scope limit, not a claim that groups never
    back down.
    """
    choice = _protest_open_choice(payload)
    return choice if choice is not None else ai_decider.NO_ACTION


def _install_gov_profile(gov_profile):
    """Two context managers, at the exact seam the institutional tests use.

    The one provider seam answers for two different political subjects in
    the same monthly turn: polities and population groups (see the module
    docstring). This dispatches by ``you_are.kind`` so the government
    profile only ever speaks for a polity, and the population's own fixed
    "open when possible" actor only ever speaks for a population group —
    neither one answers on the other's behalf.

    For a polity, every family outside "relief" gets no situation fragment
    shaped like ``_reported_missing_food`` expects, so ``_relief_choice``/
    ``_reported_missing_food`` simply see nothing and the chosen profile
    answers NO_ACTION for them too — the documented scope limit, not a
    special case in the code.
    """
    decide = GOV_DECISIONS[gov_profile]

    async def call_llm_json(prompt, *args, **kwargs):
        payload = _payload_of(prompt)
        if _actor_kind(payload) == "population_group":
            return {"selected_id": _povo_decision(payload)}
        return {"selected_id": decide(payload)}

    return (patch("src.sim.medieval.ai_decider.provider_available", return_value=True),
            patch("src.utils.llm.client.call_llm_json", call_llm_json))


async def run(seed, days, output, profile=False, gov_profile=None):
    if gov_profile is not None and gov_profile not in GOV_PROFILES:
        raise ValueError(f"gov_profile must be one of {GOV_PROFILES}")
    if gov_profile is None:
        return await _run(seed, days, output, profile, gov_profile)
    patches = _install_gov_profile(gov_profile)
    with patches[0], patches[1]:
        return await _run(seed, days, output, profile, gov_profile)


async def _run(seed, days, output, profile, gov_profile):
    world = create_medieval_world(seed)
    if gov_profile is not None:
        # Consulted for real: enabled, with enough same-day budget that every
        # polity's monthly turn (plus any daily recourse turn sharing the same
        # boundary day) gets answered, and no artificial monthly ceiling.
        world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 8})
    initial_resources = resource_totals(world)
    initial_money = sum(a.balance for a in world.economy.accounts.values())
    elapsed, jumps, boundary, net_resources, metrics = time.perf_counter(), 0, 0, Counter(), []
    print(json.dumps({"phase": "start", "gov_profile": gov_profile, "seed": seed, "days": days,
                      "initial_population": world.society.total_population, "initial_money": initial_money,
                      "ai_enabled": world.config.ai_enabled, "policy": world.config.decision_policy}), flush=True)
    while world.clock.absolute_day < days:
        start = len(world.events)
        await MedievalSimulator(world).step()
        jumps += 1
        net_resources.update(ledger_resource_effects(world.events[start:], world.economy.resources))
        assert resource_totals(world) == {rid: amount + net_resources[rid] for rid, amount in initial_resources.items()}, "unaccounted resource creation/loss"
        assert sum(a.balance for a in world.economy.accounts.values()) == initial_money
        if world.clock.absolute_day // 30 > boundary:
            boundary = world.clock.absolute_day // 30
            metric = monthly_metrics(world)
            metrics.append(metric)
            print(json.dumps({**metric, "events": len(world.events),
                              "orders": len(world.economy.freight_orders),
                              "elapsed_s": round(time.perf_counter()-elapsed, 2)}), flush=True)
    final_metrics = monthly_metrics(world)
    measured_events = len(world.events)
    measured_orders = len(world.economy.freight_orders)
    print(json.dumps({"phase": "horizon_complete", "day": world.clock.absolute_day,
                      "money_conserved": True, "all_resources_accounted": True,
                      "final_metrics": final_metrics}), flush=True)
    profiler = cProfile.Profile()
    if profile:
        profiler.enable()
    save_world(world, output)
    if profile:
        profiler.disable()
        pstats.Stats(profiler).sort_stats("cumtime").print_stats(15)
    resumed = load_world(output)
    assert world_snapshot(world) == world_snapshot(resumed) and world.events == resumed.events
    # Prove continuation, not only equality immediately after deserialization.
    await MedievalSimulator(world).step()
    await MedievalSimulator(resumed).step()
    assert world_snapshot(world) == world_snapshot(resumed) and world.events == resumed.events
    return {"scenario": "natural-autonomous-supply", "seed": seed, "saved_day": days,
"continuation_day": world.clock.absolute_day, "jumps": jumps, "events": measured_events,
             "money_total": initial_money, "orders": measured_orders,
             "gov_profile": gov_profile,
             "mean_unrest": final_metrics["mean_unrest"],
             **{f"{name}_total": final_metrics[f"{name}_total"] for name in POLITICAL_EVENTS},
            "population": final_metrics["population"],
            "missing_food_total": sum(item["missing_food"] for item in metrics),
            "mean_health": final_metrics["mean_health"],
            "deprivation_deaths": final_metrics["deprivation_deaths"],
            "monthly_metrics": metrics,
            "health": {key: n.health for key, n in world.economy.needs.items()},
            "balances": {key: a.balance for key, a in world.economy.accounts.items() if a.owner_ref.kind == "polity"},
            "food_conserved": True, "money_conserved": True, "all_resources_accounted": True,
             "save_load_equivalent": True, "real_ai_calls": 0,
            "policy": world.config.decision_policy, "elapsed_s": round(time.perf_counter()-elapsed, 2),
            "save": str(output.resolve())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--gov-profile", choices=GOV_PROFILES,
                        help="Decisor roteirizado instalado no lugar do provider; omitido = nenhum ator (mundo sem governo).")
    args = parser.parse_args()
    if args.days <= 0 or args.days % 30:
        parser.error("days must be a positive multiple of 30")
    print(json.dumps(asyncio.run(run(args.seed, args.days, args.output, args.profile, args.gov_profile)),
                     ensure_ascii=False, indent=2), flush=True)

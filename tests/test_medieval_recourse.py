"""A breach earns its creditor a turn; only a choice produces a consequence."""

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.diplomacy import ResourceTransferClause, offer_intent
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.diplomacy import offer_proposal, respond_proposal
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.recourse_policy import REVIEW_KIND, review_id
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from tests.test_medieval_creature_autonomy import choose, enable, provider
from tests.test_medieval_force import food_total, people_total

AUREN = EntityRef("polity", "auren")
ESCARLIA = EntityRef("polity", "escarlia")
HOME = "pontenegro"
TARGET = "ferroalto"
ROUTE = ("road-pontenegro-ferroalto",)
OWED = 200


def total_money(world):
    return sum(item.balance for item in world.economy.accounts.values())


def promise(world, due_day, expires_day):
    """Escárlia owes Auren a real delivery it will simply never make."""
    clause = ResourceTransferClause(debtor_ref=ESCARLIA, creditor_ref=AUREN, due_day=due_day,
                                    source_stock_id=f"stock:{TARGET}", destination_stock_id=f"stock:{HOME}",
                                    resource_id="food", quantity=OWED, route_ids=ROUTE)
    offered = record_event(world, "diplomatic_decision", "Prometer uma entrega de alimento.",
                           fact_kind=FactKind.DECISION,
                           decision=offer_intent(ESCARLIA, AUREN, (clause,), expires_day, None))
    proposal = offer_proposal(world, ESCARLIA, AUREN, (clause,), expires_day, decision_event_id=offered.id)
    accepted = record_event(world, "diplomatic_decision", "Aceitar a promessa.", fact_kind=FactKind.DECISION,
                            decision={"action": "respond_proposal", "actor_ref": AUREN.to_dict(),
                                      "proposal_id": proposal.id, "response": "accept"})
    respond_proposal(world, proposal.id, "accept", decision_event_id=accepted.id)
    return proposal


def wronged_world(due_day, expires_day):
    """Auren keeps a real garrison at its own village and is owed a delivery."""
    world = enable(create_medieval_world(73), per_step=8, maximum=10000)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    world.society.population[f"pop:{HOME}:{group.people}:soldier"] = group.model_copy(
        update={"id": f"pop:{HOME}:{group.people}:soldier", "occupation": "soldier", "count": 20})
    observe(world)
    promise(world, due_day, expires_day)
    return world


def observe(world):
    """Current administrative bulletins; knowledge, not a new capability."""
    refresh_settlement_reports(world)
    refresh_route_reports(world)


async def breached(world, engine):
    while not any(item.status == "breached" for item in world.relations.obligations.values()):
        await engine.step()
    return next(item for item in world.relations.obligations.values() if item.status == "breached")


def ai_receipts(world):
    return tuple(item for item in world.events
                 if item.event_type in {"ai_decision_interpreted", "ai_decision_declined",
                                        "ai_decision_failed"})


async def test_a_breach_earns_a_turn_that_a_provider_can_answer_with_a_real_column(tmp_path, monkeypatch):
    world = wronged_world(due_day=28, expires_day=20)
    people = people_total(world)
    engine = MedievalSimulator(world)
    obligation = await breached(world, engine)

    # The breach alone produced a turn and nothing else.
    assert world.clock.absolute_day == 29 and not world.society.detachments
    review = world.agenda.get(review_id(30))
    assert review is not None and review.kind == REVIEW_KIND
    assert not any(item.event_type == "recourse_decided" for item in world.events)

    observe(world)
    prompts = provider(monkeypatch, choose("marchar até Ferroalto"))
    await engine.step()

    # The turn fell on a monthly boundary: the column exists, its soldiers left
    # ordinary availability once, and their wages were paid exactly once.
    assert world.clock.absolute_day == 30
    detachment = next(iter(world.society.detachments.values()))
    assert detachment.stage == "marching" and detachment.destination_id == TARGET
    assert world.society.available_count(detachment.source_group_id) == 0
    payrolls = [item for item in world.economy.payrolls.values() if item.day == 30
                and detachment.source_group_id in item.workers_by_group]
    assert len(payrolls) == 1 and payrolls[0].id == detachment.id
    assert payrolls[0].workers_by_group[detachment.source_group_id] == detachment.count
    wages = next(item for item in world.events if item.event_type == "wages_paid" and item.day == 30)
    assert sum(int(delta.after) - int(delta.before) for delta in wages.deltas) == 0, "wages moved, never appeared"
    for prompt in prompts:
        # The wronged party speaks of its own promise and its own means.
        assert f"stock:{TARGET}" not in prompt and "treasury:escarlia" not in prompt

    marched_food, money = food_total(world), total_money(world)
    target = world.society.settlements[TARGET]
    owners = {key: item.owner_ref for key, item in world.economy.stocks.items()}
    sites = {key: (item.owner_ref, item.maintainer_ref) for key, item in world.map.infrastructure_sites.items()}
    taxes = {key: (item.account_id, item.income_rate) for key, item in world.authority.tax_policies.items()}

    # Arrival is observation only; occupying is a separate later decision.
    provider(monkeypatch, choose("Ocupar Ferroalto"))
    while world.society.settlements[TARGET].occupier_id is None:
        assert world.society.detachments[detachment.id].stage != "disbanded", "the column never arrived"
        await engine.step()
    assert world.knowledge.settlement_report(AUREN, TARGET) is not None
    held = world.society.settlements[TARGET]
    assert held.administrator_id == target.administrator_id and held.claimant_ids == target.claimant_ids
    # Occupation creates one explicit, owner-bound campaign bag for the
    # present column. Existing stocks keep their owners; the new bag is not a
    # hidden transfer of the occupied settlement's inventory.
    assert {key: item.owner_ref for key, item in world.economy.stocks.items()
            if key in owners} == owners
    camp_stock = world.economy.stocks[f"stock:camp:{detachment.id}"]
    assert camp_stock.owner_ref == detachment.owner_ref and camp_stock.location_id == TARGET
    assert {key: (item.owner_ref, item.maintainer_ref) for key, item in world.map.infrastructure_sites.items()} == sites
    assert {key: (item.account_id, item.income_rate) for key, item in world.authority.tax_policies.items()} == taxes
    assert total_money(world) == money and people_total(world) == people
    path = tmp_path / "recourse.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

    # Nobody feeds the column: the presence lapses by its own material fact.
    provider(monkeypatch, lambda prompt: {"selected_id": "NO_ACTION"})
    while world.society.detachments[detachment.id].stage != "disbanded":
        await engine.step()
    assert world.society.settlements[TARGET].occupier_id is None
    assert people_total(world) == people and total_money(world) == money
    assert food_total(world) == marched_food - detachment.provisions, "only the rations were eaten"
    assert world.relations.obligations[obligation.id].status == "breached", "recourse never repays the debt"
    assert any(item.event_type == "detachment_lapsed" for item in world.events)
    assert not any(item.event_type in {"battle_resolved", "casualties_taken"} for item in world.events)


async def test_without_a_provider_choice_a_breach_moves_nobody(monkeypatch):
    world = wronged_world(due_day=20, expires_day=12)
    engine = MedievalSimulator(world)
    await breached(world, engine)
    observe(world)
    assert world.agenda.get(review_id(22)) is not None

    proposals = set(world.relations.proposals)
    goods = {key: dict(item.goods) for key, item in world.economy.stocks.items()}
    balances = {key: item.balance for key, item in world.economy.accounts.items()}
    receipts = len(ai_receipts(world))
    logs = []

    # Deliberate inaction, a disabled provider, a failing one and a forged
    # answer are all the same to the world: the turn passes and nothing moves.
    logs.append(provider(monkeypatch, lambda prompt: {"selected_id": "NO_ACTION"}))
    await engine.step()
    world.config = world.config.model_copy(update={"ai_enabled": False})
    await engine.step()
    enable(world)
    logs.append(provider(monkeypatch, lambda prompt: RuntimeError("provedor fora do ar")))
    await engine.step()
    logs.append(provider(monkeypatch, lambda prompt: {"selected_id": "recourse:forjado"}))
    await engine.step()
    prompts = [prompt for log in logs for prompt in log]

    assert world.clock.absolute_day == 25 and prompts, "every open turn was offered"
    assert not world.society.detachments
    assert set(world.relations.proposals) == proposals
    assert all(item.occupier_id is None for item in world.society.settlements.values())
    assert {key: dict(item.goods) for key, item in world.economy.stocks.items()} == goods
    assert {key: item.balance for key, item in world.economy.accounts.items()} == balances
    assert not any(item.event_type == "recourse_decided" for item in world.events)

    new_receipts = ai_receipts(world)[receipts:]
    assert any(item.event_type == "ai_decision_failed" for item in new_receipts)
    assert all(not item.deltas and item.causal_origin == CausalOrigin.LLM_INTERPRETATION
               for item in new_receipts)
    for prompt in prompts:
        assert f"stock:{TARGET}" not in prompt and "treasury:escarlia" not in prompt
        assert "source_stock_id" not in prompt and "route_ids" not in prompt

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.governance.models import AuthorityOffice
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (establish_garrison, force_options, occupy_settlement,
                                    raise_detachment, raise_options)
from src.sim.medieval.garrison_policy import garrison_adapters, garrison_actors
from src.sim.medieval.institutional_agenda import monthly_actors, monthly_adapters
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


OWNER = EntityRef("polity", "auren")


def _decision(world, option):
    return record_event(world, "garrison_policy_decided", "Decisão sobre guarnição.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def test_owner_garrison_is_available_without_a_foreign_contact():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == "campomanso")
    world.society.population[f"pop:campomanso:{group.people}:soldier"] = group.model_copy(
        update={"id": f"pop:campomanso:{group.people}:soldier", "occupation": "soldier", "count": 20})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    raise_option = next(item for item in raise_options(world, OWNER) if item.destination_id == "salgueiro")
    raise_detachment(world, OWNER, raise_option.id, _decision(world, raise_option).id)
    while next(iter(world.society.detachments.values())).stage == "marching":
        world.clock = world.clock.advance(1)
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))
    refresh_settlement_reports(world)
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, _decision(world, occupy).id)
    refresh_settlement_reports(world)
    option = next(item for item in force_options(world, OWNER) if item.kind == "garrison")

    assert OWNER in garrison_actors(world)
    assert OWNER in monthly_actors(world)
    assert any(item.name == "garrison_management" for item in monthly_adapters())
    adapter = garrison_adapters()[0]
    assert any(item.id == option.id for item in adapter.options_fn(world, OWNER))
    adapter.execute_fn(world, OWNER, option.id, _decision(world, option).id)
    assert world.society.garrisons[f"garrison:{option.detachment_id}"].stage == "active"


def test_garrison_actor_discovery_includes_organization_military_offices(monkeypatch):
    import src.sim.medieval.garrison_policy as policy

    world = create_medieval_world(73)
    organization = EntityRef("organization", next(iter(world.society.organizations)))
    world.authority.offices["office:organization-military"] = AuthorityOffice(
        id="office:organization-military", institution_ref=organization,
        holder_ref=organization, scopes=("military",))
    option = type("GarrisonOption", (), {"actor_ref": organization})()
    monkeypatch.setattr(policy, "garrison_options",
                        lambda _world, actor: (option,) if actor == organization else ())

    assert garrison_actors(world) == (organization,)

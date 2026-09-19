"""Provider adapter for the bounded technology-sale affordances."""

from .institutional_decision_turn import DiscretionaryAdapter
from .technology_sale import (TechnologySaleAcceptance, execute_technology_sale,
                              technology_sale_acceptance_options, technology_sale_options)


def technology_sale_actors(world):
    actors = set()
    candidates = {account.owner_ref for account in world.economy.accounts.values()
                  if account.owner_ref.kind in {"polity", "organization"}}
    for actor in candidates:
        if technology_sale_options(world, actor) or technology_sale_acceptance_options(world, actor):
            actors.add(actor)
    return tuple(sorted(actors, key=lambda ref: (ref.kind, ref.id)))


def _options(world, actor):
    return (*technology_sale_options(world, actor), *technology_sale_acceptance_options(world, actor))


def _causes(world, option):
    if isinstance(option, TechnologySaleAcceptance):
        return (option.request_event_id,)
    return (option.sighting_event_id, option.source_event_id)


def _execute(world, actor, option_id, decision_event_id):
    option = next((item for item in _options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("stale or unknown technology sale option")
    if isinstance(option, TechnologySaleAcceptance):
        request = next((item for item in technology_sale_options(world, option.buyer_ref)
                        if item.id == option.request_option_id), None)
        if request is None:
            raise ValueError("technology sale request disappeared")
        execute_technology_sale(world, option.buyer_ref, request.id, option.request_event_id, decision_event_id)


def technology_sale_adapters():
    return (DiscretionaryAdapter(
        name="technology_sale", family="technology_sale", options_fn=_options,
        label_fn=lambda option: ("Aceitar venda de técnica já solicitada."
                                 if isinstance(option, TechnologySaleAcceptance)
                                 else "Comprar técnica observada para uma instalação própria."),
        causes_fn=_causes, execute_fn=_execute),)


__all__ = ["technology_sale_actors", "technology_sale_adapters"]

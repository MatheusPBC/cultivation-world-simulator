"""One institutional turn over already inspected customs cargo.

Customs itself owns the parcel, fee and classification rules. This adapter
only composes current owner affordances into the monthly menu.
"""

from .customs import (
    CustomsCargoOption, CustomsPaymentOption, CustomsSeizureOption, attempt_customs_fee_evasion,
    customs_cargo_options, customs_payment_options, declare_customs_manifest,
    customs_seizure_options, pay_customs_fee, return_contraband_cargo, seize_contraband_cargo,
)
from .institutional_decision_turn import DiscretionaryAdapter


def _options(world, actor):
    return (*customs_cargo_options(world, actor), *customs_payment_options(world, actor),
            *customs_seizure_options(world, actor))


def customs_actors(world):
    candidates = {account.owner_ref for account in world.economy.accounts.values()
                  if account.owner_ref.kind in {"polity", "organization"}}
    return tuple(sorted((actor for actor in candidates if _options(world, actor)),
                        key=lambda ref: (ref.kind, ref.id)))


def _causes(world, option):
    notice = world.knowledge.customs_notices.get(option.notice_id)
    return tuple(dict.fromkeys(item for item in (notice.event_id, notice.state_event_id) if item)) if notice else ()


def _label(option):
    if isinstance(option, CustomsPaymentOption):
        return "Pagar a taxa civil da carga declarada."
    return {
        "declare_customs_manifest": "Declarar a carga e aceitar a taxa civil calculada.",
        "attempt_customs_fee_evasion": "Tentar passar sem declarar a carga comum.",
        "return_contraband_cargo": "Retornar o contrabando ao estoque de origem pela rota disponível.",
        "seize_contraband_cargo": "Apreender o contrabando detectado para o estoque civil local.",
    }.get(option.action, "Escolher uma resolução alfandegária possível.")


def _execute(world, actor, option_id, decision_event_id):
    option = next((item for item in _options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("stale or unknown customs option")
    if isinstance(option, CustomsPaymentOption):
        return pay_customs_fee(world, option.id, decision_event_id=decision_event_id)
    if isinstance(option, CustomsSeizureOption):
        return seize_contraband_cargo(world, option.id, decision_event_id=decision_event_id)
    if option.action == "declare_customs_manifest":
        return declare_customs_manifest(world, option.id, decision_event_id=decision_event_id)
    if option.action == "attempt_customs_fee_evasion":
        return attempt_customs_fee_evasion(world, option.id, decision_event_id=decision_event_id)
    if option.action == "return_contraband_cargo":
        return return_contraband_cargo(world, option.id, decision_event_id=decision_event_id)
    raise ValueError("unsupported customs option")


def customs_adapters():
    return (DiscretionaryAdapter(name="customs", family="customs", options_fn=_options,
                                 label_fn=_label, causes_fn=_causes, execute_fn=_execute),)


__all__ = ["customs_adapters", "customs_actors"]

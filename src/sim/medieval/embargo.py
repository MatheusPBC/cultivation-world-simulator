"""A directed, revocable economic closure at one's own customs checkpoints.

Everything an administration could do before was either universal -- an export
rate that taxes every buyer, a service suspension that closes a passage for
everyone including itself -- or armed: route interdiction needs a column with a
prepared position. An embargo is the missing instrument between them: it names
one counterparty and refuses its cargo at the checkpoints this administration
actually staffs.

It creates no Map effect. Routes keep their capacity, other owners keep
trading, and the embargoed actor keeps every material answer it already had: a
successor shipment over another route, or the existing contraband channel. The
target is told nothing by decree; it learns when its own cargo comes back.
"""

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity, SocietyValue

from .customs import checkpoint_active
from .economy import _causes, _delta
from .events import record_event

DECLARE_ACTION = "declare_trade_embargo"
LIFT_ACTION = "lift_trade_embargo"


class EmbargoOption(SocietyValue):
    """Transient closure choice; only its ID is ever selected."""
    id: Identity
    actor_ref: EntityRef
    target_id: Identity
    checkpoint_id: Identity
    kind: str = "declare"

    def decision(self):
        return {"action": DECLARE_ACTION if self.kind == "declare" else LIFT_ACTION,
                "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


def _terms(option):
    return {"action": option.decision()["action"], "actor_ref": option.actor_ref.to_dict(),
            "target_id": option.target_id, "checkpoint_id": option.checkpoint_id,
            "policy_id": option.actor_ref.id}


def operated_checkpoints(world, actor):
    """Only checkpoints this actor operates and currently staffs."""
    return tuple(sorted((checkpoint for checkpoint in world.economy.customs_checkpoints.values()
                         if checkpoint.operator_ref == actor and checkpoint_active(world, checkpoint)),
                        key=lambda item: item.id))


def embargoes_of(world, operator_ref):
    policy = world.authority.tax_policies.get(operator_ref.id) if operator_ref.kind == "polity" else None
    return tuple(policy.embargoed_ids) if policy is not None else ()


def is_embargoed(world, operator_ref, owner_ref):
    """Whether this operator currently refuses that cargo owner."""
    return owner_ref.kind == "polity" and owner_ref.id in embargoes_of(world, operator_ref)


def embargo_blocker(world, actor, target_id, checkpoint, *, kind):
    policy = world.authority.tax_policies.get(actor.id)
    if policy is None or actor.kind != "polity":
        return "policy"
    if not can_actor_act_for(world, actor, actor, "taxation"):
        return "authority"
    if target_id == actor.id or target_id not in world.society.polities:
        return "target"
    # The closure has no substrate without a staffed post of one's own.
    if checkpoint is None or checkpoint.operator_ref != actor or not checkpoint_active(world, checkpoint):
        return "checkpoint"
    if (target_id in policy.embargoed_ids) == (kind == "declare"):
        return "already_current"
    return None


def embargo_options(world, actor):
    """Declare or lift, per named counterparty, only with a staffed own post."""
    if not isinstance(actor, EntityRef) or actor.kind != "polity":
        return ()
    checkpoints = operated_checkpoints(world, actor)
    if not checkpoints:
        return ()
    checkpoint = checkpoints[0]
    options = []
    for target_id in sorted(world.society.polities):
        for kind in ("declare", "lift"):
            if embargo_blocker(world, actor, target_id, checkpoint, kind=kind) is not None:
                continue
            options.append(EmbargoOption(
                id=(f"trade-embargo-{kind}:{actor.id}:{target_id}:{checkpoint.id}:"
                    f"{checkpoint.last_event_id}"),
                actor_ref=actor, target_id=target_id, checkpoint_id=checkpoint.id, kind=kind))
    return tuple(options)


def execute_embargo(world, option, *, decision_event_id):
    """Owner-side revalidation, then one dated policy transition."""
    policy = world.authority.tax_policies.get(option.actor_ref.id)
    checkpoint = world.economy.customs_checkpoints.get(option.checkpoint_id)
    blocker = embargo_blocker(world, option.actor_ref, option.target_id, checkpoint, kind=option.kind)
    if blocker is not None:
        raise ValueError(f"trade embargo unavailable: {blocker}")
    decision = next((item for item in world.events if item.id == decision_event_id), None)
    if (decision is None or decision.fact_kind != FactKind.DECISION
            or decision.day != world.clock.absolute_day or decision.decision != _terms(option)):
        raise ValueError("trade embargo needs a new matching owner decision")
    require_authority(world, option.actor_ref, "taxation")
    before = tuple(policy.embargoed_ids)
    after = (tuple(sorted({*before, option.target_id})) if option.kind == "declare"
             else tuple(item for item in before if item != option.target_id))
    event = record_event(
        world,
        "trade_embargo_declared" if option.kind == "declare" else "trade_embargo_lifted",
        ("A administração passou a recusar a carga dessa contraparte em seu próprio posto."
         if option.kind == "declare" else
         "A administração voltou a aceitar a carga dessa contraparte em seu próprio posto."),
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("tax_policy", policy.id, "embargoed_ids", ",".join(before), ",".join(after)),),
        cause_ids=_causes(decision_event_id, checkpoint.last_event_id))
    world.authority.tax_policies[policy.id] = policy.model_copy(update={
        "embargoed_ids": after, "embargo_policy_event_id": event.id, "last_event_id": event.id})
    return event


def embargo_adapters():
    from .institutional_decision_turn import DiscretionaryAdapter

    def execute(world, actor, option_id, decision_event_id):
        option = next((item for item in embargo_options(world, actor) if item.id == option_id), None)
        if option is None:
            raise ValueError("trade embargo option is stale or unknown")
        # The turn carries only the affordance ID; the owner recomposes the
        # counterparty and the post into its own dated authorization.
        authorization = record_event(
            world, "trade_embargo_authorized", "A instituição autorizou a medida comercial escolhida.",
            fact_kind=FactKind.DECISION, decision=_terms(option), cause_ids=(decision_event_id,))
        execute_embargo(world, option, decision_event_id=authorization.id)

    return (DiscretionaryAdapter(
        name="trade_embargo", family="customs", options_fn=embargo_options,
        label_fn=lambda option: (f"Recusar a carga de {option.target_id} no próprio posto."
                                 if option.kind == "declare"
                                 else f"Voltar a aceitar a carga de {option.target_id} no próprio posto."),
        causes_fn=lambda world, option: _causes(
            world.economy.customs_checkpoints[option.checkpoint_id].last_event_id),
        execute_fn=execute),)


__all__ = ["DECLARE_ACTION", "LIFT_ACTION", "EmbargoOption", "embargo_adapters", "embargo_blocker",
           "embargo_options", "embargoes_of", "execute_embargo", "is_embargoed", "operated_checkpoints"]

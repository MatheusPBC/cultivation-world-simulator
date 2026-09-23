"""Material, dated field instruction of a named detachment.

Institutional knowledge only makes this choice possible.  The column must
remain in place and eat for three days after its owner commits local tools.
Only its own completed instruction can contribute to field strength.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import DetachmentTraining
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _apply_stock, _causes, _delta
from .events import record_event
from .force import _decision


TRAIN_ACTION = "train_detachment"
TRAIN_KIND = "force_training"
TRAIN_DAYS = 3
TRAIN_TECHNOLOGIES = ("field_drill", "siegecraft", "field_logistics")


@dataclass(frozen=True)
class DetachmentTrainingOption:
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    technology_id: Identity
    stock_id: Identity
    tool_cost: int

    def decision(self):
        return {"action": TRAIN_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _knowledge(world, actor, technology_id):
    return next((item for item in world.knowledge.technologies.values()
                 if item.owner_ref == actor and item.technology_id == technology_id), None)


def _completed(world, detachment_id, technology_id):
    return next((item for item in world.society.detachment_trainings.values()
                 if item.detachment_id == detachment_id and item.technology_id == technology_id
                 and item.stage == "completed"), None)


def _occupied_by_training(world, detachment_id):
    return any(item.detachment_id == detachment_id and item.stage == "training"
               for item in world.society.detachment_trainings.values())


def _busy_in_combat(world, detachment_id):
    return (any(item.stage == "active" and detachment_id in item.detachment_ids
                for item in world.society.force_standoffs.values())
            or any(item.status == "offered" and detachment_id in
                   {item.challenger_detachment_id, item.defender_detachment_id}
                   for item in world.society.field_engagements.values()))


def training_options(world, actor, *, detachment_id=None):
    if not isinstance(actor, EntityRef) or not can_actor_act_for(world, actor, actor, "military"):
        return ()
    options = []
    for detachment in sorted(world.society.detachments.values(), key=lambda item: item.id):
        if (detachment.owner_ref != actor or detachment.stage != "present"
                or (detachment_id is not None and detachment.id != detachment_id)
                or detachment.provisions < (TRAIN_DAYS + 1) * detachment.count
                or _occupied_by_training(world, detachment.id)
                or _busy_in_combat(world, detachment.id)):
            continue
        for technology_id in TRAIN_TECHNOLOGIES:
            knowledge = _knowledge(world, actor, technology_id)
            if (knowledge is None or _completed(world, detachment.id, technology_id) is not None
                    or (technology_id in {"siegecraft", "field_logistics"}
                        and _completed(world, detachment.id, "field_drill") is None)):
                continue
            cost = max(1, (detachment.count + 19) // 20) * (2 if technology_id != "field_drill" else 1)
            for stock in sorted(world.economy.stocks.values(), key=lambda item: item.id):
                if (stock.owner_ref != actor or stock.location_id != detachment.location_id
                        or stock.goods.get("tools", 0) < cost):
                    continue
                options.append(DetachmentTrainingOption(
                    id=(f"detachment-training:{detachment.id}:{technology_id}:{stock.id}:"
                        f"{detachment.last_event_id}:{stock.last_event_ids.get('tools', 'premise')}:"
                        f"{knowledge.event_id}"), actor_ref=actor, detachment_id=detachment.id,
                    technology_id=technology_id, stock_id=stock.id, tool_cost=cost))
    return tuple(sorted(options, key=lambda item: item.id))


def start_training(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, TRAIN_ACTION)
    if decided_by != actor:
        raise ValueError("detachment training has the wrong actor")
    option = next((item for item in training_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("detachment training option is stale or unknown")
    require_authority(candidate, actor, "military")
    detachment = candidate.society.detachments[option.detachment_id]
    knowledge = _knowledge(candidate, actor, option.technology_id)
    stock = candidate.economy.stocks[option.stock_id]
    authorship = {"decision_event_id": decision.id, "actor_ref": actor.to_dict(),
                  "selected_affordance_id": option.id}
    goods = {**stock.goods, "tools": stock.goods["tools"] - option.tool_cost}
    equipped = _apply_stock(
        candidate, stock, goods, "detachment_training_tools_committed",
        "Ferramentas locais foram consumidas na instrução da coluna.",
        cause_ids=_causes(decision.id, knowledge.event_id, detachment.last_event_id),
        causal_origin=CausalOrigin.ACTOR_DECISION, causal_payload=authorship)
    identity = f"detachment-training:{detachment.id}:{option.technology_id}:{decision.id}"
    training = DetachmentTraining(
        id=identity, detachment_id=detachment.id, technology_id=option.technology_id,
        settlement_id=detachment.location_id, stage="training",
        started_day=candidate.clock.absolute_day, ready_day=candidate.clock.absolute_day + TRAIN_DAYS,
        decision_event_id=decision.id, knowledge_event_id=knowledge.event_id, last_event_id="pending")
    started = record_event(
        candidate, "detachment_training_started", "A coluna iniciou três dias de instrução material.",
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload=authorship,
        deltas=(_delta("detachment_training", identity, "stage", None, "training"),
                _delta("detachment_training", identity, "technology_id", None, option.technology_id),
                _delta("detachment_training", identity, "ready_day", None, training.ready_day)),
        cause_ids=_causes(decision.id, equipped.id, knowledge.event_id, detachment.last_event_id))
    candidate.society.detachment_trainings[identity] = training.model_copy(update={"last_event_id": started.id})
    candidate.agenda.schedule(ScheduledSituation(identity, TRAIN_KIND, training.ready_day))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachment_trainings[identity]


def lapse_training_for(world, detachment, *, cause_ids=()):
    lapsed = []
    for training in tuple(world.society.detachment_trainings.values()):
        if training.detachment_id != detachment.id or training.stage != "training":
            continue
        event = record_event(
            world, "detachment_training_lapsed", "A instrução cessou com a perda de presença ou provisões.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("detachment_training", training.id, "stage", "training", "lapsed"),),
            cause_ids=_causes(training.last_event_id, detachment.last_event_id, *cause_ids))
        world.society.detachment_trainings[training.id] = training.model_copy(
            update={"stage": "lapsed", "last_event_id": event.id})
        world.agenda.cancel(training.id)
        lapsed.append(event)
    return tuple(lapsed)


def resolve_trainings(world, situations):
    for situation in sorted(situations, key=lambda item: item.id):
        if situation.kind != TRAIN_KIND:
            raise ValueError("unknown force training situation")
        training = world.society.detachment_trainings.get(situation.id)
        if training is None or training.stage != "training":
            continue
        if training.ready_day != world.clock.absolute_day:
            raise ValueError("inconsistent force training deadline")
        detachment = world.society.detachments.get(training.detachment_id)
        if (detachment is None or detachment.stage != "present"
                or detachment.location_id != training.settlement_id
                or detachment.provisions < detachment.count):
            if detachment is not None:
                lapse_training_for(world, detachment, cause_ids=(training.last_event_id,))
            continue
        event = record_event(
            world, "detachment_training_completed", "A coluna concluiu três dias de instrução abastecida.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("detachment_training", training.id, "stage", "training", "completed"),),
            cause_ids=_causes(training.last_event_id, detachment.last_event_id,
                              training.knowledge_event_id))
        world.society.detachment_trainings[training.id] = training.model_copy(
            update={"stage": "completed", "last_event_id": event.id})
        if training.technology_id == "field_logistics":
            from .campaign_supply import apply_logistics_training
            apply_logistics_training(world, detachment, event.id)


def training_adapters():
    from .institutional_decision_turn import DiscretionaryAdapter

    def causes(world, option):
        detachment = world.society.detachments.get(option.detachment_id)
        stock = world.economy.stocks.get(option.stock_id)
        knowledge = _knowledge(world, option.actor_ref, option.technology_id)
        return _causes(detachment.last_event_id if detachment else None,
                       stock.last_event_ids.get("tools") if stock else None,
                       knowledge.event_id if knowledge else None)

    return (DiscretionaryAdapter(
        name="detachment_training", options_fn=training_options,
        label_fn=lambda option: (f"Treinar a coluna {option.detachment_id} em {option.technology_id} "
                                 f"por três dias, consumindo {option.tool_cost} ferramentas e rações."),
        causes_fn=causes,
        execute_fn=lambda world, actor, option_id, decision_id: start_training(world, actor, option_id, decision_id),
        family="campaign"),)

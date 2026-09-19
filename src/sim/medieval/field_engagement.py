"""A voluntarily joined field clash; no campaign, siege, loot, or occupation rule."""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.knowledge import (field_engagement_offer_notice_id,
                                               field_engagement_outcome_notice_id)
from src.classes.governance.models import FieldEngagementOfferNotice, FieldEngagementOutcomeNotice
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import FieldEngagement
from src.classes.society.models import Identity
from src.classes.environment.tile import TileType
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _causes, _delta
from .events import record_event
from .force_command import effective_doctrine
from .force import (_active_pair, _dissolve, _position_id, _strength_band,
                    POSITION_PREPARATION_DAYS)


OFFER_ACTION = "offer_field_engagement"
JOIN_ACTION = "join_field_engagement"
REVIEW_DAYS = 1
EXPIRY_DAYS = 2
SUPPLY_DAYS = 3


@dataclass(frozen=True)
class FieldEngagementOfferOption:
    id: Identity
    actor_ref: EntityRef
    notice_id: Identity
    standoff_id: Identity
    detachment_id: Identity

    def decision(self):
        return {"action": OFFER_ACTION, "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


@dataclass(frozen=True)
class FieldEngagementJoinOption:
    id: Identity
    actor_ref: EntityRef
    engagement_id: Identity
    notice_id: Identity

    def decision(self):
        return {"action": JOIN_ACTION, "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


def _supplied(detachment):
    return detachment.provisions >= SUPPLY_DAYS * detachment.count


def _prepared(world, detachment):
    position = world.society.force_positions.get(_position_id(detachment.id))
    return position is not None and position.stage == "prepared"


def _military_training_bonus(world, detachment):
    """Return the bounded effect of a learned field-training technology."""
    trained = sum(
        knowledge.owner_ref == detachment.owner_ref
        and (technology := world.research.technologies.get(knowledge.technology_id)) is not None
        and technology.capability_id == "military_training"
        for knowledge in world.knowledge.technologies.values()
    )
    return min(2, trained)


def _sighting_current(world, notice):
    standoff = world.society.force_standoffs.get(notice.standoff_id)
    return (standoff is not None and standoff.stage == "active"
            and world.clock.absolute_day - notice.learned_day < 3)


def _open_for_standoff(world, standoff_id):
    return any(item.standoff_id == standoff_id and item.status == "offered"
               for item in world.society.field_engagements.values())


def field_engagement_offer_options(world, actor, *, notice_id=None):
    """Only a supplied owner with a current bounded sighting may challenge."""
    if not can_actor_act_for(world, actor, actor, "military"):
        return ()
    options = []
    for notice in world.knowledge.force_contacts_for_actor(actor):
        if notice_id is not None and notice.id != notice_id:
            continue
        detachment = world.society.detachments.get(notice.own_detachment_id)
        if (detachment is None or detachment.owner_ref != actor or detachment.stage != "present"
                or detachment.location_id != notice.settlement_id or not _supplied(detachment)
                or not _sighting_current(world, notice) or _open_for_standoff(world, notice.standoff_id)
                # Hold is a real bounded tactical choice: it never prevents an
                # answer to a challenge, but does prevent this column opening one.
                or effective_doctrine(world, detachment.id) == "hold"):
            continue
        standoff = world.society.force_standoffs[notice.standoff_id]
        options.append(FieldEngagementOfferOption(
            id=f"field-engagement-offer:{notice.id}:{detachment.last_event_id}:{standoff.last_event_id}",
            actor_ref=actor, notice_id=notice.id, standoff_id=notice.standoff_id, detachment_id=detachment.id))
    return tuple(sorted(options, key=lambda item: item.id))


def offer_field_engagement(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in field_engagement_offer_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("field engagement option is stale or unknown")
    from .force import _decision
    decision, decided_by = _decision(candidate, decision_event_id, OFFER_ACTION)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("field engagement offer has the wrong decision")
    require_authority(candidate, actor, "military")
    notice = candidate.knowledge.force_contact_notices[option.notice_id]
    if not _sighting_current(candidate, notice):
        raise ValueError("field engagement sighting is no longer current")
    standoff = candidate.society.force_standoffs[option.standoff_id]
    pair = _active_pair(candidate, standoff)
    if pair is None:
        raise ValueError("armed contact is no longer current")
    challenger = next(item for item in pair if item.id == option.detachment_id)
    defender = next(item for item in pair if item.id != challenger.id)
    if challenger.owner_ref != actor or not _supplied(challenger):
        raise ValueError("challenger is no longer supplied")
    defender_contact = next((item for item in candidate.knowledge.force_contacts_for_actor(defender.owner_ref)
                             if item.standoff_id == standoff.id and item.own_detachment_id == defender.id), None)
    if defender_contact is None:
        raise ValueError("defender has no current contact notice")
    engagement = FieldEngagement(
        id=f"field-engagement:{decision.id}", standoff_id=standoff.id,
        challenger_ref=challenger.owner_ref, defender_ref=defender.owner_ref,
        challenger_detachment_id=challenger.id, defender_detachment_id=defender.id,
        settlement_id=standoff.settlement_id, offered_day=candidate.clock.absolute_day,
        expires_day=candidate.clock.absolute_day + EXPIRY_DAYS, decision_event_id=decision.id,
        offer_event_id="pending", last_event_id="pending")
    offer_notice = FieldEngagementOfferNotice(
        id=field_engagement_offer_notice_id(engagement.id, defender.owner_ref), recipient_ref=defender.owner_ref,
        engagement_id=engagement.id, standoff_id=standoff.id, challenger_ref=challenger.owner_ref,
        settlement_id=standoff.settlement_id, event_id="pending", learned_day=candidate.clock.absolute_day)
    event = record_event(
        candidate, "field_engagement_offered", "Uma coluna desafiou a rival para um combate de campo voluntário.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("field_engagement", engagement.id, "status", None, "offered"),
                _delta("field_engagement_offer_notice", offer_notice.id, "engagement_id", None, engagement.id)),
        cause_ids=_causes(decision.id, standoff.last_event_id, challenger.last_event_id))
    engagement = engagement.model_copy(update={"offer_event_id": event.id, "last_event_id": event.id})
    candidate.society.field_engagements[engagement.id] = engagement
    candidate.knowledge.field_engagement_offer_notices[offer_notice.id] = offer_notice.model_copy(update={"event_id": event.id})
    candidate.agenda.schedule(ScheduledSituation(engagement.id, "field_engagement", engagement.expires_day))
    from .force_contact_policy import schedule_contact_review
    schedule_contact_review(candidate, defender_contact, candidate.clock.absolute_day + REVIEW_DAYS)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.field_engagements[engagement.id]


def field_engagement_join_options(world, actor, *, notice_id=None):
    """The challenged side can only join; it may still choose no action or leave."""
    if not can_actor_act_for(world, actor, actor, "military"):
        return ()
    contact_standoffs = {notice.standoff_id for notice in world.knowledge.force_contacts_for_actor(actor)
                         if notice_id is None or notice.id == notice_id}
    options = []
    for notice in world.knowledge.field_engagement_offers_for_actor(actor):
        engagement = world.society.field_engagements.get(notice.engagement_id)
        standoff = world.society.force_standoffs.get(notice.standoff_id)
        if (engagement is None or engagement.status != "offered" or engagement.defender_ref != actor
                or engagement.offered_day >= world.clock.absolute_day or engagement.expires_day <= world.clock.absolute_day
                or notice.standoff_id not in contact_standoffs or standoff is None or standoff.stage != "active"):
            continue
        options.append(FieldEngagementJoinOption(
            id=f"field-engagement-join:{engagement.id}:{engagement.last_event_id}", actor_ref=actor,
            engagement_id=engagement.id, notice_id=notice.id))
    return tuple(sorted(options, key=lambda item: item.id))


def _casualties(count, rate_permille, survivors=1):
    if count <= survivors:
        return 0
    return min(count - survivors, max(1, count * rate_permille // 1000))


def field_strength(world, detachment):
    """The whole deterministic formula, exposed for audit and focused tests."""
    prepared, supplied = _prepared(world, detachment), _supplied(detachment)
    doctrine = effective_doctrine(world, detachment.id)
    prepared_bonus = 2 if doctrine == "hold" else 0 if doctrine == "press" else 1
    supplied_bonus = 2 if doctrine == "press" else 0 if doctrine == "hold" else 1
    training_bonus = _military_training_bonus(world, detachment)
    return detachment.count * (2 + training_bonus + int(prepared) * prepared_bonus + int(supplied) * supplied_bonus), prepared, supplied


def _engagement_strength(world, detachment):
    """Pure engagement reading: press spends preparation without mutating it yet."""
    strength, prepared, supplied = field_strength(world, detachment)
    doctrine = effective_doctrine(world, detachment.id)
    if doctrine == "press" and prepared:
        prepared = False
        strength = detachment.count * (2 + 2 * int(supplied))
    terrain = _terrain_modifier(world, detachment.location_id, doctrine)
    fatigue = _fatigue_level(world, detachment)
    morale = _morale_level(prepared=prepared, supplied=supplied, fatigue=fatigue)
    strength = max(1, strength + detachment.count * (terrain - fatigue + morale - 1))
    return strength, prepared, supplied, doctrine, morale


def _morale_level(*, prepared, supplied, fatigue):
    """Bounded material morale reading used only by field resolution.

    Morale is not a personality label and is never selected by a provider.  It
    is the current tactical posture: a supplied, prepared column starts high;
    missing provisions and prolonged deployment lower it.  The value is kept
    deliberately small so it cannot become a hidden second combat system.
    """
    value = 1 + int(supplied) + int(prepared) - min(2, fatigue)
    return max(0, min(2, value))


def _terrain_modifier(world, settlement_id, doctrine):
    """Bounded Map-owned reading of the physical ground under a clash.

    It is deliberately derived from existing geography, never selected by an
    actor or inferred from prose.  Plain/urban ground is neutral; forest,
    mountain and marsh favour a prepared hold, while open grassland/farm
    favours a prepared press.  A missing footprint is neutral rather than a
    hidden assumption.
    """
    settlement = world.society.settlements.get(settlement_id)
    if settlement is None:
        return 0
    coordinates = world.map._region_coordinates(settlement.region_id)
    terrain = [world.map.get_terrain(*coordinate) for coordinate in coordinates]
    terrain = [item for item in terrain if item is not None]
    if not terrain:
        return 0
    difficult = sum(item in {TileType.FOREST, TileType.MOUNTAIN, TileType.SWAMP, TileType.MARSH}
                    for item in terrain)
    open_ground = sum(item in {TileType.PLAIN, TileType.GRASSLAND, TileType.FARM}
                      for item in terrain)
    if difficult <= len(terrain) // 2 and open_ground <= len(terrain) // 2:
        return 0
    if difficult > open_ground:
        return 1 if doctrine == "hold" else -1
    return 1 if doctrine == "press" else 0


def _fatigue_level(world, detachment):
    """A small deterministic fatigue reading from uninterrupted deployment."""
    return min(2, max(0, (world.clock.absolute_day - detachment.started_day) // 30))


def _pre_offer_contact(world, engagement, detachment, counterparty_ref):
    """A reinforcement must have independently met this opponent before the offer.

    There is no same-day ordering primitive in the calendar.  Requiring a
    standoff begun on an earlier day is the small deterministic boundary that
    prevents a column arriving after (or alongside) an offer being conscripted
    invisibly into a fight it never had time to observe.
    """
    for notice in world.knowledge.force_contacts_for_actor(detachment.owner_ref):
        standoff = world.society.force_standoffs.get(notice.standoff_id)
        if (notice.own_detachment_id == detachment.id and notice.settlement_id == engagement.settlement_id
                and notice.counterparty_ref == counterparty_ref and standoff is not None
                and standoff.stage == "active" and standoff.started_day < engagement.offered_day
                and _sighting_current(world, notice)):
            return notice
    return None


def _participants(world, engagement, owner_ref, anchor_id, counterparty_ref):
    """Only an anchor or a prior-contact column explicitly set to press participates.

    The engagement remains a 1x1 invitation.  This merely aggregates each
    side's real, willing columns at resolution; a marching, withdrawn, foreign,
    newly-arrived, holding or elsewhere column is never pulled in.
    """
    columns = []
    for item in world.society.detachments.values():
        if (item.owner_ref != owner_ref or item.stage != "present"
                or item.location_id != engagement.settlement_id):
            continue
        if item.id == anchor_id:
            columns.append(item)
            continue
        if (effective_doctrine(world, item.id) == "press"
                and _pre_offer_contact(world, engagement, item, counterparty_ref) is not None):
            columns.append(item)
    return tuple(sorted(columns, key=lambda item: item.id))


def _participant_cause_ids(world, engagement, columns, anchor_id, counterparty_ref):
    """Direct provenance for each enrolled column and its deliberate readiness."""
    evidence = []
    for column in columns:
        evidence.append(column.last_event_id)
        if column.id == anchor_id:
            continue
        contact = _pre_offer_contact(world, engagement, column, counterparty_ref)
        command = world.society.detachment_commands.get(column.id)
        if contact is not None:
            evidence.append(contact.last_event_id)
        if command is not None:
            evidence.append(command.last_event_id)
    return tuple(evidence)


def _side_terms(world, columns):
    return tuple((column, *_engagement_strength(world, column)) for column in columns)


def _distribute_casualties(total, columns):
    """Allocate a side's bounded loss deterministically without erasing a column."""
    population = sum(column.count for column in columns)
    if total == 0:
        return {column.id: 0 for column in columns}
    allocations = {column.id: total * column.count // population for column in columns}
    remainder = total - sum(allocations.values())
    order = sorted(columns, key=lambda column: (-(total * column.count % population), column.id))
    for column in order[:remainder]:
        allocations[column.id] += 1
    if any(not 0 <= allocations[column.id] < column.count for column in columns):
        raise ValueError("field engagement casualty allocation cannot erase a column")
    return allocations


def join_field_engagement(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in field_engagement_join_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("field engagement join is stale or unknown")
    from .force import _decision
    decision, decided_by = _decision(candidate, decision_event_id, JOIN_ACTION)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("field engagement join has the wrong decision")
    engagement = candidate.society.field_engagements[option.engagement_id]
    require_authority(candidate, engagement.challenger_ref, "military")
    require_authority(candidate, engagement.defender_ref, "military")
    standoff = candidate.society.force_standoffs.get(engagement.standoff_id)
    pair = _active_pair(candidate, standoff) if standoff is not None else None
    if pair is None or {item.id for item in pair} != {engagement.challenger_detachment_id,
                                                       engagement.defender_detachment_id}:
        raise ValueError("field engagement contact is no longer current")
    if candidate.society.settlements[engagement.settlement_id].occupier_id is not None:
        raise ValueError("field engagement cannot change an existing occupation")
    challenger = candidate.society.detachments[engagement.challenger_detachment_id]
    defender = candidate.society.detachments[engagement.defender_detachment_id]
    challenger_columns = _participants(candidate, engagement, engagement.challenger_ref, challenger.id,
                                       engagement.defender_ref)
    defender_columns = _participants(candidate, engagement, engagement.defender_ref, defender.id,
                                     engagement.challenger_ref)
    if (challenger.id not in {item.id for item in challenger_columns}
            or defender.id not in {item.id for item in defender_columns}):
        raise ValueError("field engagement columns are no longer present")
    # Compute every material allocation before abandoning a prepared press
    # position.  A bad shared cohort or bounded allocation is rejected with no
    # candidate mutation, and press is already represented as unprepared by
    # the pure engagement reading above.
    challenger_terms = _side_terms(candidate, challenger_columns)
    defender_terms = _side_terms(candidate, defender_columns)
    challenger_strength = sum(term[1] for term in challenger_terms)
    defender_strength = sum(term[1] for term in defender_terms)
    challenger_count = sum(item.count for item in challenger_columns)
    defender_count = sum(item.count for item in defender_columns)
    challenger_primary = next(term for term in challenger_terms if term[0].id == challenger.id)
    defender_primary = next(term for term in defender_terms if term[0].id == defender.id)
    challenger_prepared, challenger_supplied = challenger_primary[2:4]
    defender_prepared, defender_supplied = defender_primary[2:4]
    if challenger_strength > defender_strength:
        winner, loser = challenger, defender
        ratio = defender_strength * 1000 // challenger_strength
        challenger_losses = _casualties(challenger_count, 200 * ratio // 1000, len(challenger_columns))
        defender_losses = _casualties(defender_count, 200, len(defender_columns))
    elif defender_strength > challenger_strength:
        winner, loser = defender, challenger
        ratio = challenger_strength * 1000 // defender_strength
        challenger_losses = _casualties(challenger_count, 200, len(challenger_columns))
        defender_losses = _casualties(defender_count, 200 * ratio // 1000, len(defender_columns))
    else:
        winner = loser = None
        ratio = 1000
        challenger_losses = _casualties(challenger_count, 100, len(challenger_columns))
        defender_losses = _casualties(defender_count, 100, len(defender_columns))
    losses = {**_distribute_casualties(challenger_losses, challenger_columns),
              **_distribute_casualties(defender_losses, defender_columns)}
    columns = (*challenger_columns, *defender_columns)
    groups = {detachment.source_group_id: candidate.society.population[detachment.source_group_id]
              for detachment in columns}
    group_losses = {group_id: sum(losses[item.id] for item in columns
                                  if item.source_group_id == group_id)
                    for group_id in groups}
    if any(groups[group_id].count <= loss for group_id, loss in group_losses.items() if loss):
        raise ValueError("field engagement cannot erase a source cohort")
    # Press spends the existing prepared position at the moment a real
    # engagement begins.  The abandonment is a separate causal fact rather
    # than an invisible combat modifier.
    press_abandonments = []
    for detachment in (*challenger_columns, *defender_columns):
        if effective_doctrine(candidate, detachment.id) == "press" and _prepared(candidate, detachment):
            from .force import _abandon_force_position
            abandoned = _abandon_force_position(candidate, detachment, cause_ids=(decision.id, engagement.last_event_id))
            if abandoned is not None:
                press_abandonments.append(abandoned)
    winner_ref = winner.owner_ref if winner is not None else None
    outcomes = ((challenger, defender, challenger_losses, challenger_prepared, challenger_supplied, defender_count),
                (defender, challenger, defender_losses, defender_prepared, defender_supplied, challenger_count))
    notices = []
    for own, other, own_losses, prepared, supplied, opposing_count in outcomes:
        outcome = ("won" if winner is own else "lost" if winner is other else "indecisive")
        notices.append(FieldEngagementOutcomeNotice(
            id=field_engagement_outcome_notice_id(engagement.id, own.owner_ref), recipient_ref=own.owner_ref,
            engagement_id=engagement.id, own_detachment_id=own.id,
            settlement_id=engagement.settlement_id, counterparty_ref=other.owner_ref,
            own_casualties=own_losses, counterparty_strength_band=_strength_band(opposing_count), outcome=outcome,
            own_prepared=prepared, own_supplied=supplied, event_id="pending", learned_day=candidate.clock.absolute_day))
    deltas = [
        _delta("field_engagement", engagement.id, "status", "offered", "resolved"),
        _delta("field_engagement", engagement.id, "winner_ref", None, winner_ref),
        _delta("field_engagement", engagement.id, "challenger_casualties", 0, challenger_losses),
        _delta("field_engagement", engagement.id, "defender_casualties", 0, defender_losses),
        _delta("field_engagement", engagement.id, "challenger_terms",
               None, f"columns={len(challenger_columns)};count={challenger_count};strength={challenger_strength}"),
        _delta("field_engagement", engagement.id, "defender_terms",
               None, f"columns={len(defender_columns)};count={defender_count};strength={defender_strength}"),
    ]
    for side, terms in (("challenger", challenger_terms), ("defender", defender_terms)):
        for detachment, strength, prepared, supplied, doctrine, morale in terms:
            deltas.append(_delta(
                "field_engagement", engagement.id, f"{side}_column:{detachment.id}", None,
                f"count={detachment.count};prepared={prepared};supplied={supplied};doctrine={doctrine};strength={strength}"))
            deltas.extend((
                _delta("field_engagement", engagement.id, f"terrain_modifier:{detachment.id}", None,
                       _terrain_modifier(candidate, detachment.location_id, doctrine)),
                _delta("field_engagement", engagement.id, f"fatigue_level:{detachment.id}", None,
                       _fatigue_level(candidate, detachment)),
                _delta("field_engagement", engagement.id, f"morale_level:{detachment.id}", None, morale),
            ))
    for group_id, loss in sorted(group_losses.items()):
        if loss:
            group = groups[group_id]
            deltas.append(_delta("population_group", group.id, "count", group.count, group.count - loss))
    for detachment in columns:
        loss = losses[detachment.id]
        if loss:
            deltas.append(_delta("detachment", detachment.id, "count", detachment.count, detachment.count - loss))
    deltas.extend(delta for notice in notices for delta in (
        _delta("field_engagement_outcome_notice", notice.id, "outcome", None, notice.outcome),
        _delta("field_engagement_outcome_notice", notice.id, "own_casualties", None, notice.own_casualties),
        _delta("field_engagement_outcome_notice", notice.id, "counterparty_strength_band", None,
               notice.counterparty_strength_band),
    ))
    event = record_event(
        candidate, "field_engagement_resolved",
        f"Combate de campo decidido sem sorteio: força {challenger_strength} contra {defender_strength}; razão {ratio}.",
        fact_kind=FactKind.STATE_TRANSITION, deltas=tuple(deltas),
        cause_ids=_causes(engagement.last_event_id, decision.id, standoff.last_event_id,
                          *_participant_cause_ids(candidate, engagement, challenger_columns, challenger.id,
                                                   engagement.defender_ref),
                          *_participant_cause_ids(candidate, engagement, defender_columns, defender.id,
                                                   engagement.challenger_ref),
                          *(item.id for item in press_abandonments)))
    for group_id, loss in group_losses.items():
        if loss:
            group = groups[group_id]
            candidate.society.population[group_id] = group.model_copy(update={"count": group.count - loss})
    for detachment in columns:
        loss = losses[detachment.id]
        candidate.society.detachments[detachment.id] = detachment.model_copy(
            update={"count": detachment.count - loss, "last_event_id": event.id})
    candidate.society.field_engagements[engagement.id] = engagement.model_copy(
        update={"status": "resolved", "winner_ref": winner_ref,
                "challenger_casualties": challenger_losses, "defender_casualties": defender_losses,
                "last_event_id": event.id})
    for notice in notices:
        candidate.knowledge.field_engagement_outcome_notices[notice.id] = notice.model_copy(update={"event_id": event.id})
    candidate.agenda.cancel(engagement.id)
    if loser is not None:
        loser_columns = challenger_columns if loser.owner_ref == engagement.challenger_ref else defender_columns
        for column in loser_columns:
            current_loser = candidate.society.detachments[column.id]
            _dissolve(candidate, current_loser, "field_engagement_loser_dissolved",
                      "Após a derrota, os sobreviventes da coluna se dispersaram; nenhum território mudou de dono.",
                      causes=(event.id,))
    # Only a surviving winner gets one later chance to choose an existing force
    # action.  The outcome notice, rather than hidden engagement state, is the
    # provenance for that private review.
    if winner is not None:
        winner_notice = next(notice for notice in notices if notice.outcome == "won")
        from .field_aftermath_policy import schedule_field_aftermath_review
        schedule_field_aftermath_review(candidate, winner_notice, candidate.clock.absolute_day + REVIEW_DAYS)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.field_engagements[engagement.id]


def resolve_field_engagements(world, situations):
    for situation in sorted(situations, key=lambda item: item.id):
        if situation.kind != "field_engagement":
            raise ValueError("unknown field engagement deadline")
        engagement = world.society.field_engagements.get(situation.id)
        if engagement is None or engagement.status != "offered":
            continue
        if engagement.expires_day != world.clock.absolute_day:
            raise ValueError("field engagement expired on the wrong day")
        event = record_event(
            world, "field_engagement_lapsed", "O desafio de campo expirou sem adesão; nenhuma penalidade ocorreu.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("field_engagement", engagement.id, "status", "offered", "lapsed"),),
            cause_ids=(engagement.last_event_id,))
        world.society.field_engagements[engagement.id] = engagement.model_copy(
            update={"status": "lapsed", "last_event_id": event.id})


__all__ = ["JOIN_ACTION", "OFFER_ACTION", "field_engagement_join_options", "field_engagement_offer_options",
           "field_strength", "join_field_engagement", "offer_field_engagement", "resolve_field_engagements"]

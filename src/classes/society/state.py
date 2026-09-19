"""Canonical population and identity owner for the medieval simulation."""

from dataclasses import dataclass, field

from .models import Character, Occupation, Organization, Polity, PopulationGroup, Settlement
from .migration import MigrationJourney
from .force import (AssemblyDenial, Detachment, DetachmentCommand, FieldEngagement, ForcePosition, ForceStandoff,
                    Garrison, MAX_SIEGE_GARRISON_ENDURANCE, SIEGE_GARRISON_ENDURANCE, SiegeCampaign,
                    RouteInterdiction, SettlementInvestment)
from .control import TerritorialControl
from .civic import CivicProtest
from .movement import CivicMovement
from .strike import CivicStrike
from .amnesty import CivicAmnesty
from .demography import BirthCohort
from .workforce import WorkforceTransition
from .serialization import REGISTRIES, SocietySerialization


@dataclass
class SocietyState(SocietySerialization):
    characters: dict[str, Character] = field(default_factory=dict)
    settlements: dict[str, Settlement] = field(default_factory=dict)
    polities: dict[str, Polity] = field(default_factory=dict)
    organizations: dict[str, Organization] = field(default_factory=dict)
    population: dict[str, PopulationGroup] = field(default_factory=dict)
    migrations: dict[str, MigrationJourney] = field(default_factory=dict)
    workforce_transitions: dict[str, WorkforceTransition] = field(default_factory=dict)
    detachments: dict[str, Detachment] = field(default_factory=dict)
    force_standoffs: dict[str, ForceStandoff] = field(default_factory=dict)
    force_positions: dict[str, ForcePosition] = field(default_factory=dict)
    garrisons: dict[str, Garrison] = field(default_factory=dict)
    territorial_controls: dict[str, TerritorialControl] = field(default_factory=dict)
    siege_campaigns: dict[str, SiegeCampaign] = field(default_factory=dict)
    # Keyed by detachment ID.  A command is active only while its real person,
    # column and appointing military office all remain current.
    detachment_commands: dict[str, DetachmentCommand] = field(default_factory=dict)
    field_engagements: dict[str, FieldEngagement] = field(default_factory=dict)
    route_interdictions: dict[str, RouteInterdiction] = field(default_factory=dict)
    settlement_investments: dict[str, SettlementInvestment] = field(default_factory=dict)
    assembly_denials: dict[str, AssemblyDenial] = field(default_factory=dict)
    civic_protests: dict[str, CivicProtest] = field(default_factory=dict)
    civic_movements: dict[str, CivicMovement] = field(default_factory=dict)
    civic_strikes: dict[str, CivicStrike] = field(default_factory=dict)
    civic_amnesties: dict[str, CivicAmnesty] = field(default_factory=dict)
    # Dated batches of new residents; they hold no claim over the people who
    # may have left or died before they reach working age.
    birth_cohorts: dict[str, BirthCohort] = field(default_factory=dict)

    @property
    def total_population(self) -> int:
        return sum(group.count for group in self.population.values())

    def population_at(self, settlement_id: str) -> int:
        return sum(g.count for g in self.population.values() if g.settlement_id == settlement_id)

    def present_population_at(self, settlement_id: str) -> int:
        return sum(self.available_count(g.id) for g in self.population.values() if g.settlement_id == settlement_id)

    def transfer_administration(self, settlement_id: str, administrator_id: str, successor_id: str):
        """Change only the canonical administrator after its owner has decided.

        This owner method deliberately knows nothing about diplomacy, forces,
        accounts or territorial claims.  Its caller must record the factual
        receipt and prove the current authority separately.
        """
        settlement = self.settlements.get(settlement_id)
        if (settlement is None or settlement.administrator_id != administrator_id
                or successor_id not in self.polities):
            raise ValueError("administration transfer is no longer current")
        self.settlements[settlement_id] = settlement.model_copy(update={"administrator_id": successor_id})
        return settlement

    def available_count(self, group_id: str) -> int:
        group = self.population[group_id]
        traveling = sum(j.count for j in self.migrations.values() if j.source_group_id == group_id)
        transitioning = sum(t.count for t in self.workforce_transitions.values() if t.source_group_id == group_id)
        # Raised soldiers are away from their cohort: they cannot also produce,
        # research or migrate while the detachment stands.
        detached = sum(d.count for d in self.detachments.values()
                       if d.source_group_id == group_id and d.stage != "disbanded")
        protesting = sum(item.participants for item in self.civic_protests.values()
                          if item.group_id == group_id and item.stage == "open")
        moving = sum(item.participants_by_group.get(group_id, 0)
                     for item in self.civic_movements.values()
                     if item.stage in {"active", "rebellion", "revolution", "negotiating"})
        striking = sum(item.participants_by_group.get(group_id, 0)
                       for item in self.civic_strikes.values() if item.stage == "active")
        return group.count - traveling - transitioning - detached - protesting - moving - striking

    def validate(self, region_ids: set[int] | None = None, world=None) -> None:
        for name, model in REGISTRIES.items():
            for key, value in getattr(self, name).items():
                if not isinstance(value, model) or key != value.id:
                    raise ValueError(f"invalid {name} registry identity")
        seen_regions = set()
        for settlement in self.settlements.values():
            if settlement.region_id in seen_regions:
                raise ValueError("duplicate settlement region")
            seen_regions.add(settlement.region_id)
            if region_ids is not None and settlement.region_id not in region_ids:
                raise ValueError("settlement references unknown map region")
            for polity_id in (settlement.administrator_id, settlement.occupier_id, *settlement.claimant_ids):
                if polity_id is not None and polity_id not in self.polities:
                    raise ValueError("settlement references unknown polity")
            if len(set(settlement.claimant_ids)) != len(settlement.claimant_ids):
                raise ValueError("duplicate territorial claims")
        for polity in self.polities.values():
            if polity.capital_id not in self.settlements:
                raise ValueError("unknown capital settlement")
        for organization in self.organizations.values():
            if organization.seat_id not in self.settlements:
                raise ValueError("unknown organization seat")
            if any(member not in self.characters for member in organization.member_ids):
                raise ValueError("unknown organization member")
        named_counts: dict[str, int] = {}
        for character in self.characters.values():
            if character.location_id not in self.settlements:
                raise ValueError("unknown character location")
            if character.death_day is not None:
                continue
            group = self.population.get(character.population_group_id)
            if group is None or group.people != character.people:
                raise ValueError("invalid character population reference")
            named_counts[group.id] = named_counts.get(group.id, 0) + 1
        demographics = set()
        for group in self.population.values():
            if group.settlement_id not in self.settlements:
                raise ValueError("unknown population settlement")
            key = (group.settlement_id, group.people, group.occupation)
            if key in demographics:
                raise ValueError("duplicate population cohort")
            demographics.add(key)
            if named_counts.get(group.id, 0) > group.count:
                raise ValueError("named population exceeds cohort count")
        migrating_groups = set()
        migrating_characters = set()
        for key, journey in self.migrations.items():
            if key != journey.id or journey.source_group_id not in self.population or journey.destination_id not in self.settlements:
                raise ValueError("invalid migration journey")
            if not journey.route_ids or not journey.initial_route_ids or journey.route_index >= len(journey.route_ids):
                raise ValueError("invalid migration route")
            if journey.source_group_id in migrating_groups:
                raise ValueError("a cohort may have only one active migration")
            if migrating_characters.intersection(journey.character_ids):
                raise ValueError("a named resident cannot join two journeys")
            migrating_groups.add(journey.source_group_id)
            migrating_characters.update(journey.character_ids)
            self._select_people(journey.source_group_id, journey.count, journey.character_ids)
        transitioning_groups = set()
        for key, transition in self.workforce_transitions.items():
            source = self.population.get(transition.source_group_id)
            expected_occupations = {
                "facility": {"farmer", "artisan"},
                "repair": {"artisan"},
                "customs": {"merchant"},
            }.get(transition.work_kind, set())
            traveling = source is not None and transition.destination_settlement_id != source.settlement_id
            # A customs recruitment never leaves its own settlement in this
            # version; only facility/repair demand may relocate the recruit.
            if (key != transition.id or source is None or transition.source_group_id in migrating_groups
                    or transition.source_group_id in transitioning_groups
                    or not expected_occupations
                    or transition.target_occupation not in expected_occupations
                    or source.occupation == transition.target_occupation
                    or transition.destination_settlement_id not in self.settlements
                    or (traveling and transition.work_kind == "customs")
                    or transition.target_group_id != (f"pop:{transition.destination_settlement_id}:"
                                                       f"{source.people}:{transition.target_occupation}")
                    or (transition.due_day != transition.started_day + 30 if not traveling
                        else transition.due_day <= transition.started_day)):
                raise ValueError("invalid workforce transition")
            self._select_people(transition.source_group_id, transition.count, ())
            transitioning_groups.add(transition.source_group_id)
        for key, detachment in self.detachments.items():
            source = self.population.get(detachment.source_group_id)
            if (key != detachment.id or source is None or source.occupation != "soldier"
                    or detachment.location_id not in self.settlements
                    or detachment.destination_id not in self.settlements
                    or detachment.due_day < detachment.started_day):
                raise ValueError("invalid detachment")
            if detachment.stage == "disbanded":
                continue
            if (detachment.stage == "marching") != (detachment.route_index < len(detachment.route_ids)):
                raise ValueError("invalid detachment position")
            self._select_people(detachment.source_group_id, detachment.count, ())
        for key, standoff in self.force_standoffs.items():
            left_id, right_id = standoff.detachment_ids
            left = self.detachments.get(left_id)
            right = self.detachments.get(right_id)
            if (key != standoff.id or left is None or right is None
                    or standoff.settlement_id not in self.settlements
                    or left.owner_ref == right.owner_ref):
                raise ValueError("invalid force standoff")
            if standoff.stage == "active" and (left.stage != "present" or right.stage != "present"
                                                or left.location_id != standoff.settlement_id
                                                or right.location_id != standoff.settlement_id):
                raise ValueError("active standoff requires two present rival detachments")
        positioned = set()
        for key, position in self.force_positions.items():
            detachment = self.detachments.get(position.detachment_id)
            if (key != position.id or position.detachment_id in positioned or detachment is None
                    or detachment.stage != "present" or detachment.location_id != position.settlement_id):
                raise ValueError("force position requires one present stationary detachment")
            positioned.add(position.detachment_id)
            if world is not None and position.anchor_site_id is not None:
                site = world.map.infrastructure_sites.get(position.anchor_site_id)
                settlement = self.settlements[position.settlement_id]
                if site is None or settlement.region_id not in site.region_ids:
                    raise ValueError("force position anchor must be an existing local map site")
        for key, garrison in self.garrisons.items():
            detachment = self.detachments.get(garrison.detachment_id)
            settlement = self.settlements.get(garrison.settlement_id)
            if (key != garrison.id or detachment is None or settlement is None
                    or garrison.account_id == "" or garrison.decision_event_id == ""
                    or (garrison.stage == "active" and (
                        detachment.stage != "present" or detachment.location_id != settlement.id
                        or settlement.occupier_id != detachment.owner_ref.id))):
                raise ValueError("active garrison requires its present occupied detachment")
            if world is not None and garrison.account_id not in world.economy.accounts:
                raise ValueError("garrison requires an existing owner account")
        for key, control in self.territorial_controls.items():
            settlement = self.settlements.get(control.settlement_id)
            controller_exists = ((control.controller_kind == "polity" and control.controller_id in self.polities)
                                 or (control.controller_kind == "organization"
                                     and control.controller_id in self.organizations))
            if key != control.id or settlement is None or not controller_exists:
                raise ValueError("invalid territorial control")
            if control.stage == "active":
                garrison = next((item for item in self.garrisons.values()
                                 if item.settlement_id == settlement.id
                                 and item.stage == "active"
                                 and item.detachment_id in self.detachments
                                 and self.detachments[item.detachment_id].owner_ref.kind == control.controller_kind
                                 and self.detachments[item.detachment_id].owner_ref.id == control.controller_id), None)
                if (settlement.occupier_id != control.controller_id or garrison is None):
                    raise ValueError("active territorial control requires an active supporting garrison")
        active_campaign_investments = set()
        for key, campaign in self.siege_campaigns.items():
            attacker = self.detachments.get(campaign.attacker_detachment_id)
            garrison = self.garrisons.get(campaign.defender_garrison_id)
            investment = self.settlement_investments.get(campaign.investment_id)
            if (key != campaign.id or attacker is None or garrison is None or investment is None
                    or campaign.settlement_id not in self.settlements
                    or attacker.owner_ref != campaign.attacker_ref
                    or attacker.id == garrison.detachment_id):
                raise ValueError("invalid siege campaign")
            if campaign.phase == "sieging":
                defender = self.detachments.get(garrison.detachment_id)
                if (campaign.investment_id in active_campaign_investments
                        or investment.stage != "active" or investment.detachment_id != attacker.id
                        or investment.settlement_id != campaign.settlement_id
                        or attacker.stage != "present" or attacker.location_id != campaign.settlement_id
                        or attacker.provisions < attacker.count or garrison.stage != "active"
                        or defender is None or defender.stage != "present"
                        or defender.location_id != campaign.settlement_id
                        or defender.owner_ref == campaign.attacker_ref):
                    raise ValueError("active siege campaign requires current force, supply and garrison")
                active_campaign_investments.add(campaign.investment_id)
        commanded_characters = set()
        for detachment_id, command in self.detachment_commands.items():
            detachment = self.detachments.get(detachment_id)
            character = self.characters.get(command.character_id)
            if (detachment_id != command.id or command.detachment_id != detachment_id
                    or detachment is None or character is None or character.death_day is not None
                    or detachment.stage != "present" or character.location_id != detachment.location_id
                    or command.character_id in commanded_characters):
                raise ValueError("detachment command requires one living local person and present column")
            commanded_characters.add(command.character_id)
            if world is not None:
                office = world.authority.offices.get(command.office_id)
                day = world.clock.absolute_day
                if (office is None or office.institution_ref != command.institution_ref
                        or "military" not in office.scopes or office.starts_day > day
                        or (office.ends_day is not None and day >= office.ends_day)):
                    raise ValueError("detachment command lacks current military office")
        for site_id, denial in self.assembly_denials.items():
            detachment = self.detachments.get(denial.detachment_id)
            site = world.map.infrastructure_sites.get(site_id) if world is not None else None
            position = self.force_positions.get(f"force-position:{denial.detachment_id}")
            if (site_id != denial.id or detachment is None or denial.settlement_id not in self.settlements
                    or detachment.owner_ref != denial.actor_ref or detachment.stage != "present"
                    or detachment.location_id != denial.settlement_id or position is None
                    or position.stage != "prepared" or position.settlement_id != denial.settlement_id
                    or detachment.provisions < detachment.count):
                raise ValueError("assembly denial requires a supplied prepared local detachment")
            if world is not None and (site is None
                                      or self.settlements[denial.settlement_id].region_id not in site.region_ids):
                raise ValueError("assembly denial requires a local existing site")
        for key, protest in self.civic_protests.items():
            group = self.population.get(protest.group_id)
            settlement = self.settlements.get(protest.settlement_id)
            if (key != protest.id or group is None or settlement is None
                    or group.settlement_id != protest.settlement_id
                    or protest.participants > group.count
                    or (protest.demand_kind == "site_repair" and world is not None
                        and protest.site_id not in world.map.infrastructure_sites)):
                raise ValueError("invalid civic protest")
            if protest.stage == "open" and sum(item.stage == "open" and item.settlement_id == protest.settlement_id
                                                 for item in self.civic_protests.values()) != 1:
                raise ValueError("only one civic protest may be open in a settlement")
        for key, engagement in self.field_engagements.items():
            challenger = self.detachments.get(engagement.challenger_detachment_id)
            defender = self.detachments.get(engagement.defender_detachment_id)
            standoff = self.force_standoffs.get(engagement.standoff_id)
            if (key != engagement.id or challenger is None or defender is None or standoff is None
                    or challenger.owner_ref != engagement.challenger_ref
                    or defender.owner_ref != engagement.defender_ref
                    or set(standoff.detachment_ids) != {challenger.id, defender.id}
                    or engagement.settlement_id != standoff.settlement_id):
                raise ValueError("field engagement requires its real contact columns")
        active_interdictors = set()
        active_routes = set()
        for key, interdiction in self.route_interdictions.items():
            detachment = self.detachments.get(interdiction.detachment_id)
            if (key != interdiction.id or detachment is None or detachment.owner_ref != interdiction.actor_ref
                    or interdiction.settlement_id not in self.settlements):
                raise ValueError("invalid route interdiction")
            if interdiction.stage == "active":
                position = self.force_positions.get(f"force-position:{detachment.id}")
                if ((interdiction.investment_id is None and detachment.id in active_interdictors)
                        or interdiction.route_id in active_routes
                        or detachment.stage != "present" or detachment.location_id != interdiction.settlement_id
                        or position is None or position.stage != "prepared"):
                    raise ValueError("active route interdiction requires one prepared present column")
                if interdiction.investment_id is None:
                    active_interdictors.add(detachment.id)
                active_routes.add(interdiction.route_id)
                if world is not None:
                    route = world.map.routes.get(interdiction.route_id)
                    settlement = self.settlements[interdiction.settlement_id]
                    if (route is None or settlement.region_id not in route.endpoint_region_ids
                            or world.map.force_route_interdictors.get(route.id) != interdiction.id):
                        raise ValueError("active route interdiction lacks its map effect")
            elif world is not None and world.map.force_route_interdictors.get(interdiction.route_id) == interdiction.id:
                raise ValueError("lifted route interdiction still restricts the map")
        active_investment_settlements = set()
        for key, investment in self.settlement_investments.items():
            detachment = self.detachments.get(investment.detachment_id)
            settlement = self.settlements.get(investment.settlement_id)
            entries = tuple(self.route_interdictions.get(identity) for identity in investment.route_interdiction_ids)
            if (key != investment.id or detachment is None or settlement is None
                    or detachment.owner_ref != investment.actor_ref
                    or len(entries) != len(investment.route_ids)
                    or any(item is None or item.investment_id != investment.id
                           or item.route_id != route_id or item.detachment_id != detachment.id
                           for item, route_id in zip(entries, investment.route_ids))):
                raise ValueError("invalid settlement investment")
            if investment.stage == "active":
                if (investment.settlement_id in active_investment_settlements
                        or detachment.stage != "present" or detachment.location_id != investment.settlement_id
                        or detachment.provisions < detachment.count
                        or any(item.stage != "active" for item in entries)):
                    raise ValueError("active settlement investment requires its prepared supplied column")
                active_investment_settlements.add(investment.settlement_id)
                if world is not None:
                    exits = tuple(sorted(route.id for route in world.map.routes.values()
                                         if settlement.region_id in route.endpoint_region_ids))
                    position = self.force_positions.get(f"force-position:{detachment.id}")
                    if (position is None or position.stage != "prepared" or tuple(investment.route_ids) != exits
                            or len(exits) > max(1, detachment.count // 20)):
                        raise ValueError("active settlement investment lacks its complete eligible exits")
            elif any(item.stage != "lifted" for item in entries):
                raise ValueError("lifted settlement investment keeps an active route cause")
        for key, cohort in self.birth_cohorts.items():
            settlement = self.settlements.get(cohort.settlement_id)
            if key != cohort.id or settlement is None:
                raise ValueError("invalid birth cohort")
            if cohort.stage == "pending" and world is not None:
                scheduled = world.agenda.get(cohort.id)
                if (scheduled is None or scheduled.kind != "generation_maturity"
                        or scheduled.due_day != cohort.matures_day
                        or cohort.matures_day <= world.clock.absolute_day):
                    raise ValueError("a pending generation requires its future dated maturity")
            elif cohort.stage == "matured" and world is not None and world.agenda.get(cohort.id) is not None:
                raise ValueError("a matured generation cannot stay on the agenda")
        if any(self.available_count(group_id) < 0 for group_id in self.population):
            raise ValueError("temporary work exceeds its population cohort")
        if world is None:
            return
        from src.classes.event import FactKind
        from src.classes.mechanical_language import EntityRef

        events = {event.id: event for event in world.events}
        for garrison in self.garrisons.values():
            decision = events.get(garrison.decision_event_id)
            first = next((event for event in events.values()
                          if event.event_type in {"garrison_established", "garrison_rotated"}
                          and any(delta.owner_kind == "garrison" and delta.owner_id == garrison.id
                                  and delta.aspect == "stage" and delta.before == "None"
                                  and delta.after == "active" for delta in event.deltas)), None)
            final = events.get(garrison.last_event_id)
            if (first is None or decision is None or decision.fact_kind != FactKind.DECISION
                    or decision.decision is None
                    or decision.decision.get("action") not in {"establish_garrison", "rotate_garrison"}
                    or decision.id not in {link.cause_event_id for link in first.causal_links}
                    or first.day != garrison.started_day):
                raise ValueError("garrison lacks its factual decision")
            if garrison.stage == "active":
                if final is None or final.event_type not in {"garrison_established", "garrison_maintained", "garrison_rotated"}:
                    raise ValueError("active garrison lacks its latest maintenance fact")
            elif garrison.stage == "lapsed":
                if (final is None or final.event_type != "garrison_lapsed"
                        or not any(delta.owner_kind == "garrison" and delta.owner_id == garrison.id
                                   and delta.aspect == "stage" and delta.before == "active"
                                   and delta.after == "lapsed" for delta in final.deltas)):
                    raise ValueError("lapsed garrison lacks its lapse fact")
            elif garrison.stage == "withdrawn":
                if (final is None or final.event_type not in {"garrison_withdrawn", "garrison_rotated"}
                        or not any(delta.owner_kind == "garrison" and delta.owner_id == garrison.id
                                   and delta.aspect == "stage" and delta.before == "active"
                                   and delta.after == "withdrawn" for delta in final.deltas)):
                    raise ValueError("withdrawn garrison lacks its withdrawal fact")
            elif (final is None or final.event_type != "garrison_collapsed"
                  or not any(delta.owner_kind == "garrison" and delta.owner_id == garrison.id
                             and delta.aspect == "stage" and delta.before == "active"
                             and delta.after == "collapsed" for delta in final.deltas)):
                raise ValueError("collapsed garrison lacks its collapse fact")
        for control in self.territorial_controls.values():
            decision = events.get(control.decision_event_id)
            started = next((event for event in events.values()
                            if event.event_type == "territorial_control_established"
                            and any(delta.owner_kind == "territorial_control" and delta.owner_id == control.id
                                    and delta.aspect == "stage" and delta.before == "None"
                                    and delta.after == "active" for delta in event.deltas)), None)
            final = events.get(control.last_event_id)
            if (decision is None or started is None or final is None
                    or decision.fact_kind != FactKind.DECISION or decision.decision is None
                    or decision.decision.get("action") != "establish_territorial_control"
                    or decision.decision.get("actor_ref") != {"kind": control.controller_kind,
                                                              "id": control.controller_id}
                    or control.decision_event_id not in {link.cause_event_id for link in started.causal_links}
                    or started.day != control.started_day):
                raise ValueError("territorial control lacks its factual decision")
            if control.stage == "active":
                if final.event_type != "territorial_control_established":
                    raise ValueError("active territorial control lacks its establishment fact")
            elif (final.event_type not in {"territorial_control_lapsed", "territorial_control_withdrawn"}
                  or not any(delta.owner_kind == "territorial_control" and delta.owner_id == control.id
                             and delta.aspect == "stage" and delta.before == "active"
                             and delta.after == control.stage for delta in final.deltas)):
                raise ValueError("ended territorial control lacks its closing fact")
        for campaign in self.siege_campaigns.values():
            decision = events.get(campaign.decision_event_id)
            campaign_garrison = self.garrisons.get(campaign.defender_garrison_id)
            started = next((event for event in events.values()
                            if event.event_type == "siege_campaign_started"
                            and any(delta.owner_kind == "siege_campaign" and delta.owner_id == campaign.id
                                    and delta.aspect == "phase" and delta.before == "None"
                                    and delta.after == "sieging" for delta in event.deltas)), None)
            final = events.get(campaign.last_event_id)
            scheduled = world.agenda.get(campaign.id)
            if (decision is None or started is None or final is None or decision.fact_kind != FactKind.DECISION
                    or decision.decision is None or decision.decision.get("action") != "begin_siege_campaign"
                    or decision.decision.get("actor_ref") != campaign.attacker_ref.to_dict()
                    or not str(decision.decision.get("selected_affordance_id", "")).startswith("siege-campaign:")
                    or campaign.decision_event_id not in {link.cause_event_id for link in started.causal_links}
                    or started.day != campaign.started_day
                    or not any(delta.owner_kind == "siege_campaign" and delta.owner_id == campaign.id
                               and delta.aspect == "garrison_endurance" and delta.before == "None"
                               and delta.after in {str(SIEGE_GARRISON_ENDURANCE),
                                                   str(MAX_SIEGE_GARRISON_ENDURANCE)}
                               for delta in started.deltas)):
                raise ValueError("siege campaign lacks its factual decision")
            if campaign.phase == "sieging":
                if (final.event_type not in {"siege_campaign_started", "siege_campaign_progressed"}
                        or scheduled is None or scheduled.kind != "siege_campaign"
                        or scheduled.due_day != campaign.next_progress_day
                        or campaign.next_progress_day <= world.clock.absolute_day):
                    raise ValueError("active siege campaign lacks its next material check")
                if not any(delta.owner_kind == "siege_campaign" and delta.owner_id == campaign.id
                           and delta.aspect == "garrison_endurance"
                           and delta.after == str(campaign.garrison_endurance) for delta in final.deltas):
                    raise ValueError("active siege campaign lacks its endurance receipt")
            elif (scheduled is not None or final.event_type != f"siege_campaign_{campaign.phase}"
                  or not any(delta.owner_kind == "siege_campaign" and delta.owner_id == campaign.id
                             and delta.aspect == "phase" and delta.before in {"sieging", "breached"}
                             and delta.after == campaign.phase for delta in final.deltas)):
                raise ValueError("finished siege campaign lacks its final fact")
            elif campaign.phase == "breached" and not any(
                    delta.owner_kind == "siege_campaign" and delta.owner_id == campaign.id
                    and delta.aspect == "garrison_endurance" and delta.after == "0" for delta in final.deltas):
                raise ValueError("breached siege campaign lacks its endurance receipt")
            elif campaign.phase == "breached":
                collapse = events.get(campaign_garrison.last_event_id) if campaign_garrison is not None else None
                if (campaign_garrison is None or campaign_garrison.stage != "collapsed" or collapse is None
                        or collapse.event_type != "garrison_collapsed"
                        or campaign.last_event_id not in {link.cause_event_id for link in collapse.causal_links}):
                    raise ValueError("breached siege campaign lacks its garrison collapse")
        for denial in self.assembly_denials.values():
            decision = events.get(denial.decision_event_id)
            event = events.get(denial.last_event_id)
            if (decision is None or event is None or decision.fact_kind != FactKind.DECISION
                    or decision.decision is None or set(decision.decision) != {"action", "actor_ref", "selected_affordance_id"}
                    or decision.decision.get("action") != "deny_rite_assembly"
                    or decision.decision.get("actor_ref") != denial.actor_ref.to_dict()
                    or not str(decision.decision.get("selected_affordance_id", "")).startswith(
                        f"rite-assembly-deny:{denial.detachment_id}:{denial.id}:")
                    or event.event_type != "assembly_denied"
                    or denial.decision_event_id not in {link.cause_event_id for link in event.causal_links}
                    or not any(events.get(link.cause_event_id) is not None
                               and events[link.cause_event_id].event_type == "rite_observed"
                               for link in event.causal_links)
                    or not any(delta.owner_kind == "assembly_denial" and delta.owner_id == denial.id
                               and delta.aspect == "detachment_id" and delta.before == "None"
                               and delta.after == denial.detachment_id for delta in event.deltas)):
                raise ValueError("assembly denial lacks its factual decision")
        for interdiction in self.route_interdictions.values():
            decision = events.get(interdiction.decision_event_id)
            started = next((event for event in events.values()
                            if event.event_type == ("settlement_invested" if interdiction.investment_id else "route_interdicted")
                            and any(delta.owner_kind == "route_interdiction" and delta.owner_id == interdiction.id
                                    and delta.aspect == "stage" and delta.before == "None" and delta.after == "active"
                                    for delta in event.deltas)), None)
            expected_action = "settlement_invest" if interdiction.investment_id else "interdict_route"
            if (decision is None or started is None or decision.fact_kind != FactKind.DECISION
                    or decision.decision is None or decision.decision.get("action") != expected_action
                    or decision.decision.get("actor_ref") != interdiction.actor_ref.to_dict()
                    or decision.id not in {link.cause_event_id for link in started.causal_links}):
                raise ValueError("route interdiction lacks its factual decision")
            final = events.get(interdiction.last_event_id)
            if interdiction.stage == "active":
                if final is None or final.id != started.id:
                    raise ValueError("active route interdiction lacks its start fact")
            elif (final is None or final.event_type != ("settlement_investment_lifted" if interdiction.investment_id else "route_interdiction_lifted")
                  or not any(delta.owner_kind == "route_interdiction" and delta.owner_id == interdiction.id
                             and delta.aspect == "stage" and delta.before == "active" and delta.after == "lifted"
                             for delta in final.deltas)):
                raise ValueError("lifted route interdiction lacks its factual revocation")
        for investment in self.settlement_investments.values():
            decision = events.get(investment.decision_event_id)
            started = events.get(investment.last_event_id) if investment.stage == "active" else next(
                (event for event in events.values() if event.event_type == "settlement_invested"
                 and any(delta.owner_kind == "settlement_investment" and delta.owner_id == investment.id
                         and delta.aspect == "stage" and delta.before == "None" and delta.after == "active"
                         for delta in event.deltas)), None)
            if (decision is None or started is None or decision.fact_kind != FactKind.DECISION
                    or decision.decision is None or decision.decision.get("action") != "settlement_invest"
                    or decision.decision.get("actor_ref") != investment.actor_ref.to_dict()
                    or decision.id not in {link.cause_event_id for link in started.causal_links}):
                raise ValueError("settlement investment lacks its factual decision")
            final = events.get(investment.last_event_id)
            if investment.stage == "active":
                if final is None or final.event_type != "settlement_invested":
                    raise ValueError("active settlement investment lacks its start fact")
            elif (final is None or final.event_type != "settlement_investment_lifted"
                  or not any(delta.owner_kind == "settlement_investment" and delta.owner_id == investment.id
                             and delta.aspect == "stage" and delta.before == "active" and delta.after == "lifted"
                             for delta in final.deltas)):
                raise ValueError("lifted settlement investment lacks its factual revocation")
        for command in self.detachment_commands.values():
            event = events.get(command.last_event_id)
            decisions = [events.get(link.cause_event_id) for link in event.causal_links] if event else []
            expected = "set_detachment_doctrine" if event is not None and event.event_type == "detachment_doctrine_set" \
                else "appoint_detachment_commander"
            if (event is None or event.event_type not in {"detachment_commander_appointed", "detachment_doctrine_set"}
                    or not any(item is not None and item.fact_kind == FactKind.DECISION and item.decision
                               and item.decision.get("action") == expected
                               and item.decision.get("actor_ref") == command.institution_ref.to_dict()
                               for item in decisions)):
                raise ValueError("detachment command lacks its factual decision")
        for engagement in self.field_engagements.values():
            offer = events.get(engagement.offer_event_id)
            final = events.get(engagement.last_event_id)
            decision = events.get(engagement.decision_event_id)
            if (offer is None or offer.event_type != "field_engagement_offered"
                    or offer.day != engagement.offered_day
                    or decision is None or decision.fact_kind != FactKind.DECISION
                    or decision.decision is None or decision.decision.get("action") != "offer_field_engagement"
                    or decision.decision.get("actor_ref") != engagement.challenger_ref.to_dict()
                    or not str(decision.decision.get("selected_affordance_id", "")).startswith(
                        "field-engagement-offer:")
                    or engagement.decision_event_id not in {link.cause_event_id for link in offer.causal_links}
                    or not any(delta.owner_kind == "field_engagement" and delta.owner_id == engagement.id
                               and delta.aspect == "status" and delta.before == "None" and delta.after == "offered"
                               for delta in offer.deltas)):
                raise ValueError("field engagement lacks its factual offer")
            scheduled = world.agenda.get(engagement.id)
            if engagement.status == "offered":
                if (scheduled is None or scheduled.kind != "field_engagement"
                        or scheduled.due_day != engagement.expires_day):
                    raise ValueError("open field engagement lacks its expiry")
            elif engagement.status == "lapsed":
                if (final is None or final.event_type != "field_engagement_lapsed" or scheduled is not None
                        or not any(delta.owner_kind == "field_engagement" and delta.owner_id == engagement.id
                                   and delta.aspect == "status" and delta.before == "offered" and delta.after == "lapsed"
                                   for delta in final.deltas)):
                    raise ValueError("lapsed field engagement lacks its factual expiry")
            elif engagement.status == "resolved":
                joins = [events.get(link.cause_event_id) for link in final.causal_links] if final is not None else []
                if (final is None or final.event_type != "field_engagement_resolved" or scheduled is not None
                        or not any(item is not None and item.fact_kind == FactKind.DECISION and item.decision
                                   and item.decision.get("action") == "join_field_engagement"
                                   and item.decision.get("actor_ref") == engagement.defender_ref.to_dict()
                                   and str(item.decision.get("selected_affordance_id", "")).startswith(
                                       f"field-engagement-join:{engagement.id}:")
                                   for item in joins)
                        or not any(delta.owner_kind == "field_engagement" and delta.owner_id == engagement.id
                                   and delta.aspect == "status" and delta.before == "offered" and delta.after == "resolved"
                                   for delta in final.deltas)):
                    raise ValueError("resolved field engagement lacks its factual outcome")
        for position in self.force_positions.values():
            detachment = self.detachments[position.detachment_id]
            starts = [event for event in events.values()
                      if event.event_type == "force_position_preparing"
                      and any(delta.owner_kind == "force_position" and delta.owner_id == position.id
                              and delta.aspect == "stage" and delta.before == "None" and delta.after == "preparing"
                              for delta in event.deltas)]
            if len(starts) != 1:
                raise ValueError("force position lacks its preparation fact")
            start = starts[0]
            decisions = [events.get(link.cause_event_id) for link in start.causal_links]
            if (start.day != position.started_day
                    or not any(event is not None and event.fact_kind == FactKind.DECISION
                               and event.decision and event.decision.get("action") == "prepare_force_position"
                               and event.decision.get("actor_ref") == detachment.owner_ref.to_dict()
                               and str(event.decision.get("selected_affordance_id", "")).startswith(
                                   f"force-position:{position.detachment_id}:")
                               for event in decisions)):
                raise ValueError("force position lacks its current military decision")
            scheduled = world.agenda.get(position.id)
            final = events.get(position.last_event_id)
            if position.stage == "preparing":
                if (position.last_event_id != start.id or position.ready_day <= world.clock.absolute_day
                        or scheduled is None or scheduled.kind != "force_preparation"
                        or scheduled.due_day != position.ready_day):
                    raise ValueError("pending force position lacks its dated preparation")
            elif (final is None or final.event_type != "force_position_prepared"
                  or position.ready_day > world.clock.absolute_day or scheduled is not None
                  or not any(delta.owner_kind == "force_position" and delta.owner_id == position.id
                             and delta.aspect == "stage" and delta.before == "preparing" and delta.after == "prepared"
                             for delta in final.deltas)
                  or start.id not in {link.cause_event_id for link in final.causal_links}):
                raise ValueError("prepared force position lacks its completion fact")
        for standoff in self.force_standoffs.values():
            started = events.get(standoff.started_event_id)
            final = events.get(standoff.last_event_id)
            if (started is None or final is None or started.event_type != "armed_standoff_started"
                    or started.day != standoff.started_day
                    or not any(delta.owner_kind == "force_standoff" and delta.owner_id == standoff.id
                               and delta.aspect == "stage" and delta.before == "None" and delta.after == "active"
                               for delta in started.deltas)):
                raise ValueError("force standoff lacks its factual creation receipt")
            if standoff.stage == "resolved" and (
                    standoff.resolved_day != final.day or final.event_type != "armed_standoff_resolved"
                    or not any(delta.owner_kind == "force_standoff" and delta.owner_id == standoff.id
                               and delta.aspect == "stage" and delta.before == "active" and delta.after == "resolved"
                               for delta in final.deltas)):
                raise ValueError("force standoff lacks its factual resolution receipt")
        for protest in self.civic_protests.values():
            decision = events.get(protest.decision_event_id)
            report = events.get(protest.report_event_id)
            opened = next((item for item in events.values()
                           if item.event_type == "civic_protest_opened"
                           and any(delta.owner_kind == "civic_protest" and delta.owner_id == protest.id
                                   and delta.aspect == "stage" and delta.before == "None" and delta.after == "open"
                                   for delta in item.deltas)), None)
            report_id = f"settlement_report:population_group:{protest.group_id}:{protest.settlement_id}"
            if (decision is None or report is None or opened is None or decision.fact_kind != FactKind.DECISION
                    or decision.day != protest.started_day or decision.decision is None
                    or decision.decision.get("action") != "open_civic_protest"
                    or decision.decision.get("actor_ref") != EntityRef("population_group", protest.group_id).to_dict()
                    or not str(decision.decision.get("selected_affordance_id", "")).startswith(
                        f"civic-protest-open:{protest.group_id}:{protest.report_event_id}:{protest.demand_kind}:")
                    or protest.decision_event_id not in {link.cause_event_id for link in opened.causal_links}
                    or protest.report_event_id not in {link.cause_event_id for link in opened.causal_links}
                    or report.event_type not in {"settlement_observed", "settlement_report_received"}
                    or not any(delta.owner_kind == "settlement_report" and delta.owner_id == report_id
                               and delta.aspect == "observation" for delta in report.deltas)
                    or not any(delta.owner_kind == "civic_protest" and delta.owner_id == protest.id
                               and delta.aspect == "workforce_reservation" and delta.before == "0"
                               and delta.after == str(protest.participants) for delta in opened.deltas)):
                raise ValueError("civic protest lacks its factual opening")
            scheduled = world.agenda.get(protest.id)
            final = events.get(protest.last_event_id)
            if protest.stage == "open":
                if scheduled is None or scheduled.kind != "civic_protest" or scheduled.due_day != protest.due_day:
                    raise ValueError("open civic protest lacks its dated resolution")
            elif (scheduled is not None or final is None or final.event_type != f"civic_protest_{protest.stage}"
                  or not any(delta.owner_kind == "civic_protest" and delta.owner_id == protest.id
                             and delta.aspect == "stage" and delta.before == "open" and delta.after == protest.stage
                             for delta in final.deltas)
                  or not any(delta.owner_kind == "civic_protest" and delta.owner_id == protest.id
                             and delta.aspect == "workforce_reservation" and delta.before == str(protest.participants)
                             and delta.after == "0" for delta in final.deltas)):
                raise ValueError("closed civic protest lacks its release receipt")
        active_movement_groups = set()
        active_movement_settlements = set()
        for movement in self.civic_movements.values():
            groups = [self.population.get(group_id) for group_id in movement.member_group_ids]
            leader = self.characters.get(movement.leader_character_id)
            decision = events.get(movement.decision_event_id)
            final = events.get(movement.last_event_id)
            if (movement.id not in self.civic_movements
                    or any(group is None for group in groups)
                    or any(group.settlement_id != movement.settlement_id for group in groups)
                    or any(movement.participants_by_group[group.id] > group.count for group in groups)
                    or leader is None or leader.death_day is not None
                    or leader.population_group_id not in movement.member_group_ids
                    or leader.location_id != movement.settlement_id
                    or decision is None or decision.fact_kind != FactKind.DECISION
                    or decision.decision is None
                    or decision.decision.get("action") != "form_civic_movement"
                    or decision.decision.get("actor_ref") != EntityRef("population_group", movement.initiator_group_id).to_dict()
                    or not str(decision.decision.get("selected_affordance_id", "")).startswith(
                        f"civic-movement:{movement.initiator_group_id}:{movement.settlement_id}:")
                    or final is None
                    or (movement.stage == "active" and (final.event_type != "civic_movement_formed"
                        or not any(delta.owner_kind == "civic_movement" and delta.owner_id == movement.id
                                   and delta.aspect == "stage" and delta.before == "None" and delta.after == "active"
                                   for delta in final.deltas)))
                    or (movement.stage == "rebellion" and (final.event_type != "civic_rebellion_declared"
                        or not any(delta.owner_kind == "civic_movement" and delta.owner_id == movement.id
                                   and delta.aspect == "stage" and delta.before == "active" and delta.after == "rebellion"
                                   for delta in final.deltas)))
                    or (movement.stage == "revolution" and (final.event_type != "civic_revolution_declared"
                        or not any(delta.owner_kind == "civic_movement" and delta.owner_id == movement.id
                                   and delta.aspect == "stage" and delta.before == "rebellion" and delta.after == "revolution"
                                   for delta in final.deltas)))
                    or (movement.stage == "negotiating" and (final.event_type != "civic_negotiation_offered"
                        or not any(delta.owner_kind == "civic_movement" and delta.owner_id == movement.id
                                   and delta.aspect == "stage" and delta.before in {"active", "rebellion", "revolution"}
                                   and delta.after == "negotiating"
                                   for delta in final.deltas)))
                    or (movement.stage not in {"active", "rebellion", "revolution", "negotiating"} and (final.event_type != f"civic_movement_{movement.stage}"
                        or not any(delta.owner_kind == "civic_movement" and delta.owner_id == movement.id
                                   and delta.aspect == "stage" and delta.before in {"active", "rebellion", "revolution", "negotiating"}
                                   and delta.after == movement.stage
                                   for delta in final.deltas)
                        or any(not any(delta.owner_kind == "civic_movement" and delta.owner_id == movement.id
                                       and delta.aspect == f"participants:{group.id}"
                                       and delta.before == str(movement.participants_by_group[group.id])
                                       and delta.after == "0" for delta in final.deltas)
                            for group in groups)))
                    or any(group.id in active_movement_groups for group in groups
                           if movement.stage in {"active", "rebellion", "revolution", "negotiating"})
                    or (movement.stage in {"active", "rebellion", "revolution", "negotiating"}
                        and movement.settlement_id in active_movement_settlements)):
                raise ValueError("invalid civic movement")
            if movement.stage in {"active", "rebellion", "revolution", "negotiating"}:
                active_movement_groups.update(group.id for group in groups)
                active_movement_settlements.add(movement.settlement_id)
        active_strike_groups = set()
        active_strike_movements = set()
        for strike in self.civic_strikes.values():
            movement = self.civic_movements.get(strike.movement_id)
            groups = [self.population.get(group_id) for group_id in strike.participants_by_group]
            decision = events.get(strike.decision_event_id)
            final = events.get(strike.last_event_id)
            scheduled = world.agenda.get(strike.id) if world is not None else None
            actor_group_id = None
            if decision is not None and decision.decision is not None:
                actor = decision.decision.get("actor_ref")
                if isinstance(actor, dict) and actor.get("kind") == "population_group":
                    actor_group_id = actor.get("id")
            leader = (self.characters.get(movement.leader_character_id)
                      if movement is not None else None)
            if (movement is None or any(group is None for group in groups)
                    or any(group.settlement_id != strike.settlement_id for group in groups)
                    or movement.settlement_id != strike.settlement_id
                    or strike.due_day <= strike.started_day
                    or decision is None or decision.fact_kind != FactKind.DECISION
                    or decision.decision is None or decision.decision.get("action") != "start_general_strike"
                    or actor_group_id != (leader.population_group_id if leader is not None else None)
                    or final is None
                    or (strike.stage == "active" and (movement.stage != "active"
                        or final.event_type != "civic_general_strike_started"
                        or scheduled is None or scheduled.kind != "civic_general_strike"
                        or scheduled.due_day != strike.due_day
                        or not any(delta.owner_kind == "civic_strike" and delta.owner_id == strike.id
                                   and delta.aspect == "stage" and delta.before == "None"
                                   and delta.after == "active" for delta in final.deltas)))
                    or (strike.stage != "active" and (final.event_type != "civic_general_strike_ended"
                        or scheduled is not None
                        or not any(delta.owner_kind == "civic_strike" and delta.owner_id == strike.id
                                   and delta.aspect == "stage" and delta.before == "active"
                                   and delta.after == strike.stage for delta in final.deltas)
                        or any(not any(delta.owner_kind == "civic_strike" and delta.owner_id == strike.id
                                       and delta.aspect == f"participants:{group.id}"
                                       and delta.before == str(strike.participants_by_group[group.id])
                                       and delta.after == "0" for delta in final.deltas)
                            for group in groups)))
                    or any(group.id in active_strike_groups for group in groups if strike.stage == "active")
                    or (strike.stage == "active" and strike.movement_id in active_strike_movements)):
                raise ValueError("invalid civic strike")
            for group in groups:
                # available_count includes this strike.  Add its reservation
                # back to calculate the capacity available to all other work.
                capacity = self.available_count(group.id) + strike.participants_by_group[group.id]
                if strike.participants_by_group[group.id] > capacity:
                    raise ValueError("civic strike exceeds available cohort")
            if strike.stage == "active":
                active_strike_groups.update(strike.participants_by_group)
                active_strike_movements.add(strike.movement_id)
        for amnesty in self.civic_amnesties.values():
            movement = self.civic_movements.get(amnesty.movement_id)
            settlement = self.settlements.get(amnesty.settlement_id)
            decision = events.get(amnesty.decision_event_id)
            final = events.get(amnesty.last_event_id)
            if (movement is None or settlement is None
                    or movement.settlement_id != amnesty.settlement_id
                    or movement.stage != "dissolved"
                    or settlement.administrator_id != amnesty.administrator_ref.id
                    or amnesty.administrator_ref.kind != "polity"
                    or amnesty.administrator_ref.id not in self.polities
                    or decision is None or decision.fact_kind != FactKind.DECISION
                    or decision.decision is None
                    or decision.decision.get("action") != "grant_civic_amnesty"
                    or decision.decision.get("actor_ref") != amnesty.administrator_ref.to_dict()
                    or not str(decision.decision.get("selected_affordance_id", "")).startswith(
                        f"civic-amnesty:{movement.id}:{movement.last_event_id}:")
                    or final is None or final.event_type != "civic_amnesty_granted"
                    or amnesty.decision_event_id not in {link.cause_event_id for link in final.causal_links}
                    or movement.last_event_id not in {link.cause_event_id for link in final.causal_links}
                    or not any(delta.owner_kind == "civic_amnesty" and delta.owner_id == amnesty.id
                               and delta.aspect == "stage" and delta.before == "None"
                               and delta.after == "granted" for delta in final.deltas)):
                raise ValueError("invalid civic amnesty provenance")
            if any(other.id != amnesty.id and other.movement_id == amnesty.movement_id
                   for other in self.civic_amnesties.values()):
                raise ValueError("duplicate civic amnesty for movement")
        for cohort in self.birth_cohorts.values():
            birth = events.get(cohort.birth_event_id)
            final = events.get(cohort.last_event_id)
            if (birth is None or birth.event_type != "settlement_births" or birth.day != cohort.born_day
                    or not any(delta.owner_kind == "birth_cohort" and delta.owner_id == cohort.id
                               and delta.aspect == "count" and delta.after == str(cohort.count)
                               for delta in birth.deltas)):
                raise ValueError("birth cohort lacks its factual receipt")
            if cohort.stage == "matured" and (
                    final is None or final.event_type != "generation_matured"
                    or cohort.birth_event_id not in {link.cause_event_id for link in final.causal_links}
                    or not any(delta.owner_kind == "birth_cohort" and delta.owner_id == cohort.id
                               and delta.aspect == "stage" and delta.before == "pending"
                               and delta.after == "matured" for delta in final.deltas)):
                raise ValueError("matured generation lacks its factual maturity")
        for transition in self.workforce_transitions.values():
            decision = events.get(transition.decision_event_id)
            started = events.get(transition.last_event_id)
            notice = world.knowledge.workforce_offer_notices.get(transition.notice_id)
            report = world.knowledge.workforce_demand_reports.get(transition.demand_id)
            scheduled = world.agenda.get(transition.id)
            expected_actor = EntityRef("population_group", transition.source_group_id).to_dict()
            expected_option_prefix = f"workforce_transition:{transition.source_group_id}:{transition.notice_id}:"
            if (decision is None or started is None or notice is None or report is None
                    or decision.fact_kind != FactKind.DECISION or decision.day != transition.started_day
                    or decision.decision is None or decision.decision.get("action") != "accept_workforce_offer"
                    or decision.decision.get("actor_ref") != expected_actor
                    or not isinstance(decision.decision.get("selected_affordance_id"), str)
                    or not decision.decision["selected_affordance_id"].startswith(expected_option_prefix)
                    or started.event_type != "workforce_transition_started" or started.day != transition.started_day
                    or transition.decision_event_id not in {link.cause_event_id for link in started.causal_links}
                    or notice.event_id not in {link.cause_event_id for link in started.causal_links}
                    or report.event_id not in {link.cause_event_id for link in started.causal_links}
                    or notice.source_group_id != transition.source_group_id
                    or notice.sponsor_ref != transition.sponsor_ref or notice.demand_id != transition.demand_id
                    or notice.count != transition.count or notice.stipend_per_person != transition.stipend_per_person
                    or report.sponsor_ref != transition.sponsor_ref
                    or report.work_kind != transition.work_kind or report.work_id != transition.work_id
                    or report.target_occupation != transition.target_occupation
                    or notice.target_occupation != transition.target_occupation
                    or scheduled is None or scheduled.kind != "workforce_transition"
                    or scheduled.due_day != transition.due_day or transition.due_day <= world.clock.absolute_day):
                raise ValueError("invalid workforce transition provenance")
            sponsor = world.economy.accounts.get(report.account_id)
            household = world.economy.accounts.get(f"household:{transition.source_group_id}")
            stipend = transition.count * transition.stipend_per_person
            account_deltas = {(delta.owner_id, int(delta.after) - int(delta.before)) for delta in started.deltas
                              if delta.owner_kind == "account" and delta.aspect == "balance"}
            if (sponsor is None or household is None
                    or account_deltas != {(sponsor.id, -stipend), (household.id, stipend)}
                    or not any(delta.owner_kind == "workforce_transition" and delta.owner_id == transition.id
                               and delta.aspect == "stage" and delta.before == "None" and delta.after == "training"
                               for delta in started.deltas)):
                raise ValueError("invalid workforce transition material receipt")
            if transition.work_kind == "customs":
                checkpoint = world.economy.customs_checkpoints.get(transition.work_id)
                if checkpoint is None:
                    raise ValueError("customs workforce transition lost its checkpoint")
        if any(item["kind"] == "workforce_transition" and item["id"] not in self.workforce_transitions
               for item in world.agenda.to_dict()):
            raise ValueError("workforce agenda references missing transition")

    def _select_people(self, group_id: str, count: int, character_ids: tuple[str, ...]):
        if type(count) is not int or count <= 0:
            raise ValueError("count must be a positive integer")
        group = self.population[group_id]
        if len(set(character_ids)) != len(character_ids) or len(character_ids) > count:
            raise ValueError("invalid named selection")
        selected = []
        for character_id in character_ids:
            character = self.characters.get(character_id)
            if character is None or character.death_day is not None or character.population_group_id != group_id:
                raise ValueError("selected character is not in this population")
            selected.append(character)
        named_count = sum(c.population_group_id == group_id for c in self.characters.values())
        if count > group.count or count - len(selected) > group.count - named_count:
            raise ValueError("insufficient anonymous population; select named members explicitly")
        return group, selected

    def transfer_people(
        self, group_id: str, destination_id: str, occupation: Occupation,
        count: int, character_ids: tuple[str, ...] = (),
    ) -> str:
        """Migrate or reassign workers; recruitment is reassignment to soldier.

        All checks precede mutation. Named residents are part of the transfer,
        never an addition to its count. Temporary travel has its own owner and
        must not call this operation until residence actually changes.
        """
        group, selected = self._select_people(group_id, count, character_ids)
        if destination_id not in self.settlements:
            raise ValueError("unknown destination settlement")
        if (group.settlement_id, group.occupation) == (destination_id, occupation):
            raise ValueError("transfer must change residence or occupation")
        target = next((g for g in self.population.values() if
            (g.settlement_id, g.people, g.occupation) == (destination_id, group.people, occupation)), None)
        target_id = target.id if target else f"pop:{destination_id}:{group.people}:{occupation}"
        if target is None and target_id in self.population:
            raise ValueError("population ID collision")
        updated_target = PopulationGroup(
            id=target_id, settlement_id=destination_id, people=group.people,
            occupation=occupation, count=(target.count if target else 0) + count,
        )
        updated_source = group.model_copy(update={"count": group.count - count})
        characters = {
            c.id: c.model_copy(update={"population_group_id": target_id, "location_id": destination_id})
            for c in selected
        }
        self.population.update({group.id: updated_source, target_id: updated_target})
        self.characters.update(characters)
        return target_id

    def add_people(self, settlement_id: str, people: str, occupation: Occupation, count: int) -> str:
        """Register new anonymous residents in their own cohort.

        Nobody is named, no family is recorded and no other cohort is touched.
        The caller owns the receipt and writes the provenance afterwards.
        """
        if type(count) is not int or count <= 0:
            raise ValueError("count must be a positive integer")
        if settlement_id not in self.settlements:
            raise ValueError("unknown destination settlement")
        target = next((g for g in self.population.values()
                       if (g.settlement_id, g.people, g.occupation) == (settlement_id, people, occupation)), None)
        target_id = target.id if target else f"pop:{settlement_id}:{people}:{occupation}"
        if target is None and target_id in self.population:
            raise ValueError("population ID collision")
        self.population[target_id] = PopulationGroup(
            id=target_id, settlement_id=settlement_id, people=people,
            occupation=occupation, count=(target.count if target else 0) + count,
        )
        return target_id

    def remove_people(
        self, group_id: str, count: int, *, day: int, character_ids: tuple[str, ...] = (),
    ) -> None:
        """Record actual deaths, preserving named histories outside living cohorts."""
        if type(day) is not int or day < 0:
            raise ValueError("day must be a non-negative integer")
        group, selected = self._select_people(group_id, count, character_ids)
        if any(c.birth_day > day for c in selected):
            raise ValueError("death precedes birth")
        self.population[group.id] = group.model_copy(update={"count": group.count - count})
        for character in selected:
            self.characters[character.id] = character.model_copy(update={
                "death_day": day, "population_group_id": None,
            })

    def set_occupation(self, settlement_id: str, polity_id: str | None) -> None:
        """Physical occupation alone neither grants administration nor erases claims."""
        if polity_id is not None and polity_id not in self.polities:
            raise ValueError("unknown occupying polity")
        settlement = self.settlements[settlement_id]
        self.settlements[settlement_id] = settlement.model_copy(update={"occupier_id": polity_id})

"""Bilateral conveyance of one already commissioned productive site.

This vertical deliberately treats a workshop as a physical Map identity, not
as a tradeable property record.  A seller decision is an offer encoded in the
event history; a recipient may then accept that exact offer.  The executor
recomposes the current option and revalidates every owner before changing the
Map and the facility binding.  Stocks, balances and projects never move as a
side effect of the conveyance.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.serialization import validate_actor
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity, SocietyValue

from .economy import _causes, _delta
from .events import WorldEvent, record_event


WORKSHOP_KIND = "workshop"
SELLER_ACTION = "propose_productive_site_conveyance"
ACCEPT_ACTION = "accept_productive_site_conveyance"


def _event(world, event_id: str | None) -> WorldEvent | None:
    return next((item for item in world.events if item.id == event_id), None)


def _ref_payload(ref: EntityRef) -> str:
    return json.dumps(ref.to_dict(), sort_keys=True)


def _canonical_id(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return "conveyance-" + hashlib.sha256(encoded).hexdigest()[:32]


class ProductiveSiteConveyanceOption(SocietyValue):
    """Transient seller option; its ID is recomputed from canonical facts."""

    id: Identity
    site_id: Identity
    facility_id: Identity
    seller_ref: EntityRef
    buyer_ref: EntityRef
    stock_id: Identity
    payroll_account_id: Identity
    site_last_event_id: Identity | None = None
    facility_last_event_id: Identity | None = None

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "facility_id": self.facility_id,
            "seller_ref": self.seller_ref.to_dict(),
            "buyer_ref": self.buyer_ref.to_dict(),
            "stock_id": self.stock_id,
            "payroll_account_id": self.payroll_account_id,
            "site_last_event_id": self.site_last_event_id,
            "facility_last_event_id": self.facility_last_event_id,
        }

    def model_post_init(self, __context: Any) -> None:
        expected = _canonical_id(self.canonical_payload())
        if self.id != expected:
            raise ValueError("productive site conveyance option ID is not canonical")

    def decision(self) -> dict[str, Any]:
        return {
            "action": SELLER_ACTION,
            "actor_ref": self.seller_ref.to_dict(),
            "selected_affordance_id": self.id,
        }


class ProductiveSiteConveyanceAcceptanceOption(SocietyValue):
    """Transient recipient option reconstructed from a seller decision."""

    id: Identity
    proposal_event_id: Identity
    option_id: Identity
    site_id: Identity
    facility_id: Identity
    seller_ref: EntityRef
    buyer_ref: EntityRef
    stock_id: Identity
    payroll_account_id: Identity

    def decision(self) -> dict[str, Any]:
        return {
            "action": ACCEPT_ACTION,
            "actor_ref": self.buyer_ref.to_dict(),
            "selected_affordance_id": self.id,
        }


def _active_project(world, facility_id: str, site_id: str) -> bool:
    economy = world.economy
    if any(item.facility_id == facility_id and item.stage != "completed"
           for item in economy.expansions.values()):
        return True
    if any(item.site_id == site_id and item.stage != "completed"
           for item in economy.repairs.values()):
        return True
    if any(item.site_id == site_id and item.stage not in {"completed", "superseded"}
           for item in world.research.projects.values()):
        return True
    if any(item.work_kind == "facility" and item.work_id == facility_id
           for item in world.society.workforce_transitions.values()):
        return True
    payroll = economy.payrolls.get(facility_id)
    if payroll is not None and payroll.day == world.clock.absolute_day:
        return True
    facility = economy.facilities.get(facility_id)
    current = _event(world, facility.last_event_id if facility else None)
    return bool(current is not None and current.day == world.clock.absolute_day
                and current.event_type in {"production_completed", "production_limited"})


def _compatible_bindings(world, buyer_ref: EntityRef, facility, site):
    """Find one buyer-owned stock and payroll account local to the site."""
    economy = world.economy
    old_stock = economy.stocks.get(facility.stock_id)
    if old_stock is None:
        return ()
    settlement = next((item for item in world.society.settlements.values()
                       if item.region_id in site.region_ids and item.id == old_stock.location_id), None)
    if settlement is None:
        return ()
    stocks = sorted((stock for stock in economy.stocks.values()
                     if stock.owner_ref == buyer_ref and stock.location_id == settlement.id),
                    key=lambda item: item.id)
    accounts = sorted((account for account in economy.accounts.values()
                       if account.owner_ref == buyer_ref), key=lambda item: item.id)
    if not stocks or not accounts:
        return ()
    return tuple((stock, account) for stock in stocks for account in accounts)


def _eligible_facility(world, seller_ref: EntityRef, site, facility):
    economy = world.economy
    if (site.kind != WORKSHOP_KIND or site.owner_ref != seller_ref
            or site.maintainer_ref != seller_ref or not site.enabled or site.integrity <= 0
            or facility.site_id != site.id or facility.stock_id not in economy.stocks
            or facility.recipe_id not in economy.recipes):
        return False
    # Conveying the site changes its owner, and every facility anchored to it
    # must keep belonging to that owner.  A site with more than one production
    # line cannot be handed over by rebinding a single facility.
    if sum(1 for item in economy.facilities.values() if item.site_id == site.id) != 1:
        return False
    stock = economy.stocks[facility.stock_id]
    account = economy.accounts.get(facility.payroll_account_id)
    recipe = economy.recipes[facility.recipe_id]
    return (stock.owner_ref == seller_ref and account is not None
            and account.owner_ref == seller_ref
            and recipe.capability_id in site.capability_ids
            and not _active_project(world, facility.id, site.id))


def _actor_can_transfer(world, actor_ref: EntityRef) -> bool:
    return (actor_ref.kind in {"polity", "organization"}
            and can_actor_act_for(world, actor_ref, actor_ref, "supply")
            and can_actor_act_for(world, actor_ref, actor_ref, "trade"))


def productive_site_conveyance_options(world, seller_ref: EntityRef):
    """Enumerate current workshop conveyances; no option is persisted."""
    if not isinstance(seller_ref, EntityRef) or not _actor_can_transfer(world, seller_ref):
        return ()
    try:
        validate_actor(world, seller_ref)
    except ValueError:
        return ()
    result = []
    for site in sorted(world.map.infrastructure_sites.values(), key=lambda item: item.id):
        facilities = sorted((facility for facility in world.economy.facilities.values()
                             if facility.site_id == site.id), key=lambda item: item.id)
        for facility in facilities:
            if not _eligible_facility(world, seller_ref, site, facility):
                continue
            candidates = []
            for buyer_kind, registry in (("organization", world.society.organizations),
                                         ("polity", world.society.polities)):
                for buyer_id in sorted(registry):
                    buyer_ref = EntityRef(buyer_kind, buyer_id)
                    if buyer_ref == seller_ref or not _actor_can_transfer(world, buyer_ref):
                        continue
                    candidates.extend((buyer_ref, stock, account)
                                      for stock, account in _compatible_bindings(world, buyer_ref, facility, site))
            for buyer_ref, stock, account in candidates:
                payload = {
                    "site_id": site.id,
                    "facility_id": facility.id,
                    "seller_ref": seller_ref.to_dict(),
                    "buyer_ref": buyer_ref.to_dict(),
                    "stock_id": stock.id,
                    "payroll_account_id": account.id,
                    "site_last_event_id": site.last_event_id,
                    "facility_last_event_id": facility.last_event_id,
                }
                option = ProductiveSiteConveyanceOption(
                    id=_canonical_id(payload),
                    site_id=site.id,
                    facility_id=facility.id,
                    seller_ref=seller_ref,
                    buyer_ref=buyer_ref,
                    stock_id=stock.id,
                    payroll_account_id=account.id,
                    site_last_event_id=site.last_event_id,
                    facility_last_event_id=facility.last_event_id,
                )
                result.append(option)
    return tuple(sorted(result, key=lambda item: item.id))


def seller_conveyance_options(world, seller_ref: EntityRef):
    """Alias matching the domain's shorter affordance vocabulary."""
    return productive_site_conveyance_options(world, seller_ref)


def _proposal_payload_matches(option: ProductiveSiteConveyanceOption, payload: Any) -> bool:
    return isinstance(payload, dict) and payload == option.decision()


def conveyance_acceptance_options(world, buyer_ref: EntityRef):
    """Recompose offers known to a recipient from seller decisions only."""
    if not isinstance(buyer_ref, EntityRef) or not _actor_can_transfer(world, buyer_ref):
        return ()
    options = []
    for proposal in world.events:
        if (not _is_material_decision(proposal) or proposal.day != world.clock.absolute_day
                or proposal.decision.get("action") != SELLER_ACTION):
            continue
        payload = proposal.decision
        if not isinstance(payload, dict):
            continue
        try:
            seller_ref = _seller_from_payload(payload)
        except ValueError:
            continue
        option = next((item for item in productive_site_conveyance_options(world, seller_ref)
                       if _proposal_payload_matches(item, payload)
                       and item.buyer_ref == buyer_ref), None)
        if option is None or _already_conveyed(world, proposal.id):
            continue
        options.append(ProductiveSiteConveyanceAcceptanceOption(
            id=f"{option.id}:accept:{proposal.id}", proposal_event_id=proposal.id,
            option_id=option.id, site_id=option.site_id, facility_id=option.facility_id,
            seller_ref=option.seller_ref, buyer_ref=option.buyer_ref,
            stock_id=option.stock_id, payroll_account_id=option.payroll_account_id,
        ))
    return tuple(sorted(options, key=lambda item: item.id))


def _seller_from_payload(payload: Any) -> EntityRef:
    if not isinstance(payload, dict):
        raise ValueError("conveyance proposal requires a decision payload")
    actor = payload.get("actor_ref")
    try:
        return EntityRef.from_dict(actor)
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError("conveyance proposal has an invalid seller") from exc


def _already_conveyed(world, proposal_event_id: str) -> bool:
    return any(event.event_type == "productive_site_conveyed"
               and proposal_event_id in {link.cause_event_id for link in event.causal_links}
               for event in world.events)


def _proposal_option(world, proposal: WorldEvent):
    payload = proposal.decision
    if (not _is_material_decision(proposal) or proposal.day != world.clock.absolute_day
            or not isinstance(payload, dict) or payload.get("action") != SELLER_ACTION):
        return None
    try:
        seller = _seller_from_payload(payload)
    except ValueError:
        return None
    return next((item for item in productive_site_conveyance_options(world, seller)
                 if _proposal_payload_matches(item, payload)), None)


def _acceptance_option(world, option_id: str, buyer_ref: EntityRef):
    return next((item for item in conveyance_acceptance_options(world, buyer_ref) if item.id == option_id), None)


def _decision(world, decision_event_id: str | None):
    return _event(world, decision_event_id)


def _is_material_decision(event: WorldEvent | None) -> bool:
    """Only an actor/deterministic decision may authorize an owner mutation.

    An interpretation can describe an offer, but it is never itself consent
    to change the Map or Economy.  Deterministic policy decisions remain
    accepted here because the current medieval runner uses that origin for
    its non-LLM actor policies; the public proposal/acceptance helpers mark
    explicit bilateral choices as ``ACTOR_DECISION``.
    """
    return bool(
        event is not None
        and event.fact_kind == FactKind.DECISION
        and event.causal_origin != CausalOrigin.LLM_INTERPRETATION
        and isinstance(event.decision, dict)
    )


def record_conveyance_proposal(world, option_id: str) -> WorldEvent:
    """Record the seller's current, zero-delta proposal decision."""
    option = next((item for seller in (
        *(EntityRef("polity", key) for key in sorted(world.society.polities)),
        *(EntityRef("organization", key) for key in sorted(world.society.organizations)),
    ) for item in productive_site_conveyance_options(world, seller) if item.id == option_id), None)
    if option is None:
        raise ValueError("productive site conveyance option is stale or unknown")
    if any(event.fact_kind == FactKind.DECISION and event.decision == option.decision()
           for event in world.events):
        raise ValueError("productive site conveyance proposal decision already exists")
    causes = _causes(option.site_last_event_id, option.facility_last_event_id)
    return record_event(world, "productive_site_conveyance_proposed",
                        "O proprietário apresentou uma proposta bilateral para transferir um workshop.",
                        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                        decision=option.decision(), cause_ids=causes)


def propose_site_conveyance(world, option_id: str) -> WorldEvent:
    return record_conveyance_proposal(world, option_id)


def record_conveyance_acceptance(world, option_id: str, buyer_ref: EntityRef) -> WorldEvent:
    option = _acceptance_option(world, option_id, buyer_ref)
    if option is None:
        raise ValueError("productive site conveyance acceptance option is stale or unknown")
    return record_event(world, "productive_site_conveyance_accepted",
                        "A contraparte aceitou a proposta bilateral do workshop.",
                        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                        decision=option.decision(),
                        cause_ids=(option.proposal_event_id,))


def accept_site_conveyance(world, option_id: str, *, decision_event_id: str) -> WorldEvent:
    """Execute the accepted conveyance after revalidating both decisions."""
    decision = _decision(world, decision_event_id)
    if (not _is_material_decision(decision)
            or decision.day != world.clock.absolute_day
            or decision.decision.get("action") != ACCEPT_ACTION):
        raise ValueError("productive site conveyance requires a current acceptance decision")
    actor = decision.decision.get("actor_ref")
    try:
        buyer_ref = EntityRef.from_dict(actor)
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError("acceptance has an invalid buyer") from exc
    option = _acceptance_option(world, option_id, buyer_ref)
    if option is None or decision.decision != option.decision():
        raise ValueError("productive site conveyance acceptance is stale")
    proposal = _event(world, option.proposal_event_id)
    seller_option = _proposal_option(world, proposal) if proposal is not None else None
    if seller_option is None or _already_conveyed(world, proposal.id):
        raise ValueError("productive site conveyance proposal is stale")
    seller_ref = seller_option.seller_ref
    site = world.map.infrastructure_sites.get(seller_option.site_id)
    facility = world.economy.facilities.get(seller_option.facility_id)
    old_stock = world.economy.stocks.get(seller_option.stock_id if facility is None else facility.stock_id)
    new_stock = world.economy.stocks.get(seller_option.stock_id)
    account = world.economy.accounts.get(seller_option.payroll_account_id)
    if (site is None or facility is None or old_stock is None or new_stock is None or account is None
            or not _eligible_facility(world, seller_ref, site, facility)
            or facility.stock_id == new_stock.id or facility.payroll_account_id == account.id
            or new_stock.owner_ref != buyer_ref or account.owner_ref != buyer_ref
            or (new_stock.id, account.id) not in {
                (stock.id, candidate.id)
                for stock, candidate in _compatible_bindings(world, buyer_ref, facility, site)
            }
            or not _actor_can_transfer(world, seller_ref) or not _actor_can_transfer(world, buyer_ref)):
        raise ValueError("productive site conveyance failed current owner or buyer binding validation")
    if _already_conveyed(world, proposal.id):
        raise ValueError("productive site conveyance acceptance was already executed")
    # Validate the complete replacement before recording the receipt.  This
    # keeps every rejection atomic even when a caller has edited a fixture.
    updated_facility = facility.model_copy(update={
        "stock_id": new_stock.id, "payroll_account_id": account.id,
    })
    type(facility).model_validate(updated_facility.model_dump(mode="json"))
    causes = _causes(proposal.id, decision_event_id, site.last_event_id,
                     facility.last_event_id, *old_stock.last_event_ids.values(),
                     *new_stock.last_event_ids.values(),
                     account.last_event_id)
    before_owner = _ref_payload(site.owner_ref)
    before_maintainer = _ref_payload(site.maintainer_ref)
    after_owner = _ref_payload(buyer_ref)
    event = record_event(
        world, "productive_site_conveyed",
        f"{site.name}: o workshop passou ao controle institucional da contraparte; estoques e contas permaneceram com seus proprietários.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(
            _delta("production", facility.id, "stock_id", facility.stock_id, new_stock.id),
            _delta("production", facility.id, "payroll_account_id", facility.payroll_account_id, account.id),
            _delta("site", site.id, "owner_ref", before_owner, after_owner),
            _delta("site", site.id, "maintainer_ref", before_maintainer, after_owner),
        ),
        cause_ids=causes,
    )
    world.economy.facilities[facility.id] = updated_facility.model_copy(update={"last_event_id": event.id})
    world.map.transfer_infrastructure_site_control(
        site.id, owner_ref=buyer_ref, maintainer_ref=buyer_ref, last_event_id=event.id,
    )
    return event


def execute_site_conveyance(world, option_id: str, *, decision_event_id: str) -> WorldEvent:
    return accept_site_conveyance(world, option_id, decision_event_id=decision_event_id)


__all__ = [
    "ProductiveSiteConveyanceAcceptanceOption",
    "ProductiveSiteConveyanceOption",
    "accept_site_conveyance",
    "conveyance_acceptance_options",
    "execute_site_conveyance",
    "productive_site_conveyance_options",
    "propose_site_conveyance",
    "record_conveyance_acceptance",
    "record_conveyance_proposal",
    "seller_conveyance_options",
]

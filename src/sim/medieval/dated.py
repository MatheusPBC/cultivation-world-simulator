"""Dispatch dated domains without dropping unknown scheduled situations."""

from .logistics import resolve_parcels
from .phases import resolve_dated_activities
from .commitments import resolve_diplomacy


def resolve_dated(world, situations):
    if any(s.kind not in {"activity", "cargo", "diplomacy", "diplomatic_review"} for s in situations):
        raise ValueError("unknown dated situation")
    resolve_dated_activities(world, [s for s in situations if s.kind == "activity"])
    resolve_parcels(world, [s for s in situations if s.kind == "cargo"])
    resolve_diplomacy(world, [s for s in situations if s.kind == "diplomacy"])

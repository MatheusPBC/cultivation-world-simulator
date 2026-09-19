"""Map-facing settlement footprint; demographic/political data stays society-owned."""

from dataclasses import dataclass
from functools import cached_property

from .state import SocietyState


@dataclass
class SettlementRegion:
    id: int
    settlement_id: str
    cors: list[tuple[int, int]]
    society: SocietyState

    @property
    def name(self) -> str:
        return self.society.settlements[self.settlement_id].name

    @property
    def area(self) -> int:
        return len(self.cors)

    @cached_property
    def center_loc(self) -> tuple[int, int]:
        """Authored settlement geometry is immutable during a medieval run.

        Route and travel calculations ask for this centroid thousands of times
        during a long smoke. Cache the geometry-derived value on the region;
        runtime state changes routes and society, never ``cors``. A newly
        constructed region (including a loaded map) receives its own cache.
        """
        x = sum(c[0] for c in self.cors) / len(self.cors)
        y = sum(c[1] for c in self.cors) / len(self.cors)
        return min(self.cors, key=lambda cell: ((cell[0] - x) ** 2 + (cell[1] - y) ** 2, cell))

    def get_region_type(self) -> str:
        return self.society.settlements[self.settlement_id].kind

    def get_info(self) -> str:
        return self.name

    def get_structured_info(self) -> dict:
        settlement = self.society.settlements[self.settlement_id]
        return {
            **settlement.model_dump(mode="json"),
            "population": self.society.population_at(self.settlement_id),
            "center_loc": list(self.center_loc),
        }

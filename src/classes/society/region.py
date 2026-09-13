"""Map-facing settlement footprint; demographic/political data stays society-owned."""

from dataclasses import dataclass

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

    @property
    def center_loc(self) -> tuple[int, int]:
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

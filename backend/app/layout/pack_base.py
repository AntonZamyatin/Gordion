from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def w(self) -> float:
        return self.max_x - self.min_x

    @property
    def h(self) -> float:
        return self.max_y - self.min_y

    @property
    def area(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)


@dataclass(frozen=True)
class PackParams:
    name: str
    padding: float = 80.0
    target_row_width: float | None = None  # if None, auto-derived


class PackingEngine(Protocol):
    name: str

    def pack(
        self,
        *,
        component_boxes: dict[int, BBox],
        params: PackParams,
    ) -> dict[int, tuple[float, float]]:
        """Return offsets (dx,dy) for each component bbox (in local coords)."""
        ...

from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Iterable


@dataclass(frozen=True)
class LayoutParams:
    name: str
    seed: int | None = 0  # deterministic by default


class LayoutEngine(Protocol):
    name: str

    def layout_component(
        self,
        *,
        graph,
        node_ids: Iterable[str],
        params: LayoutParams,
    ) -> dict[str, tuple[float, float]]:
        """Return local positions for nodes in the component."""
        ...

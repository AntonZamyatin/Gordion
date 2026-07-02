from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class PositionStore:
    # node_id -> (x,y) for the most recently computed full-view layout
    computed: dict[str, tuple[float, float]] = field(default_factory=dict)

    # node_id -> (x,y) set by user interactions
    overrides: dict[str, tuple[float, float]] = field(default_factory=dict)

    def apply_overrides(self, base: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
        out = dict(base)
        out.update(self.overrides)
        return out

    def set_override(self, node_id: str, x: float, y: float) -> None:
        self.overrides[node_id] = (x, y)

    def clear_override(self, node_id: str) -> None:
        self.overrides.pop(node_id, None)

    def clear_all_overrides(self) -> None:
        self.overrides.clear()

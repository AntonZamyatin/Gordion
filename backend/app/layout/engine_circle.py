from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Iterable

from app.layout.engine_base import LayoutEngine, LayoutParams


@dataclass
class CircleLayoutEngine(LayoutEngine):
    """
    Deterministic component layout:
    - sort node IDs
    - place on circle
    - radius grows ~ sqrt(n)

    This is a placeholder engine that makes the whole two-level pipeline work.
    """
    name: str = "circle"

    def layout_component(
        self,
        *,
        graph,
        node_ids: Iterable[str],
        params: LayoutParams,
    ) -> dict[str, tuple[float, float]]:
        ids = sorted(node_ids)
        n = len(ids)
        if n == 0:
            return {}

        # Radius choice: scales with sqrt(n) so components with more nodes look larger.
        R = 30.0 * math.sqrt(n)

        pos: dict[str, tuple[float, float]] = {}
        for i, nid in enumerate(ids):
            ang = 2.0 * math.pi * (i / n)
            pos[nid] = (R * math.cos(ang), R * math.sin(ang))
        return pos

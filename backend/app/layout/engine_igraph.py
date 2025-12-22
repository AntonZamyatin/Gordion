from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import igraph as ig

from app.layout.engine_base import LayoutEngine, LayoutParams


@dataclass
class IGraphLayoutEngine(LayoutEngine):
    """
    igraph-based Fruchterman–Reingold layout.

    - Undirected layout (visualization-oriented)
    - Deterministic node ordering
    - Supports warm start via `seed` positions
    """
    name: str = "igraph_fr"

    def layout_component(
        self,
        *,
        graph,
        node_ids: Iterable[str],
        params: LayoutParams,
        seed_positions: Optional[dict[str, tuple[float, float]]] = None,
    ) -> dict[str, tuple[float, float]]:
        ids = sorted(node_ids)
        n = len(ids)
        if n == 0:
            return {}

        idx = {nid: i for i, nid in enumerate(ids)}

        # Build undirected edge list
        edges = set()
        for e in graph.edges.values():
            u, v = e.start[0], e.end[0]
            if u in idx and v in idx and u != v:
                a, b = idx[u], idx[v]
                if a > b:
                    a, b = b, a
                edges.add((a, b))

        g = ig.Graph(n=n, edges=list(edges), directed=False)

        # Build seed layout if provided
        seed = None
        if seed_positions is not None:
            seed = [
                list(seed_positions.get(nid, (0.0, 0.0)))
                for nid in ids
            ]

        # Run FR
        layout = g.layout_fruchterman_reingold(
            niter=300 if n < 2000 else 600,
            seed=seed,
            grid="auto",
        )

        return {
            nid: (float(layout[i][0]), float(layout[i][1]))
            for i, nid in enumerate(ids)
        }

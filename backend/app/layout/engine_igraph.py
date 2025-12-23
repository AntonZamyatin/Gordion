from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import igraph as ig

from app.layout.engine_base import LayoutEngine, LayoutParams
from app.config.viz_config import CFG


def _node_id(endpoint):
    return endpoint[0] if isinstance(endpoint, tuple) else endpoint


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

        # Build undirected edge and weights lists
        edges_list: list[tuple[int,int]] = []
        weights: list[float] = []

        for e in graph.edges.values():
            u, v = _node_id(e.start), _node_id(e.end)
            if u in idx and v in idx and u != v:
                a, b = idx[u], idx[v]
                if a > b:
                    a, b = b, a
                edges_list.append((a, b))
                
                kind = getattr(e, "kind", None)
                
                if kind == "INTERNAL":
                    weights.append(CFG.layout.internal_edge_weight)
                else:
                    weights.append(CFG.layout.external_edge_weight)

        g = ig.Graph(n=n, edges=list(edges_list), directed=False)

        # Build seed layout if provided; otherwise None -> igraph random seed
        seed = None
        if seed_positions is not None:
            seed = []
            # deterministic fallback seed on a circle for missing nodes
            import math
            R = 10.0 * math.sqrt(n)
            for i, nid in enumerate(ids):
                if nid in seed_positions:
                    x, y = seed_positions[nid]
                else:
                    ang = 2.0 * math.pi * (i / max(n, 1))
                    x, y = R * math.cos(ang), R * math.sin(ang)
                seed.append([float(x), float(y)])

        if len(edges_list) == 0:
            # No edges: deterministic placement
            if seed is None:
                # still return a deterministic circle
                import math
                R = 10.0 * math.sqrt(n)
                return {
                    nid: (R * math.cos(2.0 * math.pi * i / n), R * math.sin(2.0 * math.pi * i / n))
                    for i, nid in enumerate(ids)
                }
            else:
                return {nid: (seed[i][0], seed[i][1]) for i, nid in enumerate(ids)}

        # Run FR
        layout = g.layout_fruchterman_reingold(
            niter=CFG.layout.fr_niter_small,
            seed=seed,
            grid=CFG.layout.fr_grid,
            weights=weights,
        )

        return {
            nid: (float(layout[i][0]), float(layout[i][1]))
            for i, nid in enumerate(ids)
        }

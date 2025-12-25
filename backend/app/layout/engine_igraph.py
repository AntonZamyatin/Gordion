from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
from collections import deque, defaultdict

import igraph as ig

from app.layout.engine_base import LayoutEngine, LayoutParams
from app.config.viz_config import CFG


def _node_id(endpoint):
    return endpoint[0] if isinstance(endpoint, tuple) else endpoint

def _linear_seed_positions(
    *,
    ids: list[str],
    edges_list: list[tuple[int, int]],
    weights: Optional[list[float]] = None,
    x_step: float = 30.0,
    y_step: float = 20.0,
    jitter: float = 0.0,
) -> dict[str, tuple[float, float]]:
    """
    Produce a topology-aware linear seed for an undirected graph component.

    Strategy:
      - Build adjacency.
      - Find an approximate diameter path (two BFS sweeps).
      - Put the diameter path ("backbone") on x-axis, evenly spaced.
      - Place remaining nodes by BFS from nearest backbone node, on alternating sides.

    Parameters:
      x_step: spacing along backbone
      y_step: spacing per BFS layer off the backbone
      jitter: small random-ish jitter (0 disables). Keep 0 for determinism.
    """
    n = len(ids)
    if n == 0:
        return {}

    # Build adjacency over indices 0..n-1
    adj: list[list[int]] = [[] for _ in range(n)]
    for a, b in edges_list:
        if a == b:
            continue
        adj[a].append(b)
        adj[b].append(a)

    # Handle isolated nodes / no edges: line in id order
    if not edges_list:
        return {nid: (i * x_step, 0.0) for i, nid in enumerate(ids)}

    def bfs_farthest(start: int) -> tuple[int, list[int]]:
        """Return (farthest_node, parent[]) from BFS starting at start."""
        parent = [-1] * n
        dist = [-1] * n
        q = deque([start])
        dist[start] = 0
        far = start
        while q:
            v = q.popleft()
            if dist[v] > dist[far]:
                far = v
            for w in adj[v]:
                if dist[w] == -1:
                    dist[w] = dist[v] + 1
                    parent[w] = v
                    q.append(w)
        return far, parent

    def reconstruct_path(parent: list[int], end: int) -> list[int]:
        path = []
        cur = end
        while cur != -1:
            path.append(cur)
            cur = parent[cur]
        path.reverse()
        return path

    # Pick a reasonable start: a leaf if exists (deg==1), else 0
    start = next((i for i in range(n) if len(adj[i]) == 1), 0)

    # Two BFS sweeps to approximate diameter
    u, _ = bfs_farthest(start)
    v, parent_u = bfs_farthest(u)
    backbone = reconstruct_path(parent_u, v)  # indices in order

    backbone_set = set(backbone)

    # Map backbone index -> x coordinate
    pos: dict[int, tuple[float, float]] = {}
    for k, node in enumerate(backbone):
        pos[node] = (k * x_step, 0.0)

    # Assign each non-backbone node to nearest backbone node using multi-source BFS
    owner = [-1] * n      # which backbone node "owns" it
    layer = [-1] * n      # distance from backbone
    q = deque()
    for b in backbone:
        owner[b] = b
        layer[b] = 0
        q.append(b)

    while q:
        vtx = q.popleft()
        for w in adj[vtx]:
            if layer[w] == -1:
                layer[w] = layer[vtx] + 1
                owner[w] = owner[vtx]
                q.append(w)

    # Group nodes by owner and by layer
    buckets: dict[int, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    for i in range(n):
        if i in backbone_set:
            continue
        buckets[owner[i]][layer[i]].append(i)

    # Place non-backbone nodes near their owner's x coordinate
    # Alternate sides (+y/-y) per layer; spread within layer by small x offsets
    for b in backbone:
        base_x, _ = pos[b]
        layers = buckets.get(b, {})
        for d in sorted(layers.keys()):
            nodes = sorted(layers[d])  # deterministic
            side = 1.0 #Sif (d % 2 == 1) else -1.0  # alternate above/below
            y = side * d * y_step

            # Spread along x slightly to reduce overlap
            # Center the small fan around base_x
            m = len(nodes)
            for j, node in enumerate(nodes):
                x = base_x + (j - (m - 1) / 2.0) * (x_step * 0.25)
                pos[node] = (x, y)

    # Any remaining nodes (shouldn't happen) -> append to the end
    missing = [i for i in range(n) if i not in pos]
    if missing:
        end_x = (len(backbone)) * x_step
        for k, i in enumerate(sorted(missing)):
            pos[i] = (end_x + k * x_step, 0.0)

    return {ids[i]: (float(x), float(y)) for i, (x, y) in pos.items()}


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
        if seed_positions is None:
            seed_positions = _linear_seed_positions(
                ids=ids,
                edges_list=edges_list,
                weights=weights,
                x_step=CFG.layout.seed_x_step,  # add to config or hardcode
                y_step=CFG.layout.seed_y_step,
                jitter=0.0,
            )

        #seed = g.layout_circle().coords

        seed = []
        import math
        R = 10.0 * math.sqrt(n)  # fallback circle for missing keys
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

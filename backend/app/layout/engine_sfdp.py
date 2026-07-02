# backend/app/layout/engine_sfdp.py
from __future__ import annotations
import random
import os
import math
from pathlib import Path


from dataclasses import dataclass
from typing import Iterable
from collections import deque, defaultdict


from app.layout.engine_base import LayoutEngine, LayoutParams

# Reuse the endpoint helper logic conceptually:
# RenderGraph edges: endpoints are node_id (str)
# CoreGraph edges: endpoints are (node_id, port)
def _endpoint_node_id(x) -> str:
    return x[0] if isinstance(x, tuple) else x

def _build_component_adjacency(
    *,
    n: int,
    edges: list[tuple[int, int]],
) -> list[list[int]]:
    adj: list[list[int]] = [[] for _ in range(n)]
    for a, b in edges:
        if a == b:
            continue
        adj[a].append(b)
        adj[b].append(a)
    return adj

def _write_svg(
    path: str | Path,
    *,
    n: int,
    edges: list[tuple[int, int]],
    coords: list[tuple[float, float]],
    width: int = 1600,
    height: int = 900,
    margin: int = 20,
    node_r: float = 1.2,
    edge_opacity: float = 0.15,
) -> None:
    """
    Minimal SVG writer for debugging layouts.
    coords is a list of (x,y) with length n, in the same index space as edges.
    """
    # Filter finite coords
    xs = [c[0] for c in coords if math.isfinite(c[0])]
    ys = [c[1] for c in coords if math.isfinite(c[1])]
    if not xs or not ys:
        return

    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    dx = max(maxx - minx, 1e-9)
    dy = max(maxy - miny, 1e-9)

    sx = (width - 2 * margin) / dx
    sy = (height - 2 * margin) / dy
    s = min(sx, sy)  # uniform scale

    def tx(x): return margin + (x - minx) * s
    def ty(y): return margin + (y - miny) * s

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                f'viewBox="0 0 {width} {height}" style="background:#111">\n')

        # edges
        f.write(f'<g stroke="#bbb" stroke-width="1" stroke-opacity="{edge_opacity}">\n')
        for a, b in edges:
            xa, ya = coords[a]
            xb, yb = coords[b]
            if not (math.isfinite(xa) and math.isfinite(ya) and math.isfinite(xb) and math.isfinite(yb)):
                continue
            f.write(f'<line x1="{tx(xa):.3f}" y1="{ty(ya):.3f}" x2="{tx(xb):.3f}" y2="{ty(yb):.3f}"/>\n')
        f.write("</g>\n")

        # nodes
        f.write('<g fill="#ddd" fill-opacity="0.9">\n')
        for i in range(n):
            x, y = coords[i]
            if not (math.isfinite(x) and math.isfinite(y)):
                continue
            f.write(f'<circle cx="{tx(x):.3f}" cy="{ty(y):.3f}" r="{node_r}"/>\n')
        f.write("</g>\n")

        f.write("</svg>\n")



def _bfs_farthest(adj: list[list[int]], start: int) -> tuple[int, list[int], list[int]]:
    """
    Returns: (farthest_vertex, parent[], dist[])
    """
    n = len(adj)
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
    return far, parent, dist


def _reconstruct_path(parent: list[int], end: int) -> list[int]:
    path: list[int] = []
    cur = end
    while cur != -1:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path


def _diameter_backbone(adj: list[list[int]]) -> list[int]:
    """
    Approximate diameter path by two BFS sweeps.
    Works well for sparse graphs and gives a stable long backbone.
    """
    n = len(adj)
    # Prefer a leaf if exists; otherwise 0
    start = next((i for i in range(n) if len(adj[i]) == 1), 0)
    u, _, _ = _bfs_farthest(adj, start)
    v, parent_u, _ = _bfs_farthest(adj, u)
    return _reconstruct_path(parent_u, v)


def _seed_positions_diameter_backbone(
    *,
    ids: list[str],
    edges_idx: list[tuple[int, int]],
    x_step: float = 30.0,
    y_step: float = 20.0,
    fan_x_step: float = 10.0,
) -> list[list[float]]:
    """
    Create a linear seed:
      - diameter path is backbone on x-axis
      - off-backbone nodes placed in BFS layers away from their nearest backbone anchor
        alternating above/below, with slight x-fanning.

    Returns: seed coords list of length n aligned with ids order.
    """
    n = len(ids)
    adj = _build_component_adjacency(n=n, edges=edges_idx)

    # Backbone = approximate diameter path
    backbone = _diameter_backbone(adj)
    backbone_set = set(backbone)

    seed = [[0.0, 0.0] for _ in range(n)]

    # Place backbone on x-axis
    for k, v in enumerate(backbone):
        seed[v] = [k * x_step, random.uniform(0, y_step)]

    # Multi-source BFS from backbone to assign owner + layer
    owner = [-1] * n
    layer = [-1] * n
    q = deque()
    for b in backbone:
        owner[b] = b
        layer[b] = 0
        q.append(b)

    while q:
        v = q.popleft()
        for w in adj[v]:
            if layer[w] == -1:
                layer[w] = layer[v] + 1
                owner[w] = owner[v]
                q.append(w)

    # Group non-backbone nodes by (owner backbone vertex, layer)
    buckets: dict[int, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    for v in range(n):
        if v in backbone_set:
            continue
        # layer[v] can still be -1 only if graph is disconnected; treat as tail
        d = layer[v] if layer[v] != -1 else (len(backbone) + 1)
        buckets[owner[v]][d].append(v)

    # Need backbone x coordinate lookup
    backbone_x = {v: seed[v][0] for v in backbone}

    # Place branches
    for b in backbone:
        base_x = backbone_x[b]
        layers = buckets.get(b, {})
        for d in sorted(layers.keys()):
            nodes = sorted(layers[d])  # deterministic
            # Alternate side by layer to avoid stacking; push farther for deeper layers
            side = 1.0 #if (d % 2 == 1) else -1.0
            y = side * d * y_step

            m = len(nodes)
            for j, v in enumerate(nodes):
                # fan slightly along x to reduce overlap within same layer
                x = base_x + (j - (m - 1) / 2.0) * fan_x_step
                seed[v] = [x, y]

    # Any unassigned vertices (should be none) => append at end
    missing = [v for v in range(n) if seed[v] == [0.0, 0.0] and v not in backbone_set]
    if missing:
        end_x = (len(backbone) + 1) * x_step
        for k, v in enumerate(sorted(missing)):
            seed[v] = [end_x + k * x_step, 0.0]

    return seed, backbone


def _seed_positions_for_render_graph(graph, ids: list[str]) -> list[list[float]]:
    # Deterministic: group by core_node_id, then by chain_index
    # Place each core node group consecutively on x; within group, small step.
    core_groups: dict[str, list[str]] = {}
    for nid in ids:
        rn = graph.nodes.get(nid)
        core = getattr(rn, "core_node_id", nid)
        core_groups.setdefault(core, []).append(nid)

    # stable order: by core id
    ordered_cores = sorted(core_groups.keys())
    x = 0.0
    seed = [[0.0, 0.0] for _ in ids]
    idx = {nid: i for i, nid in enumerate(ids)}

    CORE_STEP = 30.0
    INTRA_STEP = 5.0

    for core in ordered_cores:
        group = core_groups[core]
        # order within core by chain_index if present
        group.sort(key=lambda nid: getattr(graph.nodes.get(nid), "chain_index", 0))
        for j, nid in enumerate(group):
            seed[idx[nid]] = [x + j * INTRA_STEP, 0.0]
        x += CORE_STEP
    return seed


@dataclass
class SfdpLayoutEngine(LayoutEngine):
    """
    graph-tool SFDP layout engine.

    Notes:
    - Runs in-process (no subprocess).
    - Designed for large components; scalable force-directed.
    - Optional edge weights supported via eweight property map.
    """
    name: str = "sfdp"

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

        idx = {nid: i for i, nid in enumerate(ids)}

        # Collect induced edges + weights
        edges: list[tuple[int, int]] = []
        weights: list[float] = []

        # If the graph provides render edges with kind INTERNAL/EXTERNAL (RenderGraph),
        # use those to set weights; otherwise default to 1.0.
        for e in graph.edges.values():
            u = _endpoint_node_id(e.start)
            v = _endpoint_node_id(e.end)
            if u not in idx or v not in idx or u == v:
                continue
            a, b = idx[u], idx[v]
            edges.append((a, b))

            kind = getattr(e, "kind", None)
            if kind == "INTERNAL":
                # keep INTERNAL edges "tight" (smaller effective length)
                weights.append(6.0)
            elif kind == "EXTERNAL":
                # EXTERNAL edges slightly looser by default
                weights.append(1.0)
            else:
                weights.append(1.0)

        # No edges => deterministic line placement
        if not edges:
            step = 10.0
            return {nid: (i * step, 0.0) for i, nid in enumerate(ids)}

        # Import graph-tool lazily so backend can still start without it
        import graph_tool as gt
        import graph_tool.draw as gtd

        g = gt.Graph(directed=False)
        g.add_vertex(n)

        # Add edges. Use add_edge_list for speed.
        g.add_edge_list(edges)

        # Edge weights: assign in the same order edges were added.
        # add_edge_list inserts edges in iteration order; g.edges() should reflect that order.
        eweight = g.new_edge_property("double")
        for ee, w in zip(g.edges(), weights):
            eweight[ee] = float(w)

        # Run SFDP. Start with a conservative C, later tune.
        # params.seed is used only indirectly; SFDP isn't guaranteed deterministic,
        # but keeping a fixed initial condition later can help (we will add seeding in Step 3).

                # Build topology-aware seed (diameter backbone) for ANY graph type
        pos0 = g.new_vertex_property("vector<double>")
        seed_list, backbone = _seed_positions_diameter_backbone(
            ids=ids,
            edges_idx=edges,
            x_step=30.0,
            y_step=20.0,
            fan_x_step=10.0,
        )
        for i in range(n):
            pos0[g.vertex(i)] = seed_list[i]

        pin = g.new_vertex_property("bool")
        pin.set_value(False)
        pin[g.vertex(backbone[0])] = True
        pin[g.vertex(backbone[-1])] = True
        print(ids[0])
        
        seed_coords = [(float(pos0[g.vertex(i)][0]), float(pos0[g.vertex(i)][1])) for i in range(n)]
        _write_svg(
            f"./svg/sfdp_seed_n{n}_m{len(edges)}.svg",
            n=n, edges=edges, coords=seed_coords
        )


        pos = gtd.sfdp_layout(
            g, 
            p=0.05,
            pos=pos0,
            pin=pin,
            #pos=pos0,
            #p=2,
            #eweight=eweight,
            #multilevel=False,
            #max_iter=1500,
            #theta=0.6,             # default BH opening; OK
            #epsilon=0.01,
        )
        
        
        out_coords = [(float(pos[g.vertex(i)][0]), float(pos[g.vertex(i)][1])) for i in range(n)]
        _write_svg(
            f"./svg/sfdp_out_n{n}_m{len(edges)}.svg",
            n=n, edges=edges, coords=out_coords
        )


        out: dict[str, tuple[float, float]] = {}
        for i, nid in enumerate(ids):
            xy = pos[g.vertex(i)]
            out[nid] = (float(xy[0]), float(xy[1]))
        return out
        #return {nid: (float(seed_list[i][0]), float(seed_list[i][1])) for i, nid in enumerate(ids)}

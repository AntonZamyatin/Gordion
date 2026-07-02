# backend/app/layout/engine_sgd.py
"""2D stochastic-gradient-descent layout for the port graph.

Force-directed layout (FR/SFDP) never gave clean linear assembly layouts. SGD
stress minimization does: it places nodes so that pairwise geometric distance
matches graph-theoretic distance, which unfolds chain-like genome graphs into
straight backbones (the BandageNG look) instead of curling them into knots.

Design:
- Layout is per connected component, then components are row-packed.
- A diameter-backbone linear seed gives a strong "unfolded" prior.
- Stress terms come from all edges (local structure + bp-scaled lengths) plus a
  sparse set of pivot->all-nodes terms (global structure) so we avoid O(n^2).

The inner SGD loop is a plain Python loop for now (fine at spike scale); Phase 4
vectorizes / JITs it for 10^5-10^6.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math

import numpy as np

from app.layout.port_graph import PortGraph


@dataclass(slots=True, frozen=True)
class SgdParams:
    iterations: int = 30
    n_pivots: int = 50
    seed: int = 0
    component_pad: float = 3.0


# ---------------------------------------------------------------------------
# Graph helpers (operate on local integer indices within one component)
# ---------------------------------------------------------------------------
def _connected_components(n: int, adj: list[list[tuple[int, float]]]) -> list[list[int]]:
    seen = [False] * n
    comps: list[list[int]] = []
    for s in range(n):
        if seen[s]:
            continue
        stack = [s]
        seen[s] = True
        comp = []
        while stack:
            u = stack.pop()
            comp.append(u)
            for v, _w in adj[u]:
                if not seen[v]:
                    seen[v] = True
                    stack.append(v)
        comps.append(comp)
    return comps


def _bfs_hops(adj: list[list[tuple[int, float]]], src: int, m: int):
    """Unweighted BFS; returns (hop_dist, parent)."""
    dist = [-1] * m
    parent = [-1] * m
    dist[src] = 0
    q = [src]
    head = 0
    while head < len(q):
        u = q[head]
        head += 1
        for v, _w in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                parent[v] = u
                q.append(v)
    return dist, parent


def _dijkstra(adj: list[list[tuple[int, float]]], src: int, m: int) -> np.ndarray:
    """Shortest paths using edge target lengths as weights."""
    dist = np.full(m, np.inf)
    dist[src] = 0.0
    pq: list[tuple[float, int]] = [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def _diameter_backbone(adj: list[list[tuple[int, float]]], m: int) -> list[int]:
    """Approximate longest path via two BFS sweeps (double-sweep heuristic)."""
    hops_a, _ = _bfs_hops(adj, 0, m)
    a = int(np.argmax([h if h >= 0 else -1 for h in hops_a]))
    hops_b, parent = _bfs_hops(adj, a, m)
    b = int(np.argmax([h if h >= 0 else -1 for h in hops_b]))
    path = []
    cur = b
    while cur != -1:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------
def _linear_seed(
    adj: list[list[tuple[int, float]]], m: int, backbone: list[int]
) -> np.ndarray:
    pos = np.zeros((m, 2), dtype=float)

    # edge length lookup for consecutive backbone nodes
    tgt: dict[tuple[int, int], float] = {}
    for u in range(m):
        for v, w in adj[u]:
            tgt[(u, v)] = w

    on_backbone = set(backbone)
    x = 0.0
    backbone_x: dict[int, float] = {}
    for k, node in enumerate(backbone):
        if k > 0:
            prev = backbone[k - 1]
            x += tgt.get((prev, node), 1.0)
        backbone_x[node] = x
        pos[node] = (x, 0.0)

    # attach every other node to its nearest backbone node (multi-source BFS)
    dist = [-1] * m
    nearest = [-1] * m
    q: list[int] = []
    for node in backbone:
        dist[node] = 0
        nearest[node] = node
        q.append(node)
    head = 0
    while head < len(q):
        u = q[head]
        head += 1
        for v, _w in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                nearest[v] = nearest[u]
                q.append(v)

    y_step = 1.0
    for node in range(m):
        if node in on_backbone:
            continue
        base_x = backbone_x.get(nearest[node], 0.0)
        layer = max(dist[node], 1)
        sign = 1.0 if (node % 2 == 0) else -1.0
        pos[node] = (base_x + 0.25 * layer, sign * y_step * layer)
    return pos


# ---------------------------------------------------------------------------
# SGD
# ---------------------------------------------------------------------------
def _run_sgd(
    pos: np.ndarray,
    I: np.ndarray,
    J: np.ndarray,
    D: np.ndarray,
    W: np.ndarray,
    *,
    iterations: int,
    rng: np.random.Generator,
) -> None:
    if len(I) == 0:
        return
    w_min = float(W.min())
    w_max = float(W.max())
    eta_max = 1.0 / w_min
    eta_min = 0.1 / w_max
    if iterations > 1:
        lam = math.log(eta_max / eta_min) / (iterations - 1)
        etas = eta_max * np.exp(-lam * np.arange(iterations))
    else:
        etas = np.array([eta_max])

    order = np.arange(len(I))
    Il, Jl, Dl, Wl = I.tolist(), J.tolist(), D.tolist(), W.tolist()
    px = pos  # alias
    for it in range(iterations):
        eta = etas[it]
        rng.shuffle(order)
        for k in order.tolist():
            i = Il[k]
            j = Jl[k]
            d = Dl[k]
            mu = Wl[k] * eta
            if mu > 1.0:
                mu = 1.0
            dx = px[i, 0] - px[j, 0]
            dy = px[i, 1] - px[j, 1]
            mag = math.sqrt(dx * dx + dy * dy)
            if mag < 1e-9:
                dx, dy, mag = 1e-6, 0.0, 1e-6
            r = 0.5 * mu * (mag - d) / mag
            rx = r * dx
            ry = r * dy
            px[i, 0] -= rx
            px[i, 1] -= ry
            px[j, 0] += rx
            px[j, 1] += ry


def _layout_component(
    comp: list[int],
    adj_global: list[list[tuple[int, float]]],
    p: SgdParams,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return an (m, 2) array of local positions for one component."""
    m = len(comp)
    local = {g: i for i, g in enumerate(comp)}
    adj: list[list[tuple[int, float]]] = [[] for _ in range(m)]
    for g in comp:
        i = local[g]
        for gn, w in adj_global[g]:
            if gn in local:
                adj[i].append((local[gn], w))

    if m == 1:
        return np.zeros((1, 2), dtype=float)

    backbone = _diameter_backbone(adj, m)
    pos = _linear_seed(adj, m, backbone)

    # --- stress terms ---
    ti: list[int] = []
    tj: list[int] = []
    td: list[float] = []
    tw: list[float] = []

    seen_pairs: set[tuple[int, int]] = set()
    for i in range(m):
        for j, w in adj[i]:
            a, b = (i, j) if i < j else (j, i)
            if (a, b) in seen_pairs:
                continue
            seen_pairs.add((a, b))
            d = max(w, 1e-6)
            ti.append(a)
            tj.append(b)
            td.append(d)
            tw.append(1.0 / (d * d))

    # sparse pivots (maxmin) -> pivot-to-all stress terms for global structure
    n_piv = min(p.n_pivots, m)
    if n_piv > 0:
        first = int(rng.integers(m))
        pivots = [first]
        dmat = [_dijkstra(adj, first, m)]
        mind = dmat[0].copy()
        while len(pivots) < n_piv:
            nxt = int(np.argmax(np.where(np.isfinite(mind), mind, -1.0)))
            if nxt in pivots:
                break
            pivots.append(nxt)
            dd = _dijkstra(adj, nxt, m)
            dmat.append(dd)
            mind = np.minimum(mind, dd)

        for pv, dd in zip(pivots, dmat):
            for v in range(m):
                if v == pv:
                    continue
                d = dd[v]
                if not np.isfinite(d) or d <= 0:
                    continue
                a, b = (pv, v) if pv < v else (v, pv)
                if (a, b) in seen_pairs:
                    continue
                seen_pairs.add((a, b))
                td.append(float(d))
                ti.append(a)
                tj.append(b)
                tw.append(1.0 / (float(d) * float(d)))

    _run_sgd(
        pos,
        np.asarray(ti, dtype=np.int64),
        np.asarray(tj, dtype=np.int64),
        np.asarray(td, dtype=float),
        np.asarray(tw, dtype=float),
        iterations=p.iterations,
        rng=rng,
    )
    return pos


def _row_pack(boxes: list[tuple[float, float]], pad: float) -> list[tuple[float, float]]:
    """Place component bounding boxes (w, h) into rows; return (ox, oy) offsets."""
    if not boxes:
        return []
    total_w = sum(w for w, _h in boxes)
    row_target = max(math.sqrt(total_w * max(h for _w, h in boxes)) * 1.2, 1.0)
    offsets: list[tuple[float, float]] = []
    cur_x = 0.0
    cur_y = 0.0
    row_h = 0.0
    for w, h in boxes:
        if cur_x > 0.0 and cur_x + w > row_target:
            cur_x = 0.0
            cur_y += row_h + pad
            row_h = 0.0
        offsets.append((cur_x, cur_y))
        cur_x += w + pad
        row_h = max(row_h, h)
    return offsets


def layout_port_graph(
    pg: PortGraph, params: SgdParams | None = None
) -> dict[str, tuple[float, float]]:
    """Compute 2D positions for every port node id in the port graph."""
    p = params or SgdParams()
    node_index = {nid: i for i, nid in enumerate(pg.nodes)}
    n = len(pg.nodes)

    adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for e in pg.edges:
        i = node_index[e.u]
        j = node_index[e.v]
        if i == j:
            continue
        adj[i].append((j, e.target))
        adj[j].append((i, e.target))

    comps = _connected_components(n, adj)
    rng = np.random.default_rng(p.seed)

    comp_local: list[tuple[list[int], np.ndarray]] = []
    boxes: list[tuple[float, float]] = []
    for comp in comps:
        pos = _layout_component(comp, adj, p, rng)
        # normalize to origin
        pos = pos - pos.min(axis=0)
        w = float(pos[:, 0].max()) if len(pos) else 0.0
        h = float(pos[:, 1].max()) if len(pos) else 0.0
        comp_local.append((comp, pos))
        boxes.append((w, h))

    offsets = _row_pack(boxes, p.component_pad)

    out: dict[str, tuple[float, float]] = {}
    for (comp, pos), (ox, oy) in zip(comp_local, offsets):
        for local_i, g in enumerate(comp):
            x = float(pos[local_i, 0]) + ox
            y = float(pos[local_i, 1]) + oy
            out[pg.nodes[g]] = (x, y)
    return out

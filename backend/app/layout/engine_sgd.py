# backend/app/layout/engine_sgd.py
"""2D stochastic-gradient-descent layout for the port graph.

Force-directed layout (FR/SFDP) never gave clean linear assembly layouts. SGD
stress minimization does: it places nodes so that pairwise geometric distance
matches graph-theoretic distance, which unfolds chain-like genome graphs into
straight backbones (the BandageNG look) instead of curling them into knots.

Design:
- Layout is per connected component. Each component is then rigidly rotated to
  its *tightest* (minimum-area) bounding box so a thin chain lies flat as a bar
  (`_min_area_rotation`), very elongated ones get a small cosmetic tilt, and the
  boxes are tiled from a corner into a roughly square page, largest first
  (`_corner_pack`). None of this touches solver output — all rigid isometries, so
  intra-component distances are unchanged.
- A diameter-backbone linear seed gives a strong "unfolded" prior.
- Stress terms come from all edges (local structure + bp-scaled lengths) plus a
  sparse set of pivot->all-nodes terms (global structure) so we avoid O(n^2).

The hot inner SGD pass is JIT-compiled with numba (_sgd_iteration); the term
shuffle stays on the numpy Generator so results are identical to the plain
Python solver, seed for seed.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math

import numpy as np
from numba import njit

from app.layout.port_graph import PortGraph


@dataclass(slots=True, frozen=True)
class SgdParams:
    iterations: int = 30
    # Sparse pivot->all stress terms give the 2D "Bandage" spread (global
    # structure). Keep them on.
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
# SGD (sequential, annealed) — this is the solver whose 2D "Bandage" character
# was signed off. Do not swap it for a fully-converged stress solver (SMACOF):
# converging harder straightens chain-like graphs into a line, which is exactly
# the look we do NOT want. The under-converged annealed SGD keeps the open-loop
# 2D spread.
# ---------------------------------------------------------------------------
@njit(cache=True)
def _sgd_iteration(
    pos: np.ndarray,
    I: np.ndarray,
    J: np.ndarray,
    D: np.ndarray,
    W: np.ndarray,
    order: np.ndarray,
    eta: float,
) -> None:
    """One SGD pass over the stress terms in `order` (JIT-compiled)."""
    for idx in range(order.shape[0]):
        k = order[idx]
        i = I[k]
        j = J[k]
        d = D[k]
        mu = W[k] * eta
        if mu > 1.0:
            mu = 1.0
        dx = pos[i, 0] - pos[j, 0]
        dy = pos[i, 1] - pos[j, 1]
        mag = math.sqrt(dx * dx + dy * dy)
        if mag < 1e-9:
            dx = 1e-6
            dy = 0.0
            mag = 1e-6
        r = 0.5 * mu * (mag - d) / mag
        rx = r * dx
        ry = r * dy
        pos[i, 0] -= rx
        pos[i, 1] -= ry
        pos[j, 0] += rx
        pos[j, 1] += ry


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
    # The per-iteration term order is still shuffled with the numpy Generator
    # (so results are identical to the pure-Python solver, seed for seed); only
    # the hot inner pass is JIT-compiled.
    T = len(I)
    if T == 0:
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

    order = np.arange(T)
    for it in range(iterations):
        rng.shuffle(order)
        _sgd_iteration(pos, I, J, D, W, order, float(etas[it]))


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


def _convex_hull(points: np.ndarray) -> np.ndarray:
    """Andrew's monotone chain convex hull. Returns hull vertices in CCW order
    (no repeated closing point); handles degenerate (<3 point) inputs."""
    pts = sorted(set(map(tuple, points.tolist())))
    if len(pts) < 3:
        return np.asarray(pts, dtype=np.float64)

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for pt in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], pt) <= 0:
            lower.pop()
        lower.append(pt)
    upper: list[tuple[float, float]] = []
    for pt in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], pt) <= 0:
            upper.pop()
        upper.append(pt)
    return np.asarray(lower[:-1] + upper[:-1], dtype=np.float64)


def _bbox_wh(hull: np.ndarray, angle: float) -> tuple[float, float]:
    c, s = math.cos(-angle), math.sin(-angle)
    rx = hull[:, 0] * c - hull[:, 1] * s
    ry = hull[:, 0] * s + hull[:, 1] * c
    return float(rx.max() - rx.min()), float(ry.max() - ry.min())


# Laid perfectly flat, very elongated components all line up into one monotonous
# straight row when shelved. Anything thinner than this aspect gets a small random
# tilt so the picture reads as organic bars, not a single line. The tilt inflates
# the packed box a little — traded deliberately for looks.
_THIN_ASPECT = 5.0
_TILT_MIN = math.radians(12.0)
_TILT_MAX = math.radians(24.0)


def _min_area_rotation(points: np.ndarray) -> float:
    """Angle that rotates the point cloud so its axis-aligned bounding box has
    *minimum area*. By the Freeman-Shapira "rotating calipers" theorem, the
    minimum-area bounding rectangle of a convex polygon has one side collinear
    with one of the polygon's edges, so it suffices to test the axis angle of
    each hull edge and keep the tightest. A thin chain therefore ends up lying
    flat as a thin bar (not a diagonal sliver), which is what lets the shelf
    packer stack components with little wasted space.
    """
    hull = _convex_hull(points)
    if len(hull) < 3:
        # A single point (no rotation matters) or a segment: align it with the
        # x axis so it becomes a flat bar.
        if len(hull) == 2:
            d = hull[1] - hull[0]
            return math.atan2(float(d[1]), float(d[0]))
        return 0.0

    best_angle = 0.0
    best_area = math.inf
    nh = len(hull)
    for k in range(nh):
        edge = hull[(k + 1) % nh] - hull[k]
        theta = math.atan2(float(edge[1]), float(edge[0]))
        w, h = _bbox_wh(hull, theta)
        area = w * h
        if area < best_area:
            best_area = area
            best_angle = theta
    return best_angle


def _split_free_rect(
    free: tuple[float, float, float, float], used: tuple[float, float, float, float]
) -> list[tuple[float, float, float, float]]:
    """MaxRects split: cut a free rect around a just-placed rect, returning the (up
    to 4) leftover free rects. Non-overlapping frees pass through unchanged; caller
    prunes the degenerate pieces."""
    fx, fy, fw, fh = free
    ux, uy, uw, uh = used
    if not (ux < fx + fw and ux + uw > fx and uy < fy + fh and uy + uh > fy):
        return [free]
    out: list[tuple[float, float, float, float]] = []
    if ux > fx:
        out.append((fx, fy, ux - fx, fh))
    if ux + uw < fx + fw:
        out.append((ux + uw, fy, fx + fw - (ux + uw), fh))
    if uy > fy:
        out.append((fx, fy, fw, uy - fy))
    if uy + uh < fy + fh:
        out.append((fx, uy + uh, fw, fy + fh - (uy + uh)))
    return out


def _prune_contained(
    rects: list[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    """Drop degenerate and fully-contained free rects (keeps the free list small)."""
    out: list[tuple[float, float, float, float]] = []
    for i, a in enumerate(rects):
        ax, ay, aw, ah = a
        if aw <= 1e-9 or ah <= 1e-9:
            continue
        contained = False
        for j, b in enumerate(rects):
            if i == j:
                continue
            bx, by, bw, bh = b
            if (
                ax >= bx - 1e-9
                and ay >= by - 1e-9
                and ax + aw <= bx + bw + 1e-9
                and ay + ah <= by + bh + 1e-9
                and (bw * bh > aw * ah or (bw * bh == aw * ah and j < i))
            ):
                contained = True
                break
        if not contained:
            out.append(a)
    return out


def _corner_pack(
    boxes: list[tuple[float, float]], pad: float
) -> list[tuple[float, float, bool]]:
    """Pack component boxes into a roughly square page by growing out from one
    corner: place the largest-area box first at the origin, then each next-largest
    box in whichever free spot sits closest to that corner (smallest x+y, ties to
    the topmost then leftmost). Big components cluster near the corner and smaller
    ones tuck into the gaps they leave — a looser, less regimented look than shelved
    rows, while staying overlap-free (free space is tracked as MaxRects rectangles).

    `pad` is baked into each box's trailing margin so packed components never touch.
    The square container starts at the ideal (100%-efficient) side and grows
    geometrically until every box fits, so the page stays close to 1:1.

    Returns (ox, oy, rotated) placements, one per input box, in input order; rotated
    is always False (orientation is decided upstream) but kept for a uniform caller.
    """
    n = len(boxes)
    if n == 0:
        return []
    padded = [(w + pad, h + pad) for w, h in boxes]
    order = sorted(range(n), key=lambda i: -padded[i][0] * padded[i][1])
    side = math.sqrt(sum(w * h for w, h in padded)) or 1.0

    placements: list[tuple[float, float, bool]] = [(0.0, 0.0, False)] * n
    for _ in range(40):  # bounded growth retries
        free: list[tuple[float, float, float, float]] = [(0.0, 0.0, side, side)]
        placed: list[tuple[float, float, bool]] = [(0.0, 0.0, False)] * n
        ok = True
        for i in order:
            w, h = padded[i]
            best_key: tuple[float, float, float] | None = None
            best_xy = (0.0, 0.0)
            for fx, fy, fw, fh in free:
                if w <= fw + 1e-9 and h <= fh + 1e-9:
                    key = (fx + fy, fy, fx)  # closest to the origin corner
                    if best_key is None or key < best_key:
                        best_key = key
                        best_xy = (fx, fy)
            if best_key is None:
                ok = False
                break
            fx, fy = best_xy
            placed[i] = (fx, fy, False)
            used = (fx, fy, w, h)
            next_free: list[tuple[float, float, float, float]] = []
            for r in free:
                next_free.extend(_split_free_rect(r, used))
            free = _prune_contained(next_free)
        if ok:
            placements = placed
            break
        side *= 1.15
    return placements


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
    # Separate stream for the cosmetic thin-box tilt so it never perturbs the
    # solver's RNG consumption (which must stay byte-identical, seed for seed).
    tilt_rng = np.random.default_rng([p.seed, 1])

    comp_local: list[tuple[list[int], np.ndarray]] = []
    boxes: list[tuple[float, float]] = []
    for comp in comps:
        pos = _layout_component(comp, adj, p, rng)
        # Rigidly reorient to the component's tightest (minimum-area) bounding box,
        # then flip to landscape so it becomes a flat horizontal bar. Both are rigid
        # isometries (rotation, then an axis swap = reflection): every pairwise
        # distance is preserved, so the SGD shape is untouched — only its pose on
        # the page changes. Flat bars are what the corner packer tiles tightly.
        angle = _min_area_rotation(pos)
        if angle != 0.0:
            c, s = math.cos(-angle), math.sin(-angle)
            pos = np.stack([pos[:, 0] * c - pos[:, 1] * s, pos[:, 0] * s + pos[:, 1] * c], axis=1)
        pos = pos - pos.min(axis=0)
        w = float(pos[:, 0].max()) if len(pos) else 0.0
        h = float(pos[:, 1].max()) if len(pos) else 0.0
        if h > w:  # make it landscape (w >= h) by swapping axes
            pos = pos[:, ::-1].copy()
            w, h = h, w
        # Cosmetic tilt for very thin/linear components so a row of them doesn't
        # read as one long straight line. Still a rigid rotation (SGD shape intact);
        # it just grows the bbox the packer sees, which stays overlap-free.
        if h > 1e-9 and w / h >= _THIN_ASPECT:
            t = (1.0 if tilt_rng.random() < 0.5 else -1.0) * tilt_rng.uniform(_TILT_MIN, _TILT_MAX)
            c, s = math.cos(-t), math.sin(-t)
            pos = np.stack([pos[:, 0] * c - pos[:, 1] * s, pos[:, 0] * s + pos[:, 1] * c], axis=1)
            pos = pos - pos.min(axis=0)
            w = float(pos[:, 0].max())
            h = float(pos[:, 1].max())
        comp_local.append((comp, pos))
        boxes.append((w, h))

    # Inter-component gap. Ribbons have real width (up to ~12 world units) and can
    # bulge past the node bounding box, so a tiny gap lets neighbours' ribbons touch
    # even though the node boxes don't. Scale the gap to the graph (a fraction of the
    # largest component) with the fixed pad as a floor.
    max_dim = max((max(w, h) for w, h in boxes), default=0.0)
    pad = max(p.component_pad, 0.04 * max_dim)
    placements = _corner_pack(boxes, pad)

    out: dict[str, tuple[float, float]] = {}
    for (comp, pos), (ox, oy, _rot) in zip(comp_local, placements):
        for local_i, g in enumerate(comp):
            out[pg.nodes[g]] = (float(pos[local_i, 0]) + ox, float(pos[local_i, 1]) + oy)

    # Anchor the biggest component (packed at the origin corner) to the *top*-left.
    # The view has y-up (deck OrthographicView flipY:false), so mirror y about the
    # page top. A global reflection preserves every distance — solver shape intact.
    if out:
        y_max = max(y for _x, y in out.values())
        out = {nid: (x, y_max - y) for nid, (x, y) in out.items()}
    return out

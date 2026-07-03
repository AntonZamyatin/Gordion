# backend/app/services/ribbon.py
"""Assemble ribbon geometry (a Scene) from a laid-out port graph.

Each contig becomes one 2-point ribbon (IN -> OUT) whose width encodes coverage
and color encodes its connected component. Core links become thin link segments.
This is the render-facing geometry; the CoreGraph stays topology-only.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from app.domain.graph import CoreGraph
from app.layout.port_graph import PortGraph
from app.services.scene_codec import Scene

# tab20-style categorical palette (RGB), cycled by component id.
_PALETTE: list[tuple[int, int, int]] = [
    (31, 119, 180), (174, 199, 232), (255, 127, 14), (255, 187, 120),
    (44, 160, 44), (152, 223, 138), (214, 39, 40), (255, 152, 150),
    (148, 103, 189), (197, 176, 213), (140, 86, 75), (196, 156, 148),
    (227, 119, 194), (247, 182, 210), (127, 127, 127), (199, 199, 199),
    (188, 189, 34), (219, 219, 141), (23, 190, 207), (158, 218, 229),
]


@dataclass(slots=True, frozen=True)
class RibbonStyle:
    width_min: float = 1.0
    width_max: float = 12.0
    width_scale: float = 1.5


def width_from_coverage(cov: float | None, style: RibbonStyle) -> float:
    if cov is None or cov <= 0:
        return 2.0
    return max(style.width_min, min(style.width_max, 1.0 + style.width_scale * math.sqrt(cov)))


def build_scene(
    core: CoreGraph,
    pg: PortGraph,
    positions: dict[str, tuple[float, float]],
    *,
    source: str,
    style: RibbonStyle | None = None,
) -> Scene:
    style = style or RibbonStyle()
    comps = core.get_components()

    n = len(pg.contigs)
    contig_positions = np.empty(n * 4, dtype=np.float32)
    contig_width = np.empty(n, dtype=np.float32)
    contig_color = np.empty(n * 4, dtype=np.uint8)
    id_table: list[str] = []
    # port node id -> (contig index, side); side 0=IN, 1=OUT.
    port_ref: dict[str, tuple[int, int]] = {}

    for i, (cid, (in_id, out_id)) in enumerate(pg.contigs.items()):
        x0, y0 = positions[in_id]
        x1, y1 = positions[out_id]
        contig_positions[i * 4 : i * 4 + 4] = (x0, y0, x1, y1)
        contig_width[i] = width_from_coverage(pg.meta[cid]["coverage"], style)
        r, g, b = _PALETTE[comps.node_to_cid[cid] % len(_PALETTE)]
        contig_color[i * 4 : i * 4 + 4] = (r, g, b, 255)
        id_table.append(cid)
        port_ref[in_id] = (i, 0)
        port_ref[out_id] = (i, 1)

    link_xy: list[float] = []
    link_ep: list[int] = []
    for e in pg.edges:
        if e.kind != "EXTERNAL":
            continue
        x0, y0 = positions[e.u]
        x1, y1 = positions[e.v]
        link_xy += [x0, y0, x1, y1]
        ia, sa = port_ref[e.u]
        ib, sb = port_ref[e.v]
        link_ep += [ia, sa, ib, sb]
    link_positions = np.asarray(link_xy, dtype=np.float32)
    link_endpoints = np.asarray(link_ep, dtype=np.uint32)

    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    bbox = (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 0.0, 0.0)

    return Scene(
        source=source,
        contig_positions=contig_positions,
        contig_width=contig_width,
        contig_color=contig_color,
        link_positions=link_positions,
        id_table=id_table,
        bbox=bbox,
        link_endpoints=link_endpoints,
    )

#!/usr/bin/env python
"""Phase 2 spike driver: GFA -> port graph -> 2D SGD -> PNG + scene JSON.

Renders a matplotlib PNG (for quick eyeballing of layout quality) and writes a
scene JSON that the deck.gl spike can load with ?scene=/scene.json.

Usage:
    .venv/bin/python spikes/layout-sgd/run_layout.py backend/data/example3.gfa
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

from app.parsers.gfa import parse_gfa
from app.layout.port_graph import build_port_graph, PortGraphParams
from app.layout.engine_sgd import layout_port_graph, SgdParams

TAB20 = plt.get_cmap("tab20")


def width_from_coverage(cov: float | None) -> float:
    if cov is None or cov <= 0:
        return 2.0
    return max(1.0, min(12.0, 1.0 + 1.5 * math.sqrt(cov)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("gfa", type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "out")
    ap.add_argument(
        "--scene-out",
        type=Path,
        default=REPO / "spikes" / "deckgl-ribbons" / "public" / "scene.json",
    )
    ap.add_argument("--iterations", type=int, default=30)
    ap.add_argument("--pivots", type=int, default=50)
    ap.add_argument("--length-scale", type=float, default=0.6)
    args = ap.parse_args()

    t0 = time.perf_counter()
    core = parse_gfa(args.gfa)
    t_parse = time.perf_counter() - t0

    n_nodes = len(core.nodes)
    n_edges = len(core.edges)
    comps = core.get_components()
    n_comps = len(comps.summaries)

    pg = build_port_graph(core, PortGraphParams(length_scale=args.length_scale))

    t1 = time.perf_counter()
    pos = layout_port_graph(
        pg, SgdParams(iterations=args.iterations, n_pivots=args.pivots)
    )
    t_layout = time.perf_counter() - t1

    # --- assemble ribbons + links ---
    ribbon_segs: list[list[tuple[float, float]]] = []
    ribbon_widths: list[float] = []
    ribbon_colors: list[tuple[float, float, float, float]] = []

    contig_pos: list[float] = []   # flat inX,inY,outX,outY
    contig_w: list[float] = []
    contig_rgba: list[int] = []

    for cid, (in_id, out_id) in pg.contigs.items():
        x0, y0 = pos[in_id]
        x1, y1 = pos[out_id]
        w = width_from_coverage(pg.meta[cid]["coverage"])
        c = TAB20(comps.node_to_cid[cid] % 20)
        ribbon_segs.append([(x0, y0), (x1, y1)])
        ribbon_widths.append(w)
        ribbon_colors.append(c)
        contig_pos += [x0, y0, x1, y1]
        contig_w.append(w)
        contig_rgba += [int(c[0] * 255), int(c[1] * 255), int(c[2] * 255), 255]

    link_segs: list[list[tuple[float, float]]] = []
    link_pos: list[float] = []
    for e in pg.edges:
        if e.kind != "EXTERNAL":
            continue
        x0, y0 = pos[e.u]
        x1, y1 = pos[e.v]
        link_segs.append([(x0, y0), (x1, y1)])
        link_pos += [x0, y0, x1, y1]

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    bbox = [min(xs), min(ys), max(xs), max(ys)]
    span_x = bbox[2] - bbox[0]
    span_y = bbox[3] - bbox[1]

    # --- PNG ---
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.gfa.stem
    fig, ax = plt.subplots(figsize=(16, 16), dpi=100)
    ax.set_facecolor("#0b0e14")
    if link_segs:
        ax.add_collection(
            LineCollection(link_segs, colors="#3a4150", linewidths=0.4, zorder=1)
        )
    ax.add_collection(
        LineCollection(
            ribbon_segs,
            colors=ribbon_colors,
            linewidths=[w * 0.6 for w in ribbon_widths],
            capstyle="round",
            zorder=2,
        )
    )
    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_title(
        f"{stem}: {n_nodes} contigs, {n_edges} links, {n_comps} components  "
        f"(layout {t_layout:.2f}s)",
        color="#d7dae0",
    )
    ax.tick_params(colors="#7a828e")
    png_path = args.out / f"{stem}_sgd.png"
    fig.savefig(png_path, facecolor="#0b0e14", bbox_inches="tight")
    plt.close(fig)

    # --- scene JSON for deck.gl spike ---
    scene = {
        "source": stem,
        "contigCount": len(contig_w),
        "contigs": {"positions": contig_pos, "width": contig_w, "color": contig_rgba},
        "links": {"positions": link_pos},
        "bbox": bbox,
    }
    args.scene_out.parent.mkdir(parents=True, exist_ok=True)
    args.scene_out.write_text(json.dumps(scene))

    print(f"parsed:   {n_nodes} contigs, {n_edges} links, {n_comps} components")
    print(f"parse:    {t_parse:.2f}s   layout: {t_layout:.2f}s")
    print(f"bbox span: {span_x:.1f} x {span_y:.1f}  (aspect {span_x / max(span_y, 1e-9):.2f})")
    print(f"png:      {png_path}")
    print(f"scene:    {args.scene_out}")


if __name__ == "__main__":
    main()

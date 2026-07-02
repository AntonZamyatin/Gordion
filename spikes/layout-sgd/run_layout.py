#!/usr/bin/env python
"""Phase 2/3 spike driver: GFA -> port graph -> 2D SGD -> Scene -> PNG + JSON.

Builds the same Scene the /scene endpoint serves (via app.services.ribbon), then
renders a matplotlib PNG for quick eyeballing and writes a JSON scene for the
deck.gl spike's ?scene= mode. The binary path is exercised by the endpoint +
scripts/check_decode.mjs.

Usage:
    .venv/bin/python spikes/layout-sgd/run_layout.py backend/data/example3.gfa
"""
from __future__ import annotations

import argparse
import json
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
from app.services.ribbon import build_scene


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("gfa", type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "out")
    ap.add_argument(
        "--scene-out",
        type=Path,
        default=REPO / "spikes" / "deckgl-ribbons" / "public" / "scene.json",
    )
    ap.add_argument("--iterations", type=int, default=60)
    ap.add_argument("--pivots", type=int, default=0)
    ap.add_argument("--length-scale", type=float, default=0.6)
    args = ap.parse_args()

    t0 = time.perf_counter()
    core = parse_gfa(args.gfa)
    t_parse = time.perf_counter() - t0

    n_nodes = len(core.nodes)
    n_edges = len(core.edges)
    n_comps = len(core.get_components().summaries)

    pg = build_port_graph(core, PortGraphParams(length_scale=args.length_scale))
    t1 = time.perf_counter()
    pos = layout_port_graph(pg, SgdParams(iterations=args.iterations, n_pivots=args.pivots))
    t_layout = time.perf_counter() - t1

    scene = build_scene(core, pg, pos, source=args.gfa.stem)

    # reshape flat columns for rendering
    cpos = scene.contig_positions.reshape(-1, 2, 2)
    ccol = scene.contig_color.reshape(-1, 4) / 255.0
    lpos = scene.link_positions.reshape(-1, 2, 2) if scene.link_positions.size else np.empty((0, 2, 2))
    bbox = scene.bbox
    span_x, span_y = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # --- PNG ---
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.gfa.stem
    fig, ax = plt.subplots(figsize=(16, 16), dpi=100)
    ax.set_facecolor("#0b0e14")
    if len(lpos):
        ax.add_collection(LineCollection(lpos, colors="#3a4150", linewidths=0.4, zorder=1))
    ax.add_collection(
        LineCollection(
            cpos,
            colors=ccol,
            linewidths=(scene.contig_width * 0.6).tolist(),
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

    # --- JSON scene for the deck.gl spike (?scene=) ---
    scene_json = {
        "source": scene.source,
        "contigCount": scene.contig_count,
        "contigs": {
            "positions": scene.contig_positions.tolist(),
            "width": scene.contig_width.tolist(),
            "color": scene.contig_color.tolist(),
        },
        "links": {"positions": scene.link_positions.tolist()},
        "bbox": list(bbox),
    }
    args.scene_out.parent.mkdir(parents=True, exist_ok=True)
    args.scene_out.write_text(json.dumps(scene_json))

    print(f"parsed:   {n_nodes} contigs, {n_edges} links, {n_comps} components")
    print(f"parse:    {t_parse:.2f}s   layout: {t_layout:.2f}s")
    print(f"bbox span: {span_x:.1f} x {span_y:.1f}  (aspect {span_x / max(span_y, 1e-9):.2f})")
    print(f"png:      {png_path}")
    print(f"scene:    {args.scene_out}")


if __name__ == "__main__":
    main()

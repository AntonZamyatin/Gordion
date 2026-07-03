# backend — context

FastAPI service. Turns a `.gfa` file into a binary **GSC1** scene. Layered so coordinates never
leak into the topology layer. Read the root `../CLAUDE.md` first (esp. the golden rules).

## Pipeline (the one path that matters)

```
parse_gfa(path)                     app/parsers/gfa.py        GFA v1 → CoreGraph (topology only)
  → build_port_graph(core, params)  app/layout/port_graph.py  2 nodes/contig (IN,OUT) + edges
  → layout_port_graph(pg, SgdParams)app/layout/engine_sgd.py  2D SGD → {port_id: (x,y)}
  → build_scene(core, pg, pos, ...) app/services/ribbon.py    → Scene (ribbon geometry + colors)
  → encode_scene(scene)             app/services/scene_codec.py → bytes (GSC1)
```

`app/services/scene_service.py` is the glue (`scene_for_session`, `scene_bytes_for_session`,
`compute_layout`); `app/services/session_store.py` caches the port graph + computed positions per
session so repeat scene fetches don't recompute the layout (`recompute=true` forces it).

## Module map

- `app/main.py` — FastAPI app; CORS allows any localhost port; exposes `X-Scene-Source`.
- `app/api/routes_graph.py` — the real API (prefix `/graphs`):
  - `GET  /graphs/datasets` → every `data/*.gfa` as `{name, sizeBytes}` (name = stem, sans
    `.gfa`) — lets the frontend's Open-dataset list stay in sync with whatever files exist,
    nothing hardcoded on either side.
  - `POST /graphs/load?name=<n>` → parse `data/<n>.gfa`, create session, return id + counts.
    `name` is validated `^[A-Za-z0-9_.-]+$` (dots/hyphens allowed for real filenames like
    `hg002_hic.hic.hap1.p_ctg`; no `/`, so `DATA_DIR / f"{name}.gfa"` can never escape `data/`).
  - `GET  /graphs/{id}/scene[?recompute=true]` → binary GSC1 (`application/octet-stream`).
  - `GET  /graphs/{id}/components` → component summaries.
- `app/api/routes_scene.py` — stateless `GET /scene/{name}` (fresh layout per request, for spikes).
- `app/domain/` — `graph.py` (`CoreGraph`: nodes, edges, ports; topology only),
  `components.py` (connected components), `errors.py` (`GraphError` subclasses — must stay imported
  in `graph.py`), `attrs.py`, `patch.py`.
- `app/layout/port_graph.py` — `PortGraph`, `PortEdge(u,v,kind,target)`, `PortGraphParams`.
  Internal edge target = `min_len + length_scale*sqrt(bp)`; external edges from GFA links.
- `app/layout/engine_sgd.py` — **the layout solver. Do not swap it.** Sequential annealed SGD,
  per-component, diameter-backbone linear seed + sparse maxmin-pivot Dijkstra terms. Inner pass
  `_sgd_iteration(...)` is `@njit`. `SgdParams(iterations=30, n_pivots=50, seed=0)` — pivots ON.
  Components are then arranged (not re-laid-out); every step below is a rigid isometry
  (rotation/reflection/translation), so intra-component distances — the protected solver output —
  never change. Safe to retune. Steps: (1) `_min_area_rotation` (rotating calipers over
  `_convex_hull`) rotates each component to its *tightest* (minimum-area) box, then it's flipped to
  landscape so a chain lies flat as a thin bar. (2) A cosmetic tilt (`_THIN_ASPECT`/`_TILT_MIN`/
  `_TILT_MAX`) rotates very elongated components by a small random angle so a tiling of them doesn't
  read as one long straight line — drawn from a *separate* RNG (`tilt_rng`) so the solver's RNG
  stream stays byte-identical. Note: only whole components are tilted; thin stretches *inside* one
  component can't be rotated without reshaping it (forbidden). (3) `_corner_pack` tiles the boxes
  into a roughly square page, largest-area first, each placed in the free rect closest to the origin
  corner (MaxRects free-rect tracking via `_split_free_rect`/`_prune_contained`) — big components
  cluster at the corner, smaller ones tuck into the gaps. (4) The gap between components is scaled to
  the graph (`0.04 * max component dim`, `component_pad` floor) because ribbons have real width
  (~12 world units) and bulge past the node box — too small a gap and neighbours' ribbons overlap
  even though the node boxes don't. (5) Finally y is mirrored so the biggest component sits at the
  *top*-left (view is y-up).
- `app/services/ribbon.py` — `build_scene(...)`; `_PALETTE` (tab20), `width_from_coverage`.
- `app/services/scene_codec.py` — `Scene` dataclass, `encode_scene`/`decode_scene`, `MAGIC=b"GSC1"`.
  Columns are f32/u32/u8; `linkEndpoints` (u32) carries each link's `(contig,side)` refs so the client
  can re-derive link geometry from edited ports. **Mirror any format change in
  `frontend/src/lib/sceneCodec.ts`.** See `docs/architecture.md`.
- `app/models/schemas.py` — Pydantic DTOs (JSON responses like components). Scene is binary, not here.

## Run & test

```bash
bash backend/run_back.sh            # uvicorn on :8000 (uses repo-root .venv, py3.12)
.venv/bin/python -m pytest backend  # 30 tests (parser, components, port graph, SGD, codec, service)
```

## Retired (do not resurrect)

RenderGraph trio, Sigma exporters, `engine_igraph/sfdp/circle`, `layout_service`, `position_store`,
`pack_*`, python-igraph. The pipeline above replaced all of it.
# Architecture

End-to-end reference for how a `.gfa` file becomes pixels. For directory-scoped detail see
`backend/CLAUDE.md` and `frontend/CLAUDE.md`; for the "why", see `deckgl-migration-plan.md`.

## The pipeline

```
        BACKEND (Python / FastAPI)                          FRONTEND (React / deck.gl)
        --------------------------                          --------------------------
  .gfa ─▶ parse_gfa ─▶ CoreGraph (topology only)
              │
              ▼
        build_port_graph  ── 2 nodes per contig: IN + OUT ports
              │             internal edge target ∝ sqrt(bp); external edges = GFA links
              ▼
        layout_port_graph ── 2D SGD stress min → {port_id: (x, y)}
              │
              ▼
        build_scene ─────── ribbon geometry: 1 path/contig, width∝coverage, color/component
              │
              ▼
        encode_scene ────── GSC1 bytes ──HTTP octet-stream──▶ decodeScene ─▶ Scene (typed arrays)
                                                                    │
                                                                    ▼
                                                              buildLayers ─▶ PathLayer(s)
                                                                    │
                                                                    ▼
                                                              OrthographicView (GPU)
```

Sessions: `POST /graphs/load` parses and caches a `GraphSession` (topology + port graph + computed
positions). `GET /graphs/{id}/scene` returns the cached layout as GSC1; `?recompute=true` re-runs
SGD. The layout is the expensive step, so it is cached, not recomputed per fetch.

## Why a port graph

A contig is not a point — it has two ends. Modeling each contig as an **IN port** and an **OUT port**
(2 layout nodes) lets the solver place the two ends independently, so contig length (bp) can be
encoded as the target distance of the internal IN↔OUT edge, and links attach to the correct end.
This is a ~50× smaller graph than the old per-pixel "render graph", so layout is both faster and
cleaner. Ribbon curvature between the two ports is a render-time concern, not extra layout nodes.

## Why this specific SGD solver (and don't touch it)

Force-directed layouts (FR/SFDP) curl chain-like genome graphs into knots. **2D SGD stress
minimization** — placing nodes so geometric distance matches graph distance — unfolds them into the
straight backbones of the BandageNG look. The signed-off aesthetic depends on the solver being
**sequential (Gauss-Seidel), annealed, under-converged, with sparse pivot terms ON**
(`iterations=30, n_pivots=50`). Converging harder (SMACOF / full majorization) straightens
everything into a single line; degree-averaged Jacobi collapses it. Both were tried and both
regressed the look. The numba `@njit` inner pass is bit-identical to the reference Python solver
(the RNG shuffle deliberately stays on the numpy Generator). **Treat the current behavior as a
spec, not a starting point.**

## GSC1 binary scene format

JSON does not survive 10^5–10^6 elements and deck.gl wants typed arrays anyway, so the scene is a
columnar binary blob. **The encoder (`backend/app/services/scene_codec.py`) and decoder
(`frontend/src/lib/sceneCodec.ts`) are a matched pair — change both together.**

Wire layout:
```
[4]  magic          = b"GSC1"
[4]  uint32 LE       = header length H
[H]  UTF-8 JSON      = manifest
[..] body            = columns concatenated in manifest order
```

Manifest:
```json
{
  "version": 1,
  "source": "<name>",
  "contigCount": N,
  "linkCount": L,
  "columns": {
    "<name>": {"dtype": "f32"|"u8", "size": <components>, "offset": <byte>, "length": <elements>}
  },
  "idTable": ["<core_id_0>", ...],       // contig index → core node id (picking/display)
  "bbox": [minX, minY, maxX, maxY]
}
```

Columns (emitted in this order — **all 4-byte columns (f32/u32) before u8** so every wide offset is
4-byte aligned):

| column            | dtype | size | meaning                                         |
|-------------------|-------|------|-------------------------------------------------|
| `contigPositions` | f32   | 4    | `[inX,inY,outX,outY]` per contig (len N·4)      |
| `contigWidth`     | f32   | 1    | ribbon width per contig (len N)                 |
| `linkPositions`   | f32   | 4    | `[x0,y0,x1,y1]` per link (len L·4), baked        |
| `linkEndpoints`   | u32   | 4    | `[contigA,sideA,contigB,sideB]` per link (side 0=IN,1=OUT) |
| `contigColor`     | u8    | 4    | RGBA per contig (len N·4)                        |

The decoder **copies** each column into a fresh typed array (alignment-safe); zero-copy is a later
optimization. Contig index `i` is the universal join key: it indexes every column and `idTable`,
and is exactly what deck.gl picking returns (one contig = one path). `linkEndpoints` lets the client
**re-derive link geometry from live port positions** — so when the user drags a port, the links
attached to it follow (the baked `linkPositions` is only the initial/fallback geometry). Older
encoders may omit `linkEndpoints`; the decoder treats it as optional.

## Conventions & hazards

- Coordinates never enter `domain/` — that layer is topology only.
- deck.gl uses `OrthographicView({flipY:false})`; the frontend fits `scene.bbox` on load.
- `/DATA` is NTFS (ntfs3) and has corrupted `.git` before ("Stale file handle"). See
  `~/gordion-git-recovery.md`; moving to ext4 is recommended.
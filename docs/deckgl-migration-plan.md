# Gordion — deck.gl Migration Plan

Status: completed (2026-07-02) — all phases done; layout uses sequential annealed 2D SGD (numba-JIT'd), not the vectorized/SMACOF variants explored mid-migration.
Author: design session, 2026-07-01
Scope: re-platform the **layout + rendering pipeline** around scale and true ribbon rendering. The backend domain architecture (CoreGraph, layering, PositionStore, config) is kept.

---

## 1. Goals and non-goals

### Goals
- Render contigs as **first-class ribbons** (length ∝ bp, width ∝ coverage), Bandage/BandageNG style.
- Scale to **10^5–10^6 elements** with smooth pan/zoom and reliable picking.
- Produce **clean, unfolded (linear, rotation-free) layouts** for genome graphs.
- Remove the pseudo-vertex/RenderGraph inflation that currently drives both the layout-quality and layout-performance problems.

### Non-goals (this migration)
- Topology editing / node dragging (roadmap, but deferred; we accept deck.gl is less ergonomic here and will address it separately).
- Multi-user / persistence backends (session stays in-memory; add save/load later).
- 3D.

---

## 2. The central architectural change

**Today:** `CoreGraph → RenderGraph (each node expanded into IN→spacer×k→OUT, up to ~50×) → layout runs on the inflated render graph → export per-render-node/edge to Sigma.`

**Target:** `CoreGraph → PortGraph (2 nodes per contig: its IN and OUT port) → 2D SGD layout on the port graph → ribbon geometry derived from port positions → binary scene → deck.gl.`

Why the **port graph** (2 nodes/contig) is the right layout representation:
- It is small: 2× contigs, not ~50×. Layout stays tractable at 10^6.
- It preserves the existing port semantics exactly (IN/OUT ends already exist in CoreGraph).
- Each contig gets an **oriented segment** (IN→OUT) — the ribbon's spine — for free.
- **bp drives contig length** naturally: the internal IN↔OUT edge gets a target distance ∝ f(bp) in SGD.
- Links connect ports (OUT_u → IN_v, etc.), so external edges are first-class.

Ribbon curvature (the smooth Bandage look) is a **render-time** concern: subdivide IN→OUT into a few control points for a spline if desired. It is NOT layout nodes. MVP ships straight ribbons `[IN, OUT]`; splines come later without touching layout.

---

## 3. Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Renderer | **deck.gl** (`OrthographicView`, `PathLayer`) | GPU picking + culling + LOD for free at 10^6; `PathLayer` draws width-scaled polylines natively; binary attributes. |
| Layout | **2D SGD** (path/BFS-guided), on the port graph | Domain-correct for genome graphs; unfolds linearly; scales far better than force layout. |
| Layout unit | **PortGraph** (2 ports/contig) | Small, preserves ports, gives ribbon spine + bp-length. |
| Wire format | **Binary typed arrays** (Arrow later) | JSON does not scale to 10^6; deck.gl consumes typed arrays zero-copy. |
| View | deck.gl `OrthographicView` (non-geo, 2D cartesian) | Assembly graphs are abstract 2D, not maps. |
| Frontend state | Introduce **Zustand** store | Selection/hover/session shared across canvas + sidebars. |

Accepted tradeoff: deck.gl is weaker for interactive editing than PixiJS. Editing is deferred; revisit with deck.gl editable patterns or an overlay when it lands.

---

## 4. Binary scene contract

One endpoint returns a scene: a small JSON manifest + a binary body of typed-array columns. Defined once in `scene_codec.py` (backend) and `sceneCodec.ts` (frontend).

### Endpoint
`GET /graphs/{id}/scene?layout=sgd&pack=rows` → `application/octet-stream`

Layout: `[4-byte magic]["GSC1"] [4-byte header length N] [N bytes JSON manifest] [binary body]`

### Manifest (JSON)
```json
{
  "version": 1,
  "contigCount": 123456,
  "linkCount": 130000,
  "columns": {
    "contigPositions": {"dtype":"f32","size":4,"offset":0,"bytes":...},   // [inX,inY,outX,outY]
    "contigWidth":     {"dtype":"f32","size":1,"offset":...,"bytes":...}, // coverage-derived px
    "contigColor":     {"dtype":"u8","size":4,"offset":...,"bytes":...},  // RGBA
    "linkPositions":   {"dtype":"f32","size":4,"offset":...,"bytes":...}  // [x0,y0,x1,y1]
  },
  "idTable": ["contig_id_0","contig_id_1", ...]   // index -> core_node_id
}
```
- `idTable` maps a contig's buffer index → `core_node_id` for picking. (Large graphs: move to a separate string-table column later.)
- Body is the concatenation of columns in manifest order; each column is a contiguous typed array.

### Frontend consumption
Slice the ArrayBuffer into `Float32Array`/`Uint8Array` per manifest and hand deck.gl binary attributes:
```ts
new PathLayer({
  data: { length: contigCount, startIndices, attributes: {
    getPath: { value: contigPositions, size: 2 },      // 2 points/path
    getWidth:{ value: contigWidth, size: 1 },
    getColor:{ value: contigColor, size: 4, normalized: true },
  }},
  _pathType: 'open', widthUnits: 'pixels', pickable: true,
});
```

Arrow is the productionization path (pyarrow ↔ apache-arrow-js) once the plain format is proven; not needed for the spikes.

---

## 5. Backend changes (file by file)

### Keep (unchanged or lightly extended)
- `domain/*` — CoreGraph remains the single source of truth.
- `parsers/gfa.py`
- `config/viz_config.py` — extend with SGD + ribbon + scene params.
- `services/session_store.py`, `layout/position_store.py`
- `layout/engine_base.py` (LayoutEngine protocol), `layout/pack_base.py`, `layout/pack_rows.py` (still needed to pack multiple components).
- `services/layout_service.py` — adapt to layout the **port graph** per component, then pack. Two-level structure is preserved.

### New
- `layout/port_graph.py` — build the 2-port-per-node layout graph from a CoreGraph: nodes = `{contig}:IN`, `{contig}:OUT`; internal edge IN↔OUT with `target ∝ f(bp)`; external edges from CoreGraph links between ports.
- `layout/engine_sgd.py` — `SgdLayoutEngine(LayoutEngine)`: 2D SGD (see §6).
- `services/ribbon.py` — layout positions → per-contig polyline (`[IN, OUT]` for MVP), width from coverage, color from a colormap.
- `services/scene_codec.py` — encode/decode the §4 binary scene.
- `api/routes_scene.py` — `/graphs/{id}/scene`.
- `tests/` — golden files (see §9).

### Retire (after SGD + scene are proven, not before)
- `render/render_graph.py`, `render/render_builder.py`, `render/render_policy.py` (pseudo-vertex expansion).
- `services/export_sigma.py`, `services/export_sigma_render.py`.
- `layout/engine_igraph.py`, `layout/engine_sfdp.py`, `layout/engine_circle.py` (keep a trivial fallback if desired).
- SFDP debug SVG emission and `backend/svg`, `backend/data/sfdp_out_*.svg`.

---

## 6. Layout engine: 2D SGD spec

Reference: Zheng et al., *Graph Drawing by Stochastic Gradient Descent*; PG-SGD (path-guided) for scaling.

Per component (reuse two-level packing):
1. Build port graph; index ports `0..n-1`.
2. Sample node pairs with a target distance:
   - **Edges**: internal edge target `d = a·f(bp)` (f = `sqrt` or clamped linear); external edge target `d = c` (small constant).
   - **Non-adjacent pairs**: sample via BFS layers; target `d = hop_distance · scale` (path-guided sampling avoids all-pairs shortest paths at 10^6).
3. SGD update per sampled pair `(i,j)` with target `d`:
   - `mag = (‖p_i−p_j‖ − d) / 2`, step `μ = min(w·η, 1)`, move `p_i,p_j` toward/away by `μ·mag·unit(p_i−p_j)`.
4. Anneal `η` from `η_max → η_min` over `T` iterations. Fixed RNG seed for determinism.
5. Seed from a diameter-backbone linearization (reuse the logic already written for SFDP) so the first pass starts unfolded.

Implementation: NumPy/numba now; keep the engine swappable so a compiled/GPU kernel can replace the inner loop for the 10^6 end. Validate quality at 10^5 before pushing to 10^6.

Config (`viz_config.py`): `sgd_iterations`, `sgd_eta_max/min`, `bp_length_scale`, `internal_target_fn`, `external_target`, `pair_sample_k`.

---

## 7. Frontend changes

### Keep
- App shell: `app/App.tsx` grid, `TopBar`, `LeftSidebar`, `RightSidebar` (collapsible), CSS grid. This work was sound.

### Replace
- The Sigma canvas cell (`features/graph/GraphCanvas.tsx`, `GraphLoader.tsx`, `HoverCoreNode.tsx`, `SigmaAutoResize.tsx`) → a **`DeckCanvas.tsx`** using `@deck.gl/react` `DeckGL` + `OrthographicView`.
- Remove Sigma/graphology deps once cutover is done.

### New
- `features/graph/DeckCanvas.tsx` — DeckGL host, OrthographicView, layers, hover/click handlers.
- `features/graph/layers.ts` — build `PathLayer` (ribbons), `PathLayer`/`LineLayer` (links) from binary attributes.
- `lib/sceneCodec.ts` — parse the §4 binary scene into typed arrays + idTable.
- `store/useGraphStore.ts` — Zustand: `sessionId`, `hoveredCore`, `selectedCores`, `scene`.

### Deck.gl specifics
- **View**: `new OrthographicView({flipY:false})`; `initialViewState` fit to scene bounds (from manifest bbox).
- **Ribbons**: `PathLayer` — `pickable:true`, `widthUnits:'pixels'`, `widthMinPixels`, `getColor` per contig. Because a contig is ONE path object, **picking returns the whole contig for free** — the `core_node_id` reducer gymnastics disappear.
- **Hover highlight**: `autoHighlight:true` + `highlightColor`, or recolor via `updateTriggers` keyed on `hoveredCore`. No custom hover-ring removal needed.
- **Selection**: `onClick(info)` → `info.index` → `idTable[index]`; `info.srcEvent.shiftKey` for multi-select.
- **Resize**: DeckGL handles container resize natively — the whole ResizeObserver/remount saga is gone.

---

## 8. Phased sequencing (each phase = a commit / small PR)

Work on branch **`deckgl-migration`** off `master`. Master (Sigma) stays runnable until Phase 5 cutover. Spikes live under `/spikes` (throwaway).

### Phase 0 — Baseline & safety
- Commit current WIP.
- Add characterization tests for `parsers/gfa.py` and component detection (golden files on `example*.gfa`).
- Create the branch.
- **Exit:** green tests on the parts we intend to keep; WIP committed.

### Phase 1 — Renderer spike (de-risk deck.gl)
- Standalone Vite page: deck.gl `OrthographicView` + `PathLayer` fed **synthetic** ribbons (~200k paths) from generated typed arrays.
- Verify pan/zoom fps, picking correctness, width scaling, LOD behavior.
- **Exit:** smooth pan/zoom at target scale; click returns the correct path index.

### Phase 2 — Layout spike (de-risk SGD)
- Implement `port_graph.py` + `engine_sgd.py` (NumPy).
- Run on `example*.gfa`; dump coords; render statically in the Phase-1 spike.
- Compare visually to Bandage on the same graphs.
- **Exit:** qualitatively linear/unfolded layouts on the example graphs, including a large one.

### Phase 3 — Binary scene contract
- Implement `scene_codec.py` + `sceneCodec.ts` (§4).
- Wire the spike to a real backend `/scene` on one GFA end-to-end.
- **Exit:** spike renders a real parsed graph from the binary endpoint.

### Phase 4 — Backend rebuild
- `ribbon.py`, `routes_scene.py`; adapt `layout_service.py` to the port graph; register SGD engine.
- Retire RenderGraph, Sigma exporters, old engines, SVG debug.
- **Exit:** `/graphs/{id}/scene` serves all example GFAs; old `/view` removed.

### Phase 5 — Frontend cutover
- `DeckCanvas.tsx`, `layers.ts`, Zustand store; mount in the app shell in place of Sigma.
- Port hover + click/shift-select onto deck.gl picking.
- Remove Sigma/graphology.
- **Exit:** feature parity with today's hover + selection, on real data, in the real UI.

### Phase 6 — Cleanup & docs
- Delete dead modules; consolidate `viz_config`; update README/architecture doc.
- Fold `deckgl-migration` into `master`.
- **Exit:** no references to Sigma/RenderGraph remain; docs current.

---

## 9. Testing strategy
- **Parser golden files** (Phase 0): `example*.gfa` → serialized CoreGraph snapshot (nodes, ports, edges, parsed attrs).
- **Component detection** (Phase 0): membership snapshot per example.
- **SGD determinism** (Phase 2): fixed seed → stable coords hash; bbox within tolerance.
- **Scene codec round-trip** (Phase 3): encode→decode equals input arrays; manifest offsets valid.
- **Ribbon geometry** (Phase 4): contig length ∝ bp, width ∝ coverage within tolerance.

---

## 10. Risks & mitigations
| Risk | Mitigation |
|---|---|
| `PathLayer` width is per-path uniform (no per-vertex taper) | Accept uniform width per contig for MVP — it matches Bandage's per-contig depth encoding anyway; custom layer later if taper wanted. |
| SGD quality/perf at 10^6 | Validate at 10^5 first; keep engine swappable; NumPy→numba→GPU path; path-guided sampling avoids all-pairs SPD. |
| Binary contract churn | Start with plain typed arrays in one codec module; migrate to Arrow once stable. |
| deck.gl editing ergonomics | Editing is out of scope here; revisit with deck.gl editable patterns/overlay. |
| Big-bang regression | Spikes + phasing keep master runnable until Phase 5; branch isolation; golden tests guard kept code. |

---

## 11. What gets deleted at the end
`render/render_graph.py`, `render/render_builder.py`, `render/render_policy.py`, `services/export_sigma.py`, `services/export_sigma_render.py`, `layout/engine_igraph.py`, `layout/engine_sfdp.py` (+ SVG debug), Sigma frontend components, `sigma`/`@react-sigma/core`/`graphology` deps.
```
```
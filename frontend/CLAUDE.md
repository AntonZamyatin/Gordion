# frontend — context

React 19 + Vite + **deck.gl 9** client. Fetches a binary **GSC1** scene from the backend, decodes it
to typed arrays, and renders contigs as GPU ribbons. Read the root `../CLAUDE.md` first.

## Data flow

```
App mounts → useGraphStore.loadGraph(name)
  → api.loadGraph()   POST /graphs/load?name=      → { graphId, counts }
  → api.fetchScene()  GET  /graphs/{id}/scene       → ArrayBuffer
  → sceneCodec.decodeScene(buf) → Scene (typed arrays)   ← MUST match backend scene_codec.py
  → store holds scene + hover/selection state
  → DeckCanvas + layers.ts build PathLayers from the scene's binary attributes
```

## Module map

- `src/app/App.tsx` — app shell; loads `DEFAULT_GRAPH="example3"` on mount (a `loadedRef` guards
  React StrictMode's double-invoke). Imports `./App.css` (case-sensitive path — Linux fs).
- `src/lib/api.ts` — backend client. `BASE_URL="http://localhost:8000"`, `loadGraph`, `fetchScene`,
  `listDatasets` (`GET /graphs/datasets` → `{name, sizeBytes}[]`, drives the Open-dataset list).
- `src/lib/sceneCodec.ts` — **GSC1 decoder; mirror of backend `scene_codec.py`.** Any format change
  must land in both. Returns `Scene` (contigPositions, contigWidth, contigColor, linkPositions,
  idTable, bbox, counts).
- `src/store/useGraphStore.ts` — Zustand store: session/scene, `hoveredIndex`, `selected: Set<number>`,
  `selectionTick`, plus render-time **edits** (never sent to the backend): `portOverrides:
  Map<portKey,[dx,dy]>` (portKey = `contig*2 + side`, side 0=IN/1=OUT) from dragging the nearest port,
  `curveOverrides: Map<contigIndex,number>` (signed fraction of chord length) from the +/- curvature
  keys, and `editVersion`. Also `bulge: BulgeParams` for the live debug panel, and `datasets:
  DatasetInfo[]` for the Open list. Actions: `loadGraph`, `loadDatasets`, `recomputeLayout`,
  `setHovered`, `clickSelect`, `addToSelection` (batch, for box-select), `clearSelection`, `movePort`,
  `nudgeCurvature`, `clearEdits`,
  `setBulge`. Force layout adds `force: ForceParams` (+ `setForce`) and `livePositions:
  Float32Array | null` (+ `setLivePositions`) — the drag-relaxed base buffer; `setForce` and
  `clearEdits`/`loadGraph` clear it. `editCount` counts it as one edit.
- `src/features/graph/DeckCanvas.tsx` — `<DeckGL>` with `OrthographicView({flipY:false})`,
  `key={sessionId}` (remount on new graph), initial view fits `scene.bbox`. `onHover`/`onClick`
  route to the store only when `info.layer?.id === 'ribbons'`. The `base` the ribbon geometry builds on
  is `livePositions ?? scene.contigPositions` (forces never touch the load-time layout). **Drag modes**,
  chosen by modifier in `onDragStart` (all force modes need `force.enabled`): **plain** = neighbourhood
  force drag — pin the whole grabbed vertex (or the whole selection, if the grabbed contig is in one) to
  the cursor and relax its k-hop neighbourhood (`bfsWithin(seeds, dragLayers)`); **Ctrl** = move ONLY the
  nearest port via `movePort` — no forces, no neighbourhood, so the contig reshapes/resizes as its port
  follows the cursor (works regardless of the force master switch); **Shift** = rubber-band box select.
  Force drags call `relaxLocal` + `localBulgeUpdate` per event and publish `livePositions`; when forces are
  off, plain drag also falls back to a single-port `movePort`. A plain click deselects. **Shift selection is
  handled entirely on a separate overlay `<div>`, NOT via deck's drag events** (deck's controller
  swallows background drags, so its `onDrag` never fires on empty canvas). The overlay sits above the
  canvas with `pointerEvents: shiftHeld ? "auto" : "none"`; its pointer handlers draw the pixel-space
  rectangle and, on release, call the DeckGL ref's `pickObjects({x,y,width,height,layerIds:['ribbons']})`
  for a box (or `pickObject` for a shift-click) → `addToSelection`/`clickSelect`. Bulge offsets live in a
  ref (`offsetsVersion` bump re-runs the paths memo); a full recompute runs from an effect only when
  settled (not mid-drag).
- `src/features/graph/forceLayout.ts` — **interactive force layout, applied only while dragging** (no
  layout change on load). Reconstructs the port graph client-side from `scene.contigPositions` (2
  nodes/contig, key = `contig*2+side`, mirrors `portKey`) + `scene.linkEndpoints`. Force model:
  rigid length constraint (each contig is a rigid rod held at its own seed chord length, projected
  back after every force step, so a plain drag rotates/translates a vertex but never resizes it —
  only Ctrl-drag of a port changes a contig's length),
  port spring (pulls a link's two ports to a rest length — `edgeLength`×chord by default, or a
  per-link Ctrl-drag override → tunable junction gaps), junction straightening (per *junction*,
  not per link: contigs are clustered into junctions by union-find over ports, then every incident
  contig's far port is pushed away from the junction's mean outward direction `k·(dI − mean)` — one
  resultant over all its contigs at once, so 2-way junctions go straight and branches fan out evenly
  instead of collapsing; length-independent, no port-distance term), plus a short-range grid
  repulsion. The drag is **local, not O(N)**: `bfsWithin` returns the contigs within k hops of the
  grabbed/selected seeds, `buildLocalSim` compiles that region (contigs + their incident links, via the
  `linkAdjStart`/`linkAdjList` CSR) once per gesture, and `relaxLocal` relaxes only it each event —
  cost O(region + local links), independent of graph size. `relaxLocal` takes a **port-level** `pinned`
  map (portKey → position): those ports are held (a dragged port, or every port of a rigidly-moved
  selection); every other region port relaxes; contigs outside the region are fixed anchors. The curve
  repulsion is localised the same way (`localBulgeUpdate` in ribbonGeometry recomputes offsets for just
  the moved contigs; a full `computeBulgeOffsets` runs only on drag *release*). Output is the same
  `[inX,inY,outX,outY]`-per-contig buffer as the SGD seed, so it drops into `effectivePorts(scene,
  edits, base)` as the `base`. **Nothing is sent to the backend — render-time only, protected SGD solver
  untouched.** Params + master on/off live in the store as `force` (`ForceParams`), tuned from the
  "Debug · forces" panel; a drag publishes a full `livePositions` buffer that shadows the seed until
  reset or a force-param change.
- `src/features/graph/ribbonGeometry.ts` — **render-time geometry** (SGD layout untouched).
  `effectivePorts(scene, edits, base?)` applies port drags to produce the final `[inX,inY,outX,outY]`
  per contig — the single source used for BOTH curves and links; `base` defaults to the SGD seed but the
  force layout passes its relaxed positions in. `computeBulgeOffsets(positions, n, bulge)` reduces each
  contig to a signed perpendicular offset via a grid-based repulsion that only fires for *parallel +
  overlapping* ribbons (bubbles), so straight backbones and crossing ribbons stay put. It runs off the
  *live* ports (memoized per scene+ports+bulge), so the curve repulsion reflows during a force-layout drag.
  `buildRibbonPaths(ports, n, offsets, bulge, curveOverrides)` samples a quadratic Bézier per contig,
  adding each contig's manual `curveOverrides` fraction (×chord length) on top of the auto offset
  before picking the peak; `buildLinkPositions(scene, ports)` re-derives link segments from
  `scene.linkEndpoints` so edges follow dragged ports. Offsets are memoized per
  scene+ports+bulge (so they recompute as the layout moves — the curve repulsion is part of the drag
  simulation); ports/paths/links rebuild on edit (cheap).
- `src/features/graph/layers.ts` — `buildLayers(scene, paths, hoveredIndex, selected, selectionTick)`:
  the ribbon `PathLayer` (curved paths from `ribbonGeometry`, function `getColor`/`getWidth`,
  `updateTriggers`) + a faint link `PathLayer`. One curved path per contig, so picking still returns
  the contig index.
- `src/features/ui/{TopBar,LeftSidebar,RightSidebar}.tsx` — shell chrome. Left = Open-dataset list
  (fetched via `loadDatasets`, not hardcoded — flags files ≥500MB with a size label) + recompute;
  Right = hovered id + selection list + search-by-contig-id.

## Key ideas / gotchas

- **One contig = one pickable path.** deck.gl picking returns the whole contig — no per-vertex
  reducer gymnastics (that was the old Sigma pain, see historical memory `gordion-frontend-notes`).
- deck.gl handles canvas resize natively — no ResizeObserver/remount dance.
- Indices are the join key: `hoveredIndex`/`selected` index into the scene's contig arrays and into
  `idTable` for display.
- CSS inline styles want strings (`inset: "0"`, not `0`); `Deck.parent` cast `as HTMLDivElement`.
- deck.gl is code-split into its own chunk via `vite.config.ts` `manualChunks.deckgl`.

## Run

```bash
cd frontend && npm install && npm run dev   # :5173 (backend must be up on :8000)
npm run build                               # tsc + vite build; ~194KB app + ~608KB deckgl chunk
```
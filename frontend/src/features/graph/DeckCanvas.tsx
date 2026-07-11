import { useEffect, useMemo, useRef, useState } from "react";
import { DeckGL } from "@deck.gl/react";
import { OrthographicView } from "@deck.gl/core";

import { useGraphStore } from "../../store/useGraphStore";
import { buildLayers, type HoverZone } from "./layers";
import {
  computeBulgeOffsets,
  localBulgeUpdate,
  buildBulgeBackground,
  buildRibbonPaths,
  buildLinkPositions,
  effectivePorts,
  portKey,
  PORT_ZONE_FRAC,
  type BulgeBackground,
} from "./ribbonGeometry";
import {
  buildPortGraph,
  bfsWithin,
  buildLocalSim,
  relaxLocal,
  type LocalSim,
} from "./forceLayout";

const VIEW = new OrthographicView({ flipY: false });

// Magnetic capture radius around each port endpoint, as a fraction of the vertex's chord
// length. Larger = port (rotate) zones grab from further away; the central zone shrinks.
const PORT_MAGNET = 0.22;

type DeckPickInfo = {
  index: number;
  layer?: { id: string } | null;
  srcEvent?: MouseEvent;
  coordinate?: number[];
};

// Minimal view of the DeckGL React ref we use for rubber-band picking.
type DeckHandle = {
  pickObject: (o: { x: number; y: number; radius?: number; layerIds?: string[] }) => DeckPickInfo | null;
  pickObjects: (o: { x: number; y: number; width: number; height: number; layerIds?: string[] }) => DeckPickInfo[];
};

type SelectRect = { x0: number; y0: number; x1: number; y1: number };

export function DeckCanvas() {
  const scene = useGraphStore((s) => s.scene);
  const status = useGraphStore((s) => s.status);
  const error = useGraphStore((s) => s.error);
  const sessionId = useGraphStore((s) => s.sessionId);
  const hoveredIndex = useGraphStore((s) => s.hoveredIndex);
  const selected = useGraphStore((s) => s.selected);
  const selectionTick = useGraphStore((s) => s.selectionTick);
  const portOverrides = useGraphStore((s) => s.portOverrides);
  const curveOverrides = useGraphStore((s) => s.curveOverrides);
  const linkRestOverrides = useGraphStore((s) => s.linkRestOverrides);
  const livePositions = useGraphStore((s) => s.livePositions);
  const bulge = useGraphStore((s) => s.bulge);
  const force = useGraphStore((s) => s.force);
  const setHovered = useGraphStore((s) => s.setHovered);
  const clickSelect = useGraphStore((s) => s.clickSelect);
  const addToSelection = useGraphStore((s) => s.addToSelection);
  const clearSelection = useGraphStore((s) => s.clearSelection);
  const movePort = useGraphStore((s) => s.movePort);
  const setLinkRest = useGraphStore((s) => s.setLinkRest);
  const nudgeCurvature = useGraphStore((s) => s.nudgeCurvature);
  const setLivePositions = useGraphStore((s) => s.setLivePositions);

  // Force-drag state (deck's own drag events). "port" = single-port drag (forces off);
  // "cloud" = pinned ports follow the cursor while the local region relaxes.
  const drag = useRef<
    | { mode: "port"; key: number; anchor: number[]; start: [number, number]; viaCtrl: boolean }
    | {
        mode: "cloud";
        anchor: number[];
        sim: LocalSim;
        work: Float32Array;
        pinnedBase: Map<number, [number, number]>;
        moved: number[];
        bg: BulgeBackground; // stationary contigs frozen at drag start (see localBulgeUpdate)
      }
    | null
  >(null);
  const [nodeDragging, setNodeDragging] = useState(false);
  // Which grab zone the cursor is over (for the hover colour cue). Only tracked with forces on.
  const [hoverZone, setHoverZone] = useState<HoverZone | null>(null);

  // Rubber-band selection is handled on an overlay div (deck's controller swallows background
  // drags, so we can't rely on its onDrag for this). deckRef gives us box picking.
  const deckRef = useRef<DeckHandle | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const boxStart = useRef<{ x: number; y: number } | null>(null);
  const [selectRect, setSelectRect] = useState<SelectRect | null>(null);

  // Shift arms the selection overlay; Ctrl arms force-drag mode 2. We track both so we can
  // disable deck's pan (and rotate) for those gestures — otherwise the OrthographicController
  // grabs Ctrl+drag to rotate the view before our onDrag ever runs.
  const [shiftHeld, setShiftHeld] = useState(false);
  const [ctrlHeld, setCtrlHeld] = useState(false);
  useEffect(() => {
    const sync = (e: KeyboardEvent) => {
      setShiftHeld(e.shiftKey);
      setCtrlHeld(e.ctrlKey || e.metaKey);
    };
    window.addEventListener("keydown", sync);
    window.addEventListener("keyup", sync);
    return () => {
      window.removeEventListener("keydown", sync);
      window.removeEventListener("keyup", sync);
    };
  }, []);

  // Port graph (topology) is derived once per scene; the drag/relax paths reuse it.
  const portGraph = useMemo(() => (scene ? buildPortGraph(scene) : null), [scene]);

  // Forces are applied only while dragging, so the base layout is the raw SGD seed (or the
  // last drag's relaxed overlay). No global relax on load.
  const base = useMemo(
    () => livePositions ?? scene?.contigPositions ?? new Float32Array(0),
    [livePositions, scene],
  );

  // Fit the view to the scene; refits on a new session (key below).
  const initialViewState = useMemo(() => {
    if (!scene) return { target: [0, 0, 0] as [number, number, number], zoom: 0 };
    const [minX, minY, maxX, maxY] = scene.bbox;
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const extent = Math.max(maxX - minX, maxY - minY) || 1;
    const viewport = Math.min(window.innerWidth, window.innerHeight) * 0.8;
    return { target: [cx, cy, 0] as [number, number, number], zoom: Math.log2(viewport / extent) };
  }, [scene, sessionId]);

  // Final port positions after user edits — the single source for curves AND links.
  const ports = useMemo(
    () => (scene ? effectivePorts(scene, { portOverrides }, base) : new Float32Array(0)),
    [scene, portOverrides, base],
  );

  // Curve/bulge repulsion offsets, held in a ref so a drag can update them *locally* (only
  // the moved contigs) without a full O(N) recompute. `offsetsVersion` bumps when it changes.
  const offsetsRef = useRef<Float32Array>(new Float32Array(0));
  const [offsetsVersion, setOffsetsVersion] = useState(0);

  useEffect(() => {
    if (!scene) return;
    if (nodeDragging) return; // don't recompute globally mid force-drag
    offsetsRef.current = computeBulgeOffsets(base, scene.contigCount, bulge);
    setOffsetsVersion((v) => v + 1);
  }, [scene, base, bulge, nodeDragging]);

  const paths = useMemo(
    () =>
      scene ? buildRibbonPaths(ports, scene.contigCount, offsetsRef.current, bulge, curveOverrides) : null,
    // offsetsVersion stands in for the mutable offsetsRef contents.
    [scene, ports, offsetsVersion, bulge, curveOverrides],
  );

  const linkPositions = useMemo(
    () => (scene ? buildLinkPositions(scene, ports) : new Float32Array(0)),
    [scene, ports],
  );

  const layers = useMemo(
    () =>
      scene && paths
        ? buildLayers(scene, paths, linkPositions, hoveredIndex, selected, selectionTick, hoverZone)
        : [],
    [scene, paths, linkPositions, hoveredIndex, selected, selectionTick, hoverZone],
  );

  // +/- bends the focused contig's curvature (hovered, else the lone selection).
  const focusRef = useRef<number | null>(null);
  focusRef.current = hoveredIndex ?? (selected.size === 1 ? [...selected][0] : null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const i = focusRef.current;
      if (i == null) return;
      if (e.key === "+" || e.key === "=") nudgeCurvature(i, 1);
      else if (e.key === "-" || e.key === "_") nudgeCurvature(i, -1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nudgeCurvature]);

  const onRibbon = (info: DeckPickInfo): number | null =>
    info.index >= 0 && info.layer?.id === "ribbons" ? info.index : null;

  const nearestSide = (i: number, cx: number, cy: number): number => {
    const dIn = (ports[i * 4] - cx) ** 2 + (ports[i * 4 + 1] - cy) ** 2;
    const dOut = (ports[i * 4 + 2] - cx) ** 2 + (ports[i * 4 + 3] - cy) ** 2;
    return dOut < dIn ? 1 : 0;
  };

  // Which grab zone of contig i the point (cx,cy) falls in: 0 = IN port, 1 = central, 2 = OUT
  // port. The outer PORT_ZONE_FRAC of the chord at each end is a port (rotate) zone; the middle
  // translates. Ports are also "magnetic": a disk of radius PORT_MAGNET×chord around each
  // endpoint captures its zone even when the cursor is off to the side, past the end, or the
  // chord projection would land in the middle — making the small port zones easy to hit.
  const grabZone = (i: number, cx: number, cy: number): 0 | 1 | 2 => {
    const ax = ports[i * 4], ay = ports[i * 4 + 1];
    const bx = ports[i * 4 + 2], by = ports[i * 4 + 3];
    const ex = bx - ax, ey = by - ay;
    const len2 = ex * ex + ey * ey || 1e-12;
    const dIn2 = (cx - ax) ** 2 + (cy - ay) ** 2;
    const dOut2 = (cx - bx) ** 2 + (cy - by) ** 2;
    const magnet2 = PORT_MAGNET * PORT_MAGNET * len2;
    if (dIn2 < magnet2 || dOut2 < magnet2) return dIn2 <= dOut2 ? 0 : 2; // magnetic port capture
    const t = ((cx - ax) * ex + (cy - ay) * ey) / len2; // 0 at IN, 1 at OUT
    if (t < PORT_ZONE_FRAC) return 0;
    if (t > 1 - PORT_ZONE_FRAC) return 2;
    return 1;
  };

  // --- rubber-band overlay handlers (pixel coords relative to the wrapper) ---
  const localXY = (e: React.PointerEvent): { x: number; y: number } => {
    const r = wrapRef.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const onBoxDown = (e: React.PointerEvent) => {
    if (!e.shiftKey) return;
    const { x, y } = localXY(e);
    boxStart.current = { x, y };
    setSelectRect({ x0: x, y0: y, x1: x, y1: y });
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onBoxMove = (e: React.PointerEvent) => {
    const s = boxStart.current;
    if (!s) return;
    const { x, y } = localXY(e);
    setSelectRect({ x0: s.x, y0: s.y, x1: x, y1: y });
  };
  const onBoxUp = (e: React.PointerEvent) => {
    const s = boxStart.current;
    if (!s) return;
    boxStart.current = null;
    setSelectRect(null);
    const { x, y } = localXY(e);
    const deck = deckRef.current;
    if (!deck) return;
    if (Math.abs(x - s.x) < 3 && Math.abs(y - s.y) < 3) {
      // Shift-click → toggle the contig under the cursor.
      const hit = deck.pickObject({ x, y, radius: 4, layerIds: ["ribbons"] });
      if (hit && hit.index >= 0) clickSelect(hit.index, true);
      return;
    }
    const infos = deck.pickObjects({
      x: Math.min(s.x, x),
      y: Math.min(s.y, y),
      width: Math.abs(x - s.x),
      height: Math.abs(y - s.y),
      layerIds: ["ribbons"],
    });
    const hits = [...new Set(infos.filter((i) => i.index >= 0).map((i) => i.index))];
    addToSelection(hits);
  };

  if (status === "error") {
    return <div className="deckOverlay">Failed to load graph: {error}</div>;
  }
  if (!scene) {
    return <div className="deckOverlay">{status === "loading" ? "Loading graph…" : "No graph"}</div>;
  }

  const rectStyle = selectRect
    ? {
        left: Math.min(selectRect.x0, selectRect.x1),
        top: Math.min(selectRect.y0, selectRect.y1),
        width: Math.abs(selectRect.x1 - selectRect.x0),
        height: Math.abs(selectRect.y1 - selectRect.y0),
      }
    : null;

  return (
    <div ref={wrapRef} style={{ position: "absolute", inset: "0" }}>
      <DeckGL
        ref={(inst) => {
          deckRef.current = (inst as unknown as DeckHandle) ?? null;
        }}
        key={sessionId}
        views={VIEW}
        initialViewState={initialViewState}
        controller={{ dragPan: !nodeDragging && !ctrlHeld, dragRotate: false }}
        layers={layers}
        style={{ position: "absolute", inset: "0" }}
        getCursor={({ isDragging, isHovering }) =>
          nodeDragging || isDragging ? "grabbing" : isHovering ? "pointer" : "grab"
        }
        pickingRadius={10} // magnetic cursor: pick a ribbon/port even on a near-miss (thin ribbons)
        onHover={(info) => {
          const pick = info as DeckPickInfo;
          const i = onRibbon(pick);
          setHovered(i);
          // Colour the zone a plain drag would grab — only meaningful with forces on and not
          // mid-drag. Bail to null otherwise. Skip the state write when nothing changed.
          if (i != null && pick.coordinate && force.enabled && !nodeDragging) {
            const zone = grabZone(i, pick.coordinate[0], pick.coordinate[1]);
            setHoverZone((prev) => (prev && prev.contig === i && prev.zone === zone ? prev : { contig: i, zone }));
          } else {
            setHoverZone((prev) => (prev === null ? prev : null));
          }
        }}
        onClick={(info) => {
          const pick = info as DeckPickInfo;
          // Plain click deselects (shift interactions are handled by the overlay).
          if (!pick.srcEvent?.shiftKey) clearSelection();
        }}
        onDragStart={(info) => {
          const pick = info as DeckPickInfo;
          if (!pick.coordinate) return;
          const ev = pick.srcEvent;
          if (ev?.shiftKey) return; // selection is handled by the overlay

          const i = onRibbon(pick);
          if (i == null) return; // background drag → let the controller pan
          const [cx, cy] = pick.coordinate;
          const useForces = force.enabled && !!portGraph;

          // Ctrl+drag: move ONLY the nearest port, freely — no forces, no neighbourhood.
          // The contig reshapes/resizes as its port follows the cursor. Independent of the
          // force master switch.
          if (ev?.ctrlKey || ev?.metaKey || ctrlHeld) {
            const key = portKey(i, nearestSide(i, cx, cy));
            drag.current = {
              mode: "port",
              key,
              anchor: pick.coordinate,
              start: portOverrides.get(key) ?? [0, 0],
              viaCtrl: true,
            };
            setNodeDragging(true);
            return;
          }

          // Plain drag (forces on): neighbourhood drag. Three grab zones along a lone vertex —
          // the middle third pins the whole vertex and translates it (as does a multi-selection,
          // which moves as a whole); an end third pins ONLY that port to the cursor and leaves
          // the vertex in the relaxing region, so the far port + neighbours settle by the force
          // model (rigid rod preserves length) → the vertex rotates to follow the grabbed port.
          if (useForces) {
            const k = Math.max(1, Math.round(force.dragLayers));
            const inSelection = selected.has(i) && selected.size > 0;
            const zone = inSelection ? 1 : grabZone(i, cx, cy); // selection ⇒ translate as a whole
            const rotate = !inSelection && zone !== 1;

            const seeds = inSelection ? [...selected] : [i];
            const region = bfsWithin(portGraph!, seeds, k);
            const pinnedBase = new Map<number, [number, number]>();
            if (rotate) {
              // pin the grabbed port only; keep the vertex (i) in `region` so its far port relaxes
              const side = zone === 0 ? 0 : 1;
              const off = i * 4 + side * 2;
              pinnedBase.set(i * 2 + side, [base[off], base[off + 1]]);
            } else {
              // pin the whole grabbed vertex(es); they translate rigidly and don't relax
              for (const c of seeds) {
                region.delete(c);
                pinnedBase.set(c * 2, [base[c * 4], base[c * 4 + 1]]);
                pinnedBase.set(c * 2 + 1, [base[c * 4 + 2], base[c * 4 + 3]]);
              }
            }
            const sim = buildLocalSim(portGraph!, region);
            const moved = [...new Set([...region, ...seeds])]; // every contig that can move (bulge set)
            // Freeze the stationary contigs once so the moved set can bulge against them live.
            const bg = buildBulgeBackground(base, scene.contigCount, new Set(moved), offsetsRef.current, bulge);
            drag.current = {
              mode: "cloud",
              anchor: pick.coordinate,
              sim,
              work: new Float32Array(base),
              pinnedBase,
              moved,
              bg,
            };
            setNodeDragging(true);
            return;
          }

          // Forces disabled → single-port drag (no rest-length change; that needs Ctrl).
          const key = portKey(i, nearestSide(i, cx, cy));
          drag.current = {
            mode: "port",
            key,
            anchor: pick.coordinate,
            start: portOverrides.get(key) ?? [0, 0],
            viaCtrl: false,
          };
          setNodeDragging(true);
        }}
        onDrag={(info) => {
          const d = drag.current;
          const pick = info as DeckPickInfo;
          if (!d || !pick.coordinate) return;
          const dx = pick.coordinate[0] - d.anchor[0];
          const dy = pick.coordinate[1] - d.anchor[1];

          if (d.mode === "port") {
            movePort(d.key, d.start[0] + dx, d.start[1] + dy);
            return;
          }
          const pinned = new Map<number, [number, number]>();
          d.pinnedBase.forEach(([x, y], key) => pinned.set(key, [x + dx, y + dy]));
          relaxLocal(
            portGraph!,
            d.work,
            d.sim,
            pinned,
            force,
            Math.max(1, Math.round(force.iterations)),
            linkRestOverrides,
          );
          localBulgeUpdate(offsetsRef.current, d.work, d.moved, bulge, d.bg);
          setOffsetsVersion((v) => v + 1);
          setLivePositions(d.work.slice());
        }}
        onDragEnd={() => {
          const d = drag.current;
          if (!d) return;
          // A Ctrl-drag pins the moved port's incident links to their new lengths, so the
          // force model relaxes those junctions to the distance the user set (not the default).
          if (d.mode === "port" && d.viaCtrl && portGraph) {
            const pg = portGraph;
            const key = d.key;
            const c = key >> 1;
            const aOff = c * 4 + (key & 1) * 2;
            for (let a = pg.linkAdjStart[c]; a < pg.linkAdjStart[c + 1]; a++) {
              const e = pg.linkAdjList[a];
              const other = pg.linkA[e] === key ? pg.linkB[e] : pg.linkB[e] === key ? pg.linkA[e] : -1;
              if (other < 0) continue; // link touches this contig via its other port
              const bOff = (other >> 1) * 4 + (other & 1) * 2;
              const rx = ports[aOff] - ports[bOff];
              const ry = ports[aOff + 1] - ports[bOff + 1];
              setLinkRest(e, Math.hypot(rx, ry));
            }
          }
          drag.current = null;
          setNodeDragging(false);
        }}
      />
      {/* Selection overlay: captures pointer events only while Shift is held. */}
      <div
        onPointerDown={onBoxDown}
        onPointerMove={onBoxMove}
        onPointerUp={onBoxUp}
        style={{
          position: "absolute",
          inset: "0",
          pointerEvents: shiftHeld ? "auto" : "none",
          cursor: shiftHeld ? "crosshair" : "default",
        }}
      >
        {rectStyle && (
          <div
            style={{
              position: "absolute",
              ...rectStyle,
              border: "1px solid rgba(120,160,255,0.95)",
              background: "rgba(120,160,255,0.2)",
              pointerEvents: "none",
            }}
          />
        )}
      </div>
    </div>
  );
}

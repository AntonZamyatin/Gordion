import { create } from "zustand";

import type { Scene } from "../lib/sceneCodec";
import {
  BASE_URL,
  loadGraph as apiLoadGraph,
  fetchScene,
  listDatasets as apiListDatasets,
  type DatasetInfo,
} from "../lib/api";
import {
  CURVE_CAP,
  CURVE_STEP,
  DEFAULT_BULGE,
  type BulgeParams,
} from "../features/graph/ribbonGeometry";
import { DEFAULT_FORCE, type ForceParams } from "../features/graph/forceLayout";

type Status = "idle" | "loading" | "ready" | "error";

type GraphState = {
  baseUrl: string;
  status: Status;
  error?: string;

  sessionId?: string;
  source?: string;
  contigCount: number;
  linkCount: number;
  componentCount: number;
  scene?: Scene;

  // datasets available to open (from data/*.gfa on the backend)
  datasets: DatasetInfo[];

  // interaction (indices into the scene's contig arrays)
  hoveredIndex: number | null;
  selected: Set<number>;
  selectionTick: number; // bumps on any selection change (deck updateTriggers)

  // render-time edits on top of the SGD layout (positions never sent to the backend)
  portOverrides: Map<number, [number, number]>; // key = contig*2 + side (0=IN,1=OUT)
  curveOverrides: Map<number, number>; // contig index -> manual bulge offset (frac of chord)
  linkRestOverrides: Map<number, number>; // linkId -> connection-spring rest length (Ctrl-drag)
  // full [inX,inY,outX,outY]-per-contig buffer produced by a force-layout drag; when set,
  // it is the base the renderer builds on (shadowing the raw SGD seed). Render-time only.
  livePositions: Float32Array | null;
  editVersion: number; // bumps on any edit (geometry rebuild dep)

  // live-tunable bulge/repulsion params (debug panel)
  bulge: BulgeParams;

  // interactive force-layout params (debug panel); off by default
  force: ForceParams;

  loadGraph: (name: string) => Promise<void>;
  loadDatasets: () => Promise<void>;
  recomputeLayout: () => Promise<void>;
  setHovered: (i: number | null) => void;
  clickSelect: (i: number | null, additive: boolean) => void;
  addToSelection: (indices: number[]) => void;
  clearSelection: () => void;
  movePort: (portKey: number, dx: number, dy: number) => void;
  setLinkRest: (linkId: number, rest: number) => void;
  nudgeCurvature: (contig: number, sign: 1 | -1) => void;
  clearEdits: () => void;
  setBulge: (patch: Partial<BulgeParams>) => void;
  setForce: (patch: Partial<ForceParams>) => void;
  setLivePositions: (buf: Float32Array | null) => void;
};

export const useGraphStore = create<GraphState>((set, get) => ({
  baseUrl: BASE_URL,
  status: "idle",
  contigCount: 0,
  linkCount: 0,
  componentCount: 0,
  hoveredIndex: null,
  selected: new Set(),
  selectionTick: 0,
  portOverrides: new Map(),
  curveOverrides: new Map(),
  linkRestOverrides: new Map(),
  livePositions: null,
  editVersion: 0,
  bulge: { ...DEFAULT_BULGE },
  force: { ...DEFAULT_FORCE },
  datasets: [],

  async loadDatasets() {
    try {
      const datasets = await apiListDatasets(get().baseUrl);
      set({ datasets });
    } catch {
      // dataset listing is a nice-to-have for the Open button; a failure here
      // shouldn't block loading the default graph.
    }
  },

  async loadGraph(name: string) {
    set({ status: "loading", error: undefined });
    try {
      const meta = await apiLoadGraph(get().baseUrl, name);
      const scene = await fetchScene(get().baseUrl, meta.graphId);
      set((s) => ({
        status: "ready",
        sessionId: meta.graphId,
        source: meta.source,
        contigCount: meta.contigCount,
        linkCount: meta.linkCount,
        componentCount: meta.componentCount,
        scene,
        hoveredIndex: null,
        selected: new Set(),
        selectionTick: s.selectionTick + 1,
        portOverrides: new Map(),
        curveOverrides: new Map(),
        linkRestOverrides: new Map(),
        livePositions: null,
        editVersion: s.editVersion + 1,
      }));
    } catch (e) {
      set({ status: "error", error: String(e) });
    }
  },

  async recomputeLayout() {
    const { sessionId, baseUrl } = get();
    if (!sessionId) return;
    set({ status: "loading" });
    try {
      const scene = await fetchScene(baseUrl, sessionId, true);
      set({ scene, status: "ready" });
    } catch (e) {
      set({ status: "error", error: String(e) });
    }
  },

  setHovered(i) {
    if (get().hoveredIndex !== i) set({ hoveredIndex: i });
  },

  clickSelect(i, additive) {
    if (i == null) {
      if (!additive) get().clearSelection();
      return;
    }
    set((s) => {
      const sel = new Set(s.selected);
      if (additive) {
        if (sel.has(i)) sel.delete(i);
        else sel.add(i);
      } else {
        sel.clear();
        sel.add(i);
      }
      return { selected: sel, selectionTick: s.selectionTick + 1 };
    });
  },

  addToSelection(indices) {
    if (indices.length === 0) return;
    set((s) => {
      const sel = new Set(s.selected);
      for (const i of indices) sel.add(i);
      return { selected: sel, selectionTick: s.selectionTick + 1 };
    });
  },

  clearSelection() {
    set((s) => ({ selected: new Set(), selectionTick: s.selectionTick + 1 }));
  },

  movePort(portKey, dx, dy) {
    set((s) => {
      const portOverrides = new Map(s.portOverrides);
      portOverrides.set(portKey, [dx, dy]);
      return { portOverrides, editVersion: s.editVersion + 1 };
    });
  },

  setLinkRest(linkId, rest) {
    set((s) => {
      const linkRestOverrides = new Map(s.linkRestOverrides);
      linkRestOverrides.set(linkId, rest);
      return { linkRestOverrides, editVersion: s.editVersion + 1 };
    });
  },

  nudgeCurvature(contig, sign) {
    set((s) => {
      const curveOverrides = new Map(s.curveOverrides);
      const next = Math.max(
        -CURVE_CAP,
        Math.min(CURVE_CAP, (curveOverrides.get(contig) ?? 0) + sign * CURVE_STEP),
      );
      curveOverrides.set(contig, next);
      return { curveOverrides, editVersion: s.editVersion + 1 };
    });
  },

  clearEdits() {
    set((s) =>
      s.portOverrides.size === 0 &&
      s.curveOverrides.size === 0 &&
      s.linkRestOverrides.size === 0 &&
      s.livePositions === null
        ? s
        : {
            portOverrides: new Map(),
            curveOverrides: new Map(),
            linkRestOverrides: new Map(),
            livePositions: null,
            editVersion: s.editVersion + 1,
          },
    );
  },

  setBulge(patch) {
    set((s) => ({ bulge: { ...s.bulge, ...patch } }));
  },

  setForce(patch) {
    // Retuning the global force model re-relaxes from the SGD seed, so drop any drag
    // overlay (dragLayers only affects future drags, but clearing unconditionally keeps
    // the base unambiguous).
    set((s) => ({ force: { ...s.force, ...patch }, livePositions: null }));
  },

  setLivePositions(buf) {
    set((s) => ({ livePositions: buf, editVersion: s.editVersion + 1 }));
  },
}));

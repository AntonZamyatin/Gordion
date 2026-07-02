import { create } from "zustand";

import type { Scene } from "../lib/sceneCodec";
import { BASE_URL, loadGraph as apiLoadGraph, fetchScene } from "../lib/api";

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

  // interaction (indices into the scene's contig arrays)
  hoveredIndex: number | null;
  selected: Set<number>;
  selectionTick: number; // bumps on any selection change (deck updateTriggers)

  loadGraph: (name: string) => Promise<void>;
  recomputeLayout: () => Promise<void>;
  setHovered: (i: number | null) => void;
  clickSelect: (i: number | null, additive: boolean) => void;
  clearSelection: () => void;
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

  clearSelection() {
    set((s) => ({ selected: new Set(), selectionTick: s.selectionTick + 1 }));
  },
}));

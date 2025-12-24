// src/features/graph/HoverHighlight.tsx
import { useCallback, useEffect, useState } from "react";
import { useRegisterEvents, useSetSettings, useSigma } from "@react-sigma/core";

export function HoverCoreNode() {
  const registerEvents = useRegisterEvents();
  const setSettings = useSetSettings();
  const sigma = useSigma();

  const [hoveredCore, setHoveredCore] = useState<string | null>(null);

  const NODE_SCALE = 1.5;
  const EDGE_SCALE = 1.5;

  const HIGHLIGHT = "#ffcc00";
  const DIM = "#4b5563";

  const nodeReducer = useCallback(
    (_node: string, data: any) => {
      if (!hoveredCore) return data;

      if (data.core_node_id === hoveredCore) {
        const base = data.size ?? 1;
        return { ...data, zIndex: 10, size: base * NODE_SCALE, color: HIGHLIGHT, label: data.label };
      }
      return {...data}; // return { ...data, color: DIM };
    },
    [hoveredCore]
  );

  const edgeReducer = useCallback(
    (_edge: string, data: any) => {
      if (!hoveredCore) return data;

      if (data.kind === "INTERNAL" && data.core_node_id === hoveredCore) {
        const base = data.size ?? 1;
        return { ...data, zIndex: 5, size: base * EDGE_SCALE, color: HIGHLIGHT };
      }
      return {...data}; // return { ...data, color: DIM };
    },
    [hoveredCore]
  );

  useEffect(() => {
    setSettings({ nodeReducer, edgeReducer } as any);
    sigma.refresh();
  }, [setSettings, nodeReducer, edgeReducer, sigma]);

  useEffect(() => {
    let nodeHovered = false;

    registerEvents({
      enterNode: (e) => {
        nodeHovered = true;
        const g = sigma.getGraph();
        const attrs = g.getNodeAttributes(e.node) as any;
        setHoveredCore((attrs?.core_node_id as string) ?? null);
      },
      leaveNode: () => {
        nodeHovered = false;
        setHoveredCore(null);
      },
      enterEdge: (e) => {
        const g = sigma.getGraph();
        const attrs = g.getEdgeAttributes(e.edge) as any;
        setHoveredCore((attrs?.core_node_id as string) ?? null);
      },
      leaveEdge: () => {
        if (!nodeHovered) setHoveredCore(null);
      },
    });
  }, [registerEvents, sigma]);

  return null;
}

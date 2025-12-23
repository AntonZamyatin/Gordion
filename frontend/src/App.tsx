import { useCallback, useEffect, useMemo, useState } from "react";
import Graph from "graphology";
import {
  SigmaContainer,
  useLoadGraph,
  useSigma,
  useRegisterEvents,
  useSetSettings,
} from "@react-sigma/core";

type NodeDTO = {
  id: string;
  x: number;
  y: number;
  label?: string | null;
  size?: number;
  core_node_id?: string | null;
};

type EdgeDTO = {
  id?: string;
  source: string;
  target: string;
  size?: number;
  core_node_id?: string | null; // internal edges
  core_edge_id?: string | null; // external edges (future use)
  kind?: string | null;         // "INTERNAL" | "EXTERNAL"
};

type GraphDTO = { nodes: NodeDTO[]; edges: EdgeDTO[] };

type NodeAttrs = { core_node_id?: string | null; size?: number; label?: string };
type EdgeAttrs = { core_node_id?: string | null; kind?: string; size?: number };

function GraphLoader() {
  const loadGraph = useLoadGraph();
  const sigma = useSigma();

  useEffect(() => {
    (async () => {
      // 1) ask backend to load example.gfa and create a session
      const r1 = await fetch("http://localhost:8000/graphs/load-example", { method: "POST" });
      const graphId = await r1.json();

      // 2) fetch sigma-view DTO
      const r2 = await fetch(`http://localhost:8000/graphs/${graphId}/view`);
      const data: GraphDTO = await r2.json();

      const g = new Graph();

      for (const n of data.nodes) {
        g.addNode(n.id, {
          x: n.x,
          y: n.y,
          size: n.size ?? 6,
          label: undefined,// n.label ?? undefined,          // IMPORTANT: don't fallback to n.id
          core_node_id: n.core_node_id ?? null,
          color: "#9aa0a6",
        });
      }

      for (const e of data.edges) {
        const attrs = {
          size: e.size ?? 1,
          kind: e.kind ?? null,
          core_node_id: e.core_node_id ?? null,
          core_edge_id: e.core_edge_id ?? null,
          color: "#9aa0a6",
        };

        if (e.id) g.addEdgeWithKey(e.id, e.source, e.target, attrs);
        else g.addEdge(e.source, e.target, attrs);
      }
      

      loadGraph(g);

      requestAnimationFrame(() => {
        sigma.refresh();
        sigma.getCamera().animatedReset();
      });
    })().catch((err) => console.error(err));
  }, [loadGraph, sigma]);

  return null;
}

function HoverHighlight() {
  const registerEvents = useRegisterEvents();
  const setSettings = useSetSettings();
  const sigma = useSigma();

  const [hoveredCore, setHoveredCore] = useState<string | null>(null);

  // Slight enlargement factors (tune as needed)
  const NODE_SCALE = 1.5;
  const EDGE_SCALE = 1.5;

  const HIGHLIGHT = "#ffcc00";
  const DIM = "#4b5563";

  const nodeReducer = useCallback(
    (_node: string, data: any) => {
      if (!hoveredCore) return data;

      if (data.core_node_id === hoveredCore) {
        const base = data.size ?? 1;
        return {
          ...data,
          zIndex: 10,
          size: base * NODE_SCALE,
          color: HIGHLIGHT,
          label: data.label, // keep as-is (you likely use undefined)
        };
      }
      //return data;
      return { ...data, color: DIM };
    },
    [hoveredCore]
  );

  const edgeReducer = useCallback(
    (_edge: string, data: any) => {
      if (!hoveredCore) {
        return data;
        console.log("edgeReducer: no hovered core");
      }


      // We only enlarge INTERNAL edges belonging to the hovered core node
      if (data.kind === "INTERNAL" && data.core_node_id === hoveredCore) {
        const base = data.size ?? 1;
        return {
          ...data,
          zIndex: 5,
          size: base * EDGE_SCALE,
          color: HIGHLIGHT,
        };
      }
      //return data;
      return { ...data, color: DIM };
    },
    [hoveredCore]
  );

  // Install reducers + enable Sigma v2 edge hover events (required for enterEdge/leaveEdge)
  useEffect(() => {
    setSettings({
      nodeReducer,
      edgeReducer,
    } as any);

    sigma.refresh();
  }, [setSettings, nodeReducer, edgeReducer, sigma]);

  // Hover events: node or edge => set hovered core node id
  useEffect(() => {
    
    let nodeHovered = false;

    registerEvents({
      enterNode: (e) => {
        nodeHovered = true;
        const g = sigma.getGraph();
        const attrs = g.getNodeAttributes(e.node) as any;
        console.log("enterNode: attrs", attrs);
        setHoveredCore((attrs?.core_node_id as string) ?? null);
      },
      leaveNode: () => {
        nodeHovered = false; 
        setHoveredCore(null)
      },

      enterEdge: (e) => {
        const g = sigma.getGraph();
        const attrs = g.getEdgeAttributes(e.edge) as any;
        console.log("enterEdge: attrs", attrs);
        // For INTERNAL edges, backend sets core_node_id; EXTERNAL edges likely null
        setHoveredCore((attrs?.core_node_id as string) ?? null);
      },
      leaveEdge: () => {if (!nodeHovered) setHoveredCore(null)},
    });
  }, [registerEvents, sigma]);

  return null;
}

import type { Settings } from "sigma/settings";
import type { Attributes } from "graphology-types";
import type { NodeHoverDrawingFunction } from "sigma/rendering";

const noHover: NodeHoverDrawingFunction<Attributes, Attributes, Attributes> = () => {
  // draw nothing -> removes the white hover ring
};

export default function App() {
  return (
    <SigmaContainer
      style={{ position: "fixed", inset: 0 }}
      settings={{
        enableEdgeEvents: true,
        renderLabels: false,
        renderEdgeLabels: false,
        defaultDrawNodeHover: noHover,
      }}
    >
      <GraphLoader />
      <HoverHighlight />
    </SigmaContainer>
  );
}
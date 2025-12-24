// src/features/graph/GraphLoader.tsx
import { useEffect } from "react";
import Graph from "graphology";
import { useLoadGraph, useSigma } from "@react-sigma/core";

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
  core_node_id?: string | null;
  core_edge_id?: string | null;
  kind?: string | null;
};

type GraphDTO = { nodes: NodeDTO[]; edges: EdgeDTO[] };

export function GraphLoader() {
  const loadGraph = useLoadGraph();
  const sigma = useSigma();

  useEffect(() => {
    (async () => {
      const r1 = await fetch("http://localhost:8000/graphs/load-example", { method: "POST" });
      const graphId = await r1.json();

      const r2 = await fetch(`http://localhost:8000/graphs/${graphId}/view`);
      const data: GraphDTO = await r2.json();

      const g = new Graph();

      for (const n of data.nodes) {
        g.addNode(n.id, {
          x: n.x,
          y: n.y,
          size: n.size ?? 6,
          label: undefined,
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

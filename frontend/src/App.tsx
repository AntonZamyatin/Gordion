import { useEffect } from "react";
import Graph from "graphology";
import { SigmaContainer, useLoadGraph, useSigma } from "@react-sigma/core";

type NodeDTO = { id: string; x: number; y: number; label?: string; size?: number };
type EdgeDTO = { id?: string; source: string; target: string };
type GraphDTO = { nodes: NodeDTO[]; edges: EdgeDTO[] };

function GraphLoader() {
  const loadGraph = useLoadGraph();
  const sigma = useSigma();

  useEffect(() => {
    (async () => {
      const r = await fetch("http://localhost:8000/graph/demo");
      const data: GraphDTO = await r.json();

      const g = new Graph();

      for (const n of data.nodes) {
        g.addNode(n.id, {
          x: n.x,
          y: n.y,
          size: n.size ?? 8,
          label: n.label ?? n.id,
        });
      }
      for (const e of data.edges) {
        // graphology edge IDs must be unique if provided
        if (e.id) g.addEdgeWithKey(e.id, e.source, e.target);
        else g.addEdge(e.source, e.target);
      }

      loadGraph(g);

      requestAnimationFrame(() => {
        sigma.refresh();
        sigma.getCamera().animatedReset();
      });
    })().catch((err) => {
      console.error("Failed to load graph:", err);
    });
  }, [loadGraph, sigma]);

  return null;
}

export default function App() {
  return (
    <SigmaContainer style={{ position: "fixed", inset: 0 }}>
      <GraphLoader />
    </SigmaContainer>
  );
}

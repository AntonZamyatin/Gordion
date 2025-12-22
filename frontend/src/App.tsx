import { useEffect } from "react";
import Graph from "graphology";
import { SigmaContainer, useLoadGraph, useSigma } from "@react-sigma/core";

type NodeDTO = { id: string; x: number; y: number; label?: string; size?: number };
type EdgeDTO = { id?: string; source: string; target: string; size?: number };
type GraphDTO = { nodes: NodeDTO[]; edges: EdgeDTO[] };

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
          label: n.label ?? n.id,
        });
      }
      for (const e of data.edges) {
        const attrs = {
          size: e.size ?? 1,
          // color: e.color ?? "#999", // optional if you add it on backend
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

export default function App() {
  return (
    <SigmaContainer style={{ position: "fixed", inset: 0 }}>
      <GraphLoader />
    </SigmaContainer>
  );
}

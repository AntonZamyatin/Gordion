// Backend client: the session scene flow.
import { decodeScene, type Scene } from "./sceneCodec";

export const BASE_URL = "http://localhost:8000";

export type GraphMeta = {
  graphId: string;
  source: string;
  contigCount: number;
  linkCount: number;
  componentCount: number;
};

export async function loadGraph(baseUrl: string, name: string): Promise<GraphMeta> {
  const r = await fetch(`${baseUrl}/graphs/load?name=${encodeURIComponent(name)}`, {
    method: "POST",
  });
  if (!r.ok) throw new Error(`load ${name}: HTTP ${r.status}`);
  const j = await r.json();
  return {
    graphId: j.graph_id,
    source: j.source,
    contigCount: j.contigCount,
    linkCount: j.linkCount,
    componentCount: j.componentCount,
  };
}

export async function fetchScene(baseUrl: string, graphId: string, recompute = false): Promise<Scene> {
  const url = `${baseUrl}/graphs/${graphId}/scene${recompute ? "?recompute=true" : ""}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`scene: HTTP ${r.status}`);
  return decodeScene(await r.arrayBuffer());
}

export type DatasetInfo = { name: string; sizeBytes: number };

export async function listDatasets(baseUrl: string): Promise<DatasetInfo[]> {
  const r = await fetch(`${baseUrl}/graphs/datasets`);
  if (!r.ok) throw new Error(`datasets: HTTP ${r.status}`);
  const j = await r.json();
  return j.datasets;
}

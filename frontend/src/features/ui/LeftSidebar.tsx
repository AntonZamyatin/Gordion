// src/features/ui/LeftSidebar.tsx
import { useGraphStore } from "../../store/useGraphStore";

type Props = {
  collapsed: boolean;
};

const LARGE_FILE_BYTES = 500 * 1024 * 1024; // flag anything over this before it's clicked

function formatSize(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

export function LeftSidebar({ collapsed }: Props) {
  const source = useGraphStore((s) => s.source);
  const status = useGraphStore((s) => s.status);
  const datasets = useGraphStore((s) => s.datasets);
  const loadGraph = useGraphStore((s) => s.loadGraph);
  const loadDatasets = useGraphStore((s) => s.loadDatasets);
  const recomputeLayout = useGraphStore((s) => s.recomputeLayout);
  const busy = status === "loading";

  return (
    <aside className="leftBar">
      <div className="sidebarHeader">
        <div style={{ fontWeight: 600 }}>{collapsed ? "Params" : "Visualization params"}</div>
      </div>

      <div className="sidebarBody">
        <div
          style={{
            marginBottom: 10,
            fontWeight: 600,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>Open dataset</span>
          <button className="iconBtn" disabled={busy} onClick={() => void loadDatasets()} title="Rescan data/">
            ↻
          </button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {datasets.length === 0 && <div style={{ opacity: 0.6 }}>No .gfa files found</div>}
          {datasets.map(({ name, sizeBytes }) => (
            <button
              key={name}
              className="iconBtn"
              disabled={busy}
              style={{
                width: "100%",
                textAlign: "left",
                opacity: name === source ? 1 : 0.7,
              }}
              title={sizeBytes >= LARGE_FILE_BYTES ? "Large file — loading may take a while" : undefined}
              onClick={() => void loadGraph(name)}
            >
              {name === source ? "● " : ""}
              {name}.gfa
              <span style={{ float: "right", fontFamily: "monospace", opacity: 0.7 }}>
                {formatSize(sizeBytes)}
                {sizeBytes >= LARGE_FILE_BYTES ? " ⚠" : ""}
              </span>
            </button>
          ))}
        </div>

        <div style={{ marginTop: 14, marginBottom: 10, fontWeight: 600 }}>Layout</div>
        <button
          className="iconBtn"
          style={{ width: "100%" }}
          disabled={busy}
          onClick={() => void recomputeLayout()}
        >
          Recompute layout
        </button>
      </div>
    </aside>
  );
}

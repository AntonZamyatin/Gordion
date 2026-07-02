// src/features/ui/LeftSidebar.tsx
import { useGraphStore } from "../../store/useGraphStore";

type Props = {
  collapsed: boolean;
};

const DATASETS = ["example3", "example1", "example"];

export function LeftSidebar({ collapsed }: Props) {
  const source = useGraphStore((s) => s.source);
  const status = useGraphStore((s) => s.status);
  const loadGraph = useGraphStore((s) => s.loadGraph);
  const recomputeLayout = useGraphStore((s) => s.recomputeLayout);
  const busy = status === "loading";

  return (
    <aside className="leftBar">
      <div className="sidebarHeader">
        <div style={{ fontWeight: 600 }}>{collapsed ? "Params" : "Visualization params"}</div>
      </div>

      <div className="sidebarBody">
        <div style={{ marginBottom: 10, fontWeight: 600 }}>Dataset</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {DATASETS.map((name) => (
            <button
              key={name}
              className="iconBtn"
              disabled={busy}
              style={{ width: "100%", opacity: name === source ? 1 : 0.7 }}
              onClick={() => void loadGraph(name)}
            >
              {name === source ? "● " : ""}
              {name}.gfa
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

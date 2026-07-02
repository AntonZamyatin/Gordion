// src/features/ui/TopBar.tsx
import { useGraphStore } from "../../store/useGraphStore";

type Props = {
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  onToggleLeft(): void;
  onToggleRight(): void;
};

export function TopBar({ leftCollapsed, rightCollapsed, onToggleLeft, onToggleRight }: Props) {
  const source = useGraphStore((s) => s.source);
  const status = useGraphStore((s) => s.status);
  const contigCount = useGraphStore((s) => s.contigCount);
  const linkCount = useGraphStore((s) => s.linkCount);
  const componentCount = useGraphStore((s) => s.componentCount);

  return (
    <div className="topBar">
      <button className="iconBtn" onClick={onToggleLeft} title="Toggle left sidebar">
        {leftCollapsed ? ">" : "<"}
      </button>

      <div style={{ fontWeight: 600 }}>Gordion</div>

      <div style={{ opacity: 0.75 }}>
        file: <span style={{ fontFamily: "monospace" }}>{source ? `${source}.gfa` : "—"}</span>
      </div>

      {status === "ready" && (
        <div style={{ opacity: 0.75, fontFamily: "monospace" }}>
          {contigCount} contigs · {linkCount} links · {componentCount} components
        </div>
      )}
      {status === "loading" && <div style={{ opacity: 0.75 }}>loading…</div>}
      {status === "error" && <div style={{ color: "#e57373" }}>load failed</div>}

      <div style={{ flex: 1 }} />

      <button className="iconBtn" onClick={onToggleRight} title="Toggle right sidebar">
        {rightCollapsed ? "<" : ">"}
      </button>
    </div>
  );
}

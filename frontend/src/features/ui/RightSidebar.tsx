// src/features/ui/RightSidebar.tsx
import { useState } from "react";
import { useGraphStore } from "../../store/useGraphStore";

type Props = {
  collapsed: boolean;
};

export function RightSidebar({ collapsed }: Props) {
  const scene = useGraphStore((s) => s.scene);
  const hoveredIndex = useGraphStore((s) => s.hoveredIndex);
  const selected = useGraphStore((s) => s.selected);
  const clickSelect = useGraphStore((s) => s.clickSelect);
  const clearSelection = useGraphStore((s) => s.clearSelection);

  const [query, setQuery] = useState("");
  const [notFound, setNotFound] = useState(false);

  const hoveredId = scene && hoveredIndex != null ? scene.idTable[hoveredIndex] : null;
  const selectedIds = scene ? [...selected].map((i) => scene.idTable[i]) : [];

  const search = () => {
    if (!scene) return;
    const idx = scene.idTable.indexOf(query.trim());
    setNotFound(idx < 0);
    if (idx >= 0) clickSelect(idx, false);
  };

  return (
    <aside className="rightBar">
      <div className="sidebarHeader">
        <div style={{ fontWeight: 600 }}>{collapsed ? "Info" : "Info & search"}</div>
      </div>

      <div className="sidebarBody">
        <div style={{ marginBottom: 10, fontWeight: 600 }}>Search</div>
        <div style={{ display: "flex", gap: 6 }}>
          <input
            value={query}
            placeholder="Contig id…"
            onChange={(e) => {
              setQuery(e.target.value);
              setNotFound(false);
            }}
            onKeyDown={(e) => e.key === "Enter" && search()}
            style={{ flex: 1, height: 32, borderRadius: 8, border: "1px solid rgba(0,0,0,0.25)" }}
          />
          <button className="iconBtn" onClick={search}>
            Go
          </button>
        </div>
        {notFound && <div style={{ marginTop: 6, color: "#e57373" }}>No contig with that id</div>}

        <div style={{ marginTop: 14, marginBottom: 6, fontWeight: 600 }}>Hovered</div>
        <div style={{ fontFamily: "monospace", opacity: 0.85 }}>{hoveredId ?? "—"}</div>

        <div
          style={{
            marginTop: 14,
            marginBottom: 6,
            fontWeight: 600,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>Selection ({selectedIds.length})</span>
          {selectedIds.length > 0 && (
            <button className="iconBtn" onClick={clearSelection}>
              Clear
            </button>
          )}
        </div>
        {selectedIds.length === 0 ? (
          <div style={{ opacity: 0.6 }}>Click a contig; Shift-click to add</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 2, fontFamily: "monospace" }}>
            {selectedIds.map((id) => (
              <div key={id}>{id}</div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

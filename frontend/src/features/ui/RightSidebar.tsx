// src/features/ui/RightSidebar.tsx
import { useState } from "react";
import { useGraphStore } from "../../store/useGraphStore";
import type { BulgeParams } from "../graph/ribbonGeometry";
import type { ForceParams } from "../graph/forceLayout";

type Props = {
  collapsed: boolean;
};

// One labelled slider bound to a bulge param.
function BulgeSlider({
  label,
  field,
  min,
  max,
  step,
  precision = 2,
}: {
  label: string;
  field: keyof BulgeParams;
  min: number;
  max: number;
  step: number;
  precision?: number;
}) {
  const value = useGraphStore((s) => s.bulge[field]);
  const setBulge = useGraphStore((s) => s.setBulge);
  return (
    <label style={{ display: "block", marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, opacity: 0.85 }}>
        <span>{label}</span>
        <span style={{ fontFamily: "monospace" }}>{value.toFixed(precision)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => setBulge({ [field]: Number(e.target.value) } as Partial<BulgeParams>)}
        style={{ width: "100%" }}
      />
    </label>
  );
}

// One labelled slider bound to a force-layout param.
function ForceSlider({
  label,
  field,
  min,
  max,
  step,
  precision = 2,
}: {
  label: string;
  field: keyof ForceParams;
  min: number;
  max: number;
  step: number;
  precision?: number;
}) {
  const value = useGraphStore((s) => s.force[field] as number);
  const setForce = useGraphStore((s) => s.setForce);
  return (
    <label style={{ display: "block", marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, opacity: 0.85 }}>
        <span>{label}</span>
        <span style={{ fontFamily: "monospace" }}>{value.toFixed(precision)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => setForce({ [field]: Number(e.target.value) } as Partial<ForceParams>)}
        style={{ width: "100%" }}
      />
    </label>
  );
}

export function RightSidebar({ collapsed }: Props) {
  const scene = useGraphStore((s) => s.scene);
  const hoveredIndex = useGraphStore((s) => s.hoveredIndex);
  const selected = useGraphStore((s) => s.selected);
  const clickSelect = useGraphStore((s) => s.clickSelect);
  const clearSelection = useGraphStore((s) => s.clearSelection);
  const editCount = useGraphStore(
    (s) =>
      s.portOverrides.size +
      s.curveOverrides.size +
      s.linkRestOverrides.size +
      (s.livePositions ? 1 : 0),
  );
  const clearEdits = useGraphStore((s) => s.clearEdits);
  const forceEnabled = useGraphStore((s) => s.force.enabled);
  const setForce = useGraphStore((s) => s.setForce);

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
        <div style={{ marginTop: 4, fontSize: 12, opacity: 0.6 }}>
          Hover a contig, press <b>+</b> / <b>-</b> to bend its curvature
        </div>

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

        <hr style={{ margin: "16px 0", border: 0, borderTop: "1px solid rgba(255,255,255,0.12)" }} />

        <div
          style={{
            marginBottom: 10,
            fontWeight: 600,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>Debug · bulge</span>
          {editCount > 0 && (
            <button className="iconBtn" onClick={clearEdits}>
              Reset edits ({editCount})
            </button>
          )}
        </div>
        <BulgeSlider label="Repel strength" field="strength" min={0} max={1.5} step={0.01} />
        <BulgeSlider label="Repel radius ×chord" field="radiusFactor" min={0.1} max={3} step={0.05} />
        <BulgeSlider label="Max bulge ×chord" field="maxOffsetFrac" min={0} max={1.5} step={0.05} />
        <BulgeSlider label="Iterations" field="iterations" min={1} max={120} step={1} precision={0} />
        <BulgeSlider label="Curve samples" field="samples" min={2} max={24} step={1} precision={0} />

        <hr style={{ margin: "16px 0", border: 0, borderTop: "1px solid rgba(255,255,255,0.12)" }} />

        <label
          style={{
            marginBottom: 10,
            fontWeight: 600,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            cursor: "pointer",
          }}
        >
          <span>Debug · forces</span>
          <input
            type="checkbox"
            checked={forceEnabled}
            onChange={(e) => setForce({ enabled: e.target.checked })}
          />
        </label>
        <div style={{ fontSize: 12, opacity: 0.6, marginBottom: 10 }}>
          Force-assisted dragging only (no layout change on load). Grab a vertex near its <b>middle</b>
          to move it, or near an <b>end</b> to rotate it (that port follows the cursor, the rest reflows);
          the highlighted zone shows what you'll grab, and the ends are magnetic so they're easy to hit.
          <b>Ctrl-drag</b> moves just the nearest
          port and pins that connection's rest length to the new gap; <b>Shift-drag</b> box-selects (Shift-click adds);
          drag a <b>selected</b> vertex to move the selection rigidly while its neighbourhood reflows. Plain
          click deselects.
        </div>
        {forceEnabled && (
          <>
            <ForceSlider label="Spring elasticity" field="portAttract" min={0} max={10} step={0.02} />
            <ForceSlider label="Default edge length ×chord" field="edgeLength" min={0} max={1} step={0.02} />
            <ForceSlider label="Junction straightening" field="portRepel" min={0} max={2} step={0.02} />
            <ForceSlider label="General repulsion" field="generalRepel" min={0} max={2} step={0.02} />
            <ForceSlider label="Repel radius ×chord" field="repelRadius" min={0.2} max={4} step={0.05} />
            <ForceSlider label="Iterations / drag" field="iterations" min={1} max={40} step={1} precision={0} />
            <ForceSlider label="Damping" field="damping" min={0.05} max={1} step={0.05} />
            <ForceSlider label="Drag neighbourhood (k)" field="dragLayers" min={1} max={8} step={1} precision={0} />
          </>
        )}
      </div>
    </aside>
  );
}

// src/features/ui/LeftSidebar.tsx
type Props = {
    collapsed: boolean;
  };
  
  export function LeftSidebar({ collapsed }: Props) {
    return (
      <aside className="leftBar">
        <div className="sidebarHeader">
          <div style={{ fontWeight: 600 }}>{collapsed ? "Params" : "Visualization params"}</div>
        </div>
  
        <div className="sidebarBody">
          <div style={{ marginBottom: 10, fontWeight: 600 }}>Rendering</div>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" defaultChecked />
            Show labels
          </label>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" defaultChecked />
            Highlight core on hover
          </label>
  
          <div style={{ marginTop: 14, marginBottom: 10, fontWeight: 600 }}>Layout</div>
          <button className="iconBtn" style={{ width: "100%" }}>
            Recompute layout (placeholder)
          </button>
        </div>
      </aside>
    );
  }
  
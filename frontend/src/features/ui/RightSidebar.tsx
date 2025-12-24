// src/features/ui/RightSidebar.tsx
type Props = {
    collapsed: boolean;
  };
  
  export function RightSidebar({ collapsed }: Props) {
    return (
      <aside className="rightBar">
        <div className="sidebarHeader">
          <div style={{ fontWeight: 600 }}>{collapsed ? "Info" : "Info & search"}</div>
        </div>
  
        <div className="sidebarBody">
          <div style={{ marginBottom: 10, fontWeight: 600 }}>Search</div>
          <input
            placeholder="Node id / label..."
            style={{
              width: "100%",
              height: 34,
              padding: "0 0px",
              borderRadius: 8,
              border: "1px solid rgba(0,0,0,0.15)",
            }}
          />
  
          <div style={{ marginTop: 14, marginBottom: 10, fontWeight: 600 }}>Selection</div>
          <div style={{ opacity: 0.75 }}>No selection yet (placeholder)</div>
        </div>
      </aside>
    );
  }
  
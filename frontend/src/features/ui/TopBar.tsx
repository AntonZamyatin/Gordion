// src/features/ui/TopBar.tsx
type Props = {
    leftCollapsed: boolean;
    rightCollapsed: boolean;
    onToggleLeft(): void;
    onToggleRight(): void;
  };
  
  export function TopBar({ leftCollapsed, rightCollapsed, onToggleLeft, onToggleRight }: Props) {
    return (
      <div className="topBar">
        <button className="iconBtn" onClick={onToggleLeft} title="Toggle left sidebar">
          {leftCollapsed ? ">" : "<"}
        </button>
  
        <div style={{ fontWeight: 600 }}>Gordion</div>
  
        <div style={{ opacity: 0.75 }}>
          file: <span style={{ fontFamily: "monospace" }}>example.gfa</span>
        </div>
  
        <div style={{ opacity: 0.75 }}>
          component: <span style={{ fontFamily: "monospace" }}>ALL</span>
        </div>
  
        <div style={{ flex: 1 }} />
  
        <button className="iconBtn" title="Actions (placeholder)">
          Actions
        </button>
  
        <button className="iconBtn" onClick={onToggleRight} title="Toggle right sidebar">
          {rightCollapsed ? "<" : ">"}
        </button>
      </div>
    );
  }
  
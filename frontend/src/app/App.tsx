// src/app/App.tsx
import { useState } from "react";
import "./app.css";

import { TopBar } from "../features/ui/TopBar";
import { LeftSidebar } from "../features/ui/LeftSidebar";
import { RightSidebar } from "../features/ui/RightSidebar";
import { GraphCanvas } from "../features/graph/GraphCanvas";

export default function App() {
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  return (
    <div
      className="appShell"
      data-left-collapsed={leftCollapsed ? "true" : "false"}
      data-right-collapsed={rightCollapsed ? "true" : "false"}
    >
      <TopBar
        leftCollapsed={leftCollapsed}
        rightCollapsed={rightCollapsed}
        onToggleLeft={() => setLeftCollapsed((v) => !v)}
        onToggleRight={() => setRightCollapsed((v) => !v)}
      />

      <LeftSidebar collapsed={leftCollapsed} onToggle={() => setLeftCollapsed((v) => !v)} />

      <main className="main">
        <GraphCanvas />
      </main>

      <RightSidebar collapsed={rightCollapsed} onToggle={() => setRightCollapsed((v) => !v)} />
    </div>
  );
}

// src/app/App.tsx
import { useState } from "react";
import "./app.css";
import { dbg } from "../debug.ts";

import { TopBar } from "../features/ui/TopBar";
import { LeftSidebar } from "../features/ui/LeftSidebar";
import { RightSidebar } from "../features/ui/RightSidebar";
import { GraphCanvas } from "../features/graph/GraphCanvas";

export default function App() {
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  const onToggleLeft = () => {
    dbg("UI toggle LEFT (before)", { leftCollapsed });
    setLeftCollapsed(v => {
      dbg("UI toggle LEFT (state updater)", { prev: v, next: !v });
      return !v;
    });
  };

  dbg("App render", { leftCollapsed, rightCollapsed });

  
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

      <LeftSidebar collapsed={leftCollapsed} />

      <main className="main">
        <GraphCanvas />
      </main>

      <RightSidebar collapsed={rightCollapsed} />
    </div>
  );
}

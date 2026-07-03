// src/app/App.tsx
import { useEffect, useRef, useState } from "react";
import "./App.css";

import { TopBar } from "../features/ui/TopBar";
import { LeftSidebar } from "../features/ui/LeftSidebar";
import { RightSidebar } from "../features/ui/RightSidebar";
import { DeckCanvas } from "../features/graph/DeckCanvas";
import { useGraphStore } from "../store/useGraphStore";

const DEFAULT_GRAPH = "example3";

export default function App() {
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  const loadGraph = useGraphStore((s) => s.loadGraph);
  const loadDatasets = useGraphStore((s) => s.loadDatasets);
  const loadedRef = useRef(false);

  useEffect(() => {
    // Guard against React StrictMode's double effect invocation.
    if (loadedRef.current) return;
    loadedRef.current = true;
    void loadGraph(DEFAULT_GRAPH);
    void loadDatasets();
  }, [loadGraph, loadDatasets]);

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
        <DeckCanvas />
      </main>

      <RightSidebar collapsed={rightCollapsed} />
    </div>
  );
}

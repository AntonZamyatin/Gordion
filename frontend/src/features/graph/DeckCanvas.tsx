import { useMemo } from "react";
import { DeckGL } from "@deck.gl/react";
import { OrthographicView } from "@deck.gl/core";

import { useGraphStore } from "../../store/useGraphStore";
import { buildLayers } from "./layers";

const VIEW = new OrthographicView({ flipY: false });

type DeckPickInfo = { index: number; layer?: { id: string } | null; srcEvent?: MouseEvent };

export function DeckCanvas() {
  const scene = useGraphStore((s) => s.scene);
  const status = useGraphStore((s) => s.status);
  const error = useGraphStore((s) => s.error);
  const sessionId = useGraphStore((s) => s.sessionId);
  const hoveredIndex = useGraphStore((s) => s.hoveredIndex);
  const selected = useGraphStore((s) => s.selected);
  const selectionTick = useGraphStore((s) => s.selectionTick);
  const setHovered = useGraphStore((s) => s.setHovered);
  const clickSelect = useGraphStore((s) => s.clickSelect);

  // Fit the view to the scene; refits on a new session (key below).
  const initialViewState = useMemo(() => {
    if (!scene) return { target: [0, 0, 0] as [number, number, number], zoom: 0 };
    const [minX, minY, maxX, maxY] = scene.bbox;
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const extent = Math.max(maxX - minX, maxY - minY) || 1;
    const viewport = Math.min(window.innerWidth, window.innerHeight) * 0.8;
    return { target: [cx, cy, 0] as [number, number, number], zoom: Math.log2(viewport / extent) };
  }, [scene, sessionId]);

  const layers = useMemo(
    () => (scene ? buildLayers(scene, hoveredIndex, selected, selectionTick) : []),
    [scene, hoveredIndex, selected, selectionTick],
  );

  const onRibbon = (info: DeckPickInfo): number | null =>
    info.index >= 0 && info.layer?.id === "ribbons" ? info.index : null;

  if (status === "error") {
    return <div className="deckOverlay">Failed to load graph: {error}</div>;
  }
  if (!scene) {
    return <div className="deckOverlay">{status === "loading" ? "Loading graph…" : "No graph"}</div>;
  }

  return (
    <DeckGL
      key={sessionId}
      views={VIEW}
      initialViewState={initialViewState}
      controller={true}
      layers={layers}
      style={{ position: "absolute", inset: "0" }}
      getCursor={({ isDragging, isHovering }) =>
        isDragging ? "grabbing" : isHovering ? "pointer" : "grab"
      }
      onHover={(info) => setHovered(onRibbon(info as DeckPickInfo))}
      onClick={(info) => {
        const i = onRibbon(info as DeckPickInfo);
        clickSelect(i, !!(info as DeckPickInfo).srcEvent?.shiftKey);
      }}
    />
  );
}

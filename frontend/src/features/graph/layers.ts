import { PathLayer } from "@deck.gl/layers";

import type { Scene } from "../../lib/sceneCodec";

const HOVER_COLOR: [number, number, number, number] = [255, 208, 0, 255];
const SELECT_COLOR: [number, number, number, number] = [255, 255, 255, 255];

function startIndices(count: number): Uint32Array {
  const s = new Uint32Array(count + 1);
  for (let i = 0; i <= count; i++) s[i] = i * 2;
  return s;
}

type PickInfo = { index: number };

export function buildLayers(
  scene: Scene,
  hoveredIndex: number | null,
  selected: Set<number>,
  selectionTick: number,
) {
  const n = scene.contigCount;

  const ribbons = new PathLayer({
    id: "ribbons",
    data: {
      length: n,
      startIndices: startIndices(n),
      attributes: { getPath: { value: scene.contigPositions, size: 2 } },
    } as unknown as [],
    _pathType: "open",
    positionFormat: "XY",
    getColor: (_o: unknown, info: PickInfo) => {
      const i = info.index;
      if (i === hoveredIndex) return HOVER_COLOR;
      if (selected.has(i)) return SELECT_COLOR;
      const j = i * 4;
      return [
        scene.contigColor[j],
        scene.contigColor[j + 1],
        scene.contigColor[j + 2],
        scene.contigColor[j + 3],
      ];
    },
    getWidth: (_o: unknown, info: PickInfo) => {
      const i = info.index;
      const w = scene.contigWidth[i];
      return i === hoveredIndex || selected.has(i) ? w * 1.6 : w;
    },
    widthUnits: "pixels",
    widthMinPixels: 1.5,
    widthMaxPixels: 60,
    capRounded: true,
    jointRounded: true,
    pickable: true,
    updateTriggers: {
      getColor: [hoveredIndex, selectionTick],
      getWidth: [hoveredIndex, selectionTick],
    },
  });

  const linkCount = scene.linkPositions.length / 4;
  if (linkCount === 0) return [ribbons];

  const links = new PathLayer({
    id: "links",
    data: {
      length: linkCount,
      startIndices: startIndices(linkCount),
      attributes: { getPath: { value: scene.linkPositions, size: 2 } },
    } as unknown as [],
    _pathType: "open",
    positionFormat: "XY",
    getColor: [90, 100, 120, 150],
    getWidth: 1,
    widthUnits: "pixels",
    widthMinPixels: 0.5,
    pickable: false,
  });

  // links under ribbons
  return [links, ribbons];
}

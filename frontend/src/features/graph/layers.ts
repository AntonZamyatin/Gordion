import { PathLayer } from "@deck.gl/layers";

import type { Scene } from "../../lib/sceneCodec";
import type { RibbonPaths } from "./ribbonGeometry";

const HOVER_COLOR: [number, number, number, number] = [255, 208, 0, 255];
const SELECT_COLOR: [number, number, number, number] = [255, 255, 255, 255];

function linkStartIndices(count: number): Uint32Array {
  const s = new Uint32Array(count + 1);
  for (let i = 0; i <= count; i++) s[i] = i * 2;
  return s;
}

type PickInfo = { index: number };

export function buildLayers(
  scene: Scene,
  paths: RibbonPaths,
  linkPositions: Float32Array,
  hoveredIndex: number | null,
  selected: Set<number>,
  selectionTick: number,
) {
  const n = scene.contigCount;

  // One curved path per contig -> deck.gl still picks per-contig (info.index = contig).
  const ribbons = new PathLayer({
    id: "ribbons",
    data: {
      length: n,
      startIndices: paths.startIndices,
      attributes: { getPath: { value: paths.positions, size: 2 } },
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
    widthUnits: "common", // world-space width so ribbons scale with zoom, not screen pixels
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

  const linkCount = linkPositions.length / 4;
  if (linkCount === 0) return [ribbons];

  const links = new PathLayer({
    id: "links",
    data: {
      length: linkCount,
      startIndices: linkStartIndices(linkCount),
      attributes: { getPath: { value: linkPositions, size: 2 } },
    } as unknown as [],
    _pathType: "open",
    positionFormat: "XY",
    getColor: [90, 100, 120, 150],
    getWidth: 1,
    widthUnits: "common",
    widthMinPixels: 0.5,
    pickable: false,
  });

  // links under ribbons
  return [links, ribbons];
}

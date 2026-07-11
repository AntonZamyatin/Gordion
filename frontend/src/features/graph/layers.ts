import { PathLayer } from "@deck.gl/layers";

import type { Scene } from "../../lib/sceneCodec";
import { type RibbonPaths, PORT_ZONE_FRAC } from "./ribbonGeometry";

const HOVER_COLOR: [number, number, number, number] = [255, 208, 0, 255];
const SELECT_COLOR: [number, number, number, number] = [255, 255, 255, 255];

// Hover zone highlight colour: which part of a vertex a plain drag would grab (light yellow).
const ZONE_MOVE_COLOR: [number, number, number, number] = [255, 240, 150, 235]; // central → translate
const ZONE_ROTATE_COLOR: [number, number, number, number] = [255, 240, 150, 235]; // end → rotate

export type HoverZone = { contig: number; zone: 0 | 1 | 2 };

// The stretch of a contig's sampled path that the given zone covers (sample index range).
function zoneSamples(K: number, zone: 0 | 1 | 2): [number, number] {
  const e = Math.max(1, Math.round(K * PORT_ZONE_FRAC));
  if (zone === 0) return [0, e];
  if (zone === 2) return [K - 1 - e, K - 1];
  return [e, K - 1 - e];
}

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
  hoverZone: HoverZone | null,
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

  // Hover zone highlight: the sub-segment of the hovered ribbon a plain drag would grab, in the
  // move/rotate colour. Non-pickable and drawn on top so it doesn't intercept picks.
  let highlight: PathLayer | null = null;
  if (hoverZone && hoverZone.contig < n) {
    const { contig: i, zone } = hoverZone;
    const K = paths.samples;
    const off = paths.startIndices[i] * 2; // float offset of contig i's first sample
    const [s0, s1] = zoneSamples(K, zone);
    const cnt = s1 - s0 + 1;
    const seg = new Float32Array(cnt * 2);
    for (let s = 0; s < cnt; s++) {
      seg[s * 2] = paths.positions[off + (s0 + s) * 2];
      seg[s * 2 + 1] = paths.positions[off + (s0 + s) * 2 + 1];
    }
    highlight = new PathLayer({
      id: "zone-highlight",
      data: {
        length: 1,
        startIndices: new Uint32Array([0, cnt]),
        attributes: { getPath: { value: seg, size: 2 } },
      } as unknown as [],
      _pathType: "open",
      positionFormat: "XY",
      getColor: zone === 1 ? ZONE_MOVE_COLOR : ZONE_ROTATE_COLOR,
      getWidth: scene.contigWidth[i] * 2.2,
      widthUnits: "common",
      widthMinPixels: 3,
      widthMaxPixels: 90,
      capRounded: true,
      jointRounded: true,
      pickable: false,
      updateTriggers: { getPath: [i, zone] },
    });
  }

  const linkCount = linkPositions.length / 4;
  const links =
    linkCount === 0
      ? null
      : new PathLayer({
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

  // links under ribbons, hover highlight on top
  return [links, ribbons, highlight].filter((l): l is PathLayer => l !== null);
}

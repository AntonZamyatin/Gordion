// Phase 1 + 2 spike: deck.gl PathLayer performance/picking, and viewing real
// SGD layouts.
//
// Two modes:
//   (default)      ~200k synthetic ribbons  -> perf + picking de-risk (Phase 1)
//   ?scene=/scene.json   a real GFA layout produced by the Phase 2 driver
//
// A "ribbon" is a 2-point path (IN -> OUT) with per-path width and color, fed to
// deck.gl as a binary typed-array attribute (mirrors the planned scene contract).

import { Deck, OrthographicView } from '@deck.gl/core';
import { PathLayer } from '@deck.gl/layers';

const params = new URLSearchParams(location.search);
const hud = document.getElementById('hud')!;

type Ribbons = {
  count: number;
  positions: Float32Array; // [inX,inY,outX,outY] per ribbon
  widths: Float32Array; // per ribbon
  colors: Uint8Array; // RGBA per ribbon
  startIndices: Uint32Array; // [0,2,4,...]
  bbox: [number, number, number, number];
};

function startIndicesFor(count: number): Uint32Array {
  const s = new Uint32Array(count + 1);
  for (let i = 0; i <= count; i++) s[i] = i * 2;
  return s;
}

function bboxOf(positions: Float32Array, count: number): [number, number, number, number] {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (let i = 0; i < count; i++) {
    const x0 = positions[i * 4], y0 = positions[i * 4 + 1];
    const x1 = positions[i * 4 + 2], y1 = positions[i * 4 + 3];
    if (x0 < minX) minX = x0; if (x1 < minX) minX = x1;
    if (y0 < minY) minY = y0; if (y1 < minY) minY = y1;
    if (x0 > maxX) maxX = x0; if (x1 > maxX) maxX = x1;
    if (y0 > maxY) maxY = y0; if (y1 > maxY) maxY = y1;
  }
  return [minX, minY, maxX, maxY];
}

// ---------------------------------------------------------------------------
function makeSynthetic(n: number): Ribbons {
  const positions = new Float32Array(n * 4);
  const widths = new Float32Array(n);
  const colors = new Uint8Array(n * 4);
  const cols = Math.ceil(Math.sqrt(n));
  const spacing = 20;
  const frac = (x: number) => x - Math.floor(x);
  for (let i = 0; i < n; i++) {
    const gx = (i % cols) * spacing;
    const gy = Math.floor(i / cols) * spacing;
    const ang = frac(Math.sin(i * 12.9898) * 43758.5453) * Math.PI * 2;
    const len = 6 + frac(Math.sin(i * 78.233) * 12345.678) * 12;
    positions[i * 4] = gx;
    positions[i * 4 + 1] = gy;
    positions[i * 4 + 2] = gx + Math.cos(ang) * len;
    positions[i * 4 + 3] = gy + Math.sin(ang) * len;
    widths[i] = 1 + (i % 8);
    colors[i * 4] = 60 + ((i * 53) % 195);
    colors[i * 4 + 1] = 60 + ((i * 97) % 195);
    colors[i * 4 + 2] = 60 + ((i * 29) % 195);
    colors[i * 4 + 3] = 255;
  }
  return {
    count: n,
    positions,
    widths,
    colors,
    startIndices: startIndicesFor(n),
    bbox: bboxOf(positions, n),
  };
}

async function loadScene(url: string): Promise<{ ribbons: Ribbons; links: Float32Array }> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetch ${url}: ${res.status}`);
  const s = await res.json();
  const count: number = s.contigCount;
  const positions = new Float32Array(s.contigs.positions);
  const widths = new Float32Array(s.contigs.width);
  const colors = new Uint8Array(s.contigs.color);
  const links = new Float32Array(s.links?.positions ?? []);
  const bbox: [number, number, number, number] = s.bbox ?? bboxOf(positions, count);
  return { ribbons: { count, positions, widths, colors, startIndices: startIndicesFor(count), bbox }, links };
}

// ---------------------------------------------------------------------------
function ribbonLayer(r: Ribbons, onPick: (kind: 'hover' | 'click', i: number | null) => void) {
  return new PathLayer({
    id: 'ribbons',
    data: {
      length: r.count,
      startIndices: r.startIndices,
      attributes: { getPath: { value: r.positions, size: 2 } },
    } as unknown as [],
    _pathType: 'open',
    positionFormat: 'XY',
    getColor: (_o: unknown, info: { index: number }) => {
      const j = info.index * 4;
      return [r.colors[j], r.colors[j + 1], r.colors[j + 2], r.colors[j + 3]];
    },
    getWidth: (_o: unknown, info: { index: number }) => r.widths[info.index],
    widthUnits: 'pixels',
    widthMinPixels: 1,
    widthMaxPixels: 40,
    capRounded: true,
    jointRounded: true,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 208, 0, 255],
    onHover: (info) => onPick('hover', info.index),
    onClick: (info) => onPick('click', info.index),
  });
}

function linkLayer(links: Float32Array) {
  const count = links.length / 4;
  return new PathLayer({
    id: 'links',
    data: {
      length: count,
      startIndices: startIndicesFor(count),
      attributes: { getPath: { value: links, size: 2 } },
    } as unknown as [],
    _pathType: 'open',
    positionFormat: 'XY',
    getColor: [90, 100, 120, 160],
    getWidth: 1,
    widthUnits: 'pixels',
    widthMinPixels: 0.5,
    pickable: false,
  });
}

// ---------------------------------------------------------------------------
(async function main() {
  const sceneUrl = params.get('scene');
  let ribbons: Ribbons;
  let links: Float32Array = new Float32Array(0);
  let label: string;

  if (sceneUrl) {
    const loaded = await loadScene(sceneUrl);
    ribbons = loaded.ribbons;
    links = loaded.links;
    label = `scene ${sceneUrl}`;
  } else {
    const n = Number(params.get('n')) || 200_000;
    ribbons = makeSynthetic(n);
    label = `synthetic`;
  }

  const [minX, minY, maxX, maxY] = ribbons.bbox;
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const extent = Math.max(maxX - minX, maxY - minY) || 1;
  const viewportGuess = Math.min(window.innerWidth, window.innerHeight) * 0.9;
  const initialZoom = Math.log2(viewportGuess / extent);

  let picked = 'hover: (none)';
  const setPicked = (kind: 'hover' | 'click', index: number | null) => {
    if (index == null || index < 0) {
      if (kind === 'hover') picked = 'hover: (none)';
      return;
    }
    const j = index * 4;
    picked =
      `${kind}: contig #${index}  width=${ribbons.widths[index].toFixed(1)}px  ` +
      `rgb(${ribbons.colors[j]},${ribbons.colors[j + 1]},${ribbons.colors[j + 2]})`;
  };

  const layers = links.length ? [linkLayer(links), ribbonLayer(ribbons, setPicked)] : [ribbonLayer(ribbons, setPicked)];

  new Deck({
    parent: document.getElementById('app') as HTMLDivElement,
    views: new OrthographicView({ flipY: false }),
    initialViewState: { target: [cx, cy, 0], zoom: initialZoom },
    controller: true,
    layers,
  });

  let frames = 0;
  let last = performance.now();
  let fps = 0;
  const tick = () => {
    frames++;
    const now = performance.now();
    if (now - last >= 500) {
      fps = (frames * 1000) / (now - last);
      frames = 0;
      last = now;
    }
    hud.textContent =
      `${label}   ribbons: ${ribbons.count.toLocaleString()}   links: ${(links.length / 4).toLocaleString()}\n` +
      `fps (rAF): ${fps.toFixed(0)}\n` +
      `${picked}\n` +
      `drag = pan · wheel = zoom · hover/click a ribbon`;
    requestAnimationFrame(tick);
  };
  tick();
})();

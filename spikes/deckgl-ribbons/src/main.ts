// Phase 1 spike: prove deck.gl PathLayer performance + picking at ~200k ribbons.
//
// A "ribbon" here is a 2-point path (IN -> OUT) with a per-path width and color,
// mirroring the eventual scene contract (binary typed-array columns). Positions
// are fed to deck.gl as a *binary* attribute (the representative zero-copy path);
// width/color use index-based accessors over per-path typed arrays.
//
// Goal: eyeball smooth pan/zoom at scale and confirm picking returns the right
// ribbon. Override the count with ?n=500000 in the URL to push harder.

import { Deck, OrthographicView } from '@deck.gl/core';
import { PathLayer } from '@deck.gl/layers';

const N = Number(new URLSearchParams(location.search).get('n')) || 200_000;

// ----------------------------------------------------------------------------
// Synthetic scene: a jittered grid of short, randomly-oriented ribbons.
// Deterministic (no Math.random) so runs are comparable.
// ----------------------------------------------------------------------------
const positions = new Float32Array(N * 4); // [inX, inY, outX, outY] per ribbon
const widths = new Float32Array(N);
const colors = new Uint8Array(N * 4); // RGBA per ribbon
const startIndices = new Uint32Array(N + 1); // vertex offsets: [0, 2, 4, ...]

const cols = Math.ceil(Math.sqrt(N));
const spacing = 20;

let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

const frac = (x: number) => x - Math.floor(x);

for (let i = 0; i < N; i++) {
  const gx = (i % cols) * spacing;
  const gy = Math.floor(i / cols) * spacing;

  // deterministic pseudo-random angle + length
  const ang = frac(Math.sin(i * 12.9898) * 43758.5453) * Math.PI * 2;
  const len = 6 + frac(Math.sin(i * 78.233) * 12345.678) * 12; // 6..18

  const x0 = gx;
  const y0 = gy;
  const x1 = gx + Math.cos(ang) * len;
  const y1 = gy + Math.sin(ang) * len;

  positions[i * 4] = x0;
  positions[i * 4 + 1] = y0;
  positions[i * 4 + 2] = x1;
  positions[i * 4 + 3] = y1;

  widths[i] = 1 + (i % 8); // 1..8 px

  colors[i * 4] = 60 + ((i * 53) % 195);
  colors[i * 4 + 1] = 60 + ((i * 97) % 195);
  colors[i * 4 + 2] = 60 + ((i * 29) % 195);
  colors[i * 4 + 3] = 255;

  startIndices[i] = i * 2;

  if (x0 < minX) minX = x0; if (x1 < minX) minX = x1;
  if (y0 < minY) minY = y0; if (y1 < minY) minY = y1;
  if (x0 > maxX) maxX = x0; if (x1 > maxX) maxX = x1;
  if (y0 > maxY) maxY = y0; if (y1 > maxY) maxY = y1;
}
startIndices[N] = N * 2;

// ----------------------------------------------------------------------------
// Fit the view to the generated extent.
// Orthographic zoom z: 1 world unit == 2^z pixels.
// ----------------------------------------------------------------------------
const cx = (minX + maxX) / 2;
const cy = (minY + maxY) / 2;
const extent = Math.max(maxX - minX, maxY - minY) || 1;
const viewportGuess = Math.min(window.innerWidth, window.innerHeight) * 0.9;
const initialZoom = Math.log2(viewportGuess / extent);

const layer = new PathLayer({
  id: 'ribbons',
  data: {
    length: N,
    startIndices,
    attributes: {
      getPath: { value: positions, size: 2 },
    },
  } as unknown as [], // binary-data form; deck's TS types expect an array
  _pathType: 'open',
  positionFormat: 'XY',
  getColor: (_object: unknown, info: { index: number }) => {
    const j = info.index * 4;
    return [colors[j], colors[j + 1], colors[j + 2], colors[j + 3]];
  },
  getWidth: (_object: unknown, info: { index: number }) => widths[info.index],
  widthUnits: 'pixels',
  widthMinPixels: 1,
  widthMaxPixels: 40,
  capRounded: true,
  jointRounded: true,
  pickable: true,
  autoHighlight: true,
  highlightColor: [255, 208, 0, 255],
});

// ----------------------------------------------------------------------------
// HUD
// ----------------------------------------------------------------------------
const hud = document.getElementById('hud')!;
let picked = 'hover: (none)';

function renderHud(fps: number) {
  hud.textContent =
    `ribbons: ${N.toLocaleString()}   vertices: ${(N * 2).toLocaleString()}\n` +
    `fps (rAF): ${fps.toFixed(0)}\n` +
    `${picked}\n` +
    `drag = pan · wheel = zoom · hover/click a ribbon`;
}

function setPicked(kind: 'hover' | 'click', index: number | null) {
  if (index == null || index < 0) {
    if (kind === 'hover') picked = 'hover: (none)';
    return;
  }
  const j = index * 4;
  picked =
    `${kind}: ribbon #${index}  width=${widths[index].toFixed(1)}px  ` +
    `rgb(${colors[j]},${colors[j + 1]},${colors[j + 2]})`;
}

// ----------------------------------------------------------------------------
// Deck
// ----------------------------------------------------------------------------
new Deck({
  parent: document.getElementById('app') as HTMLDivElement,
  views: new OrthographicView({ flipY: false }),
  initialViewState: { target: [cx, cy, 0], zoom: initialZoom },
  controller: true,
  layers: [layer],
  onHover: (info) => setPicked('hover', info.index),
  onClick: (info) => setPicked('click', info.index),
});

// rAF-based fps proxy: drops when the main thread saturates.
let frames = 0;
let last = performance.now();
let fps = 0;
function tick() {
  frames++;
  const now = performance.now();
  if (now - last >= 500) {
    fps = (frames * 1000) / (now - last);
    frames = 0;
    last = now;
  }
  renderHud(fps);
  requestAnimationFrame(tick);
}
tick();
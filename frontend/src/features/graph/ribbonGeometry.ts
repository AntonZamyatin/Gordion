// Render-time ribbon geometry: turn each contig's straight IN->OUT segment into a
// smooth curved path, and repel overlapping midpoints so parallel contigs (bubbles)
// open into clear bulges.
//
// This is purely a rendering concern — the SGD layout positions (scene.contigPositions)
// are never modified. We reduce the 2D problem to a signed scalar OFFSET per contig
// along its own perpendicular: overlapping parallel ribbons get pushed to opposite
// offsets, so they bow apart into a lens-shaped bulge. A contig with no crowding keeps
// offset ~0 and stays a straight line.
//
// Pipeline:
//   computeBulgeOffsets(scene)  -> Float32Array offsets (run once per scene; O(N) via grid)
//   buildRibbonPaths(scene, offsets, overrides) -> { positions, startIndices }  (cheap; rerun on drag)

import type { Scene } from "../../lib/sceneCodec";

export type BulgeParams = {
  radiusFactor: number; // repulsion radius as a multiple of mean chord length
  strength: number; // per-iteration push (fraction of radius)
  damping: number; // fraction of accumulated push applied each iteration
  iterations: number;
  maxOffsetFrac: number; // cap |offset| as a fraction of the contig's chord length
  overlapFrac: number; // only repel if along-chord separation < this * chord length
  samples: number; // points sampled along each curved ribbon (>= 2)
};

export const DEFAULT_BULGE: BulgeParams = {
  radiusFactor: 0.45,
  strength: 0.14,
  damping: 0.5,
  iterations: 40,
  maxOffsetFrac: 0.15,
  overlapFrac: 0.5,
  samples: 12,
};

type Chords = {
  n: number;
  midX: Float32Array;
  midY: Float32Array;
  perpX: Float32Array; // unit perpendicular to the chord
  perpY: Float32Array;
  len: Float32Array; // chord length
  meanLen: number;
};

function chordsOf(p: Float32Array, n: number): Chords {
  const midX = new Float32Array(n);
  const midY = new Float32Array(n);
  const perpX = new Float32Array(n);
  const perpY = new Float32Array(n);
  const len = new Float32Array(n);
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const x0 = p[i * 4], y0 = p[i * 4 + 1], x1 = p[i * 4 + 2], y1 = p[i * 4 + 3];
    const dx = x1 - x0, dy = y1 - y0;
    const l = Math.hypot(dx, dy) || 1e-6;
    midX[i] = (x0 + x1) * 0.5;
    midY[i] = (y0 + y1) * 0.5;
    // perpendicular = chord rotated 90°, normalized
    perpX[i] = -dy / l;
    perpY[i] = dx / l;
    len[i] = l;
    sum += l;
  }
  return { n, midX, midY, perpX, perpY, len, meanLen: n ? sum / n : 1 };
}

// Uniform spatial hash grid over the (displaced) midpoints, so repulsion is O(N) with a
// bounded number of neighbor checks instead of O(N^2).
class Grid {
  private cell: number;
  private buckets = new Map<number, number[]>();
  constructor(cell: number) {
    this.cell = cell > 0 ? cell : 1;
  }
  private key(cx: number, cy: number): number {
    // pack two 16-bit-ish cell coords; fine for our extents
    return (cx * 73856093) ^ (cy * 19349663);
  }
  insert(i: number, x: number, y: number): void {
    const cx = Math.floor(x / this.cell), cy = Math.floor(y / this.cell);
    const k = this.key(cx, cy);
    const b = this.buckets.get(k);
    if (b) b.push(i);
    else this.buckets.set(k, [i]);
  }
  neighbors(x: number, y: number, out: number[]): void {
    out.length = 0;
    const cx = Math.floor(x / this.cell), cy = Math.floor(y / this.cell);
    for (let gx = cx - 1; gx <= cx + 1; gx++) {
      for (let gy = cy - 1; gy <= cy + 1; gy++) {
        const b = this.buckets.get(this.key(gx, gy));
        if (b) for (let m = 0; m < b.length; m++) out.push(b[m]);
      }
    }
  }
}

// Curve/bulge repulsion offsets, computed from the *current* port positions (not the SGD
// seed), so during a force-layout drag the ribbons bulge apart live as the neighbourhood
// reflows. `positions` is the effective [inX,inY,outX,outY]-per-contig buffer.
export function computeBulgeOffsets(
  positions: Float32Array,
  n: number,
  params: BulgeParams = DEFAULT_BULGE,
): Float32Array {
  const c = chordsOf(positions, n);
  const offset = new Float32Array(n); // always from zero: this is what lets a contig with no
                                      // crowding relax straight (the model has no pull-to-zero term)
  if (n === 0) return offset;

  const R = Math.max(c.meanLen * params.radiusFactor, 1e-6);
  const R2 = R * R;
  const push = params.strength * R;
  const neigh: number[] = [];

  for (let it = 0; it < params.iterations; it++) {
    // displaced midpoints for this iteration
    const dx = new Float32Array(n);
    const dy = new Float32Array(n);
    const grid = new Grid(R);
    for (let i = 0; i < n; i++) {
      const mx = c.midX[i] + offset[i] * c.perpX[i];
      const my = c.midY[i] + offset[i] * c.perpY[i];
      dx[i] = mx;
      dy[i] = my;
      grid.insert(i, mx, my);
    }
    const delta = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      grid.neighbors(dx[i], dy[i], neigh);
      let acc = 0;
      for (let m = 0; m < neigh.length; m++) {
        const j = neigh[m];
        if (j === i) continue;
        let vx = dx[i] - dx[j];
        let vy = dy[i] - dy[j];
        let d2 = vx * vx + vy * vy;
        if (d2 >= R2) continue;
        // Weight by how parallel the two chords are: bubbles (parallel, overlapping)
        // repel strongly; ribbons that merely cross are left alone.
        const align = Math.abs(c.perpX[i] * c.perpX[j] + c.perpY[i] * c.perpY[j]);
        if (align < 0.2) continue;
        // Skip contigs that are merely sequential along the same axis (a straight
        // backbone chain) rather than stacked over each other (a bubble): those have
        // a large along-chord separation. Tangent of i is (perpY, -perpX).
        const along = vx * c.perpY[i] + vy * -c.perpX[i];
        if (Math.abs(along) > params.overlapFrac * c.len[i]) continue;
        if (d2 < 1e-9) {
          // coincident midpoints (a perfect bubble): split the pair to opposite sides
          // deterministically by index order so they never stay stacked.
          acc += push * align * (i > j ? 1 : -1);
          continue;
        }
        const d = Math.sqrt(d2);
        const falloff = 1 - d / R;
        // project the separating direction onto i's offset axis (its perpendicular)
        const proj = (vx / d) * c.perpX[i] + (vy / d) * c.perpY[i];
        acc += push * align * falloff * proj;
      }
      delta[i] = acc;
    }
    // apply with damping + clamp to a fraction of each chord
    for (let i = 0; i < n; i++) {
      let o = offset[i] + params.damping * delta[i];
      const cap = params.maxOffsetFrac * c.len[i];
      if (o > cap) o = cap;
      else if (o < -cap) o = -cap;
      offset[i] = o;
    }
  }
  return offset;
}

// Frozen background of every *non-active* contig, for a local bulge pass. A force-drag only
// moves the contigs in its k-ring (the `active` set); everyone else holds still for the whole
// gesture, so we snapshot them once at drag start into a grid of their displaced midpoints.
// The active contigs then repel against this background as well as each other, which is what
// makes the mid-drag curvature equal the full pass — so nothing snaps on release. R/push use
// the WHOLE-graph mean chord, identical to computeBulgeOffsets, so the two agree.
export type BulgeBackground = {
  R: number;
  R2: number;
  push: number;
  grid: Grid;
  bx: Float32Array; // displaced midpoint X of each background contig
  by: Float32Array;
  bpx: Float32Array; // unit perpendicular X
  bpy: Float32Array;
  idx: Int32Array; // actual contig index (for the deterministic coincident tiebreak)
};

export function buildBulgeBackground(
  positions: Float32Array,
  n: number,
  activeSet: Set<number>,
  offsets: Float32Array,
  params: BulgeParams = DEFAULT_BULGE,
): BulgeBackground {
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const dx = positions[i * 4 + 2] - positions[i * 4];
    const dy = positions[i * 4 + 3] - positions[i * 4 + 1];
    sum += Math.hypot(dx, dy) || 1e-6;
  }
  const meanLen = n ? sum / n : 1; // whole-graph mean chord → same R as computeBulgeOffsets
  const R = Math.max(meanLen * params.radiusFactor, 1e-6);
  const push = params.strength * R;
  const bCount = Math.max(0, n - activeSet.size);
  const bx = new Float32Array(bCount), by = new Float32Array(bCount);
  const bpx = new Float32Array(bCount), bpy = new Float32Array(bCount);
  const idx = new Int32Array(bCount);
  const grid = new Grid(R);
  let w = 0;
  for (let i = 0; i < n; i++) {
    if (activeSet.has(i)) continue;
    const x0 = positions[i * 4], y0 = positions[i * 4 + 1];
    const x1 = positions[i * 4 + 2], y1 = positions[i * 4 + 3];
    const dx = x1 - x0, dy = y1 - y0;
    const l = Math.hypot(dx, dy) || 1e-6;
    const px = -dy / l, py = dx / l;
    const o = offsets[i] ?? 0;
    const mx = (x0 + x1) * 0.5 + o * px, my = (y0 + y1) * 0.5 + o * py;
    bx[w] = mx; by[w] = my; bpx[w] = px; bpy[w] = py; idx[w] = i;
    grid.insert(w, mx, my);
    w++;
  }
  return { R, R2: R * R, push, grid, bx, by, bpx, bpy, idx };
}

// Local bulge update: recompute the curve-repulsion offset for just the `active` contigs (the
// ones a drag moves), leaving every other contig's offset untouched. They repel against each
// other AND — when a `bg` is supplied — against the frozen background of stationary contigs,
// so the mid-drag curvature already matches the full pass and doesn't jump on release. Cost is
// O(active · iterations), independent of graph size. Mutates `offsets` in place.
export function localBulgeUpdate(
  offsets: Float32Array,
  positions: Float32Array,
  active: number[],
  params: BulgeParams = DEFAULT_BULGE,
  bg?: BulgeBackground | null,
): void {
  const A = active.length;
  if (A === 0) return;
  const midX = new Float32Array(A), midY = new Float32Array(A);
  const perpX = new Float32Array(A), perpY = new Float32Array(A);
  const len = new Float32Array(A);
  let sum = 0;
  for (let a = 0; a < A; a++) {
    const i = active[a];
    const x0 = positions[i * 4], y0 = positions[i * 4 + 1];
    const x1 = positions[i * 4 + 2], y1 = positions[i * 4 + 3];
    const dx = x1 - x0, dy = y1 - y0;
    const l = Math.hypot(dx, dy) || 1e-6;
    midX[a] = (x0 + x1) * 0.5; midY[a] = (y0 + y1) * 0.5;
    perpX[a] = -dy / l; perpY[a] = dx / l; len[a] = l; sum += l;
  }
  const meanLen = sum / A;
  const R = bg ? bg.R : Math.max(meanLen * params.radiusFactor, 1e-6);
  const R2 = bg ? bg.R2 : R * R;
  const push = bg ? bg.push : params.strength * R;
  // Start from zero each call (do NOT accumulate the previous frame's offsets): the model has no
  // pull-to-zero term, so accumulating would (a) never let a contig straighten once its neighbours
  // leave, and (b) over-converge relative to the from-zero release pass and snap on release. A
  // fresh 40-iter relaxation here matches computeBulgeOffsets exactly.
  const off = new Float32Array(A);
  const neigh: number[] = [];
  const bneigh: number[] = [];
  for (let it = 0; it < params.iterations; it++) {
    const dxA = new Float32Array(A), dyA = new Float32Array(A);
    const grid = new Grid(R);
    for (let a = 0; a < A; a++) {
      const mx = midX[a] + off[a] * perpX[a], my = midY[a] + off[a] * perpY[a];
      dxA[a] = mx; dyA[a] = my; grid.insert(a, mx, my);
    }
    const delta = new Float32Array(A);
    for (let a = 0; a < A; a++) {
      let acc = 0;
      // active <-> active (live)
      grid.neighbors(dxA[a], dyA[a], neigh);
      for (let m = 0; m < neigh.length; m++) {
        const b = neigh[m];
        if (b === a) continue;
        const vx = dxA[a] - dxA[b], vy = dyA[a] - dyA[b];
        const d2 = vx * vx + vy * vy;
        if (d2 >= R2) continue;
        const align = Math.abs(perpX[a] * perpX[b] + perpY[a] * perpY[b]);
        if (align < 0.2) continue;
        const along = vx * perpY[a] + vy * -perpX[a];
        if (Math.abs(along) > params.overlapFrac * len[a]) continue;
        if (d2 < 1e-9) {
          acc += push * align * (active[a] > active[b] ? 1 : -1);
          continue;
        }
        const d = Math.sqrt(d2);
        const falloff = 1 - d / R;
        const proj = (vx / d) * perpX[a] + (vy / d) * perpY[a];
        acc += push * align * falloff * proj;
      }
      // active <-> stationary background (frozen at drag start)
      if (bg) {
        bg.grid.neighbors(dxA[a], dyA[a], bneigh);
        for (let m = 0; m < bneigh.length; m++) {
          const b = bneigh[m];
          const vx = dxA[a] - bg.bx[b], vy = dyA[a] - bg.by[b];
          const d2 = vx * vx + vy * vy;
          if (d2 >= R2) continue;
          const align = Math.abs(perpX[a] * bg.bpx[b] + perpY[a] * bg.bpy[b]);
          if (align < 0.2) continue;
          const along = vx * perpY[a] + vy * -perpX[a];
          if (Math.abs(along) > params.overlapFrac * len[a]) continue;
          if (d2 < 1e-9) {
            acc += push * align * (active[a] > bg.idx[b] ? 1 : -1);
            continue;
          }
          const d = Math.sqrt(d2);
          const falloff = 1 - d / R;
          const proj = (vx / d) * perpX[a] + (vy / d) * perpY[a];
          acc += push * align * falloff * proj;
        }
      }
      delta[a] = acc;
    }
    for (let a = 0; a < A; a++) {
      let o = off[a] + params.damping * delta[a];
      const cap = params.maxOffsetFrac * len[a];
      if (o > cap) o = cap;
      else if (o < -cap) o = -cap;
      off[a] = o;
    }
  }
  for (let a = 0; a < A; a++) offsets[active[a]] = off[a];
}

// User edits layered on top of the SGD layout (all render-time; never sent back).
//   portOverrides:   keyed by portKey = contigIndex*2 + side (0=IN, 1=OUT) -> [dx,dy]
//   curveOverrides:  contigIndex -> extra signed bulge offset, as a fraction of chord
//                     length, added on top of the auto-repulsion offset (+/- keys)
export type Edits = {
  portOverrides: Map<number, [number, number]>;
};

export const portKey = (contig: number, side: number): number => contig * 2 + side;

// Grab zones along a vertex's chord: the outer PORT_ZONE_FRAC at each end is a port (rotate)
// zone, the middle is the central (translate) zone. Shared by the drag hit-test (grabZone in
// DeckCanvas) and the hover highlight (buildLayers) so they always agree.
export const PORT_ZONE_FRAC = 1 / 6;

// Final [inX,inY,outX,outY] per contig after applying port drags. This single source of
// truth is used for BOTH the ribbon curves and the link geometry, so links always stay
// attached to the ports they were computed from. `base` defaults to the raw SGD layout,
// but the interactive force layout passes its relaxed positions in as the base instead.
export function effectivePorts(scene: Scene, edits: Edits | null, base?: Float32Array): Float32Array {
  const out = new Float32Array(base ?? scene.contigPositions); // copy of the base layout
  if (!edits) return out;
  edits.portOverrides.forEach(([dx, dy], key) => {
    const i = key >> 1;
    const off = i * 4 + (key & 1) * 2;
    out[off] += dx;
    out[off + 1] += dy;
  });
  return out;
}

// Manual curvature nudges from +/- (contigIndex -> signed fraction of chord length).
// Kept separate from the auto-repulsion offsets so it survives bulge param tweaks.
export type CurveOverrides = Map<number, number>;
export const CURVE_STEP = 0.15; // fraction of chord length added/removed per keypress
export const CURVE_CAP = 3; // generous clamp — this is a deliberate user override

export type RibbonPaths = {
  positions: Float32Array; // flat XY, samples points per contig
  startIndices: Uint32Array; // length n+1
  samples: number;
};

// Build one curved path per contig from its (effective) endpoints + bulge offset. A
// quadratic Bézier whose control point sits at 2*offset along the perpendicular makes
// the curve peak pass through the displaced midpoint. Because perp/mid are recomputed
// from the effective endpoints, dragging a port reshapes the curvature live.
export function buildRibbonPaths(
  ports: Float32Array,
  n: number,
  offsets: Float32Array,
  params: BulgeParams = DEFAULT_BULGE,
  curveOverrides?: CurveOverrides,
): RibbonPaths {
  const K = Math.max(2, params.samples);
  const positions = new Float32Array(n * K * 2);
  const startIndices = new Uint32Array(n + 1);

  for (let i = 0; i < n; i++) {
    startIndices[i] = i * K;
    const x0 = ports[i * 4], y0 = ports[i * 4 + 1], x1 = ports[i * 4 + 2], y1 = ports[i * 4 + 3];
    const mx = (x0 + x1) * 0.5, my = (y0 + y1) * 0.5;
    const dx = x1 - x0, dy = y1 - y0;
    const l = Math.hypot(dx, dy) || 1e-6;
    const px = -dy / l, py = dx / l;
    const manual = curveOverrides?.get(i) ?? 0;
    const o = (offsets[i] ?? 0) + manual * l;
    // control point: peak passes through mid + o*perp  =>  ctrl = mid + 2*o*perp
    const cx = mx + 2 * o * px;
    const cy = my + 2 * o * py;
    const base = i * K * 2;
    for (let s = 0; s < K; s++) {
      const t = s / (K - 1);
      const mt = 1 - t;
      // quadratic Bézier B(t) = mt^2 P0 + 2 mt t C + t^2 P2
      positions[base + s * 2] = mt * mt * x0 + 2 * mt * t * cx + t * t * x1;
      positions[base + s * 2 + 1] = mt * mt * y0 + 2 * mt * t * cy + t * t * y1;
    }
  }
  startIndices[n] = n * K;
  return { positions, startIndices, samples: K };
}

// Link segments recomputed from current port positions (so edges follow dragged ports).
// Falls back to the baked coordinates when the scene predates linkEndpoints.
export function buildLinkPositions(scene: Scene, ports: Float32Array): Float32Array {
  const ep = scene.linkEndpoints;
  if (!ep || ep.length === 0) return scene.linkPositions;
  const out = new Float32Array(ep.length); // [x0,y0,x1,y1] per link, same count
  for (let k = 0; k < ep.length; k += 4) {
    const a = ep[k], sa = ep[k + 1], b = ep[k + 2], sb = ep[k + 3];
    out[k] = ports[a * 4 + sa * 2];
    out[k + 1] = ports[a * 4 + sa * 2 + 1];
    out[k + 2] = ports[b * 4 + sb * 2];
    out[k + 3] = ports[b * 4 + sb * 2 + 1];
  }
  return out;
}

// Client-side interactive force layout, applied ONLY while dragging (never on file load).
//
// The backend SGD positions (scene.contigPositions) are the seed and the resting layout;
// a drag relaxes a *local region* under a small force model and returns new port positions
// in the same [inX,inY,outX,outY]-per-contig layout, so it drops straight into
// effectivePorts()/the ribbon geometry. Nothing here is ever sent back to the backend —
// it's a render-time layer exactly like port drags and bulge, and the protected SGD solver
// is untouched.
//
// Port graph (reconstructed from the scene):
//   - 2 nodes per contig: IN (side 0) and OUT (side 1). Node key = contig*2 + side,
//     matching portKey() in ribbonGeometry. Positions live at contig*4 + side*2 in the
//     flat [inX,inY,outX,outY] buffer.
//   - internal edge  IN<->OUT of the same contig, rest length = its current chord
//     length (current-geometry rest lengths — preserve each contig's own extent).
//   - external edge  from each GFA link, joining the two connected ports.
//
// Force model:
//   1. rigid length      — each contig is a rigid rod: after every force step its two ports
//      constraint          are projected back to the contig's exact rest length, so a plain
//                          drag rotates/translates a vertex but NEVER stretches it. The only
//                          way to change a vertex's length is Ctrl-dragging one of its ports
//                          (that moves a single port directly, outside this relaxation).
//   2. port spring       — a Hookean spring between the two ports of a connection with a
//                          fixed default rest length (`edgeLength` × mean chord), so each
//                          junction opens to a set gap rather than collapsing to a point.
//                          A per-link rest-length override (from the store) replaces that
//                          default for links the user has tuned; the ONLY way to set an
//                          override is Ctrl-dragging a port, which pins that link's rest
//                          length to the resulting port-to-port distance.
//   3. junction          — spreads all contigs meeting at a junction apart, evenly, length-
//      straightening       independent. For each junction we take every incident contig's
//                          outward unit axis (junction port -> far port) and their mean
//                          direction `m`, then push each free contig's far port by k·(dI − m).
//                          This is one *resultant* per junction over all its contigs at once
//                          (not pairwise), so a 2-way junction goes straight, a branch fans
//                          out, and no two links fight over the same node. Zero force once the
//                          directions are balanced (Σ dI = 0).
//   4. general repulsion — short-range, grid-based; keeps unrelated ribbons from piling up.

import type { Scene } from "../../lib/sceneCodec";

export type ForceParams = {
  enabled: boolean; // master switch for force-assisted dragging (Ctrl / selection drags)
  portAttract: number; // stiffness of the connection spring pulling two ports to its rest length
  edgeLength: number; // default connection-spring rest length, × mean chord (per-link override via Ctrl-drag)
  portRepel: number; // junction-straightening strength: aligns both contigs onto a shared line (× mean chord)
  generalRepel: number; // short-range repulsion strength (× mean chord)
  repelRadius: number; // general-repulsion radius as a multiple of mean chord
  iterations: number; // relaxation passes per drag event
  damping: number; // fraction of each step applied (stability)
  dragLayers: number; // k: how many contig-hops of neighbourhood a selection drag relaxes
};

export const DEFAULT_FORCE: ForceParams = {
  enabled: true,
  portAttract: 10, // stiff spring — junctions snap firmly to their rest length
  edgeLength: 0.02, // connected ports settle ~0.02 mean-chord apart by default (tight junctions)
  portRepel: 0.36, // junction straightening / branch fan-out
  generalRepel: 0.1,
  repelRadius: 1.2,
  iterations: 12,
  damping: 0.1,
  dragLayers: 6,
};

// Node key helpers (mirror portKey): node = contig*2 + side; position at contig*4+side*2.
const posOff = (node: number): number => (node >> 1) * 4 + (node & 1) * 2;

export type PortGraph = {
  nodeCount: number; // 2 * contigCount
  contigCount: number;
  // external edges (links): parallel arrays of the two node keys
  linkA: Int32Array;
  linkB: Int32Array;
  // internal edge rest lengths, per contig (chord length of the seed)
  internalRest: Float32Array;
  meanChord: number;
  // contig -> contig adjacency (via links), CSR-style for BFS
  adjStart: Int32Array; // length contigCount+1
  adjList: Int32Array;
  // contig -> incident link ids, CSR-style (lets a drag gather its local links without
  // scanning every link in the graph)
  linkAdjStart: Int32Array; // length contigCount+1
  linkAdjList: Int32Array;
  // Junctions: maximal clusters of ports glued together by links (a meeting point where any
  // number of contig ends coincide). Straightening spreads all of a junction's contigs at once
  // (the resultant over every incident contig), instead of aligning each link's pair on its own.
  junctionOf: Int32Array; // node key -> junction id, or -1 for a port with no links
  junctionStart: Int32Array; // CSR: length junctionCount+1
  junctionPorts: Int32Array; // CSR payload: the node keys in each junction
};

// Build the port graph once per scene (memoize in the caller).
export function buildPortGraph(scene: Scene): PortGraph {
  const n = scene.contigCount;
  const p = scene.contigPositions;

  const internalRest = new Float32Array(n);
  let chordSum = 0;
  for (let i = 0; i < n; i++) {
    const dx = p[i * 4 + 2] - p[i * 4], dy = p[i * 4 + 3] - p[i * 4 + 1];
    const l = Math.hypot(dx, dy);
    internalRest[i] = l;
    chordSum += l;
  }
  const meanChord = n ? chordSum / n : 1;

  const ep = scene.linkEndpoints;
  const linkCount = ep.length >> 2;
  const linkA = new Int32Array(linkCount);
  const linkB = new Int32Array(linkCount);
  // degree count for CSR contig adjacency
  const deg = new Int32Array(n);
  for (let k = 0, e = 0; k < ep.length; k += 4, e++) {
    linkA[e] = ep[k] * 2 + ep[k + 1]; // node key = contig*2 + side
    linkB[e] = ep[k + 2] * 2 + ep[k + 3];
    const ca = ep[k], cb = ep[k + 2];
    if (ca !== cb) {
      deg[ca]++;
      deg[cb]++;
    }
  }
  const adjStart = new Int32Array(n + 1);
  for (let i = 0; i < n; i++) adjStart[i + 1] = adjStart[i] + deg[i];
  const adjList = new Int32Array(adjStart[n]);
  const cursor = adjStart.slice(0, n);
  for (let k = 0; k < ep.length; k += 4) {
    const ca = ep[k], cb = ep[k + 2];
    if (ca !== cb) {
      adjList[cursor[ca]++] = cb;
      adjList[cursor[cb]++] = ca;
    }
  }

  // contig -> incident link ids (each link touches both endpoint contigs).
  const linkDeg = new Int32Array(n);
  for (let e = 0; e < linkCount; e++) {
    const ca = linkA[e] >> 1, cb = linkB[e] >> 1;
    linkDeg[ca]++;
    if (cb !== ca) linkDeg[cb]++;
  }
  const linkAdjStart = new Int32Array(n + 1);
  for (let i = 0; i < n; i++) linkAdjStart[i + 1] = linkAdjStart[i] + linkDeg[i];
  const linkAdjList = new Int32Array(linkAdjStart[n]);
  const lcursor = linkAdjStart.slice(0, n);
  for (let e = 0; e < linkCount; e++) {
    const ca = linkA[e] >> 1, cb = linkB[e] >> 1;
    linkAdjList[lcursor[ca]++] = e;
    if (cb !== ca) linkAdjList[lcursor[cb]++] = e;
  }

  // Junction clusters: union-find over ports (nodes), joined by every link. Each resulting
  // cluster is one junction; ports with no link stay isolated (junctionOf = -1).
  const nodeCount = n * 2;
  const parent = new Int32Array(nodeCount);
  for (let i = 0; i < nodeCount; i++) parent[i] = i;
  const find = (x: number): number => {
    while (parent[x] !== x) x = parent[x] = parent[parent[x]];
    return x;
  };
  const hasLink = new Uint8Array(nodeCount);
  for (let e = 0; e < linkCount; e++) {
    hasLink[linkA[e]] = 1;
    hasLink[linkB[e]] = 1;
    const ra = find(linkA[e]), rb = find(linkB[e]);
    if (ra !== rb) parent[ra] = rb;
  }
  const junctionOf = new Int32Array(nodeCount).fill(-1);
  const rootId = new Map<number, number>();
  let jCount = 0;
  for (let pnode = 0; pnode < nodeCount; pnode++) {
    if (!hasLink[pnode]) continue;
    const r = find(pnode);
    let id = rootId.get(r);
    if (id === undefined) rootId.set(r, (id = jCount++));
    junctionOf[pnode] = id;
  }
  const jDeg = new Int32Array(jCount);
  for (let pnode = 0; pnode < nodeCount; pnode++) if (junctionOf[pnode] >= 0) jDeg[junctionOf[pnode]]++;
  const junctionStart = new Int32Array(jCount + 1);
  for (let j = 0; j < jCount; j++) junctionStart[j + 1] = junctionStart[j] + jDeg[j];
  const junctionPorts = new Int32Array(junctionStart[jCount]);
  const jcur = junctionStart.slice(0, jCount);
  for (let pnode = 0; pnode < nodeCount; pnode++) {
    const j = junctionOf[pnode];
    if (j >= 0) junctionPorts[jcur[j]++] = pnode;
  }

  return {
    nodeCount: n * 2,
    contigCount: n,
    linkA,
    linkB,
    internalRest,
    meanChord,
    adjStart,
    adjList,
    linkAdjStart,
    linkAdjList,
    junctionOf,
    junctionStart,
    junctionPorts,
  };
}

// Uniform spatial hash for the short-range general repulsion (O(N) per pass).
class Grid {
  private cell: number;
  private buckets = new Map<number, number[]>();
  constructor(cell: number) {
    this.cell = cell > 0 ? cell : 1;
  }
  private key(cx: number, cy: number): number {
    return (cx * 73856093) ^ (cy * 19349663);
  }
  insert(i: number, x: number, y: number): void {
    const k = this.key(Math.floor(x / this.cell), Math.floor(y / this.cell));
    const b = this.buckets.get(k);
    if (b) b.push(i);
    else this.buckets.set(k, [i]);
  }
  neighbors(x: number, y: number, out: number[]): void {
    out.length = 0;
    const cx = Math.floor(x / this.cell), cy = Math.floor(y / this.cell);
    for (let gx = cx - 1; gx <= cx + 1; gx++)
      for (let gy = cy - 1; gy <= cy + 1; gy++) {
        const b = this.buckets.get(this.key(gx, gy));
        if (b) for (let m = 0; m < b.length; m++) out.push(b[m]);
      }
  }
}

// BFS from `seeds` over contig adjacency, returning every contig within `maxDepth` hops
// (inclusive of the seeds at depth 0). This is the region a drag is allowed to touch.
export function bfsWithin(pg: PortGraph, seeds: Iterable<number>, maxDepth: number): Set<number> {
  const depth = new Map<number, number>();
  const queue: number[] = [];
  for (const s of seeds) {
    if (!depth.has(s)) {
      depth.set(s, 0);
      queue.push(s);
    }
  }
  for (let qi = 0; qi < queue.length; qi++) {
    const c = queue[qi];
    const d = depth.get(c)!;
    if (d >= maxDepth) continue;
    for (let a = pg.adjStart[c]; a < pg.adjStart[c + 1]; a++) {
      const nb = pg.adjList[a];
      if (!depth.has(nb)) {
        depth.set(nb, d + 1);
        queue.push(nb);
      }
    }
  }
  return new Set(depth.keys());
}

// Compact description of the contigs a drag may relax (the "region"), built ONCE per drag
// gesture so the per-event relaxation never walks the whole graph. `links` are only the
// links incident to some region contig; endpoints outside the region are read from the
// position buffer as fixed anchors. Individual ports inside the region can still be pinned
// (see relaxLocal's `pinned` map) — that's how a dragged port / a moved selection is held.
export type LocalSim = {
  region: Int32Array; // contigs that relax
  localIndex: Map<number, number>; // contig -> index in `region`
  links: Int32Array; // local link ids
};

export function buildLocalSim(pg: PortGraph, region: Iterable<number>): LocalSim {
  const list: number[] = [...region];
  const localIndex = new Map<number, number>();
  list.forEach((c, i) => localIndex.set(c, i));
  const seen = new Set<number>();
  const links: number[] = [];
  for (const c of list) {
    for (let a = pg.linkAdjStart[c]; a < pg.linkAdjStart[c + 1]; a++) {
      const lid = pg.linkAdjList[a];
      if (!seen.has(lid)) {
        seen.add(lid);
        links.push(lid);
      }
    }
  }
  return {
    region: Int32Array.from(list),
    localIndex,
    links: Int32Array.from(links),
  };
}

// Relax ONLY the region for a few iterations, in place. Cost is O(region + local links) per
// iteration — independent of total graph size. `pos` is mutated. Ports listed in `pinned`
// are held at the given positions (a dragged port, or every port of a rigidly-moved
// selection); every other region port relaxes; contigs outside the region are fixed anchors.
export function relaxLocal(
  pg: PortGraph,
  pos: Float32Array,
  sim: LocalSim,
  pinned: Map<number, [number, number]>, // portKey -> position
  params: ForceParams,
  iterations: number,
  linkRest?: Map<number, number> | null, // linkId -> absolute rest length (Ctrl-drag overrides)
): void {
  // hold pinned ports at their target positions
  pinned.forEach(([x, y], key) => {
    const o = posOff(key);
    pos[o] = x; pos[o + 1] = y;
  });

  const A = sim.region.length;
  const fx = new Float32Array(A * 2);
  const fy = new Float32Array(A * 2);
  const mc = pg.meanChord;
  const step = Math.max(0.01, Math.min(1, params.damping)) * 0.5;
  const R = Math.max(mc * params.repelRadius, 1e-6);
  const R2 = R * R;
  const genStrength = params.generalRepel * mc;
  const defRest = params.edgeLength * mc; // default connection-spring rest length
  const neigh: number[] = [];
  // local force slot for a node key, or -1 if the node's contig isn't in the region.
  const slotOf = (node: number): number => {
    const li = sim.localIndex.get(node >> 1);
    return li === undefined ? -1 : li * 2 + (node & 1);
  };
  const k = params.portRepel * mc; // junction-straightening strength

  // Junctions touched by any local link — straightening is computed once per junction (over
  // all its contigs), so gather the distinct ids up front. Fixed for the whole gesture.
  const jset = new Set<number>();
  for (let li = 0; li < sim.links.length; li++) {
    const j = pg.junctionOf[pg.linkA[sim.links[li]]];
    if (j >= 0) jset.add(j);
  }
  const junctions = Int32Array.from(jset);

  for (let it = 0; it < iterations; it++) {
    fx.fill(0);
    fy.fill(0);

    // 1. rigid length constraint is enforced *after* integration (see projection below), not
    //    as a force — so vertices never stretch under a plain drag.

    // 2. port spring (rest = per-link override or default)
    for (let li = 0; li < sim.links.length; li++) {
      const e = sim.links[li];
      const na = pg.linkA[e], nb = pg.linkB[e];
      const aO = posOff(na), bO = posOff(nb);
      const dx = pos[bO] - pos[aO], dy = pos[bO + 1] - pos[aO + 1];
      const dist = Math.hypot(dx, dy) || 1e-6;
      const rest = linkRest?.get(e) ?? defRest;
      const f = (params.portAttract * (dist - rest)) / dist; // pull toward rest length
      const sa = slotOf(na), sb = slotOf(nb);
      if (sa >= 0) { fx[sa] += f * dx; fy[sa] += f * dy; }
      if (sb >= 0) { fx[sb] -= f * dx; fy[sb] -= f * dy; }
    }

    // 3. junction straightening (one resultant per junction, over ALL its contigs at once).
    // Take the mean outward unit direction of every contig meeting at the junction, then push
    // each *free* contig's far port away from that mean → 2-way junctions go straight, branches
    // fan out evenly, and links sharing a node no longer fight each other.
    if (k > 0) {
      for (let ji = 0; ji < junctions.length; ji++) {
        const jid = junctions[ji];
        const s0 = pg.junctionStart[jid], s1 = pg.junctionStart[jid + 1];
        let mx = 0, my = 0, cnt = 0;
        for (let s = s0; s < s1; s++) {
          const near = pg.junctionPorts[s], far = near ^ 1;
          const nO = posOff(near), fO = posOff(far);
          const dx = pos[fO] - pos[nO], dy = pos[fO + 1] - pos[nO + 1];
          const dl = Math.hypot(dx, dy) || 1e-6;
          mx += dx / dl; my += dy / dl; cnt++;
        }
        if (cnt < 2) continue;
        mx /= cnt; my /= cnt; // mean outward direction at this junction
        for (let s = s0; s < s1; s++) {
          const near = pg.junctionPorts[s], far = near ^ 1;
          const slot = slotOf(far);
          if (slot < 0) continue; // this contig is anchored / outside the region
          const nO = posOff(near), fO = posOff(far);
          const dx = pos[fO] - pos[nO], dy = pos[fO + 1] - pos[nO + 1];
          const dl = Math.hypot(dx, dy) || 1e-6;
          fx[slot] += k * (dx / dl - mx); // push this contig's axis away from the mean
          fy[slot] += k * (dy / dl - my);
        }
      }
    }

    // 4. general repulsion over the region nodes only (local grid)
    if (params.generalRepel > 0) {
      const grid = new Grid(R);
      for (let i = 0; i < A; i++) {
        const c = sim.region[i];
        grid.insert(i * 2, pos[c * 4], pos[c * 4 + 1]);
        grid.insert(i * 2 + 1, pos[c * 4 + 2], pos[c * 4 + 3]);
      }
      for (let s = 0; s < A * 2; s++) {
        const cs = sim.region[s >> 1];
        const off = cs * 4 + (s & 1) * 2;
        const x = pos[off], y = pos[off + 1];
        grid.neighbors(x, y, neigh);
        for (let m = 0; m < neigh.length; m++) {
          const j = neigh[m];
          if (j === s) continue;
          const cj = sim.region[j >> 1];
          const joff = cj * 4 + (j & 1) * 2;
          const vx = x - pos[joff], vy = y - pos[joff + 1];
          const d2 = vx * vx + vy * vy;
          if (d2 >= R2 || d2 < 1e-12) continue;
          const d = Math.sqrt(d2);
          const falloff = (1 - d / R) / d;
          fx[s] += genStrength * falloff * vx;
          fy[s] += genStrength * falloff * vy;
        }
      }
    }

    // apply to region ports that aren't pinned
    for (let i = 0; i < A; i++) {
      const c = sim.region[i];
      if (!pinned.has(c * 2)) {
        pos[c * 4] += step * fx[i * 2];
        pos[c * 4 + 1] += step * fy[i * 2];
      }
      if (!pinned.has(c * 2 + 1)) {
        pos[c * 4 + 2] += step * fx[i * 2 + 1];
        pos[c * 4 + 3] += step * fy[i * 2 + 1];
      }
    }

    // rigid length projection: pull each region contig's two ports back onto its exact rest
    // length, so the port forces can rotate/translate a vertex but never resize it. A pinned
    // port stays put and the free one takes the whole correction; both free → split evenly.
    for (let i = 0; i < A; i++) {
      const c = sim.region[i];
      const inO = c * 4, outO = c * 4 + 2;
      const vx = pos[outO] - pos[inO], vy = pos[outO + 1] - pos[inO + 1];
      const d = Math.hypot(vx, vy) || 1e-6;
      const corr = (d - pg.internalRest[c]) / d; // >0: too long, pull ports together
      const inPinned = pinned.has(c * 2), outPinned = pinned.has(c * 2 + 1);
      if (inPinned && outPinned) continue; // both held → can't (and shouldn't) correct
      if (inPinned) {
        pos[outO] -= corr * vx; pos[outO + 1] -= corr * vy;
      } else if (outPinned) {
        pos[inO] += corr * vx; pos[inO + 1] += corr * vy;
      } else {
        const h = 0.5 * corr;
        pos[inO] += h * vx; pos[inO + 1] += h * vy;
        pos[outO] -= h * vx; pos[outO + 1] -= h * vy;
      }
    }
  }
}

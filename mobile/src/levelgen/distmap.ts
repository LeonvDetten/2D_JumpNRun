// Port of jumpnrun/levelgen/distmap.py: path distance to the chest for every place the player can stand.
// Feeds the bot's progress features, the par time estimate and the solver's guidance.

import { ROWS, TILE, fdiv } from "../core/constants";
import type { Level } from "../core/level";
import { JUMP_CATALOG } from "./generator";

const FALL_DRIFT = 1;

/** (gap, drop) pairs the bot can make from a standing start (sorted like Python's sorted(set)). */
function buildJumps(): [number, number][] {
  const pairs = new Map<string, [number, number]>();
  for (const j of JUMP_CATALOG) pairs.set(`${j.gap},${j.drop}`, [j.gap, j.drop]);
  const deepest = Math.max(...[...pairs.values()].map(([, d]) => d));
  for (const [gap, drop] of [...pairs.values()]) {
    if (drop === deepest) for (let d = drop + 1; d < ROWS; d++) pairs.set(`${gap},${d}`, [gap, d]);
  }
  return [...pairs.values()].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
}
export const JUMPS = buildJumps();

/** Binary min-heap of [priority, payload] pairs. */
export class MinHeap<T> {
  private keys: number[] = [];
  private vals: T[] = [];

  get size(): number {
    return this.keys.length;
  }

  push(key: number, val: T): void {
    const keys = this.keys;
    const vals = this.vals;
    let i = keys.length;
    keys.push(key);
    vals.push(val);
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (keys[p] <= key) break;
      keys[i] = keys[p];
      vals[i] = vals[p];
      i = p;
    }
    keys[i] = key;
    vals[i] = val;
  }

  pop(): [number, T] | undefined {
    const keys = this.keys;
    const vals = this.vals;
    if (!keys.length) return undefined;
    const topK = keys[0];
    const topV = vals[0];
    const lastK = keys.pop()!;
    const lastV = vals.pop()!;
    const n = keys.length;
    if (n) {
      let i = 0;
      for (;;) {
        let c = 2 * i + 1;
        if (c >= n) break;
        if (c + 1 < n && keys[c + 1] < keys[c]) c++;
        if (keys[c] >= lastK) break;
        keys[i] = keys[c];
        vals[i] = vals[c];
        i = c;
      }
      keys[i] = lastK;
      vals[i] = lastV;
    }
    return [topK, topV];
  }
}

export class DistanceMap {
  readonly cols: number;
  /** stand[r * cols + c] = 1: an empty tile with a block below. */
  readonly stand: Uint8Array;
  /** Remaining way in tiles per cell (NaN = no way to the chest). */
  readonly dist: Float64Array;
  readonly reachable: boolean;
  start: number | null = null;
  private readonly edges: { v: number; cost: number }[][];

  constructor(readonly level: Level) {
    const cols = (this.cols = level.cols);
    const solid = level.solid;
    this.stand = new Uint8Array(cols * ROWS);
    for (let c = 0; c < cols; c++) {
      for (let r = 0; r < ROWS - 1; r++) if (!solid[r][c] && solid[r + 1][c]) this.stand[r * cols + c] = 1;
    }
    this.edges = Array.from({ length: cols * ROWS }, () => []);
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < cols; c++) if (this.stand[r * cols + c]) this.moves(c, r);
    this.dist = new Float64Array(cols * ROWS).fill(NaN);
    const targets = this.targets();
    this.reachable = targets.length > 0;
    if (targets.length) this.dijkstra(targets);
    if (this.reachable) {
      const [x, y] = level.spawn;
      this.start = this.atXY(x, y, 40, 60);
      if (this.start === null) this.start = this.below(x, y, 40, 60);
    }
  }

  isStand(c: number, r: number): boolean {
    return c >= 0 && c < this.cols && r >= 0 && r < ROWS && this.stand[r * this.cols + c] === 1;
  }

  distAt(c: number, r: number): number | null {
    if (c < 0 || c >= this.cols || r < 0 || r >= ROWS) return null;
    const d = this.dist[r * this.cols + c];
    return Number.isNaN(d) ? null : d;
  }

  /** Moves from cell index u (row * cols + col) with their costs. */
  edgesOf(u: number): readonly { v: number; cost: number }[] {
    return this.edges[u] ?? [];
  }

  free(c: number, r: number): boolean {
    if (c < 0 || c >= this.cols) return false;
    return r < 0 || (r < ROWS && !this.level.solid[r][c]);
  }

  private add(uc: number, ur: number, vc: number, vr: number, cost: number): void {
    if (this.isStand(vc, vr) && (vc !== uc || vr !== ur)) this.edges[ur * this.cols + uc].push({ v: vr * this.cols + vc, cost });
  }

  /** Row where a player falling in `col` from body row `row` comes to stand (null = pit). */
  private fallFrom(col: number, row: number): number | null {
    let r = row;
    while (r < ROWS - 1) {
      if (!this.free(col, r)) return null;
      if (!this.free(col, r + 1)) return r;
      r += 1;
    }
    return null;
  }

  private moves(c: number, r: number): void {
    const free = (cc: number, rr: number) => this.free(cc, rr);
    for (const d of [-1, 1]) {
      const n = c + d;
      if (!free(n, r)) {
        if (free(c, r - 1) && this.isStand(n, r - 1) && free(c, r - 2) && free(n, r - 2)) this.add(c, r, n, r - 1, 1.3);
        continue;
      }
      if (this.isStand(n, r)) this.add(c, r, n, r, 1.0);
      else {
        for (let k = 0; k <= FALL_DRIFT; k++) {
          const col = n + d * k;
          if (k && !(free(col, r) && free(col, r + 1))) break;
          const land = this.fallFrom(col, r);
          if (land !== null) this.add(c, r, col, land, 1.0 + k + 0.3 * (land - r));
        }
      }
      if (!free(c, r - 1)) continue;
      for (const [gap, drop] of JUMPS) {
        const lc = c + d * (gap + 1);
        const lr = r + drop;
        if (!this.isStand(lc, lr)) continue;
        let ok: boolean;
        if (drop < 0) {
          ok = free(c, r - 2);
          for (let k = 1; ok && k <= gap; k++) {
            for (const rr of [r - 2, r - 1, r]) if (!free(c + d * k, rr)) ok = false;
          }
          ok = ok && free(lc, r - 2) && free(lc, r - 1);
        } else {
          ok = true;
          for (let k = 1; ok && k <= gap; k++) {
            for (const rr of [r - 1, r]) if (!free(c + d * k, rr)) ok = false;
          }
          for (let rr = r - 1; ok && rr <= lr; rr++) if (!free(lc, rr)) ok = false;
        }
        if (ok) this.add(c, r, lc, lr, gap + 1 + 0.3 * Math.abs(drop));
      }
    }
  }

  private targets(): number[] {
    const out: number[] = [];
    for (const [cx, cy] of this.level.chests) {
      const col = fdiv(cx, TILE);
      const row = Math.min(ROWS - 1, fdiv(cy, TILE));
      for (let c = col - 1; c < col + 2; c++) if (this.isStand(c, row)) out.push(row * this.cols + c);
    }
    return out;
  }

  private dijkstra(targets: number[]): void {
    const back: { u: number; cost: number }[][] = Array.from({ length: this.edges.length }, () => []);
    this.edges.forEach((out, u) => {
      for (const { v, cost } of out) back[v].push({ u, cost });
    });
    const dist = this.dist;
    const heap = new MinHeap<number>();
    for (const t of targets) {
      dist[t] = 0.0;
      heap.push(0.0, t);
    }
    while (heap.size) {
      const [d, v] = heap.pop()!;
      if (d > (Number.isNaN(dist[v]) ? Infinity : dist[v])) continue;
      for (const { u, cost } of back[v]) {
        const nd = d + cost;
        if (nd < (Number.isNaN(dist[u]) ? Infinity : dist[u])) {
          dist[u] = nd;
          heap.push(nd, u);
        }
      }
    }
  }

  /** Distance for a body at (x, y, w, h) standing on something; null if unknown. */
  atXY(x: number, y: number, w: number, h: number): number | null {
    const row = fdiv(y + h - 1, TILE);
    let best: number | null = null;
    for (const col of [fdiv(x + fdiv(w, 2), TILE), fdiv(x, TILE), fdiv(x + w - 1, TILE)]) {
      const d = this.distAt(col, row);
      if (d !== null && (best === null || d < best)) best = d;
    }
    return best;
  }

  /** Distance of the first standing place below a body in the air (null over a pit). */
  below(x: number, y: number, w: number, h: number): number | null {
    const col = fdiv(x + fdiv(w, 2), TILE);
    for (let row = Math.max(0, fdiv(y + h - 1, TILE)); row < ROWS - 1; row++) {
      if (this.isStand(col, row)) return this.distAt(col, row);
      if (col >= 0 && col < this.cols ? this.level.solid[row][col] : true) return null;
    }
    return null;
  }

  atPlayer(p: { onGround: boolean; x: number; y: number; w: number; h: number }): number | null {
    if (!p.onGround) return null;
    return this.atXY(p.x, p.y, p.w, p.h);
  }
}

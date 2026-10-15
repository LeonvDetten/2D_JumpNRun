// Port of jumpnrun/levelgen/solver.py (solve, way_cells, solve_path_legs): weighted A* over the real simulation.
// A found solution is a real, replayable action list; "not solved" can mean "search budget too small".

import { BOT_ACTIONS_V3, type Action } from "../core/actions";
import { PLAYER_SPEED, TILE, fdiv } from "../core/constants";
import type { Level } from "../core/level";
import { Simulation, Status } from "../core/sim";
import { DistanceMap } from "./distmap";

export interface SolveResult {
  solved: boolean;
  actions: number[] | null;
  expanded: number;
  maxX: number;
}

function stateKey(sim: Simulation): string {
  const p = sim.player;
  let nearby = "";
  for (const e of sim.enemies) {
    if (Math.abs(e.x - p.x) < 300 && Math.abs(e.y - p.y) < 240) nearby += `|${fdiv(e.x, 30)},${fdiv(e.y, 30)},${e.direction}`;
  }
  return `${fdiv(p.x, 8)},${fdiv(p.y, 6)},${p.vy},${p.shootCooldown > 0 ? 1 : 0},${sim.enemies.length}${nearby}`;
}

/** Min-heap ordered by (priority, insertion counter), like Python's heapq with a counter tie-break. */
class Frontier {
  private prio: number[] = [];
  private seq: number[] = [];
  private ids: number[] = [];
  private sims: Simulation[] = [];
  private counter = 0;

  get size(): number {
    return this.prio.length;
  }

  private less(i: number, j: number): boolean {
    return this.prio[i] < this.prio[j] || (this.prio[i] === this.prio[j] && this.seq[i] < this.seq[j]);
  }

  private swap(i: number, j: number): void {
    [this.prio[i], this.prio[j]] = [this.prio[j], this.prio[i]];
    [this.seq[i], this.seq[j]] = [this.seq[j], this.seq[i]];
    [this.ids[i], this.ids[j]] = [this.ids[j], this.ids[i]];
    [this.sims[i], this.sims[j]] = [this.sims[j], this.sims[i]];
  }

  push(priority: number, id: number, sim: Simulation): void {
    this.prio.push(priority);
    this.seq.push(this.counter++);
    this.ids.push(id);
    this.sims.push(sim);
    let i = this.prio.length - 1;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (!this.less(i, p)) break;
      this.swap(i, p);
      i = p;
    }
  }

  pop(): [number, Simulation] {
    const id = this.ids[0];
    const sim = this.sims[0];
    const last = this.prio.length - 1;
    this.swap(0, last);
    this.prio.pop();
    this.seq.pop();
    this.ids.pop();
    this.sims.pop();
    let i = 0;
    const n = this.prio.length;
    for (;;) {
      const l = 2 * i + 1;
      const r = l + 1;
      let m = i;
      if (l < n && this.less(l, m)) m = l;
      if (r < n && this.less(r, m)) m = r;
      if (m === i) break;
      this.swap(i, m);
      i = m;
    }
    return [id, sim];
  }
}

export interface SolveOptions {
  maxExpansions?: number;
  actionRepeat?: number;
  weight?: number;
  start?: Simulation | null;
  /** Stand on top of tile (col, row) instead of reaching the chest. */
  goal?: [number, number] | null;
  dm?: DistanceMap | null;
  actions?: readonly Action[];
  goalDist?: number | null;
}

export function solve(level: Level, opts: SolveOptions = {}): SolveResult {
  const maxExpansions = opts.maxExpansions ?? 200_000;
  const repeat = opts.actionRepeat ?? 2;
  const weight = opts.weight ?? 1.5;
  const goal = opts.goal ?? null;
  const dm = opts.dm ?? null;
  const actions = opts.actions ?? BOT_ACTIONS_V3;
  const root = opts.start ? opts.start.clone() : new Simulation(level);
  const targetX = goal === null ? level.goalX : goal[0] * TILE + fdiv(TILE, 2);
  const targetY = goal === null ? null : goal[1] * TILE;

  const reached = (sim: Simulation): boolean => {
    if (goal === null) return sim.status === Status.WON;
    const p = sim.player;
    return p.onGround && p.y + p.h === targetY && Math.abs(p.x + fdiv(p.w, 2) - targetX) <= TILE;
  };
  const useDm = dm !== null && dm.reachable && (goal === null || (opts.goalDist !== null && opts.goalDist !== undefined));
  const offset = opts.goalDist ?? 0;
  const pathH = (sim: Simulation, parentH: number): number => {
    const p = sim.player;
    const d = p.onGround ? dm!.atPlayer(p) : dm!.below(p.x, p.y, p.w, p.h);
    return d === null ? parentH : Math.max(0, d - offset) * TILE;
  };
  const priority = (sim: Simulation, h: number | null): number => {
    const p = sim.player;
    if (h !== null) return sim.frame + (weight * h) / PLAYER_SPEED;
    const remaining = targetY === null ? Math.max(0, targetX - p.x) : Math.abs(targetX - p.x - fdiv(p.w, 2)) + Math.abs(targetY - p.y - p.h);
    return sim.frame + (weight * remaining) / PLAYER_SPEED;
  };

  const parents = [-1];
  const via = [-1];
  const hs = [useDm ? pathH(root, Math.max(0, (dm!.start ?? 0) - offset) * TILE) : 0];
  const heap = new Frontier();
  heap.push(priority(root, useDm ? hs[0] : null), 0, root);
  const seen = new Set([stateKey(root)]);
  let expanded = 0;
  let bestX = root.player.x;

  while (heap.size && expanded < maxExpansions) {
    const [nodeId, sim] = heap.pop();
    expanded += 1;
    for (let ai = 0; ai < actions.length; ai++) {
      const child = sim.clone();
      const status = child.step(actions[ai], repeat);
      if (status === Status.DIED_PIT || status === Status.DIED_ENEMY) continue;
      parents.push(nodeId);
      via.push(ai);
      hs.push(useDm ? pathH(child, hs[nodeId]) : 0);
      let childId = parents.length - 1;
      if (reached(child)) {
        const path: number[] = [];
        while (childId > 0) {
          path.push(via[childId]);
          childId = parents[childId];
        }
        path.reverse();
        return { solved: true, actions: path, expanded, maxX: child.player.x };
      }
      if (status === Status.WON) continue;
      const key = stateKey(child);
      if (seen.has(key)) continue;
      seen.add(key);
      bestX = Math.max(bestX, child.player.x);
      heap.push(priority(child, useDm ? hs[childId] : null), childId, child);
    }
  }
  return { solved: false, actions: null, expanded, maxX: bestX };
}

/** Cells of the shortest way from `startCell` to the chest (following the distance map). */
export function wayCells(dm: DistanceMap, startCell: number): number[] {
  const out = [startCell];
  let u = startCell;
  const dist = (c: number) => (Number.isNaN(dm.dist[c]) ? 1e9 : dm.dist[c]);
  while ((Number.isNaN(dm.dist[u]) ? 0 : dm.dist[u]) > 0.5 && out.length < 5000) {
    let best: { v: number; cost: number } | null = null;
    for (const e of dm.edgesOf(u)) if (best === null || e.cost + dist(e.v) < best.cost + dist(best.v)) best = e;
    if (best === null || dist(best.v) >= dm.dist[u]) break;
    u = best.v;
    out.push(u);
  }
  return out;
}

export interface LegOptions {
  legTiles?: number;
  legBudget?: number;
  totalBudget?: number;
  actionRepeat?: number;
  weight?: number;
  start?: Simulation | null;
  onLeg?: (actions: number[]) => void;
}

/** Long / winding levels leg by leg: goals are cells on the distance-map way every `legTiles` tiles. */
export function solvePathLegs(level: Level, opts: LegOptions = {}): SolveResult {
  const legTiles = opts.legTiles ?? 18;
  const legBudget = opts.legBudget ?? 40_000;
  const totalBudget = opts.totalBudget ?? 800_000;
  const repeat = opts.actionRepeat ?? 2;
  const weight = opts.weight ?? 1.2;
  const dm = new DistanceMap(level);
  if (!dm.reachable) return { solved: false, actions: null, expanded: 0, maxX: 0 };
  const sim = opts.start ? opts.start.clone() : new Simulation(level);
  const p = sim.player;
  let hereDist = dm.start ?? 0;
  if (opts.start) {
    const d = p.onGround ? dm.atPlayer(p) : dm.below(p.x, p.y, p.w, p.h);
    if (d !== null) hereDist = d;
  }
  let here: number | null = null;
  let hereScore = Infinity;
  for (let r = 0; r < 13; r++) {
    for (let c = 0; c < dm.cols; c++) {
      const d = dm.distAt(c, r);
      if (d === null || Math.abs(c * TILE + fdiv(TILE, 2) - (p.x + fdiv(p.w, 2))) > TILE) continue;
      const score = Math.abs(d - hereDist);
      if (score < hereScore) {
        hereScore = score;
        here = r * dm.cols + c;
      }
    }
  }
  const cells = here !== null ? wayCells(dm, here) : [];
  const goals: number[] = [];
  let last = hereDist;
  for (const c of cells.slice(1)) {
    if (last - dm.dist[c] >= legTiles) {
      goals.push(c);
      last = dm.dist[c];
    }
  }
  const actions: number[] = [];
  let expanded = 0;
  for (const goal of [...goals, null]) {
    const budget = Math.min(goal !== null ? legBudget : 3 * legBudget, totalBudget - expanded);
    if (budget <= 0) break;
    let leg: SolveResult;
    if (goal === null) leg = solve(level, { maxExpansions: budget, actionRepeat: repeat, weight, start: sim, dm });
    else {
      const gc = goal % dm.cols;
      const gr = Math.floor(goal / dm.cols);
      leg = solve(level, { maxExpansions: budget, actionRepeat: repeat, weight, start: sim, goal: [gc, gr + 1], dm, goalDist: dm.dist[goal] });
    }
    expanded += leg.expanded;
    if (!leg.solved) {
      if (goal === null) return { solved: false, actions: null, expanded, maxX: Math.max(sim.player.x, leg.maxX) };
      continue;
    }
    for (const a of leg.actions!) sim.step(BOT_ACTIONS_V3[a], repeat);
    actions.push(...leg.actions!);
    opts.onLeg?.([...actions]);
  }
  const won = sim.status === Status.WON;
  return { solved: won, actions: won ? actions : null, expanded, maxX: sim.player.x };
}

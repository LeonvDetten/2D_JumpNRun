// Port of the parts of jumpnrun/rl/env.py (JumpNRunEnv) that the trained bot needs to play:
// the v3 observation with overview map, and the "stuck" / time-budget counters (progress along the way).
// Parity with Python: tests/bot.test.ts compares observation hashes and the network's logits.

import { BOT_ACTIONS_V3 } from "../core/actions";
import { MAX_FALL_SPEED, ROWS, SHOOT_COOLDOWN, TILE, fdiv } from "../core/constants";
import type { Level } from "../core/level";
import { Simulation, Status } from "../core/sim";
import { DistanceMap } from "../levelgen/distmap";

export const GRID_CHANNELS = 4;
export const VIEW_BEHIND = 13; // v3
export const VIEW_AHEAD = 19;
export const VIEW_COLS = VIEW_BEHIND + 1 + VIEW_AHEAD; // 33
export const VEC_SIZE = 23;
export const OV_BEHIND = 40;
export const OV_COLS = 40;
export const OV_SCALE = 4;
export const OV_CHANNELS = 4;
const NEAREST_ENEMIES = 3;
const NO_PROGRESS_FRAMES = 600;
const PATH_TIME_FACTOR = 1.2;
const MAX_FRAMES_PER_TILE = 12.0;

export interface Observation {
  grid: Float32Array; // (4, 13, 33)
  vec: Float32Array; // (23,)
  overview: Float32Array; // (4, 13, 40)
}

export class BotEnv {
  readonly actionRepeat: number;
  sim!: Simulation;
  private readonly maxStepsPerTile: number;
  private readonly noProgressSteps: number;
  private padL = 0;
  private staticW = 0;
  private staticGrid!: Float32Array; // (2, ROWS, staticW)
  private ovPad = 0;
  private ovW = 0;
  private ovStatic!: Float32Array; // (3, ROWS, ovW)
  private dm: DistanceMap | null = null;
  steps = 0;
  stepsSinceProgress = 0;
  maxSteps = 0;
  bestDist: number | null = null;

  constructor(readonly level: Level, actionRepeat = 2) {
    this.actionRepeat = actionRepeat;
    this.maxStepsPerTile = MAX_FRAMES_PER_TILE / actionRepeat;
    this.noProgressSteps = Math.floor(NO_PROGRESS_FRAMES / actionRepeat);
    this.setLevel(level);
  }

  reset(): Observation {
    this.sim = new Simulation(this.level);
    this.beginEpisode();
    return this.observe();
  }

  private beginEpisode(): void {
    const level = this.level;
    this.steps = 0;
    this.stepsSinceProgress = 0;
    this.maxSteps = Math.trunc(level.cols * this.maxStepsPerTile) + Math.floor(200 / this.actionRepeat);
    this.bestDist = null;
    this.dm ??= new DistanceMap(level);
    const p = this.sim.player;
    let here = this.dm.reachable ? this.dm.atXY(p.x, p.y, p.w, p.h) : null;
    if (here === null && this.dm.reachable) here = this.dm.start;
    this.bestDist = here;
    if (here !== null) {
      const tiles = Math.max(level.cols, Math.ceil(PATH_TIME_FACTOR * here));
      this.maxSteps = Math.trunc(tiles * this.maxStepsPerTile) + Math.floor(200 / this.actionRepeat);
    }
  }

  /** One bot decision: hold the action for `actionRepeat` frames. */
  step(action: number): { obs: Observation; terminated: boolean; truncated: boolean } {
    const before = this.sim.maxX;
    this.sim.step(BOT_ACTIONS_V3[action], this.actionRepeat);
    return this.finishStep(before);
  }

  /** Bookkeeping after the frames of one decision (split from step so the racer can go frame by frame). */
  finishStep(maxXBefore: number): { obs: Observation; terminated: boolean; truncated: boolean } {
    const sim = this.sim;
    const status = sim.status;
    this.steps += 1;
    let gained: number;
    if (this.bestDist !== null) {
      gained = 0;
      const here = this.dm!.atPlayer(sim.player);
      if (here !== null && here < this.bestDist) {
        gained = this.bestDist - here;
        this.bestDist = here;
      }
    } else {
      gained = sim.maxX - maxXBefore;
    }
    this.stepsSinceProgress = gained > 0 ? 0 : this.stepsSinceProgress + 1;
    const terminated = status !== Status.RUNNING;
    const stuck = !terminated && this.stepsSinceProgress >= this.noProgressSteps;
    const truncated = !terminated && (stuck || this.steps >= this.maxSteps);
    return { obs: this.observe(), terminated, truncated };
  }

  // ------------------------------------------------------------------ observation
  private setLevel(level: Level): void {
    const padL = VIEW_BEHIND + 1;
    const padR = VIEW_AHEAD + 1;
    const w = level.cols + padL + padR;
    const st = new Float32Array(2 * ROWS * w);
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < w; c++) {
        const lc = c - padL;
        st[r * w + c] = lc < 0 || lc >= level.cols ? 1 : level.solid[r][lc];
      }
    }
    for (const [cx, cy] of level.chests) st[ROWS * w + Math.min(fdiv(cy, TILE), ROWS - 1) * w + padL + fdiv(cx, TILE)] = 1;
    this.staticGrid = st;
    this.staticW = w;
    this.padL = padL;
    this.setOverview(level);
  }

  private setOverview(level: Level): void {
    const padL = OV_BEHIND + 1;
    const padR = OV_COLS * OV_SCALE - OV_BEHIND + OV_SCALE + 1;
    const width = level.cols + padL + padR;
    const solid = new Float32Array(ROWS * width).fill(1);
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < level.cols; c++) solid[r * width + padL + c] = level.solid[r][c];
    const stand = new Float32Array(ROWS * width);
    for (let r = 1; r < ROWS; r++) {
      for (let c = padL; c < padL + level.cols; c++) stand[r * width + c] = solid[r * width + c] * (1 - solid[(r - 1) * width + c]);
    }
    const chest = new Float32Array(ROWS * width);
    for (const [cx, cy] of level.chests) chest[Math.min(fdiv(cy, TILE), ROWS - 1) * width + padL + fdiv(cx, TILE)] = 1;
    const n = width - OV_SCALE + 1;
    const ov = new Float32Array(3 * ROWS * n);
    for (let r = 0; r < ROWS; r++) {
      for (let j = 0; j < n; j++) {
        let share = 0;
        let st = 0;
        let ch = 0;
        for (let i = 0; i < OV_SCALE; i++) {
          const k = r * width + j + i;
          share += solid[k];
          st = Math.max(st, stand[k]);
          ch = Math.max(ch, chest[k]);
        }
        ov[r * n + j] = share / OV_SCALE;
        ov[ROWS * n + r * n + j] = st;
        ov[2 * ROWS * n + r * n + j] = ch;
      }
    }
    this.ovStatic = ov;
    this.ovW = n;
    this.ovPad = padL;
  }

  observe(): Observation {
    const sim = this.sim;
    const p = sim.player;
    const pcol = fdiv(p.x + fdiv(p.w, 2), TILE);
    const c0 = pcol - VIEW_BEHIND;
    const grid = new Float32Array(GRID_CHANNELS * ROWS * VIEW_COLS);
    const w = this.staticW;
    for (let ch = 0; ch < 2; ch++) {
      for (let r = 0; r < ROWS; r++) {
        const src = ch * ROWS * w + r * w + c0 + this.padL;
        const dst = ch * ROWS * VIEW_COLS + r * VIEW_COLS;
        for (let c = 0; c < VIEW_COLS; c++) grid[dst + c] = this.staticGrid[src + c];
      }
    }
    const prow = fdiv(p.y + fdiv(p.h, 2), TILE);
    if (prow >= 0 && prow < ROWS) grid[3 * ROWS * VIEW_COLS + prow * VIEW_COLS + VIEW_BEHIND] = 1;

    const nearest: [number, (typeof sim.enemies)[number]][] = [];
    for (const e of sim.enemies) {
      const ecol = fdiv(e.x + fdiv(e.w, 2), TILE) - c0;
      const erow = fdiv(e.y + fdiv(e.h, 2), TILE);
      if (ecol >= 0 && ecol < VIEW_COLS && erow >= 0 && erow < ROWS) grid[2 * ROWS * VIEW_COLS + erow * VIEW_COLS + ecol] = e.direction;
      nearest.push([Math.abs(e.x - p.x) + Math.abs(e.y - p.y), e]);
    }
    nearest.sort((a, b) => a[0] - b[0]);

    const vec = new Float32Array(VEC_SIZE);
    vec[0] = p.vy / MAX_FALL_SPEED;
    vec[1] = p.onGround ? 1 : 0;
    vec[2] = p.facing;
    vec[3] = p.shootCooldown / SHOOT_COOLDOWN;
    vec[4] = ((((p.x + fdiv(p.w, 2)) % TILE) + TILE) % TILE) / TILE;
    vec[5] = Math.min(1, p.y / (ROWS * TILE));
    const clip = (v: number) => Math.max(-1, Math.min(1, v));
    nearest.slice(0, NEAREST_ENEMIES).forEach(([, e], i) => {
      vec[6 + 3 * i] = clip((e.x - p.x) / 600);
      vec[7 + 3 * i] = clip((e.y - p.y) / 400);
      vec[8 + 3 * i] = 1;
    });
    vec[15] = (p.x - sim.maxX) / 600;
    vec[16] = this.stepsSinceProgress / Math.max(1, this.noProgressSteps);
    vec[17] = 1 - this.steps / Math.max(1, this.maxSteps);
    nearest.slice(0, NEAREST_ENEMIES).forEach(([, e], i) => {
      vec[18 + i] = e.vy / MAX_FALL_SPEED;
    });
    let best = sim.level.chests[0];
    let bestD = Infinity;
    for (const c of sim.level.chests) {
      const d = Math.abs(c[0] - p.x) + Math.abs(c[1] - p.y);
      if (d < bestD) {
        bestD = d;
        best = c;
      }
    }
    const [cx, cy, cw, chh] = best;
    vec[21] = (cx + fdiv(cw, 2) - p.x - fdiv(p.w, 2)) / 3000;
    vec[22] = (cy + chh - p.y - p.h) / (ROWS * TILE);
    for (let i = 0; i < VEC_SIZE; i++) vec[i] = clip(vec[i]);

    return { grid, vec, overview: this.observeOverview(pcol) };
  }

  private observeOverview(pcol: number): Float32Array {
    const start = pcol - OV_BEHIND;
    const ov = new Float32Array(OV_CHANNELS * ROWS * OV_COLS);
    const n = this.ovW;
    const plane = ROWS * n;
    // channels: 0 share, 1 standable, 2 enemies (below), 3 chest
    const map = [0, 1, -1, 2];
    for (let ch = 0; ch < OV_CHANNELS; ch++) {
      const s = map[ch];
      if (s < 0) continue;
      for (let r = 0; r < ROWS; r++) {
        for (let k = 0; k < OV_COLS; k++) {
          const idx = start + this.ovPad + OV_SCALE * k;
          ov[ch * ROWS * OV_COLS + r * OV_COLS + k] = this.ovStatic[s * plane + r * n + idx];
        }
      }
    }
    for (const e of this.sim.enemies) {
      const j = fdiv(fdiv(e.x + fdiv(e.w, 2), TILE) - start, OV_SCALE);
      const row = fdiv(e.y + fdiv(e.h, 2), TILE);
      if (j >= 0 && j < OV_COLS && row >= 0 && row < ROWS) ov[2 * ROWS * OV_COLS + row * OV_COLS + j] = 1;
    }
    return ov;
  }
}

// Port of jumpnrun/editor/proof.py: the "proven way" of the level editor - a real bot action list that plays
// from the start to some point. The search runs in a Web Worker (proof.worker.ts), so building goes on.
//
// A way stays valid as long as replaying it on the edited level gives exactly the same states (player, awake
// enemies, bullets); an edit cuts it where the difference starts. Only a found way is a proof.

import { BOT_ACTIONS_V3 } from "../core/actions";
import { TILE, fdiv } from "../core/constants";
import { Level } from "../core/level";
import { Simulation, Status } from "../core/sim";
import { solve, solvePathLegs } from "../levelgen/solver";
import type { LevelModel } from "./model";

export const REPEAT = 2;
const BACKOFF = 15;
export const BASE_BUDGET = 120_000;
const MAX_BUDGET = 960_000;

export function signature(sim: Simulation): string {
  const p = sim.player;
  const enemies = sim.enemies.filter((e) => e.active).map((e) => `${e.x},${e.y},${e.vy},${e.direction}`).join(";");
  const bullets = sim.bullets.map((b) => `${b.x},${b.y},${b.direction}`).join(";");
  return `${sim.frame}|${sim.status}|${p.x},${p.y},${p.vx},${p.vy},${p.onGround},${p.facing},${p.shootCooldown}|${enemies}|${bullets}`;
}

const centre = (sim: Simulation): [number, number] => [sim.player.x + fdiv(sim.player.w, 2), sim.player.y + fdiv(sim.player.h, 2)];

interface Trace {
  actions: number[];
  sigs: string[];
  points: [number, number][];
  won: boolean;
}

/** Replay `actions`; stops at the win (later actions are dropped) or at a death (that action too). */
function trace(level: Level, actions: number[]): Trace {
  const sim = new Simulation(level);
  const sigs = [signature(sim)];
  const points = [centre(sim)];
  const done: number[] = [];
  for (const a of actions) {
    sim.step(BOT_ACTIONS_V3[a], REPEAT);
    if (sim.status === Status.DIED_PIT || sim.status === Status.DIED_ENEMY) break;
    done.push(a);
    sigs.push(signature(sim));
    points.push(centre(sim));
    if (sim.status === Status.WON) break;
  }
  return { actions: done, sigs, points, won: sim.status === Status.WON };
}

export class Proof {
  constructor(
    public actions: number[] = [],
    public sigs: string[] = [],
    public points: [number, number][] = [],
    public complete = false,
  ) {}

  static found(level: Level, actions: number[]): Proof {
    const t = trace(level, actions);
    return new Proof(t.actions, t.sigs, t.points, t.won);
  }

  get length(): number {
    return this.actions.length;
  }

  /** Keep the way only as far as it still plays the same on `level`; returns the new length. */
  revalidate(level: Level): number {
    const t = trace(level, this.actions);
    if (t.won) {
      Object.assign(this, { actions: t.actions, sigs: t.sigs, points: t.points, complete: true });
      return this.actions.length;
    }
    let k = 0;
    if (this.sigs.length && t.sigs[0] === this.sigs[0]) {
      while (k < t.actions.length && k + 1 < this.sigs.length && t.sigs[k + 1] === this.sigs[k + 1]) k++;
    } else {
      t.sigs = t.sigs.slice(0, 1);
      t.points = t.points.slice(0, 1);
    }
    Object.assign(this, { actions: t.actions.slice(0, k), sigs: t.sigs.slice(0, k + 1), points: t.points.slice(0, k + 1), complete: false });
    return k;
  }

  get endPoint(): [number, number] | null {
    return this.points.length ? this.points[this.points.length - 1] : null;
  }

  get endCol(): number {
    return this.points.length ? fdiv(this.points[this.points.length - 1][0], TILE) : 0;
  }
}

// ------------------------------------------------------------------ the search (runs in the worker)
export type SearchMessage = ["leg", number[]] | ["done", boolean, number[] | null, number] | ["error", string];

/** Search on from the end of `prefix`, report each solved leg. */
export function runSearch(text: string, prefix: number[], budget: number, post: (m: SearchMessage) => void): void {
  try {
    const level = Level.fromText(text);
    const sim = new Simulation(level);
    for (const a of prefix) sim.step(BOT_ACTIONS_V3[a], REPEAT);
    if (sim.status === Status.WON) return post(["done", true, [...prefix], sim.player.x]);
    if (sim.status !== Status.RUNNING) return post(["done", false, null, sim.player.x]);
    let found = [...prefix];
    const r = solvePathLegs(level, {
      actionRepeat: REPEAT,
      legBudget: Math.max(Math.floor(budget / 6), 5_000),
      totalBudget: budget,
      start: sim,
      onLeg: (actions) => {
        found = [...prefix, ...actions];
        post(["leg", [...found]]);
      },
    });
    if (r.solved) return post(["done", true, [...prefix, ...r.actions!], r.maxX]);
    // fallback: plain search towards the chest from the furthest proven point
    const start = new Simulation(level);
    for (const a of found) start.step(BOT_ACTIONS_V3[a], REPEAT);
    const r2 = solve(level, { maxExpansions: Math.max(Math.floor(budget / 2), 20_000), actionRepeat: REPEAT, weight: 1.5, start });
    if (r2.solved) post(["done", true, [...found, ...r2.actions!], r2.maxX]);
    else post(["done", false, null, Math.max(r.maxX, r2.maxX)]);
  } catch (e) {
    post(["error", e instanceof Error ? e.message : String(e)]);
  }
}

/** Something that runs runSearch in the background (a Web Worker in the app). */
export interface Searcher {
  start(text: string, prefix: number[], budget: number, onMessage: (m: SearchMessage) => void): void;
  stop(): void;
}

export function workerSearcher(): Searcher {
  let worker: Worker | null = null;
  return {
    start(text, prefix, budget, onMessage) {
      worker = new Worker(new URL("./proof.worker.ts", import.meta.url), { type: "module" });
      worker.onmessage = (e: MessageEvent<SearchMessage>) => onMessage(e.data);
      worker.onerror = (e) => onMessage(["error", e.message || "Prüfprozess abgestürzt"]);
      worker.postMessage({ text, prefix, budget });
    },
    stop() {
      worker?.terminate();
      worker = null;
    },
  };
}

// ------------------------------------------------------------------ editor state
export type ProofState = "none" | "running" | "complete" | "stuck" | "changed" | "invalid" | "error";

interface Job {
  text: string;
  version: number;
  prefixLen: number;
  budget: number;
  reached: number;
  searcher: Searcher;
}

/** Proof state of the level being edited: proven way, running check, last result. */
export class ProofKeeper {
  proof = new Proof();
  state: ProofState = "none";
  job: Job | null = null;
  level: Level | null = null;
  stuckX = 0;
  stuckVersion = -1;
  budget = BASE_BUDGET;
  message = "";
  private seenVersion = -1;

  constructor(private readonly model: LevelModel, private readonly makeSearcher: () => Searcher = workerSearcher) {
    this.revalidate();
  }

  /** Take over a stored solution of a freshly opened level. */
  load(actions: number[] | null): void {
    this.stop();
    this.proof = new Proof();
    this.state = "none";
    this.budget = BASE_BUDGET;
    this.seenVersion = -1;
    if (actions?.length && this.makeLevel()) {
      this.proof = Proof.found(this.level!, actions);
      this.state = this.proof.complete ? "complete" : this.proof.length ? "changed" : "none";
    }
    this.revalidate();
  }

  private makeLevel(): Level | null {
    try {
      this.level = this.model.toLevel();
    } catch {
      this.level = null;
    }
    return this.level;
  }

  /** Bring the proven way up to date with the edited level (call when the model changed). */
  revalidate(): void {
    if (this.seenVersion === this.model.version) return;
    this.seenVersion = this.model.version;
    if (!this.makeLevel()) {
      this.stop();
      this.state = "invalid";
      return;
    }
    if (this.state === "invalid") this.state = "none";
    const before = this.proof.length;
    const wasComplete = this.proof.complete;
    this.proof.revalidate(this.level!);
    if (this.proof.complete) {
      this.stop();
      this.state = "complete";
      return;
    }
    if (this.job) {
      if (this.proof.length < Math.max(this.job.reached, this.job.prefixLen)) {
        this.stop();
        this.state = "changed";
      }
      return;
    }
    if (this.state === "complete" || this.state === "stuck" || this.proof.length < before || wasComplete) {
      this.state = this.proof.length ? "changed" : "none";
    }
  }

  /** Button "Prüfen". Returns a short note for the status line. */
  check(): string {
    this.revalidate();
    if (this.state === "invalid") return "Erst eine Kiste setzen.";
    if (this.job) return "Prüfung läuft schon.";
    if (this.proof.complete) return "Schon bewiesen lösbar.";
    const retry = this.state === "stuck" && this.stuckVersion === this.model.version;
    this.budget = retry ? Math.min(this.budget * 2, MAX_BUDGET) : BASE_BUDGET;
    const keep = Math.max(0, this.proof.length - (retry ? 2 : 1) * BACKOFF);
    const text = this.model.toText();
    const job: Job = { text, version: this.model.version, prefixLen: keep, budget: this.budget, reached: 0, searcher: this.makeSearcher() };
    this.job = job;
    this.state = "running";
    job.searcher.start(text, this.proof.actions.slice(0, keep), this.budget, (m) => this.onMessage(job, m));
    if (retry) return `Gründlicher prüfen (Suchbudget ${this.budget / 1000}k).`;
    return `Prüfe ab Spalte ${this.proof.points.length ? fdiv(this.proof.points[keep][0], TILE) : 0}.`;
  }

  stop(): void {
    if (!this.job) return;
    this.job.searcher.stop();
    this.job = null;
    if (this.state === "running") this.state = this.proof.length ? "changed" : "none";
  }

  private onMessage(job: Job, m: SearchMessage): void {
    if (this.job !== job) return;
    if (m[0] === "leg") this.take(job, m[1]);
    else if (m[0] === "done") {
      if (m[1] && m[2]) this.take(job, m[2]);
      this.finish(job, m[1], m[3]);
    } else {
      job.searcher.stop();
      this.job = null;
      this.state = "error";
      this.message = m[1];
    }
  }

  /** A way found on the job's snapshot: keep it if it is longer, as far as it holds on the current level. */
  private take(job: Job, actions: number[]): void {
    const found = Proof.found(Level.fromText(job.text), actions);
    job.reached = Math.max(job.reached, found.length);
    if (this.seenVersion !== job.version && this.level) found.revalidate(this.level);
    if (found.complete || found.length > this.proof.length) this.proof = found;
    if (found.length < job.reached && !found.complete) {
      this.stop();
      this.state = "changed";
    }
  }

  private finish(job: Job, solved: boolean, maxX: number): void {
    if (this.job !== job) return;
    job.searcher.stop();
    this.job = null;
    if (this.proof.complete) this.state = "complete";
    else if (solved || this.model.version !== job.version) this.state = "changed";
    else {
      this.state = "stuck";
      this.stuckX = maxX;
      this.stuckVersion = job.version;
    }
  }

  get provenCol(): number {
    return this.proof.endCol;
  }
}

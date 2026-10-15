// Port of BotBrain / BotRacer (jumpnrun/app/bot.py): loads the network in the background and lets the bot
// race frame by frame next to the player, deciding every `action_repeat` frames.

import { BOT_ACTIONS_V3 } from "../core/actions";
import type { Level } from "../core/level";
import { Simulation, Status } from "../core/sim";
import { BotEnv, type Observation } from "./env";
import { PolicyNet } from "./net";

export const RESPAWN_FRAMES = 30;

/** Small seeded PRNG for the bot's sampling (mulberry32). */
export function seededRandom(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class BotBrain {
  net: PolicyNet | null = null;
  error: string | null = null;
  loading = false;
  /** Milliseconds of the last forward passes (debug display). */
  lastMs = 0;

  start(): void {
    if (this.loading || this.net || this.error) return;
    this.loading = true;
    PolicyNet.load()
      .then((net) => (this.net = net))
      .catch((e: unknown) => (this.error = `Bot konnte nicht geladen werden: ${e instanceof Error ? e.message : e}`))
      .finally(() => (this.loading = false));
  }

  get ready(): boolean {
    return this.net !== null;
  }

  choose(obs: Observation, random: () => number): number {
    const t0 = performance.now();
    const a = this.net!.choose(obs, random);
    this.lastMs = this.lastMs * 0.9 + (performance.now() - t0) * 0.1;
    return a;
  }
}

/** One bot in a race: plays the level with the trained policy, frame by frame. */
export class BotRacer {
  readonly env: BotEnv;
  readonly repeat: number;
  wait: number;
  respawn = 0;
  deaths = 0;
  finishFrame: number | null = null;
  frame = 0;
  /** Race frame when the current attempt started (watch mode timing). */
  lastStart = 0;
  private obs!: Observation;
  private k = 0;
  private action = 0;
  private before = 0;
  private random: () => number;

  constructor(private readonly brain: BotBrain, level: Level, delayFrames = 0, seed = Date.now()) {
    this.env = new BotEnv(level, brain.net!.manifest.action_repeat);
    this.repeat = this.env.actionRepeat;
    this.wait = delayFrames;
    this.random = seededRandom(seed);
    this.restart();
  }

  private restart(): void {
    this.lastStart = this.frame;
    this.obs = this.env.reset();
    this.k = 0;
    this.action = 0;
    this.before = this.env.sim.maxX;
  }

  get sim(): Simulation {
    return this.env.sim;
  }

  get visible(): boolean {
    return this.wait <= 0 && this.respawn === 0;
  }

  get won(): boolean {
    return this.finishFrame !== null;
  }

  /** One game frame. Returns an event: "won", "died" or null. */
  step(): "won" | "died" | null {
    this.frame += 1;
    if (this.won) return null;
    if (this.wait > 0) {
      this.wait -= 1;
      return null;
    }
    if (this.respawn > 0) {
      this.respawn -= 1;
      if (this.respawn === 0) this.restart();
      return null;
    }
    if (this.k === 0) {
      this.action = this.brain.choose(this.obs, this.random);
      this.before = this.sim.maxX;
    }
    this.sim.step(BOT_ACTIONS_V3[this.action]);
    this.k += 1;
    if (this.sim.status === Status.WON) {
      this.finishFrame = this.frame;
      return "won";
    }
    if (this.k < this.repeat && this.sim.status === Status.RUNNING) return null;
    this.k = 0;
    const r = this.env.finishStep(this.before);
    this.obs = r.obs;
    if (this.sim.status === Status.DIED_PIT || this.sim.status === Status.DIED_ENEMY || r.terminated || r.truncated) {
      this.deaths += 1;
      this.respawn = RESPAWN_FRAMES;
      return "died";
    }
    return null;
  }
}

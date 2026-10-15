// Port of jumpnrun/app/progress.py: settings, best times, stars and the inputs of the best run (ghost).
// The format is the desktop's save.json (version 1), so a save can be exported and moved between both.
// Mobile-only data (own levels, touch settings) lives under extra keys the desktop ignores.

import { FPS } from "../core/constants";
import { loadText, saveText } from "../platform/storage";

export const HEAD_STARTS = [0, 2, 5, 10];
export const STAR_LIMITS: [number, number] = [1.15, 1.5];

export interface Settings {
  fullscreen: boolean;
  music: number;
  sfx: number;
  ghost: boolean;
  head_start: number;
}

export interface MobileSettings {
  controls_size: number;
  controls_opacity: number;
  /** Small fps / bot-time display (Etappe 6 measurements). */
  show_stats: boolean;
}

export interface LevelRecord {
  best?: number;
  stars?: number;
  wins?: number;
  inputs?: string;
  races?: number;
  race_wins?: number;
  race_best?: number;
}

export interface OwnLevel {
  id: string;
  title: string;
  text: string;
  /** Proven bot way from the editor (2-frame steps), if any. */
  solution: number[] | null;
  updated: number;
}

export const DEFAULT_SETTINGS: Settings = { fullscreen: false, music: 0.5, sfx: 0.8, ghost: true, head_start: 2 };
export const DEFAULT_MOBILE: MobileSettings = { controls_size: 1, controls_opacity: 0.35, show_stats: false };

const KEY = "save.json";

export function starsFor(frames: number, par: number | null | undefined): number {
  if (!par) return 1;
  if (frames <= par * STAR_LIMITS[0]) return 3;
  if (frames <= par * STAR_LIMITS[1]) return 2;
  return 1;
}

/** "m:ss.ss" like the desktop's format_time. */
export function formatTime(frames: number | null | undefined): string {
  if (frames === null || frames === undefined) return "–:––.––";
  const seconds = frames / FPS;
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  return `${m}:${s.toFixed(2).padStart(5, "0")}`;
}

export function encodeInputs(codes: number[]): string {
  return codes.map((c) => "0123456789abcdef"[c]).join("");
}

export function decodeInputs(text: string): number[] {
  return [...text].map((ch) => parseInt(ch, 16));
}

export class Progress {
  settings: Settings = { ...DEFAULT_SETTINGS };
  mobile: MobileSettings = { ...DEFAULT_MOBILE };
  levels: Record<string, LevelRecord> = {};
  own: OwnLevel[] = [];
  private saving: Promise<void> = Promise.resolve();

  static async load(): Promise<Progress> {
    const p = new Progress();
    const raw = await loadText(KEY);
    if (raw) p.importJson(raw, true);
    return p;
  }

  /** Read a save.json (desktop or mobile). `replace` drops everything not in it. */
  importJson(raw: string, replace = false): boolean {
    let data: any;
    try {
      data = JSON.parse(raw);
    } catch {
      return false;
    }
    if (!data || typeof data !== "object") return false;
    if (replace) {
      this.settings = { ...DEFAULT_SETTINGS };
      this.levels = {};
    }
    const s = data.settings ?? {};
    for (const k of Object.keys(DEFAULT_SETTINGS) as (keyof Settings)[]) {
      if (k in s && typeof s[k] === typeof DEFAULT_SETTINGS[k]) (this.settings as any)[k] = s[k];
    }
    if (data.levels && typeof data.levels === "object") {
      for (const [key, rec] of Object.entries<LevelRecord>(data.levels)) this.levels[key] = mergeRecord(this.levels[key], rec);
    }
    const m = data.mobile ?? {};
    for (const k of Object.keys(DEFAULT_MOBILE) as (keyof MobileSettings)[]) {
      if (typeof m[k] === typeof DEFAULT_MOBILE[k]) (this.mobile as unknown as Record<string, unknown>)[k] = m[k];
    }
    if (Array.isArray(data.own_levels)) {
      for (const lvl of data.own_levels as OwnLevel[]) {
        if (!lvl || typeof lvl.text !== "string") continue;
        const i = this.own.findIndex((o) => o.id === lvl.id);
        if (i >= 0) this.own[i] = lvl;
        else this.own.push(lvl);
      }
    }
    return true;
  }

  toJson(pretty = false): string {
    const data = { version: 1, settings: this.settings, levels: this.levels, mobile: this.mobile, own_levels: this.own };
    return JSON.stringify(data, null, pretty ? 1 : undefined);
  }

  save(): void {
    const text = this.toJson();
    this.saving = this.saving.then(() => saveText(KEY, text));
  }

  get(key: string): LevelRecord {
    return this.levels[key] ?? {};
  }

  bestFrames(key: string): number | null {
    return this.get(key).best ?? null;
  }

  stars(key: string): number {
    return this.get(key).stars ?? 0;
  }

  ghost(key: string): number[] | null {
    const inputs = this.get(key).inputs;
    return inputs ? decodeInputs(inputs) : null;
  }

  recordWin(key: string, frames: number, inputs: number[], par: number | null): { best: boolean; stars: number; oldBest: number | null } {
    const entry = (this.levels[key] ??= {});
    const old = entry.best ?? null;
    const stars = starsFor(frames, par);
    const newBest = old === null || frames < old;
    if (newBest) {
      entry.best = frames;
      entry.inputs = encodeInputs(inputs);
    }
    entry.stars = Math.max(entry.stars ?? 0, stars);
    entry.wins = (entry.wins ?? 0) + 1;
    this.save();
    return { best: newBest, stars, oldBest: old };
  }

  recordRace(key: string, won: boolean, frames: number): { wins: number; races: number } {
    const entry = (this.levels[key] ??= {});
    entry.races = (entry.races ?? 0) + 1;
    if (won) {
      entry.race_wins = (entry.race_wins ?? 0) + 1;
      if (entry.race_best === undefined || frames < entry.race_best) entry.race_best = frames;
    }
    this.save();
    return { wins: entry.race_wins ?? 0, races: entry.races };
  }

  summary(): { done: number; stars: number } {
    let done = 0;
    let stars = 0;
    for (const e of Object.values(this.levels)) {
      if (e.best || e.race_wins) done++;
      stars += e.stars ?? 0;
    }
    return { done, stars };
  }
}

/** Importing a save on top of the current one keeps the better of both records. */
function mergeRecord(a: LevelRecord | undefined, b: LevelRecord): LevelRecord {
  if (!a) return { ...b };
  const out: LevelRecord = { ...a };
  if (b.best !== undefined && (a.best === undefined || b.best < a.best)) {
    out.best = b.best;
    out.inputs = b.inputs;
  }
  out.stars = Math.max(a.stars ?? 0, b.stars ?? 0);
  out.wins = Math.max(a.wins ?? 0, b.wins ?? 0);
  out.races = Math.max(a.races ?? 0, b.races ?? 0);
  out.race_wins = Math.max(a.race_wins ?? 0, b.race_wins ?? 0);
  if (b.race_best !== undefined && (a.race_best === undefined || b.race_best < a.race_best)) out.race_best = b.race_best;
  return out;
}

// Port of jumpnrun/app/levels_index.py: which levels the app offers, titles and par times (stars).
// The bundled levels come from public/data/levels.json (tools/export_levels.py); own levels from the save.

import { PLAYER_SPEED, TILE } from "../core/constants";
import { Level } from "../core/level";
import { levelKey } from "../core/levelkey";
import { DistanceMap } from "../levelgen/distmap";
import { generate } from "../levelgen/generator";

export const RANDOM_TAB = "Zufall";
export const OWN_TAB = "Eigene";

export const TIER_NAMES = [
  "Spaziergang", "Kleine Lücken", "Echte Lücken", "Gegner", "Plattformen", "Alles dabei", "Dicht gepackt",
  "Experte", "Klettern & Gruppen", "Wie die Prüfung", "Prüfungsmuster", "Lange Reise", "Sprungkatalog",
  "Kanäle & Gabeln",
];

export interface LevelEntry {
  title: string;
  text: string;
  key: string;
  folder: string;
  stem: string;
  /** Frames of the bot's proven way (stars), or an estimate. */
  par: number;
  proven: boolean;
  /** Proven bot way in 2-frame steps (BOT_ACTIONS_V3 indices), if stored. */
  solution: number[] | null;
  tier?: number;
  seed?: number;
  /** Own levels: id in the save. */
  ownId?: string;
}

export interface Tab {
  name: string;
  levels: LevelEntry[];
}

/** Frames the bot needs: the stored proven way if there is one, else the way length at full speed. */
export function parFrames(level: Level, solution: number[] | null): number {
  if (solution && solution.length) return solution.length * 2;
  try {
    const dm = new DistanceMap(level);
    if (dm.start !== null) return Math.trunc(((dm.start * TILE) / PLAYER_SPEED) * 1.1);
  } catch {
    // only an estimate
  }
  return Math.max(30, Math.floor((level.goalX - level.spawn[0]) / PLAYER_SPEED));
}

export function parLabel(entry: LevelEntry): string {
  return entry.proven ? "Bot-Weg" : "Richtzeit";
}

export function subtitle(entry: LevelEntry): string {
  if (entry.tier !== undefined) return `Zufall · Stufe ${entry.tier} · Seed ${entry.seed}`;
  if (entry.ownId) return "Eigenes Level";
  return `levels/${entry.folder}`;
}

export function randomEntry(tier: number, seed: number): LevelEntry {
  const level = generate(tier, seed);
  const text = level.toText();
  return {
    title: `${TIER_NAMES[tier]} #${seed}`,
    text,
    key: levelKey(text),
    folder: "",
    stem: "",
    par: parFrames(level, null),
    proven: false,
    solution: null,
    tier,
    seed,
  };
}

export function ownEntry(id: string, title: string, text: string, solution: number[] | null): LevelEntry {
  let par = 30;
  try {
    par = parFrames(Level.fromText(text), solution);
  } catch {
    // a half-built level without a chest
  }
  return { title, text, key: levelKey(text), folder: "eigene", stem: id, par, proven: !!solution?.length, solution, ownId: id };
}

interface BundledJson {
  tabs: { name: string; folders: string[]; levels: Omit<LevelEntry, "tier" | "seed">[] }[];
}

/** The bundled tabs (without "Eigene", which comes from the save, and without "Zufall"). */
export function parseBundled(json: BundledJson): Tab[] {
  return json.tabs.filter((t) => t.name !== OWN_TAB).map((t) => ({ name: t.name, levels: t.levels.map((l) => ({ ...l })) }));
}

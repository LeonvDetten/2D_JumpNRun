// Port of jumpnrun/core/level.py: tile map plus spawn points, shared by every simulation that plays it.
//
// Level text: one line per tile row (13 rows, top first). ' ' empty, 'B' block, 'E' enemy spawn, 'C' chest,
// 'P' player spawn (optional). Anything else is empty; rows are padded to the same width.

import {
  CHEST_H,
  CHEST_W,
  DEFAULT_SPAWN,
  ENEMY_H,
  ENEMY_W,
  PLAYER_H,
  PLAYER_W,
  ROWS,
  TILE,
  fdiv,
} from "./constants";

export type Rect = readonly [number, number, number, number];

/** Python's str.rstrip() without arguments (strips all trailing whitespace). */
export function rstrip(s: string): string {
  return s.replace(/\s+$/u, "");
}

export class Level {
  readonly name: string;
  readonly rows = ROWS;
  readonly cols: number;
  /** solid[r][c] = 1 for a block. */
  readonly solid: Uint8Array[];
  readonly enemySpawns: [number, number][] = [];
  readonly chests: Rect[] = [];
  readonly spawn: readonly [number, number];
  /** Optional per-enemy start direction / wake distance (training augmentation; the game uses defaults). */
  enemyDirections: number[] | null = null;
  enemyWakes: number[] | null = null;
  private readonly lines: string[];

  constructor(rawLines: string[], name = "") {
    let lines = rawLines.map((line) => line.replace(/[\n\r]+$/, ""));
    while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
    if (lines.length > ROWS) throw new Error(`level '${name}' has ${lines.length} rows, max is ${ROWS}`);
    while (lines.length < ROWS) lines.push("");

    this.name = name;
    this.cols = Math.max(1, ...lines.map((line) => line.length));
    this.solid = [];
    let spawn: [number, number] | null = null;
    lines.forEach((line, r) => {
      const row = new Uint8Array(this.cols);
      for (let c = 0; c < line.length; c++) {
        const ch = line[c];
        if (ch === "B") row[c] = 1;
        else if (ch === "E") {
          this.enemySpawns.push([c * TILE + fdiv(TILE - ENEMY_W, 2), r * TILE + TILE - ENEMY_H]);
        } else if (ch === "C") {
          this.chests.push([c * TILE, r * TILE + TILE - CHEST_H, CHEST_W, CHEST_H]);
        } else if (ch === "P") {
          spawn = [c * TILE + fdiv(TILE - PLAYER_W, 2), r * TILE + TILE - PLAYER_H];
        }
      }
      this.solid.push(row);
    });
    if (!this.chests.length) throw new Error(`level '${name}' has no chest ('C')`);
    this.spawn = spawn ?? DEFAULT_SPAWN;
    this.lines = lines.map((line) => line.padEnd(this.cols, " "));
  }

  static fromText(text: string, name = ""): Level {
    return new Level(text.split("\n"), name);
  }

  toText(): string {
    return this.lines.map(rstrip).join("\n") + "\n";
  }

  /** The padded text rows (all `cols` wide). */
  textRows(): readonly string[] {
    return this.lines;
  }

  get pixelWidth(): number {
    return this.cols * TILE;
  }

  get pixelHeight(): number {
    return this.rows * TILE;
  }

  /** x of the first chest, the "finish line" for progress bars. */
  get goalX(): number {
    return Math.min(...this.chests.map((c) => c[0]));
  }

  isSolid(col: number, row: number): boolean {
    return row >= 0 && row < this.rows && col >= 0 && col < this.cols && this.solid[row][col] === 1;
  }

  overlapsSolid(x: number, y: number, w: number, h: number): boolean {
    const r0 = Math.max(fdiv(y, TILE), 0);
    const r1 = Math.min(fdiv(y + h - 1, TILE), this.rows - 1);
    if (r0 > r1) return false;
    const c0 = Math.max(fdiv(x, TILE), 0);
    const c1 = Math.min(fdiv(x + w - 1, TILE), this.cols - 1);
    if (c0 > c1) return false;
    for (let r = r0; r <= r1; r++) {
      const row = this.solid[r];
      for (let c = c0; c <= c1; c++) if (row[c]) return true;
    }
    return false;
  }
}

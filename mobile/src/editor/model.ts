// Port of jumpnrun/editor/model.py: the editable level grid (painting, rectangles, columns, undo/redo).

import { ROWS } from "../core/constants";
import { Level, rstrip } from "../core/level";

export const EMPTY = " ";
export const BLOCK = "B";
export const ENEMY = "E";
export const CHEST = "C";
export const START = "P";
const TILES = new Set([BLOCK, ENEMY, CHEST, START]);
const UNDO_LIMIT = 300;

type Grid = string[][];

export class LevelModel {
  grid!: Grid;
  /** Grows with every change (the proof uses it to notice edits). */
  version = 0;
  savedVersion = 0;
  private undoStack: Grid[] = [];
  private redoStack: Grid[] = [];
  private strokeOpen = false;
  private strokeChanged = false;
  private savedText = "";

  constructor(text?: string) {
    this.parse(text ?? LevelModel.defaultText());
    this.markSaved();
  }

  static defaultText(): string {
    const rows = new Array<string>(ROWS).fill("");
    rows[11] = "  P" + " ".repeat(22) + "C";
    rows[12] = "B".repeat(30);
    return rows.join("\n") + "\n";
  }

  private parse(text: string): void {
    const lines = text.replace(/\r\n/g, "\n").split("\n");
    if (lines.length && lines[lines.length - 1] === "") lines.pop();
    if (lines.slice(ROWS).some((l) => l.trim())) throw new Error(`Das Level hat mehr als ${ROWS} Zeilen.`);
    const rows = [...lines, ...new Array<string>(ROWS).fill("")].slice(0, ROWS);
    const clean = (r: string) => [...rstrip(r)].map((ch) => (TILES.has(ch) ? ch : EMPTY)).join("");
    const width = Math.max(1, ...rows.map((r) => rstrip(r).length));
    this.grid = rows.map((r) => [...clean(r).padEnd(width, EMPTY).slice(0, width)]);
  }

  toText(): string {
    const rows = this.grid.map((row) => rstrip(row.join("")));
    while (rows.length && !rows[rows.length - 1]) rows.pop();
    return rows.join("\n") + "\n";
  }

  markSaved(): void {
    this.savedVersion = this.version;
    this.savedText = this.toText();
  }

  get dirty(): boolean {
    return this.version !== this.savedVersion && this.toText() !== this.savedText;
  }

  /** Game level of the current grid (throws if it has no chest). */
  toLevel(name = "neu"): Level {
    return Level.fromText(this.toText(), name);
  }

  get width(): number {
    return this.grid[0].length;
  }

  get(col: number, row: number): string {
    return row >= 0 && row < ROWS && col >= 0 && col < this.width ? this.grid[row][col] : EMPTY;
  }

  find(ch: string): [number, number][] {
    const out: [number, number][] = [];
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < this.width; c++) if (this.grid[r][c] === ch) out.push([c, r]);
    return out;
  }

  /** Columns up to the last non-empty tile. */
  get usedWidth(): number {
    let w = 0;
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < this.width; c++) if (this.grid[r][c] !== EMPTY) w = Math.max(w, c + 1);
    return w;
  }

  // ------------------------------------------------------------------ undo
  /** Start one undo step (a finger stroke); all changes until end() are undone together. */
  begin(): void {
    if (this.strokeOpen) return;
    this.undoStack.push(this.grid.map((r) => [...r]));
    if (this.undoStack.length > UNDO_LIMIT) this.undoStack.shift();
    this.strokeOpen = true;
    this.strokeChanged = false;
  }

  end(): void {
    if (!this.strokeOpen) return;
    this.strokeOpen = false;
    if (!this.strokeChanged) this.undoStack.pop();
    else this.redoStack = [];
  }

  /** Throw away the open stroke (a second finger turned it into a pan/zoom gesture). */
  cancelStroke(): void {
    if (!this.strokeOpen) return;
    this.strokeOpen = false;
    const before = this.undoStack.pop();
    if (before && this.strokeChanged) {
      this.grid = before;
      this.version += 1;
    }
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  private changed(): void {
    this.version += 1;
    if (this.strokeOpen) this.strokeChanged = true;
  }

  undo(): boolean {
    this.end();
    const g = this.undoStack.pop();
    if (!g) return false;
    this.redoStack.push(this.grid.map((r) => [...r]));
    this.grid = g;
    this.version += 1;
    return true;
  }

  redo(): boolean {
    this.end();
    const g = this.redoStack.pop();
    if (!g) return false;
    this.undoStack.push(this.grid.map((r) => [...r]));
    this.grid = g;
    this.version += 1;
    return true;
  }

  // ------------------------------------------------------------------ edits
  private grow(width: number): void {
    if (width > this.width) for (const row of this.grid) while (row.length < width) row.push(EMPTY);
  }

  /** Put one tile (EMPTY erases). The level grows to the right as needed. Returns true if it changed. */
  set(col: number, row: number, ch: string): boolean {
    if (row < 0 || row >= ROWS || col < 0 || (ch === EMPTY && col >= this.width)) return false;
    if (this.get(col, row) === ch) return false;
    const auto = !this.strokeOpen;
    if (auto) this.begin();
    this.grow(col + 1);
    if (ch === START) for (const [c, r] of this.find(START)) this.grid[r][c] = EMPTY;
    this.grid[row][col] = ch;
    this.changed();
    if (auto) this.end();
    return true;
  }

  /** Fill a rectangle (corners inclusive) with BLOCK or EMPTY. */
  fill(c0: number, r0: number, c1: number, r1: number, ch: string): boolean {
    const [ca, cb] = [Math.max(0, Math.min(c0, c1)), Math.max(0, Math.max(c0, c1))];
    const clampR = (r: number) => Math.max(0, Math.min(ROWS - 1, r));
    const [ra, rb] = [Math.min(clampR(r0), clampR(r1)), Math.max(clampR(r0), clampR(r1))];
    const auto = !this.strokeOpen;
    if (auto) this.begin();
    let changed = false;
    for (let r = ra; r <= rb; r++) for (let c = ca; c <= cb; c++) changed = this.set(c, r, ch) || changed;
    if (auto) this.end();
    return changed;
  }

  insertColumn(col: number): boolean {
    if (col < 0 || col > this.width) return false;
    this.begin();
    for (const row of this.grid) row.splice(col, 0, EMPTY);
    this.changed();
    this.end();
    return true;
  }

  deleteColumn(col: number): boolean {
    if (col < 0 || col >= this.width || this.width <= 1) return false;
    this.begin();
    for (const row of this.grid) row.splice(col, 1);
    this.changed();
    this.end();
    return true;
  }
}

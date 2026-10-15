// The level editor for touch (counterpart of jumpnrun/editor/app.py):
//   one finger paints with the chosen tool, two fingers pan and zoom, the minimap jumps.
//   "Prüfen" searches a real bot way in a Web Worker while you keep building (proof.ts).
// Own levels live in the save (progress.own); the current draft is kept automatically.

import { ENEMY_W, PLAYER_H, PLAYER_W, ROWS, TILE, DEFAULT_SPAWN } from "../../core/constants";
import { levelKey } from "../../core/levelkey";
import { BLOCK, CHEST, EMPTY, ENEMY, LevelModel, START } from "../../editor/model";
import { ProofKeeper, REPEAT } from "../../editor/proof";
import { drawSprite } from "../../render/assets";
import { loadText, saveText } from "../../platform/storage";
import { glassPanel, inside, panel, rect, text, type Ctx, type Rect } from "../../ui/draw";
import type { Screen } from "../../ui/screen";
import { ACCENT, CYAN, GREEN, MUTED, PANEL, PANEL_HI, PANEL_LINE, RED, TEXT, YELLOW, css, type RGB } from "../../ui/theme";
import { Button, type Widget } from "../../ui/widgets";
import { FPS } from "../../core/constants";
import { Scene, type App } from "../app";
import { ownEntry, type LevelEntry } from "../levelsIndex";
import type { OwnLevel } from "../progress";
import { EditorFileScene } from "./editorfiles";
import { GameScene } from "./game";
import { MenuScene } from "./menu";

type Tool = "block" | "enemy" | "chest" | "start" | "erase" | "rect" | "colins" | "coldel" | "hand";
const TOOLS: [Tool, string][] = [
  ["block", "Block"], ["enemy", "Gegner"], ["chest", "Kiste"], ["start", "Start"], ["erase", "Radierer"],
  ["rect", "Rechteck"], ["colins", "Spalte +"], ["coldel", "Spalte −"], ["hand", "Verschieben"],
];
const TILE_OF: Partial<Record<Tool, string>> = { block: BLOCK, enemy: ENEMY, chest: CHEST, start: START, erase: EMPTY };
const DRAFT_KEY = "editor_draft";
const REVALIDATE_DELAY = 0.15;
const PAINT_DELAY = 0.07; // s: wait a moment before painting, a second finger may follow (pan/zoom)

interface Draft {
  text: string;
  ownId: string | null;
  title: string;
  /** Proven way so far (2-frame steps). */
  solution: number[] | null;
}

class ToolButton implements Widget {
  pad = 2;
  constructor(public rect: Rect, readonly tool: Tool, private readonly editor: EditorScene) {}
  onTap = (): void => this.editor.selectTool(this.tool);
  draw(ctx: Ctx, pressed: boolean): void {
    const active = this.editor.tool === this.tool;
    panel(ctx, this.rect, active ? PANEL_HI : pressed ? PANEL_HI : PANEL, 8, active ? CYAN : PANEL_LINE);
    this.editor.drawToolIcon(ctx, this.tool, this.rect);
  }
}

export class EditorScene extends Scene {
  model = new LevelModel();
  keeper: ProofKeeper;
  ownId: string | null = null;
  title = "Neues Level";
  tool: Tool = "block";
  rectErase = false;
  private z = 22;
  private scrollX = 0;
  private scrollY = 0;
  private canvas = rect(0, 0, 0, 0);
  private minimap = rect(0, 0, 0, 0);
  private status = rect(0, 0, 0, 0);
  private pointers = new Map<number, { x: number; y: number }>();
  private gesture:
    | { kind: "none" }
    | { kind: "pending"; id: number; t: number; x0: number; y0: number }
    | { kind: "paint"; id: number; last: [number, number] | null; tile: string }
    | { kind: "rect"; id: number; start: [number, number]; end: [number, number] }
    | { kind: "col"; id: number; at: number }
    | { kind: "pan"; id: number; x: number; y: number }
    | { kind: "pinch"; d0: number; z0: number; mx: number; my: number }
    | { kind: "minimap"; id: number } = { kind: "none" };
  private toast: [string, RGB, number] = ["", TEXT, 0];
  private sinceEdit = 0;
  private seenVersion = 0;
  private draftVersion = -1;
  private draftTimer = 0;
  private t = 0;
  private buttons: Record<string, Button> = {};
  private minimapCache: { key: string; canvas: HTMLCanvasElement | null } = { key: "", canvas: null };
  private restored = false;

  constructor(app: App) {
    super(app);
    this.keeper = new ProofKeeper(this.model);
    const b = (key: string, label: string, fn: () => void, accent = false, size = 13) => {
      this.buttons[key] = this.layer.add(new Button(label, rect(0, 0, 0, 0), () => {
        app.audio.play("click");
        fn();
      }, accent, size));
    };
    b("back", "‹ Menü", () => this.leave());
    b("undo", "↶", () => this.undo(), false, 17);
    b("redo", "↷", () => this.redo(), false, 17);
    b("file", "Datei", () => app.push(new EditorFileScene(app, this)));
    b("check", "Prüfen", () => this.flash(this.keeper.check(), ACCENT), true);
    b("replay", "Bot-Weg ▶", () => this.playProof());
    b("watch", "KI ▶", () => this.play("watch"));
    b("test", "Testen ▶", () => this.play("test"));
    for (const [tool] of TOOLS) this.layer.add(new ToolButton(rect(0, 0, 0, 0), tool, this));
    void this.restoreDraft();
  }

  // ------------------------------------------------------------------ files
  private async restoreDraft(): Promise<void> {
    const raw = await loadText(DRAFT_KEY);
    if (this.restored) return;
    this.restored = true;
    if (!raw) return;
    try {
      const d = JSON.parse(raw) as Draft;
      this.load(d.text, d.ownId, d.title, d.solution, false);
    } catch {
      // a broken draft: start fresh
    }
  }

  private saveDraft(): void {
    // the proven way so far travels with the draft (replayed and cut to the current level on restore)
    const d: Draft = { text: this.model.toText(), ownId: this.ownId, title: this.title, solution: this.keeper.proof.length ? [...this.keeper.proof.actions] : null };
    this.draftVersion = this.model.version;
    void saveText(DRAFT_KEY, JSON.stringify(d));
  }

  /** Open a level text (own level, bundled level as a template, import, or a new one). */
  load(text: string, ownId: string | null, title: string, solution: number[] | null, markSaved = true): void {
    this.restored = true;
    this.keeper.stop();
    this.model = new LevelModel(text);
    if (!markSaved) this.model.version = 1; // a restored draft may hold unsaved changes
    this.keeper = new ProofKeeper(this.model);
    this.keeper.load(solution);
    this.ownId = ownId;
    this.title = title;
    this.scrollX = 0;
    this.scrollY = 0;
    this.fitZoom();
    this.seenVersion = this.model.version;
    this.saveDraft();
  }

  newLevel(): void {
    this.load(LevelModel.defaultText(), null, "Neues Level", null);
  }

  get ownLevel(): OwnLevel | null {
    return this.ownId ? this.app.progress.own.find((o) => o.id === this.ownId) ?? null : null;
  }

  /** Save as own level (a new one if `asNew` or if the level is not an own level yet). Returns false if cancelled. */
  save(asNew = false): boolean {
    const p = this.app.progress;
    let own = asNew ? null : this.ownLevel;
    if (!own) {
      const n = p.own.length + 1;
      const suggestion = this.ownId || this.title === "Neues Level" ? `Mein Level ${n}` : `${this.title} (Umbau)`;
      const name = window.prompt("Name des Levels:", suggestion);
      if (name === null) return false;
      own = { id: `own-${Date.now().toString(36)}`, title: name.trim() || suggestion, text: "", solution: null, updated: 0 };
      p.own.push(own);
    }
    own.text = this.model.toText();
    own.solution = this.keeper.state === "complete" ? [...this.keeper.proof.actions] : null;
    own.updated = Date.now();
    this.ownId = own.id;
    this.title = own.title;
    this.model.markSaved();
    p.save();
    this.saveDraft();
    this.flash(own.solution ? "Gespeichert – mit bewiesenem Bot-Weg." : "Gespeichert unter „Eigene“.", GREEN);
    return true;
  }

  deleteOwn(): void {
    const own = this.ownLevel;
    if (!own) return;
    const p = this.app.progress;
    p.own = p.own.filter((o) => o !== own);
    p.save();
    this.ownId = null;
    this.flash(`„${own.title}“ gelöscht – der Entwurf bleibt offen.`, YELLOW);
    this.saveDraft();
  }

  // ------------------------------------------------------------------ actions
  selectTool(tool: Tool): void {
    if (tool === "rect" && this.tool === "rect") this.rectErase = !this.rectErase;
    this.tool = tool;
    const tips: Record<Tool, string> = {
      block: "Block: tippen oder wischen zum Malen.", enemy: "Gegner: läuft los, sobald er ins Bild kommt.",
      chest: "Kiste = Ziel (mehrere erlaubt).", start: "Startpunkt des Piraten (genau einer).",
      erase: "Radierer: wischen löscht.", rect: this.rectErase ? "Rechteck LEEREN – nochmal tippen: Blöcke." : "Rechteck aus Blöcken ziehen – nochmal tippen: leeren.",
      colins: "Spalte einfügen: an der Stelle tippen.", coldel: "Spalte löschen: auf die Spalte tippen.",
      hand: "Verschieben mit einem Finger (zwei Finger gehen immer).",
    };
    this.flash(tips[tool], TEXT, 2.5);
  }

  private undo(): void {
    if (this.model.undo()) this.flash("Rückgängig.", TEXT, 1.2);
  }

  private redo(): void {
    if (this.model.redo()) this.flash("Wiederholt.", TEXT, 1.2);
  }

  flash(msg: string, color: RGB = TEXT, seconds = 3.5): void {
    this.toast = [msg, color, this.t + seconds];
  }

  private entry(): LevelEntry | null {
    try {
      this.model.toLevel();
    } catch {
      this.flash("Erst eine Kiste setzen – ohne Ziel ist das Level nicht spielbar.", RED);
      return null;
    }
    const solution = this.keeper.state === "complete" ? this.keeper.proof.actions : null;
    const e = ownEntry(this.ownId ?? "draft", this.title, this.model.toText(), solution);
    return { ...e, key: levelKey(e.text) };
  }

  private play(mode: "test" | "watch"): void {
    if (mode === "watch" && !this.app.bot?.ready) {
      this.flash(this.app.bot?.error ?? "Der Bot lädt noch …", YELLOW);
      return;
    }
    const e = this.entry();
    if (e) this.app.switch(new GameScene(this.app, e, mode, 0, "", { returnTo: () => this }));
  }

  private playProof(): void {
    if (!this.keeper.proof.length) {
      this.flash("Noch kein bewiesener Weg – erst „Prüfen“.", YELLOW);
      return;
    }
    const e = this.entry();
    if (e) this.app.switch(new GameScene(this.app, e, "replay", 0, "", { returnTo: () => this, replay: [...this.keeper.proof.actions] }));
  }

  private leave(): void {
    this.saveDraft();
    this.keeper.stop();
    this.app.switch(new MenuScene(this.app));
  }

  // ------------------------------------------------------------------ layout & view
  layout(): void {
    const s = this.app.screen;
    const left = s.safe.left + 6;
    const right = s.uiW - s.safe.right - 6;
    const top = 4;
    const h = 32;
    const place = (key: string, x: number, w: number) => (this.buttons[key].rect = rect(x, top, w, h));
    place("back", left, 66);
    place("undo", left + 72, 38);
    place("redo", left + 114, 38);
    place("file", left + 158, 60);
    let x = right;
    for (const [key, w] of [["check", 100], ["replay", 82], ["watch", 50], ["test", 72]] as [string, number][]) {
      x -= w;
      place(key, x, w);
      x -= 6;
    }
    const toolsTop = 42;
    const th = Math.min(33, (s.uiH - toolsTop - Math.max(4, s.safe.bottom) - 2) / TOOLS.length - 3);
    let i = 0;
    for (const w of this.layer.widgets) {
      if (w instanceof ToolButton) w.rect = rect(left, toolsTop + i++ * (th + 3), 42, th);
    }
    const cx = left + 48;
    const bottom = s.uiH - Math.max(4, s.safe.bottom);
    this.status = rect(cx, bottom - 20, right - cx, 20);
    this.minimap = rect(cx, bottom - 44, right - cx, 20);
    this.canvas = rect(cx, toolsTop, right - cx, this.minimap.y - 4 - toolsTop);
    this.fitZoom();
  }

  private fitZoom(): void {
    if (this.canvas.h > 0) this.z = Math.max(8, Math.min(48, (this.canvas.h - 14) / ROWS));
    this.clampScroll();
  }

  private get levelTop(): number {
    const extra = this.canvas.h - 12 - ROWS * this.z;
    return this.canvas.y + 12 + (extra > 0 ? extra / 2 : -this.scrollY);
  }

  private get visibleCols(): number {
    return this.canvas.w / this.z;
  }

  private clampScroll(): void {
    this.scrollX = Math.max(0, Math.min(this.scrollX, Math.max(0, this.model.width + 6 - this.visibleCols)));
    this.scrollY = Math.max(0, Math.min(this.scrollY, Math.max(0, ROWS * this.z - (this.canvas.h - 12))));
  }

  private colX(col: number): number {
    return this.canvas.x + (col - this.scrollX) * this.z;
  }

  private worldToUi(px: number, py: number): [number, number] {
    return [this.colX(px / TILE), this.levelTop + (py / TILE) * this.z];
  }

  private cellAt(x: number, y: number): [number, number] | null {
    if (!inside(this.canvas, x, y)) return null;
    const col = Math.floor(this.scrollX + (x - this.canvas.x) / this.z);
    const row = Math.floor((y - this.levelTop) / this.z);
    return row >= 0 && row < ROWS && col >= 0 ? [col, row] : null;
  }

  // ------------------------------------------------------------------ input
  pointerDown(id: number, x: number, y: number): void {
    if (this.layer.pointerDown(id, x, y)) return;
    this.pointers.set(id, { x, y });
    if (this.pointers.size === 2) {
      // second finger: pan / zoom; a stroke that just began is taken back
      if (this.gesture.kind === "paint" || this.gesture.kind === "rect") this.model.cancelStroke();
      const [a, b] = [...this.pointers.values()];
      this.gesture = { kind: "pinch", d0: Math.hypot(a.x - b.x, a.y - b.y), z0: this.z, mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
      return;
    }
    if (this.pointers.size > 2) return;
    if (inside(this.minimap, x, y, 4)) {
      this.gesture = { kind: "minimap", id };
      this.minimapJump(x);
      return;
    }
    if (!inside(this.canvas, x, y)) return;
    if (this.tool === "hand") this.gesture = { kind: "pan", id, x, y };
    else this.gesture = { kind: "pending", id, t: this.t, x0: x, y0: y };
  }

  private startGesture(id: number, x: number, y: number): void {
    const cell = this.cellAt(x, y);
    const tool = this.tool;
    if (tool === "rect") {
      if (!cell) return void (this.gesture = { kind: "none" });
      this.gesture = { kind: "rect", id, start: cell, end: cell };
    } else if (tool === "colins" || tool === "coldel") {
      this.gesture = { kind: "col", id, at: this.colAt(x, tool) };
    } else {
      this.model.begin();
      this.gesture = { kind: "paint", id, last: null, tile: TILE_OF[tool] ?? BLOCK };
      this.paintTo(cell);
    }
  }

  private colAt(x: number, tool: Tool): number {
    const f = this.scrollX + (x - this.canvas.x) / this.z;
    return tool === "colins" ? Math.round(f) : Math.floor(f);
  }

  private paintTo(cell: [number, number] | null): void {
    const g = this.gesture;
    if (g.kind !== "paint" || !cell) return;
    const tile = g.tile;
    const single = tile === START || tile === CHEST;
    if (g.last && !single) {
      // fill the gaps of fast strokes (Bresenham)
      let [c0, r0] = g.last;
      const [c1, r1] = cell;
      const dc = Math.abs(c1 - c0);
      const dr = -Math.abs(r1 - r0);
      const sc = c0 < c1 ? 1 : -1;
      const sr = r0 < r1 ? 1 : -1;
      let err = dc + dr;
      for (;;) {
        this.model.set(c0, r0, tile);
        if (c0 === c1 && r0 === r1) break;
        const e2 = 2 * err;
        if (e2 >= dr) {
          err += dr;
          c0 += sc;
        }
        if (e2 <= dc) {
          err += dc;
          r0 += sr;
        }
      }
    } else if (!g.last || !single || g.last[0] !== cell[0] || g.last[1] !== cell[1]) {
      this.model.set(cell[0], cell[1], tile);
    }
    g.last = cell;
  }

  pointerMove(id: number, x: number, y: number): void {
    if (this.layer.pointerMove(id, x, y)) return;
    const p = this.pointers.get(id);
    if (!p) return;
    const px = p.x;
    const py = p.y;
    p.x = x;
    p.y = y;
    const g = this.gesture;
    if (g.kind === "pinch") {
      const [a, b] = [...this.pointers.values()];
      if (!b) return;
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const colAtMid = this.scrollX + (g.mx - this.canvas.x) / this.z;
      const rowY = (g.my - this.levelTop) / this.z;
      this.z = Math.max(8, Math.min(48, (g.z0 * d) / Math.max(10, g.d0)));
      // keep the point under the fingers where it is, then follow the fingers
      this.scrollX = colAtMid - (mx - this.canvas.x) / this.z;
      const extra = this.canvas.h - 12 - ROWS * this.z;
      if (extra < 0) this.scrollY = rowY * this.z - (my - this.canvas.y - 12);
      g.mx = mx;
      g.my = my;
      this.clampScroll();
      return;
    }
    if (g.kind === "none" || !("id" in g) || g.id !== id) return;
    if (g.kind === "pending") {
      if (Math.hypot(x - g.x0, y - g.y0) > 6) {
        this.startGesture(id, g.x0, g.y0);
        this.pointerMove(id, x, y);
      }
      return;
    }
    if (g.kind === "pan") {
      this.scrollX -= (x - px) / this.z;
      this.scrollY -= y - py;
      this.clampScroll();
    } else if (g.kind === "paint") this.paintTo(this.cellAt(x, y));
    else if (g.kind === "rect") {
      const cell = this.cellAt(Math.max(this.canvas.x, Math.min(x, this.canvas.x + this.canvas.w - 1)), Math.max(this.levelTop, Math.min(y, this.levelTop + ROWS * this.z - 1)));
      if (cell) g.end = cell;
    } else if (g.kind === "col") g.at = this.colAt(x, this.tool);
    else if (g.kind === "minimap") this.minimapJump(x);
  }

  pointerUp(id: number, x: number, y: number): void {
    if (this.layer.pointerUp(id, x, y)) return;
    if (!this.pointers.delete(id)) return;
    const g = this.gesture;
    if (g.kind === "pinch") {
      if (this.pointers.size === 0) this.gesture = { kind: "none" };
      return;
    }
    if (g.kind === "none" || !("id" in g) || g.id !== id) return;
    if (g.kind === "pending") this.startGesture(id, g.x0, g.y0);
    const h = this.gesture;
    if (h.kind === "paint") this.model.end();
    else if (h.kind === "rect") this.model.fill(h.start[0], h.start[1], h.end[0], h.end[1], this.rectErase ? EMPTY : BLOCK);
    else if (h.kind === "col") {
      if (this.tool === "colins" ? this.model.insertColumn(h.at) : this.model.deleteColumn(h.at)) {
        this.flash(this.tool === "colins" ? `Spalte bei ${h.at} eingefügt.` : `Spalte ${h.at} gelöscht.`, TEXT, 1.5);
      }
    }
    this.gesture = { kind: "none" };
  }

  wheel(dy: number, x: number, y: number): void {
    if (!inside(this.canvas, x, y)) return;
    this.scrollX += dy / this.z / 2;
    this.clampScroll();
  }

  private minimapJump(x: number): void {
    const scale = this.minimapScale;
    this.scrollX = (x - this.minimap.x) / scale - this.visibleCols / 2;
    this.clampScroll();
  }

  private get minimapScale(): number {
    return Math.min(this.minimap.w / Math.max(1, this.model.width + 6), 6);
  }

  keyDown(code: string): void {
    if (code === "KeyZ") this.undo();
    else if (code === "KeyY") this.redo();
    else if (code === "KeyP") this.flash(this.keeper.check(), ACCENT);
    else if (code === "KeyT") this.play("test");
    else if (code === "ArrowRight") this.scrollX += 5;
    else if (code === "ArrowLeft") this.scrollX -= 5;
    else if (code === "Escape") this.leave();
    else {
      const i = Number(code.replace("Digit", "")) - 1;
      if (i >= 0 && i < TOOLS.length) this.selectTool(TOOLS[i][0]);
    }
    this.clampScroll();
  }

  enter(): void {
    this.app.audio.music(null);
  }

  hidden(): void {
    this.saveDraft();
  }

  close(): void {
    // switching to a test-play keeps the editor (and its running check) alive: nothing to do here
  }

  // ------------------------------------------------------------------ update
  update(dt: number): void {
    this.t += dt;
    if (this.gesture.kind === "pending" && this.t - this.gesture.t >= PAINT_DELAY) {
      const g = this.gesture;
      this.startGesture(g.id, g.x0, g.y0);
    }
    if (this.model.version !== this.seenVersion) {
      this.seenVersion = this.model.version;
      this.sinceEdit = 0;
    } else this.sinceEdit += dt;
    const stroking = this.gesture.kind === "paint" || this.gesture.kind === "rect";
    if (!stroking && this.sinceEdit >= REVALIDATE_DELAY) this.keeper.revalidate();
    this.draftTimer += dt;
    if (this.draftTimer > 1 && this.draftVersion !== this.model.version && !stroking) {
      this.draftTimer = 0;
      this.saveDraft();
    }
    this.buttons.undo.enabled = this.model.canUndo;
    this.buttons.redo.enabled = this.model.canRedo;
    this.buttons.replay.enabled = this.keeper.proof.length > 0;
    this.buttons.check.label = this.keeper.state === "running" ? "Prüft …" : this.keeper.state === "changed" ? "Weiterprüfen" : this.keeper.state === "stuck" ? "Nochmal" : "Prüfen";
  }

  // ------------------------------------------------------------------ drawing
  draw(screen: Screen): void {
    const ctx = screen.ui();
    ctx.fillStyle = "rgb(12,14,24)";
    ctx.fillRect(0, 0, screen.uiW, screen.uiH);
    this.drawCanvas(ctx);
    this.drawMinimap(ctx);
    this.drawStatus(ctx);
    const name = `${this.title}${this.model.dirty || !this.ownId ? " *" : ""}`;
    const fileR = this.buttons.file.rect;
    const testR = this.buttons.test.rect;
    text(ctx, name, (fileR.x + fileR.w + testR.x) / 2, 20, 13, TEXT, true, "center", testR.x - fileR.x - fileR.w - 16);
    this.layer.draw(ctx);
    const [msg, color, until] = this.toast;
    if (msg && this.t < until) {
      ctx.font = "700 13px sans-serif";
      const w = Math.min(this.canvas.w - 20, ctx.measureText(msg).width + 30);
      const r = rect(this.canvas.x + this.canvas.w / 2 - w / 2, this.minimap.y - 40, w, 30);
      glassPanel(ctx, r, 235, color, 10, 1.5);
      text(ctx, msg, r.x + r.w / 2, r.y + r.h / 2 + 0.5, 13, color, true, "center", w - 16);
    }
  }

  drawToolIcon(ctx: Ctx, tool: Tool, r: Rect): void {
    const a = this.app.assets;
    const cx = r.x + r.w / 2;
    const cy = r.y + r.h / 2;
    const s = Math.min(r.w, r.h) - 10;
    switch (tool) {
      case "block": drawSprite(ctx, a.sprite("block"), cx - s / 2, cy - s / 2, s, s); break;
      case "enemy": drawSprite(ctx, a.sprite("enemy_1_0"), cx - s / 2, cy - s / 2, s, s); break;
      case "chest": drawSprite(ctx, a.sprite("chest_0"), cx - s * 0.6, cy - s * 0.4, s * 1.2, s * 0.8); break;
      case "start": {
        const h = s + 4;
        drawSprite(ctx, a.player("IDLE", 0), cx - (h * PLAYER_W) / PLAYER_H / 2, cy - h / 2, (h * PLAYER_W) / PLAYER_H, h);
        break;
      }
      case "rect": {
        ctx.setLineDash([3, 2]);
        ctx.strokeStyle = css(this.rectErase ? RED : ACCENT);
        ctx.lineWidth = 1.5;
        ctx.strokeRect(cx - s / 2, cy - s / 2.6, s, s / 1.3);
        ctx.setLineDash([]);
        if (!this.rectErase) {
          ctx.fillStyle = css(ACCENT, 0.4);
          ctx.fillRect(cx - s / 2, cy - s / 2.6, s, s / 1.3);
        }
        break;
      }
      default: {
        const glyph = { erase: "⌫", colins: "+▕", coldel: "−▕", hand: "✋" }[tool as "erase" | "colins" | "coldel" | "hand"];
        text(ctx, glyph, cx, cy + 1, tool === "hand" ? 15 : 14, tool === "erase" || tool === "coldel" ? RED : TEXT, true, "center");
      }
    }
  }

  private drawCanvas(ctx: Ctx): void {
    const c = this.canvas;
    const z = this.z;
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(c.x, c.y, c.w, c.h, 8);
    ctx.clip();
    ctx.drawImage(this.app.assets.background, c.x, c.y, c.w, c.h);
    ctx.fillStyle = "rgba(6,8,20,0.6)";
    ctx.fillRect(c.x, c.y, c.w, c.h);
    const top = this.levelTop;
    const c0 = Math.max(0, Math.floor(this.scrollX));
    const c1 = Math.floor(this.scrollX + this.visibleCols) + 1;
    const width = this.model.width;
    // right of the level end
    const endX = this.colX(width);
    if (endX < c.x + c.w) {
      ctx.fillStyle = "rgba(90,110,160,0.16)";
      ctx.fillRect(endX, top, c.x + c.w - endX, ROWS * z);
      ctx.strokeStyle = "rgb(150,170,220)";
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.moveTo(endX, top);
      ctx.lineTo(endX, top + ROWS * z);
      ctx.stroke();
      ctx.setLineDash([]);
      text(ctx, "Level-Ende – hier weitermalen verlängert", endX + 6, top + 4, 10.5, MUTED, false, "topleft", c.x + c.w - endX - 10);
    }
    // grid
    ctx.lineWidth = 0.5;
    for (let col = c0; col <= c1; col++) {
      const x = this.colX(col);
      ctx.strokeStyle = col % 10 === 0 ? "rgba(255,255,255,0.28)" : "rgba(255,255,255,0.09)";
      ctx.beginPath();
      ctx.moveTo(x, top);
      ctx.lineTo(x, top + ROWS * z);
      ctx.stroke();
    }
    ctx.strokeStyle = "rgba(255,255,255,0.09)";
    for (let row = 0; row <= ROWS; row++) {
      ctx.beginPath();
      ctx.moveTo(c.x, top + row * z);
      ctx.lineTo(c.x + c.w, top + row * z);
      ctx.stroke();
    }
    ctx.strokeStyle = "rgb(200,60,60)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(c.x, top + ROWS * z);
    ctx.lineTo(c.x + c.w, top + ROWS * z);
    ctx.stroke();
    // tiles
    const a = this.app.assets;
    for (let row = 0; row < ROWS; row++) {
      const line = this.model.grid[row];
      for (let col = c0; col < Math.min(c1, width); col++) {
        const ch = line[col];
        if (ch !== EMPTY) this.drawTile(ctx, ch, this.colX(col), top + row * z, z);
      }
    }
    if (!this.model.find(START).length) {
      const [x, y] = this.worldToUi(DEFAULT_SPAWN[0], DEFAULT_SPAWN[1]);
      ctx.globalAlpha = 0.45;
      drawSprite(ctx, a.player("IDLE", 0), x, y, (PLAYER_W / TILE) * z, (PLAYER_H / TILE) * z);
      ctx.globalAlpha = 1;
      text(ctx, "Start (Standard)", x, y - 3, 10, MUTED, false, "bottomleft");
    }
    this.drawProof(ctx);
    this.drawGesture(ctx);
    // ruler
    ctx.fillStyle = "rgba(28,32,46,0.92)";
    ctx.fillRect(c.x, c.y, c.w, 11);
    const step = z >= 24 ? 5 : 10;
    for (let col = Math.floor(c0 / step) * step; col <= c1; col += step) {
      text(ctx, String(col), this.colX(col) + 2, c.y + 1, 8.5, MUTED, false, "topleft");
    }
    ctx.restore();
    ctx.strokeStyle = css(PANEL_LINE);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(c.x, c.y, c.w, c.h, 8);
    ctx.stroke();
  }

  private drawTile(ctx: Ctx, ch: string, x: number, y: number, z: number): void {
    const a = this.app.assets;
    const k = z / TILE;
    if (ch === BLOCK) drawSprite(ctx, a.sprite("block"), x, y, z + 0.3, z + 0.3);
    else if (ch === ENEMY) drawSprite(ctx, a.sprite("enemy_1_0"), x + ((TILE - ENEMY_W) / 2) * k, y + 20 * k, 40 * k, 40 * k);
    else if (ch === CHEST) drawSprite(ctx, a.sprite("chest_0"), x, y + 20 * k, z, 40 * k);
    else if (ch === START) drawSprite(ctx, a.player("IDLE", 0), x + 10 * k, y, 40 * k, z);
  }

  private drawProof(ctx: Ctx): void {
    const k = this.keeper;
    const z = this.z;
    const pts = k.proof.points;
    const color = k.state === "complete" ? GREEN : k.state === "running" ? ACCENT : k.proof.length ? GREEN : MUTED;
    const lo = (this.scrollX - 1) * TILE;
    const hi = (this.scrollX + this.visibleCols + 1) * TILE;
    ctx.fillStyle = css(color);
    const r = Math.max(1.2, z / 16);
    for (let i = 0; i < pts.length; i += 2) {
      const [px, py] = pts[i];
      if (px < lo || px > hi) continue;
      const [x, y] = this.worldToUi(px, py);
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }
    const top = this.levelTop;
    if (k.state === "stuck") {
      const x = this.colX(Math.floor(k.stuckX / TILE));
      ctx.fillStyle = "rgba(238,60,60,0.25)";
      ctx.fillRect(x, top, 2 * z, ROWS * z);
      ctx.strokeStyle = css(RED);
      ctx.lineWidth = 1.5;
      ctx.strokeRect(x, top, 2 * z, ROWS * z);
      text(ctx, "kein Weg gefunden", x + 3, top + 3, 11, RED, true);
    }
    const end = k.proof.endPoint;
    const pulse = k.state === "running" ? 2 * Math.abs(((this.t * 16) % 10) - 5) / 5 : 0;
    if (end && k.proof.length && !k.proof.complete) {
      const [x, y] = this.worldToUi(end[0], end[1]);
      const ring = k.state === "running" ? ACCENT : k.state === "stuck" ? RED : YELLOW;
      ctx.strokeStyle = css(ring);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, z / 2 + pulse * 3, 0, Math.PI * 2);
      ctx.stroke();
      const label = k.state === "running" ? "prüfe …" : k.state === "stuck" ? "bewiesen bis hier" : "bewiesen bis hier – danach geändert";
      text(ctx, label, x + z / 2 + 5, y, 11, ring, true, "midleft");
    } else if (k.state === "running") {
      const spawn = k.level?.spawn ?? DEFAULT_SPAWN;
      const [x, y] = this.worldToUi(spawn[0] + 20, spawn[1] + 30);
      ctx.strokeStyle = css(ACCENT);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, z / 2 + pulse * 3, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  private drawGesture(ctx: Ctx): void {
    const g = this.gesture;
    const z = this.z;
    if (g.kind === "rect") {
      const [c0, r0] = g.start;
      const [c1, r1] = g.end;
      const x0 = this.colX(Math.min(c0, c1));
      const x1 = this.colX(Math.max(c0, c1) + 1);
      const y0 = this.levelTop + Math.min(r0, r1) * z;
      const y1 = this.levelTop + (Math.max(r0, r1) + 1) * z;
      ctx.fillStyle = this.rectErase ? "rgba(238,84,84,0.3)" : "rgba(82,156,255,0.3)";
      ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
      ctx.strokeStyle = css(this.rectErase ? RED : ACCENT);
      ctx.lineWidth = 2;
      ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
    } else if (g.kind === "col") {
      const ins = this.tool === "colins";
      const x = this.colX(g.at);
      ctx.fillStyle = ins ? "rgba(82,156,255,0.9)" : "rgba(238,84,84,0.3)";
      if (ins) ctx.fillRect(x - 1.5, this.levelTop, 3, ROWS * z);
      else ctx.fillRect(x, this.levelTop, z, ROWS * z);
      text(ctx, ins ? `einfügen bei ${g.at}` : `Spalte ${g.at} löschen`, x + 4, this.levelTop + 14, 11, ins ? ACCENT : RED, true);
    }
  }

  private drawMinimap(ctx: Ctx): void {
    const m = this.minimap;
    panel(ctx, m, [20, 22, 34], 6, PANEL_LINE);
    const key = `${this.model.version}`;
    if (this.minimapCache.key !== key) {
      const cv = document.createElement("canvas");
      cv.width = this.model.width;
      cv.height = ROWS;
      const g = cv.getContext("2d")!;
      const colors: Record<string, string> = { B: "rgb(150,156,186)", E: "rgb(238,84,84)", C: "rgb(244,192,64)", P: "rgb(72,204,122)" };
      for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < this.model.width; c++) {
          const ch = this.model.grid[r][c];
          if (ch !== EMPTY) {
            g.fillStyle = colors[ch];
            g.fillRect(c, r, 1, 1);
          }
        }
      }
      this.minimapCache = { key, canvas: cv };
    }
    const scale = this.minimapScale;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.minimapCache.canvas!, m.x + 1, m.y + 2, this.model.width * scale, m.h - 4);
    ctx.imageSmoothingEnabled = true;
    const k = this.keeper;
    if (k.proof.length) {
      ctx.fillStyle = css(k.state === "complete" ? GREEN : k.state === "running" ? ACCENT : YELLOW);
      ctx.fillRect(m.x + 1, m.y + m.h - 3, k.provenCol * scale, 2);
    }
    if (k.state === "stuck") {
      ctx.fillStyle = css(RED);
      ctx.fillRect(m.x + (k.stuckX / TILE) * scale, m.y, Math.max(2, 2 * scale), m.h);
    }
    ctx.strokeStyle = css(ACCENT);
    ctx.lineWidth = 1.5;
    const vx = m.x + this.scrollX * scale;
    ctx.strokeRect(vx, m.y + 1, Math.max(6, Math.min(this.visibleCols * scale, m.x + m.w - vx)), m.h - 2);
  }

  private statusLine(): [string, RGB] {
    const k = this.keeper;
    const col = k.provenCol;
    const seconds = ((k.proof.length * REPEAT) / FPS).toFixed(1);
    switch (k.state) {
      case "invalid": return ["Keine Kiste – so ist das Level nicht spielbar. Werkzeug „Kiste“ wählen.", RED];
      case "running": return [`Prüfe … bewiesen bis Spalte ${col}. Du kannst nebenher weiterbauen.`, ACCENT];
      case "complete": return [`Lösbar: Der Bot-Weg bis zur Kiste ist bewiesen (${seconds} s Spielzeit).`, GREEN];
      case "stuck": return [`Kein Weg ab Spalte ${Math.floor(k.stuckX / TILE)} (Suchbudget ${k.budget / 1000}k). Umbauen – oder „Nochmal“ = gründlicher.`, RED];
      case "changed": return [`Bewiesen bis Spalte ${col}, danach geändert. „Weiterprüfen“ setzt dort an.`, YELLOW];
      case "error": return [`Prüfung abgebrochen: ${k.message}`, RED];
      default: return ["Noch nicht geprüft. „Prüfen“ sucht im Hintergrund einen Weg für den Bot.", MUTED];
    }
  }

  private drawStatus(ctx: Ctx): void {
    const s = this.status;
    const [msg, color] = this.statusLine();
    ctx.fillStyle = css(color);
    ctx.beginPath();
    ctx.arc(s.x + 7, s.y + s.h / 2, 4, 0, Math.PI * 2);
    ctx.fill();
    const info = `${this.model.usedWidth} Spalten`;
    const iw = 70;
    text(ctx, msg, s.x + 16, s.y + s.h / 2 + 0.5, 11, color, true, "midleft", s.w - iw - 24);
    text(ctx, info, s.x + s.w, s.y + s.h / 2 + 0.5, 10.5, MUTED, false, "midright");
  }
}

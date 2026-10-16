// Port of LevelSelectScene: tabs (Einstieg, Handgebaut, Test-Serie, Prüfung, Eigene, Zufall), a scrolling grid
// of level cards and a detail panel with the start button. Modes: single, bot (head start), watch.

import { TILE } from "../../core/constants";
import { Level } from "../../core/level";
import { levelThumbnail } from "../../ui/gfx";
import { drawFancy, fancyText, glassPanel, HEADER, inside, rect, stars, text, type Ctx, type Rect } from "../../ui/draw";
import type { Screen } from "../../ui/screen";
import { CYAN, GOLD, GREEN, MUTED, TEXT } from "../../ui/theme";
import { Button, Chips, MenuButton, Slider, Tabs, TAP_SLOP } from "../../ui/widgets";
import { Scene, type App } from "../app";
import { OWN_TAB, RANDOM_TAB, TIER_NAMES, parLabel, randomEntry, subtitle, type LevelEntry } from "../levelsIndex";
import { HEAD_STARTS, formatTime } from "../progress";
import { GameScene, type Mode } from "./game";
import { MenuScene } from "./menu";

const NUM_TIERS = TIER_NAMES.length;
const CARD_H = 112;
const GAP = 8;

export class LevelSelectScene extends Scene {
  private tabs: Tabs;
  private back: Button;
  private start: MenuButton;
  private dice: Button;
  private head: Chips<number>;
  private tierSlider: Slider;
  private selected = 0;
  private scroll = 0;
  private velocity = 0;
  private drag: { id: number; y0: number; s0: number; moved: boolean; lastY: number; lastT: number } | null = null;
  private tier: number;
  private seed: number;
  private random: LevelEntry;
  private grid = rect(0, 0, 0, 0);
  private detail = rect(0, 0, 0, 0);
  private cols = 2;
  private t = 0;
  private lastTap = { i: -1, t: 0 };

  constructor(app: App, readonly mode: Mode, tab?: string) {
    super(app);
    const labels = [...app.tabs.map((t) => t.name), OWN_TAB, RANDOM_TAB];
    this.tabs = this.layer.add(new Tabs(labels, 0, 0, app.screen.ctx, () => {
      this.selected = 0;
      this.scroll = 0;
      this.velocity = 0;
      this.app.audio.play("click");
      this.updateWidgets();
    }));
    if (tab && labels.includes(tab)) this.tabs.index = labels.indexOf(tab);
    this.back = this.layer.add(new Button("‹ Zurück", rect(0, 0, 0, 0), () => {
      this.app.audio.play("click");
      this.app.switch(new MenuScene(this.app));
    }));
    const label = mode === "single" ? "Los!" : mode === "bot" ? "Rennen starten!" : "Zuschauen";
    this.start = this.layer.add(new MenuButton(label, "", rect(0, 0, 0, 0), () => this.go()));
    this.start.glow = true;
    this.dice = this.layer.add(new Button("Neu würfeln", rect(0, 0, 0, 0), () => {
      this.seed = 1 + Math.floor(Math.random() * 99999);
      this.makeRandom();
      this.app.audio.play("click");
    }));
    this.head = this.layer.add(new Chips(app.screen.ctx, 0, 0, HEAD_STARTS, HEAD_STARTS.map((s) => `${s} s`), app.progress.settings.head_start, () => this.app.audio.play("click"), 28));
    this.tier = app.randomTier;
    this.seed = app.randomSeed;
    this.tierSlider = this.layer.add(new Slider(rect(0, 0, 0, 6), this.tier / (NUM_TIERS - 1), (v) => {
      const tier = Math.round(v * (NUM_TIERS - 1));
      if (tier !== this.tier) {
        this.tier = tier;
        this.makeRandom();
      }
    }, false));
    this.random = randomEntry(this.tier, this.seed);
    this.updateWidgets();
  }

  enter(): void {
    this.app.audio.music("menu");
  }

  // ------------------------------------------------------------------ data
  private get entries(): LevelEntry[] {
    return this.app.levelsOfTab(this.tabs.current);
  }

  private get isRandom(): boolean {
    return this.tabs.current === RANDOM_TAB;
  }

  private get entry(): LevelEntry | null {
    if (this.isRandom) return this.random;
    const e = this.entries;
    return e.length && this.selected >= 0 && this.selected < e.length ? e[this.selected] : null;
  }

  private makeRandom(): void {
    this.random = randomEntry(this.tier, this.seed);
    this.app.randomTier = this.tier;
    this.app.randomSeed = this.seed;
    this.tierSlider.value = this.tier / (NUM_TIERS - 1);
  }

  private updateWidgets(): void {
    this.dice.hidden = !this.isRandom;
    this.tierSlider.hidden = !this.isRandom;
    this.head.hidden = this.mode !== "bot";
    this.start.enabled = this.entry !== null;
  }

  private go(): void {
    const entry = this.entry;
    if (!entry) return;
    this.app.audio.play("click");
    this.app.progress.settings.head_start = this.head.value;
    this.app.progress.save();
    this.app.switch(new GameScene(this.app, entry, this.mode, this.mode === "bot" ? this.head.value : 0, this.tabs.current));
  }

  // ------------------------------------------------------------------ layout
  layout(): void {
    const s = this.app.screen;
    const left = s.safe.left + 10;
    const right = s.uiW - s.safe.right - 10;
    this.back.rect = rect(left, 6, 92, 32);
    let tx = left;
    this.tabs.rects.forEach((r) => {
      r.x = tx;
      r.y = 46;
      tx += r.w + 5;
    });
    this.tabs.rect = rect(left, 46, tx - left, 30);
    const dw = Math.min(262, (right - left) * 0.4);
    this.detail = rect(right - dw, 84, dw, s.uiH - 84 - Math.max(8, s.safe.bottom));
    this.grid = rect(left, 84, this.detail.x - 10 - left, this.detail.h);
    this.cols = Math.max(1, Math.floor((this.grid.w + GAP) / (150 + GAP)));
    const d = this.detail;
    this.start.rect = rect(d.x + 12, d.y + d.h - 52, d.w - 24, 42);
    this.head.rects.forEach((r, i) => {
      r.x = i === 0 ? d.x + 14 : this.head.rects[i - 1].x + this.head.rects[i - 1].w + 5;
      r.y = d.y + d.h - 92;
    });
    this.head.rect = rect(d.x + 14, d.y + d.h - 92, d.w - 28, 28);
    this.tierSlider.rect = rect(d.x + 18, d.y + 138, d.w - 36, 6);
    this.dice.rect = rect(d.x + 14, d.y + 158, 118, 32);
  }

  private cardRect(i: number): Rect {
    const w = (this.grid.w - GAP * (this.cols - 1)) / this.cols;
    const row = Math.floor(i / this.cols);
    const col = i % this.cols;
    return rect(this.grid.x + col * (w + GAP), this.grid.y + row * (CARD_H + GAP) - this.scroll, w, CARD_H);
  }

  private get maxScroll(): number {
    const rows = Math.ceil(this.entries.length / this.cols);
    return Math.max(0, rows * (CARD_H + GAP) - GAP - this.grid.h);
  }

  private tierBox(t: number): Rect {
    const colW = (this.grid.w - GAP) / 2;
    const h = Math.min(36, (this.grid.h - 6 * 6) / 7);
    return rect(this.grid.x + Math.floor(t / 7) * (colW + GAP), this.grid.y + (t % 7) * (h + 6), colW, h);
  }

  // ------------------------------------------------------------------ input
  pointerDown(id: number, x: number, y: number): void {
    if (this.layer.pointerDown(id, x, y)) return;
    if (inside(this.grid, x, y)) {
      this.drag = { id, y0: y, s0: this.scroll, moved: false, lastY: y, lastT: performance.now() };
      this.velocity = 0;
    }
  }

  pointerMove(id: number, x: number, y: number): void {
    if (this.layer.pointerMove(id, x, y)) return;
    const d = this.drag;
    if (!d || d.id !== id || this.isRandom) return;
    if (Math.abs(y - d.y0) > TAP_SLOP) d.moved = true;
    if (d.moved) {
      this.scroll = Math.max(0, Math.min(this.maxScroll, d.s0 - (y - d.y0)));
      const now = performance.now();
      const dt = Math.max(1, now - d.lastT);
      this.velocity = (-(y - d.lastY) / dt) * 1000;
      d.lastY = y;
      d.lastT = now;
    }
  }

  pointerUp(id: number, x: number, y: number): void {
    if (this.layer.pointerUp(id, x, y)) return;
    const d = this.drag;
    if (!d || d.id !== id) return;
    this.drag = null;
    if (d.moved) return;
    this.velocity = 0;
    if (this.isRandom) {
      for (let t = 0; t < NUM_TIERS; t++) {
        if (inside(this.tierBox(t), x, y) && t !== this.tier) {
          this.tier = t;
          this.makeRandom();
          this.app.audio.play("hover");
        }
      }
      return;
    }
    this.entries.forEach((_, i) => {
      if (!inside(this.cardRect(i), x, y)) return;
      const now = performance.now();
      if (i === this.selected && this.lastTap.i === i && now - this.lastTap.t < 400) this.go();
      this.lastTap = { i, t: now };
      this.selected = i;
      this.app.audio.play("hover");
      this.updateWidgets();
    });
  }

  wheel(dy: number): void {
    if (!this.isRandom) this.scroll = Math.max(0, Math.min(this.maxScroll, this.scroll + dy * 0.5));
  }

  keyDown(code: string): void {
    if (code === "Escape") this.app.switch(new MenuScene(this.app));
    else if (code === "Enter") this.go();
    else if (code === "Tab") {
      this.tabs.index = (this.tabs.index + 1) % this.tabs.labels.length;
      this.selected = 0;
      this.scroll = 0;
      this.updateWidgets();
    } else if (!this.isRandom && this.entries.length) {
      const moves: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -this.cols, ArrowDown: this.cols };
      if (code in moves) {
        this.selected = Math.max(0, Math.min(this.entries.length - 1, this.selected + moves[code]));
        const r = this.cardRect(this.selected);
        if (r.y < this.grid.y) this.scroll -= this.grid.y - r.y;
        if (r.y + r.h > this.grid.y + this.grid.h) this.scroll += r.y + r.h - this.grid.y - this.grid.h;
      }
    } else if (this.isRandom && (code === "ArrowLeft" || code === "ArrowRight")) {
      this.tier = Math.max(0, Math.min(NUM_TIERS - 1, this.tier + (code === "ArrowRight" ? 1 : -1)));
      this.makeRandom();
    }
  }

  update(dt: number): void {
    this.t += dt;
    this.app.background.update(dt);
    this.start.update(dt, true);
    if (!this.drag && Math.abs(this.velocity) > 5) {
      this.scroll = Math.max(0, Math.min(this.maxScroll, this.scroll + this.velocity * dt));
      this.velocity *= Math.pow(0.04, dt);
    }
  }

  // ------------------------------------------------------------------ drawing
  draw(screen: Screen): void {
    const ctx = screen.ui();
    this.app.background.draw(ctx, screen.uiW, screen.uiH);
    const title = this.mode === "single" ? "Einzelspieler" : this.mode === "bot" ? "Rennen gegen den Bot" : "Bot zuschauen";
    drawFancy(ctx, fancyText(title, 24, HEADER), screen.uiW / 2, 1, "midtop");
    if (this.isRandom) this.drawRandom(ctx);
    else this.drawGrid(ctx);
    this.drawDetail(ctx);
    this.layer.draw(ctx);
  }

  private drawGrid(ctx: Ctx): void {
    const entries = this.entries;
    const g = this.grid;
    ctx.save();
    ctx.beginPath();
    ctx.rect(g.x - 4, g.y - 2, g.w + 8, g.h + 4);
    ctx.clip();
    if (!entries.length) {
      const msg = this.tabs.current === OWN_TAB ? "Noch keine eigenen Level – im Level-Editor bauen und speichern." : "Keine Level in diesem Reiter.";
      text(ctx, msg, g.x + 8, g.y + 16, 13, MUTED, false, "topleft", g.w - 16);
    }
    const p = this.app.progress;
    entries.forEach((e, i) => {
      const r = this.cardRect(i);
      if (r.y + r.h < g.y - 4 || r.y > g.y + g.h + 4) return;
      const sel = i === this.selected;
      glassPanel(ctx, r, sel ? 220 : 170, sel ? GOLD : null, 10, 1.5);
      const tw = r.w - 14;
      const thumb = this.thumb(e, tw, 46);
      if (thumb) ctx.drawImage(thumb, r.x + 7, r.y + 7, tw, 46);
      text(ctx, e.title, r.x + 9, r.y + 60, 13, TEXT, true, "topleft", r.w - 18);
      const best = p.bestFrames(e.key);
      text(ctx, best ? formatTime(best) : "offen", r.x + 9, r.y + 80, 11, best ? GREEN : MUTED, true);
      text(ctx, `${e.proven ? "Bot" : "Ziel"} ${formatTime(e.par)}`, r.x + r.w - 9, r.y + 80, 10.5, e.proven ? CYAN : MUTED, false, "topright");
      stars(ctx, r.x + 30, r.y + r.h - 11, p.stars(e.key), 6);
      const rw = p.get(e.key).race_wins;
      if (rw) text(ctx, `${rw}× Bot besiegt`, r.x + r.w - 9, r.y + r.h - 11, 10, GOLD, true, "midright");
    });
    ctx.restore();
    const max = this.maxScroll;
    if (max > 0) {
      const trackH = g.h;
      const h = Math.max(24, (trackH * g.h) / (g.h + max));
      const y = g.y + ((trackH - h) * this.scroll) / max;
      ctx.fillStyle = "rgba(92,224,255,0.6)";
      ctx.beginPath();
      ctx.roundRect(g.x + g.w + 3, y, 3, h, 1.5);
      ctx.fill();
    }
  }

  private thumb(e: LevelEntry, w: number, h: number): HTMLCanvasElement | null {
    try {
      return levelThumbnail(Level.fromText(e.text), e.key, Math.round(w), h);
    } catch {
      return null; // a broken own level
    }
  }

  private drawRandom(ctx: Ctx): void {
    for (let t = 0; t < NUM_TIERS; t++) {
      const box = this.tierBox(t);
      const active = t === this.tier;
      glassPanel(ctx, box, active ? 230 : 120, active ? GOLD : null, 9, 1.5);
      text(ctx, String(t), box.x + 14, box.y + box.h / 2, 15, active ? GOLD : MUTED, true, "center");
      text(ctx, TIER_NAMES[t], box.x + 30, box.y + box.h / 2, 13, active ? TEXT : MUTED, true, "midleft", box.w - 36);
    }
  }

  private drawDetail(ctx: Ctx): void {
    const d = this.detail;
    glassPanel(ctx, d, 210, CYAN, 14);
    const e = this.entry;
    if (!e) {
      text(ctx, "Kein Level ausgewählt", d.x + d.w / 2, d.y + d.h / 2 - 30, 14, MUTED, true, "center");
      return;
    }
    const thumb = this.thumb(e, d.w - 24, 62);
    if (thumb) ctx.drawImage(thumb, d.x + 12, d.y + 12, d.w - 24, 62);
    text(ctx, e.title, d.x + 14, d.y + 82, 16, TEXT, true, "topleft", d.w - 28);
    text(ctx, subtitle(e), d.x + 14, d.y + 102, 10.5, MUTED, false, "topleft", d.w - 28);
    const p = this.app.progress;
    let y = d.y + 124;
    if (this.isRandom) {
      text(ctx, `Stufe ${this.tier} – ${TIER_NAMES[this.tier]}`, d.x + 14, y - 4, 12, TEXT, true, "topleft", d.w - 28);
      text(ctx, `Seed ${this.seed}`, this.dice.rect.x + this.dice.rect.w + 10, this.dice.rect.y + 16, 12, MUTED, false, "midleft");
      y += 74;
    }
    let cols = 0;
    try {
      cols = Math.floor(Level.fromText(e.text).goalX / TILE) + 1;
    } catch {
      // broken own level
    }
    const best = p.bestFrames(e.key);
    const rows: [string, string][] = [["Länge", `${cols} Spalten`], [parLabel(e), formatTime(e.par)], ["Bestzeit", best ? formatTime(best) : "–"]];
    if (this.mode === "single") {
      const s = p.settings;
      rows.push(["Geist", p.ghost(e.key) && s.ghost ? "dein Bestlauf läuft mit" : !s.ghost ? "aus (Einstellungen)" : "nach dem ersten Sieg"]);
    }
    const avail = this.start.rect.y - (this.mode === "bot" ? 52 : 8) - y;
    const lineH = Math.min(19, avail / (rows.length + (this.isRandom ? 0 : 1.2)));
    for (const [label, value] of rows) {
      text(ctx, label, d.x + 14, y, 12, MUTED, false);
      text(ctx, value, d.x + 92, y, 12, TEXT, true, "topleft", d.w - 104);
      y += lineH;
    }
    if (!this.isRandom) stars(ctx, d.x + 60, y + 9, p.stars(e.key), 9);
    if (this.mode === "bot") {
      text(ctx, "Dein Vorsprung:", d.x + 14, this.head.rect.y - 6, 11, MUTED, false, "bottomleft");
      const r = p.get(e.key);
      if (r.races) text(ctx, `${r.race_wins ?? 0} von ${r.races} Rennen gewonnen`, d.x + d.w - 14, this.head.rect.y - 6, 10.5, GOLD, true, "bottomright");
    }
  }
}

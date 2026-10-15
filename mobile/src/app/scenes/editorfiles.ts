// Editor file menu (new, open, save, save as, share / import .txt, delete) and the "open level" list.

import { ROWS } from "../../core/constants";
import { Level } from "../../core/level";
import { pickTextFile, shareText } from "../../platform/files";
import { glassPanel, inside, rect, shade, text, type Rect } from "../../ui/draw";
import type { Screen } from "../../ui/screen";
import { CYAN, GREEN, MUTED, RED, TEXT } from "../../ui/theme";
import { Button, Tabs, TAP_SLOP } from "../../ui/widgets";
import { Scene, type App } from "../app";
import { OWN_TAB, type LevelEntry } from "../levelsIndex";
import type { EditorScene } from "./editor";

const discardOk = (editor: EditorScene) =>
  !editor.model.dirty || window.confirm("Ungespeicherte Änderungen verwerfen?");

export class EditorFileScene extends Scene {
  overlay = true;
  private box = rect(0, 0, 0, 0);
  private items: Button[] = [];

  constructor(app: App, private readonly editor: EditorScene) {
    super(app);
    const own = !!editor.ownLevel;
    const entries: [string, () => void, boolean?][] = [
      ["Neues Level", () => {
        if (!discardOk(editor)) return;
        editor.newLevel();
        this.dismiss();
      }],
      ["Level öffnen …", () => {
        this.app.pop();
        this.app.push(new EditorOpenScene(this.app, editor));
      }],
      [own ? "Speichern" : "Speichern …", () => {
        if (editor.save()) this.dismiss();
      }, true],
      ["Speichern unter …", () => {
        if (editor.save(true)) this.dismiss();
      }],
      ["Als .txt teilen", () => {
        const name = editor.title.replace(/[^\wäöüÄÖÜß -]+/g, "").trim().replace(/\s+/g, "_") || "level";
        void shareText(`${name}.txt`, editor.model.toText()).then((ok) => ok && editor.flash("Level-Datei geteilt.", GREEN));
        this.dismiss();
      }],
      [".txt importieren", () => {
        if (!discardOk(editor)) return;
        void pickTextFile(".txt,text/plain").then((raw) => {
          if (raw === null) return;
          try {
            Level.fromText(raw); // checks rows and chest
            editor.load(raw, null, "Importiertes Level", null);
            editor.flash("Importiert – „Speichern“ legt es unter „Eigene“ ab.", GREEN);
          } catch (e) {
            editor.flash(`Keine gültige Level-Datei: ${e instanceof Error ? e.message : e}`, RED, 5);
          }
        });
        this.dismiss();
      }],
    ];
    if (own) {
      entries.push(["Level löschen", () => {
        if (window.confirm(`„${editor.title}“ wirklich löschen?`)) editor.deleteOwn();
        this.dismiss();
      }]);
    }
    entries.push(["Schließen", () => this.dismiss()]);
    this.items = entries.map(([label, fn, accent]) => this.layer.add(new Button(label, rect(0, 0, 0, 0), () => {
      this.app.audio.play("click");
      fn();
    }, !!accent, 14)));
  }

  private dismiss(): void {
    if (this.app.top === (this as Scene)) this.app.pop();
  }

  layout(): void {
    const s = this.app.screen;
    const cols = 2;
    const bw = 190;
    const bh = 38;
    const rows = Math.ceil(this.items.length / cols);
    const w = cols * bw + (cols - 1) * 10 + 40;
    const h = rows * (bh + 8) - 8 + 74;
    this.box = rect(s.uiW / 2 - w / 2, s.uiH / 2 - h / 2, w, h);
    this.items.forEach((b, i) => {
      b.rect = rect(this.box.x + 20 + (i % cols) * (bw + 10), this.box.y + 54 + Math.floor(i / cols) * (bh + 8), bw, bh);
    });
  }

  pointerUp(id: number, x: number, y: number): void {
    if (!this.layer.pointerUp(id, x, y) && !inside(this.box, x, y)) this.dismiss();
  }

  keyDown(code: string): void {
    if (code === "Escape") this.dismiss();
  }

  draw(screen: Screen): void {
    const ctx = screen.ui();
    shade(ctx, screen.uiW, screen.uiH, 170);
    glassPanel(ctx, this.box, 240, CYAN, 16);
    text(ctx, "Datei", this.box.x + 20, this.box.y + 16, 18, TEXT, true);
    const sub = this.editor.ownLevel ? `„${this.editor.title}“ unter Eigene` : "noch nicht unter „Eigene“ gespeichert";
    text(ctx, sub, this.box.x + this.box.w - 20, this.box.y + 20, 11, MUTED, false, "topright", this.box.w - 110);
    this.layer.draw(ctx);
  }
}

const ROW_H = 40;

/** List of all levels to open: own levels (editable) and the bundled ones (as a template). */
export class EditorOpenScene extends Scene {
  private tabs: Tabs;
  private back: Button;
  private list = rect(0, 0, 0, 0);
  private scroll = 0;
  private drag: { id: number; y0: number; s0: number; moved: boolean } | null = null;

  constructor(app: App, private readonly editor: EditorScene) {
    super(app);
    const labels = [OWN_TAB, ...app.tabs.map((t) => t.name)];
    this.tabs = this.layer.add(new Tabs(labels, 0, 0, app.screen.ctx, () => {
      this.scroll = 0;
      this.app.audio.play("click");
    }));
    if (!app.progress.own.length) this.tabs.index = 1;
    this.back = this.layer.add(new Button("‹ Zurück", rect(0, 0, 0, 0), () => this.app.pop()));
  }

  private get entries(): LevelEntry[] {
    return this.app.levelsOfTab(this.tabs.current);
  }

  layout(): void {
    const s = this.app.screen;
    const left = s.safe.left + 10;
    const right = s.uiW - s.safe.right - 10;
    this.back.rect = rect(left, 6, 92, 32);
    let x = left + 104;
    this.tabs.rects.forEach((r) => {
      r.x = x;
      r.y = 7;
      x += r.w + 5;
    });
    this.tabs.rect = rect(left + 104, 7, x - left - 104, 30);
    this.list = rect(left, 46, right - left, s.uiH - 46 - Math.max(8, s.safe.bottom));
  }

  private rowRect(i: number): Rect {
    return rect(this.list.x, this.list.y + i * (ROW_H + 6) - this.scroll, this.list.w, ROW_H);
  }

  private get maxScroll(): number {
    return Math.max(0, this.entries.length * (ROW_H + 6) - 6 - this.list.h);
  }

  pointerDown(id: number, x: number, y: number): void {
    if (this.layer.pointerDown(id, x, y)) return;
    if (inside(this.list, x, y)) this.drag = { id, y0: y, s0: this.scroll, moved: false };
  }

  pointerMove(id: number, x: number, y: number): void {
    if (this.layer.pointerMove(id, x, y)) return;
    const d = this.drag;
    if (!d || d.id !== id) return;
    if (Math.abs(y - d.y0) > TAP_SLOP) d.moved = true;
    if (d.moved) this.scroll = Math.max(0, Math.min(this.maxScroll, d.s0 - (y - d.y0)));
  }

  pointerUp(id: number, x: number, y: number): void {
    if (this.layer.pointerUp(id, x, y)) return;
    const d = this.drag;
    this.drag = null;
    if (!d || d.id !== id || d.moved) return;
    this.entries.forEach((e, i) => {
      if (!inside(this.rowRect(i), x, y)) return;
      if (!discardOk(this.editor)) return;
      this.app.audio.play("click");
      if (e.ownId) this.editor.load(e.text, e.ownId, e.title, e.solution);
      else {
        this.editor.load(e.text, null, e.title, e.solution);
        this.editor.flash("Vorlage geöffnet – „Speichern“ legt eine eigene Kopie an.", CYAN, 4);
      }
      this.app.pop();
    });
  }

  wheel(dy: number): void {
    this.scroll = Math.max(0, Math.min(this.maxScroll, this.scroll + dy * 0.5));
  }

  keyDown(code: string): void {
    if (code === "Escape") this.app.pop();
  }

  draw(screen: Screen): void {
    const ctx = screen.ui();
    ctx.fillStyle = "rgb(12,14,24)";
    ctx.fillRect(0, 0, screen.uiW, screen.uiH);
    const l = this.list;
    ctx.save();
    ctx.beginPath();
    ctx.rect(l.x - 2, l.y, l.w + 4, l.h);
    ctx.clip();
    const entries = this.entries;
    if (!entries.length) text(ctx, "Noch keine eigenen Level gespeichert.", l.x + 10, l.y + 14, 13, MUTED);
    entries.forEach((e, i) => {
      const r = this.rowRect(i);
      if (r.y + r.h < l.y || r.y > l.y + l.h) return;
      glassPanel(ctx, r, 180, null, 10);
      text(ctx, e.title, r.x + 14, r.y + r.h / 2, 14, TEXT, true, "midleft", r.w * 0.5);
      let cols = 0;
      try {
        cols = Level.fromText(e.text).cols;
      } catch {
        cols = e.text.split("\n").slice(0, ROWS).reduce((m, line) => Math.max(m, line.length), 0);
      }
      const info = `${cols} Spalten · ${e.proven ? "Bot-Weg bewiesen" : "nicht bewiesen"}${e.ownId ? "" : " · Vorlage"}`;
      text(ctx, info, r.x + r.w - 14, r.y + r.h / 2, 11, e.proven ? GREEN : MUTED, false, "midright", r.w * 0.45);
    });
    ctx.restore();
    this.layer.draw(ctx);
  }
}

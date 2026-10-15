// Port of SettingsScene, plus the mobile settings: touch button size and opacity, save export / import.

import { pickTextFile, shareText } from "../../platform/files";
import { glassPanel, rect, shade, text } from "../../ui/draw";
import type { Screen } from "../../ui/screen";
import { ACCENT, CYAN, GREEN, MUTED, RED, TEXT, type RGB } from "../../ui/theme";
import { Button, Chips, Slider, Toggle } from "../../ui/widgets";
import { Scene, type App } from "../app";
import { HEAD_STARTS } from "../progress";

export const APP_VERSION = __APP_VERSION__;

export class SettingsScene extends Scene {
  overlay = true;
  private music: Slider;
  private sfx: Slider;
  private ghost: Toggle;
  private head: Chips<number>;
  private size: Slider;
  private opacity: Slider;
  private stats: Toggle;
  private buttons: Button[];
  private message: [string, RGB] | null = null;
  private box = rect(0, 0, 0, 0);

  constructor(app: App) {
    super(app);
    const s = app.progress.settings;
    const m = app.progress.mobile;
    const ctx = app.screen.ctx;
    this.music = this.layer.add(new Slider(rect(0, 0, 150, 6), s.music, (v) => {
      s.music = Math.round(v * 100) / 100;
      app.audio.updateVolume();
    }));
    this.sfx = this.layer.add(new Slider(rect(0, 0, 150, 6), s.sfx, (v, done) => {
      s.sfx = Math.round(v * 100) / 100;
      app.audio.updateVolume();
      if (done) app.audio.play("jump");
    }));
    this.ghost = this.layer.add(new Toggle(rect(0, 0, 44, 24), s.ghost, (v) => {
      s.ghost = v;
      app.audio.play("click");
    }));
    this.head = this.layer.add(new Chips(ctx, 0, 0, HEAD_STARTS, HEAD_STARTS.map((v) => `${v} s`), s.head_start, (v) => {
      s.head_start = v;
      app.audio.play("click");
    }, 28));
    this.size = this.layer.add(new Slider(rect(0, 0, 150, 6), (m.controls_size - 0.8) / 0.5, (v) => {
      m.controls_size = Math.round((0.8 + v * 0.5) * 100) / 100;
      app.applyControlSettings();
    }, false));
    this.opacity = this.layer.add(new Slider(rect(0, 0, 150, 6), (m.controls_opacity - 0.15) / 0.65, (v) => {
      m.controls_opacity = Math.round((0.15 + v * 0.65) * 100) / 100;
      app.applyControlSettings();
    }, false));
    this.stats = this.layer.add(new Toggle(rect(0, 0, 44, 24), m.show_stats, (v) => {
      m.show_stats = v;
      app.audio.play("click");
    }));
    this.buttons = [
      this.layer.add(new Button("Spielstand sichern", rect(0, 0, 0, 0), () => void this.exportSave(), false, 13)),
      this.layer.add(new Button("Spielstand laden", rect(0, 0, 0, 0), () => void this.importSave(), false, 13)),
      this.layer.add(new Button("Fertig", rect(0, 0, 0, 0), () => this.finish(), true)),
    ];
  }

  private finish(): void {
    this.app.progress.save();
    this.app.audio.play("click");
    this.app.pop();
  }

  private async exportSave(): Promise<void> {
    const ok = await shareText("space_pirate_save.json", this.app.progress.toJson(true), "application/json");
    this.message = ok ? ["Spielstand exportiert.", GREEN] : ["Export abgebrochen.", MUTED];
  }

  private async importSave(): Promise<void> {
    const raw = await pickTextFile(".json,application/json");
    if (raw === null) return;
    if (this.app.progress.importJson(raw)) {
      this.app.progress.save();
      this.app.applyControlSettings();
      this.app.audio.updateVolume();
      this.message = ["Spielstand geladen und mit dem bisherigen zusammengeführt.", GREEN];
    } else {
      this.message = ["Die Datei ist kein Space-Pirate-Spielstand.", RED];
    }
  }

  layout(): void {
    const s = this.app.screen;
    const w = Math.min(560, s.uiW - s.safe.left - s.safe.right - 24);
    const h = Math.min(380, s.uiH - 10);
    this.box = rect(s.uiW / 2 - w / 2, s.uiH / 2 - h / 2, w, h);
    const b = this.box;
    const x = b.x + 190;
    let y = b.y + 54;
    const row = 31;
    this.music.rect = rect(x, y - 3, Math.min(170, b.w - 270), 6);
    y += row;
    this.sfx.rect = rect(x, y - 3, Math.min(170, b.w - 270), 6);
    y += row;
    this.ghost.rect = rect(x, y - 12, 44, 24);
    y += row;
    this.head.rects.forEach((r, i) => {
      const dx = i === 0 ? 0 : this.head.rects[i - 1].x + this.head.rects[i - 1].w + 6 - x;
      r.x = x + dx;
      r.y = y - 14;
    });
    this.head.rect = rect(x, y - 14, this.head.rects[3].x + this.head.rects[3].w - x, 28);
    y += row;
    this.size.rect = rect(x, y - 3, Math.min(170, b.w - 270), 6);
    y += row;
    this.opacity.rect = rect(x, y - 3, Math.min(170, b.w - 270), 6);
    y += row;
    this.stats.rect = rect(x, y - 12, 44, 24);
    const by = b.y + b.h - 50;
    this.buttons[0].rect = rect(b.x + 18, by, 150, 36);
    this.buttons[1].rect = rect(b.x + 176, by, 150, 36);
    this.buttons[2].rect = rect(b.x + b.w - 18 - 110, by, 110, 36);
  }

  keyDown(code: string): void {
    if (code === "Escape" || code === "Enter") this.finish();
  }

  draw(screen: Screen): void {
    const ctx = screen.ui();
    shade(ctx, screen.uiW, screen.uiH, 215);
    const b = this.box;
    glassPanel(ctx, b, 240, CYAN, 16);
    text(ctx, "Einstellungen", b.x + 20, b.y + 16, 20, TEXT, true);
    text(ctx, `Version ${APP_VERSION}`, b.x + b.w - 18, b.y + 20, 10, MUTED, false, "topright");
    const labels = ["Musik", "Effekte", "Geist der Bestzeit", "Vorsprung gegen Bot", "Tastengröße", "Tasten-Deckkraft", "Leistungsanzeige"];
    labels.forEach((label, i) => text(ctx, label, b.x + 22, b.y + 54 + i * 31, 14, MUTED, true, "midleft"));
    // small preview of the touch buttons
    const k = this.app.progress.mobile.controls_size;
    const a = this.app.progress.mobile.controls_opacity;
    const px = b.x + b.w - 52;
    const py = b.y + 54 + 4.5 * 31;
    ctx.beginPath();
    ctx.arc(px, py, 22 * k, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(20,26,50,${a})`;
    ctx.fill();
    ctx.strokeStyle = `rgba(255,255,255,${Math.min(0.9, a + 0.25)})`;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    if (this.message) text(ctx, this.message[0], b.x + 20, b.y + b.h - 58, 11, this.message[1], true, "bottomleft", b.w - 40);
    else text(ctx, "Steuerung: links wischen = laufen · rechts Tasten = springen / schießen", b.x + 20, b.y + b.h - 58, 11, ACCENT, false, "bottomleft", b.w - 40);
    this.layer.draw(ctx);
  }
}

// Port of MenuScene and DemoPlayer: logo, the main buttons and a panel where the bot replays proven ways.

import { BOT_ACTIONS_V3 } from "../../core/actions";
import { FPS, PLAYER_H, PLAYER_W, SCREEN_H } from "../../core/constants";
import { Level } from "../../core/level";
import { Simulation, Status } from "../../core/sim";
import { drawSprite } from "../../render/assets";
import { Snapshot } from "../../render/renderer";
import { drawLogo, glassPanel, rect, text, type Ctx, type Rect } from "../../ui/draw";
import type { Screen } from "../../ui/screen";
import { CYAN, GOLD, MUTED } from "../../ui/theme";
import { MenuButton } from "../../ui/widgets";
import { Scene, type App } from "../app";
import type { LevelEntry } from "../levelsIndex";
import { EditorScene } from "./editor";
import { LevelSelectScene } from "./levelselect";
import { SettingsScene } from "./settings";

const STEP = 1 / FPS;

/** Replays a stored proven bot solution in a small window (loops through a few levels). */
export class DemoPlayer {
  static LEVELS = ["berg", "festung", "parcours"];
  private items: [LevelEntry, number[]][] = [];
  private index = -1;
  title = "";
  private sim: Simulation | null = null;
  private actions: number[] = [];
  private frame = 0;
  private acc = 0;
  private end = 0;
  private prev: Snapshot | null = null;

  constructor(private readonly app: App) {
    for (const e of app.levelsOfTab("Test-Serie")) {
      if (DemoPlayer.LEVELS.includes(e.stem) && e.solution?.length) this.items.push([e, e.solution]);
    }
    this.next();
  }

  private next(): void {
    if (!this.items.length) return;
    this.index = (this.index + 1) % this.items.length;
    const [entry, actions] = this.items[this.index];
    this.title = entry.title;
    this.actions = actions;
    this.sim = new Simulation(Level.fromText(entry.text, entry.title));
    this.frame = 0;
    this.end = 0;
  }

  update(dt: number): void {
    if (!this.sim) return;
    this.acc += dt;
    while (this.acc >= STEP) {
      this.acc -= STEP;
      this.prev = Snapshot.of(this.sim);
      if (this.sim.status !== Status.RUNNING || Math.floor(this.frame / 2) >= this.actions.length) {
        this.end += 1;
        if (this.end > 45) this.next();
        continue;
      }
      this.sim.step(BOT_ACTIONS_V3[this.actions[Math.floor(this.frame / 2)]]);
      this.frame += 1;
    }
  }

  /** Draw into `r` (UI units); the world is scaled to the panel height. */
  draw(screen: Screen, r: Rect): void {
    if (!this.sim) return;
    const ctx = screen.ctx;
    const k = screen.dpr * screen.uiScale;
    const s = (r.h / SCREEN_H) * k;
    ctx.save();
    ctx.setTransform(k, 0, 0, k, 0, 0);
    ctx.beginPath();
    ctx.roundRect(r.x, r.y, r.w, r.h, 8);
    ctx.clip();
    ctx.setTransform(s, 0, 0, s, r.x * k, r.y * k);
    const renderer = this.app.renderer;
    const old = renderer.pixelScale;
    renderer.pixelScale = s;
    renderer.draw(ctx, this.sim, (r.w * SCREEN_H) / r.h, { alpha: Math.min(1, this.acc / STEP), prev: this.prev }, this.sim.status === Status.WON ? this.end : 0);
    renderer.pixelScale = old;
    ctx.restore();
    const c = screen.ui();
    c.strokeStyle = "rgb(120,150,220)";
    c.lineWidth = 1.5;
    c.beginPath();
    c.roundRect(r.x, r.y, r.w, r.h, 8);
    c.stroke();
  }
}

export class MenuScene extends Scene {
  updatePoint = true;
  private buttons: MenuButton[];
  private t = 0;
  private demo: DemoPlayer;
  private panel = rect(0, 0, 0, 0);

  constructor(app: App) {
    super(app);
    const a = app.assets;
    const sprite = (tint: "none" | "bot") => (ctx: Ctx, x: number, y: number, h: number) => {
      const w = (h * PLAYER_W) / PLAYER_H;
      drawSprite(ctx, a.player("IDLE", 0, tint), x, y - h / 2, w, h);
      return w;
    };
    const block = (ctx: Ctx, x: number, y: number, h: number) => {
      const s = h * 0.8;
      drawSprite(ctx, a.sprite("block"), x, y - s / 2, s, s);
      return s;
    };
    const go = (fn: () => void) => () => {
      app.audio.play("click");
      fn();
    };
    this.buttons = [
      new MenuButton("Einzelspieler", "Alle Level · Bestzeiten · Geist · Zufallslevel", rect(0, 0, 0, 0), go(() => app.switch(new LevelSelectScene(app, "single"))), sprite("none")),
      new MenuButton("Gegen den Bot", "Wettrennen gegen den KI-Piraten", rect(0, 0, 0, 0), go(() => app.switch(new LevelSelectScene(app, "bot"))), sprite("bot")),
      new MenuButton("Bot zuschauen", "Die KI spielt ein Level deiner Wahl", rect(0, 0, 0, 0), go(() => app.switch(new LevelSelectScene(app, "watch"))), sprite("bot")),
      new MenuButton("Level-Editor", "Eigene Level bauen und prüfen", rect(0, 0, 0, 0), go(() => app.switch(new EditorScene(app))), block),
      new MenuButton("Einstellungen", "Ton, Steuerung, Spielstand", rect(0, 0, 0, 0), go(() => app.push(new SettingsScene(app)))),
    ];
    for (const b of this.buttons) this.layer.add(b);
    this.demo = new DemoPlayer(app);
  }

  enter(): void {
    this.app.audio.music("menu");
  }

  layout(): void {
    const s = this.app.screen;
    const x = s.safe.left + 18;
    const w = Math.min(300, s.uiW * 0.42);
    const h = 44;
    const gap = 7;
    this.buttons.forEach((b, i) => (b.rect = rect(x, 98 + i * (h + gap), w, h)));
    const px = x + w + 26;
    const pw = s.uiW - s.safe.right - 18 - px;
    const ph = Math.min(4 * (h + gap) + h - 22, (pw * 800) / 1500);
    this.panel = rect(px, 98 + 22, pw, ph);
  }

  private botState(): void {
    const b = [this.buttons[1], this.buttons[2]];
    const bot = this.app.bot;
    for (const btn of b) btn.enabled = !!bot?.ready;
    if (bot?.loading) b.forEach((x) => (x.hint = "Der Bot lädt noch …"));
    else if (bot?.error) b.forEach((x) => (x.hint = bot.error!.slice(0, 50)));
    else {
      b[0].hint = "Wettrennen gegen den KI-Piraten";
      b[1].hint = "Die KI spielt ein Level deiner Wahl";
    }
  }

  update(dt: number): void {
    this.t += dt;
    this.app.background.update(dt);
    this.botState();
    for (const b of this.buttons) b.update(dt, false);
    this.demo.update(dt);
  }

  draw(screen: Screen): void {
    const ctx = screen.ui();
    this.app.background.draw(ctx, screen.uiW, screen.uiH);
    drawLogo(ctx, screen.uiW / 2, 50, this.t, 0.74);
    this.layer.draw(ctx);
    const p = this.panel;
    glassPanel(ctx, rect(p.x - 8, p.y - 30, p.w + 16, p.h + 38), 200, CYAN, 12);
    text(ctx, `Demo: der Bot spielt „${this.demo.title}“`, p.x, p.y - 15, 12, CYAN, true, "midleft", p.w);
    this.demo.draw(screen, p);
    const c = screen.ui();
    const { done, stars } = this.app.progress.summary();
    text(c, `${done} Level geschafft  ·  ${stars} Sterne`, screen.safe.left + 20, screen.uiH - Math.max(8, screen.safe.bottom) - 2, 13, GOLD, true, "bottomleft");
    if (!this.app.standalone) {
      text(c, "Tipp: Teilen → „Zum Home-Bildschirm“ für Vollbild & offline", screen.uiW - screen.safe.right - 18, screen.uiH - Math.max(8, screen.safe.bottom) - 2, 10.5, MUTED, false, "bottomright");
    }
  }
}

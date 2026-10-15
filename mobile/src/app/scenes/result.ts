// Port of ResultScene: confetti, time, up to three stars popping in, new best / bot comparison.

import { FPS, TILE } from "../../core/constants";
import { Status } from "../../core/sim";
import { Confetti } from "../../ui/gfx";
import { drawFancy, fancyText, glassPanel, rect, shade, star, text, TITLE_GLOW, TITLE_RED } from "../../ui/draw";
import type { Screen } from "../../ui/screen";
import { CYAN, GOLD, MUTED, RED, TEXT, type RGB } from "../../ui/theme";
import { Button } from "../../ui/widgets";
import { Scene, type App } from "../app";
import { randomEntry, type LevelEntry } from "../levelsIndex";
import { formatTime, starsFor } from "../progress";
import { GameScene } from "./game";
import { LevelSelectScene } from "./levelselect";

export class ResultScene extends Scene {
  overlay = true;
  private t = 0;
  private readonly won: boolean;
  private readonly frames: number;
  private readonly stars: number;
  private shownStars = 0;
  private info: { best?: boolean; oldBest?: number | null; wins?: number; races?: number } = {};
  private confetti: Confetti | null = null;
  private buttons: Button[];

  constructor(app: App, private readonly game: GameScene) {
    super(app);
    const entry = game.entry;
    const progress = app.progress;
    this.won = game.won;
    this.frames = game.runFrames;
    if (game.mode === "single") {
      const r = progress.recordWin(entry.key, this.frames, game.inputs, entry.par);
      this.info = r;
      this.stars = r.stars;
    } else {
      this.info = progress.recordRace(entry.key, this.won, this.frames);
      this.stars = this.won ? starsFor(this.frames, entry.par) : 0;
    }
    if (this.won) this.confetti = new Confetti(app.screen.uiW, app.screen.uiH);
    const mk = (label: string, fn: () => void, accent: boolean) => this.layer.add(new Button(label, rect(0, 0, 0, 0), () => {
      this.app.audio.play("click");
      fn();
    }, accent));
    this.buttons = [
      mk("Nochmal", () => this.again(), !this.won),
      mk("Nächstes Level", () => this.next(), this.won),
      mk("Levelauswahl", () => this.app.switch(new LevelSelectScene(this.app, this.game.mode, this.game.tab)), false),
    ];
    app.audio.music(null);
  }

  private again(): void {
    const g = this.game;
    this.app.switch(new GameScene(this.app, g.entry, g.mode, g.headStart, g.tab));
  }

  private nextEntry(): LevelEntry | null {
    const e = this.game.entry;
    if (e.tier !== undefined) {
      const seed = 1 + Math.floor(Math.random() * 99999);
      this.app.randomSeed = seed;
      return randomEntry(e.tier, seed);
    }
    const entries = this.app.levelsOfTab(this.game.tab);
    const i = entries.findIndex((x) => x.key === e.key);
    return i >= 0 && i + 1 < entries.length ? entries[i + 1] : null;
  }

  private next(): void {
    const g = this.game;
    const nxt = this.nextEntry();
    if (!nxt) this.app.switch(new LevelSelectScene(this.app, g.mode, g.tab));
    else this.app.switch(new GameScene(this.app, nxt, g.mode, g.headStart, g.tab));
  }

  layout(): void {
    const s = this.app.screen;
    const bw = 128;
    let x = s.uiW / 2 - (3 * bw + 2 * 10) / 2;
    const y = s.uiH / 2 + 104;
    for (const b of this.buttons) {
      b.rect = rect(x, y, bw, 38);
      x += bw + 10;
    }
  }

  keyDown(code: string): void {
    if (["Enter", "Space"].includes(code)) (this.won ? this.next() : this.again());
    else if (code === "KeyR") this.again();
    else if (code === "KeyN") this.next();
    else if (code === "Escape") this.app.switch(new LevelSelectScene(this.app, this.game.mode, this.game.tab));
  }

  update(dt: number): void {
    this.t += dt;
    this.confetti?.update(dt);
    const due = this.t > 0.5 ? Math.floor((this.t - 0.5) / 0.35) + 1 : 0;
    while (this.shownStars < Math.min(due, this.stars)) {
      this.shownStars += 1;
      this.app.audio.play("star");
    }
    this.game.update(dt); // the bot keeps running in the background
  }

  draw(screen: Screen): void {
    const ctx = screen.ui();
    shade(ctx, screen.uiW, screen.uiH, 150);
    this.confetti?.draw(ctx);
    const g = this.game;
    const cx = screen.uiW / 2;
    const box = rect(cx - 220, screen.uiH / 2 - 150, 440, 312);
    glassPanel(ctx, box, 235, this.won ? GOLD : RED, 18);
    const title = g.mode === "bot" ? (this.won ? "Bot geschlagen!" : "Der Bot war schneller") : "Geschafft!";
    drawFancy(ctx, fancyText(title, this.won ? 36 : 32, this.won ? TITLE_GLOW : TITLE_RED), cx, box.y - 18, "midtop");
    text(ctx, g.entry.title, cx, box.y + 40, 13, MUTED, true, "midtop", box.w - 30);
    const finished = g.sim.status === Status.WON;
    text(ctx, finished ? formatTime(this.frames) : "nicht im Ziel", cx, box.y + 58, finished ? 38 : 28, finished ? TEXT : MUTED, true, "midtop");
    const sy = box.y + 128;
    for (let i = 0; i < 3; i++) {
      const filled = i < this.shownStars;
      let pop = 1;
      if (filled && i === this.shownStars - 1) pop = 1 + 0.4 * Math.max(0, 1 - (((this.t - 0.5) % 0.35) / 0.2));
      star(ctx, cx + (i - 1) * 54, sy, 20 * pop, filled ? GOLD : [60, 66, 92]);
    }
    const lines: [string, RGB][] = [];
    if (g.mode === "single") {
      const old = this.info.oldBest;
      if (this.info.best) lines.push([`Neue Bestzeit!${old ? `  (vorher ${formatTime(old)})` : ""}`, GOLD]);
      else lines.push([`Bestzeit bleibt ${formatTime(old)}`, MUTED]);
      const label = g.entry.proven ? "Bot-Weg" : "Richtzeit";
      lines.push([`${label}: ${formatTime(g.entry.par)}  ·  3★ bis ${formatTime(Math.trunc(g.entry.par * 1.15))}`, CYAN]);
    } else {
      const bot = g.bot;
      if (bot && bot.won && !finished) {
        const left = Math.max(0, Math.floor((g.level.goalX - g.sim.player.x) / TILE));
        lines.push([`Bot im Ziel nach ${formatTime(bot.finishFrame)} – dir fehlten noch ${left} Spalten`, CYAN]);
      } else if (bot && bot.won) {
        const diff = (this.frames - bot.finishFrame!) / FPS;
        lines.push([`Bot: ${formatTime(bot.finishFrame)}   (${diff >= 0 ? "+" : "−"}${Math.abs(diff).toFixed(2)} s)`, CYAN]);
      } else if (bot) lines.push(["Der Bot war noch unterwegs.", CYAN]);
      lines.push([`Vorsprung ${g.headStart} s · ${g.deaths}× gestorben · ${this.info.wins ?? 0} von ${this.info.races ?? 1} Rennen gewonnen`, MUTED]);
    }
    let y = box.y + 162;
    for (const [msg, color] of lines) {
      text(ctx, msg, cx, y, 13, color, true, "midtop", box.w - 30);
      y += 22;
    }
    this.layer.draw(ctx);
  }
}

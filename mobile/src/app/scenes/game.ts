// Port of GameScene (jumpnrun/app/scenes.py): one run.
//   single  time trial with the ghost of the best run
//   bot     race against the trained bot; deaths send you back to the start
//   watch   (new on mobile) the bot plays the level alone, again and again

import { actionBits, actionFromBits } from "../../core/actions";
import { FPS, TILE } from "../../core/constants";
import { Level } from "../../core/level";
import { Simulation, Status } from "../../core/sim";
import { BotRacer } from "../../bot/brain";
import { Snapshot, cameraX, playerPos, type View } from "../../render/renderer";
import { drawFancy, fancyText, glassPanel, rect, shade, star, text, TITLE_GLOW, TITLE_RED, type Ctx, type Rect } from "../../ui/draw";
import type { Screen } from "../../ui/screen";
import { CYAN, GOLD, GREEN, MUTED, RED, TEXT, YELLOW, css } from "../../ui/theme";
import { Button } from "../../ui/widgets";
import { Scene, type App } from "../app";
import type { LevelEntry } from "../levelsIndex";
import { formatTime } from "../progress";
import { LevelSelectScene } from "./levelselect";
import { PauseScene } from "./pause";
import { ResultScene } from "./result";

export type Mode = "single" | "bot" | "watch";
const STEP = 1 / FPS;
const COUNTDOWN = 3 * FPS;

export class GameScene extends Scene {
  readonly level: Level;
  sim!: Simulation;
  ghost: Simulation | null = null;
  bot: BotRacer | null = null;
  countdown = 0;
  raceFrame = 0;
  inputs: number[] = [];
  respawn = 0;
  deaths = 0;
  finished = false;
  afterEnd = 0;
  deadReason: string | null = null;
  banner: [string, number] = ["", 0];
  resultShown = false;
  /** watch mode: attempts of earlier bots, wins, speed */
  private attemptsBefore = 0;
  wins = 0;
  speed = 1;
  readonly best: number | null;
  private readonly ghostInputs: number[] | null;
  private acc = 0;
  private prev: { sim: Snapshot | null; ghost: Snapshot | null; bot: Snapshot | null } = { sim: null, ghost: null, bot: null };
  private pauseButton: Button;
  private speedButton: Button;
  private deadButtons: Button[];

  constructor(app: App, readonly entry: LevelEntry, readonly mode: Mode = "single", readonly headStart = 0, readonly tab = "") {
    super(app);
    this.level = Level.fromText(entry.text, entry.title);
    const p = app.progress;
    this.ghostInputs = mode === "single" && p.settings.ghost ? p.ghost(entry.key) : null;
    this.best = p.bestFrames(entry.key);
    this.pauseButton = this.layer.add(new Button("II", rect(0, 0, 38, 34), () => this.pause()));
    this.speedButton = this.layer.add(new Button("1×", rect(0, 0, 50, 34), () => this.cycleSpeed()));
    this.speedButton.hidden = mode !== "watch";
    this.deadButtons = [
      this.layer.add(new Button("Nochmal", rect(0, 0, 130, 40), () => this.reset(), true)),
      this.layer.add(new Button("Levelauswahl", rect(0, 0, 130, 40), () => this.toSelect())),
    ];
    this.reset();
  }

  enter(): void {
    this.app.audio.music("game");
  }

  layout(): void {
    const s = this.app.screen;
    this.pauseButton.rect = rect(s.safe.left + 8, 6, 38, 34);
    this.speedButton.rect = rect(s.uiW - s.safe.right - 8 - 50, 48, 50, 34);
    const cx = s.uiW / 2;
    const cy = s.uiH / 2;
    this.deadButtons[0].rect = rect(cx - 140, cy + 34, 132, 40);
    this.deadButtons[1].rect = rect(cx + 8, cy + 34, 132, 40);
    this.app.controls.blocked = [this.pauseButton.rect, ...(this.mode === "watch" ? [this.speedButton.rect] : [])];
  }

  reset(): void {
    this.sim = new Simulation(this.level);
    this.ghost = this.ghostInputs ? new Simulation(this.level) : null;
    this.bot = null;
    const brain = this.app.bot;
    if ((this.mode === "bot" || this.mode === "watch") && brain?.ready) {
      this.bot = new BotRacer(brain, this.level, this.mode === "bot" ? this.headStart * FPS : 0);
    }
    this.countdown = this.mode === "watch" ? 0 : COUNTDOWN;
    this.raceFrame = 0;
    this.inputs = [];
    this.acc = 0;
    this.respawn = 0;
    this.deaths = 0;
    this.finished = false;
    this.afterEnd = 0;
    this.deadReason = null;
    this.banner = ["", 0];
    this.resultShown = false;
    this.prev = { sim: null, ghost: null, bot: null };
    this.app.controls.reset();
    for (const b of this.deadButtons) b.hidden = true;
    this.attemptsBefore = 0;
  }

  private pause(): void {
    if (this.finished || this.deadReason !== null) return;
    this.app.audio.play("click");
    this.app.push(new PauseScene(this.app, this));
  }

  toSelect(): void {
    this.app.switch(new LevelSelectScene(this.app, this.mode, this.tab));
  }

  private cycleSpeed(): void {
    this.speed = this.speed === 1 ? 2 : this.speed === 2 ? 4 : 1;
    this.speedButton.label = `${this.speed}×`;
  }

  hidden(): void {
    if (this.app.top === this && this.mode !== "watch") this.pause();
  }

  // ------------------------------------------------------------------ input
  pointerDown(id: number, x: number, y: number): void {
    if (this.layer.pointerDown(id, x, y)) return;
    if (this.mode !== "watch" && this.deadReason === null) this.app.controls.pointerDown(id, x, y);
  }

  pointerMove(id: number, x: number, y: number): void {
    if (this.layer.pointerMove(id, x, y)) return;
    this.app.controls.pointerMove(id, x, y);
  }

  pointerUp(id: number, x: number, y: number): void {
    if (this.layer.pointerUp(id, x, y)) return;
    this.app.controls.pointerUp(id);
  }

  keyDown(code: string): void {
    if (this.deadReason !== null) {
      if (["KeyR", "Enter", "Space"].includes(code)) this.reset();
      else if (code === "Escape") this.toSelect();
      return;
    }
    if ((code === "Escape" || code === "KeyP") && !this.finished) this.pause();
    else if (code === "KeyR" && !this.finished) this.reset();
    else this.app.controls.keyDown(code);
  }

  keyUp(code: string): void {
    this.app.controls.keyUp(code);
  }

  // ------------------------------------------------------------------ logic
  update(dt: number): void {
    this.acc += Math.min(dt, 0.1) * (this.mode === "watch" ? this.speed : 1);
    while (this.acc >= STEP) {
      this.acc -= STEP;
      this.prev = {
        sim: Snapshot.of(this.sim),
        ghost: this.ghost ? Snapshot.of(this.ghost) : null,
        bot: this.bot ? Snapshot.of(this.bot.sim) : null,
      };
      if (this.mode === "watch") this.tickWatch();
      else this.tick();
    }
  }

  private tickWatch(): void {
    const bot = this.bot;
    if (!bot) return;
    if (bot.won) {
      this.afterEnd += 1;
      if (this.afterEnd === 1) {
        this.wins += 1;
        this.app.audio.play("chest");
        this.banner = [`Geschafft in ${formatTime(bot.finishFrame! - bot.lastStart)}!`, 75];
      }
      if (this.afterEnd > 90) {
        this.attemptsBefore += bot.deaths + 1;
        this.bot = new BotRacer(this.app.bot!, this.level, 0);
        this.afterEnd = 0;
      }
    } else {
      const ev = bot.step();
      if (ev === "died") {
        this.app.audio.play("death");
        this.banner = ["Autsch – neuer Versuch", 35];
      }
    }
    if (this.banner[1] > 0) this.banner = [this.banner[0], this.banner[1] - 1];
  }

  private tick(): void {
    const audio = this.app.audio;
    if (this.countdown > 0) {
      if (this.countdown % FPS === 0) audio.play("beep");
      this.countdown -= 1;
      if (this.countdown === 0) audio.play("go");
      return;
    }
    if (this.deadReason !== null) return;
    if (this.finished) {
      this.afterEnd += 1;
      this.bot?.step();
      if (this.afterEnd === 45 && !this.resultShown) {
        this.resultShown = true;
        this.app.push(new ResultScene(this.app, this));
      }
      return;
    }
    this.raceFrame += 1;
    let sim = this.sim;
    if (this.respawn > 0) {
      this.respawn -= 1;
      if (this.respawn === 0) this.sim = sim = new Simulation(this.level);
    } else {
      const action = this.app.controls.action();
      this.inputs.push(actionBits(action));
      const before = [sim.jumps, sim.killsStomp, sim.killsShot, sim.player.shootCooldown];
      sim.step(action);
      if (sim.jumps > before[0]) audio.play("jump");
      if (sim.killsStomp > before[1]) audio.play("stomp");
      if (sim.killsShot > before[2]) audio.play("hit");
      if (sim.player.shootCooldown > before[3]) audio.play("shoot");
    }
    if (this.ghost && this.ghostInputs) {
      const i = this.raceFrame - 1;
      if (i < this.ghostInputs.length && this.ghost.status === Status.RUNNING) this.ghost.step(actionFromBits(this.ghostInputs[i]));
    }
    if (this.bot) {
      const ev = this.bot.step();
      if (ev === "won" && !this.finished) this.banner = ["Der Bot ist im Ziel!", 60];
      if (this.bot.won && this.raceFrame - this.bot.finishFrame! >= 2 * FPS && sim.status !== Status.WON) {
        audio.play("lose");
        this.finished = true;
        this.afterEnd = 0;
        return;
      }
    }
    if (this.banner[1] > 0) this.banner = [this.banner[0], this.banner[1] - 1];
    if (sim.status === Status.WON) {
      audio.play("chest");
      audio.play(this.won ? "win" : "lose");
      this.finished = true;
      this.afterEnd = 0;
    } else if ((sim.status === Status.DIED_PIT || sim.status === Status.DIED_ENEMY) && this.respawn === 0) {
      audio.play("death");
      this.deaths += 1;
      if (this.mode === "bot") {
        this.respawn = FPS;
        this.banner = ["Autsch – zurück zum Start!", 40];
      } else {
        this.deadReason = sim.status === Status.DIED_PIT ? "Du bist in eine Grube gefallen." : "Ein Gegner hat dich erwischt.";
        this.app.controls.reset();
        for (const b of this.deadButtons) b.hidden = false;
      }
    }
  }

  get attempts(): number {
    return this.attemptsBefore + (this.bot ? this.bot.deaths + 1 : 0);
  }

  get won(): boolean {
    if (this.sim.status !== Status.WON) return false;
    return this.bot === null || !this.bot.won || this.bot.finishFrame! >= this.raceFrame;
  }

  get runFrames(): number {
    return this.mode === "bot" ? this.raceFrame : this.sim.frame;
  }

  // ------------------------------------------------------------------ drawing
  draw(screen: Screen): void {
    const alpha = Math.min(1, this.acc / STEP);
    const viewW = screen.worldW;
    const r = this.app.renderer;
    let ctx = screen.world();
    const watch = this.mode === "watch";
    const focus = watch && this.bot ? this.bot.sim : this.sim;
    const focusView: View = { alpha, prev: watch ? this.prev.bot : this.prev.sim };
    const [fx] = playerPos(focus, focusView);
    const cam = r.snap(cameraX(this.level, fx, viewW));
    r.drawLevel(ctx, this.level, cam, viewW);
    const chestOpen = this.sim.status === Status.WON || (watch && this.bot?.won) ? this.afterEnd : 0;
    r.drawChests(ctx, this.level, cam, chestOpen);
    if (this.ghost && this.ghost.status !== Status.DIED_PIT) {
      r.drawPlayer(ctx, this.ghost, cam, { alpha, prev: this.prev.ghost }, "ghost", 110 / 255);
    }
    if (this.bot) this.drawBot(ctx, cam, viewW, { alpha, prev: this.prev.bot });
    if (watch) {
      if (this.bot) r.drawSimObjects(ctx, this.bot.sim, cam, viewW, { alpha, prev: this.prev.bot });
    } else {
      r.drawSimObjects(ctx, this.sim, cam, viewW, { alpha, prev: this.prev.sim });
      if (this.respawn === 0) r.drawPlayer(ctx, this.sim, cam, { alpha, prev: this.prev.sim });
    }

    ctx = screen.ui();
    this.drawHud(ctx, screen);
    if (!watch && this.deadReason === null && !this.finished) this.app.controls.draw(ctx, this.raceFrame < 4 * FPS);
    const cx = screen.uiW / 2;
    const cy = screen.uiH / 2;
    if (this.countdown > 0) {
      const n = Math.floor(this.countdown / FPS) + 1;
      const k = (this.countdown % FPS) / FPS;
      drawFancy(ctx, fancyText(String(n), 90, TITLE_GLOW), cx, cy - 20, "center", 0.8 + 0.35 * k, Math.min(1, k * 2 + 0.3));
      if (this.mode === "bot" && this.headStart) text(ctx, `Du startest ${this.headStart} s vor dem Bot`, cx, cy + 40, 15, CYAN, true, "center");
    } else if (!watch && this.raceFrame < 20) {
      drawFancy(ctx, fancyText("LOS!", 90, TITLE_GLOW), cx, cy - 20, "center", 1, 1 - this.raceFrame / 20);
    }
    if (this.banner[1] > 0) {
      ctx.font = "700 16px sans-serif";
      const w = Math.min(screen.uiW - 40, ctx.measureText(this.banner[0]).width + 50);
      const box = rect(cx - w / 2, 54, w, 34);
      glassPanel(ctx, box, 220, YELLOW, 12);
      text(ctx, this.banner[0], cx, box.y + box.h / 2 + 0.5, 16, YELLOW, true, "center");
    }
    if (this.deadReason !== null) {
      shade(ctx, screen.uiW, screen.uiH, 140);
      const box = rect(cx - 170, cy - 92, 340, 184);
      glassPanel(ctx, box, 235, RED, 16);
      drawFancy(ctx, fancyText("Autsch!", 38, TITLE_RED), cx, box.y - 12, "midtop");
      text(ctx, this.deadReason, cx, box.y + 70, 15, TEXT, true, "midtop");
    }
    this.layer.draw(ctx);
  }

  private drawBot(ctx: Ctx, cam: number, viewW: number, view: View): void {
    const bot = this.bot!;
    if (!bot.visible && !bot.won) return;
    const watch = this.mode === "watch";
    const r = this.app.renderer;
    const [bx, by] = playerPos(bot.sim, view);
    const x = bx - cam;
    if (watch) {
      r.drawPlayer(ctx, bot.sim, cam, view);
      return;
    }
    if (x > -40 && x < viewW) {
      r.drawPlayer(ctx, bot.sim, cam, view, "bot", 150 / 255);
      text(ctx, "BOT", x + 20, by - 6, 22, CYAN, true, "midbottom");
      return;
    }
    const tiles = Math.floor((bot.sim.player.x - this.sim.player.x) / TILE);
    const y = Math.max(150, Math.min(740, by + 30));
    ctx.fillStyle = css(CYAN);
    ctx.beginPath();
    if (x >= viewW) {
      ctx.moveTo(viewW - 10, y);
      ctx.lineTo(viewW - 40, y - 22);
      ctx.lineTo(viewW - 40, y + 22);
      ctx.fill();
      text(ctx, `BOT ${tiles >= 0 ? "+" : ""}${tiles}`, viewW - 50, y, 26, CYAN, true, "midright");
    } else {
      ctx.moveTo(10, y);
      ctx.lineTo(40, y - 22);
      ctx.lineTo(40, y + 22);
      ctx.fill();
      text(ctx, `BOT ${tiles >= 0 ? "+" : ""}${tiles}`, 50, y, 26, CYAN, true, "midleft");
    }
  }

  private drawHud(ctx: Ctx, screen: Screen): void {
    const left = this.pauseButton.rect.x + this.pauseButton.rect.w + 8;
    const bar: Rect = rect(left, 6, screen.uiW - screen.safe.right - 8 - left, 34);
    glassPanel(ctx, bar, 190, null, 10);
    const watch = this.mode === "watch";
    const bot = this.bot;
    const frames = watch ? (bot ? (bot.won ? bot.finishFrame! - bot.lastStart : bot.frame - bot.lastStart) : 0) : this.runFrames;
    text(ctx, formatTime(Math.max(0, frames)), bar.x + 12, bar.y + bar.h / 2 + 1, 19, TEXT, true, "midleft");
    const par = this.entry.par;
    // progress bar from the start to the chest
    const rightW = Math.min(250, bar.w * 0.36);
    const track = rect(bar.x + 100, bar.y + bar.h / 2 - 2.5, Math.max(60, bar.w - 100 - rightW - 26), 5);
    ctx.fillStyle = "rgb(50,56,84)";
    ctx.beginPath();
    ctx.roundRect(track.x, track.y, track.w, track.h, 2.5);
    ctx.fill();
    const x0 = this.level.spawn[0];
    const x1 = Math.max(this.level.goalX, x0 + 1);
    const mark = (px: number, color: string, rad: number) => {
      const k = Math.max(0, Math.min(1, (px - x0) / (x1 - x0)));
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(track.x + track.w * k, track.y + track.h / 2, rad, 0, Math.PI * 2);
      ctx.fill();
    };
    star(ctx, track.x + track.w + 2, track.y + track.h / 2, 7, GOLD);
    if (this.ghost) mark(this.ghost.player.x, "rgb(200,210,240)", 4);
    if (bot) mark(bot.visible || bot.won ? bot.sim.player.x : x0, css(CYAN), 4.5);
    if (!watch) mark(this.sim.player.x, css(GREEN), 5);
    const right = bar.x + bar.w - 12;
    if (watch) {
      const status = !bot ? "Bot nicht geladen" : `Versuch ${this.attempts} · ${this.wins}× im Ziel`;
      text(ctx, status, right - 58, bar.y + bar.h / 2 + 1, 13, CYAN, true, "midright", rightW);
    } else if (this.mode === "bot") {
      let status: string;
      if (!bot) status = "Bot nicht geladen";
      else if (bot.won) status = `Bot im Ziel: ${formatTime(bot.finishFrame)}`;
      else if (bot.wait > 0) status = `Bot startet in ${(bot.wait / FPS).toFixed(1)} s`;
      else if (bot.respawn) status = "Bot: zurück zum Start";
      else status = `Bot unterwegs · ${bot.deaths}× gestorben`;
      text(ctx, status, right, bar.y + bar.h / 2 + 1, 13, CYAN, true, "midright", rightW);
    } else {
      const best = this.best ? `Best ${formatTime(this.best)}` : "Noch keine Bestzeit";
      text(ctx, best, right, bar.y + 4, 12, this.best ? GOLD : MUTED, true, "topright", rightW);
      if (par) {
        const l3 = Math.trunc(par * 1.15);
        const l2 = Math.trunc(par * 1.5);
        text(ctx, `3★ ≤ ${formatTime(l3)}   2★ ≤ ${formatTime(l2)}`, right, bar.y + bar.h - 4, 10.5, frames <= l3 ? GREEN : MUTED, false, "bottomright", rightW);
      }
    }
  }
}

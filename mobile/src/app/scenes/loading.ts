// Port of LoadingScene: logo, running pirate on the loading bar, tips. Loads one step after the other.

import { BotBrain } from "../../bot/brain";
import { PLAYER_H, PLAYER_W } from "../../core/constants";
import { Assets, drawSprite } from "../../render/assets";
import { drawLogo, text } from "../../ui/draw";
import type { Screen } from "../../ui/screen";
import { CYAN, MUTED, TEXT, css } from "../../ui/theme";
import { Scene, type App } from "../app";
import { parseBundled } from "../levelsIndex";
import { MenuScene } from "./menu";

const MIN_SECONDS = 1.6;
export const TIPS = [
  "Auf Gegner springen besiegt sie – und gibt einen kleinen Sprung nach oben.",
  "Die Fadenkreuz-Taste schießt. Der Revolver braucht eine Sekunde zum Nachladen.",
  "Der Bot hat das Spiel per Reinforcement Learning gelernt – 50 Millionen Versuche lang.",
  "Drei Sterne gibt es, wenn du höchstens 15 % langsamer bist als der bewiesene Bot-Weg.",
  "Der Geist zeigt deinen besten Lauf – exakt, weil das Spiel deterministisch ist.",
  "Im Editor prüft „Prüfen“, ob der Bot dein Level schaffen kann.",
  "Zufallslevel kommen aus demselben Generator, mit dem der Bot trainiert hat.",
  "Der Bot rechnet direkt auf deinem Handy – ganz ohne Internet.",
];

export class LoadingScene extends Scene {
  private t = 0;
  private done = 0;
  private failed: string | null = null;
  private readonly steps: [string, () => Promise<void> | void][];
  private readonly tip = TIPS[Math.floor(Math.random() * TIPS.length)];
  private readonly stars = Array.from({ length: 160 }, () => [Math.random(), Math.random(), 0.3 + Math.random() * 0.7]);
  private switched = false;

  constructor(app: App, private readonly then?: () => Scene) {
    super(app);
    this.steps = [
      ["Sprites laden", async () => app.setAssets(await Assets.load())],
      ["Klänge synthetisieren", () => app.audio.init()],
      ["Level einlesen", async () => {
        const json = await fetch("./data/levels.json").then((r) => r.json());
        app.tabs = parseBundled(json);
      }],
      ["Bot wecken", () => {
        app.bot = new BotBrain();
        app.bot.start();
      }],
    ];
    void this.run();
  }

  private async run(): Promise<void> {
    for (const [label, fn] of this.steps) {
      await new Promise((r) => setTimeout(r, 60)); // let a frame show before the heavy work
      try {
        await fn();
      } catch (e) {
        this.failed = `${label} fehlgeschlagen: ${e instanceof Error ? e.message : e}`;
        return;
      }
      this.done += 1;
    }
  }

  private get fraction(): number {
    return Math.min(this.done / this.steps.length, this.t / MIN_SECONDS);
  }

  update(dt: number): void {
    this.t += dt;
    if (!this.switched && this.done === this.steps.length && this.t >= MIN_SECONDS) {
      this.switched = true;
      this.app.switch(this.then ? this.then() : new MenuScene(this.app));
    }
  }

  draw(screen: Screen): void {
    const ctx = screen.ui();
    const w = screen.uiW;
    const h = screen.uiH;
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, "rgb(16,14,44)");
    g.addColorStop(1, "rgb(4,4,14)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    for (const [x, y, s] of this.stars) {
      const glow = 0.5 + 0.5 * Math.sin(this.t * 3 * s + x * 100);
      const c = Math.round(90 + 150 * glow * s);
      ctx.fillStyle = `rgb(${c},${c},${Math.min(255, c + 40)})`;
      ctx.fillRect((((x * w - this.t * 20 * s) % w) + w) % w, y * h, s > 0.8 ? 1.5 : 1, s > 0.8 ? 1.5 : 1);
    }
    drawLogo(ctx, w / 2, h * 0.36, this.t, 0.95);
    const bw = Math.min(380, w * 0.55);
    const bar = { x: w / 2 - bw / 2, y: h * 0.66, w: bw, h: 10 };
    ctx.fillStyle = "rgb(30,34,60)";
    ctx.beginPath();
    ctx.roundRect(bar.x, bar.y, bar.w, bar.h, 5);
    ctx.fill();
    const fill = Math.max(10, bar.w * this.fraction);
    ctx.fillStyle = css(CYAN);
    ctx.beginPath();
    ctx.roundRect(bar.x, bar.y, fill, bar.h, 5);
    ctx.fill();
    ctx.strokeStyle = "rgb(120,140,200)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.roundRect(bar.x, bar.y, bar.w, bar.h, 5);
    ctx.stroke();
    if (this.app.assets) {
      const ph = 36;
      const pw = (ph * PLAYER_W) / PLAYER_H;
      drawSprite(ctx, this.app.assets.player("RUN", Math.floor(this.t * 12) % 7), bar.x + fill - pw / 2, bar.y + 2 - ph, pw, ph);
    }
    const label = this.failed ?? (this.done < this.steps.length ? `${this.steps[this.done][0]} …` : "Bereit!");
    text(ctx, label, w / 2, bar.y + 20, 13, this.failed ? [238, 84, 84] : TEXT, true, "midtop", w - 40);
    text(ctx, "Tipp: " + this.tip, w / 2, h - Math.max(14, screen.safe.bottom + 6), 11.5, MUTED, false, "midbottom", w - 60);
  }
}

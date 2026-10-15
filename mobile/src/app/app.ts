// The app shell (port of jumpnrun/app/main.py): scene stack with fades, the frame loop, input routing.

import { Audio } from "../audio/audio";
import { Controls } from "../input/controls";
import type { Assets } from "../render/assets";
import { Renderer } from "../render/renderer";
import { text, type Ctx } from "../ui/draw";
import type { Screen } from "../ui/screen";
import { MUTED, TEXT } from "../ui/theme";
import { WidgetLayer } from "../ui/widgets";
import type { BotBrain } from "../bot/brain";
import { SpaceBackground } from "../ui/gfx";
import { OWN_TAB, ownEntry, type LevelEntry, type Tab } from "./levelsIndex";
import type { Progress } from "./progress";

const FADE_SECONDS = 0.18;

export abstract class Scene {
  /** Draw the scene below first (pause, result, settings). */
  overlay = false;
  /** A good moment to reload for a downloaded update (main menu). */
  updatePoint = false;
  readonly layer = new WidgetLayer();

  constructor(readonly app: App) {}

  enter(): void {}
  /** Called after the screen size changed (and once before the first draw). */
  layout(): void {}
  update(_dt: number): void {}
  abstract draw(screen: Screen): void;
  close(): void {}

  pointerDown(id: number, x: number, y: number): void {
    this.layer.pointerDown(id, x, y);
  }
  pointerMove(id: number, x: number, y: number): void {
    this.layer.pointerMove(id, x, y);
  }
  pointerUp(id: number, x: number, y: number): void {
    this.layer.pointerUp(id, x, y);
  }
  keyDown(_code: string): void {}
  keyUp(_code: string): void {}
  wheel(_dy: number, _x: number, _y: number): void {}
  /** The app went to the background (pause a running game). */
  hidden(): void {}
}

export class App {
  readonly controls: Controls;
  renderer!: Renderer;
  assets!: Assets;
  background!: SpaceBackground;
  /** Started from the home screen (no Safari bars). */
  readonly standalone: boolean =
    window.matchMedia?.("(display-mode: standalone)").matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
  audio: Audio;
  tabs: Tab[] = [];
  tierNames: string[] = [];
  randomTier = 3;
  randomSeed = 1;
  bot: BotBrain | null = null;
  private ownEntries: LevelEntry[] = [];
  private ownSig = "";
  private stack: Scene[] = [];
  private pending: Scene | null = null;
  private fade = 0;
  private last = 0;
  private needsLayout = true;
  /** Smoothed frame time (s) and the longest frame of the last second, for the stats display. */
  private frameTime = 1 / 60;
  private worstFrame = 0;
  private worstShown = 0;
  private worstSince = 0;
  /** A new version was downloaded (service worker); applied the next time the menu is shown. */
  updateReady: (() => void) | null = null;

  constructor(
    readonly screen: Screen,
    readonly progress: Progress,
  ) {
    this.controls = new Controls(screen);
    this.audio = new Audio(progress.settings);
    this.applyControlSettings();
  }

  setAssets(assets: Assets): void {
    this.assets = assets;
    this.renderer = new Renderer(assets);
    this.background = new SpaceBackground(assets.background);
  }

  /** Levels of a tab: the bundled ones, or the own levels from the save. */
  levelsOfTab(tab: string): LevelEntry[] {
    if (tab === OWN_TAB) {
      // cached: building an entry computes the distance map for the par time
      const own = [...this.progress.own].sort((a, b) => b.updated - a.updated);
      const sig = own.map((o) => `${o.id}@${o.updated}`).join(",");
      if (sig !== this.ownSig) {
        const old = new Map(this.ownEntries.map((e) => [e.ownId!, e]));
        this.ownEntries = own.map((o) => {
          const prev = old.get(o.id);
          return prev && prev.text === o.text && prev.title === o.title && prev.proven === !!o.solution?.length
            ? prev
            : ownEntry(o.id, o.title, o.text, o.solution);
        });
        this.ownSig = sig;
      }
      return this.ownEntries;
    }
    return this.tabs.find((t) => t.name === tab)?.levels ?? [];
  }

  applyControlSettings(): void {
    this.controls.settings = { size: this.progress.mobile.controls_size, opacity: this.progress.mobile.controls_opacity };
  }

  // ------------------------------------------------------------------ scene stack
  get top(): Scene {
    return this.stack[this.stack.length - 1];
  }

  /** Replace the whole stack (with a short fade). */
  switch(scene: Scene): void {
    this.pending = scene;
    this.fade = Math.max(this.fade, 0.0001);
  }

  push(scene: Scene): void {
    this.stack.push(scene);
    scene.layout();
    scene.enter();
  }

  pop(): void {
    if (this.stack.length > 1) this.stack.pop()?.close();
  }

  start(first: Scene): void {
    this.stack = [first];
    first.layout();
    first.enter();
    this.bindEvents();
    requestAnimationFrame((t) => this.frame(t));
  }

  private swap(): void {
    // a downloaded update is applied between scenes, never in the middle of a run
    if (this.updateReady && this.pending?.updatePoint) {
      this.updateReady();
      this.updateReady = null;
    }
    for (const s of this.stack) s.close();
    this.controls.reset();
    this.stack = [this.pending!];
    this.pending = null;
    this.top.layout();
    this.top.enter();
  }

  // ------------------------------------------------------------------ loop
  private frame(t: number): void {
    const raw = this.last ? (t - this.last) / 1000 : 1 / 60;
    const dt = Math.min(0.1, raw);
    this.last = t;
    this.frameTime += (raw - this.frameTime) * 0.05;
    this.worstFrame = Math.max(this.worstFrame, raw);
    if (t - this.worstSince > 1000) {
      this.worstShown = this.worstFrame;
      this.worstFrame = 0;
      this.worstSince = t;
    }
    if (this.needsLayout) {
      this.needsLayout = false;
      this.screen.resize();
      for (const s of this.stack) s.layout();
    }
    this.update(dt);
    this.draw();
    requestAnimationFrame((tt) => this.frame(tt));
  }

  private update(dt: number): void {
    if (this.pending) {
      this.fade += dt / FADE_SECONDS;
      if (this.fade >= 1) {
        this.swap();
        this.fade = -1;
      }
    } else if (this.fade < 0) {
      this.fade = Math.min(0, this.fade + dt / FADE_SECONDS);
    }
    if (!this.screen.portrait) this.top.update(dt);
  }

  private draw(): void {
    const screen = this.screen;
    if (this.renderer) this.renderer.pixelScale = (screen.dpr * screen.cssH) / 800;
    let first = this.stack.length - 1;
    while (first > 0 && this.stack[first].overlay) first--;
    for (const s of this.stack.slice(first)) s.draw(screen);
    const ctx = screen.ui();
    const a = Math.abs(this.fade);
    if (a > 0) {
      ctx.fillStyle = `rgba(0,0,0,${Math.min(1, a)})`;
      ctx.fillRect(0, 0, screen.uiW, screen.uiH);
    }
    if (this.progress.mobile.show_stats) this.drawStats(ctx);
    if (screen.portrait) this.drawRotateHint(ctx);
  }

  private drawStats(ctx: Ctx): void {
    const s = this.screen;
    const fps = Math.round(1 / Math.max(1e-3, this.frameTime));
    const bot = this.bot?.ready ? ` · Bot ${this.bot.lastMs.toFixed(1)} ms` : "";
    const msg = `${fps} fps · max ${Math.round(this.worstShown * 1000)} ms${bot} · ${Math.round(s.cssW)}×${Math.round(s.cssH)} @${s.dpr}x`;
    ctx.font = "600 10px ui-monospace, Menlo, monospace";
    const w = ctx.measureText(msg).width + 12;
    ctx.fillStyle = "rgba(0,0,0,0.55)";
    ctx.fillRect(s.uiW / 2 - w / 2, s.uiH - 16 - s.safe.bottom, w, 14);
    text(ctx, msg, s.uiW / 2, s.uiH - 9 - s.safe.bottom, 10, [180, 255, 180], true, "center");
  }

  private drawRotateHint(ctx: Ctx): void {
    const s = this.screen;
    // portrait: the UI space is laid out for the short side, so draw in CSS pixels
    ctx.setTransform(s.dpr, 0, 0, s.dpr, 0, 0);
    ctx.fillStyle = "rgb(8,10,24)";
    ctx.fillRect(0, 0, s.cssW, s.cssH);
    const cx = s.cssW / 2;
    const cy = s.cssH / 2 - 30;
    const t = performance.now() / 1000;
    const angle = (Math.sin(t * 2) * 0.5 + 0.5) * (Math.PI / 2);
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(-angle);
    ctx.strokeStyle = "rgb(92,224,255)";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.roundRect(-28, -48, 56, 96, 10);
    ctx.stroke();
    ctx.restore();
    text(ctx, "Bitte das Handy drehen", cx, cy + 80, 20, TEXT, true, "midtop");
    text(ctx, "Space Pirate wird im Querformat gespielt.", cx, cy + 110, 14, MUTED, false, "midtop");
  }

  // ------------------------------------------------------------------ input
  private bindEvents(): void {
    const canvas = this.screen.canvas;
    const pos = (e: PointerEvent): [number, number] => this.screen.toUi(e.clientX, e.clientY);
    canvas.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      try {
        canvas.setPointerCapture(e.pointerId);
      } catch {
        // synthetic or already released pointer
      }
      if (this.pending || this.screen.portrait) return;
      const [x, y] = pos(e);
      this.top.pointerDown(e.pointerId, x, y);
    });
    canvas.addEventListener("pointermove", (e) => {
      e.preventDefault();
      if (this.pending || this.screen.portrait) return;
      const [x, y] = pos(e);
      this.top.pointerMove(e.pointerId, x, y);
    });
    const up = (e: PointerEvent) => {
      e.preventDefault();
      this.audio.unlock();
      if (this.screen.portrait) return;
      const [x, y] = pos(e);
      this.top.pointerUp(e.pointerId, x, y);
    };
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointercancel", up);
    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const [x, y] = this.screen.toUi(e.clientX, e.clientY);
      this.top.wheel(e.deltaY, x, y);
    }, { passive: false });
    window.addEventListener("keydown", (e) => {
      if (e.repeat && !e.code.startsWith("Arrow")) {
        e.preventDefault();
        return;
      }
      this.audio.unlock();
      if (["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Tab"].includes(e.code)) e.preventDefault();
      if (!this.pending) this.top.keyDown(e.code);
    });
    window.addEventListener("keyup", (e) => this.top.keyUp(e.code));
    window.addEventListener("resize", () => (this.needsLayout = true));
    window.addEventListener("orientationchange", () => (this.needsLayout = true));
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        this.controls.reset();
        for (const s of this.stack) s.hidden();
        this.audio.suspend();
      } else {
        this.audio.resume();
        this.last = 0;
      }
    });
    // no context menu / text selection on long press
    canvas.addEventListener("contextmenu", (e) => e.preventDefault());
  }
}

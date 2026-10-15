// The canvas and its two coordinate systems:
//   world: the game world, 800 units high (13 tiles of 60 + HUD room, as on the desktop), any width
//   ui:    menus, HUD and touch controls, UI_H units high (about the height of an iPhone in points)
// Both are scaled to the canvas height, so the layout is the same on every phone; wider phones show more.

import { SCREEN_H } from "../core/constants";

export const UI_H = 390;

export interface Insets {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export class Screen {
  readonly canvas: HTMLCanvasElement;
  readonly ctx: CanvasRenderingContext2D;
  /** CSS pixels of the canvas. */
  cssW = 1;
  cssH = 1;
  dpr = 1;
  /** UI units per CSS pixel and the UI size. */
  uiScale = 1;
  uiW = 1;
  readonly uiH = UI_H;
  /** World units across the canvas. */
  worldW = 1;
  /** Safe area (notch, home indicator) in UI units. */
  safe: Insets = { left: 0, right: 0, top: 0, bottom: 0 };
  portrait = false;
  private probe: HTMLDivElement;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) throw new Error("no 2d canvas");
    this.ctx = ctx;
    this.probe = document.createElement("div");
    this.probe.style.cssText =
      "position:fixed;left:0;top:0;width:0;height:0;visibility:hidden;pointer-events:none;" +
      "padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)";
    document.body.appendChild(this.probe);
    this.resize();
  }

  resize(): void {
    const w = Math.max(1, window.innerWidth);
    const h = Math.max(1, window.innerHeight);
    this.dpr = Math.min(window.devicePixelRatio || 1, 3);
    this.cssW = w;
    this.cssH = h;
    this.canvas.style.width = `${w}px`;
    this.canvas.style.height = `${h}px`;
    this.canvas.width = Math.round(w * this.dpr);
    this.canvas.height = Math.round(h * this.dpr);
    this.portrait = h > w;
    // in portrait the game is not played (hint to rotate); still lay out for the long side
    this.uiScale = h / UI_H;
    this.uiW = w / this.uiScale;
    this.worldW = (w / h) * SCREEN_H;
    const cs = getComputedStyle(this.probe);
    const px = (v: string) => (parseFloat(v) || 0) / this.uiScale;
    this.safe = { top: px(cs.paddingTop), right: px(cs.paddingRight), bottom: px(cs.paddingBottom), left: px(cs.paddingLeft) };
  }

  /** Draw in UI units from now on. */
  ui(): CanvasRenderingContext2D {
    const s = this.dpr * this.uiScale;
    this.ctx.setTransform(s, 0, 0, s, 0, 0);
    return this.ctx;
  }

  /** Draw in world units from now on. */
  world(): CanvasRenderingContext2D {
    const s = (this.dpr * this.cssH) / SCREEN_H;
    this.ctx.setTransform(s, 0, 0, s, 0, 0);
    return this.ctx;
  }

  /** CSS pixel position -> UI units. */
  toUi(clientX: number, clientY: number): [number, number] {
    return [clientX / this.uiScale, clientY / this.uiScale];
  }

  /** Factor from UI units to world units. */
  get uiToWorld(): number {
    return SCREEN_H / UI_H;
  }
}

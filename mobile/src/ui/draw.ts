// Canvas drawing helpers with the desktop look: text, glass panels, fancy gradient text, stars, shades.

import { ACCENT, CYAN, GOLD, GOLD_DARK, PANEL, PANEL_LINE, TEXT, css, font, type RGB } from "./theme";

export type Ctx = CanvasRenderingContext2D;

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export const rect = (x: number, y: number, w: number, h: number): Rect => ({ x, y, w, h });
export const inside = (r: Rect, x: number, y: number, pad = 0): boolean =>
  x >= r.x - pad && x <= r.x + r.w + pad && y >= r.y - pad && y <= r.y + r.h + pad;
export const inflate = (r: Rect, dx: number, dy = dx): Rect => rect(r.x - dx, r.y - dy, r.w + 2 * dx, r.h + 2 * dy);

export type Anchor = "topleft" | "midleft" | "center" | "midtop" | "topright" | "midright" | "midbottom" | "bottomleft" | "bottomright";
const ANCHORS: Record<Anchor, [CanvasTextAlign, CanvasTextBaseline]> = {
  topleft: ["left", "top"],
  midleft: ["left", "middle"],
  bottomleft: ["left", "bottom"],
  midtop: ["center", "top"],
  center: ["center", "middle"],
  midbottom: ["center", "bottom"],
  topright: ["right", "top"],
  midright: ["right", "middle"],
  bottomright: ["right", "bottom"],
};

export function text(
  ctx: Ctx,
  msg: string,
  x: number,
  y: number,
  size = 16,
  color: RGB | string = TEXT,
  bold = false,
  anchor: Anchor = "topleft",
  maxWidth?: number,
): number {
  ctx.font = font(size, bold);
  ctx.fillStyle = typeof color === "string" ? color : css(color);
  const [align, baseline] = ANCHORS[anchor];
  ctx.textAlign = align;
  ctx.textBaseline = baseline;
  let m = msg;
  if (maxWidth !== undefined && ctx.measureText(m).width > maxWidth) {
    while (m.length > 1 && ctx.measureText(m + "…").width > maxWidth) m = m.slice(0, -1);
    m += "…";
  }
  ctx.fillText(m, x, y);
  return ctx.measureText(m).width;
}

export function textWidth(ctx: Ctx, msg: string, size: number, bold = false): number {
  ctx.font = font(size, bold);
  return ctx.measureText(msg).width;
}

export function roundRectPath(ctx: Ctx, r: Rect, radius: number): void {
  const rad = Math.max(0, Math.min(radius, r.w / 2, r.h / 2));
  ctx.beginPath();
  ctx.moveTo(r.x + rad, r.y);
  ctx.arcTo(r.x + r.w, r.y, r.x + r.w, r.y + r.h, rad);
  ctx.arcTo(r.x + r.w, r.y + r.h, r.x, r.y + r.h, rad);
  ctx.arcTo(r.x, r.y + r.h, r.x, r.y, rad);
  ctx.arcTo(r.x, r.y, r.x + r.w, r.y, rad);
  ctx.closePath();
}

export function panel(ctx: Ctx, r: Rect, color: RGB = PANEL, radius = 8, border: RGB | null = PANEL_LINE): void {
  roundRectPath(ctx, r, radius);
  ctx.fillStyle = css(color);
  ctx.fill();
  if (border) {
    ctx.strokeStyle = css(border);
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

/** Translucent dark-blue panel with a gradient and a coloured border (glass_panel of gfx.py). */
export function glassPanel(ctx: Ctx, r: Rect, alpha = 215, border: RGB | null = ACCENT, radius = 18, lineWidth = 2): void {
  const a = alpha / 255;
  const g = ctx.createLinearGradient(0, r.y, 0, r.y + r.h);
  g.addColorStop(0, `rgba(30,38,74,${a})`);
  g.addColorStop(1, `rgba(12,14,34,${a})`);
  roundRectPath(ctx, r, radius);
  ctx.fillStyle = g;
  ctx.fill();
  if (border) {
    ctx.strokeStyle = css(border);
    ctx.lineWidth = lineWidth;
    ctx.stroke();
  }
}

export function shade(ctx: Ctx, w: number, h: number, alpha = 150, color: RGB = [4, 6, 16]): void {
  ctx.fillStyle = css(color, alpha / 255);
  ctx.fillRect(0, 0, w, h);
}

export function verticalGradient(ctx: Ctx, r: Rect, top: string, bottom: string): void {
  const g = ctx.createLinearGradient(0, r.y, 0, r.y + r.h);
  g.addColorStop(0, top);
  g.addColorStop(1, bottom);
  ctx.fillStyle = g;
  ctx.fillRect(r.x, r.y, r.w, r.h);
}

export function star(ctx: Ctx, cx: number, cy: number, size: number, color: RGB, rotation = 0): void {
  ctx.beginPath();
  for (let k = 0; k < 10; k++) {
    const r = k % 2 === 0 ? size : size * 0.45;
    const a = -Math.PI / 2 + (k * Math.PI) / 5 + rotation;
    const px = cx + r * Math.cos(a);
    const py = cy + r * Math.sin(a);
    if (k === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.fillStyle = css(color);
  ctx.fill();
  ctx.strokeStyle = color === GOLD ? "rgb(40,30,10)" : "rgb(40,44,60)";
  ctx.lineWidth = Math.max(1, size / 12);
  ctx.stroke();
}

export function stars(ctx: Ctx, cx: number, cy: number, count: number, size = 18, total = 3,
  filled: RGB = GOLD, empty: RGB = [70, 76, 100]): void {
  const gap = size * 2 + 6;
  const x0 = cx - (gap * (total - 1)) / 2;
  for (let i = 0; i < total; i++) star(ctx, x0 + i * gap, cy, size, i < count ? filled : empty);
}

export interface FancyOptions {
  top?: RGB;
  bottom?: RGB;
  outline?: RGB;
  glow?: RGB | null;
  outlinePx?: number;
}

const fancyCache = new Map<string, HTMLCanvasElement>();

/** Text with a vertical colour gradient, a dark outline and an optional glow, cached as a bitmap. */
export function fancyText(msg: string, size: number, opts: FancyOptions = {}, pixelRatio = 2): HTMLCanvasElement {
  const top = opts.top ?? [255, 240, 180];
  const bottom = opts.bottom ?? GOLD_DARK;
  const outline = opts.outline ?? [30, 16, 6];
  const glowColor = opts.glow ?? null;
  const outlinePx = opts.outlinePx ?? Math.max(2, size / 22);
  const key = [msg, size, top, bottom, outline, glowColor, outlinePx, pixelRatio].join("|");
  const hit = fancyCache.get(key);
  if (hit) return hit;
  const measure = document.createElement("canvas").getContext("2d")!;
  measure.font = font(size, true);
  const w = Math.ceil(measure.measureText(msg).width);
  const h = Math.ceil(size * 1.25);
  const pad = Math.ceil(outlinePx + size * 0.3);
  const c = document.createElement("canvas");
  c.width = (w + 2 * pad) * pixelRatio;
  c.height = (h + 2 * pad) * pixelRatio;
  const ctx = c.getContext("2d")!;
  ctx.scale(pixelRatio, pixelRatio);
  ctx.font = font(size, true);
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  const x = pad;
  const y = pad + h / 2;
  ctx.lineJoin = "round";
  if (glowColor) {
    ctx.save();
    ctx.shadowColor = css(glowColor, 0.9);
    ctx.shadowBlur = size * 0.35;
    ctx.fillStyle = css(glowColor);
    ctx.fillText(msg, x, y);
    ctx.fillText(msg, x, y);
    ctx.restore();
  }
  ctx.strokeStyle = css(outline);
  ctx.lineWidth = outlinePx * 2;
  ctx.strokeText(msg, x, y);
  const g = ctx.createLinearGradient(0, y - size / 2, 0, y + size / 2);
  g.addColorStop(0, css(top));
  g.addColorStop(1, css(bottom));
  ctx.fillStyle = g;
  ctx.fillText(msg, x, y);
  (c as HTMLCanvasElement & { logicalW: number; logicalH: number }).logicalW = w + 2 * pad;
  (c as HTMLCanvasElement & { logicalW: number; logicalH: number }).logicalH = h + 2 * pad;
  fancyCache.set(key, c);
  return c;
}

/** Draw a fancyText bitmap centred (or anchored) at x, y in logical units. */
export function drawFancy(ctx: Ctx, img: HTMLCanvasElement, x: number, y: number, anchor: "center" | "midtop" = "center", scale = 1, alpha = 1): Rect {
  const m = img as HTMLCanvasElement & { logicalW: number; logicalH: number };
  const w = m.logicalW * scale;
  const h = m.logicalH * scale;
  const left = x - w / 2;
  const top = anchor === "center" ? y - h / 2 : y;
  if (alpha < 1) ctx.globalAlpha = alpha;
  ctx.drawImage(img, left, top, w, h);
  if (alpha < 1) ctx.globalAlpha = 1;
  return rect(left, top, w, h);
}

export const LOGO_SPACE: FancyOptions = { top: [210, 250, 255], bottom: [60, 150, 230], outline: [6, 14, 40], glow: CYAN };
export const LOGO_PIRATE: FancyOptions = { top: [255, 246, 200], bottom: GOLD_DARK, outline: [34, 16, 4], glow: [255, 170, 60] };
export const TITLE_GLOW: FancyOptions = { glow: [255, 170, 60] };
export const TITLE_RED: FancyOptions = { top: [255, 210, 210], bottom: [190, 60, 60], outline: [40, 6, 6] };
export const HEADER: FancyOptions = { top: [240, 248, 255], bottom: [120, 170, 240], outline: [6, 10, 30], outlinePx: 2 };

/** "SPACE PIRATE" logo with a gentle float (Logo of gfx.py). */
export function drawLogo(ctx: Ctx, cx: number, cy: number, t: number, scale = 1): void {
  const bob = Math.sin(t * 1.6) * 3 * scale;
  drawFancy(ctx, fancyText("SPACE", 42, LOGO_SPACE, 3), cx, cy - 24 * scale + bob, "center", scale);
  drawFancy(ctx, fancyText("PIRATE", 56, LOGO_PIRATE, 3), cx, cy + 18 * scale + bob, "center", scale);
}

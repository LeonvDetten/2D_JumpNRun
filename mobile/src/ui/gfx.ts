// Port of the app visuals of jumpnrun/app/gfx.py: drifting space background, level thumbnails, confetti.

import { ROWS } from "../core/constants";
import type { Level } from "../core/level";
import { CYAN, GOLD, type RGB, css } from "./theme";
import type { Ctx } from "./draw";

export class SpaceBackground {
  private stars: [number, number, number, number][] = [];
  t = 0;

  constructor(private readonly image: CanvasImageSource & { width: number; height: number }) {
    let s = 7;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    const speeds = [0.2, 0.5, 1.0];
    for (let i = 0; i < 140; i++) this.stars.push([rnd(), rnd(), speeds[Math.floor(rnd() * 3)], rnd() * 6.28]);
  }

  update(dt: number): void {
    this.t += dt;
  }

  /** Fills (0, 0, w, h) in the current coordinate system. */
  draw(ctx: Ctx, w: number, h: number): void {
    const iw = w * 1.15;
    const ih = h * 1.15;
    const ox = (Math.sin(this.t * 0.05) * 0.5 + 0.5) * (iw - w);
    const oy = (Math.cos(this.t * 0.037) * 0.5 + 0.5) * (ih - h);
    ctx.drawImage(this.image, -ox, -oy, iw, ih);
    ctx.fillStyle = "rgba(4,6,18,0.47)";
    ctx.fillRect(0, 0, w, h);
    for (const [x, y, speed, phase] of this.stars) {
      const sx = (((x * w - this.t * 6 * speed) % w) + w) % w;
      const glow = 0.5 + 0.5 * Math.sin(this.t * (1.5 + speed * 2) + phase);
      const c = Math.round(120 + 135 * glow * speed);
      ctx.fillStyle = `rgb(${c},${c},${Math.min(255, c + 30)})`;
      const r = speed < 1 ? 0.6 : 1.1;
      ctx.beginPath();
      ctx.arc(sx, y * h, r, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

const thumbCache = new Map<string, HTMLCanvasElement>();

/** Small picture of the whole level (blocks, enemies, chest, start), fitted into w x h (cached). */
export function levelThumbnail(level: Level, key: string, w: number, h: number, scale = 2): HTMLCanvasElement {
  const ck = `${key}:${w}x${h}`;
  const hit = thumbCache.get(ck);
  if (hit) return hit;
  const c = document.createElement("canvas");
  c.width = Math.round(w * scale);
  c.height = Math.round(h * scale);
  const ctx = c.getContext("2d")!;
  ctx.scale(scale, scale);
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, "rgb(22,26,58)");
  g.addColorStop(1, "rgb(10,12,30)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  let used = 0;
  for (let r = 0; r < ROWS; r++) for (let col = 0; col < level.cols; col++) if (level.solid[r][col]) used = Math.max(used, col);
  const cols = Math.max(used + 2, Math.floor(level.goalX / 60) + 3, 10);
  const tx = Math.min(w / cols, h / ROWS);
  const ty = Math.min(h / ROWS, tx * 3);
  const ox = (w - cols * tx) / 2;
  const oy = (h - ROWS * ty) / 2;
  ctx.fillStyle = "rgb(150,160,196)";
  for (let r = 0; r < ROWS; r++) {
    const row = level.solid[r];
    let col = 0;
    while (col < Math.min(cols, level.cols)) {
      if (row[col]) {
        const start = col;
        while (col < level.cols && row[col]) col++;
        ctx.fillRect(ox + start * tx, oy + r * ty, Math.max(0.5, (col - start) * tx), Math.max(0.5, ty));
      }
      col++;
    }
  }
  const px = (x: number, y: number): [number, number] => [ox + (x / 60) * tx, oy + (y / 60) * ty];
  const dot = Math.max(0.8, Math.min(tx, ty) * 0.35);
  ctx.fillStyle = "rgb(240,90,90)";
  for (const [x, y] of level.enemySpawns) {
    const [ex, ey] = px(x + 20, y + 20);
    ctx.beginPath();
    ctx.arc(ex, ey, dot, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = css(GOLD);
  for (const [cx, cy] of level.chests) {
    const [x, y] = px(cx, cy);
    ctx.fillRect(x - 0.5, y - 0.5, Math.max(2, tx), Math.max(2, ty * 0.7));
  }
  const [sx, sy] = px(level.spawn[0] + 20, level.spawn[1] + 30);
  ctx.fillStyle = "rgb(90,230,140)";
  ctx.beginPath();
  ctx.arc(sx, sy, dot + 1, 0, Math.PI * 2);
  ctx.fill();
  if (thumbCache.size > 200) thumbCache.clear();
  thumbCache.set(ck, c);
  return c;
}

export class Confetti {
  static COLORS: RGB[] = [GOLD, CYAN, [255, 110, 150], [130, 240, 140], [190, 140, 255]];
  private parts: { x: number; y: number; vx: number; vy: number; a: number; va: number; c: string }[] = [];

  constructor(w: number, private h: number, n = 120) {
    let s = 3;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < n; i++) {
      this.parts.push({
        x: rnd() * w, y: -rnd() * h, vx: (rnd() - 0.5) * 40, vy: 40 + rnd() * 70,
        a: rnd() * 6.28, va: (rnd() - 0.5) * 12, c: css(Confetti.COLORS[Math.floor(rnd() * 5)]),
      });
    }
  }

  update(dt: number): void {
    for (const p of this.parts) {
      p.x += p.vx * dt + Math.sin(p.a) * 15 * dt;
      p.y += p.vy * dt;
      p.a += p.va * dt;
      if (p.y > this.h + 10) p.y -= this.h + 30;
    }
  }

  draw(ctx: Ctx): void {
    for (const p of this.parts) {
      ctx.fillStyle = p.c;
      ctx.fillRect(p.x, p.y, Math.abs(Math.cos(p.a)) * 4.5 + 1, 3);
    }
  }
}

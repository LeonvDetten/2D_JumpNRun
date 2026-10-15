// Touch widgets in UI units (about iPhone points): buttons, tabs, toggles, sliders, chips.
// A WidgetLayer routes pointers: a tap fires on release over the same widget, drags go to sliders.

import { css, CYAN, GOLD, MUTED, PANEL, PANEL_HI, PANEL_LINE, TEXT, ACCENT } from "./theme";
import { glassPanel, inside, panel, rect, roundRectPath, text, textWidth, type Ctx, type Rect } from "./draw";

export const TAP_SLOP = 12;

export interface Widget {
  rect: Rect;
  enabled?: boolean;
  hidden?: boolean;
  /** Extra hit margin around the rect (touch targets). */
  pad?: number;
  onTap?: (x: number, y: number) => void;
  onDrag?: (x: number, y: number, phase: "down" | "move" | "up") => void;
  draw(ctx: Ctx, pressed: boolean): void;
}

export class WidgetLayer {
  widgets: Widget[] = [];
  private active = new Map<number, { w: Widget; x0: number; y0: number; moved: boolean }>();

  add<T extends Widget>(w: T): T {
    this.widgets.push(w);
    return w;
  }

  hit(x: number, y: number): Widget | null {
    for (let i = this.widgets.length - 1; i >= 0; i--) {
      const w = this.widgets[i];
      if (!w.hidden && w.enabled !== false && inside(w.rect, x, y, w.pad ?? 4)) return w;
    }
    return null;
  }

  isPressed(w: Widget): boolean {
    for (const a of this.active.values()) if (a.w === w && !a.moved) return true;
    return false;
  }

  pointerDown(id: number, x: number, y: number): boolean {
    const w = this.hit(x, y);
    if (!w) return false;
    this.active.set(id, { w, x0: x, y0: y, moved: false });
    w.onDrag?.(x, y, "down");
    return true;
  }

  pointerMove(id: number, x: number, y: number): boolean {
    const a = this.active.get(id);
    if (!a) return false;
    if (Math.hypot(x - a.x0, y - a.y0) > TAP_SLOP) a.moved = true;
    a.w.onDrag?.(x, y, "move");
    return true;
  }

  pointerUp(id: number, x: number, y: number): boolean {
    const a = this.active.get(id);
    if (!a) return false;
    this.active.delete(id);
    a.w.onDrag?.(x, y, "up");
    if (!a.moved && a.w.enabled !== false && inside(a.w.rect, x, y, (a.w.pad ?? 4) + 8)) a.w.onTap?.(x, y);
    return true;
  }

  cancel(): void {
    this.active.clear();
  }

  draw(ctx: Ctx): void {
    for (const w of this.widgets) if (!w.hidden) w.draw(ctx, this.isPressed(w));
  }
}

// ---------------------------------------------------------------------------------------------- buttons
export class Button implements Widget {
  enabled = true;
  hidden = false;
  pad = 6;
  constructor(
    public label: string,
    public rect: Rect,
    public onTap?: () => void,
    public accent = false,
    public size = 15,
  ) {}

  draw(ctx: Ctx, pressed: boolean): void {
    const r = this.rect;
    if (this.accent && this.enabled) panel(ctx, r, pressed ? [60, 130, 230] : [40, 96, 190], 10, CYAN);
    else panel(ctx, r, pressed ? PANEL_HI : PANEL, 10, pressed ? ACCENT : PANEL_LINE);
    text(ctx, this.label, r.x + r.w / 2, r.y + r.h / 2 + 0.5, this.size, this.enabled ? TEXT : MUTED, true, "center", r.w - 12);
  }
}

/** Large glassy menu button with an optional icon and hint line (MenuButton of gfx.py). */
export class MenuButton implements Widget {
  enabled = true;
  hidden = false;
  pad = 4;
  hot = 0;
  glow = false;
  constructor(
    public label: string,
    public hint: string,
    public rect: Rect,
    public onTap?: () => void,
    public icon?: (ctx: Ctx, x: number, y: number, h: number) => number,
  ) {}

  update(dt: number, focused: boolean): void {
    const target = focused && this.enabled ? 1 : 0;
    this.hot += (target - this.hot) * Math.min(1, dt * 12);
  }

  draw(ctx: Ctx, pressed: boolean): void {
    const hot = pressed ? 1 : Math.max(this.hot, this.glow ? 0.6 : 0);
    const r = rect(this.rect.x + 6 * (pressed ? 1 : 0), this.rect.y, this.rect.w, this.rect.h);
    const top: number[] = this.enabled ? [40, 60, 110, 210] : [36, 40, 56, 170];
    const bottom: number[] = this.enabled ? [16, 22, 48, 230] : [24, 26, 36, 170];
    const hi = [70, 120, 220, 235];
    const t = top.map((v, i) => v + (hi[i] - v) * hot);
    if (hot > 0.05) {
      ctx.save();
      ctx.shadowColor = css(CYAN, 0.45 * hot);
      ctx.shadowBlur = 14;
      roundRectPath(ctx, r, 12);
      ctx.fillStyle = "rgba(0,0,0,0.01)";
      ctx.fill();
      ctx.restore();
    }
    const g = ctx.createLinearGradient(0, r.y, 0, r.y + r.h);
    g.addColorStop(0, `rgba(${t[0] | 0},${t[1] | 0},${t[2] | 0},${t[3] / 255})`);
    g.addColorStop(1, `rgba(${bottom[0]},${bottom[1]},${bottom[2]},${bottom[3] / 255})`);
    roundRectPath(ctx, r, 12);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = css(hot > 0.5 ? CYAN : PANEL_LINE);
    ctx.stroke();
    let x = r.x + 14;
    if (this.icon) x += this.icon(ctx, x, r.y + r.h / 2, r.h * 0.62) + 10;
    const color = this.enabled ? TEXT : MUTED;
    text(ctx, this.label, x, r.y + r.h / 2 - (this.hint ? 7 : 0), 18, color, true, "midleft", r.x + r.w - x - 8);
    if (this.hint) text(ctx, this.hint, x + 1, r.y + r.h / 2 + 11, 10.5, this.enabled ? MUTED : [110, 116, 136], false, "midleft", r.x + r.w - x - 8);
  }
}

// ---------------------------------------------------------------------------------------------- tabs
export class Tabs implements Widget {
  index = 0;
  rects: Rect[] = [];
  rect: Rect;
  constructor(public labels: string[], x: number, y: number, ctx: Ctx, public onChange?: (i: number) => void, height = 30, size = 13) {
    let cx = x;
    for (const label of labels) {
      const w = textWidth(ctx, label, size, true) + 24;
      this.rects.push(rect(cx, y, w, height));
      cx += w + 5;
    }
    this.rect = rect(x, y, cx - x, height);
    this.size = size;
  }
  size: number;

  get current(): string {
    return this.labels[this.index];
  }

  onTap = (x: number, y: number): void => {
    this.rects.forEach((r, i) => {
      if (inside(r, x, y, 3) && i !== this.index) {
        this.index = i;
        this.onChange?.(i);
      }
    });
  };

  draw(ctx: Ctx): void {
    this.labels.forEach((label, i) => {
      const r = this.rects[i];
      const active = i === this.index;
      if (active) glassPanel(ctx, r, 235, CYAN, 9, 1.5);
      else panel(ctx, r, PANEL, 9, PANEL_LINE);
      text(ctx, label, r.x + r.w / 2, r.y + r.h / 2 + 0.5, this.size, active ? TEXT : MUTED, true, "center");
    });
  }
}

export class Toggle implements Widget {
  pad = 10;
  hidden = false;
  constructor(public rect: Rect, public value: boolean, public onChange?: (v: boolean) => void) {}

  onTap = (): void => {
    this.value = !this.value;
    this.onChange?.(this.value);
  };

  draw(ctx: Ctx): void {
    const r = this.rect;
    roundRectPath(ctx, r, r.h / 2);
    ctx.fillStyle = this.value ? "rgb(60,150,255)" : "rgb(60,64,84)";
    ctx.fill();
    const kx = this.value ? r.x + r.w - r.h / 2 : r.x + r.h / 2;
    ctx.beginPath();
    ctx.arc(kx, r.y + r.h / 2, r.h / 2 - 3, 0, Math.PI * 2);
    ctx.fillStyle = "rgb(240,244,255)";
    ctx.fill();
    text(ctx, this.value ? "An" : "Aus", r.x + r.w + 10, r.y + r.h / 2, 13, this.value ? TEXT : MUTED, true, "midleft");
  }
}

export class Slider implements Widget {
  pad = 14;
  hidden = false;
  constructor(public rect: Rect, public value: number, public onChange?: (v: number, done: boolean) => void, public showPercent = true) {}

  onDrag = (x: number, _y: number, phase: "down" | "move" | "up"): void => {
    this.value = Math.max(0, Math.min(1, (x - this.rect.x) / this.rect.w));
    this.onChange?.(this.value, phase === "up");
  };

  draw(ctx: Ctx): void {
    const r = this.rect;
    roundRectPath(ctx, r, r.h / 2);
    ctx.fillStyle = "rgb(50,54,76)";
    ctx.fill();
    roundRectPath(ctx, rect(r.x, r.y, Math.max(r.h, r.w * this.value), r.h), r.h / 2);
    ctx.fillStyle = css(CYAN);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(r.x + r.w * this.value, r.y + r.h / 2, r.h * 1.1, 0, Math.PI * 2);
    ctx.fillStyle = "rgb(240,244,255)";
    ctx.fill();
    if (this.showPercent) text(ctx, `${Math.round(this.value * 100)} %`, r.x + r.w + 16, r.y + r.h / 2, 13, TEXT, true, "midleft");
  }
}

/** One-of-n choice (e.g. head start 0/2/5/10 s). */
export class Chips<T> implements Widget {
  rects: Rect[] = [];
  rect: Rect;
  pad = 4;
  hidden = false;
  constructor(ctx: Ctx, x: number, y: number, public options: T[], public labels: string[], public value: T, public onChange?: (v: T) => void, height = 30) {
    let cx = x;
    for (const label of labels) {
      const w = textWidth(ctx, label, 13, true) + 24;
      this.rects.push(rect(cx, y, w, height));
      cx += w + 6;
    }
    this.rect = rect(x, y, cx - x, height);
  }

  onTap = (x: number, y: number): void => {
    this.options.forEach((o, i) => {
      if (inside(this.rects[i], x, y, 3)) {
        this.value = o;
        this.onChange?.(o);
      }
    });
  };

  draw(ctx: Ctx): void {
    this.options.forEach((o, i) => {
      const r = this.rects[i];
      const active = o === this.value;
      panel(ctx, r, active ? [40, 96, 190] : PANEL, r.h / 2, active ? GOLD : PANEL_LINE);
      text(ctx, this.labels[i], r.x + r.w / 2, r.y + r.h / 2 + 0.5, 13, active ? TEXT : MUTED, true, "center");
    });
  }
}

/** A plain drawn element in the layer (no interaction). */
export class Label implements Widget {
  enabled = false;
  constructor(public rect: Rect, public paint: (ctx: Ctx) => void) {}
  draw(ctx: Ctx): void {
    this.paint(ctx);
  }
}

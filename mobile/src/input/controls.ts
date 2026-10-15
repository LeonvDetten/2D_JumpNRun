// Touch controls (UI units) plus keyboard:
//   left half   a floating stick - where the finger lands is the centre, sliding left/right walks
//   right half  two buttons - jump (large, bottom right) and shoot; any other touch on the right jumps
// Keyboard as on the desktop: A/D or arrows walk, W/Space/Up jump, Enter shoots.

import { action, type Action } from "../core/actions";
import type { Ctx, Rect } from "../ui/draw";
import { inside, roundRectPath } from "../ui/draw";
import type { Screen } from "../ui/screen";

type Role = "stick" | "jump" | "shoot" | "ignore";

interface Touch {
  role: Role;
  ox: number;
  oy: number;
  x: number;
  y: number;
}

export interface ControlSettings {
  /** Button size factor (0.8 .. 1.3). */
  size: number;
  /** Opacity of the buttons (0.15 .. 0.8). */
  opacity: number;
}

const DEAD_ZONE = 9;
const STICK_RANGE = 34;

export class Controls {
  private touches = new Map<number, Touch>();
  private keys = new Set<string>();
  settings: ControlSettings = { size: 1, opacity: 0.35 };
  /** Areas that belong to other buttons (pause), never start a control there. */
  blocked: Rect[] = [];
  /** Set when shoot or jump was pressed (for "tap to continue"). */
  pressedSince = false;

  constructor(private readonly screen: Screen) {}

  reset(): void {
    this.touches.clear();
  }

  // ------------------------------------------------------------------ layout
  get jumpButton(): { x: number; y: number; r: number } {
    const s = this.screen;
    const k = this.settings.size;
    const r = 44 * k;
    return { x: s.uiW - s.safe.right - 22 - r, y: s.uiH - Math.max(s.safe.bottom, 8) - 18 - r, r };
  }

  get shootButton(): { x: number; y: number; r: number } {
    const j = this.jumpButton;
    const k = this.settings.size;
    const r = 34 * k;
    return { x: j.x - j.r - 26 * k - r, y: j.y - 38 * k, r };
  }

  private roleAt(x: number, y: number): Role {
    if (this.blocked.some((b) => inside(b, x, y, 6))) return "ignore";
    if (x < this.screen.uiW * 0.45) return "stick";
    const sh = this.shootButton;
    if (Math.hypot(x - sh.x, y - sh.y) <= sh.r * 1.3) return "shoot";
    const j = this.jumpButton;
    if (Math.hypot(x - j.x, y - j.y) <= j.r * 1.3) return "jump";
    // the rest of the right side: whichever button is closer (generous targets)
    return Math.hypot(x - sh.x, y - sh.y) / sh.r < Math.hypot(x - j.x, y - j.y) / j.r ? "shoot" : "jump";
  }

  // ------------------------------------------------------------------ events
  pointerDown(id: number, x: number, y: number): boolean {
    const role = this.roleAt(x, y);
    if (role === "ignore") return false;
    this.touches.set(id, { role, ox: x, oy: y, x, y });
    if (role === "jump" || role === "shoot") this.pressedSince = true;
    return true;
  }

  pointerMove(id: number, x: number, y: number): void {
    const t = this.touches.get(id);
    if (!t) return;
    t.x = x;
    t.y = y;
    if (t.role === "stick") {
      // the centre follows a finger that slides far, so turning around is always quick
      const dx = x - t.ox;
      if (dx > STICK_RANGE) t.ox = x - STICK_RANGE;
      else if (dx < -STICK_RANGE) t.ox = x + STICK_RANGE;
    } else if (t.role === "jump" || t.role === "shoot") {
      // sliding between the two buttons switches between them
      if (x >= this.screen.uiW * 0.45) t.role = this.roleAt(x, y) === "shoot" ? "shoot" : "jump";
    }
  }

  pointerUp(id: number): void {
    this.touches.delete(id);
  }

  keyDown(code: string): void {
    this.keys.add(code);
    if (["KeyW", "Space", "ArrowUp", "Enter"].includes(code)) this.pressedSince = true;
  }

  keyUp(code: string): void {
    this.keys.delete(code);
  }

  /** The input for this frame. */
  action(): Action {
    const k = this.keys;
    let left = k.has("KeyA") || k.has("ArrowLeft");
    let right = k.has("KeyD") || k.has("ArrowRight");
    let jump = k.has("KeyW") || k.has("Space") || k.has("ArrowUp");
    let shoot = k.has("Enter") || k.has("NumpadEnter");
    for (const t of this.touches.values()) {
      if (t.role === "stick") {
        const dx = t.x - t.ox;
        if (dx < -DEAD_ZONE) left = true;
        else if (dx > DEAD_ZONE) right = true;
      } else if (t.role === "jump") jump = true;
      else if (t.role === "shoot") shoot = true;
    }
    if (left && right) left = right = false;
    return action(left, right, jump, shoot);
  }

  get touchActive(): boolean {
    return this.touches.size > 0;
  }

  // ------------------------------------------------------------------ drawing
  draw(ctx: Ctx, showHint: boolean): void {
    const a = this.settings.opacity;
    const act = this.action();
    const stick = [...this.touches.values()].find((t) => t.role === "stick");
    if (stick) {
      const dx = Math.max(-STICK_RANGE, Math.min(STICK_RANGE, stick.x - stick.ox));
      ctx.fillStyle = `rgba(255,255,255,${a * 0.35})`;
      roundRectPath(ctx, { x: stick.ox - STICK_RANGE - 22, y: stick.oy - 22, w: 2 * STICK_RANGE + 44, h: 44 }, 22);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(stick.ox + dx, stick.oy, 20, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${Math.min(0.9, a + 0.3)})`;
      ctx.fill();
    } else if (showHint) {
      const y = this.screen.uiH - Math.max(this.screen.safe.bottom, 8) - 44;
      const x = this.screen.safe.left + 70;
      ctx.fillStyle = `rgba(255,255,255,${a * 0.5})`;
      for (const d of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(x + d * 34, y);
        ctx.lineTo(x + d * 18, y - 13);
        ctx.lineTo(x + d * 18, y + 13);
        ctx.closePath();
        ctx.fill();
      }
      ctx.beginPath();
      ctx.arc(x, y, 9, 0, Math.PI * 2);
      ctx.fill();
    }
    this.drawButton(ctx, this.jumpButton, act.jump, "jump");
    this.drawButton(ctx, this.shootButton, act.shoot, "shoot");
  }

  private drawButton(ctx: Ctx, b: { x: number; y: number; r: number }, pressed: boolean, kind: "jump" | "shoot"): void {
    const a = this.settings.opacity;
    ctx.beginPath();
    ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
    ctx.fillStyle = pressed ? `rgba(92,224,255,${Math.min(0.85, a + 0.35)})` : `rgba(20,26,50,${a})`;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = `rgba(255,255,255,${Math.min(0.9, a + 0.25)})`;
    ctx.stroke();
    ctx.fillStyle = `rgba(255,255,255,${Math.min(0.95, a + 0.45)})`;
    const s = b.r * 0.42;
    if (kind === "jump") {
      ctx.beginPath();
      ctx.moveTo(b.x, b.y - s);
      ctx.lineTo(b.x + s * 0.95, b.y + s * 0.55);
      ctx.lineTo(b.x - s * 0.95, b.y + s * 0.55);
      ctx.closePath();
      ctx.fill();
    } else {
      // a crosshair
      ctx.lineWidth = Math.max(2, b.r * 0.08);
      ctx.strokeStyle = ctx.fillStyle;
      ctx.beginPath();
      ctx.arc(b.x, b.y, s * 0.75, 0, Math.PI * 2);
      ctx.moveTo(b.x - s * 1.15, b.y);
      ctx.lineTo(b.x - s * 0.35, b.y);
      ctx.moveTo(b.x + s * 0.35, b.y);
      ctx.lineTo(b.x + s * 1.15, b.y);
      ctx.moveTo(b.x, b.y - s * 1.15);
      ctx.lineTo(b.x, b.y - s * 0.35);
      ctx.moveTo(b.x, b.y + s * 0.35);
      ctx.lineTo(b.x, b.y + s * 1.15);
      ctx.stroke();
    }
  }
}
